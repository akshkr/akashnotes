---
id: flows-steps-and-state
title: Flow steps and state
section: Flows
applies_to: "3.x"
updated: 2026-10-21
---

# Flow steps and state

This page covers how steps are declared, how data moves between them, and where Orbit stores a flow run's state. For the basics, read [Flows overview](flows-overview.md) first.

## Declaring steps

`step()` wraps a job and says where it sits in the graph:

```python
step(fn, after=None, name=None, timeout=None, retries=None)
```

| Argument | Type | Default | Meaning |
|---|---|---|---|
| `fn` | job | required | A function decorated with `@app.job` |
| `after` | `str` or `list[str]` | `None` | Names of the steps that must succeed first |
| `name` | `str` | `fn.__name__` | Step name. Must be unique within the flow |
| `timeout` | duration | job's `timeout` | Overrides the job timeout for this step only |
| `retries` | `int` | job's `retries` | Overrides the job's retry count for this step only |

A step whose `after` lists more than one step waits until **all** of them have succeeded (fan-in). If several steps share the same `after`, they are enqueued together and run in parallel on whichever workers are free (fan-out):

```python
flow = Flow("fulfil-order", steps=[
    step(reserve_stock),
    step(charge_card,    after="reserve_stock"),
    step(print_label,    after="charge_card"),
    step(send_receipt,   after="charge_card"),
    step(close_order,    after=["print_label", "send_receipt"]),
])
```

## Passing data between steps

Orbit passes two kinds of values to a step function:

1. **Run inputs.** These are the keyword arguments given to `flow.run(...)`. A step receives an input only if its function has a parameter with that name.
2. **Upstream results.** If a step function has a parameter **with the same name as an upstream step**, Orbit passes that step's return value into it.

```python
@app.job()
def charge_card(order_id: str, reserve_stock: dict) -> dict:
    # reserve_stock is the value returned by the reserve_stock step
    return {"charge_id": "ch_7781", "amount_cents": reserve_stock["total_cents"]}

@app.job()
def send_receipt(order_id: str, charge_card: dict) -> None:
    ...

run = fulfil_order.run(order_id="A-1001")
```

If the parameter name matches neither a run input nor an upstream step, the parameter's default value is used. If it has no default, the step fails on its first attempt with `TypeError`. A renamed step (`name="..."`) is passed in under its **new** name.

> **Note:** You can only inject results from steps listed in your own `after` chain. Orbit will not inject a sibling's result, because the sibling may not have finished yet.

## What a step may return

Step results are stored in the [result backend](results-backend.md) and passed on to later steps, so the rules for job arguments apply to them too:

- Results must be JSON-serializable. Returning a `datetime`, a `set` or an ORM object fails the step with **`ORB-1201 SerializationError`**. Convert these values first: ISO-8601 strings for times, lists for sets, IDs for objects.
- Results must fit within `[limits] max_payload_kb` (512 KB by default). A bigger result fails the step with **`ORB-1202 PayloadTooLarge`**, *after* the work itself has finished. This catches people out with steps that return query results or rendered documents.

When a result is large, store it somewhere else and return a reference:

```python
@app.job(timeout="5m")
def export_report(account_id: str) -> dict:
    data = build_report(account_id)              # may be several MB
    key = f"reports/{account_id}/2026-10.json"
    blob_store.put(key, data)
    return {"report_key": key, "rows": len(data)}
```

You can raise `max_payload_kb` in [`orbit.toml`](configuration-reference.md). The same limit applies to all job payloads, and big payloads slow down every broker round trip, so returning a reference is almost always the better choice.

## Where run state lives

Each run has one **run record** in the result backend. It holds:

| Field | Contents |
|---|---|
| `run_id` | e.g. `fr_01JB7Q9ZC3` |
| `flow` | Flow name, e.g. `fulfil-order` |
| `inputs` | The keyword arguments passed to `flow.run()` |
| `steps.<name>.state` | `pending`, `queued`, `running`, `succeeded`, `failed` or `skipped` |
| `steps.<name>.attempts` | Number of attempts so far |
| `steps.<name>.job_id` | The job ID of the step's latest attempt |
| `steps.<name>.result` | The return value, once the step has succeeded |
| `started_at` / `finished_at` | UTC timestamps |

The record is kept for `[results] ttl_days` (7 by default), counted from the moment the run **finishes**. Runs that are still in progress never expire. Once the record is gone, `orbit flows status <run_id>` reports `unknown run`.

### Protecting run state

If a run record is missing or cannot be decoded while the run is still in progress, the next step that touches it fails with **`ORB-1503 FlowStateCorrupt`**. In practice this happens for three reasons:

- **Redis eviction.** The result backend's Redis uses an eviction policy such as `allkeys-lru` and drops run records under memory pressure. Use `maxmemory-policy noeviction` on any Redis that holds results.
- **Manual edits.** Someone ran `DEL` or `UPDATE` on keys or rows while debugging.
- **Mixed versions while upgrading.** Workers from different 3.x minor versions wrote the same record. Keep all workers on one version per flow; `orbit doctor` warns when it sees mixed versions.

How to recover from `ORB-1503` is covered in [Error handling in flows](flows-error-handling.md).

## Checking a run

```text
$ orbit flows status fr_01JB7Q9ZC3
flow: fulfil-order   state: running   started: 2026-10-21T08:14:02Z

STEP            STATE      ATTEMPTS  JOB ID
reserve_stock   succeeded  1         j_5f2a0c
charge_card     succeeded  2         j_5f2a91
print_label     running    1         j_5f2b14
send_receipt    succeeded  1         j_5f2b15
close_order     pending    0         -
```

## See also

- [Error handling in flows](flows-error-handling.md)
- [Idempotency](idempotency.md): why every step should be safe to run twice
- [Flow API reference](api-reference-flow.md)
