# Changelog

Notable changes to the course content. Newest first.

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
