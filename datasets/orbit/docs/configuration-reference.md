---
id: configuration-reference
title: Configuration reference (orbit.toml)
section: Configuration
applies_to: "3.x"
updated: 2026-11-05
---

# Configuration reference (`orbit.toml`)

Orbit 3.x is configured through a single file, `orbit.toml`. It replaced the 2.x combination of `orbit.ini` and `ORBIT_*` environment variables in **3.0.0**. If you are still on 2.x, see [Environment variables (2.x)](environment-variables-2x.md). To convert an existing setup, see [Migrating from 2.x to 3.x](migrating-2-to-3.md).

## How configuration is loaded

Orbit reads `orbit.toml` from the **current working directory** whenever an `Orbit(...)` app is created or an `orbit` CLI command starts. Settings are resolved in this order, and the first source that sets a value wins:

1. Keyword arguments to the constructor, e.g. `Orbit(broker="redis://...")`
2. `orbit.toml`
3. Built-in defaults (listed below)

Environment variables are **not** a source in 3.x. Orbit ignores `ORBIT_BROKER_URL`, `ORBIT_CONCURRENCY` and `ORBIT_LEASE` even if they are set, and `orbit doctor` prints a warning when it finds them. To feed secrets in from the environment, read them yourself and pass them to the constructor:

```python
import os
from orbit import Orbit

app = Orbit(broker=os.environ["REDIS_URL"])
```

Alternatively, render `orbit.toml` when the container starts (see [Docker deployment](deployment-docker.md)).

**Unknown sections and keys are errors.** A typo such as `[worker] concurency = 8` stops startup with **`ORB-1802 UnknownConfigKey`**, and the message suggests the closest valid key. A value of the wrong type (a string where an integer is expected) also stops startup, with a message that names the key.

## Complete example

```toml
[broker]
url = "redis://:CHANGE_ME@redis.internal.example.com:6379/0"

[worker]
concurrency = 8
prefetch = 10
lease_seconds = 300
heartbeat_seconds = 30

[retries]
max_attempts = 3
backoff = "exponential"
max_delay_seconds = 600

[results]
backend = "redis"
ttl_days = 7

[dashboard]
auth = "oidc"
oidc_issuer = "https://login.example.com/"
oidc_client_id = "orbit-dashboard"

[telemetry]
otlp_endpoint = "http://otel-collector:4317"
service_name = "billing-workers"

[limits]
max_payload_kb = 512
```

## `[broker]`

| Key | Type | Default | Description |
|---|---|---|---|
| `url` | string | none | Broker connection URL. Required unless you pass `broker=` to `Orbit()`. The scheme picks the broker: [Redis](broker-redis.md), [Postgres](broker-postgres.md) or [SQS](broker-sqs.md) |

## `[worker]`

| Key | Type | Default | Description |
|---|---|---|---|
| `concurrency` | int | `4` | Jobs a worker process runs at the same time. `orbit worker --concurrency` overrides it |
| `prefetch` | int | `10` | Jobs a worker reserves ahead of time, on top of the ones it is running |
| `lease_seconds` | int | `300` | Visibility timeout. A job that is not acknowledged or renewed within this time can be handed to another worker |
| `heartbeat_seconds` | int | `30` | How often a running job's lease is renewed and worker liveness is reported |

`heartbeat_seconds` must be smaller than `lease_seconds`, or leases expire between heartbeats. `orbit doctor` warns when `heartbeat_seconds` is more than a third of `lease_seconds`. Leases that expire on long jobs cause duplicate runs (`ORB-1101 LeaseExpired`). See [Leases and heartbeats](leases-and-heartbeats.md).

> **Note:** Do not set `prefetch` above 100 on 3.2.x. There is an **open** issue in which workers' memory keeps growing when `prefetch` is greater than 100. Most workloads gain nothing above 20–50. See [Troubleshooting memory](troubleshooting-memory.md).

## `[retries]`

| Key | Type | Default | Description |
|---|---|---|---|
| `max_attempts` | int | `3` | Default retry limit for jobs that do not pass `retries=` to `@app.job` |
| `backoff` | string | `"exponential"` | Default backoff strategy: `"exponential"`, `"linear"` or `"fixed"` |
| `max_delay_seconds` | int | `600` | Upper limit on any single retry delay |

The values you pass to `@app.job(...)` always win over this section. How attempts are counted, and how the backoff delay grows, is covered in [Retries and backoff](retries-and-backoff.md).

## `[results]`

| Key | Type | Default | Description |
|---|---|---|---|
| `backend` | string | `"redis"` | `"redis"`, `"postgres"` or `"none"` |
| `ttl_days` | int | `7` | How long results and finished flow runs are kept |

The result backend uses the `[broker] url` connection. It has no URL of its own. See [Result backend](results-backend.md) for which combinations are supported.

## `[dashboard]`

| Key | Type | Default | Description |
|---|---|---|---|
| `auth` | string | `"token"` | `"token"` or `"oidc"` |
| `oidc_issuer` | string | none | Issuer URL. Required when `auth = "oidc"` |
| `oidc_client_id` | string | none | Client ID registered with your identity provider. Required when `auth = "oidc"` |

If `auth = "oidc"` is set and either OIDC key is missing, the dashboard will not start and reports `ORB-1702 OIDCMisconfigured`. See [Dashboard](dashboard.md) and [Dashboard OIDC sign-in](dashboard-auth-oidc.md).

## `[telemetry]`

| Key | Type | Default | Description |
|---|---|---|---|
| `otlp_endpoint` | string | none | OTLP/gRPC endpoint. If it is not set, telemetry export is turned off |
| `service_name` | string | `"orbit"` | Value of the `service.name` resource attribute |

See [Metrics](observability-metrics.md) and [Tracing](observability-tracing.md).

## `[limits]`

| Key | Type | Default | Description |
|---|---|---|---|
| `max_payload_kb` | int | `512` | Largest serialized job payload, or step/job result, in KB |

A payload over the limit is rejected at enqueue time with **`ORB-1202 PayloadTooLarge`**, and a result over the limit is rejected when the job finishes. Raising the limit affects every broker round trip, so prefer passing IDs or references.

## Validating a config

```bash
$ orbit doctor
```

`orbit doctor` loads `orbit.toml` with the same rules as a worker, connects to the broker and checks that worker versions match. See [CLI reference](cli-reference.md#orbit-doctor).
