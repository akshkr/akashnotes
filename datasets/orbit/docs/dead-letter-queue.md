---
id: dead-letter-queue
title: Dead-letter queue
section: Reliability
applies_to: all
updated: 2026-10-02
---

# Dead-letter queue (DLQ)

When a job has used all of its attempts, Orbit stops retrying it and moves it to the
**dead-letter queue**, logging **ORB-1301 RetryExhausted**. A dead job keeps everything you
need to rerun it: its arguments, queue, priority, idempotency key, attempt history and the
last exception with its traceback.

```text
ERROR orbit.worker [ORB-1301] RetryExhausted: job j_7a3e10 send_receipt failed 3/3 attempts;
      moved to DLQ (queue=emails)
```

The DLQ exists so that failures are **parked, not lost**. Nothing in it runs again until you
tell it to.

## What ends up in the DLQ

Any job that exhausted its retry policy (see [Retries and backoff](retries-and-backoff.md)):

- jobs whose attempts all raised or timed out;
- jobs that never raised but kept outliving their lease. Each lease expiry (ORB-1101) counts as
  an attempt;
- **flow steps** (3.x) that exhausted their retries. Their entry carries the flow run ID, and
  replaying them resumes the run. See [Error handling in flows](flows-error-handling.md).

Not in the DLQ: errors raised at enqueue time, such as ORB-1201 SerializationError, ORB-1202
PayloadTooLarge and ORB-2001 IdempotencyConflict. The caller receives these as exceptions, and
no job is ever created.

## Retention

> **Note:** Dead jobs are kept **until you replay or purge them**. They have no expiry. The
> `[results] ttl_days` setting applies to job results, flow runs and idempotency records,
> **not** to the DLQ. A DLQ nobody looks at grows forever, so alert on its size.

Where the DLQ lives depends on the broker:

| Broker | Storage |
|---|---|
| Redis | List `orbit:dlq:<queue>` plus the job hash |
| Postgres | Table `orbit_dead_jobs` |
| SQS | Orbit-managed queue `<prefix>-<queue>-dlq` (not an SQS redrive DLQ) |

## Inspecting: `orbit dlq list`

```text
$ orbit dlq list
JOB ID     JOB              FLOW RUN       ERROR     FAILED AT
j_7a3e10   send_receipt     -              ORB-1301  2026-10-01T14:02:11Z
j_7a3e5c   send_receipt     -              ORB-1301  2026-10-01T14:02:13Z
j_7b0042   export_report    fr_01JC4N8T2W  ORB-1301  2026-10-01T15:40:57Z
```

Entries are listed oldest first. `FLOW RUN` is `-` for standalone jobs. The list is meant for
scripting. For triage, open the DLQ in the [dashboard](dashboard.md). It shows the last
exception, the full traceback and every attempt, and since 3.2.0 you can filter it by error
code.

What to look for:

- **The same exception on many jobs within a few seconds** usually means a dependency outage
  (an SMTP server, a partner API). Fix or wait out the outage, then replay.
- **Attempts that ended in ORB-1101 LeaseExpired** mean the job is too long for its lease.
  Replaying won't help until you fix the lease. See
  [Leases and heartbeats](leases-and-heartbeats.md).
- **A one-off exception on a single job** is usually bad input or a bug. Read the traceback
  before you replay.

## Replaying: `orbit dlq replay <job_id>`

```text
$ orbit dlq replay j_7a3e10
replayed j_7a3e10 -> j_7c91d4
```

Replay puts the job back on its **original queue** as a **new job with a new ID** (the second
ID printed). It keeps the original arguments and idempotency key, and the attempt count starts
again from zero, so the job gets the full retry policy. The dashboard links the new job to the
dead original.

Replay uses the retry policy in your *current* code and config, not the policy the job had
when it died. That lets you deploy a fix (or a higher `retries`) first, and then replay.

### Replaying many jobs

`orbit dlq replay` takes one job ID. To replay a batch, filter the list output:

```bash
# Replay every dead send_receipt job (standalone jobs only)
orbit dlq list | awk 'NR>1 && $2=="send_receipt" && $3=="-" {print $1}' \
  | xargs -n1 orbit dlq replay
```

> **Note:** Replay a small sample first. If the root cause isn't fixed, a mass replay moves the
> same jobs back into the DLQ a few minutes later, after hammering the failing dependency
> again.

### Replay and idempotency

A dead job **keeps its idempotency key reserved**. If your application enqueues the same key
again, it gets the dead job's handle back and no new job is created. `orbit dlq replay` is the
supported way to rerun the work, and the replayed job takes over the key. See
[Idempotency](idempotency.md).

## Purging: `orbit dlq purge`

```text
$ orbit dlq purge
Delete 3 dead-lettered job(s)? This cannot be undone. [y/N]: y
purged 3 job(s)
```

Purge deletes **every** DLQ entry on the broker after asking for confirmation. In scripts
without a TTY, pipe the answer in (`yes | orbit dlq purge`). It can't be undone, so save the
list first (`orbit dlq list > dlq-2026-10-01.txt`). Purging also releases the idempotency keys
those jobs held. Purging a flow step's entry leaves its run permanently `failed`.
`orbit dlq purge` has been available since 2.8.0.

## Operating the DLQ

- **Alert on DLQ depth.** It should be zero or close to zero. A DLQ that keeps growing is an
  incident. See [Metrics](observability-metrics.md).
- **Review it daily.** Replay what an outage caused, fix what a bug caused, and purge
  deliberately.
- **Restrict dashboard access.** Anyone who can sign in to the dashboard can replay and purge.
  See [Dashboard](dashboard.md).

## See also

- [Retries and backoff](retries-and-backoff.md)
- [CLI reference](cli-reference.md#orbit-dlq)
- [Error codes](error-codes.md)
