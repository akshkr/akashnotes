---
id: retries-and-backoff
title: Retries and backoff
section: Reliability
applies_to: 3.x
updated: 2026-09-22
---

# Retries and backoff

When a job attempt fails, Orbit schedules another attempt after a **backoff** delay. It keeps
doing so until the job succeeds or runs out of attempts. A job that runs out is moved to the
[dead-letter queue](dead-letter-queue.md) with **ORB-1301 RetryExhausted**.

## Global policy: `[retries]`

The `[retries]` section of `orbit.toml` sets the default for every job:

```toml
[retries]
max_attempts = 3            # total attempts, including the first
backoff = "exponential"     # "exponential" | "linear" | "fixed"
max_delay_seconds = 600     # cap on any single backoff delay
```

These are also the built-in defaults, so a project with no `[retries]` section behaves
exactly as shown.

## Per-job policy: `@app.job(retries=...)`

Override the policy for one job on its decorator:

```python
@app.job(retries=5, backoff="exponential", timeout="30s")
def charge_card(payment_id: str): ...

@app.job(retries=2, backoff="fixed")
def refresh_avatar(user_id: str): ...
```

`retries` is the job's **maximum number of attempts** and replaces `max_attempts` for that
job. Both count the first attempt. `retries=5` means at most five runs: the first plus four
retries.

Precedence: decorator arguments override `orbit.toml`, which overrides the built-in defaults.
`backoff` and `retries` can be overridden independently. `max_delay_seconds` is global only.

## Backoff strategies

Let *n* be the retry number (1 for the first retry). Before jitter, the delay is:

| `backoff` | Delay before retry *n* | Retries 1–5 |
|---|---|---|
| `"exponential"` (default) | 2ⁿ seconds | 2 s, 4 s, 8 s, 16 s, 32 s |
| `"linear"` | 10 × *n* seconds | 10 s, 20 s, 30 s, 40 s, 50 s |
| `"fixed"` | 10 seconds | 10 s, 10 s, 10 s, 10 s, 10 s |

Every delay is capped at `max_delay_seconds` (600 s by default). With exponential backoff the
cap kicks in at the tenth retry (2¹⁰ = 1024 s → 600 s).

**Jitter.** Orbit then picks the actual delay uniformly between 50% and 100% of the computed
value. A retry scheduled for "8 s" runs somewhere between 4 and 8 seconds later. Jitter stops
a burst of jobs that failed together (say, during a database blip) from all retrying at the
same instant. You can't turn it off.

> **Note:** The defaults are tuned for brief, transient failures: two retries within about
> six seconds. For flaky third-party APIs that go down for minutes at a time, raise the
> attempts (for example `retries=10`, which spreads nine retries over up to about 17 minutes)
> rather than the delay cap.

## What counts as a failed attempt

| Event | Counts as an attempt? | Logged as |
|---|---|---|
| The job raises any exception | Yes | the exception |
| The attempt exceeds `timeout` | Yes | `TimeoutError` |
| The lease expired and the job was redelivered | **Yes** | **ORB-1101 LeaseExpired** |
| The worker was killed for memory while running it | Yes | **ORB-2101 WorkerOOM** |
| Graceful shutdown handed the job back unstarted | No | n/a |

The lease row deserves attention. A job that regularly **outlives its lease** never raises,
yet each redelivery burns an attempt. With the default policy it lands in the DLQ after its
third delivery, even though the code may have succeeded every time. If you see ORB-1301
preceded by ORB-1101, the fix is lease sizing, not retry tuning. See
[Leases and heartbeats](leases-and-heartbeats.md).

Errors raised at **enqueue** time, such as **ORB-1201 SerializationError**, **ORB-1202
PayloadTooLarge** and **ORB-2001 IdempotencyConflict**, never reach the retry machinery.
They are raised to the caller.

## Permanent errors

Orbit retries every exception. If an error can never succeed on retry (the record was
deleted, the input is invalid), catch it in the job and return. Otherwise each such job
burns its attempts and clutters the DLQ:

```python
@app.job(retries=4)
def sync_invoice(invoice_id: str):
    try:
        invoice = billing.get_invoice(invoice_id)
    except billing.NotFound:
        log.info("invoice %s deleted before sync; skipping", invoice_id)
        return  # success: nothing left to do
    push_to_ledger(invoice)
```

## What it looks like in the logs

```text
WARN  orbit.worker  job j_61c0aa charge_card attempt 1/5 failed:
      ConnectionResetError; retrying in 1.6s
WARN  orbit.worker  job j_61c0aa charge_card attempt 2/5 failed:
      ConnectionResetError; retrying in 3.1s
...
ERROR orbit.worker  [ORB-1301] RetryExhausted: job j_61c0aa charge_card
      failed 5/5 attempts; moved to DLQ (queue=default)
```

Attempt numbers count total attempts, so `retries=5` shows `/5`.

## Coming from 2.x

In 2.x the global policy lived in the `[retries]` section of `orbit.ini`. Decorator
arguments behave the same in both lines. `orbit migrate-config orbit.ini` converts the
section to `orbit.toml`.

> **Warning:** `orbit migrate-config` in **3.0.1** silently **dropped the `[retries]`
> section**. Migrated projects fell back to the built-in defaults. This was fixed in
> **3.0.3**. If you migrated with 3.0.1, open your `orbit.toml` and confirm `[retries]` is
> there. Re-running `orbit migrate-config` on 3.0.3 or later regenerates it.

## See also

- [Dead-letter queue](dead-letter-queue.md)
- [Error handling in flows](flows-error-handling.md): retries for individual flow steps
- [Configuration reference](configuration-reference.md)
