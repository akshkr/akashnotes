---
id: environment-variables-2x
title: Environment variables (2.x)
section: Configuration
applies_to: "2.x"
updated: 2026-03-02
---

# Environment variables (2.x)

> **Note:** This page is for **Orbit 2.x** (2.8 and 2.9) only. Orbit 3.x ignores every variable listed here and reads its settings from [`orbit.toml`](configuration-reference.md). 2.9.0 is the last 2.x release, and it reaches **end of life on 2026-12-31**. After that date it gets no further fixes, including security fixes. Plan your move with [Migrating from 2.x to 3.x](migrating-2-to-3.md).

In 2.x, settings come from an `orbit.ini` file plus a small set of `ORBIT_*` environment variables. The environment variables exist so that container platforms can inject the broker URL and worker sizing without changing the file.

## Supported variables

2.x reads exactly **three** environment variables:

| Variable | Type | Default | Overrides `orbit.ini` key | 3.x equivalent |
|---|---|---|---|---|
| `ORBIT_BROKER_URL` | URL string | none | `[orbit] broker_url` | `[broker] url` |
| `ORBIT_CONCURRENCY` | positive integer | `4` | `[orbit] concurrency` | `[worker] concurrency` |
| `ORBIT_LEASE` | integer **seconds** | `300` | `[orbit] lease` | `[worker] lease_seconds` |

Other settings, including the `[retries]` section, can only be set in `orbit.ini`. Orbit 2.x ignores variables such as `ORBIT_RETRIES` or `ORBIT_PREFETCH`, and does not warn you about them. If a setting seems to have no effect, check that it is one of the three above.

## Precedence in 2.x

In 2.x, **an environment variable wins over `orbit.ini`**. The full order is:

1. Keyword arguments to `Orbit(...)`, e.g. `Orbit(broker="redis://...")`
2. `ORBIT_*` environment variables
3. `orbit.ini`
4. Built-in defaults

This caused the most common 2.x support question: "I changed `concurrency` in `orbit.ini` and nothing happened." The deployment was also setting `ORBIT_CONCURRENCY`, which silently won.

Variables are read **once, when the process starts**. If you change them, restart the workers.

## Value formats

### `ORBIT_BROKER_URL`

The same URL format as the 3.x `[broker] url`:

```bash
export ORBIT_BROKER_URL="redis://:CHANGE_ME@redis.internal.example.com:6379/0"
```

If the URL contains special characters such as `@`, `:` or `/` in the password, percent-encode them. A wrongly encoded URL usually shows up as `ORB-1002 BrokerAuthError` and not as a parse error, because the password is cut at the first unescaped character.

### `ORBIT_CONCURRENCY`

A positive integer. `0`, negative numbers and non-numeric values make the worker exit at startup. The `--concurrency` flag on `orbit worker` overrides this variable.

### `ORBIT_LEASE`

A whole number of **seconds**. Duration strings are **not** accepted in 2.x: `ORBIT_LEASE=5m` makes the worker exit at startup with `invalid literal for int()`. Use `ORBIT_LEASE=300`.

If your jobs sometimes run longer than the lease, raise this value. Otherwise a second worker may pick up the same job while the first is still running it (`ORB-1101 LeaseExpired`). See [Leases and heartbeats](leases-and-heartbeats.md) and [Troubleshooting duplicates](troubleshooting-duplicates.md).

## Example: Docker Compose on 2.9

```yaml
services:
  worker:
    image: registry.example.com/billing-worker:2025.11
    command: orbit worker --queues default,high
    environment:
      ORBIT_BROKER_URL: "redis://redis:6379/0"
      ORBIT_CONCURRENCY: "8"
      ORBIT_LEASE: "900"   # nightly invoices take up to ~10 min
    volumes:
      - ./orbit.ini:/app/orbit.ini:ro
```

## Example: Kubernetes on 2.9

```yaml
env:
  - name: ORBIT_BROKER_URL
    valueFrom:
      secretKeyRef:
        name: orbit-broker
        key: url
  - name: ORBIT_CONCURRENCY
    value: "8"
  - name: ORBIT_LEASE
    value: "600"
```

## Checking what a 2.x worker is using

`orbit doctor` on 2.9 prints each resolved setting and where it came from:

```text
$ orbit doctor
orbit 2.9.0 (python 3.11.9)
broker_url   redis://redis:6379/0   (env ORBIT_BROKER_URL)
concurrency  8                      (env ORBIT_CONCURRENCY)
lease        900                    (env ORBIT_LEASE)
[ok] broker reachable
```

## Moving these variables to 3.x

`orbit migrate-config orbit.ini` converts the **file** only. It does not read `ORBIT_*` variables from your shell. When you migrate, copy each variable's value into `orbit.toml` by hand, using the 3.x column in the table above. Alternatively, pass the broker URL from the environment in code with `Orbit(broker=os.environ[...])`. The complete checklist is in [Migrating from 2.x to 3.x](migrating-2-to-3.md).
