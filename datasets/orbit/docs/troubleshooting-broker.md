---
id: troubleshooting-broker
title: Troubleshooting broker problems
section: Troubleshooting
applies_to: "all"
updated: 2026-11-05
---

# Troubleshooting broker problems

When workers sit idle while jobs pile up, or logs fill with `ORB-10xx` codes, the broker
connection is the first suspect. Start with one command:

```bash
orbit doctor
```

`orbit doctor` connects to the configured broker, validates your config and compares package
versions. On 3.x it reads `orbit.toml`. On 2.x it reads `orbit.ini` and `ORBIT_BROKER_URL`.
Fix whatever it reports before going further.

## Quick symptom table

| Symptom | Likely code | Section |
|---|---|---|
| Workers can't start, "connection refused" | ORB-1001 | [Connection errors](#connection-errors-orb-1001) |
| "WRONGPASS", "password authentication failed", AccessDenied | ORB-1002 | [Auth errors](#auth-errors-orb-1002) |
| Thousands of Redis connections after a failover | ORB-1001 flood | [Reconnect storm](#redis-reconnect-storm-after-failover-310) |
| SQS throughput caps out, warnings in logs | ORB-1901 | [SQS throttling](#sqs-fifo-throttling-orb-1901) |
| Postgres jobs wait several seconds before pickup | none | [LISTEN/NOTIFY](#postgres-listennotify-misses-events-under-load) |

## Connection errors (ORB-1001)

1. Check the URL that's actually in effect. In 3.x that's `[broker] url`. A `broker=` argument
   to `Orbit(...)` overrides it.
2. From the worker host, test the network path, for example `redis-cli -u "$URL" ping` or
   `psql "$URL" -c 'select 1'`.
3. In containers, `localhost` means the container itself, not the host.
4. Brief ORB-1001 bursts during a planned broker restart are normal. Workers reconnect, and jobs
   that were running stay leased until their lease expires.

## Auth errors (ORB-1002)

Auth errors don't fix themselves through retries. Check:

- the password in the URL is URL-encoded (`@` becomes `%40`, `/` becomes `%2F`);
- the Redis ACL user has permission on the key prefix Orbit uses;
- the Postgres role can `LISTEN` and can write the jobs table;
- for SQS, the instance role has `sqs:ReceiveMessage`, `sqs:DeleteMessage`,
  `sqs:ChangeMessageVisibility` and `sqs:SendMessage`.

## Redis reconnect storm after failover (3.1.0)

**Affects:** 3.1.0 only. **Fixed in:** 3.1.2.

After a Redis primary failover (Sentinel, or a managed service promoting a replica), 3.1.0
workers reconnected immediately and in parallel from every worker slot, with no backoff. Redis
CPU went to 100%, `connected_clients` climbed into the thousands, and logs showed a wall of
ORB-1001. The cluster often fell over again under the load.

```text
WARN orbit.broker.redis ORB-1001 BrokerConnectionError: Connection reset by peer (attempt 1)
WARN orbit.broker.redis ORB-1001 BrokerConnectionError: Connection reset by peer (attempt 1)
... repeated ~4,000 times in 20 seconds
```

**Fix:** Upgrade to 3.1.2 or later. 3.1.2 added jittered exponential backoff to reconnects and
shares one reconnect attempt per worker process.

**If you can't upgrade yet:** stop all workers, wait for the failover to finish, then start
workers in small batches. Setting a Redis `maxclients` limit protects the broker but not your
throughput.

## SQS FIFO throttling (ORB-1901)

**Affects:** all versions.

FIFO queues have much lower API request limits than standard queues. Ordering is per message
group, so a queue with only one group processes one message at a time no matter how many
workers you add. Orbit logs `BrokerRateLimited` (ORB-1901) and backs off.

Fixes, roughly in order of impact:

1. **Use more message groups.** If you only need ordering per customer, group by customer.
2. **Reduce receive calls.** Fewer, larger receives beat many small ones. SQS returns at most 10
   messages per call, so `prefetch = 10` is the sweet spot ([scaling-workers.md](scaling-workers.md)).
3. **Enable high-throughput mode** on the FIFO queue in AWS.
4. **Switch to a standard queue** and make the job body itself safe to run twice
   ([idempotency.md](idempotency.md#making-side-effects-idempotent)).

> **Note:** FIFO deduplication in SQS only covers a five-minute window, and Orbit keeps no
> idempotency records of its own on SQS. Neither gives you long-lived de-duplication. See
> [broker-sqs.md](broker-sqs.md#idempotency-on-sqs) and [faq.md](faq.md).

## Postgres LISTEN/NOTIFY misses events under load

**Affects:** the Postgres broker, all versions. Status: under investigation.

The Postgres broker uses `LISTEN/NOTIFY` to wake workers when a job is enqueued. Under heavy
write load, notifications can be missed. Workers then only find the job on their next poll, so
jobs are **delayed, not lost**. The dashboard shows a growing "age of oldest job" while workers
look idle.

Things that make it worse:

- **PgBouncer in transaction pooling mode.** `LISTEN` is session-scoped and doesn't work through
  transaction pooling. Connect workers directly or use session pooling.
- A listener connection that's busy, or long transactions on the jobs table.

See [broker-postgres.md](broker-postgres.md) for how the Postgres broker polls and listens.

## Result backend vs broker

`ResultBackendUnavailable` (ORB-1601) looks similar but has nothing to do with the broker. The
job ran, and only saving its result failed. See [results-backend.md](results-backend.md).

Still stuck? Collect `orbit doctor` output and the first ORB code from the logs, then open an
issue labelled `comp:broker-redis`, `comp:broker-postgres` or `comp:broker-sqs`
([contributing.md](contributing.md)).
