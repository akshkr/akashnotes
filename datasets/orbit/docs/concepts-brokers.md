---
id: concepts-brokers
title: Brokers
section: Brokers
applies_to: all
updated: 2026-09-16
---

# Brokers

The **broker** is the durable store between the code that enqueues jobs and the workers that
run them. Orbit uses it for:

- **Queued jobs**: waiting, ordered by [priority](concepts-queues-priorities.md)
- **Scheduled jobs**: [delayed](scheduling-delays.md) and retrying jobs that aren't due yet
- **Leases**: which worker holds which job, and until when
  ([Leases and heartbeats](leases-and-heartbeats.md))
- **The dead-letter queue**: jobs that ran out of attempts ([DLQ](dead-letter-queue.md))
- **Coordination**: the scheduler lock, so that only one worker fires each cron tick

The broker does **not** store job return values. Those go to the
[result backend](results-backend.md), which reuses the broker's connection: a Redis broker can
store results in Redis, and a Postgres broker in Postgres. SQS has no result backend.

## Supported brokers

| | Redis | Postgres | Amazon SQS |
|---|---|---|---|
| Extra | `orbit[redis]` | `orbit[postgres]` | `orbit[sqs]` |
| URL scheme | `redis://`, `rediss://` | `postgresql://` | `sqs://` |
| Pickup latency | Milliseconds (blocking pop) | Usually ms (LISTEN/NOTIFY), polling fallback | Long polling; typically sub-second |
| Priorities | Native | Native | Emulated (one SQS queue per level) |
| Delays | Sorted set | `run_at` column | `DelaySeconds` (≤ 15 min), re-delayed beyond that |
| Lease mechanism | Sorted set of deadlines | `leased_until` column | SQS visibility timeout |
| Operational burden | You run Redis (persistence on!) | You already run Postgres | Managed; you pay per request |
| Good fit | High throughput, low latency | Moderate volume, one less system | AWS-native, bursty, no servers |

Details, tuning and known issues for each broker:

- [Redis broker](broker-redis.md)
- [Postgres broker](broker-postgres.md)
- [Amazon SQS broker](broker-sqs.md)

## Choosing a broker

Answer these in order:

1. **Are you already all-in on AWS and do you want no servers to run?** Use SQS. Accept
   emulated priorities and per-request pricing.
2. **Is your volume modest (say, under a few hundred jobs per second) and do you already run
   Postgres?** Use the Postgres broker. One less moving part, and backups and failover are
   already handled.
3. **Otherwise** use Redis. It is the most widely deployed Orbit broker and the one the
   maintainers test hardest.

> **Note:** You cannot move queued jobs between brokers. To switch, point new enqueues at the
> new broker, keep a few workers on the old broker until its queues drain (check
> `orbit dlq list` too), then retire it.

## Configuring the broker

In **3.x** the broker is a single URL in `orbit.toml`:

```toml
[broker]
url = "redis://localhost:6379/0"
```

You can also pass it in code, which overrides the file:

```python
app = Orbit(broker="postgresql://orbit:secret@db.internal.example.com:5432/orbit")
```

In **2.x** the URL came from the `ORBIT_BROKER_URL` environment variable or the `orbit.ini`
file:

```bash
export ORBIT_BROKER_URL="redis://localhost:6379/0"
```

`orbit migrate-config orbit.ini` copies the 2.x value into `[broker] url`. See
[Migrating from 2.x to 3.x](migrating-2-to-3.md). Don't commit broker passwords. See
[Security](security.md) for how to inject the URL at deploy time.

## Checking connectivity

```bash
$ orbit doctor
orbit 3.2.1 (python 3.12.6)
[ok]   config    orbit.toml loaded (4 sections)
[ok]   broker    postgresql://orbit@db.internal.example.com:5432/orbit reachable (3.1 ms)
[ok]   results   postgres backend reachable
```

Broker errors use the `ORB-10xx` range, plus one SQS-specific code:

| Code | Name | Typical cause |
|---|---|---|
| ORB-1001 | BrokerConnectionError | Wrong host/port, DNS, firewall, broker down or failing over |
| ORB-1002 | BrokerAuthError | Wrong password, expired IAM credentials, missing TLS client cert |
| ORB-1901 | BrokerRateLimited | SQS throttled the request (most often on FIFO queues) |

Workers and producers both retry broker connections with backoff, so a short outage shows up
as ORB-1001 warnings followed by recovery. It does not crash anything. A long outage causes
enqueue calls to raise once their internal retries run out. Handle that in your web tier.
[Broker problems](troubleshooting-broker.md) has a step-by-step diagnosis guide.

## Delivery semantics

All three brokers give the same guarantee: **at-least-once delivery**. A job is removed from
the broker only after a worker acknowledges it. If the worker dies, or its lease expires
before the acknowledgement, the job is delivered again. None of the brokers can offer
exactly-once on its own, so design jobs to be [idempotent](idempotency.md).
