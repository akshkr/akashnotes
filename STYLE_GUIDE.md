# STYLE_GUIDE: How every v2 lesson is written

This is the contract shared by planners, writers and reviewers. Where this guide is silent, see
`SYLLABUS_V2.md`. For exact paths and slugs, see `tools/day_map.json`. For APIs, model
IDs and prices, see `docs/facts_pack/`. For course data, see `DATASET_SPEC.md`.

## 1. Audience and voice
- **Readers:** working software engineers *and* freshers (new grads with basic Python). Every
  lesson must work for both groups: a full path for freshers, and a fast path for experienced
  engineers.
- **Voice:** second person, practical, direct and warm. Explain things the way a senior colleague
  would at a whiteboard. Avoid hype, vendor slogans and textbook tone.
- **Banned filler:** "just", "simply", "obviously", "as you know", "easy", "trivial",
  "in today's fast-paced world". Never write "as you've seen in prod". Write "teams do X because Y" instead.
- **Define before use.** At a term's first use, expand the acronym and give a one-clause plain
  definition. Each lesson introduces at most about 5 new terms, listed in At a Glance.
- **Two bridges for every key idea:**
  - the plain-language version, in the main text;
  - the SWE analogy, in the callout. If the analogy target isn't common knowledge (circuit breaker,
    ORM, DI), gloss it in one clause.
- **Math** goes in an optional `<details>` "Under the hood" aside. Use words → toy numbers →
  formula, in that order. Nothing on the critical path depends on it.

## 2. File layout and lesson anatomy (exact order and headings)

**Path:** `v2/<phase_dir>/<folder>/<slug>.md`, taken from DAY_MAP.json.

The H1 is the plain title: `# Structured Outputs: Native JSON Schema & Extraction`.
After the H1, the sections appear in this order:

1. **Hook paragraph.** 2–4 sentences on the problem and why you should care.
2. `## At a Glance`, a bullet list with these fields, in this order:
   - `**Time:** ~2 h core (+ optional Go Deeper) · **Depth:** working`
   - `**Prerequisites:**` linked days, plus primers if any
   - `**You'll build:**` the concrete artifact
   - `**Stops at:**` what is deliberately out of scope, copied from the syllabus
   - `**Fast path:**` "Already know X? Read §Y and do Exercise Z" (about 30–60 min)
   - `**Cost:**` "≈ $0.05 on `<default model>` (prices as of 2026-11, [verify](link))"
   - `**New terms:**` comma list, 5 at most
3. `> **Coming from Software Engineering?**` A blockquote callout of 3–6 sentences with the SWE
   analogy and what transfers. Freshers can skip it; the main text never depends on it.
4. **Core sections** (H2s with descriptive titles, not "Step 1"). Follow the explanation ladder:
   1. **Problem first:** a naive attempt failing, or a real need (≤3 sentences).
   2. **Plain intuition** with an everyday analogy.
   3. **Tiny worked example** by hand, small enough to check in your head.
   4. **Name the parts.** Introduce terms, plus a Mermaid diagram of the mechanism or flow.
   5. **Minimal runnable code.** ≤20 lines, sync, cheapest model, followed by its expected output.
   6. **Turn a knob / break it.** Change one thing and show the effect, including the most common
      failure and its real error text.
   7. **Realistic version.** Each block adds one concern (errors, async, types, cost), under the
      same `script_id`.
   8. **Trade-offs and when NOT to use it.** A decision table or rule of thumb, plus a short
      `### In production` subsection (≤5 bullets).
4b. `## Go Deeper (optional)`: one or more collapsible blocks,
    `<details><summary>Go deeper: <topic></summary> … </details>`. Each holds advanced material:
    - under-the-hood mechanics and math
    - extra variants and edge cases
    - production depth beyond the 5 bullets
    - "what experts also do"

    Each block is self-contained. Key Takeaways, core exercises and later days never depend on
    them. This is where depth goes, so the core stays at about 2 hours. Omit the section if there's
    nothing worth adding.
5. `## Common Pitfalls`: 3–6 bullets. Each gives the symptom (with real error text where possible),
   the cause and the fix.
6. `> **Where we stop:**` a one-sentence box: what is not covered, why, and a link for the curious
   (or "see [Day N](…)").
7. `## Key Takeaways`: exactly 5 bullets that test steps 1–8 of the ladder.
8. `## Quick Reference`: a table (API / pattern / when to use / gotcha).
9. `## Exercises`: tiered and numbered.
   - 1 **Warm-up** (modify the shown code), 2 **Core**, 1 optional **Stretch** (marked; may use Go
     Deeper material). That makes 4 in total. Each solution script is ≤40 lines.
   - Every exercise has a collapsible solution: a `<details>` block whose `<summary>` reads
     `Solution`. Put **a blank line after `<summary>…</summary>`** and before `</details>`, or the
     markdown inside won't render.
   - Solution code follows the code rules: its own script_id such as `…/solution_ex2`, or `# fragment`.
10. `## References & Further Reading`: 3–8 links. Official docs first, then the best practitioner
    sources. Each link gets a one-line "why read it".
11. `## What's Next`: one short paragraph linking the next day by its exact title.

**Day budget (≈2 h core path: reading + running code + exercises). Enforced by `lesson_check.py --budget`:**
- **Core prose** (everything outside `<details>`): 2,000–3,000 words. Hard limit 3,300.
- **Go Deeper** prose: ≤1,500 words.
- **Body scripts** (script_ids outside Exercises): **usually 7–8**. More only when the topic truly
  needs it (hard max 10). Concept-heavy days may have fewer.
- **Exercises:** 3 + 1 optional stretch; each solution ≤40 lines.
- **Capstones:** may use up to about 1.5× the script count; the prose budget is the same.

Prefer cutting repetition to cutting clarity. If something is valuable but not core, move it to Go
Deeper rather than deleting it.

## 3. Code rules (learners copy this code, so it must run)
- **Python 3.11+.** **OpenAI Python SDK 3.x, Responses API** (`client.responses.create/parse/stream`).
  Chat Completions appears only in D12's comparison box, labelled "legacy / compatibility".
  Anthropic appears only in D2 and D7.
- **Model IDs** come from FACTS_PACK. Every lesson declares them once:
  `MODEL = os.environ.get("ATLAS_MODEL", "<cheapest current model>")`. Never hard-code a retired
  ID (gpt-4o, gpt-4o-mini, gpt-4.1, o3, whisper-1).
- **Every** ```python block's first line is `# script_id: <script_id_prefix><name>`, using the prefix
  from DAY_MAP. Blocks that share an id are stitched in document order into ONE file, which must
  parse and run top to bottom. Non-runnable illustrations (a lone method, pseudo-code, a cheat sheet)
  carry `# fragment` on their second line.
- **Each script starts with a header comment** listing install (`uv add …`), required env vars,
  and services (e.g. "needs Postgres from compose.yaml").
- **Non-capstone lessons are self-contained.** If you need an earlier day's helper, include a compact
  version inline with a comment such as `# built on Day 12 — see ../../…`. Never import across lessons.
- **Capstones are multi-file projects:** one script_id per file, named by module path
  (`day_022_capstone_r1_extractor/atlas/schemas`). Sibling files import each other as
  `from atlas.schemas import Issue`. Never import a name from a module whose code sits in the *same*
  script_id. (This assumes the pipeline writes each id to `<script_id>.py`; flag anything that
  conflicts.)
- **Style:**
  - Blocks are ≤40 lines.
  - Comments explain *why*, not *what*.
  - Type hints on public functions.
  - Use the stdlib where reasonable.
  - Sync code first. Async appears only from D12 as optional, and is required from D22.
- **Show expected output** in a ```text block after runnable code (mark it "your numbers will differ").
- **Never put a secret in code.** Read keys from the environment. Never print keys. Make side
  effects (sending, deleting, posting) require explicit approval in examples.
- **Forbidden** (the checker enforces most of these): module-level `openai.ChatCompletion`;
  `response_format={"type":"json_object"}` (except one labelled comparison); `PyPDF2`; Pydantic v1
  `@validator`; FastAPI `@app.on_event`; `budget_tokens`; date-suffixed Claude IDs; Gradio
  `type="messages"`; `ragas.evaluate()` as the main path; `langgraph.prebuilt.create_react_agent`;
  low-level MCP `Server` boilerplate; GPTCache; OpenAI fine-tuning jobs; the OpenAI Evals platform;
  the Assistants API.
- **Verify, don't guess.**
  - Use only API shapes confirmed in FACTS_PACK, or ones you confirm yourself: introspect the
    installed package in a throwaway venv, or read the official docs or source.
  - If you can't confirm something, leave it out, or describe it in prose with "⚠ verify against
    current docs".
  - Never invent a parameter, model ID, price or URL.
- **Prices and figures** always carry "as of 2026-11, verify at <link>".

## 4. Diagrams
- Mermaid only: `flowchart`, `sequenceDiagram`, `stateDiagram-v2`, `classDiagram`, `mindmap`
  (sparingly).
- Draw a diagram wherever there is a flow, a structure, a lifecycle or a decision. Most lessons have 2–4.
- Keep each diagram to about 15 nodes. Label the edges, use plain words in node text, and quote
  labels that contain punctuation: `A["Model (proposes)"]`.
- Every diagram must render. `lesson_check.py --mermaid` runs `mmdc` on each one.

## 5. Links
- **Internal** links are relative, from the lesson file to the target file, always in this form:
  `[Day 15: Pydantic for LLM Apps](../../Phase_2_Building_with_LLM_APIs/Day_015_pydantic_for_llms/pydantic_for_llms.md)`.
  Use DAY_MAP for exact paths. Link every prerequisite in At a Glance, the first mention of a
  concept taught on another day, and What's Next. Forward pointers are allowed ("we go deeper in
  [Day 49](…)").
- **Primers:** `../../Appendix_Primers/<file>.md` (file names in §8).
- **External** links: use only URLs listed in FACTS_PACK, or URLs you fetched yourself and saw
  return 200. No invented or guessed URLs. Prefer stable official doc pages over blog posts.

## 6. The product thread: "Atlas" over the Orbit dataset
Learners build **Atlas**, an AI assistant for the maintainers of **Orbit**, a fictional open-source
Python background-jobs library. The data lives in `datasets/orbit/` (see `DATASET_SPEC.md`):
docs, issues, a SQLite DB and eval seeds. Code reads it via
`DATA_DIR = Path(os.environ.get("ORBIT_DATA", "datasets/orbit"))`. Use Orbit data in examples
instead of toys whenever it fits. Toy data is allowed only for a "tiny worked example" (ladder step 3).

**Atlas module map.** Every lesson uses the same names, so the code reads as one growing codebase.

| Module | Main names | Introduced |
|---|---|---|
| `atlas/config.py` | `MODEL`, `EMBED_MODEL`, `DATA_DIR` | D2 / D12 |
| `atlas/llm.py` | `client`, `complete()`, `CostTracker`, `log_call()` | D12 |
| `atlas/tokens.py` | `count_tokens()`, `estimate_cost()` | D4 |
| `atlas/prompts/` + `registry.py` | `load_prompt(name, version)` | D9 / D21 |
| `atlas/schemas.py` | `Issue`, `IssueRecord`, `DocChunk`, `Citation`, `Answer` | D15–16 |
| `atlas/extract.py` | `extract_issue()`, `reliable_extract()` | D16–17 |
| `atlas/evals/` | `run_eval()`, checks, judges | D20 / D30 / D45 |
| `atlas/ingest.py` | `load_document()`, `chunk()` | D24–25 |
| `atlas/index.py` | `Index.upsert()`, `.search()`, `.hybrid_search()` | D26–27 |
| `atlas/rerank.py` | `rerank()` | D31 |
| `atlas/rag.py` | `ask()` | D28 |
| `atlas/sql.py` | `ask_sql()` | D33 |
| `atlas/tools.py` | `@tool`, `TOOLS`, `dispatch()`, `ToolExecutor`, `envelope_ok/err`, `TransientToolError`/`PermanentToolError` | D35–37 |
| `atlas/tracker.py` | `MockTracker` (`add_label`, `post_comment`, `actions`) | D37 (D55 extends) |
| `atlas/mcp_server.py` | Atlas MCP server (`search_docs`, `ask`) | D40 |
| `atlas/workflows.py` | `route_issue()` | D41 |
| `atlas/tracing.py` | `setup_tracing()` | D12 / D42 |
| `atlas/agent.py` | `run_agent()`, `AgentResult` | D48 |
| `atlas/context.py`, `memory.py` | `ContextManager`, `MemoryStore` | D49 / D50 |
| `atlas/graph.py` | `build_investigator_graph()` | D53–55, D61 |
| `atlas/api/`, `atlas/ui/` | FastAPI app, Gradio app | D77+, D34 / D79 |
| `atlas/plan.py` · `agentic_rag.py` | `make_plan()`/`replan()` · `agentic_ask()` | D51 · D52 |
| `atlas/sdk_agent.py` · `pydantic_agent.py` | `build_sdk_agent()`/`run_sdk_agent()` · `build_pydantic_agent()` | D56 · D57 |
| `atlas/debug.py` · `atlas/evals/agent_evals.py` | `detect_failures()` · `run_agent_suite()` (D62 adapts a compact copy) | D58 · D59 |
| `atlas/data.py` · `atlas/batch.py` · `atlas/costs.py` | `load_jsonl()`/`load_issues()` · batch runs · `cost_from_usage()`, `Budget`/`BudgetExceeded` | D10/D15 · D18 · D18 |
| `atlas/evals/checks.py`, `runner.py`, `gate.py` | code-based checks, `run_eval()`, the pass-rate gate | D20 |
| `atlas/pipeline.py`, `report.py`, `cli.py` | the R1 pipeline (`DocPage`/`DocRecord`/`extract_doc`) | D22 |
| `atlas/tracker.py` · `atlas/mcp_client.py` | `MockTracker` (add_label, post_comment) · `mcp_tools_as_functions()`, `call_mcp_tool()` | D37 · D39 |
| `atlas/evals/datasets.py`, `analysis.py`, `judges.py`, `agreement.py`, `ci.py` | `EvalCase`/`generate_cases()` · `FailureMode`/`build_taxonomy()` · `RUBRICS`/`make_judge()` · `agreement()`/`swap_test()` · `select_suite()`/`run_with_repeats()` | D43 · D44 · D45 · D46 · D47 |
| `atlas/multi_agent.py` · `atlas/triage_agents.py` · `atlas/debate.py` | `run_subagent()`, `RunStats` · `TriageDecision`, `HandoffNote` · `debate()`, `Verdict` | D64 · D65 · D67 |
| `atlas/graph.py` (+) · `atlas/llm.py` (+) | `build_supervisor_graph()` · **`AgentBudget`, `BudgetExceeded`, `agent_span`** (they live in `llm.py`, not a separate module) | D66 · D67 |
| `atlas/config.py` (+) · `atlas/finetune/data.py` · `atlas/evals/compare.py` | `LOCAL_MODEL` (default **`qwen3:4b-instruct-2507-q4_K_M`**, the same build D95 fine-tunes), `make_client()` · `SYSTEM_PROMPT_EXTRACT`, `build_dataset()` · `Candidate`, `go_no_go()` | D91 · D94 · D96 |
| `atlas/api/{app,models,events,ws}.py` · `atlas/services.py` | `create_app`, `AskRequest`/`AskResponse`, `AgentEvent`, `to_sse` · `AtlasServices` | D77 (ws: D79) |
| `atlas/jobs.py` · `atlas/ui/app.py`, `atlas/ui/components.py` · `atlas/voice.py` | `submit_background`, `enqueue_report` · `build_ui`, `safe_markdown`, `COMPONENTS` · `voice_turn` | D78 · D79/D80 · D81 |
| `atlas/config.py` (+ `Settings`) · `scripts/smoke_test.py` | `Settings.from_env` added **below** the existing `MODEL`/`DATA_DIR`/`EMBED_MODEL` constants (never replace them) | D82 |
| `atlas/api/auth.py`, `atlas/tenancy.py`, `atlas/quotas.py` | `Principal`, `require_scope` · `tenant_key`, `assert_owner` · `PlanLimits` | D83 |
| `atlas/resilience.py` · `atlas/cache.py`, `atlas/model_router.py` | `RetryPolicy`, `CircuitBreaker`, `ResilientLLM` · `SemanticCache` · `choose_model` | D84 · D85 |
| `atlas/monitoring.py`, `atlas/feedback.py` · `atlas/flags.py` · `atlas/ops.py`, `atlas/index_migration.py`, `scripts/game_day.py` | `EventLog`, `evaluate_alerts` · `canary_gate` · `set_override`, `dual_write`/`backfill` | D86 · D87 · D88 |
| `scripts/assemble_r5.py` · `atlas/slo.py`, `atlas/chaos.py` | carries D77–D88 files into R5 · SLOs and error budgets, the chaos drill | D89 · D90 |

**The full per-day contracts live in the phase briefs `.restructure/v2/plans/PHASE_*.md`.** They extend this map with the exact signatures (for example `MockTracker` D37, `step_span` D42, `make_judge` D45, `run_suite`/`gate` D47). When this map and a phase brief disagree, the phase brief wins.

## 7. Owned topics (teach once; later days cover only the delta)
| Topic | Owner |
|---|---|
| Cost tracker | D12 |
| Provider prompt caching | D18 |
| Hosted `file_search` | D32 |
| ACL filters | D27 |
| Evaluator–optimizer | D41 |
| Failure-taxonomy method | D44 |
| Idempotent side effects | D54 |
| Sub-agent isolation | D64 |
| `store=False` / retention | D73 |
| SSE over HTTP | D77 |
| Background mode | D78 |
| Tenant isolation | D83 |
| Backoff / circuit breakers | D84 |
| Semantic cache + routing | D85 |
| Migration playbook | D87 (drill in D21) |
| Redis basics | D78 |
| Traffic replay + alerts | D86 |
| Index migration + kill switches | D88 |
| Load-test harness | D90 (reused by D93) |

A day that reuses an owned topic links to the owner in one line and adds only what is new.

## 8. Appendix primers (outside the 100 days)
**Path:** `v2/Appendix_Primers/<file>.md`.

| File | Topic |
|---|---|
| `A01_terminal_git_github` | Terminal, Git & GitHub |
| `A02_project_setup_secrets` | Project setup & secrets |
| `A03_python_for_this_course` | Python for this course |
| `A04a_async_python_basics` | Async Python I |
| `A04b_async_python_concurrency` | Async Python II |
| `A05_http_json_apis` | HTTP, JSON & APIs |
| `A06_numpy_vectors` | NumPy & vectors |
| `A07_sql_postgres` | SQL & Postgres |
| `A08_docker_compose` | Docker & compose |
| `A09_pytest_and_ci` | pytest & CI |
| `A10_backend_production_vocabulary` | Backend & production vocabulary |
| `A11a_model_words` | Model words |
| `A11b_training_vocabulary` | Training vocabulary |
| `A12_eval_metrics_basics` | Eval metrics basics |
| `A13_typescript_for_ai_engineers` | TypeScript for AI engineers |

**Primer anatomy:**
1. `# Title`
2. `## Who this is for` (with "skip if…")
3. 3–6 short H2 sections (about 1,200–2,000 words in total) using the same ladder, with runnable
   examples. script_ids use the form `primer_a04a/<name>`.
4. `## Self-Check` (5 questions with collapsible answers)
5. `## Learn More` (2–4 verified free resources)

## 9. Definition of done (writer runs these; reviewer re-checks)
- `python3 tools/lesson_check.py <file> --mermaid --budget` reports 0 errors (budget warnings are acceptable only if justified). Run `--online` once at the end
  to check external links.
- No forward dependency: anything used comes from an earlier day, or is taught in this lesson.
- Every ⚠ verify item in the day's plan is resolved, or explicitly labelled in the text.
- Key Takeaways, Exercises and the stop line match the syllabus entry.
- Atlas names follow §6; owned topics follow §7.
