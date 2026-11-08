---
id: scaling-workers
title: Scaling workers
section: Operations
applies_to: "3.x"
updated: 2026-10-22
---

# Scaling workers

Orbit scales horizontally. You add worker processes, and the broker spreads jobs across them.
There are three levers, and they behave differently:

| Lever | Where it's set | What it controls |
|---|---|---|
| Number of worker processes | your process manager (systemd, Kubernetes replicas) | Total capacity across hosts |
| `concurrency` | `[worker] concurrency` (default `4`) or `--concurrency` | Jobs one worker process runs at once |
| `prefetch` | `[worker] prefetch` (default `10`) | Jobs one worker reserves ahead of time, beyond the ones running |

`--concurrency` on the command line overrides `[worker] concurrency` from `orbit.toml`. Both are
**per worker process**, not per host. Two instances of
`orbit worker --queues default --concurrency 8` on the same machine run up to 16 jobs.

## Capacity arithmetic

```text
max running jobs   = worker_processes × concurrency
max reserved jobs  = worker_processes × (concurrency + prefetch)
```

Reserved jobs are leased to a worker, so no other worker can take them. With 10 workers at
`concurrency = 8` and `prefetch = 10`, up to 180 jobs can be "taken" while only 80 actually
run. When jobs are short this hides network latency. When jobs are long it causes **head-of-line
blocking**: an idle worker has nothing to do while a busy one holds a full buffer.

## Choosing `concurrency`

| Workload | Starting point | Notes |
|---|---|---|
| I/O-bound (HTTP calls, LLM APIs, email) | 8 to 32 | Limited by downstream rate limits, not CPU |
| Mixed | 4 to 8 | The default of 4 is deliberately conservative |
| CPU-bound (image processing, parsing) | number of cores, or fewer | More processes beat more concurrency here |
| Memory-heavy | measure first | Peak memory ≈ concurrency × peak per job |

Raise concurrency step by step and watch queue latency and error rates in the dashboard. When a
downstream API starts returning 429s, more concurrency only turns them into retries
([retries-and-backoff.md](retries-and-backoff.md)).

## Choosing `prefetch`

- **Many tiny jobs (milliseconds):** a higher prefetch, around 20 to 50, keeps workers busy.
- **Long jobs (minutes):** use `prefetch = 1` or `2`. Long-running jobs are also where
  [lease expiry](leases-and-heartbeats.md) bites, and reserved jobs waiting in a busy worker's
  buffer only add to the risk.

> **Note:** On Orbit 3.2.x, keep `prefetch` at or below 100. Higher values trigger a known
> worker memory growth issue that is still open. See
> [troubleshooting-memory.md](troubleshooting-memory.md).

## Separate queues, separate workers

Priorities order jobs within what a worker consumes. Capacity isolation still comes from giving
important queues their own workers:

```bash
# Latency-sensitive work gets dedicated capacity
orbit worker --queues high --concurrency 4

# Everything else; can also pick up high when idle
orbit worker --queues default,high --concurrency 16
```

This is also the practical answer to starvation of low-priority work while priority aging isn't
available ([faq.md](faq.md)). See [concepts-queues-priorities.md](concepts-queues-priorities.md).

## Broker-specific limits

Scaling out increases load on the broker as well as on your code.

| Broker | Watch for |
|---|---|
| Redis | Connection count per worker × workers; `maxclients`; CPU on failover |
| Postgres | Connection limits; poller load on the jobs table; LISTEN/NOTIFY under load |
| SQS | API request limits, especially on FIFO queues (ORB-1901); a single receive call returns at most 10 messages, so prefetch above 10 costs extra API calls |

The SQS row is the one teams hit most when scaling. A FIFO queue throttles long before a standard
queue does, and Orbit reports it as `BrokerRateLimited` (ORB-1901). Fixes are in
[troubleshooting-broker.md](troubleshooting-broker.md).

## Autoscaling

Scale on **queue depth and age of the oldest job**, not on CPU. I/O-bound workers can be
saturated at 5% CPU. Export the queue metrics through OTLP
([observability-metrics.md](observability-metrics.md)) and drive your autoscaler from them. For
Kubernetes, see [deployment-kubernetes.md](deployment-kubernetes.md).

When scaling **down**, make sure the platform sends `SIGTERM` and waits. The worker hands back
its prefetched jobs and finishes the running ones. A hard kill makes in-flight jobs reappear
after `lease_seconds` and run a second time ([troubleshooting-duplicates.md](troubleshooting-duplicates.md)).

## A worked example

A support-ticket enrichment service enqueues about 40 jobs per second. Each job makes one LLM
call that takes about 2 seconds.

- Required concurrency ≈ 40 jobs/s × 2 s = 80 jobs in flight, plus about 25% headroom, so 100.
- With 4 hosts × 1 worker each: `--concurrency 25`.
- Jobs are short and I/O-bound, so keep `prefetch = 10`.
- Lease of 300 s is far above the 2 s runtime, so there's no lease tuning needed.

```toml
[worker]
concurrency = 25
prefetch = 10
lease_seconds = 300
heartbeat_seconds = 30
```

Next: [performance-tuning.md](performance-tuning.md) for per-job overheads such as payload size,
heartbeats and result storage.
