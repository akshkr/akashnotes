---
id: deployment-kubernetes
title: Deploying on Kubernetes
section: Deployment
applies_to: "3.x"
updated: 2026-10-30
---

# Deploying on Kubernetes

This page shows a production-style layout: a worker `Deployment`, a single-replica dashboard behind an Ingress, and `orbit.toml` delivered as a `Secret`. Build the image as described in [Docker deployment](deployment-docker.md). Kubernetes runs it unchanged.

## Configuration as a Secret

The broker URL usually contains a password, so store the whole `orbit.toml` in a `Secret` and mount it into the working directory:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: orbit-config
stringData:
  orbit.toml: |
    [broker]
    url = "redis://:CHANGE_ME@redis-master.data.svc:6379/0"

    [worker]
    prefetch = 20
    lease_seconds = 600
    heartbeat_seconds = 30

    [results]
    backend = "redis"
    ttl_days = 7

    [telemetry]
    otlp_endpoint = "http://otel-collector.observability.svc:4317"
    service_name = "shop-workers"
```

> **Note:** A file mounted with `subPath` is **not** updated when the Secret changes. After you edit the config, run `kubectl rollout restart deployment/orbit-worker`. Orbit reads `orbit.toml` only when it starts.

## Workers

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orbit-worker
spec:
  replicas: 3
  selector: { matchLabels: { app: orbit-worker } }
  template:
    metadata: { labels: { app: orbit-worker } }
    spec:
      terminationGracePeriodSeconds: 330
      containers:
        - name: worker
          image: registry.example.com/shop:2026.10.3
          command: ["orbit", "worker", "--queues", "default,high", "--concurrency", "8"]
          workingDir: /app
          resources:
            requests: { cpu: "500m", memory: "512Mi" }
            limits:   { memory: "1Gi" }
          readinessProbe:
            exec: { command: ["orbit", "doctor"] }
            periodSeconds: 60
            timeoutSeconds: 10
          volumeMounts:
            - name: config
              mountPath: /app/orbit.toml
              subPath: orbit.toml
      volumes:
        - name: config
          secret: { secretName: orbit-config }
```

### Choosing `terminationGracePeriodSeconds`

When a pod is deleted, the worker gets `SIGTERM` and starts its graceful shutdown (see [CLI reference](cli-reference.md#orbit-worker)). Kubernetes sends `SIGKILL` once the grace period runs out. Use this rule:

```
terminationGracePeriodSeconds ≥ longest job timeout + heartbeat_seconds
```

In the example above, the longest job has `timeout="5m"`: 300 + 30 = 330. If a job is killed anyway, it is not lost. It runs again on another pod once its lease expires (`lease_seconds`, 600 here). Every rollout and node drain can trigger this, so jobs must be [idempotent](idempotency.md). See [Leases and heartbeats](leases-and-heartbeats.md).

### Probes: readiness yes, liveness no

`orbit doctor` makes a good **readiness** probe. Do **not** use it as a **liveness** probe. During a broker outage every pod would fail liveness at the same moment, and Kubernetes would restart the whole fleet. When Redis returned, every worker would then reconnect at once. On 3.1.0 that pattern caused a reconnect storm after Redis failover, which was fixed in 3.1.2. Even on current versions, mass restarts throw away in-flight work for no reason. If you need a liveness probe, use a plain process check.

If you run Redis with Sentinel or an operator that fails over automatically, run **3.1.2 or later**.

### Disruption budget

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: orbit-worker
spec:
  maxUnavailable: 1
  selector: { matchLabels: { app: orbit-worker } }
```

## Resources and memory

- Set a memory **limit**. A worker that reaches it logs `ORB-2101 WorkerOOM` before it is OOM-killed, and the pod restart shows `OOMKilled`.
- Keep `prefetch` at 100 or below on 3.2.x. Above that there is an open memory-growth issue. In the example above, 20 is plenty for 8 concurrency slots.
- CPU limits often throttle workers in ways that are hard to see. Prefer CPU requests without limits. See [Performance tuning](performance-tuning.md).

## Autoscaling

Scale workers on **queue depth or queue wait**, not CPU. Many Orbit jobs spend their time waiting on I/O. Export metrics through the Collector ([Metrics](observability-metrics.md)), then use KEDA or the Prometheus adapter with a query like:

```promql
max by (queue) (orbit_queue_depth{queue="default"})
```

Use `max`, not `sum`, because every worker reports the same depth value. Choosing targets and per-queue worker pools is covered in [Scaling workers](scaling-workers.md).

## Dashboard

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orbit-dashboard
spec:
  replicas: 1
  selector: { matchLabels: { app: orbit-dashboard } }
  template:
    metadata: { labels: { app: orbit-dashboard } }
    spec:
      containers:
        - name: dashboard
          image: registry.example.com/shop:2026.10.3
          command: ["orbit", "dashboard", "--port", "7777"]
          workingDir: /app
          ports: [{ containerPort: 7777 }]
          volumeMounts:
            - { name: config, mountPath: /app/orbit.toml, subPath: orbit.toml }
      volumes:
        - name: config
          secret: { secretName: orbit-dashboard-config }
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: orbit-dashboard
spec:
  ingressClassName: nginx
  tls: [{ hosts: [orbit.example.com], secretName: orbit-dashboard-tls }]
  rules:
    - host: orbit.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend: { service: { name: orbit-dashboard, port: { number: 7777 } } }
```

- Keep `replicas: 1` in token mode, because each replica generates its own token. For more than one replica, use [OIDC](dashboard-auth-oidc.md), which stores sessions in the broker.
- ingress-nginx sends `X-Forwarded-Proto`. If a cloud load balancer terminates TLS *in front of* the ingress, set `use-forwarded-headers: "true"` in the controller ConfigMap. Otherwise OIDC sign-in loops (a known 3.2.0 issue).
- Give the dashboard its own Secret (`orbit-dashboard-config`) with a `[dashboard]` section and a separate `service_name`.

## Checklist

| Item | Why |
|---|---|
| `terminationGracePeriodSeconds` ≥ longest timeout + heartbeat | Avoid duplicate runs on every rollout |
| `orbit doctor` as readiness only | Avoid restarting the whole fleet during a broker outage |
| Orbit ≥ 3.1.2 with Redis failover | Reconnect storm fix |
| `prefetch` ≤ 100 on 3.2.x | Open memory-growth issue |
| Memory limit set | Bounded `ORB-2101` failures instead of node pressure |
| One dashboard replica, or OIDC | Token is generated per process |

See also: [Docker deployment](deployment-docker.md), [systemd deployment](deployment-systemd.md), [Security](security.md).
