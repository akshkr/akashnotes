---
id: observability-metrics
title: Metrics
section: Observability
applies_to: "3.x"
updated: 2026-10-22
---

# Metrics

Orbit workers, producers and the dashboard export metrics with **OpenTelemetry over OTLP**. You send them to an OpenTelemetry Collector or straight to any backend that accepts OTLP. Tracing uses the same settings; see [Tracing](observability-tracing.md).

## Enabling export

```toml
[telemetry]
otlp_endpoint = "http://otel-collector:4317"
service_name = "billing-workers"
```

- If `otlp_endpoint` is not set, export is **off**. That is the default.
- Orbit exports over **OTLP/gRPC**. Point it at the collector's gRPC port, which is usually `4317`. The HTTP port `4318` will not work.
- `service_name` becomes the `service.name` resource attribute. Use a different name for each deployment, for example `billing-workers` and `billing-dashboard`.
- The export interval follows the standard `OTEL_METRIC_EXPORT_INTERVAL` variable (in milliseconds, default 60000). This is an OpenTelemetry SDK setting, not an Orbit one.

> **Note:** Orbit does **not** serve a Prometheus `/metrics` endpoint. To use Prometheus, run an OpenTelemetry Collector with a `prometheus` exporter (example below), and have Prometheus scrape the collector.

## Metric catalogue

All metrics carry `orbit.version` and `service.name`. The attributes listed below are added on top of those.

| Metric | Type | Unit | Attributes | Description |
|---|---|---|---|---|
| `orbit.jobs.enqueued` | counter | `{job}` | `queue`, `job`, `priority` | Jobs enqueued (counted on the producer side) |
| `orbit.jobs.started` | counter | `{job}` | `queue`, `job` | Attempts started |
| `orbit.jobs.completed` | counter | `{job}` | `queue`, `job`, `outcome` | Finished attempts. `outcome` is `succeeded`, `failed` or `retried` |
| `orbit.job.duration` | histogram | `s` | `queue`, `job`, `outcome` | Time spent running one attempt |
| `orbit.job.queue_wait` | histogram | `s` | `queue`, `priority` | Time from when a job was due to when it started |
| `orbit.queue.depth` | gauge | `{job}` | `queue`, `priority` | Jobs ready to run, not counting delayed jobs |
| `orbit.queue.delayed` | gauge | `{job}` | `queue` | Jobs waiting for a delay or a retry backoff |
| `orbit.dlq.depth` | gauge | `{job}` | `queue` | Entries in the dead-letter queue |
| `orbit.worker.busy` | gauge | `{slot}` | `worker` | Concurrency slots in use |
| `orbit.worker.prefetched` | gauge | `{job}` | `worker` | Jobs reserved but not started |
| `orbit.lease.expired` | counter | `{job}` | `queue`, `job` | Leases that expired while the job ran (`ORB-1101`) |
| `orbit.worker.heartbeat.missed` | counter | `{event}` | `worker` | Heartbeats that missed their deadline (`ORB-1102`) |
| `orbit.broker.throttled` | counter | `{request}` | `broker` | Broker requests that were throttled (`ORB-1901`, SQS) |
| `orbit.flow.runs` | counter | `{run}` | `flow`, `outcome` | Flow runs finished |
| `orbit.errors` | counter | `{error}` | `error_code` | Every `ORB-` error that was logged, by code |

### Aggregating gauges correctly

Each worker reports `orbit.queue.depth`, `orbit.queue.delayed` and `orbit.dlq.depth` **for every queue it consumes**. So with 6 workers on `default`, there are 6 copies of the same depth value. Aggregate these gauges with `max`, never `sum`:

```promql
max by (queue) (orbit_queue_depth)
```

Use `sum` for the per-worker gauges (`orbit.worker.busy`, `orbit.worker.prefetched`) and for all counters.

## Prometheus through the Collector

```yaml
# otel-collector.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
exporters:
  prometheus:
    endpoint: 0.0.0.0:9464
service:
  pipelines:
    metrics:
      receivers: [otlp]
      exporters: [prometheus]
```

The Prometheus exporter turns dots into underscores and adds unit and `_total` suffixes. For example, `orbit.jobs.completed` becomes `orbit_jobs_completed_total` and `orbit.job.duration` becomes `orbit_job_duration_seconds`.

## Suggested alerts

| Alert | Expression (Prometheus) | Why |
|---|---|---|
| DLQ growing | `increase(max by (queue) (orbit_dlq_depth)[30m]) > 0` | Jobs are running out of retries (`ORB-1301`) |
| Leases expiring | `sum(rate(orbit_lease_expired_total[10m])) > 0` | Long jobs are running twice; see [Leases and heartbeats](leases-and-heartbeats.md) |
| Heartbeats missed | `sum by (worker) (rate(orbit_worker_heartbeat_missed_total[5m])) > 0` | The worker is overloaded or blocked, or its network is unstable |
| Queue wait high | `histogram_quantile(0.95, sum by (le, queue) (rate(orbit_job_queue_wait_seconds_bucket[10m]))) > 60` | Not enough workers; see [Scaling workers](scaling-workers.md) |
| SQS throttling | `sum(rate(orbit_broker_throttled_total[5m])) > 1` | See [SQS broker](broker-sqs.md) |
| Worker memory | container memory near limit, plus `orbit_errors_total{error_code="ORB-2101"}` | See [Troubleshooting memory](troubleshooting-memory.md) |

`orbit.worker.prefetched` is worth graphing on 3.2.x. If it stays near your `prefetch` value while memory rises, you may be hitting the open memory-growth issue with `prefetch` above 100.

## Cardinality

The `job` attribute takes the job function's qualified name, such as `billing.jobs.send_receipt`, and `queue` takes the queue name. Neither includes job IDs or arguments, so cardinality stays bounded as long as you don't create queue names on the fly (one queue per customer, for example).

## See also

- [Tracing](observability-tracing.md)
- [Performance tuning](performance-tuning.md)
- [Configuration reference: `[telemetry]`](configuration-reference.md#telemetry)
