---
id: broker-sqs
title: Amazon SQS broker
section: Brokers
applies_to: all
updated: 2026-09-30
---

# Amazon SQS broker

The SQS broker runs Orbit on Amazon Simple Queue Service. You operate no queue servers.
In exchange you get a few constraints that the other brokers don't have. Read this page in
full before choosing SQS for production.

```bash
pip install "orbit[sqs]"
```

## Connection URL

```toml
# 3.x: orbit.toml
[broker]
url = "sqs://us-east-1/orbit-prod"
```

The URL has the form `sqs://<region>/<prefix>`. Each Orbit queue maps to an SQS queue named
`<prefix>-<queue>`, so the `default` queue becomes `orbit-prod-default`. Append `.fifo` to
the prefix (`sqs://us-east-1/orbit-prod.fifo`) to use FIFO queues instead of standard queues.
Orbit moves the suffix to the end of each queue name, as SQS requires, so `default` becomes
`orbit-prod-default.fifo`.

Credentials come from the standard AWS credential chain: environment, shared config file,
container role or instance profile. Never put access keys in the URL. 2.x reads the same URL
from `ORBIT_BROKER_URL`.

### IAM permissions

```json
{
  "Effect": "Allow",
  "Action": [
    "sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage",
    "sqs:ChangeMessageVisibility", "sqs:GetQueueUrl",
    "sqs:GetQueueAttributes", "sqs:CreateQueue"
  ],
  "Resource": "arn:aws:sqs:us-east-1:123456789012:orbit-prod-*"
}
```

`sqs:CreateQueue` is only needed if you let Orbit create queues on first use. If you create
queues with Terraform or CloudFormation, drop it. A missing permission surfaces as
**ORB-1002 BrokerAuthError**.

## How Orbit maps onto SQS

| Orbit concept | SQS mechanism |
|---|---|
| Lease | Visibility timeout, set to `lease_seconds` on receive |
| Heartbeat | `ChangeMessageVisibility` every `heartbeat_seconds` |
| Ack | `DeleteMessage` |
| Delay | `DelaySeconds` |
| Scheduler lock | A message in `<prefix>-orbit-locks` with a long visibility timeout |
| DLQ | An Orbit-managed queue `<prefix>-<queue>-dlq` |

**Leases.** SQS caps the visibility timeout at 12 hours, so a single lease can't exceed that.
Heartbeats keep extending it, so long jobs are fine as long as heartbeats get through. See
[Leases and heartbeats](leases-and-heartbeats.md).

**Delays.** SQS only supports delays up to 15 minutes per message. For longer delays, Orbit
re-sends the message with a fresh delay every 15 minutes until it is due. A 2-hour delay
therefore costs 8 sends. See [Delays](scheduling-delays.md).

### Priorities

SQS has no message priority. Orbit emulates it with **one SQS queue per priority level**:

| Orbit queue + priority | SQS queue |
|---|---|
| `default`, `high` | `orbit-prod-default-high` |
| `default`, `normal` | `orbit-prod-default` |
| `default`, `low` | `orbit-prod-default-low` |

Workers drain `-high` before `normal` before `-low` within each queue. The extra queues are
created only when a job with that priority is first enqueued. Priority on SQS is
**best-effort**: SQS long-polling returns whatever messages are available, so under light
load a `normal` job may start a moment before a `high` one enqueued at the same time.

## Do not configure an SQS redrive policy

> **Note:** Don't attach an SQS redrive policy (`maxReceiveCount`) to Orbit-managed queues.
> SQS counts receives, not failures. Heartbeat-extended leases, graceful shutdown hand-backs
> and prefetch all add receives. SQS would then move healthy jobs to its own DLQ behind
> Orbit's back, and those jobs never appear in `orbit dlq list`. Orbit already enforces your
> retry policy and dead-letters jobs itself with **ORB-1301 RetryExhausted**. See
> [Dead-letter queue](dead-letter-queue.md).

## FIFO queues and throttling (ORB-1901)

FIFO queues give strict ordering and built-in deduplication, but they have much lower
per-queue throughput limits than standard queues. When Orbit exceeds them, SQS throttles the
request and Orbit logs:

```text
WARN orbit.broker.sqs [ORB-1901] BrokerRateLimited: SendMessage throttled on
orbit-prod-default.fifo (attempt 2/5, retrying in 0.4s)
```

Orbit retries throttled calls with backoff, so a burst usually just slows down. Sustained
ORB-1901 means you are above the queue's limit. Options, best first:

1. **Use standard queues** unless you truly need strict ordering. Most jobs don't, because
   retries and redelivery reorder jobs anyway.
2. **Spread message groups.** By default Orbit uses the job's name as the `MessageGroupId`, so
   one hot job type serializes onto one group. Ordering is per group, so adding workers
   doesn't help. Splitting hot work across more job types or queues does.
3. **Enable high-throughput mode** on the FIFO queue in AWS.
4. Smooth out bulk enqueues: send a backfill in batches with short pauses, not in one tight
   loop. Lower `prefetch` on workers as well, since every prefetched message adds receive and
   visibility calls.

AWS publishes the current throughput quotas, and they change. Check them for your region.

## Idempotency on SQS

On Redis and Postgres, Orbit keeps idempotency records in the result backend. SQS deployments
run with `[results] backend = "none"` (see below), so those records aren't available. What
we can say today:

- On a **FIFO** queue, Orbit sets the SQS `MessageDeduplicationId` to the job name plus the
  key's value. SQS drops duplicate sends within its **5-minute** deduplication interval. A
  duplicate enqueued six minutes later is accepted.
- On a **standard** queue, `idempotency_key` doesn't de-duplicate enqueues at all.

> **Note:** This section is incomplete. The interaction between `idempotency_key`, FIFO
> deduplication and `orbit dlq replay` is still being documented (`comp:docs`). Until then,
> treat SQS as having **no long-lived enqueue de-duplication**. Make the job body itself
> idempotent, as described in [Idempotency](idempotency.md#making-side-effects-idempotent).

## Results and payload size

SQS has no matching result backend, and mixed setups (an SQS broker with a Redis result
backend) aren't supported. Set it explicitly:

```toml
[broker]
url = "sqs://us-east-1/orbit-prod"

[results]
backend = "none"
```

The default is `"redis"`, so an SQS project that leaves out `[results]` gets **ORB-1601
ResultBackendUnavailable**. With `backend = "none"`, Flows aren't available. See
[Result backend](results-backend.md). SQS also enforces its own maximum message size.
Keep `[limits] max_payload_kb` at or below your queue's configured maximum, or sends that
pass Orbit's check will still be rejected by SQS. Large data belongs in S3, with the object
key passed as the argument.

## See also

- [Brokers](concepts-brokers.md)
- [Broker problems](troubleshooting-broker.md)
- [Error codes](error-codes.md)
