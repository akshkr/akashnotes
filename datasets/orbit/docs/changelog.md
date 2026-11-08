---
id: changelog
title: Changelog
section: Project
applies_to: "all"
updated: 2026-11-05
---

# Changelog

All notable changes to Orbit, newest first. Orbit follows semantic versioning. Breaking changes
only land in major releases. This page lists the major, minor and notable patch releases.
Known issues that cut across versions are collected at the end.

| Version | Released | Status |
|---|---|---|
| **3.2.1** | 2026-10-20 | Current |
| 3.2.0 | 2026-09-15 | Supported |
| 3.1.2 | 2026-07-08 | Critical fixes only |
| 3.1.0 | 2026-06-01 | Superseded by 3.1.2 |
| 3.0.3 | 2026-04-14 | Unsupported |
| 3.0.0 | 2026-03-02 | Unsupported |
| 2.9.0 | 2025-11-20 | Last 2.x. Security fixes until EOL on 2026-12-31 |
| 2.8.0 | 2025-06-10 | Unsupported |

The support policy is in [security.md](security.md#supported-versions).

## 3.2.1 (2026-10-20)

**Fixed**
- `orbit doctor` now checks that the result backend is reachable, not just the broker.
- `ScheduleDrift` (ORB-1402) is no longer logged for runs that are less than one second late.
- `orbit flows status <run_id>` no longer shows skipped steps as `pending`.

**Improved**
- `BrokerRateLimited` (ORB-1901) log lines now include the SQS queue name and message group.

**Still open**: the dashboard OIDC redirect loop behind a reverse proxy, and memory growth with
`prefetch` > 100. Both are described under 3.2.0.

## 3.2.0 (2026-09-15)

**Added**
- Dashboard: the OIDC login flow was rewritten (`[dashboard] auth = "oidc"`, `oidc_issuer`,
  `oidc_client_id`) and now reports `OIDCMisconfigured` (ORB-1702) at startup instead of on
  first login.
- Dashboard: you can filter the DLQ by error code.

**Changed**
- Worker: the prefetch buffer was reworked to reduce pickup latency for short jobs.

**Known issues**
- **OIDC redirect loop behind a reverse proxy.** When TLS is terminated at a proxy, login loops
  between the dashboard and the IdP. This is open. The workaround is to send
  `X-Forwarded-Proto: https` ([dashboard-auth-oidc.md](dashboard-auth-oidc.md)).
- **Memory growth with `prefetch` > 100** on 3.2.x. This is open. The workaround is to keep
  `prefetch` ≤ 100 ([troubleshooting-memory.md](troubleshooting-memory.md)).

## 3.1.2 (2026-07-08)

**Fixed**
- **Redis reconnect storm after failover**, introduced in 3.1.0. Reconnects now use jittered
  exponential backoff, and each worker process makes one shared reconnect attempt
  ([troubleshooting-broker.md](troubleshooting-broker.md)).
- `WorkerHeartbeatLost` (ORB-1102) is no longer reported for workers that shut down cleanly.

## 3.1.0 (2026-06-01)

**Added**
- Redis broker: new connection management with Sentinel and managed-failover support.
- Dashboard: a Flow runs view with per-step timings.
- Telemetry: OTLP spans for each Flow step, linked to the parent run (`[telemetry]`).

**Known issue**: workers could open thousands of connections in a reconnect storm after a Redis
failover. Fixed in 3.1.2. Upgrade directly to 3.1.2 or later.

## 3.0.3 (2026-04-14)

**Fixed**
- `orbit migrate-config` silently dropped the entire `[retries]` section. This was a regression
  reported against 3.0.1. If you migrated on 3.0.1, run the migration again and review
  `max_attempts`, `backoff` and `max_delay_seconds` ([migrating-2-to-3.md](migrating-2-to-3.md)).
- `ConfigMigrationError` (ORB-1801) now names the `orbit.ini` key it could not convert.
- Flow runs whose run record disappeared mid-run (for example through Redis eviction) now fail
  with `FlowStateCorrupt` (ORB-1503) instead of hanging.

## 3.0.0 (2026-03-02)

The first 3.x release. Read [migrating-2-to-3.md](migrating-2-to-3.md) before upgrading.

**Added**
- **Flows**: DAGs of Steps, built with `Flow(...)` and `step(..., after=...)`, run with
  `flow.run(...)` or `orbit flows run <name>`, and inspected with `orbit flows status <run_id>`.
  New codes: ORB-1501 `FlowCycleDetected`, ORB-1502 `StepTimeout`, ORB-1503 `FlowStateCorrupt`.
  See [flows-overview.md](flows-overview.md).
- **`orbit.toml`**: one config file with `[broker]`, `[worker]`, `[retries]`, `[results]`,
  `[dashboard]`, `[telemetry]` and `[limits]` sections ([configuration-reference.md](configuration-reference.md)).
- `orbit migrate-config orbit.ini` converts 2.x configuration. New codes: ORB-1801
  `ConfigMigrationError`, ORB-1802 `UnknownConfigKey`.

**Breaking**
- `orbit.ini` and the `ORBIT_*` environment variables (`ORBIT_BROKER_URL`, `ORBIT_CONCURRENCY`,
  `ORBIT_LEASE`) are replaced by `orbit.toml`.
- Unknown keys in `orbit.toml` are an error (ORB-1802), not a warning.

**Note**: Flow step results are subject to `[limits] max_payload_kb` (512 KB by default). A
larger result fails the step with `PayloadTooLarge` (ORB-1202).

## 2.9.0 (2025-11-20)

The last 2.x release. **End of life: 2026-12-31.**

**Added**
- Support for Python 3.12.
- Deprecation warnings for `orbit.ini` settings whose name or meaning changes in 3.0.

**Fixed**
- Postgres broker workers now reconnect after a database restart instead of exiting.

## 2.8.0 (2025-06-10)

**Added**
- `orbit doctor`, which checks broker connectivity, config and package versions.
- `orbit dlq purge`.

**Changed**
- `SerializationError` (ORB-1201) messages now name the offending argument and its type.

## Known issues across versions

| Issue | Affects | Status | Where |
|---|---|---|---|
| Duplicate execution when a long job outlives its lease (ORB-1101) | all | By design. Tune `heartbeat_seconds` or raise `lease_seconds` | [troubleshooting-duplicates.md](troubleshooting-duplicates.md) |
| SQS FIFO throttling (ORB-1901) | all | Mitigations documented | [troubleshooting-broker.md](troubleshooting-broker.md) |
| Scheduler drift across DST (ORB-1402) | all | Run schedulers in UTC | [scheduling-cron.md](scheduling-cron.md) |
| Windows worker ignores SIGTERM | all | Open | [faq.md](faq.md) |
| Flow step results over 512 KB (ORB-1202) | 3.x | Pass references | [flows-steps-and-state.md](flows-steps-and-state.md) |
| Postgres LISTEN/NOTIFY misses events under load | all | Under investigation | [troubleshooting-broker.md](troubleshooting-broker.md) |

**Requested, not scheduled:** Python 3.13 support, and priority aging for long-waiting jobs.
**Docs in progress:** idempotency with SQS ([faq.md](faq.md#how-do-i-make-jobs-idempotent-on-sqs)).
