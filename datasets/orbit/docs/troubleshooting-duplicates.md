---
id: troubleshooting-duplicates
title: "Troubleshooting: jobs running twice"
section: Troubleshooting
applies_to: "all"
updated: 2026-11-05
---

# Troubleshooting: jobs running twice

A customer got two receipts, or a webhook fired twice, or a counter went up by two. This page
explains why Orbit can run a job more than once and how to stop it from hurting.

## First, the guarantee

Orbit delivers jobs **at least once**. When a worker takes a job, the broker hides it for the
length of its **lease**. If the worker doesn't acknowledge the job before the lease runs out,
the broker assumes the worker died and hands the job to someone else. That's what makes Orbit
survive crashed workers, and it's also why duplicates are possible. Exactly-once execution of
arbitrary side effects isn't something any job queue can promise. What you can do is:

1. make duplicates **rare** by sizing leases and heartbeats correctly, and
2. make duplicates **harmless** with idempotency.

## Cause 1: lease expiry on long jobs (ORB-1101)

This is the most common cause by far, and it's **by design**: the lease is doing its job.

```text
09:00:00  worker-a  leased job j_8c0e71 (send_monthly_report), lease 300s
09:05:00  broker    lease expired, job visible again
09:05:01  worker-b  leased job j_8c0e71
09:05:01  worker-a  WARN ORB-1101 LeaseExpired job=j_8c0e71
09:07:40  worker-a  job finished (first run)
09:09:52  worker-b  job finished (second run)
```

Heartbeats renew the lease of a running job every `heartbeat_seconds`. A long job is only
redelivered when **its lease runs out before a heartbeat renews it**. In practice that happens
when:

- `heartbeat_seconds` is set close to or above `lease_seconds`, so one delayed heartbeat is
  enough to lose the lease;
- the job blocks the worker, for example with a tight CPU loop or a blocking C extension, so
  heartbeats can't be sent;
- the broker is unreachable for longer than the lease, so heartbeats fail.

**Fix:** keep heartbeats well inside the lease, and give genuinely long jobs a larger lease:

```toml
[worker]
lease_seconds = 900      # longer than your slowest healthy job
heartbeat_seconds = 30   # at most a third of lease_seconds
```

On 2.x there's no `orbit.toml`. Set `ORBIT_LEASE=900` instead
([environment-variables-2x.md](environment-variables-2x.md)). The mechanics are explained in
[leases-and-heartbeats.md](leases-and-heartbeats.md).

## Cause 2: the worker was killed mid-job

If a worker is killed with `SIGKILL`, by the OOM killer (ORB-2101), or because a node
disappeared, its running jobs are redelivered when their leases expire. Look for `WorkerHeartbeatLost`
(ORB-1102) around the time of the duplicate.

- Make sure your platform sends `SIGTERM` and waits. Set systemd's `TimeoutStopSec`
  ([deployment-systemd.md](deployment-systemd.md)) or Kubernetes'
  `terminationGracePeriodSeconds` ([deployment-kubernetes.md](deployment-kubernetes.md)) longer
  than your typical job.
- **Windows:** the worker currently ignores `SIGTERM`, so service managers fall back to a hard
  kill and in-flight jobs run again. Run production workers on Linux, in containers or WSL2
  ([faq.md](faq.md)).

## Cause 3: retries after a partial side effect

A retry runs the **whole** job again. If the job charged a card and then crashed while writing
to the database, the retry charges the card again. This isn't a lease problem. The fix is
idempotency (below), or moving each side effect into its own job or Flow step
([flows-overview.md](flows-overview.md)).

## Cause 4: the producer enqueued twice

Double-clicks, client retries on an HTTP timeout, or two services reacting to the same event all
produce two *distinct* jobs. The dashboard shows two different job IDs with the same arguments.
An idempotency key collapses them into one.

## Make duplicates harmless: idempotency keys

```python
from orbit import Orbit

app = Orbit(broker="redis://localhost:6379/0")

@app.job(retries=3, backoff="exponential", timeout="30s", idempotency_key="order_id")
def send_receipt(order_id: str):
    ...

send_receipt.enqueue(order_id="A-1001")
send_receipt.enqueue(order_id="A-1001")  # deduplicated: same key, same args
```

If a second enqueue uses the same key with *different* arguments, Orbit refuses it with
`IdempotencyConflict` (ORB-2001). That usually means the key isn't specific enough.

> **Note:** An idempotency key deduplicates **enqueues**. It doesn't stop a leased job from
> being redelivered after ORB-1101. For that, the job body itself must be safe to repeat: check
> a "sent" flag, use a provider-side idempotency token, or use an upsert. See
> [idempotency.md](idempotency.md).

## Diagnosis checklist

| What you see | Most likely cause | Fix |
|---|---|---|
| Same job ID ran twice, ORB-1101 in logs | Lease expiry | Larger `lease_seconds`, healthy heartbeats |
| Same job ID, ORB-1102 or a deploy at that time | Worker killed | Graceful shutdown timeouts |
| Same job ID, attempt number > 1 | Retry after partial work | Idempotent job body |
| Different job IDs, same arguments | Producer double-enqueue | `idempotency_key` |
| Duplicates only on Windows hosts | SIGTERM ignored | Run workers on Linux |

To see the attempt history and job IDs, open the job in the dashboard ([dashboard.md](dashboard.md)),
or search worker logs for the job ID.
