---
id: api-reference-job
title: "API reference: jobs"
section: Reference
applies_to: "3.x"
updated: 2026-11-05
---

# API reference: jobs

A **job** is a Python function registered with [`app.job`](api-reference-orbit.md#appjob). The
decorator returns a job object. You can call it directly like the original function, or
`.enqueue()` it to run on a worker.

```python
from orbit import Orbit

app = Orbit(broker="redis://localhost:6379/0")

@app.job(retries=3, backoff="exponential", timeout="30s", idempotency_key="order_id")
def send_receipt(order_id: str): ...

send_receipt.enqueue(order_id="A-1001", priority="high", delay="10s")
```

## `@app.job(...)` parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `retries` | `int` | `[retries] max_attempts` (3) | Maximum attempts for this job. Overrides the config value. |
| `backoff` | `str` | `[retries] backoff` (`"exponential"`) | How the wait between attempts grows. Waits are capped at `[retries] max_delay_seconds` (600). |
| `timeout` | duration `str` | none | Wall-clock limit for one attempt. |
| `idempotency_key` | `str` | none | Name of the keyword argument whose value identifies the work. |
| `queue` | `str` | `"default"` | Queue the job is sent to. See [concepts-queues-priorities.md](concepts-queues-priorities.md). |

### `retries` and `backoff`

When an attempt raises, Orbit schedules the next one after a backoff delay. After the last
attempt fails, the job moves to the dead-letter queue and Orbit logs `RetryExhausted`
(ORB-1301). Backoff strategies other than `"exponential"` and the exact delay formula are on
[retries-and-backoff.md](retries-and-backoff.md).

### `timeout`

Durations are strings with a unit: `"500ms"`, `"30s"`, `"5m"`, `"1h"`. An attempt that runs
past its timeout is stopped and counts as a failed attempt, so it is retried like any other
failure. Inside a Flow, the same limit surfaces as `StepTimeout` (ORB-1502).

> **Note:** `timeout` and the worker lease are separate. A job with `timeout="20m"` on workers
> with `lease_seconds = 300` depends on heartbeats to keep its lease alive for the whole 20
> minutes. If heartbeats stall, the job can be redelivered and run twice (ORB-1101). See
> [leases-and-heartbeats.md](leases-and-heartbeats.md).

### `idempotency_key`

The *name* of an argument, not a value. With `idempotency_key="order_id"`, two enqueues with
`order_id="A-1001"` create one job. If the second enqueue has the same key but different
arguments, it raises `IdempotencyConflict` (ORB-2001). See [idempotency.md](idempotency.md).

## Calling a job directly

```python
send_receipt(order_id="A-1001")
```

A direct call runs the function **in the current process**, synchronously. It skips the broker,
retries, timeout and idempotency handling. This is meant for unit tests and REPL debugging.
In production code, always use `.enqueue()`.

## `.enqueue(**kwargs, priority=None, delay=None, queue=None)`

Serializes the arguments, writes the job to the broker and returns a handle immediately.

| Parameter | Type | Description |
|---|---|---|
| `**kwargs` | JSON-serializable values | The job's arguments. Pass them by keyword. |
| `priority` | `str` or `None` | Priority level, for example `"high"`. `None` uses the default. See [concepts-queues-priorities.md](concepts-queues-priorities.md). |
| `delay` | duration `str` or `None` | Don't make the job available before this much time has passed, for example `"10s"`. See [scheduling-delays.md](scheduling-delays.md). |
| `queue` | `str` or `None` | Send this one job to a different queue from the decorator's. `None` keeps the decorator's queue. |

**Reserved names.** `.enqueue()` consumes `priority`, `delay` and `queue` itself, so a job
function can't have parameters with those names. Rename them, for example to `ticket_priority`.

**Errors raised at enqueue time**

| Code | When |
|---|---|
| ORB-1201 `SerializationError` | An argument isn't JSON-serializable |
| ORB-1202 `PayloadTooLarge` | The serialized arguments exceed `[limits] max_payload_kb` (512) |
| ORB-2001 `IdempotencyConflict` | Same idempotency key, different arguments |
| ORB-1001 `BrokerConnectionError` | The broker can't be reached |

Enqueue errors are raised to the caller **before** anything is written, so a failed enqueue
never leaves a half-written job behind.

### The returned handle

`.enqueue()` returns a handle with an `id` attribute. That's the job ID shown in the dashboard,
logged by workers, and accepted by `orbit dlq replay <job_id>`.

```python
handle = send_receipt.enqueue(order_id="A-1001")
log.info("queued receipt", extra={"job_id": handle.id})
```

## Job lifecycle

| State | Meaning |
|---|---|
| `queued` | Written to the broker, waiting (or delayed) |
| `leased` | Reserved by a worker, either prefetched or about to run |
| `running` | Executing. Heartbeats renew the lease |
| `succeeded` | Finished. The return value is stored for `[results] ttl_days` |
| `retrying` | An attempt failed, and the job waits for its backoff delay |
| `dead` | Retries exhausted, moved to the DLQ (ORB-1301) |

Return values must also be JSON-serializable. Large results are better stored elsewhere, with a
reference returned instead ([results-backend.md](results-backend.md)).
