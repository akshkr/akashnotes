---
id: index
title: Orbit documentation
section: Overview
applies_to: all
updated: 2026-10-21
---

# Orbit documentation

Orbit is an open-source Python library for **background jobs and workflows**. You decorate a
function, enqueue it, and a pool of workers runs it somewhere else: with retries, backoff,
leases, a dead-letter queue, cron schedules and (since 3.0) multi-step **Flows**.

```python
from orbit import Orbit

app = Orbit(broker="redis://localhost:6379/0")

@app.job(retries=3, backoff="exponential", timeout="30s", idempotency_key="order_id")
def send_receipt(order_id: str):
    ...

send_receipt.enqueue(order_id="A-1001", priority="high", delay="10s")
```

```bash
orbit worker --queues default,high --concurrency 8
```

New to Orbit? Start with the [Quickstart](quickstart.md). It gets a worker running against a
local Redis in about ten minutes.

## Which version are these docs for?

The current release is **3.2.1** (2026-10-20). Every page shows an `applies_to` value in its
header:

| `applies_to` | Meaning |
|---|---|
| `3.x` | Only true for Orbit 3.0 and later (`orbit.toml`, Flows, the new CLI layout) |
| `2.x` | Only true for the 2.x line (`orbit.ini` and `ORBIT_*` environment variables) |
| `all` | Applies to both lines; differences are called out inline |

> **Note:** 2.9.0 (2025-11-20) is the last 2.x release. The 2.x line reaches **end of life on
> 2026-12-31**. After that date it gets no security fixes. If you are still on 2.x, read
> [Migrating from 2.x to 3.x](migrating-2-to-3.md) and run `orbit migrate-config orbit.ini`.

## Documentation map

### Getting started
- [Quickstart](quickstart.md): install, configure, run a worker, enqueue a job
- [Installation](installation.md): supported Python versions, extras, verifying an install
- [Migrating from 2.x to 3.x](migrating-2-to-3.md)

### Core concepts
- [Jobs](concepts-jobs.md): defining, enqueueing and the job lifecycle
- [Workers](concepts-workers.md): concurrency, prefetch, shutdown
- [Queues and priorities](concepts-queues-priorities.md)
- [Brokers](concepts-brokers.md): picking between Redis, Postgres and SQS
- [Glossary](glossary.md)

### Brokers
- [Redis broker](broker-redis.md)
- [Postgres broker](broker-postgres.md)
- [Amazon SQS broker](broker-sqs.md)

### Reliability
- [Retries and backoff](retries-and-backoff.md)
- [Dead-letter queue](dead-letter-queue.md)
- [Idempotency](idempotency.md)
- [Leases and heartbeats](leases-and-heartbeats.md)

### Scheduling
- [Cron schedules](scheduling-cron.md)
- [Delays](scheduling-delays.md)

### Flows (3.x)
- [Flows overview](flows-overview.md)
- [Steps and state](flows-steps-and-state.md)
- [Error handling in flows](flows-error-handling.md)

### Results, configuration and CLI
- [Result backend](results-backend.md)
- [Configuration reference (`orbit.toml`)](configuration-reference.md)
- [Environment variables (2.x)](environment-variables-2x.md)
- [CLI reference](cli-reference.md)

### Dashboard and observability
- [Dashboard](dashboard.md) and [Dashboard auth with OIDC](dashboard-auth-oidc.md)
- [Metrics](observability-metrics.md) and [Tracing](observability-tracing.md)

### Deployment and operations
- [Docker](deployment-docker.md), [Kubernetes](deployment-kubernetes.md),
  [systemd](deployment-systemd.md)
- [Scaling workers](scaling-workers.md) and [Performance tuning](performance-tuning.md)
- [Security](security.md)

### Troubleshooting
- [Error codes (ORB-xxxx)](error-codes.md)
- [Broker problems](troubleshooting-broker.md)
- [Duplicate execution](troubleshooting-duplicates.md)
- [Memory growth](troubleshooting-memory.md)
- [FAQ](faq.md)

### Reference
- [`Orbit` API](api-reference-orbit.md), [Job API](api-reference-job.md),
  [Flow API](api-reference-flow.md)
- [Changelog](changelog.md)
- [Contributing](contributing.md)

## How Orbit fits together

| Piece | What it does | Read more |
|---|---|---|
| Job | A decorated Python function plus its arguments | [concepts-jobs](concepts-jobs.md) |
| Queue | A named stream of jobs; workers subscribe to queues | [concepts-queues-priorities](concepts-queues-priorities.md) |
| Broker | Stores queued, delayed and leased jobs | [concepts-brokers](concepts-brokers.md) |
| Worker | Claims jobs, runs them, renews leases with heartbeats | [concepts-workers](concepts-workers.md) |
| Result backend | Stores return values and idempotency records | [results-backend](results-backend.md) |
| Scheduler | Enqueues jobs on a cron schedule | [scheduling-cron](scheduling-cron.md) |
| Flow | A DAG of steps with tracked state (3.x only) | [flows-overview](flows-overview.md) |

Orbit delivers each job **at least once**. Most of the reliability pages explain how to live
with that guarantee: make jobs idempotent, size leases correctly, and keep an eye on the DLQ.

## Getting help

- Search the [FAQ](faq.md) and the [error code list](error-codes.md) first. Every Orbit error
  is logged with a stable `ORB-xxxx` code, and searching for the code is usually the fastest
  route to an answer.
- Run `orbit doctor`. It checks broker connectivity, your config file and installed versions,
  and its output is the first thing maintainers will ask for in an issue.
- File issues on the project tracker with the right `comp:*` label (for example `comp:core`,
  `comp:broker-redis`, `comp:scheduler`). Include your Orbit version, Python version, broker
  and the `orbit doctor` output.

These docs are maintained alongside the code. Found a gap? See
[Contributing](contributing.md); docs fixes use the `comp:docs` label.
