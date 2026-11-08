# Capstone R5, Part 1: Integrate & Harden

You now own twelve good parts that have never met. Wire them in the wrong order and each still passes its own tests while the system fails: a cache that answers before the tenant is known hands Acme's runbook to Zephyr, and retries that skip the breaker turn one outage into a retry storm. Integration is choosing that order, proving it with tests and running it somewhere production-like. Today R5 becomes one system on staging.

## At a Glance

- **Time:** ~3 h core (capstone; fine to split across two sittings) (+ optional Go Deeper) · **Depth:** working
- **Prerequisites:** Days 77–88: [Serving LLM Apps with FastAPI](../../Phase_9_Production/Day_077_fastapi_serving/fastapi_serving.md), [Async Jobs](../../Phase_9_Production/Day_078_async_jobs/async_jobs.md), [Chat UIs](../../Phase_9_Production/Day_079_chat_uis_streaming/chat_uis_streaming.md), [Generative UI](../../Phase_9_Production/Day_080_generative_ui/generative_ui.md), [Voice](../../Phase_9_Production/Day_081_voice_realtime/voice_realtime.md), [Containerize & Deploy](../../Phase_9_Production/Day_082_containerize_deploy/containerize_deploy.md), [Auth & Quotas](../../Phase_9_Production/Day_083_auth_multitenancy_quotas/auth_multitenancy_quotas.md), [Reliability](../../Phase_9_Production/Day_084_reliability_fallbacks/reliability_fallbacks.md), [Caching](../../Phase_9_Production/Day_085_caching_cost_scale/caching_cost_scale.md), [Monitoring](../../Phase_9_Production/Day_086_monitoring_feedback/monitoring_feedback.md), [Shipping Changes](../../Phase_9_Production/Day_087_shipping_changes_safely/shipping_changes_safely.md), [Operating AI Systems](../../Phase_9_Production/Day_088_operating_ai_systems/operating_ai_systems.md); plus your R2–R4 tags ([Day 34](../../Phase_3_RAG/Day_034_capstone_r2_ask/capstone_r2_ask.md), [Day 62](../../Phase_6_Agents/Day_062_capstone_r3_ship/capstone_r3_ship.md), [Day 76](../../Phase_8_Safety_and_Security/Day_076_capstone_r4_triage/capstone_r4_triage.md))
- **You'll build:** R5 integrated: one FastAPI app that serves R2 (ask), R3 (investigate) and R4 (triage) through a fixed request pipeline, 8 integration tests, a hardening checklist, and a first staging deploy with recorded numbers
- **Stops at:** staging. Load tests, the chaos drill, SLOs and the production release are [Day 90](../../Phase_9_Production/Day_090_capstone_r5_launch/capstone_r5_launch.md); multi-region, Kubernetes and SSO are out of scope
- **Fast path:** your R5 repo already holds each day's `### Commit it to R5` changes? Read §2 (One Request, by Hand), §6 (The Pipeline) and §9 (Integration Tests), run the tests, deploy, then do Exercise 2 (~1.5 h)
- **Cost:** ≈ $1 for the 10-minute staging replay, the fast evals and a few investigations on `gpt-6-luna` (prices as of 2026-11, [verify](https://developers.openai.com/api/docs/pricing)). Everything else runs keyless on `ATLAS_BACKEND=stub`
- **New terms:** composition root, request pipeline order, backend adapter (reference vs stub), hardening checklist, release candidate (rc) tag

> **Coming from Software Engineering?** This is a composition root plus a middleware pipeline, the same shape as an Express or ASP.NET Core app with a servlet-style filter chain in front of the handlers. R2–R4 plug in through ports and adapters (an adapter is a thin wrapper that makes one interface look like another), so tests swap the real backends for stand-ins with one setting. You test at the HTTP boundary. R1–R4 were the portfolio thread; R5 is the product they feed. What's new: every stage can spend money, so the order of the stages is also a cost decision.

## Twelve Parts, One Product

Think of an airport: check-in (auth), baggage limits (caps and quotas), a fast lane for people already cleared (the cache), the choice of plane (routing), a backup flight (fallback) and a logbook of every passenger (the event log). Each desk works. Security after boarding is the bug.

R5 is the release that puts every earlier release behind one front door:

| Release | Built on | What it does | In R5 it becomes |
|---|---|---|---|
| R1 Extractor | [Day 22](../../Phase_2_Building_with_LLM_APIs/Day_022_capstone_r1_extractor/capstone_r1_extractor.md) | issue → typed record | offline batch job; not behind the API in R5.0 |
| R2 Ask | Day 34 | cited RAG answers | `POST /v1/ask`, `/v1/ask/stream` |
| R3 Investigator | Days 61–62 | cited diagnosis of one issue | `POST /v1/investigate/stream` |
| R4 Triage | Day 76 | proposed labels, duplicate, reply; approval + audit | `POST /v1/triage` (proposes only) |
| R5 Atlas | Days 89–90 | one product, staging, then production | this repo |

Two parts stay off in R5: voice (Day 81) is optional, and the WebSocket route (Day 79) has no auth on the socket yet.

**Start state.** Your `r4-v1.0` tag (or the course's `r4-reference` tag) plus your Day 77–88 commits, made from each lesson's `### Commit it to R5` table. Missing a day? §3's `assemble_r5` rebuilds it. Today's code imports those files; it doesn't re-print them.

```mermaid
flowchart LR
  UI["Gradio UI (D79, D80)"] -->|"SSE + API key"| API
  subgraph API["FastAPI app (D77)"]
    G["auth, caps, quotas (D83)"] --> C["semantic cache (D85)"]
    C --> R["model router (D85)"]
    R --> X["resilience (D84)"]
  end
  X --> S["services: R2 ask, R3 investigate, R4 triage"]
  S --> O["OpenAI Responses API"]
  API --- RD[("Redis: quotas, RQ, kill switches")]
  S --- PG[("Postgres + pgvector")]
  RD --- W["RQ worker (D78)"]
  API --> EV[("event log (D86)")]
  API -.->|"spans"| PH["Phoenix (D42)"]
```

## One Request, by Hand

Trace one request on paper: Acme's on-call engineer asks "How do retries back off?". The numbers are toys; §11 measures real ones.

| # | Stage (owner) | Toy cost | If it says no |
|---|---|---|---|
| 1 | Request id (today) | 0 ms | never |
| 2 | Body limit (today) | 0 ms | 413, or 411 with no `Content-Length` |
| 3 | Auth: key → `Principal` (D83) | 1 ms, SQLite | 401 / 403 |
| 4 | Kill switches (D88) | 0 ms, cached 5 s | 503, or 429 for a tenant cap |
| 5 | Input cap (D83) | 1 ms, tokenizer | 413 `input_too_large` |
| 6 | Rate limit (D83) | 1 ms, Redis | 429 + `Retry-After` |
| 7 | Semantic cache, tenant-scoped (D85) | 3 ms | **hit: answer now, $0** |
| 8 | Token reservation (D83) | 1 ms, Redis | 429 `quota_exceeded` |
| 9 | Route model (D85) | 0 ms | never: picks `gpt-6-luna` or `gpt-6.1-terra` |
| 10 | Resilient call (D84) | 1,800 ms; 2,400 in + 250 out tokens | fallback model, or a degraded 200 |
| 11 | Settle tokens (D83) | 1 ms | never: runs in `finally` |
| 12 | Event row + online checks (D86) | 2 ms + background | never |

Stage 10 at `gpt-6-luna` prices ($0.10 in, $0.50 out per 1M tokens, as of 2026-11, [verify](https://developers.openai.com/api/docs/pricing)) is 2,400 × $0.10/1M + 250 × $0.50/1M = $0.00024 + $0.000125 ≈ **$0.00037**. Stages 1–8 together cost a few milliseconds and no tokens, so you can always afford the safe order.

Now find the two wrong orders from the hook:

- **Cache (7) before auth (3).** Before auth there's no tenant to put in the cache key, so a shared key serves Zephyr the answer citing Acme's runbook. Fix: cache after auth, tenant inside `cache_scope()`.
- **Retries that ignore the breaker (10).** A retry loop outside `ResilientLLM`, or SDK retries underneath it, turns one 503 into 4 × 3 = 12 upstream calls. Fix: one retry layer, the SDK client at `max_retries=0`, and every attempt asks its breaker first.

A quieter third: **reserving tokens (8) before the cache (7)** charges cache hits against the quota. Streams are the one exception (§6).

## The Project Layout

R5 is one repo. Each file printed today has one `script_id`, named after its module path, so files import each other as `from atlas.api.deps import Deps`. The rest is carried forward.

```text
atlas/
  config.py            CHANGED  D82 Settings + backend, index_version, phoenix_endpoint, cache_threshold
  services.py          CHANGED  D77 seam widened; reference adapters over R2-R4
  stubs.py             NEW      keyless, tenant-aware stand-ins
  api/deps.py          NEW      the composition root: Deps, build_deps()
  api/pipeline.py      NEW      the 12-stage request path
  api/app.py           CHANGED  create_app(settings): middleware, routes, readiness
  ui/main.py           NEW      D79 chat + API key + cards + feedback
scripts/seed_tenants.py, scripts/smoke_staging.py     NEW
tests/test_integration.py                            NEW
```

<details><summary>Carried files and the names used from each</summary>

| Carried file (not re-printed) | From | Names used today |
|---|---|---|
| `atlas/api/models.py`, `atlas/api/events.py` | D77 | `Answer`, `Citation`, `AskRequest`, `AskResponse`, `InvestigateRequest`, `TriageRequest`, `AgentEvent`, `sse_stream` |
| `atlas/jobs.py` | D78 | `get_redis` (sync), `load_open_issues`, `rules_triage` |
| `atlas/ui/app.py`, `atlas/ui/components.py` | D79, D80 | `iter_sse`, `to_messages`, `_route`, `AgentEvent`; `to_ui_event`, `render_html` |
| `atlas/api/auth.py`, `atlas/tenancy.py`, `atlas/quotas.py` | D83 | `Principal`, `KeyStore`, `require_principal`, `require_scope`; `tenant_key`, `visible_tenants`, `load_corpus`, `search`; `PLANS`, `RateLimiter`, `TokenQuota`, `QuotaExceeded`, `count_tokens`, `get_redis` (async) |
| `atlas/resilience.py` | D84 | `ResilientLLM`, `RetryPolicy`, `CircuitBreaker`, `CallMeta`, `AllModelsUnavailable`, `degraded_answer`, `keyword_search`, `load_chunks`, `FakeAsyncClient`, `FaultInjector` |
| `atlas/cache.py`, `atlas/model_router.py` | D85 | `SemanticCache`, `hashed_embed`, `cache_scope`, `detect_version`; `choose_model`, `cost_usd`, `STRONG` |
| `atlas/monitoring.py`, `atlas/feedback.py`, `scripts/replay_traffic.py` | D86 | `RequestEvent`, `EventLog`, `score_request`, `Answer`; `feedback_router`; `replay_traffic` |
| `atlas/flags.py`, `release.toml` | D87 | `ReleaseWatcher`, `resolve_prompt`, `RELEASE_TOML` |
| `atlas/ops.py`, `atlas/index_migration.py`, `scripts/game_day.py` | D88 | `get_overrides`, `plan_request`; `openai_embed`; `DrillReport` (used by Day 90) |
| `atlas/tracing.py` | D42 | `setup_tracing`, `step_span` |
| `scripts/smoke_test.py` | D82 | `smoke` |
| R2–R4 modules (`atlas/rag.py`, `graph.py`, `tools.py`, `triage.py`, `schemas.py`, `prompts/`) | r4 tag | `rag.retrieve`/`build_context`/`verify_citations`, `build_investigator_graph`, `read_issue`, `build_triage_graph` (reference backend only) |

</details>

Three conventions: `atlas/` and `atlas/api/` are namespace packages (no `__init__.py`); `pythonpath = ["."]` under `[tool.pytest.ini_options]` lets tests import `scripts.*`; and only `app.py` imports routes, while shared names live in `deps.py` and `pipeline.py`, so imports stay one-directional.

Missing a carried file? `assemble_r5` stitches it from its lesson and rewrites flat imports to `atlas.*`, never overwriting yours.

```python
# script_id: day_089_capstone_r5_integrate/scripts/assemble_r5
# scripts/assemble_r5.py: write the carried files you don't have yet, from the course lessons.
# Run: uv run python scripts/assemble_r5.py [COURSE_DIR]   Stdlib only.
# COURSE_DIR defaults to the course checkout holding $ORBIT_DATA (<course>/datasets/orbit).
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

CARRIED = {   # R5 file -> (day, that lesson's script_ids, stitched in order): §3's table as data
    "atlas/api/events.py": ("077", ["events"]), "atlas/jobs.py": ("078", ["atlas_jobs"]),
    "atlas/ui/app.py": ("079", ["atlas_ui"]), "atlas/ui/components.py": ("080", ["components"]),
    "scripts/smoke_test.py": ("082", ["smoke_test"]), "atlas/api/auth.py": ("083", ["auth"]),
    "atlas/tenancy.py": ("083", ["tenancy"]), "atlas/quotas.py": ("083", ["quotas"]),
    "atlas/resilience.py": ("084", ["atlas_resilience"]), "atlas/cache.py": ("085", ["atlas_cache"]),
    "atlas/model_router.py": ("085", ["atlas_router"]), "atlas/monitoring.py": ("086", ["atlas_monitoring"]),
    "atlas/feedback.py": ("086", ["feedback"]), "scripts/replay_traffic.py": ("086", ["replay_traffic"]),
    "atlas/flags.py": ("087", ["atlas_release"]), "atlas/ops.py": ("088", ["atlas_ops"]),
    "atlas/index_migration.py": ("088", ["index_migration", "openai_embed"]),
    "scripts/game_day.py": ("088", ["game_day"]),
    "atlas/tracing.py": ("042", ["atlas/tracing"]),
}
MODULES = {   # a lesson's flat import name -> its R5 module
    "auth": "atlas.api.auth", "tenancy": "atlas.tenancy", "quotas": "atlas.quotas",
    "atlas_resilience": "atlas.resilience", "atlas_cache": "atlas.cache", "first_semantic_cache": "atlas.cache",
    "atlas_router": "atlas.model_router", "atlas_monitoring": "atlas.monitoring", "atlas_release": "atlas.flags",
    "atlas_ops": "atlas.ops", "atlas_jobs": "atlas.jobs", "events": "atlas.api.events",
    "components": "atlas.ui.components", "smoke_test": "scripts.smoke_test", "feedback": "atlas.feedback",
    "index_migration": "atlas.index_migration", "atlas_ui": "atlas.ui.app",
}
# Day 77 kept its request/response models in `events`; R5 imports them from atlas.api.models
MODELS_SHIM = ("from atlas.api.events import (Answer, AskRequest, AskResponse, Citation,  # noqa: F401\n"
               "                              InvestigateRequest, TriageRequest)\n")
FENCE = re.compile(r"```python\n# script_id: day_\d{3}_\w+/(\S+)\n(.*?)```", re.S)
```

```python
# script_id: day_089_capstone_r5_integrate/scripts/assemble_r5
def stitch(course: Path, day: str, ids: list[str]) -> str:
    lesson = next(course.glob(f"Phase_*/Day_{day}_*/*.md"))
    blocks: dict[str, list[str]] = {}
    for sid, code in FENCE.findall(lesson.read_text(encoding="utf-8")):
        blocks.setdefault(sid, []).append(code)
    code = "\n".join(part for sid in ids for part in blocks[sid])
    for flat, mod in MODULES.items():                 # `from auth import X` -> `from atlas.api.auth import X`
        code = re.sub(rf"^(\s*)from {flat} import", rf"\1from {mod} import", code, flags=re.M)
        code = re.sub(rf"^(\s*)import {flat}\b", rf"\1import {mod} as {flat}", code, flags=re.M)
    return code


def assemble(course: Path, root: Path) -> tuple[list[str], list[str]]:
    wrote, kept = [], []
    files = {path: (lambda d=day, i=ids: stitch(course, d, i)) for path, (day, ids) in CARRIED.items()}
    files["atlas/api/models.py"] = lambda: MODELS_SHIM
    for path, build in files.items():
        target = root / path
        if target.exists():                           # your own commit wins
            kept.append(path)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(build(), encoding="utf-8")
        wrote.append(path)
    return wrote, kept


if __name__ == "__main__":
    default = Path(os.environ.get("ORBIT_DATA", "datasets/orbit")).resolve().parents[1]
    course = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    wrote, kept = assemble(course, Path(__file__).resolve().parents[1])
    print(f"wrote {len(wrote)} carried files, kept {len(kept)} of yours")
```

```text
wrote 20 carried files, kept 0 of yours        (on a clean copy; your own repo keeps more)
```

## Settings and the Composition Root

A **composition root** is the one place where every long-lived object is constructed and connected. In R5 that's `build_deps()`, called once in FastAPI's `lifespan`; nothing else builds a client, a Redis connection or a cache. One place answers "which retry policy is live?", and tests swap one object.

Day 82's `Settings` gains four fields and two paths. The stub backend needs no OpenAI key, so the key is required only for `ATLAS_BACKEND=reference`.

```python
# script_id: day_089_capstone_r5_integrate/atlas/config
# atlas/config.py: Day 82's Settings plus the R5 fields. Stdlib only. Env: ATLAS_* (see .env.example)
# Keep the r4-reference constants block (MODEL, DATA_DIR, STATE_DIR, PRICES_PER_1M, ...) at the top
# of this file unchanged: R2-R4 modules import those names. Only Settings is shown here.
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


class ConfigError(RuntimeError):
    """Startup configuration is invalid; the message lists every problem found."""


def _split(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


@dataclass(frozen=True)
class Settings:
    env: Literal["dev", "staging", "prod"]
    release: str
    model: str
    fallback_models: tuple[str, ...]
    embed_model: str
    data_dir: Path
    redis_url: str
    database_url: str | None
    api_url: str
    allowed_origins: tuple[str, ...]
    backend: Literal["reference", "stub"] = "stub"   # new: which R2-R4 sit behind the API
    index_version: str = "v1"                       # new: part of every cache key (Day 88)
    phoenix_endpoint: str | None = None             # new: OTLP URL, e.g. http://localhost:6006/v1/traces; None = off
    cache_threshold: float = 0.95                   # new: from Day 85's threshold sweep
    state_dir: Path = Path(".atlas")                # keys.db, events.db
    release_file: Path = Path("release.toml")       # Day 87's pins and canaries
```

```python
# script_id: day_089_capstone_r5_integrate/atlas/config
    # (Settings continues) every knob from the environment, checked once, every problem reported
    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        e = os.environ if environ is None else environ
        env, backend = e.get("ATLAS_ENV", "dev"), e.get("ATLAS_BACKEND", "stub")
        problems: list[str] = []
        if env not in ("dev", "staging", "prod"):
            problems.append(f"ATLAS_ENV must be dev, staging or prod, not {env!r}")
        required = ["ATLAS_RELEASE", "ATLAS_REDIS_URL"] + (["OPENAI_API_KEY"] if backend == "reference" else [])
        if env != "dev" and (missing := [k for k in required if not e.get(k)]):
            problems.append("missing " + ", ".join(missing))
        if backend not in ("reference", "stub") or (env == "prod" and backend == "stub"):
            problems.append(f"ATLAS_BACKEND={backend!r} is not allowed in {env}")
        origins = _split(e.get("ATLAS_ALLOWED_ORIGINS", "http://localhost:7860"))
        if env != "dev" and "*" in origins:          # Day 82 blocked it in prod; R5 blocks staging too
            problems.append("ATLAS_ALLOWED_ORIGINS='*' is only allowed in dev")
        try:
            threshold = float(e.get("ATLAS_CACHE_THRESHOLD", "0.95"))
        except ValueError:
            threshold = -1.0
        if not 0 < threshold <= 1:
            problems.append("ATLAS_CACHE_THRESHOLD must be a number in (0, 1]")
        if problems:
            raise ConfigError(f"ATLAS_ENV={env}: " + "; ".join(problems))
        return cls(env=env, release=e.get("ATLAS_RELEASE", "dev"),  # type: ignore[arg-type]
                   model=e.get("ATLAS_MODEL", "gpt-6-luna"),
                   fallback_models=_split(e.get("ATLAS_FALLBACK_MODELS", "gpt-6.1-terra")),
                   embed_model=e.get("ATLAS_EMBED_MODEL", "text-embedding-3-small"),
                   data_dir=Path(e.get("ORBIT_DATA", "datasets/orbit")),
                   redis_url=e.get("ATLAS_REDIS_URL", "redis://localhost:6379/0"),
                   database_url=e.get("ATLAS_DATABASE_URL") or None,
                   api_url=e.get("ATLAS_API_URL", "http://localhost:8000"), allowed_origins=origins,
                   backend=backend, index_version=e.get("ATLAS_INDEX_VERSION", "v1"),  # type: ignore[arg-type]
                   phoenix_endpoint=e.get("ATLAS_PHOENIX_ENDPOINT") or None, cache_threshold=threshold,
                   state_dir=Path(e.get("ATLAS_STATE_DIR", ".atlas")),
                   release_file=Path(e.get("ATLAS_RELEASE_FILE", "release.toml")))
```

```python
# script_id: day_089_capstone_r5_integrate/atlas/config
if __name__ == "__main__":
    s = Settings.from_env({"ATLAS_REDIS_URL": "fake://"})
    print(s.env, s.backend, s.model, s.fallback_models, s.index_version)
    try:
        Settings.from_env({"ATLAS_ENV": "prod", "ATLAS_RELEASE": "3f2c1ab", "ATLAS_REDIS_URL": "redis://r:6379/0"})
    except ConfigError as err:
        print(f"ConfigError: {err}")
```

```text
dev stub gpt-6-luna ('gpt-6.1-terra',) v1
ConfigError: ATLAS_ENV=prod: ATLAS_BACKEND='stub' is not allowed in prod
```

`Deps` holds every long-lived object; `build_deps()` is its only constructor. Two details matter: the OpenAI client has `max_retries=0` because `ResilientLLM` is the one retry layer, and there's one pool per model the router can pick (pool *m* tries *m* first), all sharing one breaker per model.

```python
# script_id: day_089_capstone_r5_integrate/atlas/api/deps
# atlas/api/deps.py: the composition root. Every long-lived object is built here, once, at startup.
# Install: uv add "openai>=3.46,<4" "redis>=8.1" fakeredis numpy   Env: see atlas/config.py
from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import numpy as np

from atlas.api.auth import KeyStore
from atlas.cache import SemanticCache, hashed_embed
from atlas.config import Settings
from atlas.flags import ReleaseWatcher
from atlas.jobs import get_redis as get_sync_redis     # Day 78's sync client: Day 88's levers use it
from atlas.model_router import STRONG
from atlas.monitoring import EventLog
from atlas.quotas import RateLimiter, TokenQuota, get_redis   # Day 83's async client
from atlas.resilience import (CircuitBreaker, DocChunk, FakeAsyncClient, FaultInjector, ResilientLLM,
                              RetryPolicy, load_chunks)
from atlas.services import AtlasServices, ParseShim, load_services

INTERACTIVE = RetryPolicy(max_attempts=3, max_wait_s=5.0)    # a person is waiting: fall back sooner


@dataclass
class Deps:
    settings: Settings
    redis: Any                          # async Redis: rate limits, token quotas, stream slots
    ops_redis: Any                      # sync Redis: kill switches and their audit log
    services: AtlasServices
    llms: dict[str, ResilientLLM]       # one pool per routable model; all share `breakers`
    breakers: dict[str, CircuitBreaker]
    cache: SemanticCache
    events: EventLog
    keys: KeyStore
    quotas: TokenQuota
    limiter: RateLimiter
    release: ReleaseWatcher
    chunks: list[DocChunk]              # degraded mode's keyword index (Day 84)
    client: Any = None                  # the real AsyncOpenAI, closed at shutdown
```

```python
# script_id: day_089_capstone_r5_integrate/atlas/api/deps
def build_pools(client: Any, models: list[str], *, policy: RetryPolicy = INTERACTIVE
                ) -> tuple[dict[str, ResilientLLM], dict[str, CircuitBreaker]]:
    """Pool m tries m first, then the others. One breaker per model, shared by every pool."""
    pools = {m: ResilientLLM(client, [m, *(x for x in models if x != m)], policy=policy) for m in models}
    breakers = pools[models[0]].breakers
    for pool in pools.values():
        pool.breakers = breakers
    return pools, breakers


def _embedder(settings: Settings):
    if settings.backend == "stub":
        return hashed_embed                         # Day 85's offline stand-in: tests and demos only
    from atlas.index_migration import openai_embed  # Day 88's real embedder (needs a key)
    v = SimpleNamespace(embed_model=settings.embed_model, dims=256)   # small vectors: cache only

    def embed(texts: list[str]) -> np.ndarray:
        vecs = openai_embed(texts, v)
        return vecs / np.linalg.norm(vecs, axis=1, keepdims=True)    # the cache's dot product = cosine
    return embed


def build_deps(settings: Settings) -> Deps:
    models = list(dict.fromkeys([settings.model, *settings.fallback_models, STRONG]))
    client = None
    if settings.backend == "reference":
        from openai import AsyncOpenAI
        client = AsyncOpenAI(timeout=30.0, max_retries=0)    # ResilientLLM is the ONE retry layer
    pools, breakers = build_pools(ParseShim(client) if client else FakeAsyncClient(FaultInjector({})), models)
    redis = get_redis(settings.redis_url)
    settings.state_dir.mkdir(parents=True, exist_ok=True)
    return Deps(settings=settings, redis=redis, ops_redis=get_sync_redis(settings.redis_url),
                services=load_services(settings), llms=pools, breakers=breakers,
                cache=SemanticCache(_embedder(settings), threshold=settings.cache_threshold),
                events=EventLog(settings.state_dir / "events.db"),
                keys=KeyStore(str(settings.state_dir / "keys.db")),
                quotas=TokenQuota(redis), limiter=RateLimiter(redis),
                release=ReleaseWatcher(settings.release_file), chunks=load_chunks(settings.data_dir),
                client=client)
```

Stub mode uses Day 84's `FakeAsyncClient`, which has the real client's `responses.create` shape, so breakers, fallbacks and degraded mode run the same code in tests as in production.

## Plugging In R2–R4

Day 77's `AtlasServices` seam widens: `ask()` now receives the tenant's visible groups, the model pool and the prompt version. Two **backend adapters** implement it: `reference` wraps the r4-reference modules, and `stub` is keyless, so CI (and anyone with a broken R3) still runs the whole system. `ATLAS_BACKEND=reference|stub` picks one.

```python
# script_id: day_089_capstone_r5_integrate/atlas/services
# atlas/services.py: the seam between the API and R2-R4 (replaces Day 77's AtlasServices).
# ATLAS_BACKEND=stub -> atlas/stubs.py; reference -> thin adapters over the r4-reference modules.
from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import pydantic

from atlas.api.events import AgentEvent
from atlas.api.models import Answer
from atlas.config import Settings
from atlas.resilience import CallMeta


@dataclass
class AskOutcome:
    answer: Answer
    hits: list[str]              # retrieved doc ids: online checks compare citations with them
    meta: CallMeta               # which model answered, attempts, fallback (Day 84)
    input_tokens: int            # real usage from the response, not a length heuristic
    output_tokens: int


@dataclass(frozen=True)
class AtlasServices:
    """Day 77's seam, widened: ask() gets the tenant's groups, a model pool and a prompt version."""
    name: str                                        # "reference" | "stub", shown by /readyz
    ask: Callable[..., Awaitable[AskOutcome]]        # (question, *, groups, llm, effort, ...)
    investigate: Callable[[int], AsyncIterator[AgentEvent]]
    triage: Callable[[int], Awaitable[dict]]


def load_services(settings: Settings) -> AtlasServices:
    if settings.backend == "stub":
        from atlas.stubs import stub_services
        return stub_services()
    try:
        return reference_services(settings)
    except ImportError as exc:                       # fail at startup, never on a customer's request
        raise RuntimeError(f"ATLAS_BACKEND=reference needs the r4-reference modules ({exc}); "
                           "check out the tag, or set ATLAS_BACKEND=stub") from exc
```

R3 streams LangGraph updates; the UI speaks `AgentEvent`. With `stream_mode="updates"`, each chunk is `{node_name: what_that_node_returned}`, and `adapt_graph_events()` translates. `ParseShim` exists because `ResilientLLM` calls `responses.create()` while R2 needs `responses.parse()` for its `Answer` schema; the shim forwards one to the other.

```python
# script_id: day_089_capstone_r5_integrate/atlas/services
async def adapt_graph_events(updates: AsyncIterator[Any]) -> AsyncIterator[AgentEvent]:
    """LangGraph stream_mode="updates" chunks, {node: state_update}, -> Day 77 AgentEvents."""
    usage: dict = {}
    async for chunk in updates:
        for node, update in chunk.items():
            if not isinstance(update, dict):          # "__interrupt__" carries a tuple
                continue
            usage = update.get("usage", usage)
            for m in update.get("messages", []):
                for call in getattr(m, "tool_calls", None) or []:
                    yield AgentEvent(type="tool_call", data={"name": call["name"], "args": call["args"]})
                if getattr(m, "type", "") == "tool":
                    yield AgentEvent(type="tool_result", data={"name": m.name, "chars": len(str(m.content))})
            if d := update.get("diagnosis"):          # R3's Diagnosis, as a dict
                for c in d.get("doc_citations", []):
                    yield AgentEvent(type="citation", data={"doc_id": c["doc_id"]})
                yield AgentEvent(type="final", data={"text": f"{d['summary']}\n\nProbable cause: "
                                                     f"{d['probable_cause']}", "usage": usage,
                                                     "needs_human": d["needs_human"]})
            else:
                yield AgentEvent(type="status", data={"step": node, "state": "done"})


class ParseShim:
    """ResilientLLM calls client.responses.create(); route it to .parse() so R2's schema is kept."""

    def __init__(self, client: Any) -> None:
        self._client, self.responses = client, self

    async def create(self, **kwargs: Any) -> Any:
        return await self._client.responses.parse(**kwargs)
```

The reference adapters stay thin. Ask reuses R2's retrieval, prompts and citation check and changes only the call: async, through the pool, with the router's effort, the plan's output cap and `store=False` ([Day 73](../../Phase_8_Safety_and_Security/Day_073_privacy_pii/privacy_pii.md)). Triage uses R4's checkpointer file and thread id, so a maintainer still approves with `python cli.py resume triage-<id>`.

```python
# script_id: day_089_capstone_r5_integrate/atlas/services
def reference_services(settings: Settings) -> AtlasServices:
    """Adapters over R2 (Day 34), R3 (Day 61) and R4 (Day 76). Any missing module raises ImportError."""
    from langgraph.checkpoint.sqlite import SqliteSaver

    from atlas import rag
    from atlas.config import STATE_DIR                  # R4's constant, kept in config.py
    from atlas.graph import AgentConfig, build_investigator_graph
    from atlas.prompts.registry import load_prompt      # Day 21: returns a Prompt, so use .text; release.toml picks the version
    from atlas.schemas import Answer as R2Answer
    from atlas.tools import read_issue
    from atlas.triage import build_triage_graph

    index = rag.make_index()                            # ATLAS_INDEX=pg|memory, as in R2

    async def ask(question: str, *, groups: tuple[str, ...], llm: Any, effort: str,
                  max_output_tokens: int, prompt_version: str) -> AskOutcome:
        hits = await asyncio.to_thread(rag.retrieve, question, index=index, groups=groups)
        context, used = rag.build_context(hits)
        try:
            resp, meta = await llm.create(instructions=load_prompt("ask", prompt_version).text,
                                          input=f"{context}\n\nQuestion: {question}", text_format=R2Answer,
                                          reasoning={"effort": effort}, max_output_tokens=max_output_tokens,
                                          store=False)    # Day 73: the provider keeps nothing
        except pydantic.ValidationError:                # JSON cut off at the output cap (Day 16)
            idk = Answer(text=rag.IDK_TEXT, citations=[])
            return AskOutcome(idk, [], CallMeta(llm.models[0], 1, False, False, 0.0), 0, max_output_tokens)
        draft = resp.output_parsed or R2Answer(text=rag.IDK_TEXT, citations=[])
        good = [c for c in draft.citations if c not in rag.verify_citations(draft, used)]
        answer = Answer.model_validate({"text": draft.text if good else rag.IDK_TEXT,   # R2's rule
                                        "citations": [c.model_dump() for c in good]})
        u = resp.usage
        return AskOutcome(answer, [h.chunk.doc_id for h in used], meta,
                          u.input_tokens if u else 0, u.output_tokens if u else 0)
```

```python
# script_id: day_089_capstone_r5_integrate/atlas/services
    # (reference_services continues)
    async def investigate(issue_id: int) -> AsyncIterator[AgentEvent]:
        cfg = AgentConfig()
        graph = build_investigator_graph(config=cfg)    # no checkpointer: a one-shot API run
        start = {"thread_id": f"api-{issue_id}", "issue": read_issue(issue_id).model_dump()}
        updates = graph.astream(start, {"recursion_limit": 4 * cfg.max_steps + 12}, stream_mode="updates")
        async for event in adapt_graph_events(updates):
            yield event

    def triage_sync(issue_id: int) -> dict:
        saver = SqliteSaver(sqlite3.connect(str(STATE_DIR / "triage.sqlite"), check_same_thread=False))
        graph = build_triage_graph(saver)               # same file and thread id as R4's cli.py
        cfg = {"configurable": {"thread_id": f"triage-{issue_id}"}, "recursion_limit": 30}
        if done := graph.get_state(cfg).values.get("proposal"):
            return done                                 # already proposed: same answer, $0
        return graph.invoke({"issue_id": issue_id}, cfg)["proposal"]   # pauses at approval

    async def triage(issue_id: int) -> dict:
        return await asyncio.to_thread(triage_sync, issue_id)

    return AtlasServices("reference", ask, investigate, triage)
```

The stub searches Day 83's toy corpus (public docs plus Acme's and Zephyr's runbook notes), filtering by tenant *before* ranking, and still calls the pool it's handed, so a test that marks `gpt-6-luna` down sees a real fallback.

```python
# script_id: day_089_capstone_r5_integrate/atlas/stubs
# atlas/stubs.py: keyless stand-ins for R2-R4 (Day 77's stubs, now tenant-aware). ATLAS_BACKEND=stub.
# No key, no Postgres. Generation still goes through the ResilientLLM pool it is handed (a
# FakeAsyncClient in stub mode), so breakers, fallbacks and degraded mode behave as in production.
from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator

from fastapi import HTTPException

from atlas.api.events import AgentEvent
from atlas.api.models import Answer, Citation
from atlas.jobs import load_open_issues, rules_triage
from atlas.quotas import count_tokens
from atlas.resilience import ResilientLLM
from atlas.services import AskOutcome, AtlasServices
from atlas.tenancy import load_corpus, search
from atlas.ui.components import to_ui_event

WORD = re.compile(r"[a-z0-9_]{3,}")


def _cite_id(doc_id: str) -> str:
    return doc_id.removeprefix("docs/")             # public docs are cited by slug, as in R2


def _best_line(text: str, question: str) -> str:
    """The prose line sharing the most words with the question: a stand-in for a real answer."""
    want = set(WORD.findall(question.lower()))
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and ln.lstrip()[0] not in "-#|`>"]
    return max(lines, key=lambda ln: len(want & set(WORD.findall(ln.lower()))), default="")[:200]
```

```python
# script_id: day_089_capstone_r5_integrate/atlas/stubs
def stub_services() -> AtlasServices:
    corpus, issues = load_corpus(), load_open_issues()   # Day 83's toy tenants, Day 78's open issues

    async def ask(question: str, *, groups: tuple[str, ...], llm: ResilientLLM, effort: str,
                  max_output_tokens: int, prompt_version: str) -> AskOutcome:
        docs = search(corpus, question, groups)          # the tenant filter runs BEFORE ranking
        prompt = "\n\n".join(d.text[:2000] for d in docs) + f"\n\nQuestion: {question}"
        resp, meta = await llm.create(input=prompt, max_output_tokens=max_output_tokens)
        cites = [Citation(doc_id=_cite_id(d.doc_id), quote=_best_line(d.text, question)) for d in docs[:2]]
        text = f"[{resp.model}, prompt {prompt_version}] " + (cites[0].quote if cites else "I don't know.")
        return AskOutcome(Answer(text=text, citations=cites), [_cite_id(d.doc_id) for d in docs], meta,
                          count_tokens(prompt), count_tokens(text))

    async def triage(issue_id: int) -> dict:
        if issue_id not in issues:
            raise HTTPException(404, "not found")
        return rules_triage(issues[issue_id]).model_dump()   # Day 78's rules: proposes, applies nothing
```

```python
# script_id: day_089_capstone_r5_integrate/atlas/stubs
    # (stub_services continues)
    async def investigate(issue_id: int) -> AsyncIterator[AgentEvent]:
        issue = issues.get(issue_id)
        if issue is None:
            yield AgentEvent(type="error", data={"code": "not_found"})
            return
        words = set(WORD.findall(issue["title"].lower()))
        yield AgentEvent(type="tool_call", data={"name": "search_issues", "args": {"query": issue["title"]}})
        similar = sorted((i for i in issues.values() if i["id"] != issue_id), reverse=True,
                         key=lambda i: len(words & set(WORD.findall(i["title"].lower()))))[:2]
        yield AgentEvent(type="tool_result", data={"name": "search_issues", "chars": len(json.dumps(similar))})
        yield to_ui_event("DuplicateCandidates", json.dumps({"issue_id": issue_id, "candidates": [
            {"issue_id": i["id"], "title": i["title"][:120], "confidence": "low",
             "reason": "shared title words (stub)"} for i in similar]}))     # a Day 80 card
        for d in search(corpus, issue["title"], ("public",))[:2]:
            yield AgentEvent(type="citation", data={"doc_id": _cite_id(d.doc_id)})
        yield AgentEvent(type="final", data={"text": f"Stub diagnosis for #{issue_id}: {issue['title']}",
                                             "usage": {"input_tokens": count_tokens(issue["body"]),
                                                       "output_tokens": 60}})

    return AtlasServices("stub", ask, investigate, triage)
```

```mermaid
sequenceDiagram
  participant UI as Gradio UI
  participant API as POST /v1/investigate/stream
  participant P as pipeline
  participant A as adapter
  participant G as R3 graph
  UI->>API: issue_id + Bearer key
  API->>P: dependency: auth, guards, reserve, stream slot
  P-->>API: Ticket (or 401/413/429 before any byte)
  API->>A: services.investigate(issue_id)
  A->>G: astream(stream_mode="updates")
  G-->>A: {"agent": ...}, {"tools": ...}, {"diagnose": ...}
  A-->>API: AgentEvents: tool_call, tool_result, citation, final
  API-->>UI: SSE events, then done
  Note over P: finally: settle tokens, release slot, write one event row
```

## The Pipeline

This is the day's core idea: one request path, in a fixed order, for every route. Exits before the cache cost nothing; the model call is the first stage that spends money.

```mermaid
flowchart TD
  A["request id + body limit"] -->|"too big"| E1["413 / 411"]
  A --> B["auth: key to Principal"]
  B -->|"bad key"| E2["401 / 403"]
  B --> C["kill switches (D88)"]
  C -->|"route paused"| E3["503"]
  C --> D["input cap, then rate limit (D83)"]
  D -->|"over"| E4["413 / 429 + Retry-After"]
  D --> F["tenant-scoped cache (D85)"]
  F -->|"hit"| OK1["200 cached, $0"]
  F --> G["reserve tokens (D83)"]
  G -->|"daily quota"| E5["429"]
  G --> H["route model (D85)"]
  H --> I["ResilientLLM (D84)"]
  I -->|"primary down"| OK2["200 fallback=true"]
  I -->|"all down"| OK3["200 degraded=true"]
  I --> J["settle + event row + online checks"]
```

A `Ticket` is what the guards hand to a handler. It carries a `RequestEvent` that each stage fills in, so `finish()` writes exactly one row per request.

```python
# script_id: day_089_capstone_r5_integrate/atlas/api/pipeline
# atlas/api/pipeline.py: ONE request path for every route, in a fixed order (see the diagram).
# No key needed with ATLAS_BACKEND=stub. Every stage reuses the day that built it.
from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import anyio
from fastapi import BackgroundTasks, HTTPException

from atlas.api.auth import Principal
from atlas.api.deps import Deps
from atlas.api.events import AgentEvent
from atlas.api.models import AskRequest, AskResponse, InvestigateRequest
from atlas.cache import cache_scope, detect_version
from atlas.flags import resolve_prompt
from atlas.model_router import choose_model, cost_usd
from atlas.monitoring import Answer as CheckedAnswer, RequestEvent, score_request
from atlas.ops import get_overrides, plan_request
from atlas.quotas import PLANS, PlanLimits, QuotaExceeded, Reservation, count_tokens
from atlas.resilience import AllModelsUnavailable, degraded_answer, keyword_search
from atlas.tenancy import tenant_key, visible_tenants
from atlas.tracing import step_span

CONTEXT_TOKENS = 1_500              # retrieved sources: Day 83's estimate
INVESTIGATE_TOKENS = 20_000         # flat reservation per agent run, settled to real usage
EFFORTS = ["none", "low", "medium", "high"]


class AskResult(AskResponse):
    """Day 77's response plus the flags that tests, dashboards and the UI read."""
    model: str
    variant: str = "control"
    cached: bool = False
    fallback: bool = False
    degraded: bool = False
```

```python
# script_id: day_089_capstone_r5_integrate/atlas/api/pipeline
@dataclass
class Ticket:
    """What the guards hand to a handler. `ev` is filled in stage by stage and written once."""
    principal: Principal
    route: str
    limits: PlanLimits
    input_tokens: int
    ev: RequestEvent
    mode: str = "full"                                  # Day 88: "full" | "retrieval_only"
    force_fallback: bool = False
    background: BackgroundTasks | None = None
    reservation: Reservation | None = None
    stream_key: str | None = None
    check: tuple | None = None                          # (CheckedAnswer, hits, question) for Day 86
    started: float = field(default_factory=time.perf_counter)


def hour_key(p: Principal) -> str:                      # feeds Day 88's per-tenant hourly caps
    return tenant_key(p, "tokens_h", time.strftime("%Y%m%d%H", time.gmtime()))


async def guard(p: Principal, route: str, text: str, deps: Deps, *, request_id: str,
                background: BackgroundTasks | None = None) -> Ticket:
    """Stages 4-6: kill switches, input cap, rate limit. Cheapest first; any of them can say no."""
    with step_span("guard", "pipeline", **{"atlas.tenant": p.tenant_id, "atlas.route": route}):
        used = int(await deps.redis.get(hour_key(p)) or 0)
        ov = get_overrides(deps.ops_redis)              # sync, but read at most every 5 s (Day 88)
        plan = plan_request(route, p.tenant_id, ov, tokens_this_hour=used)
        if plan.status == 202:                          # queue mode: R5.0 has no queued ask path
            raise HTTPException(503, plan.message, headers={"Retry-After": "30"})
        if plan.status >= 400:
            raise HTTPException(plan.status, plan.message)
        limits, n_in = PLANS[p.plan], count_tokens(text)
        if n_in > limits.max_input_tokens:
            raise QuotaExceeded("input_too_large")      # 413 before Redis or a model is touched
        rate = await deps.limiter.hit(tenant_key(p, "rpm"), limits.rpm)
        if not rate.allowed:
            raise QuotaExceeded("rate_limited", rate.retry_after_s)   # 429 + Retry-After
    ev = RequestEvent(request_id=request_id, ts=time.time(), tenant_id=p.tenant_id, route=route,
                      model="none", status=200, latency_ms=0.0)
    return Ticket(p, route, limits, n_in, ev, plan.mode, plan.force_fallback, background)
```

Streams are the exception to "reserve after the cache": an SSE route sends `200` with its first event, so everything that can say no runs in the route's dependency (Day 83's rule). Streams reserve first, and a cache hit settles to zero, refunding it.

```python
# script_id: day_089_capstone_r5_integrate/atlas/api/pipeline
async def reserve_stream(t: Ticket, deps: Deps) -> None:
    """Streams must say no BEFORE the 200 goes out, so they reserve inside the route dependency."""
    out = t.limits.max_output_tokens
    est = INVESTIGATE_TOKENS if t.route == "investigate" else t.input_tokens + CONTEXT_TOKENS + out
    t.reservation = await deps.quotas.reserve(t.principal, est)
    try:
        t.stream_key = await deps.quotas.acquire_stream(t.principal)
    except QuotaExceeded:
        await deps.quotas.settle(t.reservation, 0)      # hand the tokens back
        raise


async def answer(t: Ticket, question: str, deps: Deps) -> AskResult:
    """Stages 7-10: cache, reserve, route, resilient call. Fills t.ev as it goes."""
    p, ev, out = t.principal, t.ev, t.limits.max_output_tokens
    prompt_v, ev.variant = resolve_prompt("ask", p, deps.release.get(), user_id=p.key_id)   # Day 87
    route = choose_model(question, plan=p.plan)                                              # Day 85
    fallbacks = deps.settings.fallback_models
    model = fallbacks[0] if t.force_fallback and fallbacks else route.model                 # Day 88 lever
    scope = cache_scope(p, model=model, prompt_version=prompt_v, index_version=deps.settings.index_version)
    scope += f":orbit={detect_version(question)}"           # as Day 85's cached_ask() does
    with step_span("cache", "pipeline"):
        hit = await asyncio.to_thread(deps.cache.lookup, scope, question)   # embedding may be a network call
    if hit:
        ev.model, ev.cached, ev.citations = model, True, len(hit.answer.citations)
        return AskResult(answer=hit.answer, usage={}, request_id=ev.request_id, model=model,
                         variant=ev.variant, cached=True)
    if t.reservation is None:                               # JSON routes reserve only on a miss
        t.reservation = await deps.quotas.reserve(p, t.input_tokens + CONTEXT_TOKENS + out)
    try:
        if t.mode == "retrieval_only":                      # Day 88's lever takes the outage path
            raise AllModelsUnavailable([], 0)
        with step_span("generate", "llm", **{"atlas.model": model}):
            o = await deps.services.ask(question, groups=visible_tenants(p), prompt_version=prompt_v,
                                        llm=deps.llms.get(model, deps.llms[deps.settings.model]),
                                        effort=min(route.effort, t.limits.effort, key=EFFORTS.index),
                                        max_output_tokens=out)
    except AllModelsUnavailable:                            # Day 84: cited links, no generation
        d = degraded_answer(question, keyword_search(question, deps.chunks))
        ev.fallback = ev.degraded = True
        ev.citations = len(d.citations)
        return AskResult(answer=d.model_dump(include={"text", "citations"}), usage={}, model="none",
                         request_id=ev.request_id, variant=ev.variant, fallback=True, degraded=True)
```

```python
# script_id: day_089_capstone_r5_integrate/atlas/api/pipeline
    # (answer continues: a model answered)
    ev.model, ev.fallback, ev.citations = o.meta.model, o.meta.fallback, len(o.answer.citations)
    ev.input_tokens, ev.output_tokens = o.input_tokens, o.output_tokens
    ev.cost_usd = cost_usd(o.meta.model, o.input_tokens, o.output_tokens)   # real usage x Day 85 prices
    t.check = (CheckedAnswer(o.answer.text, [c.doc_id for c in o.answer.citations]), o.hits, question)
    if o.answer.citations and not o.meta.fallback:          # cache only healthy, cited answers
        await asyncio.to_thread(deps.cache.store, scope, question, o.answer)
    usage = {"input_tokens": o.input_tokens, "output_tokens": o.output_tokens, "cost_usd": ev.cost_usd}
    return AskResult(answer=o.answer, usage=usage, request_id=ev.request_id, model=o.meta.model,
                     variant=ev.variant, fallback=o.meta.fallback)


async def finish(t: Ticket, deps: Deps, *, status: int) -> None:
    """Stages 11-12. Always runs (call it from `finally`): settle tokens, then write ONE event row."""
    used = t.ev.input_tokens + t.ev.output_tokens
    with anyio.CancelScope(shield=True):                    # a cancelled request still settles (Day 83)
        if t.reservation:
            await deps.quotas.settle(t.reservation, used)
            await deps.redis.incrby(hour_key(t.principal), used)
            await deps.redis.expire(hour_key(t.principal), 7_200)
        if t.stream_key:
            await deps.quotas.release_stream(t.stream_key)
    t.ev.status, t.ev.latency_ms = status, round((time.perf_counter() - t.started) * 1000, 1)
    deps.events.record(t.ev)                                # metrics only: no question or answer text
    if t.check and t.background is not None and status == 200:
        t.background.add_task(score_request, deps.events, t.ev, *t.check)   # Day 86, after the response


async def handle_ask(t: Ticket, req: AskRequest, deps: Deps) -> AskResult:
    status = 500
    try:
        result = await answer(t, req.question, deps)
        status = 200
        return result
    except HTTPException as exc:
        status = exc.status_code
        raise
    except QuotaExceeded:
        status = 429
        raise
    finally:
        await finish(t, deps, status=status)
```

The streaming variant reuses `answer()` and the service's event stream, and ends in the same `finish()`. A disconnect is recorded as 499, so it doesn't count as an outage on Day 86's dashboard.

```python
# script_id: day_089_capstone_r5_integrate/atlas/api/pipeline
async def handle_stream(t: Ticket, req: AskRequest | InvestigateRequest,
                        deps: Deps) -> AsyncIterator[AgentEvent]:
    """Stages 7-12 for SSE routes. Auth, guards and the reservation already ran in the dependency."""
    status = 500
    try:
        if isinstance(req, AskRequest):
            r = await answer(t, req.question, deps)
            if t.check:
                yield AgentEvent(type="status", data={"step": "retrieved", "doc_ids": t.check[1]})
            yield AgentEvent(type="token", data={"text": r.answer.text})   # one chunk: see Go Deeper
            for c in r.answer.citations:
                yield AgentEvent(type="citation", data={"doc_id": c.doc_id})
            yield AgentEvent(type="final", data=r.model_dump(
                include={"request_id", "model", "cached", "fallback", "degraded"}))
        else:
            async for e in deps.services.investigate(req.issue_id):
                if e.type == "final":                       # the run's real usage, priced like ask
                    u, t.ev.model = e.data.get("usage") or {}, deps.settings.model   # R3 runs on ATLAS_MODEL
                    t.ev.input_tokens, t.ev.output_tokens = u.get("input_tokens", 0), u.get("output_tokens", 0)
                    t.ev.cost_usd = cost_usd(t.ev.model, t.ev.input_tokens, t.ev.output_tokens)
                    e = e.model_copy(update={"data": {**e.data, "request_id": t.ev.request_id}})
                elif e.type == "citation":
                    t.ev.citations += 1
                yield e
        status = 200
    except (GeneratorExit, asyncio.CancelledError):
        status = 499                                        # the client left: not an outage
        raise
    finally:
        await finish(t, deps, status=status)
```

## Wiring the App

`create_app(settings)` connects everything and fixes the old capstone's three bugs: a hard-coded API URL (now `ATLAS_API_URL`), a content-length cost heuristic (now real `usage`) and no tracing (now a span per stage). Middleware runs outermost first: request id, then CORS (so rejections still carry headers a browser can read), then the body limit. FastAPI has no built-in body cap, so `BodyLimit` is a small pure ASGI middleware, which never buffers an SSE stream.

```python
# script_id: day_089_capstone_r5_integrate/atlas/api/app
# atlas/api/app.py: create_app(settings) wires middleware, routes and the composition root.
# Run: ATLAS_BACKEND=stub ATLAS_REDIS_URL=fake:// uv run uvicorn atlas.api.app:create_app --factory --port 8000
# Install: uv add "fastapi>=0.162" uvicorn "redis>=8.1" fakeredis   Services: Redis (or fake://)
# No `from __future__ import annotations` here: FastAPI must see the Depends() inside closures.
import asyncio
import re
import uuid
from collections.abc import AsyncIterable, AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent

MAX_BODY_BYTES = 64_000                  # JSON bodies only; AskRequest caps a question at 2,000 chars
_RID = re.compile(r"[A-Za-z0-9-]{8,64}")


class RequestContext:
    """Give every request an id before anything else runs (a caller's valid X-Request-Id is kept)."""
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "http":
            sent = dict(scope["headers"]).get(b"x-request-id", b"").decode()
            scope.setdefault("state", {})["request_id"] = sent if _RID.fullmatch(sent) else uuid.uuid4().hex
        await self.app(scope, receive, send)


class BodyLimit:
    """413 for big bodies, 411 when a POST has no Content-Length. Runs before any JSON parsing."""
    def __init__(self, app, max_bytes: int = MAX_BODY_BYTES) -> None:
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "http" and scope["method"] in ("POST", "PUT", "PATCH"):
            raw = dict(scope["headers"]).get(b"content-length")
            status = 411 if raw is None else 413 if not raw.isdigit() or int(raw) > self.max_bytes else 0
            if status:
                body = {"error": "length_required" if status == 411 else "body_too_large"}
                await JSONResponse(body, status_code=status)(scope, receive, send)
                return
        await self.app(scope, receive, send)
```

```python
# script_id: day_089_capstone_r5_integrate/atlas/api/app
from atlas.api.auth import Principal, require_principal, require_scope
from atlas.api.deps import Deps, build_deps
from atlas.api.pipeline import Ticket, guard, reserve_stream
from atlas.config import Settings
from atlas.feedback import feedback_router
from atlas.quotas import QuotaExceeded
from atlas.tracing import setup_tracing


async def on_quota(request: Request, exc: QuotaExceeded) -> JSONResponse:    # Day 83's mapping
    headers = {"Retry-After": str(exc.retry_after_s)} if exc.retry_after_s else {}
    return JSONResponse({"error": exc.code, "retry_after_s": exc.retry_after_s},
                        status_code=413 if exc.code == "input_too_large" else 429, headers=headers)


def admitted(route: str, *, stream: bool = False):
    """Dependency factory: auth, guards and (for streams) the reservation, BEFORE any byte is sent."""
    async def dep(request: Request, background: BackgroundTasks,
                  p: Annotated[Principal, Depends(require_scope(route))]) -> Ticket:
        deps: Deps = request.app.state.deps
        raw = (await request.body()).decode()           # cap the raw JSON: covers every body shape
        t = await guard(p, route, raw, deps, request_id=request.state.request_id, background=background)
        if stream:
            await reserve_stream(t, deps)
        return t
    return dep


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()          # ConfigError lists every problem, at boot

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if settings.phoenix_endpoint:
            setup_tracing("atlas", endpoint=settings.phoenix_endpoint)   # Day 42 (endpoint is keyword-only)
        app.state.deps = deps = build_deps(settings)
        app.state.keys = deps.keys                      # Day 83's require_principal reads this
        app.include_router(feedback_router(deps.events, require_principal))   # Day 86 needs the log
        yield
        await deps.redis.aclose()
        if deps.client is not None:
            await deps.client.close()

    app = FastAPI(title="Atlas", version=settings.release, lifespan=lifespan)
    app.add_exception_handler(QuotaExceeded, on_quota)
    app.add_middleware(BodyLimit)                       # added first = innermost
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.allowed_origins),
                       allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])
    app.add_middleware(RequestContext)                  # added last = outermost: runs first
    add_routes(app)
    return app
```

Every model-calling route takes a `Ticket` from `admitted()`, so none can skip the guards (the old capstone's `/stream` had no rate limit). Day 86's `/v1/feedback` needs only `require_principal`. Readiness checks Redis, Postgres and the index version, never the model: a provider outage should degrade answers, not pull every replica out of the load balancer.

```python
# script_id: day_089_capstone_r5_integrate/atlas/api/app
from atlas.api.events import sse_stream
from atlas.api.models import AskRequest, InvestigateRequest, TriageRequest
from atlas.api.pipeline import AskResult, finish, handle_ask, handle_stream
from atlas.ops import get_overrides


def add_routes(app: FastAPI) -> None:
    @app.post("/v1/ask")
    async def ask(body: AskRequest, request: Request,
                  t: Annotated[Ticket, Depends(admitted("ask"))]) -> AskResult:
        return await handle_ask(t, body, request.app.state.deps)

    @app.post("/v1/ask/stream", response_class=EventSourceResponse)
    async def ask_stream(body: AskRequest, request: Request,
                         t: Annotated[Ticket, Depends(admitted("ask", stream=True))]
                         ) -> AsyncIterable[ServerSentEvent]:
        async for sse in sse_stream(handle_stream(t, body, request.app.state.deps), request, timeout_s=60):
            yield sse

    @app.post("/v1/investigate/stream", response_class=EventSourceResponse)
    async def investigate(body: InvestigateRequest, request: Request,
                          t: Annotated[Ticket, Depends(admitted("investigate", stream=True))]
                          ) -> AsyncIterable[ServerSentEvent]:
        async for sse in sse_stream(handle_stream(t, body, request.app.state.deps), request, timeout_s=120):
            yield sse

    @app.post("/v1/triage")
    async def triage(body: TriageRequest, request: Request,
                     t: Annotated[Ticket, Depends(admitted("triage"))]) -> dict:
        status = 500
        try:
            proposal = await request.app.state.deps.services.triage(body.issue_id)
            status = 200
            return proposal                             # proposes only: a maintainer approves (Day 76)
        except HTTPException as exc:
            status = exc.status_code
            raise
        finally:
            await finish(t, request.app.state.deps, status=status)
```

```python
# script_id: day_089_capstone_r5_integrate/atlas/api/app
    # (add_routes continues)
    @app.get("/healthz")
    async def healthz(request: Request) -> dict:       # liveness + "what is deployed?" (Day 82)
        return {"status": "ok", "release": request.app.state.deps.settings.release}

    @app.get("/readyz")
    async def readyz(request: Request) -> dict:        # local dependencies only, NEVER the model
        deps: Deps = request.app.state.deps
        ov = get_overrides(deps.ops_redis)
        checks = {"redis": await _redis_ok(deps.redis),
                  "postgres": await asyncio.to_thread(_postgres_ok, deps.settings.database_url),
                  "index": ov.index_version in (None, deps.settings.index_version) and bool(deps.chunks)}
        if not all(checks.values()):
            raise HTTPException(503, detail=checks)
        return {"status": "ready", "backend": deps.services.name, "checks": checks}


async def _redis_ok(redis) -> bool:
    try:
        return bool(await redis.ping())
    except Exception:                                   # readiness reports problems; it never raises
        return False


def _postgres_ok(url: str | None) -> bool:
    if url is None:
        return True                                     # not configured: stub backend or memory index
    try:
        import psycopg
        with psycopg.connect(url, connect_timeout=2) as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False
```

During Day 88's migration, a replica configured for index `v1` while the override points reads at `v2` reports not ready, so it can't serve answers keyed to the wrong index.

## The UI, Connected

R5's UI adds a per-session API key field, Day 80's cards for `component` events, and Helpful/Wrong buttons that post to `/v1/feedback` with the last `request_id`. The key goes out only in the `Authorization` header; the UI server never stores it. Voice (Day 81) stays off, behind a flag, until you need it.

```python
# script_id: day_089_capstone_r5_integrate/atlas/ui/main
# atlas/ui/main.py: Day 79's chat, connected to R5: per-session API key, Day 80 cards, Day 86 feedback.
# Install: uv add "gradio>=6.31" httpx2   Env: ATLAS_API_URL (http://api:8000 in compose)
# Run: uv run python -m atlas.ui.main   (Day 79's atlas/ui/app.py stays as is; this file adds the wiring)
from __future__ import annotations

import os
from collections.abc import Iterator

import gradio as gr
import httpx2

from atlas.ui.app import AgentEvent, _route, iter_sse, to_messages
from atlas.ui.components import render_html

API_URL = os.environ.get("ATLAS_API_URL", "http://localhost:8000")   # from env, never hard-coded


def chat_fn(message: str, history: list, api_key: str) -> Iterator[tuple[list[gr.ChatMessage], str]]:
    path, body = _route(message)                    # "#209" investigates; anything else asks
    events, cards, request_id = [], [], ""
    headers = {"Authorization": f"Bearer {api_key.strip()}"}
    try:
        with httpx2.stream("POST", API_URL + path, json=body, headers=headers,
                           timeout=httpx2.Timeout(10.0, read=130.0)) as r:   # > the 120 s agent deadline
            r.raise_for_status()
            for e in iter_sse(r.iter_lines()):
                if e.type == "component":           # validated again, then filled into a fixed template
                    cards.append(gr.ChatMessage(content=render_html(e.data["name"], e.data["props"])))
                    continue
                request_id = e.data.get("request_id", request_id)
                events.append(e)
                yield cards + to_messages(events), request_id
    except httpx2.HTTPStatusError as exc:            # 401 bad key, 429 slow down, 503 paused
        events.append(AgentEvent(type="error", data={"code": exc.response.status_code}))
    except httpx2.HTTPError as exc:
        events.append(AgentEvent(type="error", data={"code": type(exc).__name__}))
    yield cards + to_messages(events), request_id
```

```python
# script_id: day_089_capstone_r5_integrate/atlas/ui/main
def send_feedback(rating: str, api_key: str, request_id: str) -> str:
    if not request_id:
        return "Ask something first."
    r = httpx2.post(f"{API_URL}/v1/feedback", json={"request_id": request_id, "rating": rating},
                    headers={"Authorization": f"Bearer {api_key.strip()}"}, timeout=10.0)
    return "Thanks, recorded." if r.status_code == 204 else f"Feedback failed ({r.status_code})."


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="Atlas") as demo:
        api_key = gr.Textbox(label="Atlas API key", type="password", placeholder="atk_...")
        last_id = gr.State("")                      # the latest answer's request_id, per session
        gr.ChatInterface(fn=chat_fn, additional_inputs=[api_key], additional_outputs=[last_id],
                         chatbot=gr.Chatbot(height=520, sanitize_html=True, render_markdown=True),
                         description="Ask about Orbit, or type #209 to investigate an issue.")
        with gr.Row():
            helpful, wrong = gr.Button("Helpful"), gr.Button("Wrong")
        note = gr.Markdown()
        helpful.click(lambda key, rid: send_feedback("up", key, rid), [api_key, last_id], note)
        wrong.click(lambda key, rid: send_feedback("down", key, rid), [api_key, last_id], note)
    return demo


if __name__ == "__main__":
    build_ui().launch(server_name=os.environ.get("ATLAS_UI_HOST", "127.0.0.1"), server_port=7860)
```

With `additional_outputs`, `ChatInterface` expects each yield to be a tuple, chat response first, so `chat_fn` yields `(messages, request_id)`.

## Integration Tests

Days 77–88's unit tests prove each part; these eight prove the *order*. They run at the HTTP boundary on `ATLAS_BACKEND=stub` and `fake://` Redis: no key, no Docker.

```python
# script_id: day_089_capstone_r5_integrate/scripts/seed_tenants
# scripts/seed_tenants.py: create the four staging tenants and their API keys.
# Run: uv run python -m scripts.seed_tenants   Env: ATLAS_STATE_DIR (where keys.db lives)
# Raw keys go ONCE into a 0600 file; only key ids are printed, so keys never reach logs.
from __future__ import annotations

import json
import os
from pathlib import Path

from atlas.api.auth import KeyStore

TENANTS = {   # tenant -> (plan, scopes); limits per plan come from Day 83's PLANS
    "orbit-maintainers": ("team", {"ask", "investigate", "triage"}),
    "acme": ("free", {"ask", "investigate"}),
    "zephyr": ("free", {"ask", "investigate"}),
    "demo": ("demo", {"ask"}),
}


def seed_tenants(store: KeyStore) -> dict[str, str]:
    """Issue one key per tenant and return tenant -> raw key (shown nowhere else, ever)."""
    return {tenant: store.issue(tenant, plan, scopes) for tenant, (plan, scopes) in TENANTS.items()}


if __name__ == "__main__":
    state = Path(os.environ.get("ATLAS_STATE_DIR", ".atlas"))
    state.mkdir(parents=True, exist_ok=True)
    out = state / "staging_keys.json"
    keys = seed_tenants(KeyStore(str(state / "keys.db")))
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)    # owner-only, like an SSH key
    with os.fdopen(fd, "w") as f:
        json.dump(keys, f)
    for tenant, raw in keys.items():
        print(f"{tenant:18} key_id={raw.split('_')[1]}")
    print(f"raw keys -> {out} (mode 600): copy them to your secret store, then delete the file")
```

```python
# script_id: day_089_capstone_r5_integrate/tests/test_integration
# tests/test_integration.py: 8 end-to-end tests at the HTTP boundary. No key, no Docker.
# Install: uv add --dev pytest fakeredis   Run: uv run pytest tests/test_integration.py -q
from __future__ import annotations

import os
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from atlas import quotas
from atlas.api.app import create_app
from atlas.api.deps import build_pools
from atlas.config import Settings
from atlas.flags import RELEASE_TOML
from atlas.resilience import FakeAsyncClient, FaultInjector, RetryPolicy
from scripts.seed_tenants import seed_tenants

FAST = RetryPolicy(max_attempts=2, base_s=0.01, cap_s=0.02)     # tests shouldn't sleep for real


@pytest.fixture
def api(tmp_path, monkeypatch):
    (tmp_path / "release.toml").write_text(RELEASE_TOML)         # Day 87: prompt.ask v3 -> v4 at 10%
    settings = Settings.from_env({"ATLAS_BACKEND": "stub", "ATLAS_REDIS_URL": "fake://",
                                  "ATLAS_STATE_DIR": str(tmp_path),
                                  "ATLAS_RELEASE_FILE": str(tmp_path / "release.toml"),
                                  "ORBIT_DATA": os.environ.get("ORBIT_DATA", "datasets/orbit")})
    monkeypatch.setattr(quotas, "time", SimpleNamespace(time=lambda: 1_800_000_000.0))  # one rate window
    with TestClient(create_app(settings)) as client:
        client.keys = seed_tenants(client.app.state.deps.keys)
        yield client


def ask(c: TestClient, tenant: str | None, q: str = "How do retries back off?", path: str = "/v1/ask"):
    headers = {"Authorization": f"Bearer {c.keys[tenant]}"} if tenant else {}
    return c.post(path, json={"question": q}, headers=headers)
```

```python
# script_id: day_089_capstone_r5_integrate/tests/test_integration
def test_1_no_key_is_401(api):
    assert ask(api, None).status_code == 401
    assert api.post("/v1/ask", json={"question": "x"}, headers={"Authorization": "Bearer atk_x_y"}).status_code == 401


def test_2_tenants_are_isolated(api):
    q = "What lease_seconds do we use for the nightly ETL queue?"
    mine = ask(api, "acme", q).json()
    theirs = ask(api, "zephyr", q).json()
    assert any(c["doc_id"] == "acme/runbook" for c in mine["answer"]["citations"])
    assert all(not c["doc_id"].startswith("acme/") for c in theirs["answer"]["citations"])
    assert "900" not in theirs["answer"]["text"]                  # Acme's private value
    r = api.post("/v1/feedback", json={"request_id": mine["request_id"], "rating": "down"},
                 headers={"Authorization": f"Bearer {api.keys['zephyr']}"})
    assert r.status_code == 404                                   # a foreign id looks like no id


def test_3_rate_limit_61st_request(api):
    codes = [ask(api, "acme").status_code for _ in range(61)]     # free plan: 60 requests/minute
    assert codes[:60] == [200] * 60 and codes[60] == 429
    assert int(ask(api, "acme").headers["Retry-After"]) > 0


def test_4_cache_hits_are_per_tenant(api):
    q = "How do I fix ORB-1101 errors?"
    assert ask(api, "acme", q).json()["cached"] is False
    assert ask(api, "acme", q).json()["cached"] is True
    assert ask(api, "zephyr", q).json()["cached"] is False        # same words, other tenant: miss
```

```python
# script_id: day_089_capstone_r5_integrate/tests/test_integration
def test_5_fallback_then_degraded(api):
    deps = api.app.state.deps
    deps.llms, deps.breakers = build_pools(FakeAsyncClient(FaultInjector({}, down={"gpt-6-luna"})),
                                           list(deps.llms), policy=FAST)
    body = ask(api, "acme", "How do workers send heartbeats?").json()
    assert body["fallback"] is True and body["model"] == "gpt-6.1-terra"
    deps.llms, deps.breakers = build_pools(FakeAsyncClient(FaultInjector({}, down=set(deps.llms))),
                                           list(deps.llms), policy=FAST)
    r = ask(api, "acme", "How does the dead letter queue work?")
    assert r.status_code == 200 and r.json()["degraded"] is True   # an answer, never a 500


def test_6_sse_has_citations_and_ends_with_done(api):
    r = ask(api, "acme", path="/v1/ask/stream")
    names = [line.removeprefix("event: ") for line in r.text.splitlines() if line.startswith("event: ")]
    assert r.status_code == 200 and "citation" in names and names[-1] == "done"


def test_7_canary_bucket_is_stable(api):
    for q in ["How do retries back off?", "What is a lease?", "How do I pause a queue?"]:
        assert ask(api, "zephyr", q).status_code == 200
    variants = {e.variant for e in api.app.state.deps.events.window(5, tenant_id="zephyr")}
    assert len(variants) == 1                                     # one user, one variant, every time


def test_8_one_event_row_per_request(api):
    ids = [ask(api, "zephyr", q).json()["request_id"] for q in ["What is Orbit?", "What is a flow?"]]
    ids.append(ask(api, "zephyr", "What is Orbit?").json()["request_id"])   # a cache hit
    rows = api.app.state.deps.events.window(5, tenant_id="zephyr")
    assert sorted(e.request_id for e in rows) == sorted(ids)
    assert [e.cost_usd > 0 for e in sorted(rows, key=lambda e: e.ts)] == [True, True, False]
```

```text
$ uv run pytest tests/test_integration.py -q
........                                                                 [100%]
8 passed in 1.2s            (your timing will differ)
```

Test 2 failing points at `search()` or `cache_scope()`, test 3 at a route that skipped `admitted()`, test 8 at a `return` that bypassed `finish()`.

## The Hardening Checklist

A **hardening checklist** lists each production rule, where it's enforced and what proves it. A rule with no proof is a hope. Rows map to the OWASP Top 10 for LLM Applications (2025) where one applies, for example LLM02 Sensitive Information Disclosure and LLM10 Unbounded Consumption ([Day 68](../../Phase_8_Safety_and_Security/Day_068_threat_modeling/threat_modeling.md)).

| Rule | Where it's enforced | What proves it |
|---|---|---|
| Timeouts on every hop, each longer than the one it wraps: OpenAI 30 s per attempt, SSE 60 s (ask) / 120 s (investigate), UI read 130 s | `build_deps`, `add_routes`, `ui/main.py` | test 6 ends with `done`; staging replay p95 |
| Body caps: 411/413 at the door, 413 `input_too_large` per plan | `BodyLimit`, `guard()` | `smoke_staging` and a curl check (add a test as practice) |
| CORS allow-list; `*` refused outside dev | `CORSMiddleware`, `Settings.from_env` | Day 82's config tests (add a staging case) |
| `store=False` on ask; documented exception: Day 78's background jobs keep data about 10 minutes for polling ([Day 73](../../Phase_8_Safety_and_Security/Day_073_privacy_pii/privacy_pii.md)) | reference `ask()` | code review + `grep -rn "store=" atlas/` |
| Log metrics, never content: event rows hold ids, tokens and flags only | `RequestEvent` | test 8 (inspect a row) |
| Secrets only from the environment; raw keys never printed | `Settings`, `seed_tenants` | Day 82 tests; `git grep atk_` is empty |
| Prompt versions come from `release.toml`, not code | `resolve_prompt` in `answer()` | test 7 |
| One retry layer | `AsyncOpenAI(max_retries=0)` + `ResilientLLM` | test 5 (fallback after the primary's attempts) |
| Fallback models pass the eval suite too | CI `eval` job with `ATLAS_MODEL=gpt-6.1-terra` | Day 47 gate |
| Red-team fast suite on every PR ([Day 75](../../Phase_8_Safety_and_Security/Day_075_red_teaming_ci/red_teaming_ci.md)) | `deploy.yml` `redteam` job | CI |
| Readiness never calls the model | `/readyz` | `smoke_staging` with the provider blocked |
| Graceful shutdown drains streams | `uvicorn --timeout-graceful-shutdown 130` | rolling deploy during the replay: no 5xx |

## Deploy to Staging

**Staging** is a production-like environment where you prove the deploy before real users arrive. Run compose locally first, then push the same image through Day 82's pipeline. Only changes from Day 82's files are shown.

```yaml
# file: compose.yaml  (changes from Day 82: R5 commands, state volume, Postgres; api/ui healthchecks unchanged)
x-atlas: &atlas
  image: ${ATLAS_IMAGE:-atlas}:${ATLAS_TAG:-dev}
  env_file: ${ATLAS_ENV_FILE:-.env}
  environment:
    ATLAS_ENV: ${ATLAS_ENV:-staging}
    ATLAS_BACKEND: ${ATLAS_BACKEND:-stub}               # reference once R2-R4 + Postgres are in place
    ATLAS_REDIS_URL: redis://redis:6379/0
    ATLAS_DATABASE_URL: postgresql://atlas:atlas@postgres:5432/atlas
    ATLAS_API_URL: http://api:8000
    ATLAS_STATE_DIR: /app/state
    GRADIO_SERVER_NAME: 0.0.0.0
  volumes: [atlas-state:/app/state]
  restart: unless-stopped

services:
  api:
    <<: *atlas
    command: ["uvicorn", "atlas.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000",
              "--timeout-graceful-shutdown", "130"]
    depends_on:
      redis: { condition: service_healthy }
      postgres: { condition: service_healthy }
  ui:
    <<: *atlas
    command: ["python", "-m", "atlas.ui.main"]
    environment: { ATLAS_UI_HOST: 0.0.0.0, ATLAS_API_URL: http://api:8000 }
  postgres:
    image: pgvector/pgvector:0.8.7-pg18-trixie
    environment: { POSTGRES_USER: atlas, POSTGRES_PASSWORD: atlas, POSTGRES_DB: atlas }
    healthcheck: { test: ["CMD", "pg_isready", "-U", "atlas"], interval: 5s, timeout: 3s, retries: 10 }
    volumes: [pg-data:/var/lib/postgresql]              # PG 18 images moved the data path
  # redis and worker: unchanged from Day 82

volumes: { atlas-state: {}, pg-data: {}, redis-data: {}, atlas-logs: {} }
```

The `ui` service's own `environment` replaces the anchor's map, so it repeats `ATLAS_API_URL`. Phoenix stays on your laptop (`phoenix serve`, Day 42): point `ATLAS_PHOENIX_ENDPOINT` at it locally, or leave it unset on staging.

Day 82's pipeline gains two jobs before `build`, so a cross-tenant leak or a red-team regression blocks the image:

```yaml
# file: .github/workflows/deploy.yml  (add next to Day 82's `test` job; `build` now needs all three)
  integration:
    needs: test
    runs-on: ubuntu-latest
    env: { ATLAS_BACKEND: stub, ATLAS_REDIS_URL: "fake://" }
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/setup-uv@v10.3.3
        with: { enable-cache: true }
      - run: uv sync --locked --all-extras --dev
      - run: uv run pytest tests/test_integration.py -q
  redteam:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/setup-uv@v10.3.3
        with: { enable-cache: true }
      - run: uv sync --locked --all-extras --dev
      - run: uv run pytest tests/security -m "not docker"    # Day 75's fast suite
  # build:  needs: [eval, integration, redteam]
```

After `deploy-staging`, seed the tenants once and run `smoke_staging`: Day 82's smoke per tenant, then three multi-tenant checks (no key → 401, Zephyr can't see Acme's runbook, the stream ends with `done`). `--replay 600` adds Day 86's replay across all four tenants at 1 request/s, about 10 minutes.

```python
# script_id: day_089_capstone_r5_integrate/scripts/smoke_staging
# scripts/smoke_staging.py: Day 82's smoke per tenant + the multi-tenant checks + Day 86's replay.
# Run: uv run python -m scripts.smoke_staging https://staging.example [--replay 600]   Stdlib + atlas.
# Needs the API running and $ATLAS_STATE_DIR/staging_keys.json from scripts.seed_tenants.
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from scripts.smoke_test import smoke          # Day 82: /healthz, /readyz, a cited canary answer

LEAK_PROBE = "What lease_seconds do we use for the nightly ETL queue?"   # only Acme's runbook says


def post(url: str, body: dict, key: str | None) -> tuple[int, str]:
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as err:     # 4xx/5xx still carry a body
        return err.code, err.read().decode()
```

```python
# script_id: day_089_capstone_r5_integrate/scripts/smoke_staging
def staging_checks(base: str, keys: dict[str, str]) -> list[str]:
    failures = [f"smoke failed for {t}" for t, k in keys.items() if not smoke(base, api_key=k)]
    if post(f"{base}/v1/ask", {"question": "hi"}, None)[0] != 401:
        failures.append("a request with no key did not get 401")
    status, text = post(f"{base}/v1/ask", {"question": LEAK_PROBE}, keys["zephyr"])
    if status != 200 or "acme/" in text:
        failures.append(f"isolation: zephyr got {status} or saw Acme's data")
    status, text = post(f"{base}/v1/ask/stream", {"question": "How do retries back off?"}, keys["acme"])
    names = [ln.removeprefix("event: ") for ln in text.splitlines() if ln.startswith("event: ")]
    if status != 200 or names[-1:] != ["done"]:
        failures.append(f"stream: status {status}, last event {names[-1:]}")
    return failures


if __name__ == "__main__":
    base = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("ATLAS_API_URL", "http://localhost:8000")).rstrip("/")
    keys = json.loads((Path(os.environ.get("ATLAS_STATE_DIR", ".atlas")) / "staging_keys.json").read_text())
    failures = staging_checks(base, keys)
    print("\n".join(failures) or "staging checks OK")
    if "--replay" in sys.argv and not failures:
        from scripts.replay_traffic import replay_traffic      # Day 86
        n = int(sys.argv[sys.argv.index("--replay") + 1])
        print(replay_traffic(base, keys=keys, n=n, rps=1.0))   # 600 requests ~ 10 minutes
    sys.exit(1 if failures else 0)
```

```text
smoke OK release=3f2c1ab citations=2          (once per tenant)
staging checks OK
ReplayReport(sent=600, ok=..., errors=..., p50_ms=..., p95_ms=...)    (your numbers will differ)
```

```mermaid
flowchart LR
  PR["pull request"] --> T["test + integration + redteam"]
  T --> EV["eval gate (D47)"]
  EV --> B["build image, tag = git sha"]
  B --> D["deploy-staging (D82)"]
  subgraph STG["staging"]
    API2["api: /healthz /readyz"] --- R2[("redis")]
    API2 --- P2[("postgres + pgvector")]
    UI2["ui"] --> API2
    W2["worker"] --- R2
  end
  D --> STG
  D --> S["seed_tenants, then smoke_staging --replay 600"]
  S --> REP["STAGING_REPORT.md"]
```

While the replay runs, watch Day 86's dashboard and Phoenix, then write the numbers down: they're the baseline for Day 90's load test and SLOs.

```markdown
<!-- file: STAGING_REPORT.md -->
# Staging report: r5.0.0-rc1 (<git sha>, <date>)
| Metric (10-min replay, 4 tenants) | Value | Source |
|---|---|---|
| requests / errors (ReplayReport counts the demo tenant's expected 429s too) | <n> / <n> | ReplayReport + event log `status` |
| p50 / p95 latency | <ms> / <ms> | ReplayReport + dashboard |
| $ per request (mean) | <$> | event log `usd_per_req` |
| cache hit rate | <%> | event log `cache_hit` |
| online check pass rate | <%> | `online_pass_rate` (Day 86) |
| fallback / degraded rate | <%> / <%> | event log |
| Known issues | <list, each with an owner> | |
```

## Trade-offs and Tagging

R5 skips multi-region, Kubernetes, SSO, a Redis-backed shared cache (Day 85 has one), token streaming through the fallback layer and a WebSocket route (Day 79's `/v1/ws/chat` has no auth yet, so it isn't mounted). None blocks staging.

| Choice | R5 picks | Pick the other when |
|---|---|---|
| Real backends vs stubs in CI | stubs on every PR, reference nightly | you have a cheap, stable eval budget per PR |
| One app vs a service per route | one FastAPI app | routes need different scaling or deploy cadences |
| In-process cache | per replica | more than one replica serves the same tenants |
| Investigate durability | one-shot over HTTP | runs exceed a few minutes: move them to Day 78 jobs |

### In production

- Run the Day 88 on-call rota and runbooks against staging traffic now, not at launch.
- Turn budget alerts on (Day 86's `evaluate_alerts`) before the replay, so a runaway loop pages you.
- Rotate the seeded staging keys after the replay; never reuse them in production.
- Keep `ATLAS_BACKEND=stub` refused in prod (it is, in `Settings.from_env`).
- Watch `fallback` and `degraded` rates separately: one means a provider is wobbling, the other means users are getting less.

**Tag it.** A **release candidate (rc) tag** marks a build that passed staging and awaits its final gates. With the checks green and `STAGING_REPORT.md` filled in, run `git tag -a r5.0.0-rc1 -m "R5 integrated on staging"` and push it. Today's reference solution is the course repo's `r5-part1-reference` tag (⚠ the link ships with the course materials): diff against it, don't copy it.

The release README leads with numbers. Start it now; Day 90 fills the production column:

```markdown
<!-- file: README.md (release section) -->
## Atlas r5.0.0-rc1: numbers first
| | Staging (today) | Production (Day 90) |
|---|---|---|
| Eval: Day 47 fast suite pass rate (primary / fallback model) | <%> / <%> | |
| Eval: Day 75 red-team fast suite | <passed>/<total> | |
| Online check pass rate (Day 86) | <%> | |
| $ per request (mean, 10-min replay) | <$> | |
| p95 latency, ask / investigate | <ms> / <ms> | |
| Cache hit rate | <%> | |
**Known failures.** Day 86's `cites_existing_doc` check only knows the public docs, so it fails answers that cite a tenant runbook; the ask stream sends the answer as one chunk; in-process cache per replica.
**Reference solution.** Tag `r5-part1-reference` in the course repo; this repo's own tags are `r5.0.0-rc1` and later.
```

## Go Deeper (optional)

<details><summary>Go deeper: token streaming with a fallback</summary>

Today's ask stream sends the answer as one `token` event, because Day 84's `ResilientLLM` wraps `responses.create()` without `stream=True` (its docstring says so). True token streaming with fallback follows one rule: **you may switch models only before the first token reaches the client.** Open the primary's stream and wait for its first `response.output_text.delta` under a short deadline. If the stream errors or the deadline passes first, record a breaker failure and open the next model's stream. Once a token has gone out, a failure ends the stream with an `error` event and the UI offers a retry. Splicing two models' half-answers into one reply is worse than a clean error. Measure time to first token (Day 13) before and after: the switch costs you the deadline every time the primary is slow.

</details>

<details><summary>Go deeper: running the lesson's code outside your repo</summary>

The files printed today import about twenty files from Days 42 and 77–88, which this page doesn't re-print. Without them, the extracted lesson stops at `ModuleNotFoundError: No module named 'atlas.quotas'`. Run `python scripts/assemble_r5.py` first: it writes clean copies of every missing carried file from the course lessons, then `pytest tests/test_integration.py` runs on them. To compare with your own repo, assemble into an empty copy and diff. If a carried file's names differ from the table in §3, fix the import here, not the carried file. The carried file is the contract that day's tests prove.

</details>

<details><summary>Go deeper: what to add before real customers</summary>

- **Per-tenant data deletion.** Day 73's erasure path must reach the event log, the cache (`SemanticCache.invalidate("t:<tenant>:")`) and R4's checkpoints. Write the test before a customer asks for it.
- **Request signing for the UI → API hop** if the UI runs on a different network than the API. Today it relies on the bearer key alone.
- **Shadow traffic for `reference`.** Mirror a sample of stub-backed staging traffic to the reference backend, compare with Day 87's `compare_variants`, and switch only when the guards pass.
- **Separate API keys for the UI and for scripts**, so revoking a leaked script key doesn't log every browser out.

</details>

## Common Pitfalls

- **`ImportError: cannot import name 'X' from partially initialized module 'atlas.api.app' (most likely due to a circular import)`.** A route module imported `app.py` to reach a shared name. Only `app.py` imports routes; shared names live in `deps.py` and `pipeline.py`.
- **Cache checked before auth or quota.** Free cross-tenant reads, or cache hits that eat quota. Follow the pipeline diagram; tests 2 and 4 catch both.
- **Two retry layers again.** The SDK's default retries under `ResilientLLM` turn 3 attempts into 9. Build the client with `max_retries=0` in `build_deps`, as shown.
- **Works in compose, fails on the platform.** `ATLAS_API_URL` or `ATLAS_REDIS_URL` still name compose services (`http://api:8000`). Use one `.env` per environment.
- **An SSE route outside the pipeline.** The old capstone's `/stream` had no rate limit. Every model-calling route takes a `Ticket` from `admitted()`; Exercise 2's test calls every `/v1` route without a key to prove none is open.
- **`sqlite3.OperationalError: database is locked` under replay.** Keep one WAL-mode `EventLog` per process (it's in `Deps`), or move the log to Postgres on staging.

> **Where we stop:** R5 is integrated and running on staging with first numbers; load tests, the chaos drill, SLOs, the production release and the public demo are [Day 90](../../Phase_9_Production/Day_090_capstone_r5_launch/capstone_r5_launch.md).

## Key Takeaways

- Integration is mostly about **order**: auth before cache, cache before reservation, breaker before every retry, settle and record in `finally`. A wrong order passes every unit test and fails in production.
- Trace one request by hand first: the stages before the model call cost milliseconds and no tokens, so the safe order is affordable.
- A **composition root** (`build_deps`) and a **backend adapter** setting (`ATLAS_BACKEND=reference|stub`) let CI run the whole system with no key while production runs the real R2–R4.
- Prove the order with tests at the HTTP boundary: isolation, quota, cache scope, fallback and degraded mode, SSE, canary stability and one event row per request.
- A **hardening checklist** row needs a place where the rule is enforced and something that proves it. Deploy to staging, replay real-shaped traffic, write the numbers down and tag a **release candidate**.

## Quick Reference

| Pattern / API | Use it for | Gotcha |
|---|---|---|
| `build_deps(settings)` in `lifespan` | build every client, pool and store once | nothing else may construct a client |
| `AsyncOpenAI(max_retries=0)` + `ResilientLLM` | exactly one retry layer | a default client stacks retries |
| `build_pools(client, models)` | one pool per routable model | share the breakers, or fuses disagree |
| `Depends(admitted(route, stream=...))` | guards before any byte is sent | streams reserve first and refund on a hit |
| `cache_scope(p, model=, prompt_version=, index_version=)` | tenant-safe cache keys | add `:orbit=<version>` as Day 85 does |
| `finish(t, deps, status=)` in `finally` | settle tokens, write one event row | a bare `return` before it skips both |
| `uvicorn atlas.api.app:create_app --factory` | no app built at import time | the factory reads env at startup |
| `ATLAS_BACKEND=stub` + `ATLAS_REDIS_URL=fake://` | keyless CI and local runs | refused in prod by `Settings` |

## Exercises

1. **Warm-up: traceable deploys.** Make `RequestContext` also add `X-Request-Id` and `X-Atlas-Release` headers to every response, including SSE and 4xx. Then assert both headers in `smoke_staging`.

<details><summary>Solution</summary>

Wrap `send` and append the headers to the `http.response.start` message. Because this is pure ASGI, it works for SSE too. In `smoke_staging`, check `resp.headers["X-Atlas-Release"]` on `/healthz`.

```python
# script_id: day_089_capstone_r5_integrate/solution_ex1
# RequestContext v2: stamps X-Request-Id and X-Atlas-Release on every response. Runs as a demo.
import re
import uuid

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

_RID = re.compile(r"[A-Za-z0-9-]{8,64}")


class RequestContext:
    def __init__(self, app, release: str = "dev") -> None:
        self.app, self.release = app, release

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        sent = dict(scope["headers"]).get(b"x-request-id", b"").decode()
        rid = sent if _RID.fullmatch(sent) else uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = rid

        async def stamped(message) -> None:
            if message["type"] == "http.response.start":
                extra = [(b"x-request-id", rid.encode()), (b"x-atlas-release", self.release.encode())]
                message["headers"] = [*message.get("headers", []), *extra]
            await send(message)
        await self.app(scope, receive, stamped)


if __name__ == "__main__":
    app = FastAPI()

    @app.get("/healthz")
    async def healthz(request: Request) -> dict:
        return {"request_id": request.state.request_id}

    app.add_middleware(RequestContext, release="3f2c1ab")
    r = TestClient(app).get("/healthz", headers={"X-Request-Id": "smoke-0001"})
    print(r.headers["x-request-id"], r.headers["x-atlas-release"], r.json())
```

```text
smoke-0001 3f2c1ab {'request_id': 'smoke-0001'}
```

In `create_app`, register it with `app.add_middleware(RequestContext, release=settings.release)`.

</details>

2. **Core: no unprotected endpoints.** Write a test that finds every `/v1/*` route and proves each one refuses a request without a key.

<details><summary>Solution</summary>

Read the routes from the OpenAPI schema rather than `app.routes`: FastAPI 0.162 keeps an included router (like Day 86's feedback router) as one nested entry in `app.routes`, while the schema lists every path. Then call each route with no key. Checking behaviour also catches a route that has `require_principal` but swallows its error.

```python
# script_id: day_089_capstone_r5_integrate/solution_ex2
# tests/test_routes.py: every /v1 route answers 401 without a key. Run: uv run pytest tests/test_routes.py -q
from tests.test_integration import api  # noqa: F401  (reuse the fixture: routes exist after startup)


def test_every_v1_route_requires_a_key(api):  # noqa: F811
    paths = api.app.openapi()["paths"]
    v1 = [(path, method) for path, ops in paths.items() if path.startswith("/v1/") for method in ops]
    assert len(v1) >= 5, v1                               # ask, ask/stream, investigate, triage, feedback
    for path, method in v1:
        url = path.replace("{", "").replace("}", "")      # /v1/reports/{job_id} -> /v1/reports/job_id
        r = api.request(method.upper(), url, json={})
        assert r.status_code == 401, f"{method.upper()} {path} answered {r.status_code} without a key"
```

Add a route without a key check and the failure names it: `AssertionError: POST /v1/debug answered 200 without a key`.

</details>

3. **Core: tests as guard rails.** Delete the tenant from the cache key, watch which integration test fails, then restore it.

<details><summary>Solution</summary>

Test 4 fails: Zephyr's request comes back `cached=True` with Acme's answer. The test below makes the leak permanent and visible. It pins the canary variant, so the tenant is the only difference between the two keys.

```python
# script_id: day_089_capstone_r5_integrate/solution_ex3
# tests/test_cache_leak.py: a tenant-less cache key leaks across tenants. Run with pytest.
from atlas.api import pipeline
from tests.test_integration import api, ask  # noqa: F401  (reuse the fixture and helper)


def leaky_scope(p, *, model: str, prompt_version: str, index_version: str) -> str:
    return f"cache:idx={index_version}:prompt={prompt_version}:model={model}"   # no t:<tenant>


def test_tenantless_cache_key_leaks(api, monkeypatch):  # noqa: F811
    monkeypatch.setattr(pipeline, "cache_scope", leaky_scope)
    monkeypatch.setattr(pipeline, "resolve_prompt", lambda *a, **k: ("v3", "control"))
    q = "What lease_seconds do we use for the nightly ETL queue?"
    ask(api, "acme", q)
    leaked = ask(api, "zephyr", q).json()
    assert leaked["cached"] is True
    assert any(c["doc_id"] == "acme/runbook" for c in leaked["answer"]["citations"])
```

The fix is the one you deleted: `cache_scope()` starts every key with `tenant_key(p, ...)`.

</details>

4. **Stretch (optional): real-backend confidence.** Add a nightly workflow that deploys nothing, runs Day 47's fast suite with `ATLAS_BACKEND=reference` and a live key against staging, and stops at $0.50.

<details><summary>Solution</summary>

Schedule it, give it the secret and a hard timeout, and pass the budget to the suite. Your Day 47 runner (or Day 18's `Budget`) must read `ATLAS_EVAL_BUDGET_USD` and stop when it is spent.

```yaml
# file: .github/workflows/nightly-reference.yml
name: nightly-reference
on:
  schedule: [{ cron: "17 3 * * *" }]     # 03:17 UTC, off the hour
  workflow_dispatch:
permissions: { contents: read }
jobs:
  reference-fast-suite:
    runs-on: ubuntu-latest
    timeout-minutes: 20                    # a hung run can't burn money all night
    env:
      OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      ATLAS_BACKEND: reference
      ATLAS_API_URL: ${{ vars.STAGING_URL }}
      ATLAS_EVAL_BUDGET_USD: "0.50"
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/setup-uv@v10.3.3
        with: { enable-cache: true }
      - run: uv sync --locked --all-extras --dev
      - run: uv run pytest -m eval -q        # Day 47's fast suite
```

</details>

## References & Further Reading

- [FastAPI: Server-Sent Events](https://raw.githubusercontent.com/fastapi/fastapi/master/docs/en/docs/tutorial/server-sent-events.md): the native `fastapi.sse` API the stream routes use.
- [FastAPI: lifespan events](https://raw.githubusercontent.com/fastapi/fastapi/master/docs/en/docs/advanced/events.md): where the composition root runs, and why not `@app.on_event`.
- [Docker Compose services reference](https://docs.docker.com/reference/compose-file/services/): `depends_on` conditions and healthchecks for the staging stack.
- [setup-uv README](https://raw.githubusercontent.com/astral-sh/setup-uv/main/README.md): why the workflow pins `v10.3.3` (there's no `@v10` tag).
- [OpenAI: data controls](https://developers.openai.com/api/docs/guides/your-data): `store`, retention and the background-mode exception in the hardening table.
- [Arize Phoenix](https://github.com/Arize-ai/phoenix): the local tracing UI that shows today's per-stage spans.
- [pgvector](https://github.com/pgvector/pgvector): the image tag and PG 18 volume path used in compose.

## What's Next

R5 runs on staging with its first numbers. In [Day 90: Capstone R5, Part 2: Launch & Prove It](../../Phase_9_Production/Day_090_capstone_r5_launch/capstone_r5_launch.md) you load-test it, break it on purpose in a chaos drill, set SLOs from today's baseline, push it through an eval-gated production release and finish the numbers-first README.
