---
id: error-codes
title: Error codes
section: Reference
applies_to: "all"
updated: 2026-11-05
---

# Error codes

Every error Orbit raises or logs has a stable code of the form `ORB-NNNN`. Codes never change
meaning between releases, so it's safe to search for them, alert on them and match on them.
In Python, each code is an exception class with the same name, for example
`BrokerConnectionError` for ORB-1001.

```text
2026-10-22T08:14:03Z WARN  orbit.worker ORB-1101 LeaseExpired job=j_5f2a0c queue=default lease_seconds=300
```

| Range | Area |
|---|---|
| 10xx | Broker connectivity |
| 11xx | Leases and worker liveness |
| 12xx | Payloads |
| 13xx | Retries |
| 14xx | Scheduler |
| 15xx | Flows (3.x only) |
| 16xx | Result backend |
| 17xx | Dashboard auth |
| 18xx | Configuration (3.x only) |
| 19xx | Broker rate limits |
| 20xx | Idempotency |
| 21xx | Worker resources |

## Broker

### ORB-1001 BrokerConnectionError
**Cause:** The broker is unreachable. Common reasons are a wrong host or port, DNS, a firewall,
or the broker restarting. **Fix:** Run `orbit doctor`, then check `[broker] url` (on 2.x,
`ORBIT_BROKER_URL`). A flood of these right after a Redis failover on 3.1.0 is a known bug, fixed
in 3.1.2. See [troubleshooting-broker.md](troubleshooting-broker.md).

### ORB-1002 BrokerAuthError
**Cause:** The broker rejected the credentials. **Fix:** Check the user and password in the URL,
the Redis ACLs, the Postgres role, or the IAM permissions for SQS.

### ORB-1901 BrokerRateLimited
**Cause:** SQS throttled a request from a worker or producer. This is most common on FIFO
queues. **Fix:** Lower the number of receive calls (fewer workers, `prefetch` ≤ 10), spread work
across message groups, or switch to a standard queue and make the job body idempotent. See
[broker-sqs.md](broker-sqs.md#fifo-queues-and-throttling-orb-1901).

## Leases and workers

### ORB-1101 LeaseExpired
**Cause:** A job outlived its lease, so it may run twice. **Fix:** Make sure heartbeats can renew
the lease (`[worker] heartbeat_seconds`), or raise `[worker] lease_seconds` for long jobs. On 2.x,
use `ORBIT_LEASE`. See [troubleshooting-duplicates.md](troubleshooting-duplicates.md).

### ORB-1102 WorkerHeartbeatLost
**Cause:** The broker stopped receiving a worker's heartbeats. The worker may have frozen, lost
its network connection, or been killed. **Fix:** Look for CPU-bound code that blocks the worker
and for network partitions. The worker's jobs are redelivered when their leases expire.

### ORB-2101 WorkerOOM
**Cause:** A worker process was killed for exceeding available memory. **Fix:** Lower
`concurrency`, keep payloads small, and on 3.2.x keep `prefetch` ≤ 100. See
[troubleshooting-memory.md](troubleshooting-memory.md).

## Payloads

### ORB-1201 SerializationError
**Cause:** Job arguments aren't JSON-serializable, for example a `datetime`, a `set` or an ORM
object. **Fix:** Pass primitives and IDs, and convert other types explicitly.

### ORB-1202 PayloadTooLarge
**Cause:** The arguments, or a Flow step result, are over `[limits] max_payload_kb` (default
512). **Fix:** Store large data elsewhere and pass a reference.

## Retries

### ORB-1301 RetryExhausted
**Cause:** A job failed on every attempt allowed by its retry policy, and Orbit moved it to the
DLQ. **Fix:** Inspect it with `orbit dlq list`, fix the root cause, then run
`orbit dlq replay <job_id>`. See [dead-letter-queue.md](dead-letter-queue.md).

## Scheduler

### ORB-1401 ScheduleParseError
**Cause:** The cron expression passed to `app.schedule(..., cron=...)` is invalid. **Fix:** Use
five fields, for example `"0 9 * * MON"`.

### ORB-1402 ScheduleDrift
**Cause:** A scheduled run fired noticeably late or early. The usual reasons are a DST transition
or clock skew between hosts. **Fix:** Keep hosts NTP-synced and run every worker in UTC. See
[scheduling-cron.md](scheduling-cron.md).

## Flows (3.x)

### ORB-1501 FlowCycleDetected
**Cause:** The `after=` dependencies form a loop. **Fix:** Make the step graph acyclic.

### ORB-1502 StepTimeout
**Cause:** A step ran longer than its timeout (the `step(..., timeout=)` override, or else its
job's `timeout`). **Fix:** Raise the timeout or split the step into smaller steps.

### ORB-1503 FlowStateCorrupt
**Cause:** A run's record in the result backend is missing or can't be decoded while the run is
still in progress. The usual reasons are Redis eviction (`maxmemory-policy` not `noeviction`),
keys or rows deleted or edited by hand, or workers on different 3.x minor versions writing the
same run. **Fix:** Purge the run's DLQ entries and start a fresh run. See
[flows-error-handling.md](flows-error-handling.md#recovering-from-orb-1503).

## Results

### ORB-1601 ResultBackendUnavailable
**Cause:** Orbit can't reach the result backend, or `[results] backend` doesn't match the broker
(for example the default `"redis"` with an SQS broker). **Fix:** Check `[results] backend` and its
connectivity. While the backend is down, enqueues with an idempotency key are refused, workers
don't acknowledge jobs whose results they can't write (so those jobs run again once their lease
expires), and flow runs can't advance. See [results-backend.md](results-backend.md).

## Dashboard

### ORB-1701 DashboardAuthFailed
**Cause:** A bad token or a rejected OIDC login. **Fix:** Check `[dashboard] auth` and the user's
credentials.

### ORB-1702 OIDCMisconfigured
**Cause:** `oidc_issuer` or `oidc_client_id` is missing or wrong. **Fix:** See
[dashboard-auth-oidc.md](dashboard-auth-oidc.md).

## Configuration (3.x)

### ORB-1801 ConfigMigrationError
**Cause:** `orbit migrate-config orbit.ini` could not convert a setting. **Fix:** Convert that
key by hand. On 3.0.1, also re-run with 3.0.3 or later, which no longer drops `[retries]`.

### ORB-1802 UnknownConfigKey
**Cause:** `orbit.toml` has a typo or an unsupported key. **Fix:** Compare it with
[configuration-reference.md](configuration-reference.md).

## Idempotency

### ORB-2001 IdempotencyConflict
**Cause:** A job was enqueued with an idempotency key that matches an existing job, but with
different arguments. **Fix:** Derive the key from everything that makes the work unique. See
[idempotency.md](idempotency.md).
