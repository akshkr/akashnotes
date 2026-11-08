# Course Revamp Plan (v2)

> **Status: APPROVED 2026-11-06, executing.** This replaces the in-place, no-renumber
> approach in `RESTRUCTURE_PROMPT.md`. Progress: `.restructure/v2/STATUS.md`.
>
> **Owner decisions (2026-11-06):**
> 1. Keep exactly 100 days; a full re-sequence is allowed.
> 2. Provider: **OpenAI is primary** for all runnable code. Anthropic appears only in a
>    few places in the early introduction (e.g. the SDK intro), as an introduction.
> 3. Template (§5) approved.
> 4. Internal links: write normal markdown links wherever needed. The format can be
>    adjusted later.
> 5. Run the fresh 1-agent-per-day pass (1.1).
> 6. **No git commits and no branch for now.** Write the new tree to `v2/`; leave git
>    state untouched.
> 7. Models: summarization uses a lower model (Sonnet). All generation (research,
>    planning, writing, reviewing) uses **Opus at xhigh effort**. "I don't want flaws in
>    the content."

---

## 0. The request, restated

- **Task 1: redesign the syllabus.** Find the right teaching order for everyone. Find
  what's missing (important or recent). Remove what's redundant, outdated or unimportant.
  Method: per-day agent summaries, then compile, then add, then remove.
- **Task 2: rewrite every lesson** with parallel agents. Plan how each topic will be
  explained first, then write it. Keep the useful existing devices (SWE→AI callout,
  exercises/questionnaire) and drop the rest. Every lesson goes basic → detail and has
  well-placed examples, commented runnable code, diagrams, references/links and internal
  links, plus my own judgment.
- **Constraint: small contexts.** No agent reads many lessons. Work is split into small
  tasks.
- **Gate:** nothing runs until you approve.

## 1. Operating rules (context safety; these apply to every stage)

1. **The orchestrator (me) never opens a lesson body.** I work only from small digests
   on disk.
2. **Agent scopes are small and fixed:**
   - summarizer: 1 lesson
   - planner: one phase's *plans* (no lessons)
   - writer: 1 new lesson plus at most 3 old lessons it salvages from
   - reviewer: at most 3 lessons
3. **Shared docs are small and sliced.** `STYLE_GUIDE.md` is at most 150 lines.
   `FACTS_PACK/` is split by area, with each file at most 150 lines. An agent loads only
   the slices its topic needs.
4. **Agents write results to disk and reply in at most 5 lines.** I never paste digests
   into chat.
5. **Checkpoint.** `.restructure/v2/STATUS.md` is updated after every step, so any
   session can resume without redoing work.
6. **Isolation.** All work happens on branch `course-v2`. New lessons go into a staging
   tree `v2/`. The old `Phase_*` tree stays untouched as the salvage source until the
   final cutover.

## 2. Stage 0: housekeeping (needs your OK)

- Commit the current working tree (the staged Phase-1 reorder) as a baseline, so the old
  course can always be recovered. Exclude `temp.py`, which is a stray copy of a D004
  snippet. Unstage it and delete it.
- Create branch `course-v2`, add `.restructure/` to `.gitignore`, and commit per batch.
  Never push.

## 3. Task 1: syllabus

### 1.1 Per-day pass (1 agent per lesson, 100 agents, Sonnet, batches of about 20)
Inputs: one lesson plus its existing card from `.restructure/inventory/`.
Output: `.restructure/v2/days/Dxxx.md`, at most 15 lines:
```
### D014 <current title>
- heading: <=10 words
- summary: 1-2 lines
- concepts: <keys> | depth: intro / working / deep
- keep: <=3 assets worth salvaging (analogy, example, diagram, exercise) with line refs
- drop: <=3 outdated or redundant parts with line refs
- verdict: essential | useful | redundant-with Dxxx | outdated
```
The `keep:` line is new. Task 2 needs it ("keep what's useful"), and the old cards don't
have it.

### 1.2 Compile current coverage
- A **script** (no LLM) renders `CURRENT_SYLLABUS.md` as Day | heading | summary, for you
  to read.
- **1 agent** builds a coverage matrix from the 100 digests (about 20k tokens): which days
  teach each concept, and at what depth. It also flags redundancy clusters and forward
  dependencies. Output: `.restructure/v2/coverage.md`.

### 1.3 Find what's missing (3 research agents in parallel, with web access)
- **A. The 2026 AI-engineering landscape.** What the job expects now. Candidate topics,
  each with why it matters, evidence links and a priority.
- **B. Currency audit of every tool and library the course uses.** For each: keep,
  modernize or retire, with official doc links. Examples to check: CrewAI, AutoGen,
  GPTCache, NeMo, autoawq, LangChain 1.x, the LangGraph `interrupt()` API, MCP SDK
  high-level API, RAGAS.
- **C. The fresher lens.** Which prerequisites a fresher lacks (Python async, HTTP/JSON,
  venv, git, Docker, numpy). Proposal: short **primers in an appendix**, not days.

Each output is at most 80 lines.

### 1.4 Design `SYLLABUS_V2.md` (me, from the compact inputs only)
- The phase map, and one entry per day:
  ```
  ### Day 014 — <title>
  - why it matters: 1 line
  - you'll learn: 3 bullets
  - prereqs: Day 010, Day 012
  - stop at: <depth ceiling: what we deliberately do NOT go into, with a link out>
  - you'll build: <artifact>
  - salvage from: old D014 (Pydantic basics), old D029 (strict mode)
  - action: REWRITE | MERGE(old 4+5) | NEW
  ```
- An old→new mapping table, a retired list with a reason for each, and the capstone
  storyline.
- A concept→day map. Writers use it for internal links.

**Starting direction** (to be validated in 1.4, not fixed):

| # | Phase | ~Days | Notes |
|---|---|---|---|
| 0 | Start here | 2 | Career map; setup + first API call (fresher-friendly) |
| 1 | How LLMs work | 6 | Tokens, transformer intuition, sampling, context windows, model landscape (incl. reasoning and open models), cost/latency basics |
| 2 | Prompting & structured output | 12 | Messages, few-shot, CoT + reasoning models, SDKs, streaming, Pydantic + native structured outputs, retries, prompt caching, testing, **first eval set**, prompts-as-code, capstone 1 |
| 3 | RAG | 14 | Embeddings, parsing, chunking, pgvector, hybrid (BM25/RRF), pipeline, **retrieval eval**, reranking and query rewriting, advanced (contextual, GraphRAG optional), long context vs RAG, capstone 2 |
| 4 | Tools & MCP | 6 | Function calling, strict schemas, execution and errors, parallel calls, **MCP consume + build** |
| 5 | Agents | 14 | Loop, stop conditions/budgets, context engineering and memory, planning, LangGraph, durable state, HITL (`interrupt()`), tracing/debugging, agent SDKs, capstone 3, career checkpoint |
| 6 | Multi-agent | 6 | When (not) to, supervisor, handoffs, critic/debate, one framework, cost and tracing |
| 7 | Evaluation & observability | 10 | Tracing (OTel GenAI), judges + calibration, RAG/agent eval, eval datasets from traces, **evals in CI**, online monitoring |
| 8 | Safety & security | 8 | Injection, guardrails, output handling (XSS), sandboxing, PII, least-privilege tools, red-teaming, capstone 4 |
| 9 | Open models & fine-tuning | 8 | Local models, quantization, serving, should-you-fine-tune, synthetic data, LoRA, eval, distillation/routing |
| 10 | Production | 11 | API serving, async jobs, streaming transports, UIs, containers, cloud, resilience, caching, cost routing, auth, capstone 5 |
| 11 | Career | 3 | Interview, portfolio, launch |

Evals spiral through the course: first eval set (P2), retrieval eval (P3), agent eval
(P5), the full discipline (P7), and eval as a deploy gate (P10).

### 1.5 Stress test (3 agents in parallel, reading only `SYLLABUS_V2.md`)
- A fresher persona, a senior-SWE persona, and a curriculum red-team (ordering, forward
  dependencies, depth too deep or too shallow, gaps).
- Each writes at most 40 lines. I revise the syllabus from their notes.

### 🔒 Gate 2: you approve the syllabus.

## 4. Task 2: writing

### 2.1 Foundations (before anyone writes)
- **`STYLE_GUIDE.md`** (I write it): the template (§5), voice, depth rubric, and rules
  for code, diagrams and links.
- **`FACTS_PACK/`**: 4–6 research agents with web access verify current call patterns,
  versions, model IDs and official doc URLs, one area each:
  - LLM SDKs and structured outputs
  - RAG stack
  - agents/LangGraph
  - MCP
  - evals/observability
  - serving/fine-tuning

  Anthropic facts come via the `claude-api` skill. `REFERENCE.md` is updated from the
  pack first, per CLAUDE.md.
- **`LINKS.md`**: vetted URLs, each fetched and confirmed to return 200. Writers cite only
  these, or fetch-verify any new link.
- **Tooling**, extending `tools/`:
  - (a) "Day N" and internal-link resolver, plus a check that What's Next points to the
    next day
  - (b) stitched-script local-import check (would catch the D018/D048 bug)
  - (c) Mermaid render check via `mmdc`
  - (d) external link checker
  - (e) best-effort SDK signature check in a throwaway venv: do the called methods and
    kwargs exist?
  - (f) run pure-Python (no-network) scripts with a timeout
  - (g) single-file mode, so writers can check their own lesson

  CI gets (a) and (b), which are offline and cheap. (c)–(f) run locally at each batch
  gate.

### 2.2 Per-phase teaching plans (1 planner per phase, about 11 agents, no lesson reading)
Inputs: that phase's slice of the syllabus, `STYLE_GUIDE.md`, and the `days/Dxxx.md`
digests of its salvage sources. Output: one plan per day, at most 40 lines:
- hook
- SWE analogy, plus a fresher bridge (plain-language version)
- explanation ladder: intuition → concrete example → mechanism → code → production notes
- the running example
- diagrams to draw (type and what each shows)
- scripts (`script_id`: what each demonstrates)
- pitfalls
- 3–5 exercises
- internal links (which concept links to which day)
- references needed
- the stop line, and "not covered here (see Day N)"

One planner per phase keeps scope consistent and stops days within a phase from
overlapping.

### 2.3 Pilot (3 lessons end-to-end)
- Lessons: one concept day (Tokenization), one code-heavy day (structured outputs or tool
  calling), and one capstone.
- Full pipeline for each: writer → reviewer → fixes → all checks.

### 🔒 Gate 3: you review the 3 pilots. We tune the template and style guide, then scale.

### 2.4 Batch writing (one phase per batch, parallel)
- **1 writer per day.** Inputs: its day plan, the style guide, its `FACTS_PACK` slices and
  its source lessons (at most 3). It writes `v2/.../<slug>.md`, runs single-file checks,
  fixes problems, and replies in at most 5 lines.
- **1 reviewer per 2–3 days** (fresh eyes). It scores each lesson against the rubric in
  §6, fixes small issues directly, and sends bigger ones back for one fix pass.
- **Batch gate:** every tool in 2.1 passes. Then commit on `course-v2`, append the batch
  to the CHANGELOG, and update STATUS. You can review any batch before the next starts.
- Writers add internal links as they write. The syllabus's concept→day map fixes all
  numbering up front, so links can point forward and back from the start.

### 2.5 Global files and cutover
- Rebuild `index.md` from the syllabus, update `REFERENCE.md`, and rebuild
  `GLOSSARY.md`; lessons link to it at a term's first use.
- Update CLAUDE.md (new day map, template, rules) and CHANGELOG.
- Cutover: replace the old `Phase_*` trees with `v2/`, using `git mv` where a slug
  survives. Produce an **old→new URL map** for the frontend, YouTube links and any
  learner-progress data.

### 2.6 Final QA
- Run the full tool suite.
- Each per-phase arc reviewer reads only a script-extracted "At a glance" and "Key
  takeaways" for its phase, to check flow.

### 🔒 Gate 4: you review, then merge.

## 5. Proposed lesson template

| # | Section | Status |
|---|---|---|
| 1 | `# Title` + one-line hook | keep |
| 2 | **At a glance**: time · prerequisites (linked) · what you'll build | **new** |
| 3 | `> Coming from Software Engineering?` callout | **keep** (signature); the main text never depends on it, so freshers aren't lost |
| 4 | Core explanation, basic → detail, with examples placed where a concept first appears | rewrite |
| 5 | Optional depth/math in collapsible **Under the hood** asides | keep the rule |
| 6 | Mermaid diagrams wherever there is a flow, structure or state | keep, validated |
| 7 | Runnable, commented code: `pip install` line, `# script_id`, small blocks, cheap default models | keep, stricter |
| 8 | **Common pitfalls** | **new** |
| 9 | **Key takeaways** (5 bullets) | replaces the Summary mindmap + Checkpoint |
| 10 | Quick Reference table | keep |
| 11 | Exercises with collapsible solutions (the questionnaire) | keep |
| 12 | **References & further reading**: official docs first, verified links | **new** |
| 13 | What's Next: one paragraph that links the next day | keep |

## 6. Per-lesson quality bar (reviewer rubric, 1–5 each)
- **Accuracy:** matches `FACTS_PACK`; no unverified APIs; prices carry an "as of / verify"
  caveat.
- **Flow:** basic → detail, with no forward dependencies.
- **Examples:** concrete, and placed where each concept first appears.
- **Code:** runnable when stitched, commented with the *why*, `script_id` correct, no
  deprecated patterns.
- **Diagrams:** render cleanly and actually explain something.
- **Links:** internal links resolve; external links are vetted.
- **Depth:** stops at the declared ceiling.
- **Readability:** a fresher can follow it, and the SWE callout is useful.
- **Template:** all sections present.

## 7. Scale and cost (honest numbers)

| Stage | Agent runs |
|---|---|
| Task 1 | ~107 (100 per-day summarizers on Sonnet, 3 researchers, 1 compiler, 3 stress-testers) |
| Task 2 | ~160 (~6 fact researchers, ~11 planners, 100 writers, ~35 reviewers, fix passes, ~5 QA) |
| **Total** | **~270** |

- Writers are the bulk of the cost: each reads about 15–25k tokens and writes 6–10k.
  Several million tokens in all.
- This runs over several sessions. Batches go one phase at a time, so you can stop at any
  point and keep everything finished so far.
- Batches run as workflows you can watch in `/workflows`. That's well above the usual
  size guideline, which is why it's spelled out here for approval.

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Fabricated APIs or links | `FACTS_PACK` + signature check + link checker; "verify" labels where docs couldn't be confirmed |
| Voice drift across 100 writers | Style guide, pilot gate, one planner per phase, reviewers |
| Days overlapping | Per-phase plans fix each day's scope and "not covered here" |
| Context overflow | Fixed small scopes (§1) |
| Half-migrated course | Staging tree; cutover only at the end; per-batch commits |
| External breakage (URLs, YouTube links, progress) | Old→new map delivered at cutover |

## 9. Decisions needed before Stage 0
1. **Numbering:** keep exactly 100 days and allow a full re-sequence? (Recommended.)
2. **Primary provider for runnable code:** OpenAI, Anthropic, or provider-neutral? Either
   way, the other provider appears only where the APIs really differ.
3. **Template (§5):** approve it, including dropping the Summary mindmap + Checkpoint in
   favour of Key takeaways?
4. **Internal link format:** relative `.md` links, plain "Day N — Title" text, or your
   frontend's URL scheme?
5. **Step 1.1:** a fresh 1-agent-per-day pass (recommended), or reuse the old cards to
   save about 100 runs?
6. **Git:** commit the baseline (without `temp.py`) and commit per batch on `course-v2`,
   never pushing?
