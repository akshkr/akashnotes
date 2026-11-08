---
id: concepts-jobs
title: Jobs
section: Concepts
applies_to: all
updated: 2026-11-05
---

# Jobs

A **job** is one call to a Python function, made by a worker instead of by the code that asked
for it. You turn a function into a job by decorating it with `@app.job`. You run it later by
calling `.enqueue()` with the arguments.

```python
from orbit import Orbit

app = Orbit(broker="redis://localhost:6379/0")

@app.job(retries=3, backoff="exponential", timeout="30s", idempotency_key="order_id")
def send_receipt(order_id: str):
    order = load_order(order_id)
    mailer.send(order.customer_email, render_receipt(order))

# Somewhere in your web handler:
send_receipt.enqueue(order_id="A-1001", priority="high", delay="10s")
```

The decorated function is still a normal function. `send_receipt("A-1001")` runs it
immediately, in-process, with no broker involved. That is handy in unit tests.

## Job options

Options passed to `@app.job` apply to every enqueue of that job:

| Option | Default | Description |
|---|---|---|
| `retries` | `[retries] max_attempts` (3) | Maximum attempts for this job. See [Retries and backoff](retries-and-backoff.md). |
| `backoff` | `"exponential"` | Delay strategy between attempts |
| `timeout` | none | Maximum run time per attempt, e.g. `"30s"`, `"5m"`, `"2h"` |
| `idempotency_key` | none | Name of the argument whose value de-duplicates enqueues. See [Idempotency](idempotency.md). |
| `queue` | `"default"` | Queue the job is sent to. See [Queues and priorities](concepts-queues-priorities.md). |

Options passed to `.enqueue()` apply to that one job:

| Option | Example | Description |
|---|---|---|
| `priority` | `"high"` | `"high"`, `"normal"` (default) or `"low"` |
| `delay` | `"10s"` | Don't run before this much time has passed. See [Delays](scheduling-delays.md). |
| `queue` | `"emails"` | Override the decorator's queue for this enqueue |

Durations are strings with a unit suffix: `ms`, `s`, `m`, `h` or `d`, and units can be combined
(`"1h30m"`). A bare integer is interpreted as seconds.

## Arguments must be JSON

The broker stores job arguments as JSON. Orbit checks this **at enqueue time**, so a bad
argument fails in the caller and doesn't surface later on a worker:

```text
orbit.errors.SerializationError: [ORB-1201] argument 'order' of send_receipt is not
JSON-serializable (type Order)
```

The fix is almost always to **pass identifiers, not objects**. Send `order_id="A-1001"`, not
the `Order` instance. The worker re-reads fresh data when the job runs, which also avoids
acting on stale state.

The serialized payload is also size-checked against `[limits] max_payload_kb` (512 KB by
default). Larger payloads fail with **ORB-1202 PayloadTooLarge**:

```toml
# orbit.toml (3.x)
[limits]
max_payload_kb = 512
```

If you hit ORB-1202, put the large blob in object storage or your database and pass its key.
Raising `max_payload_kb` makes the broker slower for everyone and does not help on brokers
that have their own message size cap (see [Amazon SQS broker](broker-sqs.md)).

## Job lifecycle

Every job moves through a small set of states. You can see them in the
[dashboard](dashboard.md):

| State | Meaning |
|---|---|
| `queued` | In the broker and waiting for a worker, or waiting for its `delay` to pass |
| `leased` | Reserved by a worker that holds a [lease](leases-and-heartbeats.md) on it: prefetched or about to start |
| `running` | Executing; heartbeats keep the lease alive |
| `retrying` | The last attempt failed; waiting out its backoff delay |
| `succeeded` | Returned normally; the return value goes to the [result backend](results-backend.md) |
| `dead` | Out of attempts (**ORB-1301 RetryExhausted**); moved to the [DLQ](dead-letter-queue.md) |

```text
enqueue ─▶ queued ─▶ leased ─▶ running ─▶ succeeded
             ▲                    │
             │                    ▼
             └──── retrying ◀── failed ──(attempts exhausted)──▶ dead (DLQ)
```

Jobs created by a [cron schedule](scheduling-cron.md) enter at `queued` like any other job.

Each job has a short, stable **job ID** such as `j_5f2a0c`. `.enqueue()` returns a handle that
carries it as `handle.id`. The same ID is used in logs, the dashboard,
traces and commands like `orbit dlq replay <job_id>`. The full handle API is in the
[Job API reference](api-reference-job.md).

## Delivery guarantee: at least once

Orbit guarantees that every enqueued job runs **at least once**. It does not guarantee
exactly once. The usual way a job runs twice is that its lease expires while it is still
running, which Orbit logs as **ORB-1101 LeaseExpired**. Another worker then picks it up.

> **Note:** Write every job so that running it twice is harmless. Use the `idempotency_key`
> option to stop duplicate *enqueues*, and use database constraints or upserts inside the job
> to stop duplicate *side effects*. [Duplicate execution](troubleshooting-duplicates.md)
> walks through real cases.

## Timeouts

`timeout` caps a single attempt. When it is exceeded, the worker cancels the attempt and
records it as a failure, which then follows the normal retry policy. Async jobs (`async def`)
are cancelled cleanly. Sync jobs are interrupted at the next Python bytecode boundary, so a
call stuck inside a C extension may overrun.

Keep `timeout` well below `[worker] lease_seconds` unless heartbeats are running. Otherwise
the lease can expire before the timeout fires.

## Jobs versus flows

A job is one function call. If you need several steps with dependencies between them ("create
the account, *then* send the welcome email"), use a [Flow](flows-overview.md) (3.x only).
Don't chain jobs by enqueueing from inside other jobs. Flows track the state of each step and
can resume after a failure.

## See also

- [Workers](concepts-workers.md)
- [Job API reference](api-reference-job.md)
- [Error codes](error-codes.md)
