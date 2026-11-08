---
id: flows-error-handling
title: Error handling in flows
section: Flows
applies_to: "3.x"
updated: 2026-10-23
---

# Error handling in flows

Every flow step is an ordinary Orbit job, so it fails, retries and dead-letters in the same way as any other job. This page covers what changes when that job is part of a [flow](flows-overview.md): what happens to the rest of the graph, and how to resume a run that failed.

## What happens when a step fails

1. The step raises an exception. Orbit records the attempt and retries it according to the step's retry policy, which is the job's `retries`/`backoff` or the `step(..., retries=)` override. Retry delays work as described in [Retries and backoff](retries-and-backoff.md).
2. If every attempt fails, Orbit logs **`ORB-1301 RetryExhausted`**. The step's job moves to the [dead-letter queue](dead-letter-queue.md), and the step is marked `failed`.
3. Every step that depends on the failed step, directly or through other steps, is marked `skipped`.
4. **Branches that do not depend on the failed step keep running** to completion.
5. When nothing is left to run, the run is marked `failed`.

Point 4 surprises people. Take this graph:

```python
flow = Flow("fulfil-order", steps=[
    step(reserve_stock),
    step(charge_card,  after="reserve_stock"),
    step(print_label,  after="charge_card"),
    step(send_receipt, after="charge_card"),
    step(close_order,  after=["print_label", "send_receipt"]),
])
```

If `print_label` fails, `send_receipt` still runs, because it does not depend on `print_label`, and `close_order` is skipped. If that is not what you want, make `send_receipt` wait for `print_label`.

## Step timeouts

A step that runs longer than its timeout is stopped and fails that attempt with **`ORB-1502 StepTimeout`**. A timeout counts as a failed attempt, so it is retried like any other failure. A step that times out every time ends in `ORB-1301` and the DLQ, just like a step that raises.

```python
step(export_report, after="collect_rows", timeout="10m", retries=2)
```

> **Note:** The step `timeout` and the worker [lease](leases-and-heartbeats.md) are two separate things. If a step runs longer than `[worker] lease_seconds` and heartbeats cannot renew its lease, the broker may hand the same step to a second worker while the first is still running it (`ORB-1101 LeaseExpired`). The step then runs **twice**. This is expected behaviour and not specific to flows; see [Troubleshooting duplicates](troubleshooting-duplicates.md). Make every step [idempotent](idempotency.md).

## Resuming a failed run

You do not need to start a new run from scratch. A failed step's job is in the DLQ, and **replaying it resumes the original run**:

```bash
$ orbit dlq list
JOB ID     JOB            FLOW RUN       ERROR     FAILED AT
j_5f2b14   print_label    fr_01JB7Q9ZC3  ORB-1301  2026-10-21T08:19:40Z

$ orbit dlq replay j_5f2b14
replayed j_5f2b14 -> j_5f31e0 (flow run fr_01JB7Q9ZC3 resumed)
```

The replay does the following:

- It sets the run back to `running` and the step to `queued`, with its attempt counter reset to zero.
- If the step now succeeds, every step that was `skipped` because of it goes back to `pending` and is enqueued when its dependencies are met.
- It **does not** re-run steps that have already succeeded. Their stored results are passed in again as usual.

You can only replay while the run record still exists, that is, within `[results] ttl_days` of the run finishing. After that, `orbit dlq replay` re-enqueues the job as a standalone job with no flow, and prints a warning. For that reason, fix the bug and deploy *before* you replay. If the cause is still there, the replay just fails again and goes back to the DLQ.

`orbit dlq purge` deletes DLQ entries without replaying them. Purging a step's entry leaves its run permanently `failed`.

## Errors that cannot be retried

Some flow errors are not about a single attempt, and retrying will not help:

| Code | When | What to do |
|---|---|---|
| `ORB-1501 FlowCycleDetected` | When the flow is defined (import time) | Fix the `after=` graph. Workers refuse to load the module until you do |
| `ORB-1503 FlowStateCorrupt` | The run record is missing or cannot be decoded | Start a new run. See below |
| `ORB-1601 ResultBackendUnavailable` | Run state cannot be read or written | Restore the backend. Steps are retried once it is back |
| `ORB-1202 PayloadTooLarge` | A step's result is over `max_payload_kb` | Return a reference instead; see [Steps and state](flows-steps-and-state.md) |
| `ORB-1201 SerializationError` | A step's result is not JSON-serializable | Convert the value before returning it |

`ORB-1202` and `ORB-1201` are retried like other failures, but the same code returns the same value, so expect them to end in the DLQ.

### Recovering from ORB-1503

A corrupt run record cannot be repaired from the CLI. The safe recovery is:

1. Find the inputs. The dashboard shows them as long as any part of the record can be read. Otherwise, get them from your own logs.
2. Purge the run's DLQ entries so that nobody replays them into a broken run.
3. Start a fresh run with `flow.run(...)`. Steps that already took effect, such as a charge, must use an [idempotency key](idempotency.md) so that the new run does not repeat their side effects.

To prevent `ORB-1503` (Redis eviction, manual edits, mixed versions), see [Steps and state](flows-steps-and-state.md#protecting-run-state).

## Designing steps that fail well

- **Keep steps small.** If one step charges a card and then sends an email, an email failure retries the charge. Split them.
- **Alert on the DLQ, not on single failures.** See `orbit.dlq.depth` in [Metrics](observability-metrics.md).

## See also

- [Error codes](error-codes.md): the full list of `ORB-` codes
- [Dead-letter queue](dead-letter-queue.md)
- [Tracing](observability-tracing.md): following one run across workers
