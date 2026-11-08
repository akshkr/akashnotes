---
id: scheduling-cron
title: Cron schedules
section: Scheduling
applies_to: all
updated: 2026-10-23
---

# Cron schedules

Use `app.schedule` to run a job on a recurring schedule written as a cron expression:

```python
from orbit import Orbit

app = Orbit()  # broker from orbit.toml

@app.job(retries=3, timeout="10m")
def send_digest():
    for team in teams_with_digest_enabled():
        build_and_send_digest(team.id)

app.schedule(send_digest, cron="0 9 * * MON")   # 09:00 every Monday
```

At each matching minute, Orbit **enqueues** an ordinary job. That job goes to the job's queue
with `normal` priority. It goes through the normal [retry policy](retries-and-backoff.md), and
it shows up in the [dashboard](dashboard.md) like any other job. For one-off "run this later"
work, use `enqueue(delay=...)` instead. See [Delays](scheduling-delays.md).

Scheduled jobs take **no arguments**. Load whatever the job needs inside it.

## Cron syntax

Orbit accepts standard **five-field** expressions:

```text
┌───────── minute        0–59
│ ┌─────── hour          0–23
│ │ ┌───── day of month  1–31
│ │ │ ┌─── month         1–12 or JAN–DEC
│ │ │ │ ┌─ day of week   0–6 (0 = Sunday) or SUN–SAT
│ │ │ │ │
0 9 * * MON
```

Each field accepts `*`, single values, lists (`1,15`), ranges (`MON-FRI`) and steps (`*/15`).

| Expression | Runs |
|---|---|
| `*/5 * * * *` | Every five minutes |
| `0 * * * *` | At the top of every hour |
| `30 2 * * *` | 02:30 every day (see the DST note below) |
| `0 9 * * MON-FRI` | 09:00 on weekdays |
| `0 0 1 * *` | Midnight on the first of each month |
| `0 9 * * MON` | 09:00 every Monday |

A six-field expression (with seconds), a typo, or an out-of-range value raises **ORB-1401
ScheduleParseError** when `app.schedule` is called, which is at import time. A bad schedule
therefore fails the deploy rather than silently never firing:

```text
orbit.errors.ScheduleParseError: [ORB-1401] invalid cron expression '0 9 * * MON *':
expected 5 fields, got 6
```

## Who fires the schedule

There is no separate scheduler process. **Every worker runs the scheduler loop**, but only the
worker holding the **scheduler lock** on the broker enqueues ticks. Each tick fires exactly
once, however many workers you run.

- The lock holder renews the lock with each heartbeat.
- If the holder dies, another worker takes over the lock once it has gone unrenewed for three
  heartbeat intervals (90 s with the default `heartbeat_seconds = 30`).
- The lock is held regardless of which `--queues` a worker consumes. A worker that only
  consumes `high` can still enqueue a schedule whose job goes to `default`.

> **Note:** **Missed ticks are not backfilled.** If no worker was running at 09:00 on Monday,
> or the lock was changing hands at that exact minute, the 09:00 run is skipped. The next run
> is the next matching time. If a run must never be missed, have the job check when it last
> succeeded and catch up itself.

## Time zones and DST

Cron expressions are evaluated in the **local time zone of the worker that holds the scheduler
lock**. Orbit has no per-schedule time zone setting. This has two consequences:

1. **Run every worker in the same time zone, ideally UTC** (`TZ=UTC` in your container or unit
   file). If workers disagree, a schedule jumps by hours whenever the lock moves to a worker in
   a different zone.
2. If that zone observes **daylight saving time**, some local times are skipped or repeated
   once a year:

| Transition | Local time affected | What happens |
|---|---|---|
| Spring forward (clocks jump from 02:00 to 03:00) | 02:00–02:59 doesn't exist | A `30 2 * * *` run fires late, at the first valid minute, and logs ORB-1402 |
| Fall back (01:00–01:59 happens twice) | 01:00–01:59 repeats | A `30 1 * * *` run can fire **twice** and logs ORB-1402 |

**ORB-1402 ScheduleDrift** is logged whenever a tick fires noticeably earlier or later than its
nominal time, whether because of DST or because the host clock jumped (an NTP correction, a VM
resumed from pause). Since 3.2.1, ticks less than one second late no longer log it.

```text
WARN orbit.scheduler [ORB-1402] ScheduleDrift: send_digest due 2026-03-29T02:30:00+01:00
fired 2026-03-29T03:00:00+02:00 (local time skipped by DST transition)
```

Drift across DST transitions is a known, long-standing issue. The supported fix is to run
workers in UTC and write expressions in UTC. If your business rule is "09:00 Berlin time",
accept that the UTC expression shifts by an hour twice a year, or schedule hourly and let the
job decide whether it is time to act. Keep every host NTP-synced to prevent clock-skew drift.

## Overlapping runs

A schedule does not wait for the previous run to finish. If `*/5 * * * *` sometimes takes
seven minutes, two runs overlap. Make scheduled jobs safe to run concurrently, or have the job
take a lock or check a "running" flag in your database. Because scheduled jobs have no
arguments, `idempotency_key` doesn't apply to them directly. [Idempotency](idempotency.md)
shows the dispatcher pattern for at-most-once-per-period work.

## Changing or removing schedules

Schedules live in code. Workers register them at startup from the `app.schedule` calls they
import. To change or remove one, edit the code and redeploy **all** workers. During a rolling
deploy, an old worker that still holds the lock keeps firing the old schedule until it is
replaced. The dashboard's **Schedules** view shows the last and next run of each schedule, so
you can confirm the change took effect.

## See also

- [Delays](scheduling-delays.md)
- [`app.schedule` API](api-reference-orbit.md)
- [Error codes](error-codes.md)
