---
id: scheduling-delays
title: Delayed jobs
section: Scheduling
applies_to: "all"
updated: 2026-10-24
---

# Delayed jobs

A delayed job is an ordinary [job](concepts-jobs.md) that workers can only see after a set amount of time has passed. Use a delay for "do this once, later", such as sending a reminder in 30 minutes or retrying a partner webhook in an hour. For "do this every Monday at 09:00", use a [cron schedule](scheduling-cron.md).

## Enqueuing with a delay

```python
from orbit import Orbit

app = Orbit(broker="redis://localhost:6379/0")

@app.job(retries=3, backoff="exponential", timeout="30s", idempotency_key="order_id")
def send_receipt(order_id: str): ...

# Workers will not see this job for at least 10 seconds
send_receipt.enqueue(order_id="A-1001", priority="high", delay="10s")
```

`delay` takes either a duration string or a whole number of seconds:

| Value | Meaning |
|---|---|
| `45` or `"45s"` | 45 seconds |
| `"10m"` | 10 minutes |
| `"2h"` | 2 hours |
| `"1h30m"` | 90 minutes |
| `"1d"` | 24 hours |

Delays use the same duration parser as `timeout=` on `@app.job`, so any format that works in one place works in the other. A malformed string such as `"10 minutes"` raises `ValueError` at enqueue time. The job never reaches the broker.

## A delay means "not before", not "exactly at"

A delay promises that the job will not start before it is due. It does not promise that the job starts *at* that moment. When the delay ends, the job goes to the back of its queue at its normal [priority](concepts-queues-priorities.md). It does not skip ahead of jobs that are already waiting at the same priority. If every worker is busy, a due job waits like any other job.

To see whether due jobs are waiting, compare queue depth with how long jobs sit in the queue. Both are listed in [metrics](observability-metrics.md).

## How each broker implements delays

| Broker | Mechanism | Typical precision |
|---|---|---|
| [Redis](broker-redis.md) | Sorted set keyed by due time. Workers move due jobs into the live queue | about 1 s |
| [Postgres](broker-postgres.md) | `run_at` column, polled and woken by `LISTEN/NOTIFY` | 1–2 s |
| [SQS](broker-sqs.md) | Native `DelaySeconds` up to 15 minutes, then "hops" | about 1 s for delays up to 15 min |

### Long delays on SQS

SQS caps `DelaySeconds` at 900 seconds (15 minutes). For longer delays, Orbit sends the message with the maximum delay and records the remaining time in a message attribute. When a worker receives a message that is not due yet, it sends it again with the next hop and deletes the original. Your code never sees this, and hops are **not** counted as retry attempts.

Each hop still costs one `SendMessage` and one `DeleteMessage` call. A 2-hour delay takes 8 hops. If you enqueue thousands of long-delayed jobs at the same moment, you can hit SQS throttling, which shows up as `ORB-1901 BrokerRateLimited`. Spread out the enqueues or shorten the delays. For tuning advice, see [SQS broker](broker-sqs.md).

## Which clock is used?

Orbit measures delays with the **broker's** clock: Redis `TIME`, Postgres `now()`, or SQS on the server side. It never uses the clock of the process that called `enqueue`. A producer whose clock is a few minutes off therefore cannot make a delayed job run early or late.

Cron schedules work differently. They are evaluated in a time zone, so they can drift across daylight-saving changes (`ORB-1402 ScheduleDrift`). See [Cron schedules](scheduling-cron.md).

> **Note:** A delay is relative ("10 minutes from now"), so daylight-saving changes never affect it. To get "09:00 local time tomorrow", compute the number of seconds yourself in the user's time zone, or use a cron schedule.

## Delays, leases and retries

- **Time spent waiting is not part of the run.** The job's `timeout` and its [lease](leases-and-heartbeats.md) start when a worker picks the job up, not when it is enqueued.
- **Retries use the same mechanism.** When an attempt fails, Orbit puts the job back on the queue with a delay chosen by the [retry policy](retries-and-backoff.md). That delay is capped by `[retries] max_delay_seconds` (600 by default).
- **Idempotency keys are held from enqueue time.** A delayed job holds its [idempotency key](idempotency.md) from the moment you enqueue it, not from the moment it runs. If you enqueue it again with the same key during the delay, Orbit treats the second call as a duplicate.

## Payload size and many delayed jobs

The arguments of a delayed job stay in the broker for the whole delay. The usual `[limits] max_payload_kb` cap (512 KB) applies, and a job over the cap fails with `ORB-1202 PayloadTooLarge`. On Redis, a million delayed jobs with 4 KB payloads use about 4 GB of memory before anything runs. Pass an ID (`order_id="A-1001"`) and load the full record inside the job.

## See also

- [Cron schedules](scheduling-cron.md): recurring work
- [Retries and backoff](retries-and-backoff.md): how retry delays are calculated
- [Performance tuning](performance-tuning.md): sizing Redis memory for large numbers of delayed jobs
