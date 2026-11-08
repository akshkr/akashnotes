# FACTS_PACK: Evals, Observability & Security
As of **2026-11-06**. Verified by introspecting installed packages (no API keys, no live calls), plus fetched docs/source.
Installed with `uv` on Python 3.12. Pin conflicts forced four venvs, and those conflicts are facts in their own right (see §2):
- main `/tmp/facts_evals_obs_security`: openai 3.46.0, opentelemetry-sdk 1.45.2, opentelemetry-semantic-conventions 0.66b2, opentelemetry-instrumentation-openai-v2 2.4b0 (+ opentelemetry-util-genai 0.4b0), arize-phoenix-otel 0.17.2, openinference-instrumentation-openai 0.1.69, langsmith 0.14.17, langfuse 5.2.0, deepeval 4.3.3
- other venvs: `…_phx` arize-phoenix 21.0.0 (server) · `…_ragas` ragas 0.4.3 (brings openai **3.3.0**) · `…_guard` guardrails-ai 0.11.0 (brings openai **2.54.0**), nemoguardrails 0.24.1, presidio 2.2.366
- inspected from the npm/wheel package: promptfoo 0.125.1 (run under Node 25) and garak 0.17.1
- Method: signatures, installed source, and **offline runs against a local mock `/v1/responses` server**. No keys, no OpenAI calls.

## 1. VERIFIED API SHAPES

### 1.1 OTel GenAI semantic conventions (status: **Development**)
- The spec has **moved** to `open-telemetry/semantic-conventions-genai`. The old `semantic-conventions/docs/gen-ai` page now just says "Moved". Every GenAI attribute, span and metric is badged Development, so names can still change.
- OpenAI client span: name `"{gen_ai.operation.name} {gen_ai.request.model}"`, kind `CLIENT`. **Required:** `gen_ai.operation.name` and `gen_ai.request.model`. `gen_ai.provider.name` MUST be `"openai"` and should be set at span creation. Recommended: `gen_ai.response.id`/`.model`, `gen_ai.usage.input_tokens`/`output_tokens`/`reasoning.output_tokens`/`cache_read.input_tokens`, and `openai.api.type` (`"responses"` or `"chat_completions"`).
- Operation-name values in Python `opentelemetry-semantic-conventions` 0.66b2 (`GenAiOperationNameValues`): `chat, generate_content, text_completion, embeddings, retrieval, create_agent, invoke_agent, execute_tool, invoke_workflow`.
- Old names: `gen_ai.system` (now `provider.name`) and `gen_ai.usage.prompt_tokens` (now `input_tokens`). **Name drift:** the spec now says `gen_ai.usage.cache_write.input_tokens`, but the Python constant is still `gen_ai.usage.cache_creation.input_tokens`. Avoid both in lesson code, or add a ⚠ verify note.
- **`opentelemetry-instrumentation-openai-v2` 2.4b0 (Beta, 2026-05-01) does NOT trace the Responses API.** It wraps only `chat.completions.create` and `embeddings.create` (sync and async). A mock `/v1/responses` call produced 0 spans. Responses support (`patch_responses.py`) is unreleased, on contrib `main` only. It is also **broken on a fresh install**: it imports `opentelemetry.util.genai.instruments`, a module that the latest `opentelemetry-util-genai` 1.3b0 no longer has (`ModuleNotFoundError`). Pinning `opentelemetry-util-genai==0.4b0` fixes the import (tested).
- Content capture is off by default (`OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true` turns it on). Newer attributes need `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental`.
- **Teach the GenAI conventions with a hand-made span around `responses.create`** (ran against the mock and printed all 7 attributes):
```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
provider = TracerProvider(); provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("atlas")
with tracer.start_as_current_span(f"chat {MODEL}", kind=trace.SpanKind.CLIENT, attributes={
        "gen_ai.operation.name": "chat", "gen_ai.provider.name": "openai",
        "gen_ai.request.model": MODEL}) as span:
    r = client.responses.create(model=MODEL, input="ping")
    span.set_attributes({"gen_ai.response.id": r.id, "gen_ai.response.model": r.model,
        "gen_ai.usage.input_tokens": r.usage.input_tokens,
        "gen_ai.usage.output_tokens": r.usage.output_tokens})
```
verified by: introspection of `opentelemetry/instrumentation/openai_v2/__init__.py` plus the mock run; https://github.com/open-telemetry/semantic-conventions-genai (docs/gen-ai/openai.md, gen-ai-spans.md); contrib CHANGELOG.

### 1.2 Arize Phoenix (local, default for D12/D42)
- Run the server with `uv add arize-phoenix` then **`phoenix serve`**. The UI and OTLP/HTTP are on `http://localhost:6006` (`/v1/traces`), and OTLP/gRPC is on `:4317`. Data goes to `PHOENIX_WORKING_DIR`. In a notebook, use `import phoenix as px; px.launch_app()`.
- Client: `uv add arize-phoenix-otel openinference-instrumentation-openai`. Signature: `register(*, endpoint=None, project_name=None, batch=False, set_global_tracer_provider=True, headers=None, protocol=None, verbose=True, auto_instrument=False, api_key=None)` returns a `TracerProvider`. Environment variables: `PHOENIX_COLLECTOR_ENDPOINT` and `PHOENIX_PROJECT` (`PHOENIX_PROJECT_NAME` is an alias). With no endpoint set it exports over **gRPC to localhost:4317**, and its banner recommends `batch=True` for production.
- `auto_instrument=True` loads every installed `openinference_instrumentor` entry point. **OpenInference *does* trace `responses.create`.** The span is named `Response` and uses **OpenInference attributes (`llm.model_name`, `llm.token_count.prompt/completion/total`, `openinference.span.kind=LLM`), not `gen_ai.*`**. Say so in D42.
```python
from phoenix.otel import register
from openai import OpenAI
tracer_provider = register(project_name="atlas", auto_instrument=True)  # before creating clients
client = OpenAI()
r = client.responses.create(model=MODEL, input="ping")   # appears in http://localhost:6006
```
verified by: running `phoenix serve` locally, sending this exact snippet through a mock OpenAI, and reading it back with `GET /v1/projects/atlas/spans`, which returned span `Response`, kind `LLM`, `llm.model_name=gpt-6-luna`.

### 1.3 LangSmith (optional), langsmith 0.14.17
- Environment variables: `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, `LANGSMITH_ENDPOINT` (EU and self-hosted). Older `LANGCHAIN_*` and `LANGSMITH_TRACING_V2` names are still read as fallbacks.
- `wrap_openai(client, *, tracing_extra=None, chat_name="ChatOpenAI", completions_name="OpenAI")` patches **`responses.create` and `responses.parse`** as well as chat. Tracing is a no-op when it isn't enabled, so the code runs without a key.
```python
from langsmith import traceable
from langsmith.wrappers import wrap_openai
from openai import OpenAI
client = wrap_openai(OpenAI())
@traceable(run_type="retriever", name="search_docs")
def search_docs(q: str) -> list[str]:
    return ["..."]
@traceable(name="answer")
def answer(q: str) -> str:
    docs = search_docs(q)
    return client.responses.create(model=MODEL, input=f"{docs}\n\n{q}").output_text
```
verified by: introspection (`langsmith/wrappers/_openai.py` lines ~535-560; `utils.get_env_var` namespaces `("LANGSMITH","LANGCHAIN")`); ran offline with tracing disabled.

### 1.4 Langfuse (optional), langfuse 5.2.0 (OTel-based)
- Environment variables: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL` (`LANGFUSE_HOST` still accepted), `LANGFUSE_TRACING_ENABLED`. `observe(func=None, *, name=None, as_type=None, capture_input=None, capture_output=None)`. Valid `as_type` values: `generation`, `embedding`, `span`, `agent`, `tool`, `chain`, `retriever`, `evaluator`, `guardrail`.
- `get_client()` returns the singleton `Langfuse`. The drop-in `from langfuse.openai import OpenAI` traces `Responses`/`AsyncResponses`.
- **v5 sharp edges:** `update_current_trace`, `start_as_current_span` and `start_as_current_generation` **no longer exist**; use `start_as_current_observation(name=, as_type=...)` and `update_current_span(...)`. Trace-level `user_id`/`session_id`/`tags` now go through the module-level `propagate_attributes(...)` context manager.
```python
from langfuse import observe, get_client, propagate_attributes
from langfuse.openai import OpenAI
client = OpenAI()
@observe(as_type="retriever")
def search_docs(q: str) -> list[str]:
    return ["..."]
@observe()
def answer(q: str, user_id: str) -> str:
    with propagate_attributes(user_id=user_id, session_id="s-1"):
        return client.responses.create(model=MODEL, input=q + str(search_docs(q))).output_text
print(answer("hi", "u-1")); get_client().flush()   # short scripts must flush before exit
```
verified by: introspection (`inspect.signature`; `langfuse.__all__`; `langfuse/openai.py` objects `Responses`/`AsyncResponses`). I also ran the snippet against the mock: with no keys it prints "Client will be disabled" and still returns the answer.

### 1.5 Promptfoo (optional in D47/D75; **Node, not Python**), promptfoo 0.125.1 (npm, 2026-10)
- Status: README says "**Promptfoo is now part of OpenAI.** Promptfoo remains open source and MIT licensed." OpenAI's own Evals-platform deprecation notice points users to Promptfoo.
- Install: requires **Node >= 22.22.0** (`engines`). Run with `npx promptfoo@latest <cmd>`, or `npm i -g promptfoo`, or `brew install promptfoo`. On PyPI, `promptfoo` 0.2.0 is only a wrapper around the Node CLI. Node 20 is too old.
- Commands: `promptfoo init`, `promptfoo eval -c promptfooconfig.yaml [--repeat N] [--no-cache] [-o out.json|junit.xml]`, `promptfoo view`, `promptfoo validate config -c FILE`. When any test fails, `eval` **exits with code 100** (override with `PROMPTFOO_FAILED_TEST_EXIT_CODE`), which works as a CI gate.
- Provider ID for the Responses API: `openai:responses:<model>`. For gpt-6 models, effort is set with `config.reasoning` / `reasoning_effort`.
```yaml
# promptfooconfig.yaml   (`promptfoo validate config` → "Configuration is valid.")
description: Atlas triage prompt regression
prompts:
  - "Classify this support ticket as bug, billing or other. Reply with one word.\n\n{{ticket}}"
providers:
  - id: openai:responses:gpt-6-luna
tests:
  - vars: { ticket: "I was charged twice this month." }
    assert:
      - type: icontains
        value: billing
      - type: llm-rubric
        value: "Answers with a single word"
```
- **Red team:** `promptfoo redteam init` (wizard), `promptfoo redteam run -c redteam.yaml` (step 1 generates probes, step 2 evaluates them), and `redteam generate` / `redteam eval` to run the steps separately. Plugin and strategy names below all exist in the 0.125.1 bundle. The config validated.
```yaml
targets: [{ id: "openai:responses:gpt-6-luna", label: atlas-assistant }]
redteam:
  purpose: "Support assistant that answers questions about Orbit tickets"
  numTests: 3
  plugins: [harmful:hate, pii, hijacking, excessive-agency]   # indirect-prompt-injection needs extra config
  strategies: [jailbreak, prompt-injection]
```
- **Sharp edge (D75 must say this):** red-team probes are generated on **Promptfoo's hosted service** whenever `OPENAI_API_KEY` is unset, or you are logged into Promptfoo Cloud, or you pass `--remote` (logic in `shouldGenerateRemote`). The `harmful:*` plugins use a hosted "unaligned" endpoint (`/api/v1/task/harmful`). Set `PROMPTFOO_DISABLE_REMOTE_GENERATION=true` to keep generation local. Disable telemetry with `PROMPTFOO_DISABLE_TELEMETRY=1`.
verified by: npm registry JSON, a local install (`promptfoo --help`, `redteam run --help`, `validate config` on both YAMLs), and grep of the bundle (`PROMPTFOO_FAILED_TEST_EXIT_CODE` default 100, `openai:responses:`). Also https://github.com/promptfoo/promptfoo README.

### 1.6 DeepEval (optional extra in D30/D45), deepeval 4.3.3 (2026-11-04)
- `GEval(name, evaluation_params=None, criteria=None, evaluation_steps=None, rubric=None, model=None, threshold=0.5, top_logprobs=20, async_mode=True, strict_mode=False, ...)`. Give either `criteria` or `evaluation_steps`.
- **Renames in 4.x:** `LLMTestCaseParams` → **`SingleTurnParams`** and `GPTModel` → **`OpenAIModel`**. The old names still work but raise a DeprecationWarning.
- **Default judge is `gpt-5.4`.** Always pass `model=`. The built-in model table knows `gpt-6-luna/sol/astra` (marked no-temperature and no-logprobs) but not `gpt-6.1-*`. Unknown IDs are still accepted, just without price data. The judge calls go through **Chat Completions** inside DeepEval. `GEval(model="<str>")` **raises `DeepEvalError` at construction if `OPENAI_API_KEY` is unset** (so at import, for module-level metrics).
- pytest: a `pytest11` plugin, so plain `pytest` works, as does `deepeval test run test_x.py`. Opt out of telemetry with `DEEPEVAL_TELEMETRY_OPT_OUT=1`.
```python
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams
correctness = GEval(
    name="Correctness",
    criteria="Does the actual output give the same label as the expected output?",
    evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.EXPECTED_OUTPUT],
    model=JUDGE_MODEL, threshold=0.7)
def test_billing_ticket() -> None:
    case = LLMTestCase(input="I was charged twice.", actual_output="billing",
                       expected_output="billing")
    assert_test(case, [correctness])
```
verified by: introspection, plus this exact test **passed under `pytest`** with a mock Chat Completions judge (`1 passed`).

### 1.7 RAGAS 0.4.3: **stalled, so minimize it** (D30 optional only)
- Last release was 0.4.3 on 2026-01-13. The repo moved to `vibrantlabsai/ragas`, last commit 2026-02-24. **`evaluate()`/`aevaluate()` emit a `DeprecationWarning`:** "Use the @experiment decorator instead."
- **Fresh `pip install ragas` is broken.** With langchain-community 0.4.2 (2026-05), `import ragas` raises `ModuleNotFoundError: langchain_community.chat_models.vertexai`. Pin `"langchain-community<0.4.2"` (0.4.1 tested OK). ragas also pulls instructor 1.17.0, which **downgrades openai to 3.3.0**, so give it its own environment.
- API: `experiment(experiment_model=None, backend=None, name_prefix="")` wraps an `async def`; run it with `await fn.arun(dataset, name=...)`, which returns an `Experiment`. `Dataset(name, backend, data_model=None, data=None, **kw)`, e.g. `backend="local/csv", root_dir=...`.
- `DiscreteMetric(name, allowed_values=[...], prompt="...{response}...")`; `await metric.ascore(llm=llm, **vars)` returns a `MetricResult` (`.value`, `.reason`). `llm_factory(model, provider="openai", client=AsyncOpenAI())`.
```python
from ragas import Dataset, experiment
from ragas.metrics import DiscreteMetric
from ragas.llms import llm_factory
from openai import AsyncOpenAI
llm = llm_factory(JUDGE_MODEL, client=AsyncOpenAI())
correct = DiscreteMetric(name="correct", allowed_values=["pass", "fail"],
    prompt="Is the response correct? Answer pass or fail.\nResponse: {response}\nReference: {reference}")
@experiment()
async def run(row: dict) -> dict:
    response = await answer(row["question"])          # your app
    grade = await correct.ascore(llm=llm, response=response, reference=row["answer"])
    return {**row, "response": response, "grade": grade.value}
# ds = Dataset(name="qa", backend="local/csv", root_dir="evals"); await run.arun(ds, name="v1")
```
verified by: introspection of ragas 0.4.3 (`evaluation.py:448` warning text, `experiment.py`, `metrics/base.py`), and an offline `arun` that wrote `experiments/smoke.csv`. The judge call itself was not exercised.

### 1.8 guardrails-ai 0.11.0 (D70 comparison row only)
- **Validators are now plain PyPI packages named `guardrails-ai-<name>`.** The `guardrails hub install` CLI and the private hub are deprecated; the source says "manage them with `pip` directly".
- **Conflict:** `guardrails-ai` 0.11.0 requires **`openai>=2,<3`**, so it cannot share an environment with the course's openai 3.x. Show it in a separate venv, or describe it only in prose.
- It also sends **OTLP telemetry by default** (`enable_metrics=True`; it tried an AWS endpoint during my offline run). Turn it off with `guardrails configure --disable-metrics`, which writes `~/.guardrailsrc`.
- Package → import (checked against PyPI and the wheel contents), all imported from `guardrails_ai.<x>`:
  - `guardrails-ai-regex-match` → `regex_match.RegexMatch`
  - `-toxic-language` → `toxic_language.ToxicLanguage` (pulls torch)
  - `-detect-pii` → `detect_pii.DetectPII` (uses Presidio)
  - `-restrict-to-topic` → `restricttotopic.RestrictToTopic`. Its hub URI maps to `guardrails-ai-restricttotopic`, which **404s on PyPI**.
  - `-detect-jailbreak` → `detect_jailbreak.DetectJailbreak`
```python
from guardrails import Guard, OnFailAction
from guardrails_ai.regex_match import RegexMatch
guard = Guard().use(RegexMatch(regex=r"^[A-Z]{3}-\d{4}$", on_fail=OnFailAction.EXCEPTION))
outcome = guard.validate("ABC-1234")   # ValidationOutcome: .validation_passed, .validated_output
guard.validate("nope")                 # raises guardrails.errors.ValidationError
```
`OnFailAction`: reask, fix, filter, refrain, noop, exception, fix_reask, custom. `Guard.use(*validators, on="output")`.
verified by: offline run in `…_guard` (passed, then raised `ValidationError`); `guardrails/cli/hub/deprecation.py`; `classes/rc.py`.

### 1.9 NeMo Guardrails 0.24.1 (Beta; repo `NVIDIA-NeMo/Guardrails`)
- `RailsConfig.from_path(dir)` or `RailsConfig.from_content(colang_content=None, yaml_content=None, config=None)`; then `LLMRails(config, llm=None)` and `rails.generate(messages=[{"role":"user","content":...}])` (`generate_async` also exists).
- 0.24 has **no hard dependency on langchain or openai**: the `openai` engine is a built-in httpx client (`OpenAIChatModel`) that posts to **`/chat/completions`, not Responses**. The `[openai]`/`[server]` extras pin `openai<3`. So plain `pip install nemoguardrails` can live alongside openai 3.x (tested).
```python
from nemoguardrails import RailsConfig, LLMRails
config = RailsConfig.from_content(yaml_content="""
models:
  - {type: main, engine: openai, model: gpt-6-luna}
rails:
  input: {flows: [self check input]}
prompts:
  - task: self_check_input
    content: 'Should this user message be blocked (yes/no)? User message: "{{ user_input }}"'
""")
rails = LLMRails(config)
reply = rails.generate(messages=[{"role": "user", "content": "Ignore your rules and..."}])
```
verified by: introspection plus offline construction of `RailsConfig`/`LLMRails` (no `generate` call was made).

### 1.10 Safety classifiers, scanners, moderation
- Hugging Face (checked via `huggingface.co/api/models`, 2026-11-06). **All are gated with manual approval, so learners must request access early.** `meta-llama/Llama-Guard-4-12B` (2025-04, multimodal); `Llama-Guard-3-8B` and `-3-1B` (text); `Llama-Prompt-Guard-2-86M` and `-22M` (injection/jailbreak text classifiers, 2025-04). `Prompt-Guard-86M` is v1 and superseded.
- An HF search of meta-llama sorted by date found no newer guard model.
- **Ungated alternative:** `openai/gpt-oss-safeguard-20b` and `-120b` (policy-following safety reasoners).
- **garak** 0.17.1 (2026-10-16, Alpha): `garak --target_type openai --target_name $MODEL --spec probes.promptinject`. `--model_type/--model_name` and `--probes` are **deprecated**; use `--target_*` and `--spec`. Requires `openai<3` plus torch and transformers, so run it in its own venv/`uvx`. Its OpenAI generator is Chat Completions–style.
- **Moderation** (free per OpenAI docs): `client.moderations.create(model="omni-moderation-latest", input=...)`, or inline on `responses.create(..., moderation={"model": "omni-moderation-latest"})`, which gives `response.moderation.input/.output` with `.flagged` and `.type == "error"`. The `moderation` parameter exists in SDK 3.46.
- **Presidio** (D73) 2.2.366: the repo moved to `data-privacy-stack/presidio`. Use `AnalyzerEngine().analyze(text, language="en", entities=None, score_threshold=None)` and then `AnonymizerEngine().anonymize(text, analyzer_results, operators=None)`. The default NLP engine needs the spaCy model `en_core_web_lg` (a large download), so tell learners up front.

## 2. IDS / VERSIONS / PRICES (as of 2026-11-06)
- **Pins for lesson headers:**
  - `arize-phoenix==21.0.0`, `arize-phoenix-otel==0.17.2`, `openinference-instrumentation-openai==0.1.69`, `langsmith==0.14.17`, `langfuse==5.2.0`, `deepeval==4.3.3`
  - `ragas==0.4.3` with `langchain-community<0.4.2`; `opentelemetry-sdk==1.45.2`; `opentelemetry-instrumentation-openai-v2==2.4b0` with `opentelemetry-util-genai==0.4b0`
  - **These pin openai<3 (own venv):** `guardrails-ai==0.11.0`, `garak==0.17.1`. Also `nemoguardrails==0.24.1` and promptfoo `0.125.1` (Node >= 22.22). Sources: https://pypi.org/pypi/<pkg>/json and https://registry.npmjs.org/promptfoo
- **Prices:** moderation is free ("The moderation endpoint is free to use", https://developers.openai.com/api/docs/guides/moderation). Self-hosting is free: DeepEval, RAGAS, NeMo and guardrails-ai are Apache-2.0; LangSmith SDK, Langfuse SDK and Promptfoo are MIT; **Phoenix is Elastic-2.0 (source-available, not OSI)**. I did not verify hosted LangSmith/Langfuse tier prices (their sites are TLS-blocked here), so don't quote them.
- **OpenAI Evals platform:** existing evals became read-only on **2026-10-31**, and the dashboard and API **shut down on 2026-11-30**. The migration path is Promptfoo (https://developers.openai.com/api/docs/deprecations).
- **OWASP Top 10 for LLM Applications 2025** (the `2_0_vulns/` files in the OWASP GitHub repo): LLM01 Prompt Injection · LLM02 Sensitive Information Disclosure · LLM03 Supply Chain · LLM04 Data and Model Poisoning · LLM05 Improper Output Handling · LLM06 Excessive Agency · LLM07 System Prompt Leakage · LLM08 Vector and Embedding Weaknesses · LLM09 Misinformation · LLM10 Unbounded Consumption.
- **OWASP Agentic Top 10 (2026) and the EU AI Act dates: UNVERIFIED.** genai.owasp.org and artificialintelligenceact.eu both fail TLS here. Don't list the ASI01–10 items or exact AI Act dates as fact. For the AI Act, give the phased structure in prose (prohibitions → GPAI → high-risk) with "⚠ verify: the 2025 Digital Omnibus proposal may move high-risk dates".

## 3. DON'T USE
| Don't | Use instead |
|---|---|
| OpenAI Evals platform / Evals API (shut down 2026-11-30) | pytest harness (default) or Promptfoo |
| `ragas.evaluate()` / `aevaluate()` (DeprecationWarning) | `@experiment` + `DiscreteMetric`, or a hand-built judge |
| `guardrails hub install hub://…` and the private hub | `pip install guardrails-ai-<name>`; `from guardrails_ai.<name> import …` |
| DeepEval `LLMTestCaseParams`, `GPTModel` | `SingleTurnParams`, `OpenAIModel` |
| Langfuse `from langfuse.decorators import observe` (gone), `update_current_trace`, `start_as_current_span/generation` | `from langfuse import observe, propagate_attributes`; `start_as_current_observation` |
| OTel `gen_ai.system`, `gen_ai.usage.prompt_tokens/completion_tokens` | `gen_ai.provider.name`, `gen_ai.usage.input_tokens/output_tokens` |
| `opentelemetry-instrumentation-openai-v2` to trace Responses (it traces nothing) | OpenInference (Phoenix) or manual `gen_ai.*` spans |
| `LANGCHAIN_TRACING_V2` / `LANGCHAIN_API_KEY` | `LANGSMITH_TRACING` / `LANGSMITH_API_KEY` |
| garak `--model_type/--model_name/--probes` | `--target_type/--target_name/--spec` |
| `meta-llama/Prompt-Guard-86M` (v1) | `Llama-Prompt-Guard-2-86M` / `-22M` |

## 4. ⚠ VERIFY RESOLUTIONS
- D012 | local Phoenix auto-instrumentation | **CONFIRMED.** `phoenix serve` plus `register(auto_instrument=True)` traces `responses.create`; run end to end.
- D030 | RAGAS `evaluate()` deprecated; DeepEval optional | **CONFIRMED.** Also **CORRECTED:** a fresh ragas install fails to import, so pin `langchain-community<0.4.2`. DeepEval 4.3.3 works (use `SingleTurnParams` and an explicit judge `model=`).
- D042 | OTel GenAI conventions, status Development | **CONFIRMED** (Development; spec moved to `semantic-conventions-genai`). **CORRECTED:** the official OpenAI instrumentor does not trace the Responses API. Use Phoenix/OpenInference (`llm.*` attributes) or manual `gen_ai.*` spans.
- D047 | Promptfoo optional (Node) | **CONFIRMED.** Node >= 22.22.0, `npx promptfoo@latest eval`, exits 100 when a test fails. Promptfoo is now part of OpenAI (still MIT).
- D070 | moderation API free | **CONFIRMED** (also inline `moderation=` on `responses.create`).
- D070 | guardrails-ai package names | **CORRECTED.** See the §1.8 table. Note `restrict-to-topic` (not `restricttotopic`) and that guardrails-ai pins `openai<3`.
- D073 | Presidio | **CONFIRMED** (2.2.366; the repo moved to data-privacy-stack; needs spaCy `en_core_web_lg`).
- D075 | Promptfoo red-team mode | **CONFIRMED** (`redteam init/run/generate/eval`). Caveat: probes are generated remotely unless `PROMPTFOO_DISABLE_REMOTE_GENERATION=true`.

## 5. VERIFIED LINKS (HTTP 200 from this environment, 2026-11-06)
- https://github.com/open-telemetry/semantic-conventions-genai: the new home of the GenAI semantic conventions (see `docs/gen-ai/openai.md`)
- https://github.com/open-telemetry/opentelemetry-python-contrib/tree/main/instrumentation-genai/opentelemetry-instrumentation-openai-v2: the official OpenAI instrumentor
- https://github.com/Arize-ai/phoenix: Phoenix (local tracing and eval UI)
- https://github.com/Arize-ai/openinference: OpenInference instrumentors (used by Phoenix)
- https://github.com/langchain-ai/langsmith-sdk: LangSmith SDK (`@traceable`, `wrap_openai`)
- https://github.com/langfuse/langfuse-python: Langfuse Python SDK v5
- https://github.com/promptfoo/promptfoo: Promptfoo CLI (evals and red teaming)
- https://developers.openai.com/api/docs/deprecations: Evals platform shutdown timeline
- https://developers.openai.com/cookbook/examples/evaluation/moving-from-openai-evals-to-promptfoo: OpenAI's migration guide to Promptfoo
- https://developers.openai.com/api/docs/guides/moderation: moderation endpoint and inline `moderation=`
- https://github.com/confident-ai/deepeval: DeepEval (GEval, pytest)
- https://github.com/vibrantlabsai/ragas: RAGAS (moved repo; `@experiment`)
- https://github.com/guardrails-ai/guardrails: Guardrails AI
- https://github.com/NVIDIA-NeMo/Guardrails: NeMo Guardrails
- https://github.com/NVIDIA/garak: garak LLM vulnerability scanner
- https://github.com/data-privacy-stack/presidio: Presidio PII detection and anonymization
- https://huggingface.co/meta-llama/Llama-Guard-4-12B: Llama Guard 4 (gated)
- https://huggingface.co/meta-llama/Llama-Prompt-Guard-2-86M: Prompt Guard 2 injection classifier (gated)
- https://huggingface.co/openai/gpt-oss-safeguard-20b: open-weight safety classifier (ungated)
- https://github.com/OWASP/www-project-top-10-for-large-language-model-applications/tree/main/2_0_vulns: OWASP LLM Top 10 2025 source text
- https://www.anthropic.com/research/building-effective-agents: "Building effective AI agents" (the `/engineering/` URL redirects here)
- https://www.anthropic.com/research/effective-context-engineering-for-ai-agents: "Effective context engineering for AI agents"
- https://www.anthropic.com/research/writing-tools-for-agents: "Writing effective tools for AI agents"
- https://www.anthropic.com/research/contextual-retrieval: "Contextual retrieval in AI systems"
- https://github.com/chroma-core/context-rot: Chroma "Context Rot" toolkit, which links the report at research.trychroma.com/context-rot

**NOT fetchable here (TLS-intercepted), so writers must click-check before citing:** genai.owasp.org (LLM Top 10 2025 and Agentic Top 10 2026), Simon Willison's "lethal trifecta" post, Hamel Husain's evals FAQ, the artificialintelligenceact.eu timeline, research.trychroma.com/context-rot (the canonical URL per the GitHub README), and the docs sites for LangSmith, Langfuse, Promptfoo, DeepEval, RAGAS and Phoenix.
