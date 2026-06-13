# CLAUDE.md — Working on this repository

This file orients Claude (and any AI assistant) to what this repo is, how it's
built, and the rules for editing it. Read it before making changes.

---

## 1. What this is

A **100-day course that helps experienced software engineers transition into AI
engineering** (building production LLM apps — not ML research). The content is
**Markdown lessons** that an external frontend pipeline renders into web pages.

- **Audience:** working SWEs. The pedagogical hook — used throughout and central
  to the course's value — is translating AI concepts into things a SWE already
  knows (e.g. tokenization ≈ character encoding, RAG ≈ a data-access layer,
  vector DB ≈ CRUD with similarity instead of equality).
- **Voice:** practical, direct, job-transition–focused. Each phase ends with a
  capstone; the course closes on interview/portfolio/career.
- This repo is **content only**. The publish/render/extract tooling lives in a
  **separate frontend project** — `scripts/` and `main.py` were intentionally
  removed from here.

---

## 2. Repository structure

```
index.md                     # master day-by-day index (human-facing TOC)
REFERENCE.md                 # ★ source of truth: model IDs, pricing, lib gotchas, day map
CHANGELOG.md                 # change history (update when you change facts)
CLAUDE.md                    # this file
tools/check_snippets.py      # static checker (fences + python parse)
.github/workflows/           # CI that runs the checker
Phase_<N>_<Name>/
  Day_<NNN>_<slug>/
    <slug>.md                # one lesson per folder; filename matches the slug
```

**Canonical day/phase map (authoritative copy in `REFERENCE.md`):**

| Phase | Days | Title |
|---|---|---|
| 0 | 1 | Getting Started |
| 1 | 2–18 | LLM Foundations *(capstone D18)* |
| 2 | 19–34 | RAG & Tool Calling *(capstone D34)* |
| 3 | 35–49 | Single Agent Architectures *(capstone D48, Career Checkpoint D49)* |
| 4 | 50–55 | Multi-Agent Systems |
| 5 | 56–73 | Evaluation & Security *(capstone D73)* |
| 6 | 74–82 | Fine-tuning & Optimization |
| 7 | 83–97 | Production Deployment *(capstone D97)* |
| 8 | 98–100 | Career Launch |

The five portfolio capstones: **D18, D34, D48, D73, D97**.

---

## 3. ★ The rendering & `script_id` model (read this before editing code)

Lessons are **rendered to web pages**: Mermaid blocks become diagrams, and
fenced code blocks become syntax-highlighted code. **Python code blocks are also
extracted and executed by the external frontend pipeline**, keyed on a
first-line comment:

```python
# script_id: day_034_capstone_rag_chatbot/extraction_pipeline
...
```

**Concatenation convention:** blocks that **share the same `script_id`** (within
a file) are **stitched together, in document order, into one runnable file.**
This is why a class can be introduced in one block and extended in later blocks
under the same id, and why most lessons repeat a `script_id` several times —
**repeated `script_id`s are intentional, not collisions.**

Consequences for editing:

- **Correctness matters more here, not less.** Learners read the page and
  *copy the code into their own projects* — there is no compiler between your
  code and them. A wrong import or API call fails on *their* machine and costs
  trust. Keep all code runnable and current.
- **Never break fence balance.** Every code block must open and close with
  ```` ``` ````. An odd fence count means code renders as prose (this is how a
  past bug left a method un-highlighted). The CI hard-fails on this.
- **Don't split a logical script.** If you add a block that's part of an
  existing class/script, give it the **same `script_id`** as that script, not a
  new one (a new id would extract as an orphan fragment).
- **Some blocks are intentionally non-runnable fragments** — cheat-sheets
  (`.../quick_reference`), lone methods shown for illustration, pseudo-code.
  These won't parse standalone; that's fine. The CI reports them as *warnings*,
  not errors.

---

## 4. Lesson anatomy (keep this structure consistent)

A typical day, in order:

1. `# Title` (H1).
2. A **`> **Coming from Software Engineering?**`** blockquote callout near the
   top — the signature device. Most days have one; keep/extend it.
3. Prose + **Mermaid** diagrams + **Python** code blocks (each with a
   `# script_id:`).
4. **`## Summary`** — usually a Mermaid `mindmap`.
5. **`## Quick Reference`** — a table.
6. **`## Exercises`** — a numbered list.
7. **`## What's Next?`** — one short paragraph pointing to the **next day**.

When you add or edit a day, match this structure and the surrounding day's tone,
comment density, and formatting.

---

## 5. Models, providers, and library conventions

**Always defer to `REFERENCE.md` for exact model IDs and pricing.** Summary of
current conventions (verify before quoting numbers — they drift):

- **Anthropic:** `claude-opus-4-8` / `claude-opus-4-6`, `claude-sonnet-4-6`,
  `claude-haiku-4-5`. Use **bare** IDs (no date suffix). Recent models use
  **adaptive thinking** (`thinking={"type":"adaptive"}`, `output_config={"effort":...}`),
  **not** `budget_tokens`. `claude-haiku-4-5`, `claude-opus-4-6` are REAL — do
  not "correct" them to older names.
- **OpenAI:** SDK **v1+** — `client = OpenAI(); client.chat.completions.create(...)`,
  never module-level `openai.ChatCompletion.create`. Vision is in `gpt-4o`;
  `gpt-4-vision-preview` is deprecated.
- **Pricing/figures:** never bake a hard number without an "as of `<date>`,
  verify at the provider" caveat. Correct wrong numbers; don't invent precise
  ones.
- **Common library gotchas** (full list in `REFERENCE.md`): Pydantic v2
  (`@field_validator`, `Field(default_factory=...)`); `pypdf` (not `PyPDF2`);
  llama.cpp `llama-cli`/`llama-quantize`/`convert_hf_to_gguf.py`; Gradio 5
  `type="messages"`; RAGAS 0.2+ `EvaluationDataset`; FastAPI `lifespan` over
  `@app.on_event`; `ollama.embed(input=...)`.

**Never guess SDK signatures.** If you don't have verified docs for a library's
API (e.g. the Claude Agent SDK), don't fabricate call signatures — that's what
made Day 096 a credibility problem. Either verify against current docs or
implement the pattern on a surface you *can* verify (Day 096 now uses the plain
Messages API for this reason).

---

## 6. Maintenance workflow

1. **Change a fact in `REFERENCE.md` first** (model ID, price, day map), then
   update any lesson that restates it, then add a line to `CHANGELOG.md`.
2. **Run the checker** before committing:
   ```bash
   python3 tools/check_snippets.py        # exits non-zero on unbalanced fences
   python3 tools/check_snippets.py --strict   # also fail on python parse warnings
   ```
   CI runs this on push/PR. Default gate = fence parity (hard); parse failures
   are warnings (intentional fragments exist).
3. **Cross-reference discipline.** A past renumber left widespread rot: wrong
   "What's Next" footers, capstone day numbers that didn't match filenames, and
   two premature "course complete" blocks. When you touch a day, verify its
   "What's Next" points to the *actual* next day and any "Day N" references
   match the day map in §2 / `REFERENCE.md`.

---

## 7. Rules for editing (do / don't)

**Do:**
- Keep code runnable, current, and provider-accurate (learners copy it).
- Keep fences balanced and `script_id` grouping intact.
- Match the lesson structure (§4) and the neighbouring days' style.
- Fix factual/cross-reference errors freely; add "verify" caveats to volatile
  numbers.
- Surface anomalies (e.g. unexpected staged deletions, contradictions) instead
  of silently proceeding.

**Don't (without explicit user approval):**
- **Renumber or merge days.** The day count and numbering are load-bearing —
  changing them cascades across all 100 files, `index.md`, folder names, every
  cross-reference, and `REFERENCE.md`. This is high blast radius and hard to
  reverse. To add a topic, prefer **repurposing a thin/redundant day in place**
  (keep its number; update only that day + its neighbours' footers + the index).
- **Wholesale provider swaps** (changing the primary LLM provider across
  examples) — large, opinionated, product-level change.
- Fabricate SDK APIs you can't verify (§5).

---

## 8. Known state & open items (as of 2026-06)

- A full content-refinement pass fixed runnable-code bugs, cross-reference rot,
  the truncated Day 3, duplicated sections, and model/pricing accuracy. See
  `CHANGELOG.md`.
- **P0 consistency backfill done:** all 100 days now have the standard sections
  (Summary → Quick Reference → Exercises with collapsible solutions → What's
  Next). See `IMPROVEMENT_PLAN.md` for remaining workstreams (P1–P3).
- The checker reports **0 errors, 0 warnings** and CI runs in **`--strict`**.
  Intentional non-runnable blocks carry a `# fragment` marker that the checker
  skips — keep that marker when editing cheat-sheet/pseudo-code blocks.
- **Day 096** is deliberately implemented on the Messages API (patterns), with
  an accurate high-level pointer to the real Claude Agent SDK — not fabricated
  SDK code.
- **Deferred, needs user direction:** (1) consolidating redundant days
  (066/067, 069–071, 090/092, 044–046) and reinvesting the slots in gaps
  (reranking, retrieval eval, structured outputs, PII/data-privacy);
  (2) standardizing on a single primary provider. Both are product decisions —
  propose a plan and get sign-off before executing.
