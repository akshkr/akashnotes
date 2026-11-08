---
id: broker-postgres
title: Postgres broker
section: Brokers
applies_to: all
updated: 2026-08-04
---

# Postgres broker

The Postgres broker stores jobs in ordinary tables in a PostgreSQL database. If you already
run Postgres, it means one less system to operate, back up and secure. In return you get
lower peak throughput than Redis. Install it with the `postgres` extra:

```bash
pip install "orbit[postgres]"
```

PostgreSQL **13 or newer** is required.

## Connection URL

```toml
# 3.x: orbit.toml
[broker]
url = "postgresql://orbit:s3cret@db.internal.example.com:5432/orbit?sslmode=require"
```

```bash
# 2.x: environment
export ORBIT_BROKER_URL="postgresql://orbit:s3cret@db.internal.example.com:5432/orbit?sslmode=require"
```

The URL is passed to the driver unchanged, so standard libpq parameters such as `sslmode`,
`sslrootcert` and `application_name` work as usual.

## Schema

On first connect, Orbit creates its tables, all prefixed `orbit_`, in the database named in the
URL. The database user needs `CREATE` on the schema for that first run, and only
`SELECT/INSERT/UPDATE/DELETE` on the `orbit_*` tables afterwards.

| Table | Holds |
|---|---|
| `orbit_jobs` | One row per job: queue, priority, `run_at`, `leased_until`, attempts, payload (`jsonb`) |
| `orbit_dead_jobs` | Dead-lettered jobs, kept until replayed or purged |
| `orbit_workers` | Worker IDs and last heartbeat |
| `orbit_locks` | The scheduler lock |
| `orbit_results`, `orbit_flow_runs` | Only with `[results] backend = "postgres"` (3.x) |

Orbit manages the schema itself, and upgrades between minor versions apply any changes
automatically. Don't add your own triggers to these tables.

## How claiming works

Workers claim jobs with a single statement using `FOR UPDATE SKIP LOCKED`:

```sql
UPDATE orbit_jobs SET leased_until = now() + interval '300 seconds', worker_id = $1
WHERE id IN (
  SELECT id FROM orbit_jobs
  WHERE queue = ANY($2) AND run_at <= now() AND leased_until IS NULL
  ORDER BY priority, run_at
  LIMIT $3
  FOR UPDATE SKIP LOCKED)
RETURNING id, payload;
```

`SKIP LOCKED` lets many workers claim concurrently without blocking on each other's rows. The
`300 seconds` comes from `lease_seconds` (3.x) or `ORBIT_LEASE` (2.x). Heartbeats push
`leased_until` forward.

### Wakeups: LISTEN/NOTIFY plus polling

So that idle workers don't hammer the database, each enqueue sends a `NOTIFY` on the
`orbit_jobs` channel, and idle workers `LISTEN` on it. As a safety net, every worker also
polls every **5 seconds** whatever notifications it receives. The interval is fixed and not
configurable.

> **Note:** **LISTEN/NOTIFY can miss events under load.** When the database is busy, or the
> listening connection is briefly reset, notifications are dropped. No jobs are lost: they
> stay in `orbit_jobs`, and the next 5-second poll picks them up. But pickup latency jumps
> from milliseconds to several seconds. If your p99 pickup latency shows a ~5 s plateau,
> this is why. This is a known issue (`comp:broker-postgres`). Its effect is bounded by the
> polling fallback.

### Connection poolers

LISTEN requires a **session-level** connection. With PgBouncer in **transaction** pooling
mode, LISTEN silently does nothing and every pickup waits for the 5-second poll. Either:

- connect workers directly to Postgres (simplest), or
- use a PgBouncer pool in **session** mode for workers.

Producers that only enqueue can safely go through a transaction-mode pool.

## Operations

**Vacuum.** `orbit_jobs` is a high-churn table: every job is inserted, updated a few times,
then deleted. Autovacuum defaults are often too lazy for it. On busy systems, tune it per
table:

```sql
ALTER TABLE orbit_jobs SET (autovacuum_vacuum_scale_factor = 0.01,
                            autovacuum_vacuum_cost_delay = 2);
```

Table bloat shows up as slowly rising claim latency. Check it with `pg_stat_user_tables`
(`n_dead_tup`).

**Throughput.** On a modest instance (4 vCPU), expect a few hundred to around a thousand jobs
per second end to end. Past that, the claim query becomes the bottleneck and Redis is the
better choice. See [Performance tuning](performance-tuning.md).

**Backups.** Queued jobs are part of your normal database backups. After restoring a backup,
expect some redelivery. Rows that were leased at backup time have stale `leased_until`
values and are reclaimed once those deadlines pass.

**Result backend.** You can use the same database for results with
`[results] backend = "postgres"` (3.x). Results go to the `orbit_results` table over the
broker's connection. See
[Result backend](results-backend.md).

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| ORB-1001 BrokerConnectionError at startup | `pg_hba.conf` rejects the host, or `sslmode` mismatch |
| ORB-1002 BrokerAuthError | Wrong password, or user lacks privileges on the `orbit_*` tables |
| Pickup latency stuck around 5 s | LISTEN not working: transaction pooler, or missed NOTIFY under load |
| Claim latency creeping up over weeks | Table bloat; tune autovacuum |

More in [Broker problems](troubleshooting-broker.md).
