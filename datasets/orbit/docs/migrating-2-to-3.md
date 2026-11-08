---
id: migrating-2-to-3
title: Migrating from 2.x to 3.x
section: Migration
applies_to: "all"
updated: 2026-10-20
---

# Migrating from 2.x to 3.x

Orbit **3.0.0** (2026-03-02) made two big changes. It added [Flows](flows-overview.md), and it replaced `orbit.ini` + `ORBIT_*` environment variables with a single `orbit.toml`. Job code is almost unchanged: `Orbit(...)`, `@app.job(...)`, `.enqueue(...)` and `app.schedule(...)` keep the same signatures. Most of the migration is configuration and rollout order.

**2.9.0 is the last 2.x release and reaches end of life on 2026-12-31.** We recommend migrating straight to the current release, **3.2.1**.

## Before you start

- **Get to 2.9.0 first.** 3.x workers understand the job format that 2.9.0 producers write. Messages from older 2.x releases still in the queue should be drained before you upgrade.
- **Check your Python version.** Python 3.13 is not supported yet. Stay on 3.12 or earlier for now (see [FAQ](faq.md)).
- **List where configuration comes from.** Collect your `orbit.ini` and every place that sets `ORBIT_BROKER_URL`, `ORBIT_CONCURRENCY` or `ORBIT_LEASE`: Compose files, Kubernetes manifests, systemd units, CI. See [Environment variables (2.x)](environment-variables-2x.md).

## Step 1: Convert `orbit.ini`

Install 3.x in a separate virtualenv and run the converter next to your existing file:

```bash
$ orbit migrate-config orbit.ini
read orbit.ini (2 sections, 6 keys)
wrote orbit.toml
  [broker]   url
  [worker]   concurrency, lease_seconds
  [retries]  max_attempts, backoff, max_delay_seconds
note: ORBIT_BROKER_URL is set in this shell but was not migrated
```

> **Note:** Use `orbit migrate-config` from **3.0.3 or later**. The converter in 3.0.1 **silently dropped the `[retries]` section**, so migrated workers fell back to the default retry settings. If you migrated with 3.0.1, compare your `orbit.toml` with `orbit.ini` and add `[retries]` back.

How the converter behaves:

- It writes `orbit.toml` to the **current directory**. It refuses to run if an `orbit.toml` already exists there, so it never overwrites one.
- It reads **only the file**. `ORBIT_*` variables in your shell are not copied into the output. The converter only reminds you that they are set (see the last line of output above).
- An ini key with no 3.x equivalent is reported as **`ORB-1802 UnknownConfigKey`** and left out. The rest of the file is still converted.
- A file it cannot parse, or a value it cannot convert, stops the command with **`ORB-1801 ConfigMigrationError`**, and no `orbit.toml` is written.
- It reads `orbit.ini` the way 2.x does, **without** `ConfigParser` interpolation. `%(name)s` references are not resolved: convert those keys by hand. A literal `%`, such as a percent-encoded password, should be copied through unchanged.

## Step 2: Move the environment variables

Copy each variable into `orbit.toml` by hand:

| 2.x variable | 3.x `orbit.toml` | Notes |
|---|---|---|
| `ORBIT_BROKER_URL` | `[broker] url` | Or pass `Orbit(broker=os.environ["..."])` to keep secrets out of the file |
| `ORBIT_CONCURRENCY` | `[worker] concurrency` | `orbit worker --concurrency` still overrides it |
| `ORBIT_LEASE` | `[worker] lease_seconds` | Same unit (seconds) |

3.x **ignores** these variables. If you forget one, nothing fails. The worker just runs with the value in `orbit.toml` or the default. For example, a worker that had `ORBIT_LEASE=900` falls back to 300 seconds, and long jobs start running twice (`ORB-1101 LeaseExpired`). Run `orbit doctor` on each host. It warns about any `ORBIT_*` variable that is still set.

## Step 3: Review the new settings

3.x adds settings that 2.x did not have. Their defaults are safe, but check them:

| Setting | Default | Why check it |
|---|---|---|
| `[worker] heartbeat_seconds` | `30` | Must be well below `lease_seconds`; see [Leases and heartbeats](leases-and-heartbeats.md) |
| `[worker] prefetch` | `10` | Keep it at 100 or below on 3.2.x ([memory issue](troubleshooting-memory.md)) |
| `[results] backend` | `"redis"` | Set `"postgres"` or `"none"` if your broker is not Redis; see [Result backend](results-backend.md) |
| `[limits] max_payload_kb` | `512` | Larger payloads are rejected with `ORB-1202` |
| `[telemetry]` | off | Optional OTLP export; see [Metrics](observability-metrics.md) |
| `[dashboard] auth` | `"token"` | Consider OIDC for shared dashboards |

Every key is documented in the [Configuration reference](configuration-reference.md).

## Step 4: Roll out workers first, then producers

The two message formats are compatible **in one direction only**:

| | 2.9 producer | 3.x producer |
|---|---|---|
| **2.9 worker** | ✅ | ❌ cannot read 3.x jobs |
| **3.x worker** | ✅ | ✅ |

So the order is:

1. Deploy 3.x **workers** alongside, or in place of, the 2.9 workers. They consume jobs from both versions.
2. Once no 2.9 workers are left, deploy the 3.x **producers** (web apps, cron hosts, anything that calls `.enqueue()`).
3. Remove `orbit.ini` and the `ORBIT_*` variables.

If you deploy producers first, 2.9 workers that pick up the new jobs fail them, and those jobs end up in the [dead-letter queue](dead-letter-queue.md). You can replay them with `orbit dlq replay <job_id>` once 3.x workers are running.

## Step 5: Verify

```bash
$ orbit doctor
orbit 3.2.1 (python 3.12.6)
[ok]   config    orbit.toml loaded (6 sections)
[ok]   broker    redis://redis:6379/0 reachable (PING 0.6 ms)
[ok]   versions  4 workers online, all 3.2.1
```

Then watch for a few hours:

- `ORB-1101 LeaseExpired` in logs → a lease setting is missing (see Step 2)
- `ORB-1301 RetryExhausted` → check that `[retries]` came through the migration
- `ORB-1601 ResultBackendUnavailable` → `[results] backend` does not match your broker

## Rolling back

Keep `orbit.ini` and your 2.9 deployment artifacts until the migration is finished. Before you roll workers back to 2.9, **stop the 3.x producers and drain** the jobs they enqueued, because 2.9 workers cannot read them. Flow runs that are still in progress cannot be resumed on 2.x.

## See also

- [Changelog](changelog.md): what changed in each 3.x release
- [CLI reference](cli-reference.md): `orbit migrate-config`, `orbit doctor`
