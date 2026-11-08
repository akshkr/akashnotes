---
id: concepts-workers
title: Workers
section: Concepts
applies_to: 3.x
updated: 2026-10-24
---

# Workers

A **worker** is a long-running process that claims jobs from one or more queues, runs them,
and reports the outcome to the broker. You start one with the CLI:

```bash
orbit worker --queues default,high --concurrency 8
```

You can run as many worker processes as you like, on as many machines as you like. They
coordinate only through the broker. They never talk to each other directly.

## Anatomy of a worker process

Each worker process has two parts:

- A **supervisor** loop. It claims jobs from the broker, keeps a small local buffer of
  prefetched jobs, sends [heartbeats](leases-and-heartbeats.md) that renew the lease on every
  running job, and handles signals.
- A pool of **execution slots**, one per unit of `concurrency`. Plain functions run in a
  thread per slot. `async def` jobs run as tasks on a shared event loop.

Because sync jobs run in threads, CPU-bound work in pure Python is limited by the GIL. For
CPU-heavy jobs, run more worker processes with a lower `--concurrency` each, not one process
with a high value. [Scaling workers](scaling-workers.md) has sizing recipes.

## Configuration

Worker settings live in the `[worker]` section of `orbit.toml`:

```toml
[worker]
concurrency = 4           # execution slots per worker process
prefetch = 10             # jobs claimed ahead of free slots
lease_seconds = 300       # how long a claim is valid without a heartbeat
heartbeat_seconds = 30    # how often running jobs' leases are renewed
```

Precedence, from highest to lowest:

1. CLI flags (`--concurrency`, `--queues`)
2. `orbit.toml`
3. Built-in defaults (shown above)

> **Note:** In 2.x the same settings came from environment variables: `ORBIT_CONCURRENCY` and
> `ORBIT_LEASE` (there was no separate prefetch or heartbeat setting). 3.x ignores `ORBIT_*`
> variables completely. A worker whose container still sets them starts without complaint.
> Only `orbit doctor` warns about them. Run `orbit migrate-config` and see
> [Migrating from 2.x to 3.x](migrating-2-to-3.md).

### Concurrency

`concurrency` is the number of jobs a single worker process runs at the same time. The
default of 4 is deliberately conservative. I/O-bound jobs (HTTP calls, database writes) often
run well at 16–32 per process. CPU-bound jobs rarely benefit from more than one per core.

Total cluster concurrency is `processes × concurrency`. Remember that every slot may hold a
database or HTTP connection, and size your connection pools to match.

### Prefetch

`prefetch` is how many *extra* jobs the supervisor claims beyond its free slots, so that a
slot that finishes can start the next job without a broker round trip. Prefetched jobs are
leased to this worker even though they haven't started yet. That has two consequences:

- A large prefetch on a slow worker can starve faster workers. Jobs sit in one worker's buffer
  while other workers are idle.
- Prefetched jobs count against their lease. If a job waits in the buffer longer than
  `lease_seconds`, it is redelivered elsewhere (**ORB-1101 LeaseExpired**).

> **Warning:** On **3.2.x**, setting `prefetch` above about 100 causes steady memory growth in
> the supervisor. This is an open issue (`comp:core`). Keep `prefetch` at 100 or below. The
> default of 10 is fine for nearly everyone. If a worker is killed for memory, Orbit records
> **ORB-2101 WorkerOOM** against the jobs it was running. See
> [Memory growth](troubleshooting-memory.md).

## Choosing queues

`--queues` takes a comma-separated list of queue names. A worker consumes **only** the queues
you list. The order of the list doesn't matter; see
[Queues and priorities](concepts-queues-priorities.md) for how a worker picks between them.

```bash
# Latency-sensitive work gets its own pool
orbit worker --queues high --concurrency 16

# Everything else
orbit worker --queues default,reports --concurrency 4
```

Every worker also takes part in [cron scheduling](scheduling-cron.md). Exactly one worker in
the cluster holds the scheduler lock at a time, whatever queues it consumes.

## Startup checks

On start, the worker logs its effective configuration and runs the same checks as
`orbit doctor`:

```text
2026-10-24T08:12:03Z INFO  orbit.worker  orbit 3.2.1 worker w-7f3a starting
2026-10-24T08:12:03Z INFO  orbit.worker  queues=default,high concurrency=8 prefetch=10
2026-10-24T08:12:03Z INFO  orbit.worker  lease_seconds=300 heartbeat_seconds=30
2026-10-24T08:12:03Z INFO  orbit.broker  connected redis://localhost:6379/0
```

If the broker is unreachable, the worker retries the connection with backoff and logs
**ORB-1001 BrokerConnectionError**. It does not exit, so your process manager doesn't
restart-loop it.

## Shutdown

On `SIGTERM` or `SIGINT` a worker shuts down gracefully:

1. It stops claiming new jobs.
2. It hands prefetched-but-unstarted jobs back to the broker immediately.
3. It waits for running jobs to finish, still heartbeating while it waits.
4. It exits when the last running job completes.

A second `SIGTERM` or `SIGINT` forces an immediate exit. Jobs that were still running are
**not** acknowledged. They are redelivered when their leases expire, which is safe as long as
your jobs are [idempotent](idempotency.md). Under Kubernetes, set
`terminationGracePeriodSeconds` to at least your longest expected job duration. See
[Kubernetes](deployment-kubernetes.md).

> **Note:** **Windows workers ignore `SIGTERM`.** This is a known issue (`comp:core`). On
> Windows, stop a worker with Ctrl+C (which sends `CTRL_C_EVENT` and triggers the same graceful
> shutdown). Process managers that only send `SIGTERM` will hang until their kill timeout. We
> recommend Linux or WSL for anything beyond local development.

## Health and liveness

When the broker stops receiving a worker's heartbeats, Orbit records **ORB-1102
WorkerHeartbeatLost** for that worker. A worker that sees its own heartbeats failing stops
claiming new work until they succeed again. Heartbeat age, not CPU or memory, is the right
liveness signal. The [dashboard](dashboard.md) lists
live workers, and [Metrics](observability-metrics.md) exposes per-worker heartbeat age.

## See also

- [Leases and heartbeats](leases-and-heartbeats.md)
- [Scaling workers](scaling-workers.md)
- [Performance tuning](performance-tuning.md)
- [CLI reference](cli-reference.md)
