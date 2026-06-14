# Changelog

Notable changes to the course content. Newest first.

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
