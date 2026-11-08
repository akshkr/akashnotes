---
id: results-backend
title: Result backend
section: Results
applies_to: "3.x"
updated: 2026-10-22
---

# Result backend

The **result backend** stores the return values of jobs and the state of [flow runs](flows-steps-and-state.md). It is separate from the [broker](concepts-brokers.md). The broker moves jobs to workers, and the result backend remembers what happened to them afterwards. You need a result backend if you:

- read a job's return value from the code that enqueued it,
- use [Flows](flows-overview.md), which keep all run state in the result backend, or
- want the [dashboard](dashboard.md) to show job results and flow graphs.

Fire-and-forget workloads that never read results can turn the backend off.

## Configuration

```toml
# orbit.toml
[results]
backend = "redis"   # "redis" (default), "postgres", or "none"
ttl_days = 7        # how long results and finished flow runs are kept
```

| Key | Default | Description |
|---|---|---|
| `backend` | `"redis"` | Where results are stored |
| `ttl_days` | `7` | Retention, counted from when a job or flow run finishes |

The result backend has **no connection settings of its own**. It uses the connection from `[broker] url`:

| `backend` | Requires | Storage |
|---|---|---|
| `"redis"` | a Redis broker | keys `orbit:result:<job_id>` and `orbit:flowrun:<run_id>` in the broker's database |
| `"postgres"` | a Postgres broker | tables `orbit_results` and `orbit_flow_runs` in the broker's database |
| `"none"` | any broker | nothing is stored |

### SQS users

The [SQS broker](broker-sqs.md) has no matching result backend, and 3.2 does not support mixed setups such as an SQS broker with a Redis result backend. With SQS, set `backend = "none"`. **Flows are not available in that configuration**: `flow.run()` raises `ORB-1601 ResultBackendUnavailable`. If an SQS deployment needs results, write them to your own datastore inside the job.

> **Note:** The default is `backend = "redis"` whatever broker you use. A Postgres or SQS deployment that never sets `[results]` gets `ORB-1601` the first time a result is written. `orbit doctor` reports the mismatch before you deploy, so run it in CI.

## Reading results

`enqueue()` returns a handle. Call `.result()` on it to wait for the job to finish:

```python
handle = send_receipt.enqueue(order_id="A-1001")
print(handle.id)                    # "j_5f2a0c"

receipt = handle.result(timeout="30s")
```

- If the job succeeded, you get its return value.
- If the job failed for good (`ORB-1301 RetryExhausted`), `.result()` raises the job's last exception again.
- If the job has not finished within the timeout, you get `TimeoutError`. The job keeps running.

Blocking on `.result()` inside a web request ties up a request thread until a worker picks up the job. That only works for jobs that are short and run on a lightly loaded queue. Otherwise, return `handle.id` to the client and let it poll.

## What gets stored

| Record | Contents | Size limit |
|---|---|---|
| Job result | return value (JSON), final state, attempt count, finish time | `[limits] max_payload_kb` |
| Flow run | inputs, per-step state, per-step results | `max_payload_kb` per step result |

Return values must be JSON-serializable (`ORB-1201 SerializationError`) and no bigger than `max_payload_kb`, 512 KB by default (`ORB-1202 PayloadTooLarge`). Large step results are the most common way flows hit the limit; [Steps and state](flows-steps-and-state.md) shows how to return a reference instead.

## Retention

`ttl_days` is counted from when the job or run **finishes**. Jobs that are queued, running or waiting for a retry, and flows that are still running, never expire. When a record expires:

- `handle.result()` raises `LookupError`.
- `orbit flows status <run_id>` prints `unknown run`.
- `orbit dlq replay` on a step from that run re-enqueues it as a standalone job (see [Error handling in flows](flows-error-handling.md)).

With the Redis backend, expiry uses native key TTLs. With Postgres, workers delete expired rows in batches of 1,000 every few minutes, so expect a short delay before rows disappear.

## Sizing and operating the backend

- **Redis memory.** Roughly (results per day × average result size × `ttl_days`). 200,000 jobs a day with 2 KB results and the default 7 days is about 2.8 GB. Set `maxmemory-policy noeviction`: an eviction policy silently deletes flow run records and causes `ORB-1503 FlowStateCorrupt`.
- **Postgres bloat.** Batch deletes leave dead tuples behind. Keep autovacuum on for `orbit_results`. On large tables, consider lowering `autovacuum_vacuum_scale_factor`.
- **Shared instance.** The result backend shares a server with the broker, so a backlog of results can slow the broker down. If results are large, keep `ttl_days` low.

## When the backend is unavailable

If a worker cannot write a result, it logs `ORB-1601 ResultBackendUnavailable` and **does not acknowledge the job**. The job's lease then expires, and another worker runs it again. This prevents silent result loss, but the job body runs twice, which is one more reason to make jobs [idempotent](idempotency.md). Callers blocked in `.result()` get `ORB-1601` raised once their timeout ends.

## See also

- [Configuration reference](configuration-reference.md#results)
- [Flow steps and state](flows-steps-and-state.md)
- [Performance tuning](performance-tuning.md)
