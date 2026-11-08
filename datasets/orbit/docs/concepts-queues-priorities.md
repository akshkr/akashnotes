---
id: concepts-queues-priorities
title: Queues and priorities
section: Concepts
applies_to: all
updated: 2026-08-27
---

# Queues and priorities

Orbit gives you two tools to control *what runs first*. Most confusion comes from mixing them
up:

- A **queue** is a named stream of jobs. It decides **which workers** can run a job.
- A **priority** is a per-job label inside a queue. It decides **which job a worker takes
  next** from that queue.

## Queues

Every job goes to exactly one queue. Unless you say otherwise, that queue is `default`. Set a
queue on the decorator, or override it for a single enqueue:

```python
@app.job(queue="emails")
def send_receipt(order_id: str): ...

@app.job(queue="reports", timeout="20m")
def build_monthly_report(account_id: str): ...

# One-off override
send_receipt.enqueue(order_id="A-1001", queue="emails-bulk")
```

Queues need no declaration. A queue exists as soon as something is enqueued to it or a worker
subscribes to it. Queue names may contain lowercase letters, digits, `-` and `_`. On SQS they
are also used to build the SQS queue name, so keep them short (see
[Amazon SQS broker](broker-sqs.md)).

Workers subscribe to queues by name:

```bash
orbit worker --queues default,emails --concurrency 8
```

A job on a queue that no worker subscribes to just waits. Nothing errors. The
[dashboard](dashboard.md) flags queues that have a backlog but no consumers. That is usually
the first place to look when "jobs aren't running".

### How a worker chooses between queues

When a worker listens to several queues, it polls them **round-robin with equal weight**. The
order you list them in `--queues` has **no effect**. `--queues high,default` and
`--queues default,high` behave identically.

This is deliberate. Strict queue ordering lets one busy queue starve the others completely.
If you need a queue to be served faster, give it **dedicated workers**:

```bash
# Pool A: only the latency-sensitive queue
orbit worker --queues high --concurrency 16

# Pool B: everything else, plus spare capacity for high
orbit worker --queues high,default,reports --concurrency 8
```

## Priorities

Within a queue, each job has one of three priorities:

| Priority | Use for |
|---|---|
| `high` | User-facing work someone is waiting on (password resets, receipts) |
| `normal` | The default; most background work |
| `low` | Bulk and backfill work that can wait (re-indexing, exports) |

```python
send_receipt.enqueue(order_id="A-1001", priority="high")
reindex_customer.enqueue(customer_id="c_981", priority="low")
```

When a worker takes a job from a queue, it always takes the **highest-priority job that is
ready**. Among jobs of the same priority, order is roughly FIFO by enqueue time. "Roughly"
because retries, delays and lease redeliveries re-enter the queue at the time they become
ready, not at their original enqueue time.

> **Note:** Priorities are **strict and do not age**. Under a sustained flood of `high` jobs,
> `low` jobs on the same queue can wait indefinitely. Priority aging has been requested, but
> Orbit does not implement it in any release. If starvation matters, put bulk work on its own
> queue with its own workers instead of relying on `low`.

Priority only matters *within* one queue. A `high` job on `reports` does not jump ahead of a
`normal` job on `default`. The worker's round-robin decides which queue it reads next, and
priority decides which job it takes from that queue.

## Broker support

Each broker implements priority differently. The behaviour you see is the same, but there
are performance differences:

| Broker | Priority implementation | Notes |
|---|---|---|
| Redis | Native: one list per queue and priority | Cheapest; no extra cost for using priorities |
| Postgres | Native: `ORDER BY priority, run_at` on claim | Uses an index on `(queue, priority, run_at)` |
| SQS | **Emulated**: one SQS queue per priority level | Triples the number of SQS queues and receive calls |

On SQS, if you never use `high` or `low` on a queue, Orbit never creates the extra SQS queues
for it. See [Amazon SQS broker](broker-sqs.md#priorities) for the naming scheme.

## Concurrency limits

There are two levels of concurrency limit:

- **Per worker process**: `--concurrency` or `[worker] concurrency` (default 4).
- **Per queue, cluster-wide**: the sum of the concurrency of the workers that subscribe to
  that queue. To cap a queue at, say, 10 concurrent jobs (for example to protect a
  rate-limited partner API), run exactly that much worker capacity for it:

```bash
# At most 2 × 5 = 10 concurrent partner-sync jobs
orbit worker --queues partner-sync --concurrency 5   # replica 1
orbit worker --queues partner-sync --concurrency 5   # replica 2
```

## Patterns

| Goal | Do this |
|---|---|
| Keep receipts fast during a bulk export | Separate `emails` and `exports` queues with separate workers |
| Let urgent jobs skip the line occasionally | `priority="high"` on the same queue |
| Throttle calls to a fragile dependency | A dedicated queue with a fixed total concurrency |
| Drain a backlog after an incident | Temporarily start extra workers subscribed to that queue |

## See also

- [Workers](concepts-workers.md)
- [Scaling workers](scaling-workers.md)
- [Delays](scheduling-delays.md)
