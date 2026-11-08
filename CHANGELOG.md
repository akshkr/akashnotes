# Changelog

Notable changes to the course content. Newest first.

## 2026-11 (v2: full re-sequence and rewrite)

- **The whole course was redesigned and rewritten (v2).** It still has 100 days, now in 12 phases.
  `SYLLABUS_V2.md` is the new syllabus, and `docs/old_to_new_map.csv` maps every
  old day to its new home. The v1 course is archived in `archive/v1/`.
- **Why.**
  - 66 v1 lessons used `gpt-4o`/`gpt-4o-mini` (shutting down 2027-01-14) and Chat Completions.
  - Evals started at D58, and MCP arrived at D95.
  - Several topics were taught 3–5 times.
  - Two capstones (D18, D48) didn't run when extracted.
  - Some lessons were built on retired products: OpenAI hosted fine-tuning, the Evals platform, the
    Assistants API, GPTCache.
- **New structure:**
  - Setup and a first API call on Day 2.
  - An eval habit from D20, with a full evals phase before agents.
  - RAG, then tools and MCP (D35–41), then agents (LangGraph as the capstone runtime, with the OpenAI
    Agents SDK as the alternative).
  - Multi-agent, then safety and security, then production, then open models and fine-tuning
    (open weights), then career.
- **New topics:**
  - Model selection and lifecycle; your first eval set; prompts as code.
  - Text-to-SQL; long context vs RAG; built-in tools.
  - Context engineering; planning; agentic RAG; coding agents and skills.
  - Threat modeling; safe output handling; red-teaming in CI.
  - Voice and realtime; auth and multi-tenancy; operating AI systems.
- **Removed or reduced:**
  - CrewAI (3 days), LlamaIndex and PydanticAI became comparison rows (D57).
  - DSPy and GraphRAG became sections.
  - Part-1/Part-2 pairs were merged.
- **One product thread:** "Atlas" over the synthetic **Orbit** dataset (`datasets/orbit/`, CC0),
  shipped as R1–R5.
- **Every lesson follows the new template** (`STYLE_GUIDE.md`):
  - A ~2-hour core, with a fast path and a cost estimate.
  - An optional Go Deeper section.
  - 3 + 1 exercises with solutions.
  - References that were verified (live links checked, TLS-proxy aware).
- **Facts were verified, not remembered.**
  - `REFERENCE.md` was rebuilt from installed-package introspection plus official docs (2026-11-06):
    the GPT-6 lineup, the Responses API, Claude 5.x, MCP SDK 2.x, LangGraph 1.2, Gradio 6, TRL 1.x
    and more.
  - About 25 stale claims were corrected along the way. Examples: free Hugging Face CPU Spaces now
    need PRO; Postgres `ts_rank` isn't BM25; `qwen3:4b` is a different model from the
    `qwen3:4b-instruct-2507` build we fine-tune.
- **Added:** 15 fresher primers (`Appendix_Primers/`), a generated `index.md`, and `GLOSSARY.md`
  (446 terms).
- **Tooling:**
  - `tools/lesson_check.py`: template, budget, stitched-import bug, deprecated APIs, Mermaid
    rendering, online links.
  - `tools/run_scripts.py`: runs every extracted script.
  - `tools/course_qa.py`: link and day-chain QA.
  - `tools/build_index.py`
  - CI runs the lesson gate and course QA.
- **Known limitation:** no API key was available during the rewrite, so API-calling scripts were
  verified against the installed SDKs' signatures, not executed. Run one smoke pass with a real key
  before relying on the shown outputs.

## 2026-07 (Phase 1 reordering)

- **Reordered Phase 1 (LLM Foundations) for a smoother learning arc** — no content
  rewritten beyond transition prose. Moves (folders renamed, `script_id`s, index,
  "What's Next" previews, opening recaps, and all cross-references updated; checker
  `--strict` 0/0):
  - **Tokenization ⇄ Transformers** (now D2 Tokenization → D3 Transformers): tokens
    are defined before the attention mechanism that operates on them.
  - **System vs User Prompts moved ahead of the prompt-engineering trio** (now D6),
    before Zero/Few-Shot (D7) and Chain of Thought (D8–D9): message roles are the
    foundation those techniques build on.
  - **Retry ⇄ Testing** (now D15 Retry → D16 Testing): error handling is introduced
    before testing wraps around the error-handled code.
  - Fixed two pre-existing stale cross-references surfaced during the sweep
    (D37 token ref, D15 temperature ref).

## 2026-06 (curriculum analysis + execution)

- **Curriculum-level analysis** (`CURRICULUM_REPORT.md`, multi-agent workflow over
  the TOC) → reconciled into the `IMPROVEMENT_PLAN.md` canonical backlog. Verified
  many "missing" items were already implemented by the earlier passes (D091 native
  prompt caching, D029 native structured outputs, D047 failure-mode diagnosis).
- **Executed the in-place tracks** (all keep the 100-day numbering; checker `--strict`
  0/0 throughout):
  - Ordering callouts (D9 SDK-setup, D32 "agent" forward-ref); currency positioning
    (D17 DSPy, D53 CrewAI, D95 MCP); capstone reuse made code-visible (D34/D48/D99);
    D94 adaptive-thinking section (verified `thinking`/`effort` API); D26 trimmed.
  - **Three in-place repurposes** (deleted the redundant lesson, authored a new one,
    renamed folder/file, updated index + neighbour footers):
    - **D046** Database Storage → **Agent Memory & Context Budgeting** (overlapped
      D044 persistence).
    - **D092** Model Fallback → **Retrieval Evaluation & Reranking** (overlapped D090;
      provider-fallback note moved to D090).
    - **D067** API Key Security → **PII & Data Privacy in RAG/Agents** (secrets stay
      in D066).
- **Still held for sign-off:** phase rebalancing (P4 thin / P5 heavy) and provider
  standardization — see `IMPROVEMENT_PLAN.md` §2 and §5.

## 2026-06 (multi-agent quality review)

- **Multi-agent course-quality review + staged fixes.** Ran a fan-out →
  adversarial-debate → arc-audit workflow over all 100 lessons (~1,135 gatekept
  findings, both invariants enforced: simple SWE-migration voice; no-ML-background
  ceiling). Applied in reviewed batches (checker green, `--strict`):
  - Batch 1 — corrected stale/wrong "What's Next" footers and premature
    "course complete" blocks (Days 5, 13, 16, 20, 37, 50, 62, 73, 74, 89, 94, 95).
  - Batches 2-4 — ~1,090 findings across 96 lessons: stale SDK signatures
    (PydanticAI, RAGAS, Guardrails, TRL, langchain_chroma), nonexistent Ollama/HF
    model tags, MCP `AnyUrl` compare + path-traversal guard, missing imports under
    split `script_id`s, `claude-sonnet-4-5`→`4-6`, one-clause SWE/jargon glosses,
    corrected Day 2 attention & Day 19 embedding analogies, collapsible solutions,
    Checkpoint ordering, dated pricing caveats.
  - Held for author sign-off (CLAUDE.md §7): provider standardization, redundant-day
    consolidation (089/093, 044/045, 074/075, 051-055), GPU on-ramp for Days 78-79,
    index.md reranking mismatch.

## 2026-06

- **Content refinement pass across all 100 lessons.** Fixed runnable-code bugs
  (OpenAI v1 client, Pydantic v2 validators/defaults, `pypdf`, llama.cpp binary
  renames, Gradio 5 chat format, Anthropic `with_options(timeout=)`, Docker
  sandbox temp-file naming, RAGAS `EvaluationDataset` API, `ollama.embed`,
  multimodal token counting). Repaired cross-references and "What's Next"
  footers left by an earlier renumber; rewrote the Day 1 roadmap and Day 49
  career checkpoint to the real 9-phase / 100-day structure; completed the
  truncated Day 3 (tokenization); removed duplicated sections (Days 26, 83) and
  two premature "course complete" blocks (Days 89, 93); corrected model IDs and
  pricing to the current lineup.
- Added Exercises sections to Days 30, 31, 88; expanded Day 8 (when CoT doesn't
  help + cost tradeoff).
- Strengthened the Day 96 disclaimer / grounded its code in a verified API.
- **Quality push (P0–P1 of `IMPROVEMENT_PLAN.md`):**
  - P0: standard sections (Summary → Quick Reference → Exercises w/ collapsible
    solutions → What's Next) backfilled across all 100 days; 13 intentional
    fragment blocks marked `# fragment`; CI now runs `--strict` (checker 0/0).
  - P1: a runnable `## Checkpoint` added to every hands-on day (~95); the two
    double-lessons (039, 075) given explicit Part-1/Part-2 framing (mis-placed
    mid-file footers fixed); the 5 capstones threaded into one "Portfolio thread
    (N of 5)" narrative; `GLOSSARY.md` added; native structured-outputs section
    added to Day 029.
  - Declined as quality-negative: provider rip-out (kept the deliberate
    OpenAI+Anthropic coverage) and per-day difficulty chips (noise).
- Added this CHANGELOG and `REFERENCE.md` (central models/pricing/day-map).
- Removed `main.py` and `scripts/` (publish/extract tooling now lives outside
  the content repo).

<!--
Template for future entries:

## YYYY-MM
- <what changed> (Day NN / phase / repo-wide)
- When you bump a model ID or price, update REFERENCE.md first, then any lesson
  that restates the value, then add a line here.
-->
