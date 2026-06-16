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

> Refined by the 2026-06 curriculum analysis (`CURRICULUM_REPORT.md`). The
> **Canonical backlog** at the bottom of this file is the authoritative version;
> the table below is the summary.

| Repurpose (keep number) | Into |
|---|---|
| 046 (thin; ≈044/045 persistence) | **Agent memory & context budgeting** |
| 092 (≈090 circuit breakers) | **Retrieval evaluation + reranking & hybrid search** |
| 067 (≈066 API keys) | **PII & data privacy in RAG/agents** |
| 069+070 (HITL overlap) | rewrite-in-place to free a slot (Phase 4 expansion) |

Note: *native structured outputs & tool-call reliability* is no longer a standalone
repurpose target — fold it into **D029** (tool schemas) / **D064** (guardrails) instead.

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

## Canonical improvement backlog (2026-06)

Merges the lesson-level multi-agent review (`ANALYSIS_REPORT.md`) and the
curriculum-level analysis (`CURRICULUM_REPORT.md`). The lesson review applied
~1,120 single-file findings in place (see `CHANGELOG.md`). What remains below is
**structural / product-level** work. Standing rule per CLAUDE.md §7: **repurpose
in place, keep day numbers, no renumber.**

### 0 — Done (no further action)
- **Cross-day de-dup, applied:** D089 Docker ↔ D093 Cloud (D089 now containerizing-
  only; reliability → D090; reciprocal pointers); D069 feedback section → pointer
  to D072. D044↔D045 time-travel and D047 re-teach already resolved via Day-45
  pointers. D083 SSE sections differentiated.
- **TOC reconciled:** index.md updated for the D089 de-dup and the D034 reranking
  mismatch.

### 1 — Gap closure via in-place repurpose (DONE — 2026-06)
All three authored in place (kept day numbers; folders/files renamed; index + neighbour footers updated; checker `--strict` 0/0):
| Repurpose (kept number) | Into | Status |
|---|---|---|
| **D046** Database Storage | **Agent Memory & Context Budgeting** | ✅ done (overlapped D044 persistence, which stays canonical) |
| **D092** Model Fallback | **Retrieval Evaluation & Reranking** | ✅ done (fallback note moved to D090; D026 reranking can now point here) |
| **D067** API Key Security | **PII & Data Privacy in RAG/Agents** | ✅ done (secrets coverage stays in D066) |

*Structured-output reliability* was already covered (D029 strict tools + `output_config.format`); no standalone day needed.

### 2 — Phase balance (HIGH; needs sign-off — may free P5 slots for P4)
- **P4 Multi-Agent (6 days)** is the thinnest phase for an increasingly central
  topic; **P5 Eval+Security (18 days)** carries the redundancy. Consolidating a
  P5 overlap (e.g. rewrite **D069** to cover basic + multi-stage HITL, freeing
  **D070** conceptually *without* renumbering) could feed a P4 expansion
  (multi-agent debugging/observability, handoff & cost-aware routing).

### 3 — Currency additions (MEDIUM; all in-place, with "as of <date>, verify" caveats)
- **D091** add native prompt caching (Anthropic `cache_control`, OpenAI prompt
  caching) as the primary pattern; semantic caching second.
- **D029/D064** native structured outputs (json_schema / output_config) + retry-
  on-parse-fail + first-try-parse reliability metric.
- **D094** adaptive thinking: when to enable, cost/latency trade-off, route by complexity.
- **D087** reframe agentic UI as the default (tool call → component), Streamlit/Gradio to a sidebar.
- **D032** video-frame inputs for agents (frame sampling + cost).
- **D047** failure-mode diagnosis section (loops, hallucinated tool calls, context overflow).
- Positioning caveats: **D017 DSPy** ("advanced/optional, not core"), **D053 CrewAI**
  ("prototyping; LangGraph for production"), **D095 MCP** ("emerging standard as of 2026").
  *Currency adoption figures in `CURRICULUM_REPORT.md` are agent web-estimates — verify before quoting.*

### 4 — Within-day trims (LOW; recount first — D044/D089 changed since the line counts were taken)
- **D026** context injection and **D044** checkpoints exceed the 400–650 band. Trim
  *duplicated/secondary* sections only; do not cut on-topic content. Re-measure first.

### 5 — Provider standardization (product decision; still open)
- Phase 7 (and D052) lean OpenAI while the course centers Anthropic. The reviews
  only fixed internal contradictions + added setup notes. A full pass (pick one
  primary provider, show the other as a labeled "same in <other>" aside) remains
  open. Pairs with §P2 above.

### 6 — Capstone enhancements (LOW; optional, in-place)
- Make portfolio reuse code-visible: D34 note on reusing D18 extraction; D48 commented
  import of the D34 RAG chatbot; D99 "wiring your 5 projects together" section.

### Ordering fixes (LOW; in-place callouts — partly done)
- SDK setup (D10–11) lands after live code (D4–9): D4 setup callout already added;
  D9 still uses live client code that could carry the same callout. "agent" used on
  D30/D32 before its formal D35 intro — add a one-line "formal agent loop arrives D35".
