---
id: leases-and-heartbeats
title: Leases and heartbeats
section: Reliability
applies_to: all
updated: 2026-10-14
---

# Leases and heartbeats

Leases let Orbit recover jobs from workers that crash, freeze or lose the network. They are
also the main reason a job can **run twice**.

## What a lease is

When a worker claims a job, the broker doesn't hand the job over for good. It gives the worker
a **lease**: the right to run that job until a deadline. Other brokers call this a *visibility
timeout*. While the lease is valid, no other worker can claim the job.

- If the worker finishes and acknowledges the job **before the deadline**, the job is done.
- If the deadline passes without an acknowledgement, the broker assumes the worker is gone and
  makes the job **claimable again**. Another worker runs it.

That second case makes Orbit at-least-once. It also fires when the worker is merely *slow*,
in which case the original worker may still be running the job when a second one starts it.

## Heartbeats

A fixed deadline would force you to set the lease longer than your slowest job. Heartbeats
avoid that. Every `heartbeat_seconds`, the worker supervisor renews the lease of **each job it
is running** (and each prefetched job), pushing the deadline out to `now + lease_seconds`
again. A 40-minute job on a 5-minute lease is fine as long as heartbeats keep arriving.

```toml
# orbit.toml (3.x)
[worker]
lease_seconds = 300       # deadline if no heartbeat arrives
heartbeat_seconds = 30    # renewal interval
```

```text
t=0s     claim job j_61c0aa          lease until t=300
t=30s    heartbeat                   lease until t=330
t=60s    heartbeat                   lease until t=360
...      (worker freezes at t=95)
t=390s   lease deadline passes       job claimable again
t=391s   worker w-2 claims j_61c0aa  ── the job now runs a second time
```

When this happens Orbit logs **ORB-1101 LeaseExpired**:

```text
2026-10-14T03:12:44Z WARN  orbit.worker ORB-1101 LeaseExpired job=j_61c0aa queue=default lease_seconds=300
```

A lease expiry also **counts as an attempt** under the retry policy, so a job that keeps
outliving its lease ends in the [DLQ](dead-letter-queue.md) with ORB-1301. See
[Retries and backoff](retries-and-backoff.md).

## Why duplicate execution is by design

Duplicate execution from lease expiry on long jobs is **expected behaviour, not a bug**. The
broker can't tell a dead worker from a slow one, so Orbit prefers running a job twice to never
running it. Tune the settings below to make it rare, and use [idempotency](idempotency.md) to
make it harmless. [Duplicate execution](troubleshooting-duplicates.md) has a checklist.

## Sizing the two settings

Heartbeats fail to arrive in three situations:

1. **The worker is really gone** (crash, OOM kill, node lost). Here you *want* a short lease, so
   the job is retried quickly.
2. **The worker is alive but heartbeats are blocked.** The usual cause is a C extension that
   holds the GIL for a long stretch (some image, compression and numeric libraries), or an
   overloaded host.
3. **The broker is unreachable** for longer than the lease, for example during a long failover.

Rules of thumb:

- Keep `heartbeat_seconds` **at most a third of** `lease_seconds`, so one or two late
  heartbeats don't cost you the lease. `orbit doctor` warns when you break this rule.
- Set `lease_seconds` longer than the **longest stretch heartbeats might be blocked** (case 2),
  not longer than your longest job.
- Remember the cost: a longer lease means a crashed worker's jobs wait longer before they are
  retried.

| Workload | `lease_seconds` | `heartbeat_seconds` |
|---|---|---|
| Short web-triggered jobs (< 30 s) | 300 (default) | 30 (default) |
| Long I/O-bound jobs (minutes to hours) | 300 | 30. Heartbeats carry them |
| CPU-heavy jobs using GIL-holding native code | 900–1800 | 60 |
| Flaky network to the broker | 600 | 30 |

> **Note:** `timeout` on a job and the lease are independent. A job with `timeout="20m"`
> needs working heartbeats for the full 20 minutes, or a lease longer than 20 minutes.

## Heartbeat loss: ORB-1102

If the broker stops receiving a worker's heartbeats, Orbit records **ORB-1102
WorkerHeartbeatLost** and the dashboard marks the worker as lost. Its jobs are redelivered as
their leases expire, each logging ORB-1101. A worker that sees its own heartbeats failing
stops claiming new jobs until they succeed again. Since 3.1.2, ORB-1102 is no longer reported
for workers that shut down cleanly.

## Per-broker implementation

| Broker | Lease stored as | Heartbeat does |
|---|---|---|
| [Redis](broker-redis.md) | Score in the `orbit:leases` sorted set | Rewrites the score |
| [Postgres](broker-postgres.md) | `leased_until` column | `UPDATE ... SET leased_until = now() + lease` |
| [SQS](broker-sqs.md) | Message visibility timeout | `ChangeMessageVisibility` |

A worker shutting down gracefully hands prefetched jobs back at once and keeps heartbeating its
running jobs until they finish ([Workers](concepts-workers.md#shutdown)).

## Orbit 2.x

2.x had **only one** setting, `ORBIT_LEASE` (whole seconds, default 300; `[orbit] lease` in
`orbit.ini`). The heartbeat interval was **not configurable**. 2.x workers always heartbeated
at **one tenth of the lease**, which is 30 s with the default.

So raising `ORBIT_LEASE` to fix duplicates also slowed heartbeats. With `ORBIT_LEASE=3600`,
heartbeats went out every 6 minutes, and a crashed worker's jobs waited up to an hour. 3.0 split the two into `lease_seconds` and
`heartbeat_seconds`. `orbit migrate-config` doesn't write `heartbeat_seconds`, so migrated
workers use the 3.x default of 30 s whatever their old lease was. That is usually an
improvement. Check that `heartbeat_seconds` is still at most a third of `lease_seconds` if you
lowered the lease. See [Environment variables (2.x)](environment-variables-2x.md).

## See also

- [Duplicate execution](troubleshooting-duplicates.md)
- [Configuration reference](configuration-reference.md)
- [Error codes](error-codes.md)
