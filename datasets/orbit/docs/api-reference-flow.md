---
id: api-reference-flow
title: "API reference: Flow and step"
section: Reference
applies_to: "3.x"
updated: 2026-11-05
---

# API reference: `Flow` and `step`

Flows were introduced in Orbit 3.0.0. A **Flow** is a directed acyclic graph (DAG) of **Steps**,
and each step wraps a job. Orbit runs a step once all of the steps it depends on have succeeded,
and steps without dependencies on each other run in parallel. There's no 2.x equivalent. On 2.x,
people chained jobs by enqueueing the next job from inside the previous one.

For the concepts, read [flows-overview.md](flows-overview.md) first. This page lists signatures
and behaviour.

```python
from orbit import Orbit, Flow, step

app = Orbit(broker="redis://localhost:6379/0")

@app.job(retries=3, timeout="30s")
def create_account(user_id: str): ...

@app.job(retries=5, backoff="exponential", timeout="10s")
def send_welcome(user_id: str): ...

flow = Flow("onboarding", steps=[
    step(create_account),
    step(send_welcome, after="create_account"),
])

run = flow.run(user_id="u_42")
```

## `Flow(name, steps)`

| Parameter | Type | Description |
|---|---|---|
| `name` | `str` | Unique name within the app. It's used by `orbit flows run <name>` and in the dashboard. |
| `steps` | `list[step]` | The steps of the graph, in any order. |

The graph is validated **when the `Flow` is constructed**:

- If `after=` dependencies form a loop, construction raises `FlowCycleDetected` (ORB-1501). The
  message lists the cycle, for example `charge -> fulfil -> charge`.
- A dependency that names a step not in `steps` raises `ValueError`.
- Two flows with the same `name` in one app raise `ValueError` at registration.

Because validation happens at import time, a broken graph fails your test suite and your
deploy, not the first production run.

## `step(func, after=None, name=None, timeout=None, retries=None)`

| Parameter | Type | Description |
|---|---|---|
| `func` | job | A function decorated with `@app.job`. |
| `after` | `str`, `list[str]` or `None` | Name or names of the steps that must succeed first. |
| `name` | `str` or `None` | Step name, unique within the flow. Defaults to the function's name. |
| `timeout` | duration `str` or `None` | Overrides the job's `timeout` for this step only. |
| `retries` | `int` or `None` | Overrides the job's `retries` for this step only. |

```python
step(fulfil, after=["charge", "reserve_stock"])   # waits for both
```

Unless you override them on `step()`, each step inherits the job's own settings. `retries` and
`backoff` govern step retries, and `timeout` becomes the step timeout. A step that exceeds it
fails with `StepTimeout` (ORB-1502) and is retried under its retry policy. When its retries are
exhausted, the step fails and every step downstream of it is marked `skipped`. Independent
branches keep running, and the run ends as `failed` once nothing is left to run. Error-handling
patterns are on [flows-error-handling.md](flows-error-handling.md).

### Step results

A step's return value is stored in the result backend and made available to downstream steps.
Results must be JSON-serializable and are held to `[limits] max_payload_kb` (default 512 KB). A
step whose result is larger fails with `PayloadTooLarge` (ORB-1202) **after doing its work**.
That is painful for expensive steps, so write big outputs to object storage and return a key:

```python
@app.job(timeout="5m")
def render_report(user_id: str) -> dict:
    key = upload_pdf(build_pdf(user_id))   # e.g. "reports/u_42.pdf"
    return {"report_key": key}             # tiny result, well under 512 KB
```

How inputs and upstream results reach each step is described in
[flows-steps-and-state.md](flows-steps-and-state.md).

## `flow.run(**inputs)`

Starts a new run and returns a run handle immediately. It doesn't wait for the run to finish.

```python
run = flow.run(user_id="u_42")
print(run.id)        # e.g. "fr_01JB9W3E6Q"
```

- Inputs follow the same rules as job arguments: keyword-only and JSON-serializable
  (ORB-1201 otherwise).
- Each call creates an independent run. Use an `idempotency_key` on the first step's job if
  repeated calls must not repeat side effects ([idempotency.md](idempotency.md)).

The same thing from the command line:

```bash
orbit flows run onboarding
orbit flows status fr_01JB9W3E6Q
```

`orbit flows status` prints each step with its state (`pending`, `queued`, `running`,
`succeeded`, `failed`, `skipped`), its attempt count and the job ID of its latest attempt.

## Run state and the result backend

Run state lives in the result backend configured under `[results]`:

```toml
[results]
backend = "redis"
ttl_days = 7
```

Two failure modes come from this:

| Code | Cause |
|---|---|
| ORB-1601 `ResultBackendUnavailable` | The backend is unreachable. Runs can't advance until it's back. |
| ORB-1503 `FlowStateCorrupt` | The run record is missing or unreadable mid-run: Redis eviction, keys or rows deleted by hand, or workers on mixed 3.x versions. |

> **Note:** `ttl_days` is counted from when a run **finishes**, so a run that is still in
> progress never expires, however long it takes. Raise `ttl_days` only if you need to inspect or
> resume finished runs for longer than a week.

## Observability

With `[telemetry]` configured, each run is a trace and each step is a child span (since 3.1.0).
See [observability-tracing.md](observability-tracing.md).
