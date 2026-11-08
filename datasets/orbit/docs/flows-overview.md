---
id: flows-overview
title: Flows overview
section: Flows
applies_to: "3.x"
updated: 2026-10-21
---

# Flows overview

A **Flow** is a set of [jobs](concepts-jobs.md) that run in a fixed order. You give the order as a directed acyclic graph (DAG) of **Steps**. Each step wraps an ordinary Orbit job and runs only after the steps it depends on have succeeded. Flows arrived in **3.0.0**, along with `orbit.toml`. They do not exist in 2.x.

Use a flow when the order of work matters and you want one place to see a whole multi-step process: onboarding, order fulfilment, nightly ETL. Use a plain job when the work is a single unit, even if it is large.

## A minimal flow

```python
from orbit import Orbit, Flow, step

app = Orbit(broker="redis://localhost:6379/0")

@app.job(timeout="30s")
def create_account(user_id: str) -> dict:
    return {"account_id": "acc_901"}

@app.job(retries=5, backoff="exponential")
def send_welcome(user_id: str, create_account: dict) -> None:
    ...

flow = Flow("onboarding", steps=[
    step(create_account),
    step(send_welcome, after="create_account"),
])

run = flow.run(user_id="u_42")
print(run.id)   # e.g. "fr_01JB7Q4M2K"
```

`flow.run(...)` returns as soon as the run is recorded and its first steps are enqueued. It does not wait for the flow to finish. Step functions must be jobs, which means functions decorated with `@app.job`. If you pass a plain function to `step()`, you get a `TypeError` when the flow is defined. Each step takes its broker, retry policy and timeout from its job. You can override these per step; see [Steps and state](flows-steps-and-state.md).

## How a run executes

There is no separate flow coordinator process. Your [workers](concepts-workers.md) do the coordination:

1. `flow.run()` writes a run record to the [result backend](results-backend.md) and enqueues every root step (a step with no `after`).
2. When a worker finishes a step, it updates the run record. It then enqueues every step whose `after` dependencies have all succeeded.
3. When no steps are left to run, the run is marked `succeeded` or `failed`.

Each step is a normal job. It shows up in queue metrics, follows its retry policy, and can end up in the [dead-letter queue](dead-letter-queue.md). Because run state lives in the result backend, **flows need a result backend.** See [Result backend](results-backend.md) for which brokers support one.

## Run and step states

| Run state | Meaning |
|---|---|
| `pending` | Run recorded, no step picked up yet |
| `running` | At least one step is queued or running |
| `succeeded` | Every step succeeded |
| `failed` | At least one step failed for good; see [Error handling](flows-error-handling.md) |

Steps add two more states. `queued` means the step's job is on the broker. `skipped` means an upstream step failed, so the step will never run.

## Validation when the flow is defined

When you construct a `Flow`, Orbit checks the graph straight away, at import time:

- A dependency cycle (`a` after `b`, and `b` after `a`) raises **`ORB-1501 FlowCycleDetected`**. The message names the steps in the cycle.
- An `after=` that names a step not in the flow raises `ValueError`.
- Two steps with the same name raise `ValueError`. Use `step(fn, name="...")` to include the same job twice.

Since these checks run at import time, a broken flow stops the worker from starting. It cannot fail halfway through a production run.

> **Note:** `ORB-1501` is raised only when the flow is defined. A run never hits it. If a long-running worker logs it, someone deployed code with a cycle, and the worker refused to load it.

## Starting and watching runs from the CLI

```bash
$ orbit flows run onboarding
started run fr_01JB7Q9ZC3 (flow=onboarding, steps=2)

$ orbit flows status fr_01JB7Q9ZC3
```

`orbit flows run <name>` starts a run **with no inputs**. Each step then gets only the default values of its parameters. That is useful for flows like `nightly-rollup`, which need no arguments. If a flow needs inputs such as `user_id`, start it from Python with `flow.run(...)`. For all subcommands and their output, see the [CLI reference](cli-reference.md). The [dashboard](dashboard.md) shows the same information as a graph.

## Flows compared with chaining jobs yourself

| | Chaining jobs by hand (`a` enqueues `b`) | Flow |
|---|---|---|
| Order is visible in one place | No, it is spread across job bodies | Yes, the `steps=[...]` list |
| Fan-out and fan-in | Manual bookkeeping | `after=["a", "b"]` |
| Status of the whole process | Build it yourself | `orbit flows status`, dashboard |
| Resume after a failure | Re-enqueue by hand | Replay the failed step from the DLQ |
| Extra storage | None | One run record per run in the result backend |

## Next steps

- [Steps and state](flows-steps-and-state.md): passing data between steps, size limits, where state is stored
- [Error handling in flows](flows-error-handling.md): retries, timeouts, skipped branches and resuming
- [Flow API reference](api-reference-flow.md)
