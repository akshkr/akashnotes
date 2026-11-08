---
id: troubleshooting-memory
title: "Troubleshooting: worker memory growth and ORB-2101"
section: Troubleshooting
applies_to: "3.x"
updated: 2026-10-23
---

# Troubleshooting: worker memory growth and ORB-2101

Typical symptoms: a worker's resident memory climbs for hours and never comes back down, the
container gets `OOMKilled`, or logs show `WorkerOOM` (ORB-2101) after a restart. Work through
the causes below. The first one is a known Orbit bug. The rest are configuration or job code.

## Known issue: memory growth with `prefetch` above 100 (3.2.x)

**Affects:** 3.2.0 and 3.2.1. **Status:** open, not fixed in any release yet.

On 3.2.x, workers configured with `[worker] prefetch` greater than 100 grow steadily, roughly in
proportion to throughput. Memory is not released after jobs complete. The cause is in the
prefetch buffer that was reworked in 3.2.0, which keeps references to already-acknowledged
messages when the buffer is large. Workers at the default `prefetch = 10` are not affected.

```text
# RSS of one worker, prefetch = 500, concurrency = 16, ~800 jobs/s
t+0h    410 MB
t+2h    1.3 GB
t+4h    2.2 GB
t+4h12m ERROR orbit.worker ORB-2101 WorkerOOM rss_mb=2048 limit_mb=2048
```

**Workaround:**

```toml
[worker]
prefetch = 50   # anything <= 100 avoids the leak on 3.2.x
```

If you really need a deep buffer for very short jobs, add worker processes rather than
raising prefetch ([scaling-workers.md](scaling-workers.md)). As a stopgap you can recycle
workers on a schedule, for example with systemd's `RuntimeMaxSec=6h` and `Restart=always`.
Graceful restarts don't lose jobs ([deployment-systemd.md](deployment-systemd.md)).

> **Note:** This is the only known memory leak in Orbit itself. If your workers grow with
> `prefetch` ≤ 100, the cause is almost certainly one of the sections below.

## Concurrency × peak job memory

Peak worker memory is roughly:

```text
baseline (~150 MB) + concurrency × peak memory of one job
```

A job that loads a 300 MB model or a large DataFrame at `concurrency = 8` needs about 2.5 GB
at peak. If your limit is 2 GB, you will see ORB-2101 only when several heavy jobs happen to
overlap, which makes it look random. Lower `concurrency`, or route heavy jobs to a separate
queue with its own low-concurrency worker:

```bash
orbit worker --queues heavy --concurrency 2
```

## Large payloads and results

Arguments and return values are held in memory while they're serialized and deserialized.
`[limits] max_payload_kb` (default 512) caps arguments, and Flow step results are held to the
same limit (`PayloadTooLarge`, ORB-1202). Raising the limit to make an ORB-1202 go away usually
just moves the problem into memory.

- Pass object-store keys, not file contents.
- Return small summaries from jobs, not whole datasets.
- For Flows, have a step write its large output elsewhere and return the location. See
  [flows-steps-and-state.md](flows-steps-and-state.md).

## Leaks in job code

Worker processes are long-lived, so module-level state accumulates:

```python
_cache = {}  # grows forever in a long-lived worker

@app.job()
def enrich(ticket_id: str):
    _cache[ticket_id] = fetch_ticket(ticket_id)  # never evicted
```

Use bounded caches (`functools.lru_cache(maxsize=...)`), close clients and files you open, and
avoid appending to global lists. To find the leak, take snapshots with `tracemalloc` in a
staging worker:

```python
import tracemalloc

tracemalloc.start(25)

@app.job()
def memory_report():
    snapshot = tracemalloc.take_snapshot()
    for stat in snapshot.statistics("lineno")[:10]:
        print(stat)
```

Enqueue `memory_report` a few times, an hour apart, and compare which lines keep growing.

## Result backend growth (not worker memory)

If it's **Redis** memory that grows rather than the worker, look at `[results] ttl_days`. At the
default of 7 days, a high-throughput service keeps a week of results. Lower it, or return
`None` from jobs whose results nobody reads ([performance-tuning.md](performance-tuning.md)).

## Summary table

| Signal | Cause | Fix |
|---|---|---|
| Steady growth, `prefetch` > 100, 3.2.x | Known prefetch buffer leak | `prefetch` ≤ 100 |
| Spiky OOMs when heavy jobs overlap | Concurrency × job size | Lower concurrency, separate queue |
| ORB-1202 alongside high memory | Big payloads or results | Pass references |
| Slow growth at any setting | Job-level leak | `tracemalloc`, bounded caches |
| Broker or Redis memory grows | Result retention | Lower `ttl_days` |

See also: [error-codes.md](error-codes.md#orb-2101-workeroom) and the 3.2.0 entry in the
[changelog](changelog.md).
