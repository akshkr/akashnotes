---
id: quickstart
title: Quickstart
section: Getting started
applies_to: 3.x
updated: 2026-10-21
---

# Quickstart

This guide takes you from nothing to a running worker processing jobs on a local Redis broker.
It takes about ten minutes. It targets **Orbit 3.x** (current: 3.2.1). On 2.x, configuration
works differently; see [Environment variables (2.x)](environment-variables-2x.md).

You need Python 3.10–3.12 and Docker (or any Redis 6.2+ you can reach).

## 1. Install Orbit

```bash
python -m venv .venv && source .venv/bin/activate
pip install "orbit[redis,dashboard]>=3.2.1,<3.3"
orbit --version
```

[Installation](installation.md) covers the other brokers and the optional extras.

## 2. Start Redis

```bash
docker run -d --name orbit-redis -p 6379:6379 redis:7 \
  redis-server --appendonly yes --maxmemory-policy noeviction
```

The two flags make Redis behave like a queue rather than a cache. The
[Redis broker](broker-redis.md) page explains why both matter.

## 3. Write `orbit.toml`

Create a project directory with this file in it:

```toml
# orbit.toml
[broker]
url = "redis://localhost:6379/0"

[worker]
concurrency = 4

[results]
backend = "redis"
ttl_days = 7
```

Every key you leave out uses its default. The full list is in the
[configuration reference](configuration-reference.md). Orbit reads `orbit.toml` from the
current working directory, so run every command below from this directory.

## 4. Define a job

```python
# tasks.py
import time
from orbit import Orbit

app = Orbit()  # broker URL comes from orbit.toml

@app.job(retries=3, backoff="exponential", timeout="30s", idempotency_key="order_id")
def send_receipt(order_id: str):
    print(f"sending receipt for {order_id}")
    time.sleep(1)  # pretend to call an email API
    return {"order_id": order_id, "status": "sent"}

@app.job()
def send_digest():
    print("weekly digest")

app.schedule(send_digest, cron="0 9 * * MON")
```

A few things to notice:

- Arguments must be JSON-serializable, so pass an ID and not an object
  ([Jobs](concepts-jobs.md)).
- `idempotency_key="order_id"` means enqueueing the same order twice creates one job
  ([Idempotency](idempotency.md)).
- `app.schedule` registers a [cron schedule](scheduling-cron.md). Any running worker fires it.

## 5. Check your setup

```bash
$ orbit doctor
orbit 3.2.1 (python 3.12.6)
[ok]   config    orbit.toml loaded (3 sections)
[ok]   broker    redis://localhost:6379/0 reachable (PING 0.3 ms)
[ok]   results   redis backend reachable
```

If the broker line fails with **ORB-1001 BrokerConnectionError**, Redis isn't running or isn't
on port 6379. If you see **ORB-1802 UnknownConfigKey**, there is a typo in `orbit.toml`.

## 6. Start a worker

In a second terminal, from the same directory:

```bash
orbit worker --queues default,high --concurrency 4
```

```text
INFO  orbit.worker  orbit 3.2.1 worker w-3c1e starting
INFO  orbit.worker  queues=default,high concurrency=4 prefetch=10
INFO  orbit.broker  connected redis://localhost:6379/0
INFO  orbit.worker  registered jobs: tasks.send_receipt, tasks.send_digest
```

The worker must be able to import your job modules, which is why it runs from the project
directory. [Workers](concepts-workers.md) explains concurrency, prefetch and shutdown.

## 7. Enqueue jobs

Back in the first terminal:

```python
# enqueue.py
from tasks import send_receipt

handle = send_receipt.enqueue(order_id="A-1001")
print("queued", handle.id)
print(handle.result(timeout="30s"))

# Higher priority, and not before 10 seconds from now
send_receipt.enqueue(order_id="A-1002", priority="high", delay="10s")
```

```bash
$ python enqueue.py
queued j_5f2a0c
{'order_id': 'A-1001', 'status': 'sent'}
```

The worker terminal shows each job start and finish. Run `enqueue.py` a second time and
`A-1001` is **not** sent again. The idempotency key returns the existing job instead.

Now break something on purpose. Make `send_receipt` raise an exception, restart the worker and
enqueue a new order ID. You'll see the retries back off and then
**ORB-1301 RetryExhausted** as the job moves to the dead-letter queue:

```bash
orbit dlq list
orbit dlq replay <job_id>   # after fixing the bug
```

See [Retries and backoff](retries-and-backoff.md) and [Dead-letter queue](dead-letter-queue.md).

## 8. Open the dashboard

```bash
orbit dashboard --port 7777
```

The dashboard prints a sign-in URL with a one-time token to its log. Open it to see queues,
running jobs, the DLQ and your schedule. Token mode is fine on a laptop. Before you share a
dashboard with a team, read [Dashboard](dashboard.md) and
[Dashboard auth with OIDC](dashboard-auth-oidc.md).

## 9. Stop the worker

Press Ctrl+C. The worker stops claiming jobs, finishes the ones it is running, and exits. On
Linux and macOS, `SIGTERM` does the same. On Windows only Ctrl+C works; see
[Workers](concepts-workers.md#shutdown).

## Next steps

- Model a multi-step process with [Flows](flows-overview.md).
- Learn how Orbit avoids losing jobs, and why it occasionally runs one twice:
  [Leases and heartbeats](leases-and-heartbeats.md).
- Deploy for real: [Docker](deployment-docker.md), [Kubernetes](deployment-kubernetes.md) or
  [systemd](deployment-systemd.md).
- Coming from 2.x? Read [Migrating from 2.x to 3.x](migrating-2-to-3.md).
