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
