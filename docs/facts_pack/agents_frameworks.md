# FACTS_PACK · agents_frameworks
As of **2026-11-06**. Python 3.12 venv `/tmp/facts_agents_frameworks` (no API keys; no live calls).
Installed (= PyPI latest on 2026-11-06): langgraph 1.2.20 · langgraph-checkpoint 4.3.1 · -sqlite 3.1.3 · -postgres 3.2.0 · langchain 1.4.9 · langchain-core 1.7.6 · langchain-openai 1.7.4 · openai-agents 0.24.0 · pydantic-ai-slim 2.66.0 · crewai 1.15.36 · llama-index-core 0.14.25 · llama-index-llms-openai 0.8.3 · openai 3.46.0.
Method: `inspect.signature`, reading installed source, and **offline end-to-end runs** with fake/scripted models (LangChain `GenericFakeChatModel`, Agents SDK `agents.testing.ScriptedModel`, PydanticAI `TestModel`/`FunctionModel`). Writers can reuse these test doubles so lessons run without keys.

## 1. VERIFIED API SHAPES
All snippets assume `MODEL = os.environ.get("ATLAS_MODEL", "gpt-6-luna")` (ID from the openai FACTS slice).

### 1.1 LangGraph 1.2.20 (`uv add langgraph langgraph-checkpoint-sqlite`)
```python
import operator
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt, Command
class State(TypedDict):
    steps: Annotated[list[str], operator.add]   # reducer: returned lists are APPENDED (no reducer = last write wins)
g = StateGraph(State)
g.add_node("work", lambda s: {"steps": ["work"]})
g.add_node("gate", lambda s: {"steps": [f"approved={interrupt('ok to publish?')}"]})
g.add_edge(START, "work"); g.add_edge("gate", END)
g.add_conditional_edges("work", lambda s: "work" if len(s["steps"]) < 3 else "gate", ["work", "gate"])
app, cfg = g.compile(checkpointer=InMemorySaver()), {"configurable": {"thread_id": "t1"}, "recursion_limit": 25}
out = app.invoke({"steps": []}, cfg)          # paused: out["__interrupt__"] == [Interrupt(value='ok to publish?', id=...)]
out = app.invoke(Command(resume="yes"), cfg)  # resumes; "gate" re-runs from its first line
```
verified by: introspection + this exact snippet run offline (final `out` = `{'steps': ['work', 'work', 'work', 'approved=yes']}`).
Sharp edges:
- `START`/`END` are the strings `"__start__"`/`"__end__"`. `add_conditional_edges(source, path, path_map=None)`: `path_map` may be a list or a dict.
- `compile(checkpointer=None, *, store=None, interrupt_before=None, interrupt_after=None, ...)`. `invoke(input, config, *, context=None, stream_mode="values", durability=None, version="v1")`.
- **`InMemorySaver` is canonical. `MemorySaver` is the same object** (`MemorySaver is InMemorySaver` → True) and raises no warning. Teach `InMemorySaver`.
- **`interrupt()` needs a checkpointer and a `thread_id`.** On resume the node **re-executes from the top**, so put side effects *after* the interrupt, or make them idempotent. Multiple interrupts in one node are matched to resume values by order. In 1.2 the paused result carries an `"__interrupt__"` key; `app.get_state(cfg).next` → `('gate',)` and `.interrupts` hold the payload.
- `Command(*, graph=None, update=None, resume=None, goto=())`. `Command` can also be *returned* from a node (`update=` + `goto=`) to route and update state in one step.
- **`recursion_limit` default is 10007** (env `LANGGRAPH_DEFAULT_RECURSION_LIMIT`; source `langgraph/_internal/_config.py`), **not 25**. Always pass it explicitly in `config`. Exceeding it raises `langgraph.errors.GraphRecursionError`.
- `get_state_history(cfg)` yields `StateSnapshot`s, newest first (`.values`, `.next`, `.config`, `.parent_config`, `.interrupts`).
- **`update_state(config, values, as_node=None)` does NOT mutate in place.** It writes a NEW checkpoint whose parent is the given one (verified: history went 6→7, and `parent_config` = the old checkpoint) and returns that new config. Values pass through reducers (a list field gets appended). Time travel = `new_cfg = update_state(old_snapshot.config, {...})`, then `invoke(None, new_cfg)` replays from the fork (verified: inc→dbl run gave 4; forking before `dbl` with n=10 gave 20).
- Stream modes (`typing.get_args(StreamMode)`): `values, updates, checkpoints, tasks, debug, messages, custom`. With a list (`stream_mode=["updates","values"]`) each chunk is a `(mode, chunk)` tuple. `messages` streams LLM tokens as `(message_chunk, metadata)`.
- **SqliteSaver** lives in the separate package `langgraph-checkpoint-sqlite`: `from langgraph.checkpoint.sqlite import SqliteSaver`. `SqliteSaver.from_conn_string("ckpt.db")` is a **context manager** (`with ... as cp:`). Direct form: `SqliteSaver(sqlite3.connect(path, check_same_thread=False))`. Async: `from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver`.
- **PostgresSaver**: package `langgraph-checkpoint-postgres` (+ `psycopg[binary]`). `from langgraph.checkpoint.postgres import PostgresSaver`. `with PostgresSaver.from_conn_string(DB_URI) as cp: cp.setup()`; call `.setup()` once to create the tables.
- **Long-term Store** (cross-thread memory): `from langgraph.store.memory import InMemoryStore`; `g.compile(checkpointer=..., store=store)`. A node takes `runtime: Runtime` (`from langgraph.runtime import Runtime`) and uses `runtime.store.put(("memories", user_id), key, {"text": ...})`, `.get(ns, key)` → `Item | None` (`.value`), and `.search(ns_prefix, query=None, filter=None, limit=10)` → `list[SearchItem]`. Semantic search needs `InMemoryStore(index={...})` (embedding config; ⚠ verify the shape before teaching it). Verified offline.
- `from langgraph.prebuilt import create_react_agent` emits a deprecation warning: "moved to `langchain.agents` ... removed in V2.0".

### 1.2 LangChain 1.4.9 / langchain-openai 1.7.4 (`uv add langchain langchain-openai`)
```python
from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware
from langchain.chat_models import init_chat_model
from langchain.tools import tool
from langchain_openai import ChatOpenAI

@tool
def get_weather(city: str) -> str:
    """Get the weather for a city."""        # the docstring becomes the tool description
    return f"Sunny in {city}"
model = ChatOpenAI(model=MODEL, use_responses_api=True)   # or init_chat_model(f"openai:{MODEL}")
agent = create_agent(model, tools=[get_weather], system_prompt="Be brief.",
                     middleware=[ModelCallLimitMiddleware(run_limit=8)])
result = agent.invoke({"messages": [{"role": "user", "content": "Weather in Paris?"}]})
print(result["messages"][-1].content)
```
verified by: introspection + offline run with a fake chat model (messages: Human → AI(tool_call) → Tool → AI).
Sharp edges:
- `create_agent(model: str | BaseChatModel, tools=None, *, system_prompt=None, middleware=(), response_format=None, state_schema=None, context_schema=None, checkpointer=None, store=None, interrupt_before=None, interrupt_after=None, debug=False, name=None, cache=None)` returns a **compiled LangGraph graph**, so `invoke/stream/get_state` all apply. With `response_format=Model` (or `ToolStrategy(Model)` / `ProviderStrategy(Model)` from `langchain.agents.structured_output`) the result dict has `result["structured_response"]` holding a Model instance (verified offline with `ToolStrategy`).
- Middleware exported from `langchain.agents.middleware` includes `HumanInTheLoopMiddleware(interrupt_on={"tool_name": True|InterruptOnConfig})` (needs a checkpointer), `SummarizationMiddleware(model, trigger=..., keep=("messages", 20))`, `ModelCallLimitMiddleware(thread_limit=, run_limit=, exit_behavior="end")`, `ToolCallLimitMiddleware`, `ModelRetryMiddleware`, `ToolRetryMiddleware`, `ModelFallbackMiddleware`, `PIIMiddleware`, `TodoListMiddleware`, `LLMToolSelectorMiddleware`, `ContextEditingMiddleware`, and decorator hooks `before_model`, `after_model`, `wrap_model_call`, `wrap_tool_call`, `dynamic_prompt`.
- `ChatOpenAI`: **the default model is `gpt-3.5-turbo`, which was shut down on 2026-10-23 (deprecations page), so always pass `model=`.** `use_responses_api` defaults to `None` (auto). Auto picks Responses only when you set `reasoning`/`include`/`truncation`/`context_management`/`use_previous_response_id`/`output_version="responses/v1"`, or use built-in tools, or a `gpt-6*` model is called **with tools** (source `langchain_openai/chat_models/base.py::_use_responses_api`). A plain `gpt-6-luna` call **without** tools still goes to Chat Completions, so **pass `use_responses_api=True` explicitly.**
- `init_chat_model("openai:gpt-6-luna")` → `ChatOpenAI` with `use_responses_api=None`. Pass `use_responses_api=True` as a kwarg to force it.

### 1.3 OpenAI Agents SDK, pin `openai-agents==0.24.0` (`uv add "openai-agents==0.24.0"`; import name `agents`)
```python
from agents import (Agent, Runner, function_tool, input_guardrail, GuardrailFunctionOutput,
                    InputGuardrailTripwireTriggered, SQLiteSession)

@function_tool                                   # schema from type hints + docstring; strict by default
def get_weather(city: str) -> str:
    """Return the weather for a city."""
    return f"Sunny in {city}"
@function_tool(needs_approval=True)              # human-in-the-loop gate
def delete_file(path: str) -> str:
    """Delete a file."""
    return f"deleted {path}"
agent = Agent(name="Assistant", instructions="Be brief.", model=MODEL, tools=[get_weather, delete_file])
result = Runner.run_sync(agent, "Weather in Paris?", session=SQLiteSession("user-1", "chat.db"), max_turns=8)
print(result.final_output)
```
```python
result = Runner.run_sync(agent, "delete a.txt")              # approval-gated tool → run pauses
state = result.to_state()
for item in result.interruptions:                            # list[ToolApprovalItem]: .name, .arguments
    state.approve(item)                                      # or state.reject(item, rejection_message="...")
result = Runner.run_sync(agent, state)                       # resume by passing the RunState as input

@input_guardrail
async def no_secrets(ctx, agent, user_input) -> GuardrailFunctionOutput:
    return GuardrailFunctionOutput(output_info=None, tripwire_triggered="password" in str(user_input))
guarded = Agent(name="G", instructions="...", model=MODEL, input_guardrails=[no_secrets])
try: Runner.run_sync(guarded, "my password is hunter2")
except InputGuardrailTripwireTriggered as e: print("blocked", e.guardrail_result.output.output_info)
```
verified by: introspection + offline runs with the SDK's own test double `agents.testing.ScriptedModel` (tool call, session, approval→resume, guardrail tripwire, `output_type`, handoff, `as_tool`, `MaxTurnsExceeded` all exercised); docs https://openai.github.io/openai-agents-python/ (tracing/, human_in_the_loop/, sessions/, guardrails/, handoffs/).
Sharp edges:
- `Runner.run(starting_agent, input, *, context=None, max_turns=10, hooks=None, run_config=None, error_handlers=None, previous_response_id=None, auto_previous_response_id=False, conversation_id=None, session=None)` is **async** → `RunResult`. `run_sync` has the same signature; `run_streamed` → `RunResultStreaming` (iterate `async for ev in r.stream_events()`). `input` may be a `str`, a list of input items, or a `RunState`.
- **`max_turns` default = 10.** Exceeding it raises `agents.MaxTurnsExceeded`. Other errors: `InputGuardrailTripwireTriggered`, `OutputGuardrailTripwireTriggered`, `ModelBehaviorError`, `UserError` (all subclass `AgentsException`).
- **Always pass `model=`.** Without it the default is `os.getenv("OPENAI_DEFAULT_MODEL", "gpt-5.6-luna")` (`agents/models/default_models.py`). That model is live and not on the deprecations page, but it isn't the course's MODEL. The default transport is the Responses API (`OpenAIResponsesModel`). `OpenAIChatCompletionsModel` exists for compatible servers.
- `Agent` fields: `name, handoff_description, tools, mcp_servers, mcp_config, instructions, prompt, handoffs, model, model_settings, input_guardrails, output_guardrails, output_type, hooks, tool_use_behavior, reset_tool_choice`. With `output_type=PydanticModel`, `result.final_output` is a model instance (or use `result.final_output_as(Model)`).
- `RunResult`: `final_output`, `new_items` (types: `tool_call_item`, `tool_call_output_item`, `message_output_item`, `handoff_call_item`, `handoff_output_item`, `tool_approval_item`), `last_agent`, `interruptions`, `to_input_list()`, `to_state()`, `last_response_id`.
- **Handoffs:** `Agent(..., handoffs=[billing_agent])` or `handoff(agent, tool_name_override=, on_handoff=, input_type=, input_filter=)`. The default tool name is `transfer_to_<snake_name>` ("Billing agent" → `transfer_to_billing_agent`). After a handoff `result.last_agent` is the specialist; reuse it for the next turn.
- **Agents as tools:** `translator.as_tool(tool_name="translate", tool_description="...")` → `FunctionTool`. The manager keeps control, unlike a handoff. `tool_name`/`tool_description` are positional-or-keyword with no default, so pass both.
- **Guardrails:** `@input_guardrail(run_in_parallel=True)` / `@output_guardrail` functions receive `(ctx, agent, input_or_output)` and return `GuardrailFunctionOutput(output_info, tripwire_triggered)`. Input guardrails run only on the *first* agent; output guardrails only on the agent that produces the final output (docs/guardrails). Tool-level guardrails: `tool_input_guardrail`, `tool_output_guardrail`.
- **Sessions:** `SQLiteSession(session_id, db_path=":memory:")`, importable from `agents`. Default is in-memory, so pass a file path to persist. Also `OpenAIConversationsSession` (server-side, Conversations API) and, in `agents.extensions.memory`, `AsyncSQLiteSession`/`AdvancedSQLiteSession`/`MongoDBSession`/`DaprSession` (more extras exist; ⚠ verify per backend). `await session.get_items()`. Combining `session=` with `conversation_id`/`previous_response_id`/`auto_previous_response_id` raises `UserError` (verified).
- **Tracing is ON by default** and exports to the OpenAI Traces dashboard. Disable it with `OPENAI_AGENTS_DISABLE_TRACING=1`, `set_tracing_disabled(True)`, or `RunConfig(tracing_disabled=True)`. Redirect it with `set_trace_processors([...])` (replaces the OpenAI exporter) or add to it with `add_trace_processor(p)`. `RunConfig(trace_include_sensitive_data=False)` drops prompts and outputs from spans. **Tracing is unavailable for ZDR orgs** (docs/tracing). Phoenix, Langfuse, LangSmith and Logfire are listed as external processors.
- **Offline tests:** `from agents.testing import ScriptedModel, assistant_message, function_call`; `Agent(model=ScriptedModel([[function_call("get_weather", {"city": "Paris"}, call_id="c1")], [assistant_message("Sunny.")]]))`. This is verified and is the right tool for CI and for keyless learners.
- `function_tool(..., strict_mode=True, needs_approval=False, timeout=None, failure_error_function=<default>)`. By default a tool exception is returned **to the model** as an error string, not raised. Pass `failure_error_function=None` to raise.

### 1.4 PydanticAI 2.66.0 (`uv add "pydantic-ai-slim[openai]"`; the full `pydantic-ai` pulls in every provider)
```python
from dataclasses import dataclass
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
@dataclass
class Deps:
    user_id: str
class Answer(BaseModel):
    city: str
    temp_c: int
agent = Agent(f"openai:{MODEL}", deps_type=Deps, output_type=Answer, instructions="Be brief.")
@agent.tool                                   # first param must be RunContext[Deps]; @agent.tool_plain if no ctx
def get_temp(ctx: RunContext[Deps], city: str) -> int:
    """Return the temperature in Celsius."""   # the docstring becomes the tool description
    return 21
print(agent.run_sync("Weather in Paris?", deps=Deps("u1")).output)   # an Answer instance
```
verified by: introspection + this snippet run offline with the model swapped (`with agent.override(model=TestModel()):` → `Answer(city='a', temp_c=0)` after calling the tool; `FunctionModel` returned a scripted output).
Sharp edges:
- **`"openai:<id>"` resolves to `OpenAIResponsesModel`** (Responses API) in 2.66. `"openai-chat:<id>"` → `OpenAIChatModel`. `"openai-responses:<id>"` is explicit.
- **`Agent("openai:...")` raises `pydantic_ai.UserError` at construction if `OPENAI_API_KEY` is unset.** Pass `defer_model_check=True` to build it keyless (as in tests or imports) and supply the model at run time.
- `Agent(model=None, *, output_type=str, instructions=None, system_prompt=(), deps_type=object, name=None, model_settings=None, retries=None, tools=(), toolsets=None, defer_model_check=False, end_strategy="graceful", tool_timeout=None, ...)`. `run_sync(user_prompt, *, message_history=None, deps=None, model=None, usage_limits=None, ...)` → `AgentRunResult`: `.output`, `.all_messages()`, `.new_messages()`, `.usage` (**a property**; calling `.usage()` warns `PydanticAIDeprecationWarning`). Async: `await agent.run(...)`; streaming: `agent.run_stream(...)`.
- Structured output goes through an output tool named `final_result` by default. `NativeOutput(Model)` / `PromptedOutput(Model)` / `ToolOutput(Model)` choose the strategy. Raise `ModelRetry("msg")` inside a tool or validator to make the model retry.
- Tool approval: `@agent.tool(requires_approval=True)`. The run then ends with `DeferredToolRequests` output; resume with `deferred_tool_results=DeferredToolResults(...)` (⚠ verify the exact flow before teaching it; not exercised here).
- `Agent.override(*, deps=, model=, tools=, toolsets=, instructions=, ...)` is a **context manager** for tests. `TestModel(call_tools="all", custom_output_text=None, custom_output_args=None, seed=0)` calls every tool and synthesizes schema-valid output. `FunctionModel(fn)`, where `fn(messages, info: AgentInfo) -> ModelResponse` (from `pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart`). Set `pydantic_ai.models.ALLOW_MODEL_REQUESTS = False` in tests to block real calls.
- **It prints a startup banner** advertising Logfire on the first run. Set `PYDANTIC_AI_NO_BANNER=1` (or `pydantic_ai.BANNER_ENABLED = False`) so lesson output stays clean.

### 1.5 Comparison rows (D057 landscape): CrewAI, LlamaIndex, A2A
| Framework | Version (PyPI, 2026-11-06) | Core abstraction (verified by introspection) | OpenAI model-ID caveat |
|---|---|---|---|
| CrewAI | `crewai==1.15.36` (Python `>=3.10,<3.14`) | Role-based crews: `Agent(role, goal, backstory)` (required), `Task(description, expected_output)` (required), `Crew(agents, tasks, process=Process.sequential\|hierarchical).kickoff(inputs={...})` → `CrewOutput` (`.raw`, `.pydantic`, `.json_dict`, `.tasks_output`, `.token_usage`). `crewai create crew` scaffolds JSON-first (`crew.jsonc`) by default | **Default model `gpt-4.1-mini`** (`crewai/constants.py::DEFAULT_LLM_MODEL`; that model retires 2027-01-14). Its OpenAI provider defaults to **`api="completions"`**, so pass `LLM(model="openai/<id>", api="responses")` explicitly (verified: `api` attr = `responses`) |
| LlamaIndex | `llama-index-core==0.14.25`, `llama-index-llms-openai==0.8.3` | Data/RAG-first: indexes + query engines; agents via `llama_index.core.agent.workflow` (`FunctionAgent`, `ReActAgent`, `AgentWorkflow`; `FunctionAgent(tools=, llm=, system_prompt=, can_handoff_to=, output_cls=)`). Responses API: `from llama_index.llms.openai import OpenAIResponses` | **Hard-coded model table.** It knows `gpt-6-luna`, `gpt-6-sol`, `gpt-6.1-sol` and `gpt-6-astra` (1,050,000 ctx), but **`gpt-6.1-terra` raises `ValueError: Unknown model`**. The constructor succeeds; the error comes on first `.metadata` use. Default models: `OpenAI` → `gpt-3.5-turbo` (**shut down 2026-10-23**), `OpenAIResponses` → `gpt-4o-mini` (retires 2027-01-14), so always pass `model=` |
| A2A | spec **v1.0.1** (GitHub release 2026-05-28); Python `a2a-sdk==1.3.0` (2026-10-27) | An open agent-to-agent protocol (agent cards, tasks, messages) under the **Linux Foundation** (contributed by Google). It *complements* MCP: MCP connects agent↔tools, A2A connects agent↔agent | n/a. One prose paragraph only; no SDK code in the course (none verified here) |

## 2. IDS / VERSIONS / PRICES
Exact pins (PyPI JSON `https://pypi.org/pypi/<pkg>/json`, fetched 2026-11-06; upload date in parentheses):
`langgraph==1.2.20` (11-05) · `langgraph-checkpoint==4.3.1` · `langgraph-checkpoint-sqlite==3.1.3` · `langgraph-checkpoint-postgres==3.2.0` · `langgraph-prebuilt==1.1.1` · `langchain==1.4.9` (11-04) · `langchain-core==1.7.6` · `langchain-openai==1.7.4` · **`openai-agents==0.24.0`** (2026-10-15; pre-1.0, no status classifier, so pin it exactly) · `pydantic-ai(-slim)==2.66.0` (11-04; Python ≥3.11) · `crewai==1.15.36` (11-06; Python <3.14) · `llama-index-core==0.14.25` (09-21) · `llama-index-llms-openai==0.8.3` (10-12) · `a2a-sdk==1.3.0` (10-27) · `openai==3.46.0` (pulled in by these; `httpx2` 2.16.0).
Framework default models (all from installed source; why "always pass model=" matters):
| Framework | Default if you omit the model | Status (https://developers.openai.com/api/docs/deprecations, as of 2026-11-06) |
|---|---|---|
| `ChatOpenAI` / llama-index `OpenAI` | `gpt-3.5-turbo` | **shut down 2026-10-23** |
| llama-index `OpenAIResponses` | `gpt-4o-mini` | shuts down 2027-01-14 |
| CrewAI (`DEFAULT_LLM_MODEL`) | `gpt-4.1-mini` | shuts down 2027-01-14 |
| openai-agents | `gpt-5.6-luna` (env `OPENAI_DEFAULT_MODEL`) | live |
No framework adds per-token charges; prices are the provider's (see the openai slice). Agents SDK tracing: the docs say "View free traces at OpenAI Traces dashboard" (https://openai.github.io/openai-agents-python/tracing/, as of 2026-11-06).

## 3. DON'T USE
| Don't | Use instead | Evidence |
|---|---|---|
| `from langgraph.prebuilt import create_react_agent` | `from langchain.agents import create_agent` | runtime DeprecationWarning: "moved to `langchain.agents` ... removed in V2.0" |
| `MemorySaver` in new code | `InMemorySaver` (same class; the alias still works) | `MemorySaver is InMemorySaver` |
| `StateGraph(..., config_schema=...)` | `context_schema=` + `runtime: Runtime` in nodes | runtime warning: "`config_schema` is deprecated ... use `context_schema`" |
| `from langgraph.checkpoint.sqlite import SqliteSaver` with only `langgraph` installed | also `uv add langgraph-checkpoint-sqlite` (Postgres: `langgraph-checkpoint-postgres`) | separate dists |
| Relying on LangGraph's "default recursion limit 25" | pass `{"recursion_limit": N}` explicitly | default is 10007 in 1.2.20 |
| `langchain.agents.AgentExecutor`, `initialize_agent`, `langchain.memory.*`, `langchain.chains.LLMChain` | `create_agent` + a LangGraph checkpointer (legacy code lives in `langchain-classic` 1.0.8) | `ImportError`/`ModuleNotFoundError` in langchain 1.4.9 |
| `ChatOpenAI()` / llama-index `OpenAI()` with no model | always pass `model=MODEL` | default `gpt-3.5-turbo` was shut down 2026-10-23 |
| `ChatOpenAI(model=...)` relying on auto API choice | `use_responses_api=True` | a tool-less call goes to Chat Completions |
| PydanticAI `result_type=`, `result.data`, `result.usage()` | `output_type=`, `result.output`, `result.usage` | `TypeError` / attribute missing / deprecation warning in 2.66 |
| CrewAI default LLM / implicit Chat Completions | `LLM(model="openai/<id>", api="responses")` | default `gpt-4.1-mini` retires 2027-01-14; `api` defaults to `"completions"` |
| llama-index with `gpt-6.1-terra` | `gpt-6-luna` / `gpt-6.1-sol` / `gpt-6-astra` (in its table) | `ValueError: Unknown model` |
| OpenAI Swarm | OpenAI Agents SDK | Swarm README: "now replaced by the OpenAI Agents SDK" |
| OpenAI Assistants API (`client.beta.assistants`/`threads`) | Responses + Conversations API, or the Agents SDK | shut down 2026-08-26 (deprecations page); the SDK attribute still exists but the API is gone |
| OpenAI Agent Builder | the Agents SDK (ChatKit remains) | shuts down 2026-11-30 (deprecations page) |
| `client.beta.agents...` (managed Agents API) in code | prose only + "⚠ verify" | docs show `client.beta.agents.sessions.create`, but released `openai==3.46.0` has **no** `beta.agents` (it's only on GitHub main) |

## 4. ⚠ VERIFY RESOLUTIONS
- D053 | `InMemorySaver` | **CONFIRMED.** `from langgraph.checkpoint.memory import InMemorySaver` (1.2.20); `MemorySaver` is an identical alias. Also CONFIRMED: `langchain.agents.create_agent` for the standard loop; `StateGraph`/`TypedDict`/`Annotated` reducers; compile/invoke/stream (§1.1–1.2).
- D056 | Agents SDK `Agent`/`Runner`, tools, sessions, guardrails, tracing (pinned version) | **CONFIRMED** at `openai-agents==0.24.0` (§1.3; offline runs with `agents.testing.ScriptedModel`). Correction: the default model, if you omit `model=`, is `gpt-5.6-luna`, so set it explicitly.
- D056 | choosing a runtime: managed agents API | **CONFIRMED (prose only).** The OpenAI "Agents API" (managed Codex harness, **beta**) is documented at developers.openai.com/api/docs/guides/agents-api/overview, but released `openai==3.46.0` has no `client.beta.agents`. **UNVERIFIABLE as code:** describe it in prose with "⚠ verify", and no snippet.
- D057 | which model IDs each framework supports (llama-index) | **CONFIRMED with detail.** llama-index-llms-openai 0.8.3 knows `gpt-6-luna`, `gpt-6-sol`, `gpt-6.1-sol` and `gpt-6-astra`; `gpt-6.1-terra` → `ValueError`. CrewAI and LangChain pass any ID through. PydanticAI accepts any `openai:<id>` string. Agents SDK: any string.
- D049 (related, LangChain side) | DIY summarizing | **CONFIRMED:** `SummarizationMiddleware(model, trigger=("tokens", N), keep=("messages", 20))` exists in langchain 1.4.9. Server-side compaction is out of scope here (openai slice).
- (SYLLABUS D055/D057 HITL) | `interrupt()` + `Command(resume=)`; Agents SDK approvals | **CONFIRMED** (§1.1, §1.3). Note that the node re-executes on resume.
- (B_currency) | "`o3`/`o3-pro`/`gpt-5*` snapshots shut down 2026-12-11" | **CORRECTED:** only the original `gpt-5`, `-mini`, `-nano`, `-pro` (2025 snapshots) and `o3`/`o3-pro` shut down 2026-12-11. The `gpt-5.6-*` models are their listed *replacements* and are live. Also: `gpt-3.5-turbo`/`gpt-4`/`gpt-4-turbo`/`gpt-4.1-nano` shut down 2026-10-23.
- (B_currency) | versions langgraph 1.2.20, langchain 1.4.9, pydantic-ai 2.66.0, crewai 1.15.36, llama-index 0.14.25, openai-agents 0.24.0 | **CONFIRMED** (PyPI JSON 2026-11-06). B_currency's CrewAI "JSON-first scaffold" note: **CONFIRMED** (`crewai_cli/create_json_crew.py`: "This is the default `crewai create crew` path").

## 5. VERIFIED LINKS (all HTTP 200 on 2026-11-06)
- https://openai.github.io/openai-agents-python/ (Agents SDK docs home)
- https://openai.github.io/openai-agents-python/running_agents/ (Runner, max_turns, RunConfig)
- https://openai.github.io/openai-agents-python/tools/ (function_tool, agents as tools)
- https://openai.github.io/openai-agents-python/handoffs/ (handoffs, input filters)
- https://openai.github.io/openai-agents-python/guardrails/ (input/output/tool guardrails, scope rules)
- https://openai.github.io/openai-agents-python/sessions/ (SQLiteSession and other session backends)
- https://openai.github.io/openai-agents-python/human_in_the_loop/ (needs_approval → interruptions → approve/reject → resume)
- https://openai.github.io/openai-agents-python/tracing/ (default-on tracing, three ways to disable it, custom processors, ZDR note)
- https://github.com/openai/openai-agents-python (SDK source)
- https://developers.openai.com/api/docs/guides/agents.md (OpenAI: Agents API vs Agents SDK vs Responses)
- https://developers.openai.com/api/docs/guides/agents/quickstart.md (official Python quickstart, `pip install openai-agents`)
- https://developers.openai.com/api/docs/guides/agents-api/overview.md (managed Agents API, beta)
- https://developers.openai.com/api/docs/deprecations.md (Assistants, Agent Builder, model shutdown dates)
- https://github.com/langchain-ai/langgraph (LangGraph source and README)
- https://github.com/langchain-ai/langgraph/tree/main/libs/checkpoint-sqlite (SqliteSaver package)
- https://github.com/langchain-ai/langgraph/tree/main/libs/checkpoint-postgres (PostgresSaver package)
- https://github.com/langchain-ai/langchain (LangChain 1.x source: create_agent, middleware)
- https://github.com/pydantic/pydantic-ai (PydanticAI source and README)
- https://github.com/crewAIInc/crewAI (CrewAI source)
- https://github.com/run-llama/llama_index (LlamaIndex source)
- https://github.com/a2aproject/A2A (A2A spec repo: Linux Foundation, v1.0.1)
- https://github.com/openai/swarm (Swarm README: replaced by the Agents SDK)
- https://pypi.org/project/openai-agents/ · https://pypi.org/project/langgraph/ · https://pypi.org/project/pydantic-ai/ (version pins)
Unreachable here (TLS): docs.langchain.com, ai.pydantic.dev, docs.crewai.com, developers.llamaindex.ai, a2a-protocol.org. **Don't cite them as verified.**
