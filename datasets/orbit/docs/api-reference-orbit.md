---
id: api-reference-orbit
title: "API reference: Orbit"
section: Reference
applies_to: "3.x"
updated: 2026-09-16
---

# API reference: `Orbit`

`Orbit` is the application object. It holds the broker connection, the registry of jobs and
schedules, and the loaded configuration. Create **one** per service, at module level, and import
it wherever you define jobs.

```python
from orbit import Orbit, Flow, step

app = Orbit(broker="redis://localhost:6379/0")
```

`Orbit`, `Flow` and `step` are all exported from the top-level `orbit` package. See also
[api-reference-job.md](api-reference-job.md) and [api-reference-flow.md](api-reference-flow.md).

## Constructor

```python
Orbit(broker: str | None = None)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `broker` | `str` or `None` | `None` | Broker URL. When omitted, Orbit uses `[broker] url` from `orbit.toml`. |

### How configuration is resolved

1. An explicit `broker=` argument wins.
2. Otherwise `orbit.toml` in the current working directory is read.
3. Every other setting (`[worker]`, `[retries]`, `[results]`, `[limits]` and so on) comes only
   from `orbit.toml` and falls back to the documented defaults
   ([configuration-reference.md](configuration-reference.md)).

If both are missing, constructing `Orbit()` raises `BrokerConnectionError` (ORB-1001) with the
message `no broker configured`. Unknown keys in `orbit.toml` raise `UnknownConfigKey` (ORB-1802)
at construction time, not later when a worker starts.

The constructor does **not** connect to the broker. The connection is opened on first use, so
importing your app module in tests or scripts is cheap.

> **Note:** In 2.x the constructor also read `ORBIT_BROKER_URL`, `ORBIT_CONCURRENCY` and
> `ORBIT_LEASE`. 3.x ignores those variables. If you relied on them, either pass `broker=`
> explicitly or run `orbit migrate-config orbit.ini`. See
> [environment-variables-2x.md](environment-variables-2x.md).

The broker URL scheme selects the broker implementation. URL formats for Redis, Postgres and SQS
are on [concepts-brokers.md](concepts-brokers.md).

## `app.job(...)`

A decorator that registers a function as a job and returns a job object with `.enqueue()`.

```python
@app.job(retries=3, backoff="exponential", timeout="30s", idempotency_key="order_id")
def send_receipt(order_id: str): ...
```

You can use it bare-bones as `@app.job()`, in which case every option falls back to
`orbit.toml`. All parameters and the returned object are documented in
[api-reference-job.md](api-reference-job.md).

Job names are the function's module-qualified name, for example `billing.tasks.send_receipt`.
Renaming or moving a function changes its name, so jobs already queued under the old name will
fail on new workers. Drain the queue before you rename.

## `app.schedule(func, cron=...)`

Registers a recurring schedule for an existing job.

```python
@app.job()
def send_digest(): ...

app.schedule(send_digest, cron="0 9 * * MON")   # 09:00 every Monday
```

| Parameter | Type | Description |
|---|---|---|
| `func` | job | A function already decorated with `@app.job`. |
| `cron` | `str` | A standard five-field cron expression: minute, hour, day of month, month, day of week. |

- An invalid expression raises `ScheduleParseError` (ORB-1401) **when `app.schedule` is
  called**, so a typo fails at import time, not at 9 a.m. on Monday.
- Scheduled runs are enqueued like any other job and go through the job's normal retry policy.
- Scheduled jobs take no arguments. Load whatever you need inside the job.
- Around DST changes, runs can fire late or twice and log `ScheduleDrift` (ORB-1402). Write cron
  expressions for hosts running in UTC ([scheduling-cron.md](scheduling-cron.md)).

For one-off delays, use `enqueue(delay=...)` instead ([scheduling-delays.md](scheduling-delays.md)).

## Exceptions

Every Orbit error is an exception whose class name matches the error name, and each one carries
the code in its `code` attribute:

```python
from orbit.errors import PayloadTooLarge

try:
    summarize.enqueue(document=big_text)
except PayloadTooLarge as exc:
    print(exc.code)   # "ORB-1202"
```

The full list is on [error-codes.md](error-codes.md).

## Typical module layout

```python
# atlas_jobs/app.py
from orbit import Orbit

app = Orbit()   # broker comes from orbit.toml

# atlas_jobs/tasks.py
from atlas_jobs.app import app

@app.job(retries=5, timeout="2m")
def enrich_ticket(ticket_id: str): ...
```

Start workers for it with `orbit worker --queues default,high --concurrency 8`
([cli-reference.md](cli-reference.md)).
