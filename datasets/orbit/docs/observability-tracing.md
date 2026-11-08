---
id: observability-tracing
title: Tracing
section: Observability
applies_to: "3.x"
updated: 2026-10-22
---

# Tracing

Orbit creates OpenTelemetry spans for enqueuing, running jobs and running [flows](flows-overview.md). It carries trace context through the broker, so the web request that enqueued a job and the worker that ran it end up in **the same trace**. Tracing uses the same `[telemetry]` settings as [metrics](observability-metrics.md):

```toml
[telemetry]
otlp_endpoint = "http://otel-collector:4317"
service_name = "checkout-api"
```

Give producers and workers different `service_name` values so the two halves of a trace are easy to tell apart.

## Spans Orbit creates

| Span name | Kind | Created by | When |
|---|---|---|---|
| `orbit.enqueue <job>` | PRODUCER | producer | Each `.enqueue()` call |
| `orbit.job <job>` | CONSUMER | worker | Each **attempt** of a job |
| `orbit.flow.run <flow>` | INTERNAL | producer | Each `flow.run()` call |
| `orbit.schedule <job>` | PRODUCER | scheduler | Each time a [cron schedule](scheduling-cron.md) fires |

Common span attributes:

| Attribute | Example |
|---|---|
| `orbit.job.id` | `j_5f2a0c` |
| `orbit.job.name` | `billing.jobs.send_receipt` |
| `orbit.queue` | `high` |
| `orbit.priority` | `high` |
| `orbit.attempt` | `2` |
| `orbit.flow.run_id` | `fr_01JB7Q9ZC3` |
| `orbit.flow.step` | `charge_card` |
| `orbit.error_code` | `ORB-1502` |

When an attempt fails, its span gets status `ERROR` and an `exception` event, and `orbit.error_code` is set if the failure has an `ORB-` code.

## How context crosses the broker

When you call `.enqueue()`, Orbit writes the current W3C `traceparent` (and `tracestate`, if present) into the job's headers. The headers are stored next to the arguments and **do not count towards `max_payload_kb`**. The worker reads them back and starts `orbit.job` as a child of `orbit.enqueue`.

A traced job therefore looks like this:

```text
POST /checkout                         checkout-api   182 ms
└─ orbit.enqueue send_receipt          checkout-api     2 ms
   ├─ orbit.job send_receipt  attempt=1   billing-workers  ERROR ORB-1001
   └─ orbit.job send_receipt  attempt=2   billing-workers  340 ms
      └─ POST https://mail.example.com/v1/send          290 ms
```

Retries are **sibling spans** under the same `orbit.enqueue` span, one for each attempt. The gap between them is the backoff delay. A [delayed job](scheduling-delays.md) shows up the same way: the gap between `orbit.enqueue` and `orbit.job` is the delay plus the time spent waiting in the queue.

## Flows

`flow.run()` opens an `orbit.flow.run` span. Every step's `orbit.job` span is a child of it, so the whole DAG appears as one trace, with parallel branches shown side by side.

> **Note:** A flow that runs for hours produces a trace that lasts for hours. Some tracing backends close traces after a fixed window, often 30 to 60 minutes, and show late spans as orphans. For long flows, search by `orbit.flow.run_id` instead of relying on the trace view.

## Sampling is decided at enqueue time

Orbit uses the OpenTelemetry SDK's parent-based sampling. The decision is made **where the trace starts**, usually in the producer, and the worker follows it. If your web app samples 10% of requests, then 10% of the jobs it enqueues are traced, whatever the worker's own settings are.

Configure sampling with the standard OpenTelemetry variables in the producer:

```bash
export OTEL_TRACES_SAMPLER=parentbased_traceidratio
export OTEL_TRACES_SAMPLER_ARG=0.1
```

Jobs that start with no parent context, such as cron-scheduled jobs and `orbit flows run` from the CLI, are sampled by the sampler configured on the **worker**.

## Using your own TracerProvider

If your process sets a global OpenTelemetry `TracerProvider` **before** it creates `Orbit(...)`, Orbit uses that provider and does **not** create its own exporter. In that case `otlp_endpoint` and `service_name` have no effect on traces, and spans go wherever your provider sends them. This is usually what you want in an app that is already instrumented. If Orbit spans seem to vanish, check the order in which the two are set up.

## Adding your own spans

Inside a job, the active span is `orbit.job`, so ordinary OpenTelemetry code nests under it automatically:

```python
from opentelemetry import trace
tracer = trace.get_tracer("billing")

@app.job(retries=3, timeout="30s")
def sync_invoices(account_id: str):
    with tracer.start_as_current_span("fetch-ledger") as span:
        span.set_attribute("account.id", account_id)
        rows = ledger.fetch(account_id)
    ...
```

## Correlating logs

Orbit's log records include `trace_id` and `span_id` when a span is active. Add them to your log formatter so that you can jump from a log line such as `ORB-1101 LeaseExpired job=j_5f2a0c` to the trace that shows both executions of the job.

## Troubleshooting

| Symptom | Check |
|---|---|
| No spans at all | `otlp_endpoint` is set and reachable on the gRPC port. A global provider may be overriding it |
| Producer and worker spans in separate traces | The producer runs 2.x, which writes no `traceparent` header, or a proxy job copies the arguments without the headers |
| Only some jobs traced | Expected: the producer's sampler decides |
| Spans from long flows show as orphans | The backend's trace window is shorter than the flow |

See also: [Metrics](observability-metrics.md) and [Troubleshooting duplicates](troubleshooting-duplicates.md).
