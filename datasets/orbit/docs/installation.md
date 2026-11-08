---
id: installation
title: Installation
section: Getting started
applies_to: all
updated: 2026-10-22
---

# Installation

Orbit is a pure-Python package published to PyPI as `orbit`. The core package has no broker
client. You choose a broker by installing an **extra**.

## Requirements

| Orbit line | Python | Status |
|---|---|---|
| 3.x (current: 3.2.1) | 3.10, 3.11, 3.12 | Supported |
| 2.x (last: 2.9.0) | 3.8 – 3.12 (3.12 needs 2.9.0) | Security fixes only, **EOL 2026-12-31** |

> **Note:** Python 3.13 is **not yet supported** on any Orbit release. The import works, but
> the test suite is not run against 3.13 and workers are known to emit deprecation warnings
> from a dependency. Support is tracked as an open feature request under `comp:core`; please
> add a reaction there instead of opening a new issue.

Broker servers you connect to:

| Broker | Minimum server version | Extra |
|---|---|---|
| Redis | 6.2 | `orbit[redis]` |
| PostgreSQL | 13 | `orbit[postgres]` |
| Amazon SQS | n/a (managed) | `orbit[sqs]` |

## Installing Orbit 3.x

Pick one broker extra, plus any optional extras you need:

```bash
# Redis broker (most common)
pip install "orbit[redis]"

# Postgres broker
pip install "orbit[postgres]"

# SQS broker
pip install "orbit[sqs]"

# Several at once
pip install "orbit[redis,dashboard,otel]"
```

| Extra | Adds |
|---|---|
| `redis` | Redis broker and Redis result backend |
| `postgres` | Postgres broker and Postgres result backend |
| `sqs` | Amazon SQS broker (uses the standard AWS credential chain; no result backend) |
| `dashboard` | The web UI started by `orbit dashboard` |
| `otel` | OTLP exporter for the `[telemetry]` section |
| `all` | Everything above |

In production, pin to a minor line so that a fresh build can't pull a new minor release
under you:

```text
# requirements.txt
orbit[redis,dashboard]>=3.2.1,<3.3
```

If you use Poetry or uv, the equivalent constraint is `orbit = {version = ">=3.2.1,<3.3",
extras = ["redis", "dashboard"]}` or `uv add "orbit[redis,dashboard]>=3.2.1,<3.3"`.

## Verifying the install

```bash
$ orbit --version
orbit 3.2.1 (python 3.12.6)

$ orbit doctor
orbit 3.2.1 (python 3.12.6)
[ok]   config    orbit.toml loaded (7 sections)
[ok]   broker    redis://localhost:6379/0 reachable (PING 0.4 ms)
[ok]   results   redis backend reachable
[ok]   worker    heartbeat_seconds=30 is at most lease_seconds/3 (300)
```

`orbit doctor` exits non-zero if any check fails, so you can use it as a container readiness
step. Common failures:

- **ORB-1001 BrokerConnectionError**: the broker host or port is wrong, or a firewall is
  in the way. See [Broker problems](troubleshooting-broker.md).
- **ORB-1002 BrokerAuthError**: the credentials in `[broker] url` were rejected.
- **ORB-1802 UnknownConfigKey**: `orbit.toml` has a key Orbit doesn't recognise. This is
  usually a typo or a 2.x key that was pasted in by hand. The
  [configuration reference](configuration-reference.md) lists every valid key.

## Installing or staying on 2.x

If you can't upgrade yet, pin below 3.0:

```bash
pip install "orbit[redis]>=2.9,<3"
```

2.x reads configuration from `orbit.ini` and `ORBIT_*` environment variables
(`ORBIT_BROKER_URL`, `ORBIT_CONCURRENCY`, `ORBIT_LEASE`). It does not read `orbit.toml`. See
[Environment variables (2.x)](environment-variables-2x.md).

> **Note:** `pip install orbit` with no version constraint installs 3.x. A 2.x project that
> picks up 3.x will start, but its workers will ignore `orbit.ini` and connect to the default
> broker. Always pin.

## Upgrading from 2.x

Upgrade the package, then convert your configuration:

```bash
pip install "orbit[redis]>=3.2.1,<3.3"
orbit migrate-config orbit.ini      # writes orbit.toml next to it
orbit doctor
```

Read [Migrating from 2.x to 3.x](migrating-2-to-3.md) before you upgrade production workers.
Run 2.x and 3.x workers against the same queues only as described there.

## Platform notes

- **Linux and macOS** are fully supported for production.
- **Windows** works for local development. Workers on Windows currently ignore `SIGTERM`, so
  use Ctrl+C to stop them (details in [Workers](concepts-workers.md#shutdown)). For
  production, run Linux workers or use WSL.
- **Containers**: see [Docker](deployment-docker.md) and
  [Kubernetes](deployment-kubernetes.md) for images and probes.

## Installing from source

To hack on Orbit itself, clone the repository and install it in editable mode with the dev
extras. [Contributing](contributing.md) describes the full test setup, including the
broker containers the integration tests need.

## Next steps

- [Quickstart](quickstart.md): run your first job
- [Brokers](concepts-brokers.md): choose between Redis, Postgres and SQS
