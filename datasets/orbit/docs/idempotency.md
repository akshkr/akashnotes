---
id: idempotency
title: Idempotency
section: Reliability
applies_to: all
updated: 2026-10-08
---

# Idempotency

Orbit delivers every job **at least once**, which means it will sometimes deliver a job more
than once. A double-clicked "Pay" button enqueues twice. A web request that times out gets
retried by the client. A lease expires on a slow job and a second worker picks it up.
**Idempotency** is how you make "more than once" harmless.

Orbit helps in two places: it de-duplicates **enqueues** using an idempotency key, and it
skips **deliveries** of jobs that have already succeeded. It can't make your job's side
effects idempotent for you. That part is your code.

## Idempotency keys

Name the argument that identifies the unit of work:

```python
@app.job(retries=3, backoff="exponential", timeout="30s", idempotency_key="order_id")
def send_receipt(order_id: str):
    ...

send_receipt.enqueue(order_id="A-1001")   # enqueued
send_receipt.enqueue(order_id="A-1001")   # de-duplicated: returns the same job
```

`idempotency_key` takes the **name** of one argument. The key Orbit stores combines the job
name with that argument's value (`send_receipt:A-1001`), so two different jobs can use the
same `order_id` without colliding.

If the natural key spans several values, pass a combined key argument:

```python
@app.job(idempotency_key="dedupe_key")
def apply_credit(account_id: str, invoice_id: str, dedupe_key: str): ...

apply_credit.enqueue(account_id="acct_7", invoice_id="inv_311",
                     dedupe_key="acct_7:inv_311")
```

## What happens on enqueue

| Situation | Result of `.enqueue()` |
|---|---|
| Key not seen before | Job is enqueued and the key is recorded |
| Key held by a job that is scheduled, queued, running or retrying, **same arguments** | Returns the existing job's handle; nothing new is enqueued |
| Key held by a job that **succeeded** within the retention window, same arguments | Returns the existing handle; the job is not run again |
| Key held by a **dead** job (in the DLQ) | Returns the dead job's handle; rerun it with `orbit dlq replay` |
| Key seen before with **different arguments** | Raises **ORB-2001 IdempotencyConflict** |
| Result backend configured but unreachable | Raises **ORB-1601 ResultBackendUnavailable** |
| `[results] backend = "none"` | No record is kept; enqueues are not de-duplicated (see [Brokers](#brokers)) |

"Same arguments" means the canonical JSON of all arguments is identical. ORB-2001 is
deliberately loud. Two different payloads claiming the same key almost always means a bug,
such as reusing an order ID across tenants:

```text
orbit.errors.IdempotencyConflict: [ORB-2001] key send_receipt:A-1001 already used by job
j_5f2a0c with different arguments
```

> **Note:** Idempotency records live in the **result backend**, not the broker, and expire
> after `[results] ttl_days` (7 days by default). After that, the same key can be enqueued
> again as a new job. If your duplicates can arrive more than a week apart (monthly billing
> runs, for example), raise `ttl_days` or include the period in the key (`"acct_7:2026-10"`).

Orbit **fails closed**: if it can't reach the result backend to check a key, it refuses to
enqueue (ORB-1601) and does not risk a duplicate. Catch that in your web tier and return a
retryable error to the client. See [Result backend](results-backend.md).

## What happens on delivery

Before running a job that has an idempotency key, the worker checks the record. If another
delivery of the same key has already **succeeded**, the worker acknowledges this delivery
without running it and logs `skipped duplicate delivery`.

That covers redeliveries that arrive *after* the first run finished. It can't help when two
deliveries run **at the same time**. The classic case is a long job whose lease expires
mid-run (**ORB-1101 LeaseExpired**), so a second worker starts it while the first is still
going. Both see "not yet succeeded". See
[Leases and heartbeats](leases-and-heartbeats.md) and
[Duplicate execution](troubleshooting-duplicates.md).

## Making side effects idempotent

Guard every external effect so that doing it twice equals doing it once:

```python
@app.job(idempotency_key="order_id")
def send_receipt(order_id: str):
    with db.transaction() as tx:
        inserted = tx.execute(
            "INSERT INTO receipts_sent (order_id, sent_at) VALUES (%s, now()) "
            "ON CONFLICT (order_id) DO NOTHING RETURNING order_id",
            (order_id,),
        ).fetchone()
        if inserted is None:
            return  # another delivery already sent it
        mailer.send(receipt_for(order_id))
```

Patterns, strongest first:

| Pattern | Use when |
|---|---|
| Pass the key to the downstream API (most payment and email providers accept one) | The side effect is in someone else's system |
| Unique constraint plus `INSERT ... ON CONFLICT DO NOTHING` | The effect is a row in your database |
| Upsert to a final state (`SET status = 'shipped'`) instead of incrementing | Updating counters or state |
| Check-then-act inside a transaction with a row lock | Nothing else fits |

> **Note:** If the job sends an email *before* committing the guard row, a crash between the
> two still causes a double send. Commit the guard and the effect together, or push the key
> to the provider.

## Scheduled jobs

Jobs created by [cron schedules](scheduling-cron.md) have no natural key. If a run must
happen at most once per period, take the period as an argument and use it as the key, then
enqueue it from a small scheduled dispatcher job.

## Brokers

Idempotency keys behave the same on Redis and Postgres, with the result backend on the
same server. **SQS** has no result backend, so Orbit keeps no idempotency records there. FIFO
queues get SQS's short-lived deduplication instead, and that interaction is only partly
documented. See [Amazon SQS broker](broker-sqs.md#idempotency-on-sqs).

## See also

- [Jobs](concepts-jobs.md)
- [Dead-letter queue](dead-letter-queue.md)
- [Error codes](error-codes.md)
