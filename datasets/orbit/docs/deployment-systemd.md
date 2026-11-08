---
id: deployment-systemd
title: Running workers with systemd
section: Deployment
applies_to: "3.x"
updated: 2026-11-05
---

# Running workers with systemd

If you deploy to plain Linux VMs rather than containers, systemd is the simplest way to keep
Orbit workers running, restart them when they crash, and shut them down without losing work.
This page shows a production-ready unit file, how to run several queue sets on one host, and
how shutdown interacts with leases.

Running in containers instead? See [deployment-docker.md](deployment-docker.md) or
[deployment-kubernetes.md](deployment-kubernetes.md).

> **Note:** This page describes Orbit 3.x, where configuration lives in `orbit.toml`. On 2.9 the
> unit file is almost identical, but settings come from `ORBIT_*` variables in an
> `EnvironmentFile=` instead. See [environment-variables-2x.md](environment-variables-2x.md).

## Recommended layout

| Path | Purpose |
|---|---|
| `/srv/atlas-jobs/` | Your application code (the module that creates `app = Orbit(...)`) |
| `/srv/atlas-jobs/.venv/` | Virtualenv with Orbit and your dependencies |
| `/srv/atlas-jobs/orbit.toml` | Worker configuration, readable only by the `orbit` user |
| `/etc/systemd/system/orbit-worker@.service` | Template unit, one instance per queue set |

The worker reads `orbit.toml` from its working directory, so `WorkingDirectory=` must point at
the directory that holds it.

```toml
# /srv/atlas-jobs/orbit.toml
[broker]
url = "redis://redis.internal.example.com:6379/0"

[worker]
concurrency = 8
prefetch = 10
lease_seconds = 300
heartbeat_seconds = 30
```

Create a dedicated system user and lock the config file down:

```bash
sudo useradd --system --home /srv/atlas-jobs --shell /usr/sbin/nologin orbit
sudo chown -R orbit:orbit /srv/atlas-jobs
sudo chmod 600 /srv/atlas-jobs/orbit.toml
```

## The template unit

```ini
# /etc/systemd/system/orbit-worker@.service
[Unit]
Description=Orbit worker (queues: %i)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=orbit
Group=orbit
WorkingDirectory=/srv/atlas-jobs
ExecStartPre=/srv/atlas-jobs/.venv/bin/orbit doctor
ExecStart=/srv/atlas-jobs/.venv/bin/orbit worker --queues %i --concurrency 8
Restart=on-failure
RestartSec=5
KillSignal=SIGTERM
TimeoutStopSec=330
MemoryMax=2G
LimitNOFILE=65536

# Hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=/srv/atlas-jobs/var

[Install]
WantedBy=multi-user.target
```

Running `orbit doctor` in `ExecStartPre=` makes a bad deploy fail fast and visibly: an
unreachable broker (ORB-1001) or a typo in `orbit.toml` (ORB-1802) stops the unit from starting
instead of producing a worker that crash-loops. See [error-codes.md](error-codes.md).

## Starting instances

The instance name after `@` becomes `%i`, which is passed to `--queues`. One instance per queue
is the easiest to reason about:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now orbit-worker@default.service
sudo systemctl enable --now orbit-worker@high.service
```

To have a single worker consume several queues, note that commas are not valid in unit names.
Escape the instance name, and systemd unescapes it again for `%i`:

```bash
sudo systemctl enable --now "orbit-worker@$(systemd-escape 'default,high').service"
```

How many instances and what `--concurrency` to use is covered in
[scaling-workers.md](scaling-workers.md).

## Graceful shutdown and `TimeoutStopSec`

When systemd sends `SIGTERM`, the worker stops taking new jobs from the broker, hands its
prefetched (not yet started) jobs back, and waits for running jobs to finish. If they are still
running when `TimeoutStopSec` runs out, systemd sends `SIGKILL`.

A job killed that way is not lost. The broker makes it visible again once its lease expires, and
another worker runs it **again from the start**. That is the most common source of duplicate
side effects after a deploy. See [troubleshooting-duplicates.md](troubleshooting-duplicates.md).

Rule of thumb: set `TimeoutStopSec` to at least your longest job `timeout` plus
`heartbeat_seconds`, the same rule as Kubernetes' `terminationGracePeriodSeconds`. For jobs
capped at `timeout="5m"` with the default 30-second heartbeat that gives 330, as above. If some
jobs run longer than any stop timeout you can accept, make them idempotent and check that
heartbeats keep their leases alive ([leases-and-heartbeats.md](leases-and-heartbeats.md)).

> **Note:** `MemoryMax=` is a hard cgroup limit. A worker that reaches it logs `WorkerOOM`
> (ORB-2101), then the kernel kills it and systemd restarts the unit. On 3.2.x, check
> `prefetch` first. See [troubleshooting-memory.md](troubleshooting-memory.md).

## Rolling restarts

Restart instances one at a time so the queue never loses all of its consumers:

```bash
for unit in $(systemctl list-units 'orbit-worker@*' --plain --no-legend | awk '{print $1}'); do
  sudo systemctl restart "$unit"
  sleep 10
done
```

## Logs

Workers log to stdout and stderr, which journald collects:

```bash
journalctl -u 'orbit-worker@*' -f
journalctl -u orbit-worker@high.service --since "1 hour ago" | grep ORB-
```

For metrics and traces, configure `[telemetry]` as described in
[observability-metrics.md](observability-metrics.md).

## The dashboard

Run the dashboard as a separate, non-template unit. Bind it behind a TLS-terminating reverse
proxy and never expose it without authentication ([security.md](security.md)):

```ini
# /etc/systemd/system/orbit-dashboard.service (excerpt)
[Service]
User=orbit
WorkingDirectory=/srv/atlas-jobs
ExecStart=/srv/atlas-jobs/.venv/bin/orbit dashboard --port 7777
Restart=on-failure
```
