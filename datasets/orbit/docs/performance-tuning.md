---
id: performance-tuning
title: Performance tuning
section: Operations
applies_to: "3.x"
updated: 2026-11-05
---

# Performance tuning

Most Orbit performance problems are not in Orbit. They come from oversized payloads, chatty
result storage, or concurrency settings that fight the broker. Work through this page in order
and measure after every change.

For adding capacity (more workers, higher concurrency), start with
[scaling-workers.md](scaling-workers.md). This page is about making each job cheaper.

## 1. Measure first

- The dashboard (`orbit dashboard --port 7777`) shows throughput, queue depth and per-job
  duration. See [dashboard.md](dashboard.md).
- With `[telemetry]` configured, every job execution becomes a span, which lets you separate
  time spent *waiting in the queue* from time spent *running*:

```toml
[telemetry]
otlp_endpoint = "http://otel-collector.example.com:4317"
service_name = "atlas-jobs"
```

See [observability-tracing.md](observability-tracing.md). If queue wait dominates, you need more
capacity. If run time dominates, keep reading.

## 2. The knobs that matter

| Setting | Default | Effect of raising it | Effect of lowering it |
|---|---|---|---|
| `[worker] concurrency` | `4` | More parallelism, more memory and broker connections | Less contention |
| `[worker] prefetch` | `10` | Lower pickup latency for short jobs | Fairer distribution of long jobs |
| `[worker] lease_seconds` | `300` | Slower recovery of jobs from dead workers | Risk of duplicate runs (ORB-1101) |
| `[worker] heartbeat_seconds` | `30` | Fewer broker writes, but a lost worker is detected later | More broker writes |
| `[results] ttl_days` | `7` | More storage in the result backend | Results expire sooner |
| `[limits] max_payload_kb` | `512` | Allows bigger arguments, which are slower everywhere | Rejects big payloads early (ORB-1202) |

## 3. Keep payloads small

Every job argument is serialized to JSON, written to the broker, read by a worker, and
possibly copied into the DLQ and the dashboard. A 400 KB payload costs that much on every hop
and every retry.

```python
# Slow: the whole document travels through the broker
summarize.enqueue(document=open("report.txt").read())

# Fast: pass a reference and load it inside the job
summarize.enqueue(document_id="doc_8812")
```

Non-JSON types such as `datetime`, `Decimal` or dataclasses raise `SerializationError`
(ORB-1201). Convert them explicitly, for example to ISO 8601 strings, rather than wrapping
arguments in ad-hoc encoders.

> **Note:** Raising `max_payload_kb` is almost never the right fix for ORB-1202. It moves the
> problem into broker memory. The same limit applies to Flow step results
> ([flows-steps-and-state.md](flows-steps-and-state.md)).

## 4. Heartbeat cost

Each heartbeat is a broker write for every running job. At the default 30 seconds, 1,200
running jobs produce about 40 heartbeat writes per second. That is fine for Redis, but it is
noticeable on Postgres and costs money on SQS.

Keep `heartbeat_seconds` at no more than a third of `lease_seconds`, so one delayed heartbeat
doesn't expire the lease. Don't lower it below 10 seconds unless you have measured a reason
to. Details are in [leases-and-heartbeats.md](leases-and-heartbeats.md).

## 5. Prefetch and fairness

A large prefetch helps with very short jobs because the worker never waits on a network round
trip. With long jobs it backfires: one worker hoards work while others sit idle.

| Typical job duration | Suggested `prefetch` |
|---|---|
| < 100 ms | 20–50 |
| 100 ms – 10 s | 10 (default) |
| > 10 s | 1–2 |

> **Note:** On 3.2.x, `prefetch` values above 100 cause steady worker memory growth (an open
> issue). Treat 100 as a hard ceiling until it is fixed. See
> [troubleshooting-memory.md](troubleshooting-memory.md).

## 6. Result storage

If nothing reads a job's return value, storing it is wasted work. Two options:

- Return `None` from fire-and-forget jobs. There's nothing to serialize.
- Lower `[results] ttl_days` so the backend doesn't grow without bound. Seven days is generous
  for most job types.

When the result backend becomes slow or unavailable, recording results fails with
`ResultBackendUnavailable` (ORB-1601). Workers don't acknowledge those jobs, so they run again
once their lease expires. See [results-backend.md](results-backend.md).

## 7. Retries are load too

Every retry is another full execution. A retry storm against a struggling dependency makes
the outage longer. Exponential backoff with a sensible cap (`[retries] max_delay_seconds`,
default 600) spreads that load out. Make sure jobs fail fast on errors that will never succeed,
such as validation errors, instead of burning all `max_attempts`.
See [retries-and-backoff.md](retries-and-backoff.md).

## Reference numbers

These are illustrative numbers from the project's benchmark harness. They are not guarantees:
4 vCPU host, local Redis broker, no-op jobs, Orbit 3.2.1.

| Config | Jobs/s per worker |
|---|---|
| `concurrency=4`, `prefetch=10` | ~1,900 |
| `concurrency=16`, `prefetch=10` | ~3,400 |
| `concurrency=16`, `prefetch=50` | ~4,100 |
| `concurrency=16`, `prefetch=50`, 200 KB payloads | ~310 |

The last row is the point of section 3: payload size outweighs every other setting.
