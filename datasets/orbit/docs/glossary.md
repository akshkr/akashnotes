---
id: glossary
title: Glossary
section: Reference
applies_to: "all"
updated: 2026-07-15
---

# Glossary

Short definitions of the terms used throughout the Orbit docs, in alphabetical order. Each entry
links to the page with the full explanation. Terms that only exist in 3.x are marked **(3.x)**.

**At-least-once delivery**
Orbit's delivery guarantee. Every enqueued job runs at least once, and occasionally more than
once, after a lease expiry or a worker crash. Design jobs to be safe to repeat. See
[troubleshooting-duplicates.md](troubleshooting-duplicates.md).

**Backoff**
The wait between a failed attempt and the next retry. See *Exponential backoff*.

**Broker**
The external system that stores queued jobs and hands them to workers. Orbit supports Redis,
Postgres and Amazon SQS. In 3.x it's configured with `[broker] url`, and in 2.x with
`ORBIT_BROKER_URL`. See [concepts-brokers.md](concepts-brokers.md).

**Concurrency limit**
The maximum number of jobs one worker process runs at the same time. It's set with
`[worker] concurrency` (default 4) or `orbit worker --concurrency`. See
[scaling-workers.md](scaling-workers.md).

**Dead-letter queue (DLQ)**
Where a job goes after its last retry fails (`RetryExhausted`, ORB-1301). You manage it with
`orbit dlq list`, `orbit dlq replay <job_id>` and `orbit dlq purge`. See
[dead-letter-queue.md](dead-letter-queue.md).

**Delay**
A minimum wait before a job becomes available to workers, as in
`enqueue(..., delay="10s")`. See [scheduling-delays.md](scheduling-delays.md).

**Enqueue**
To submit a job to the broker with `job.enqueue(**kwargs)`. The call returns once the job is
stored, not when it has run. See [api-reference-job.md](api-reference-job.md).

**Exponential backoff**
A retry policy where the wait roughly doubles after each failed attempt, up to
`[retries] max_delay_seconds` (600 by default). It's the default `backoff`. See
[retries-and-backoff.md](retries-and-backoff.md).

**Flow (3.x)**
A named DAG of Steps that Orbit runs as one unit, started with `flow.run(...)` or
`orbit flows run <name>`. See [flows-overview.md](flows-overview.md).

**Flow run (3.x)**
One execution of a Flow, identified by a `run_id` and inspected with
`orbit flows status <run_id>`.

**Heartbeat**
A periodic signal from a running worker (`[worker] heartbeat_seconds`, default 30) that tells the
broker the worker is alive and renews the leases of its running jobs. Losing it raises
`WorkerHeartbeatLost` (ORB-1102). See [leases-and-heartbeats.md](leases-and-heartbeats.md).

**Idempotency key**
A value that identifies a unit of work, so that enqueuing the same work twice creates only one
job. It's declared with `@app.job(idempotency_key="order_id")`. A mismatch raises
`IdempotencyConflict` (ORB-2001). See [idempotency.md](idempotency.md).

**Job**
A Python function registered with `@app.job`, plus the arguments of one particular enqueue. See
[concepts-jobs.md](concepts-jobs.md).

**Lease (visibility timeout)**
The period during which a job taken by a worker is hidden from other workers
(`[worker] lease_seconds`, default 300, `ORBIT_LEASE` in 2.x). If the lease expires before the
job is acknowledged, the job is redelivered (`LeaseExpired`, ORB-1101). SQS calls this the
*visibility timeout*.

**`orbit.ini` (2.x)**
The 2.x configuration file. 3.x replaced it with `orbit.toml`, and
`orbit migrate-config orbit.ini` converts between them. See
[migrating-2-to-3.md](migrating-2-to-3.md).

**`orbit.toml` (3.x)**
The single configuration file for Orbit 3.x, with sections `[broker]`, `[worker]`, `[retries]`,
`[results]`, `[dashboard]`, `[telemetry]` and `[limits]`. See
[configuration-reference.md](configuration-reference.md).

**Payload**
The serialized (JSON) arguments of a job. It's capped by `[limits] max_payload_kb`, default 512
(`PayloadTooLarge`, ORB-1202).

**Prefetch**
How many extra jobs a worker reserves ahead of the ones it's running (`[worker] prefetch`,
default 10). See [performance-tuning.md](performance-tuning.md).

**Priority**
A per-job hint for the order in which a worker takes jobs, set with `enqueue(priority="high")`.
See [concepts-queues-priorities.md](concepts-queues-priorities.md).

**Queue**
A named stream of jobs, such as `default` or `high`. Workers consume the queues listed in
`--queues`.

**Result backend**
Where job return values and Flow run state are stored (`[results] backend`, default `"redis"`),
kept for `ttl_days` (default 7). See [results-backend.md](results-backend.md).

**Retry policy**
The rules for re-running a failed job: the maximum number of attempts (`[retries] max_attempts`,
default 3, or `retries=` per job), the backoff strategy, and the delay cap.

**Schedule (cron)**
A recurring trigger registered with `app.schedule(job, cron="0 9 * * MON")`. Parse errors raise
ORB-1401, and DST or clock-skew problems log ORB-1402. See
[scheduling-cron.md](scheduling-cron.md).

**Step (3.x)**
One node in a Flow. It wraps a job and can depend on other steps with `after=`. See
[flows-steps-and-state.md](flows-steps-and-state.md).

**Telemetry (OTLP)**
Metrics and traces exported over OpenTelemetry's OTLP protocol, configured with
`[telemetry] otlp_endpoint` and `service_name`. See
[observability-metrics.md](observability-metrics.md) and
[observability-tracing.md](observability-tracing.md).

**Worker**
A long-running process started with `orbit worker` that takes jobs from the broker and runs
them. See [concepts-workers.md](concepts-workers.md).
