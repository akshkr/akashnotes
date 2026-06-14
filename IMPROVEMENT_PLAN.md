# Course Improvement Plan

Goal: make the course **extremely high quality** while keeping it **easy and
written in natural language**. Status of each item is tracked in this file as we
execute (see `CHANGELOG.md` for shipped changes).

## Guiding principle: progressive disclosure

Depth fights approachability. Resolve it by keeping the **main flow of every
lesson short, conversational, and SWE-translated**, and pushing rigor into
*optional* layers (collapsible "Go deeper" notes, exercise solutions,
references). Three invariants must survive every change:

1. The **"Coming from Software Engineering?"** translation voice.
2. **Copy-runnable, current code** (learners paste it; the pipeline runs it).
3. The **100-day numbering** — improve **in place**, never renumber.

## Diagnosis (from the structural audit, 2026-06)

- **Format half-delivered:** Exercises missing in **59/100** days; Quick
  Reference in **37**; Summary in **26**; "What's Next" in **8**.
- **Pacing whiplash:** lengths 242→871 lines (median 501). Bloated non-capstone
  days: `llamaindex` (871), `quantization` (845), `cost_engineering` (804).
- **Redundancy + filler splits:** 066/067, 069–071, 090/092, 044–046; eight
  topics padded into Part 1/Part 2.
- **"Read about it," not "do it":** most days lack practice; capstones aren't
  threaded into one portfolio.
- **Content gaps:** reranking/hybrid search depth, retrieval-eval discipline,
  native structured outputs/tool reliability, prompt-caching economics, PII/data
  privacy.
- **Maintainability:** mitigated by `REFERENCE.md` + CI; needs an ongoing cadence.

## Workstreams

### P0 — Consistency pass (highest quality-per-effort, low risk)
- **A. Canonical lesson skeleton + rubric** (see Definition of Done below).
- **B. Backfill** in leverage order: Exercises (59 days, with collapsible
  solutions) → Quick Reference (37) → Summary mindmaps (26) → "What's Next" (8).
- **C. Accuracy cadence:** annotate intentional fragment blocks so CI can run
  `--strict`; enforce the "as of <date>, verify" pattern; add a quarterly
  refresh checklist to `CHANGELOG.md`.

### P1 — The "do it" spine
- **Checkpoint per day:** one runnable snippet to execute and verify.
- **Thread the 5 capstones** (D18→D34→D48→D73→D97) into one continuous portfolio
  app that becomes the D99 portfolio.
- **Right-size** the 3 bloated days into a ~400–650-line band (capstones exempt).

### P1/P2 — Close content gaps via in-place repurposing (no renumber)
| Repurpose | Into |
|---|---|
| one of 069–071 (HITL ×3) | Retrieval evaluation (precision/recall/NDCG) |
| 067 (≈066 API keys) | PII & data privacy in RAG/agents |
| 092 (≈090 circuit breakers) | Reranking & hybrid search depth |
| 046 (≈044/045 persistence) | Native structured outputs & tool-call reliability |

### P2 — Provider & voice consistency
- Pick a **primary provider**; show the other as a labeled "same in <other>"
  aside. Standardize phase-by-phase.
- Add recurring **"Common mistake"** and **"In production"** boxes.

### P3 — Learner experience
- Per-day header chips: prerequisites, estimated time, difficulty.
- Phase-boundary self-assessments; glossary; cross-links.

## Definition of Done (per-lesson rubric)

A lesson is "high quality" when it has: an SWE-translation callout; one clear
diagram; **runnable, current** code that passes the CI parser; a Checkpoint to
run; a Summary; a Quick Reference; 3–4 scaffolded exercises with collapsible
solutions; a correct "What's Next"; length in band (or justified); and every
model/price/cross-reference agreeing with `REFERENCE.md`.

## Sequencing

1. P0 consistency backfill + accuracy cadence.
2. P1 checkpoints, capstone threading, right-sizing.
3. P1/P2 gap swap-map + provider standardization.
4. Ongoing quarterly accuracy refresh.

---

## Batch 5 backlog (from the 2026-06 multi-agent review — needs author sign-off)

The review applied ~1,120 single-file findings in place (see `CHANGELOG.md`).
These items were held because they touch **content across multiple days**, the
**day map**, or **provider strategy** — high blast radius per CLAUDE.md §7.
Rule for all of them: **repurpose in place, keep day numbers, no renumber.**

### A — Cross-day consolidation (PROPOSED; awaiting approval)

| # | Overlap | Proposed resolution (no renumber) |
|---|---|---|
| A1 | **D089 Docker ↔ D093 Cloud** (substantial duplication; reliability patterns also in D090) | D089 = containerizing only (Dockerfile/Compose/health probes). D093 = deploying that image to cloud (Render/Railway/AWS/GCP, CI/CD, secrets). Move retry/circuit-breaker reliability to live **only in D090**; D089/D093 link to it. |
| A2 | **D044 Checkpoints ↔ D045 Time-Travel** | D045 stays the canonical time-travel home; D044's subsection already teasered to a pointer. Confirm no remaining code overlap. |
| A3 | **D069 HITL ↔ D072 Injecting Feedback** (069–071 are HITL×3) | D072 = canonical "inject feedback into agent state"; trim D069's overlapping feedback section to a pointer. Optionally free one of 069–071 for the gap-topic swap below. |
| A4 | **D047 Debugging re-teaches D045 time-travel** | Trim D047's LangGraph time-travel re-teach to a one-line pointer to D045; keep D047 on logging/tracing/failure modes. |

### B — Long-day trims (judgment calls)
- **D026** context injection (741 lines) and **D044** (692) exceed the 400–650 band. Trim *duplicated/secondary* sections only; do not cut on-topic content.

### C — Within-day dedup
- **D083** fastapi two SSE sections — **resolved** in Batches 2-4 (differentiated + `[DONE]` standardized).

### D — Provider standardization
- Phase 7 (and D052) lean OpenAI while the course centers Anthropic. The review
  only fixed internal contradictions + added setup notes; a full standardization
  pass (pick one primary provider, show the other as a labeled aside) remains a
  product decision. Pairs with the long-standing open item in §"P2".

### Related existing swap-map (P1/P2 above, still open)
069–071 → retrieval eval · 067 → PII/privacy · 092 → reranking depth · 046 →
structured outputs. A3's freed HITL slot could feed the retrieval-eval swap.
