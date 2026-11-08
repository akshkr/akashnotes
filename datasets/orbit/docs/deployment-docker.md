---
id: deployment-docker
title: Deploying with Docker
section: Deployment
applies_to: "3.x"
updated: 2026-10-29
---

# Deploying with Docker

This guide runs Orbit workers and the dashboard in containers with Docker Compose, using Redis as the [broker](broker-redis.md). The same image works on any container platform. For Kubernetes manifests, see [Kubernetes deployment](deployment-kubernetes.md).

## The image

Orbit has no official image. Build one from your application code, since workers need your job modules to be importable.

```dockerfile
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends gettext-base \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt      # pins orbit==3.2.1

COPY . .
RUN useradd --uid 10001 orbit && chown -R orbit /app
USER orbit

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["orbit", "worker", "--queues", "default,high", "--concurrency", "8"]
```

Stay on Python 3.12. Python 3.13 is not supported yet (see [FAQ](faq.md)).

## Getting secrets into `orbit.toml`

Orbit 3.x reads its settings **only** from `orbit.toml` and constructor arguments. It does not read `ORBIT_*` environment variables, and it **does not expand `${VAR}` placeholders** inside `orbit.toml`. To keep the broker password out of the image, render the file when the container starts:

```toml
# orbit.toml.tmpl (committed to the repo)
[broker]
url = "${REDIS_URL}"

[worker]
lease_seconds = 300
heartbeat_seconds = 30

[results]
backend = "redis"

[telemetry]
otlp_endpoint = "http://otel-collector:4317"
service_name = "${SERVICE_NAME}"
```

```sh
#!/bin/sh
# docker-entrypoint.sh
set -eu
envsubst < /app/orbit.toml.tmpl > /app/orbit.toml
exec "$@"
```

The `exec` matters. It makes `orbit` PID 1, so it receives `SIGTERM` directly instead of through a shell that would swallow it.

The other option is to pass the URL in code, `Orbit(broker=os.environ["REDIS_URL"])`, and leave `[broker]` out of the file.

## Compose file

```yaml
services:
  redis:
    image: redis:7
    command: ["redis-server", "--appendonly", "yes", "--maxmemory-policy", "noeviction"]
    volumes: ["redis-data:/data"]

  worker:
    build: .
    environment:
      REDIS_URL: "redis://redis:6379/0"
      SERVICE_NAME: "shop-workers"
    deploy:
      replicas: 3
      resources:
        limits: { memory: 1g }
    stop_grace_period: 2m
    healthcheck:
      test: ["CMD", "orbit", "doctor"]
      interval: 60s
      timeout: 10s
      retries: 3
    depends_on: [redis]

  dashboard:
    build: .
    command: ["orbit", "dashboard", "--port", "7777"]
    environment:
      REDIS_URL: "redis://redis:6379/0"
      SERVICE_NAME: "shop-dashboard"
    ports: ["7777:7777"]
    depends_on: [redis]

volumes:
  redis-data:
```

Notes on the Redis settings:

- `--maxmemory-policy noeviction` matters when Redis is also the [result backend](results-backend.md). An eviction policy can delete flow run records, which shows up as `ORB-1503 FlowStateCorrupt`.
- `--appendonly yes` keeps queued and delayed jobs across a Redis restart.

## Shutdown and `stop_grace_period`

> **Note:** Docker's default stop timeout is **10 seconds**. After that it sends `SIGKILL`. A worker that is killed in the middle of a job never acknowledges it, so the job runs again on another worker, but only after its **lease expires**, which is up to `lease_seconds` (300 s by default) later. To the user that looks like a job that ran twice and also stalled for five minutes.

Set `stop_grace_period` to at least your longest job `timeout` plus a few seconds. When the worker receives `SIGTERM`, it stops fetching jobs, hands prefetched jobs back to the broker, and waits for running jobs to finish (see [CLI reference](cli-reference.md#orbit-worker)). If some jobs run longer than any grace period you can accept, make them [idempotent](idempotency.md) and read [Troubleshooting duplicates](troubleshooting-duplicates.md).

## Health checks

`orbit doctor` exits with `1` if the config is invalid or the broker cannot be reached, so it works as a container health check. Keep the interval long (60 s), because each run opens a new broker connection. A failing health check only marks the container `unhealthy`. Compose does not restart it because of that.

## Memory

Set a memory limit on workers. A worker that reaches it logs `ORB-2101 WorkerOOM` before the kernel kills it. Usual causes are large payloads, jobs that load whole datasets into memory, and on 3.2.x, `prefetch` set above 100 (an open issue). See [Troubleshooting memory](troubleshooting-memory.md).

## Dashboard

The Compose file above publishes the dashboard on port 7777 in token mode. Get the sign-in URL from the logs:

```bash
docker compose logs dashboard | grep "sign in"
```

The token changes every time the container restarts. Run only **one** dashboard replica in token mode, or switch to [OIDC](dashboard-auth-oidc.md). If you put a TLS-terminating proxy in front of it, the proxy must send `X-Forwarded-Proto: https`.

## Docker Desktop on Windows

Docker Desktop runs Linux containers, so the open issue where native Windows workers ignore `SIGTERM` does not apply. Running workers in containers is the recommended way to develop on Windows.

## See also

- [Kubernetes deployment](deployment-kubernetes.md)
- [systemd deployment](deployment-systemd.md)
- [Scaling workers](scaling-workers.md)
