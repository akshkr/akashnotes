---
id: broker-redis
title: Redis broker
section: Brokers
applies_to: 3.x
updated: 2026-07-15
---

# Redis broker

Redis is the most widely used Orbit broker. It has the lowest pickup latency and highest
throughput, and it is what the maintainers run in the main integration suite. Install it with
the `redis` extra:

```bash
pip install "orbit[redis]"
```

Redis **6.2 or newer** is required. 7.x is recommended.

## Connection URL

```toml
[broker]
url = "redis://localhost:6379/0"
```

| Form | Example |
|---|---|
| Plain TCP, database 0 | `redis://localhost:6379/0` |
| Password (Redis `requirepass`) | `redis://:s3cret@redis.internal.example.com:6379/0` |
| ACL user and password | `redis://orbit:s3cret@redis.internal.example.com:6379/0` |
| TLS | `rediss://redis.internal.example.com:6380/0` |

The number at the end selects the Redis logical database. The
[result backend](results-backend.md) has no connection settings of its own. With
`backend = "redis"` it stores results in the **same database** as the broker, under
`orbit:result:*` keys. Never run `FLUSHDB` on that database to clear old results, because it
also deletes every queued job. Let `ttl_days` expire them.

Since 3.1.0, Orbit also works with Redis Sentinel and with managed failover endpoints. See
[Broker problems](troubleshooting-broker.md) for failover behaviour.

```toml
[broker]
url = "redis://localhost:6379/0"

[results]
backend = "redis"
ttl_days = 7
```

## How Orbit uses Redis

All keys are prefixed with `orbit:`. You should never need to modify them by hand. Knowing
the layout helps when you are debugging with `redis-cli`:

| Key | Type | Holds |
|---|---|---|
| `orbit:q:<queue>:<priority>` | list | Ready jobs, one list per priority (`high`, `normal`, `low`) |
| `orbit:scheduled` | sorted set | Delayed and retrying jobs, scored by due time |
| `orbit:leases` | sorted set | Running job IDs, scored by lease deadline |
| `orbit:job:<job_id>` | hash | Payload, attempt count, metadata |
| `orbit:dlq:<queue>` | list | Dead-lettered job IDs |
| `orbit:workers` | hash | Worker IDs and last heartbeat time |
| `orbit:lock:scheduler` | string | Cron scheduler lock holder |
| `orbit:result:<job_id>` | string | Job result (result backend, expires after `ttl_days`) |
| `orbit:flowrun:<run_id>` | string | Flow run state (result backend) |

Workers claim jobs with a blocking pop, so an idle worker picks up a new job within
milliseconds. Heartbeats rewrite each running job's score in `orbit:leases`. A background
sweep returns jobs whose deadline has passed to their queue. That sweep is the source of
**ORB-1101 LeaseExpired** (see [Leases and heartbeats](leases-and-heartbeats.md)).

## Required Redis settings

Redis defaults are tuned for caching, not for queues. Two settings matter:

```conf
# redis.conf
appendonly yes
appendfsync everysec
maxmemory-policy noeviction
```

- **Persistence.** Without AOF (or at least RDB snapshots), a Redis restart **loses every
  queued job**. `appendfsync everysec` can lose up to a second of enqueues on a crash, which
  is acceptable for most workloads.
- **No eviction.** With an `allkeys-*` or `volatile-*` policy, Redis silently deletes job
  hashes under memory pressure. Jobs then vanish without a trace. With `noeviction`, enqueues
  fail loudly instead.

> **Note:** Managed Redis services often default to an eviction policy such as
> `volatile-lru`. Check it explicitly. `orbit doctor` warns if `maxmemory-policy` is anything
> other than `noeviction`.

## Failover and high availability

Orbit works with a primary–replica setup behind a failover endpoint (a managed service
endpoint or a proxy). During failover, clients see a few seconds of **ORB-1001
BrokerConnectionError**. Workers reconnect with jittered backoff and carry on. In-flight jobs
whose heartbeats were missed during failover may be redelivered.

Orbit does not support Redis Cluster (sharded) mode. Its claim operations use multi-key
scripts that must run on a single node.

### Known issue: reconnect storm after failover (3.1.0)

In **3.1.0**, workers reconnected after a failover **without jitter and without a connection
cap**. With many workers this produced a reconnect storm: thousands of simultaneous
connections, Redis CPU pinned at 100%, and a cascade of ORB-1001 errors that could last
minutes after the new primary was healthy.

This was **fixed in 3.1.2** (2026-07-08). Reconnects now use jittered exponential backoff,
and each worker process makes one shared reconnect attempt instead of one per slot.

If you are on 3.1.0, upgrade:

```bash
pip install "orbit[redis]>=3.1.2"
```

If you can't upgrade straight away, stagger restarts of your worker fleet after a failover,
and lower `--concurrency` temporarily. Fewer slots means fewer pooled connections per worker.

## Sizing and performance

- Each worker process holds roughly `concurrency + 2` connections: one per slot for acks, plus
  the blocking claim and the heartbeat connection. Check Redis `maxclients` against
  `workers × (concurrency + 2)` plus your producers.
- A job's memory footprint in Redis is approximately its serialized payload plus ~300 bytes.
  A backlog of a million 2 KB jobs needs around 2.3 GB.
- Keep payloads small (pass IDs). `[limits] max_payload_kb` (default 512) is a hard cap, and
  oversized jobs fail with **ORB-1202 PayloadTooLarge**.

## Troubleshooting

| Symptom | Likely cause | See |
|---|---|---|
| ORB-1001 bursts after a failover, Redis CPU at 100% | Reconnect storm on 3.1.0 | Upgrade to ≥ 3.1.2 |
| ORB-1002 on startup | Wrong password or ACL user lacks `+@all` on `orbit:*` keys | [Security](security.md) |
| Jobs disappear without reaching the DLQ | Eviction policy is not `noeviction` | Above |
| Jobs run twice after a Redis restart | AOF disabled; lease state lost | [Duplicate execution](troubleshooting-duplicates.md) |

For general broker diagnosis see [Broker problems](troubleshooting-broker.md).
