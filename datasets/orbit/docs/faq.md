---
id: faq
title: Frequently asked questions
section: Help
applies_to: "all"
updated: 2026-11-05
---

# Frequently asked questions

Short answers with links to the page that has the details. If your question isn't here, search
the [error codes](error-codes.md) first. Most "why did X happen" questions start with an
`ORB-` code in the logs.

## General

### Does Orbit run each job exactly once?

No. Orbit delivers jobs **at least once**. A job whose lease expires (ORB-1101) or whose worker
dies can run again. Make side effects idempotent. See
[troubleshooting-duplicates.md](troubleshooting-duplicates.md).

### How do I check that my setup is healthy?

Run `orbit doctor`. It checks broker connectivity, validates your configuration, and reports
workers that are running mismatched Orbit versions.

### What's the largest payload I can enqueue?

512 KB by default, set by `[limits] max_payload_kb`. Larger payloads fail with
`PayloadTooLarge` (ORB-1202). The same limit applies to Flow step results. Pass references to
large data instead of the data itself ([performance-tuning.md](performance-tuning.md)).

### Is Python 3.13 supported?

Not yet. Orbit is tested up to Python 3.12. Python 3.13 support is an open feature request, and
the blocker is a C-extension dependency of the Redis broker. Follow the request in the issue
tracker rather than opening a new one.

### Can Orbit raise the priority of jobs that have waited a long time (priority aging)?

Not today. Priority aging is a requested feature, but nothing is scheduled. Until then, prevent
starvation of low-priority work by giving each queue its own workers
([scaling-workers.md](scaling-workers.md#separate-queues-separate-workers)) rather than relying
only on priorities ([concepts-queues-priorities.md](concepts-queues-priorities.md)).

### Does Orbit work on Windows?

For development, yes. For production, we recommend against it. There's a known issue where the
Windows worker **ignores SIGTERM**, so service managers have to kill it hard. In-flight jobs are
then redelivered after their lease expires and run twice. Use WSL2, Docker
([deployment-docker.md](deployment-docker.md)) or a Linux host.

## Versions and upgrades

### We're on 2.x. How long do we have?

2.9.0 (released 2025-11-20) is the last 2.x release. The 2.x line reaches **end of life on
2026-12-31**. Until then it gets security fixes only. See
[migrating-2-to-3.md](migrating-2-to-3.md).

### Where did `orbit.ini` and the `ORBIT_*` variables go?

Orbit 3.0.0 replaced them with a single `orbit.toml`. Convert an existing file with:

```bash
orbit migrate-config orbit.ini
```

The old variables (`ORBIT_BROKER_URL`, `ORBIT_CONCURRENCY`, `ORBIT_LEASE`) are documented in
[environment-variables-2x.md](environment-variables-2x.md).

### `orbit migrate-config` lost my retry settings

That's a bug in 3.0.1, where the converter silently dropped the whole `[retries]` section. It was
fixed in 3.0.3. Upgrade, run the migration again, and diff the result. If you migrated on 3.0.1
and deployed, your jobs have been running with the defaults (`max_attempts = 3`,
`backoff = "exponential"`, `max_delay_seconds = 600`) rather than your settings.

### What's the current release?

3.2.1, released 2026-10-20. See the [changelog](changelog.md).

## Dashboard

### Dashboard OIDC login loops forever behind our proxy

This is a known issue since 3.2.0, and it's still open. The dashboard builds its redirect URL as
`http://` because the proxy terminates TLS. Make the proxy send `X-Forwarded-Proto: https`.
For nginx, use the literal value. Don't use `$scheme`, which is `http` when nginx itself sits
behind a TLS-terminating load balancer:

```nginx
proxy_set_header X-Forwarded-Proto https;
```

See [dashboard-auth-oidc.md](dashboard-auth-oidc.md).

### What port does the dashboard use?

Whatever you pass: `orbit dashboard --port 7777`. Put it behind TLS ([security.md](security.md)).

## Brokers

### How do I make jobs idempotent on SQS?

We know this is under-documented, and better docs are in progress. The short version:

- SQS deployments run with `[results] backend = "none"`, so Orbit keeps **no idempotency
  records** on SQS. `idempotency_key` doesn't de-duplicate enqueues the way it does on Redis and
  Postgres.
- On a **FIFO** queue, Orbit passes the key to SQS as the `MessageDeduplicationId`, but SQS only
  remembers it for a **five-minute** window. A re-enqueue after that is a new message.
- Standard (non-FIFO) queues get no enqueue de-duplication at all, and can deliver a message
  twice even without a lease expiry. The job body must be safe to repeat.

Start with [idempotency.md](idempotency.md) and [broker-sqs.md](broker-sqs.md).

### We see ORB-1901 on SQS

That's SQS throttling, usually on FIFO queues. See
[troubleshooting-broker.md](troubleshooting-broker.md#sqs-fifo-throttling-orb-1901).

### Scheduled jobs ran an hour late after the clocks changed

That's `ScheduleDrift` (ORB-1402) around a DST transition. Run every worker in UTC, because any
worker can hold the scheduler lock, and write cron expressions in UTC
([scheduling-cron.md](scheduling-cron.md)).

## Failures

### Where do jobs go when they keep failing?

After the last retry they are moved to the dead-letter queue with `RetryExhausted` (ORB-1301).
Use `orbit dlq list`, `orbit dlq replay <job_id>` and `orbit dlq purge`
([dead-letter-queue.md](dead-letter-queue.md)).
