# FACTS_PACK: openai_core (OpenAI Python SDK 3.x core text APIs)
As of **2026-11-06**. Venv `/tmp/facts_openai_core` (Python 3.11): **openai 3.46.0** (latest on PyPI, uploaded 2026-11-05; GitHub CHANGELOG already lists 3.47.0), **httpx2 2.16.0** (pulled in by openai; plain `httpx` is NOT installed), **tiktoken 0.14.0**, **pydantic 2.14.3**. openai requires Python ≥3.10.
No live API calls were made (no keys). "introspection" = `inspect.signature` / installed source in that venv. Pin in lessons: `uv add "openai>=3.46,<4" pydantic` (add `tiktoken` only where used).

## 1. VERIFIED API SHAPES
Every snippet was also run client-side against a local `httpx2.MockTransport` (canned JSON): this proves the SDK accepts the params and exposes the attributes. Server-side behaviour comes from the cited docs. Snippets reuse `client`, `MODEL` and `json` from earlier ones.
### 1.1 Client + basic call (`instructions` vs `input`, `output_text`, `usage`)
```python
import os
from openai import OpenAI
MODEL = os.environ.get("ATLAS_MODEL", "gpt-6-luna")
client = OpenAI()  # reads OPENAI_API_KEY; defaults: max_retries=2, timeout=600s (connect 5s)
resp = client.responses.create(
    model=MODEL,
    instructions="You are Atlas, a terse support assistant.",  # system/developer-level
    input="Summarize: login fails after password reset.",       # str OR list of items
)
print(resp.output_text)            # joins every output_text part of every message item; "" if none
u = resp.usage                     # input_tokens, output_tokens, total_tokens
print(u.input_tokens, u.output_tokens, u.output_tokens_details.reasoning_tokens,
      u.input_tokens_details.cached_tokens, u.input_tokens_details.cache_write_tokens)
```
verified by: introspection (`Responses.create`, `Response.output_text` property, `ResponseUsage`); https://developers.openai.com/api/docs/guides/text.md
- All `create` params are keyword-only and SDK-optional (even `model`): always pass `model`. `instructions` outrank `input` messages (text guide). With `previous_response_id`, earlier `instructions` are **not** carried over (SDK docstring), so re-send them every turn.
- `resp.output` is a list of typed items (`message`, `reasoning`, `function_call`, `compaction`, ...). Never index `output[0].content[0].text`; the text guide warns `output` often has several items. Message items carry `phase` (`"commentary"` | `"final_answer"`); `output_text` concatenates **both** phases.
- `resp.status`: `completed | failed | in_progress | cancelled | queued | incomplete`. `resp.incomplete_details.reason`: `max_output_tokens | max_messages | content_filter | steered`.
- Reasoning tokens are billed as output tokens (reasoning guide). `resp._request_id` is public (README).
### 1.2 Errors, retries, timeouts, async, httpx2
```python
import asyncio, openai
from openai import AsyncOpenAI
try:
    resp = client.with_options(max_retries=5, timeout=30.0).responses.create(model=MODEL, input="hi")
except openai.RateLimitError as e:           # 429 (raised after SDK retries are exhausted)
    print("back off", e.status_code, e.request_id)
except openai.APIStatusError as e:           # any other 4xx/5xx; has .status_code .response .body
    print(e.status_code)
except openai.APIConnectionError as e:       # network failure; APITimeoutError is a subclass
    print("unreachable", e.__cause__)
async def ask_all(qs: list[str]) -> list[str]:
    async with AsyncOpenAI() as ac:
        rs = await asyncio.gather(*(ac.responses.create(model=MODEL, input=q) for q in qs))
        return [r.output_text for r in rs]
```
verified by: introspection (`openai.*Error` MROs, `_constants.py`, `_base_client._should_retry`); README in the installed wheel's METADATA
- Hierarchy: `OpenAIError > APIError > {APIStatusError, APIConnectionError > APITimeoutError}`. Status classes: 400 `BadRequestError`, 401 `AuthenticationError`, 403 `PermissionDeniedError`, 404 `NotFoundError`, 409 `ConflictError`, 422 `UnprocessableEntityError`, 429 `RateLimitError`, >=500 `InternalServerError`.
- Auto-retried (default **2** retries, exponential backoff 0.5s to 8s, honours `retry-after` up to 120s): connection errors, 408, 409, 429, >=500. `max_retries=0` disables. **Stream consumption is never retried.**
- Default timeout **600s** (`httpx2.Timeout(600, connect=5.0)`). Flex guide recommends `timeout=900.0`.
- **httpx2 (openai 3.0.0, 2026-08-12):** the SDK now depends on `httpx2`, and plain `httpx` is no longer installed. Any `http_client=httpx.Client(...)`, `httpx.Timeout`, `httpx.MockTransport` or respx-style mock must move to `httpx2.*`, or use `openai.DefaultHttpx2Client(...)`. The old `DefaultHttpxClient` name still works and now builds an httpx2 client. **TLS changes too:** httpx2 uses the OS trust store, not `certifi`. Corporate TLS proxies or slim containers may fail until you set `SSL_CERT_FILE`/`SSL_CERT_DIR` (httpx2.md). Async gets better concurrency from `pip install "openai[aiohttp]"` plus `http_client=DefaultAioHttpClient()`.
### 1.3 Conversation state: manual list, `previous_response_id`, Conversations API, `store`, compaction
```python
history = [{"role": "user", "content": "My order #12 is late."}]
r1 = client.responses.create(model=MODEL, input=history, store=False)  # stateless
history += r1.output                       # keep ALL items (reasoning, tool calls, phase)
history.append({"role": "user", "content": "Can you expedite it?"})
r2 = client.responses.create(model=MODEL, input=history, store=False)
# Server-side chaining: needs a STORED response (store defaults to True); prior tokens are STILL billed
first = client.responses.create(model=MODEL, input="My order #12 is late.")
r3 = client.responses.create(model=MODEL, previous_response_id=first.id, input="And refund shipping?")
conv = client.conversations.create()       # durable object; items have no 30-day TTL
r4 = client.responses.create(model=MODEL, conversation=conv.id, input="Hi again")
long = client.responses.create(model=MODEL, input=history, store=False,  # server compaction
    context_management=[{"type": "compaction", "compact_threshold": 200_000}])
```
verified by: introspection (`create` params, `ContextManagement` TypedDict, `client.conversations.*`); https://developers.openai.com/api/docs/guides/conversation-state.md ; …/guides/compaction.md ; …/guides/migrate-to-responses.md
- **`store` defaults to true** ("Defaults to true when omitted", SDK docstring; "Responses are stored by default", migration guide). Stored responses are kept 30 days. Items in a Conversation have no 30-day TTL. `store=False` is the stateless/ZDR path; reasoning items then carry `encrypted_content` by default, so replay them.
- `previous_response_id` **cannot be combined** with `conversation` (SDK docstring). It chains stored responses (reasoning guide: "Continue reasoning with stored responses"), every earlier token in the chain is billed again as input, and `instructions` do not carry over.
- Compaction: `context_management` is a list of `{"type": "compaction", "compact_threshold": int}` (only `"compaction"` is supported). Once the rendered context passes the threshold, the server emits an opaque `compaction` output item. With manual lists, append it and you may drop earlier items. With `previous_response_id`, send only the new message and don't prune. It is ZDR-friendly with `store=False`. There is also a standalone `client.responses.compact(model=..., input=[...])`, where `model` is required; use `[*compacted.output, new_msg]` as the next input.
### 1.4 Structured outputs (`responses.parse` + Pydantic; raw `json_schema`)
```python
from pydantic import BaseModel
class Ticket(BaseModel):
    title: str
    priority: int
    assignee: str | None          # "optional" = nullable; every field is sent as required
resp = client.responses.parse(model=MODEL, input="Login broken since reset, P2", text_format=Ticket)
ticket = resp.output_parsed         # Ticket instance, or None (refusal / no final text)
if ticket is None:
    parts = [c for i in resp.output if i.type == "message" for c in i.content]
    print("refused:", [c.refusal for c in parts if c.type == "refusal"] or resp.status)
raw = client.responses.create(model=MODEL, input="...", text={"format": {
    "type": "json_schema", "name": "ticket", "strict": True,
    "schema": {"type": "object", "properties": {"title": {"type": "string"}},
               "required": ["title"], "additionalProperties": False}}})
```
verified by: introspection (`lib/_parsing/_responses.py`: `type_to_text_format_param`, `parse_text`, `output_parsed`); mock run (refusal leads to `output_parsed is None`); https://developers.openai.com/api/docs/guides/structured-outputs.md
- `text_format=` accepts a Pydantic model (or dataclass-like type via TypeAdapter). The SDK sends `text.format = {"type": "json_schema", "strict": True, "name": <ClassName>, "schema": ...}`. It adds `additionalProperties: false` and lists **every** field in `required`, so Python defaults don't make a field optional. Use `X | None`. Parsing is `model_parse_json`, so a schema mismatch raises `pydantic.ValidationError`.
- `parse` only parses messages whose `phase` is absent or `"final_answer"`.
- Refusal: the message content part has `type == "refusal"` with a `.refusal` string, and `output_parsed` is None. Always check `resp.status == "incomplete"` too, because truncated JSON fails to parse.
- Raw form: `text={"format": {"type": "json_schema", "name", "strict": True, "schema"}}`. Responses has no `response_format`. Strict rules: the root must be an object (not `anyOf`), every property is required, `additionalProperties: false` on every object, at most 5,000 properties and 10 nesting levels, at most 1,000 enum values, at most 120,000 characters across names and enums. `$defs` and recursion are allowed. Supported keywords include `pattern`, `format` (date-time/date/email/uuid…), `minimum`/`maximum`, `minItems`/`maxItems`.
- JSON mode `{"type": "json_object"}` still exists ("always use Structured Outputs instead of JSON mode when possible"). Per STYLE_GUIDE, use it only in one labelled comparison.
### 1.5 Function calling (item shapes, `call_id`, `tool_choice`, parallel calls, strict)
```python
import json
tools = [{"type": "function", "name": "get_ticket", "description": "Fetch a ticket by id.",
          "strict": True, "parameters": {"type": "object", "properties": {"ticket_id": {"type": "string"}},
                                         "required": ["ticket_id"], "additionalProperties": False}}]
items = [{"role": "user", "content": "What's the status of T-1?"}]
resp = client.responses.create(model=MODEL, input=items, tools=tools)
items += resp.output                                   # includes the function_call item(s)
for call in (i for i in resp.output if i.type == "function_call"):
    args = json.loads(call.arguments)                  # arguments is a JSON *string*
    items.append({"type": "function_call_output", "call_id": call.call_id,
                  "output": json.dumps({"id": args["ticket_id"], "status": "open"})})
final = client.responses.create(model=MODEL, input=items, tools=tools)
print(final.output_text)
```
verified by: introspection (`ResponseFunctionToolCall`, `FunctionToolParam`, `response_input_param.FunctionCallOutput`); mock run; https://developers.openai.com/api/docs/guides/function-calling.md
- Tool defs are **flat** (`{"type": "function", "name", "description", "parameters", "strict"}`), with no nested `"function": {...}` as in Chat Completions. The SDK TypedDict marks `name`, `parameters` and `strict` as required keys.
- Call item: `type="function_call"`, `call_id`, `name`, `arguments` (str), `id`, `status`. Result item: `{"type": "function_call_output", "call_id": <same call_id>, "output": str | list of content parts}`. A missing or mismatched `call_id` is a listed migration error. Answer **every** call before the next request.
- **Strict default:** omitted `strict` in Responses means the API *tries* to normalise to strict and falls back to non-strict (the echoed tool then shows `strict: false`). Chat Completions is non-strict by default. Send `strict: True` explicitly. Strict needs `additionalProperties: false` plus all fields in `required` (use `["string", "null"]` for optional).
- `tool_choice`: `"auto"` (default) | `"required"` | `"none"` | `{"type": "function", "name": "get_ticket"}` | `{"type": "allowed_tools", "mode": "auto", "tools": [...]}`. Parallel calls are on by default; `parallel_tool_calls=False` gives zero or one call.
- Pydantic helper: `openai.pydantic_responses_function_tool(Model, name=..., description=...)` builds a strict tool. With `client.responses.parse(tools=[...])`, each call item gets `.parsed_arguments` (a Model instance).
### 1.6 Reasoning effort, sampling/logprobs restrictions, `max_output_tokens` and `incomplete`
```python
r = client.responses.create(model=MODEL, input="Classify: 'refund please'", reasoning={"effort": "low"},
                            max_output_tokens=25_000)            # caps reasoning + visible tokens
if r.status == "incomplete" and r.incomplete_details.reason == "max_output_tokens":
    print("ran out of room", r.output_text or "(during reasoning)")  # input+reasoning still billed
# Sampling knobs + logprobs ONLY with effort "none", on a model that accepts it (Luna, 6.1 Terra, 6 Sol)
s = client.responses.create(model="gpt-6-luna", input="Name a colour.", reasoning={"effort": "none"},
                            temperature=1.2, top_logprobs=5, include=["message.output_text.logprobs"])
part = next(i for i in s.output if i.type == "message").content[0]
print([(lp.token, round(lp.logprob, 2)) for lp in part.logprobs[:3]])
```
verified by: introspection (`ReasoningEffort` Literal, `ResponseIncludable`, `ResponseOutputText.logprobs`); https://developers.openai.com/api/docs/guides/reasoning.md ; …/guides/latest-model.md ; model pages
- SDK effort literal: `none | minimal | low | medium | high | xhigh | max`. Support per model (model pages): `gpt-6-luna`, `gpt-6.1-terra`, `gpt-6-sol`: none/low/medium/high/xhigh/max. `gpt-6.1-sol`: low…max (no none/minimal). `gpt-6-astra`: low…max (**`none` returns HTTP 400**). The default is `medium` (documented for Luna, 6.1 Sol, 6 Sol, 6.1 Terra). `minimal` should become `low`.
- When effort is not `none`: **remove `temperature`, `top_p`, `top_logprobs`** and drop `message.output_text.logprobs` from `include` (latest-model guide). `temperature` ranges 0–2 and `top_logprobs` 0–20.
- Reserve at least **25,000** tokens for reasoning plus output when you start (reasoning guide). Every GPT-6 model page lists "Reasoning token support". The docs advise a goal, constraints and an output contract "without prescribing every intermediate step". "CoT prompting helps only at `none`" is a heuristic, so give it a ⚠ verify note.
### 1.7 Streaming
```python
for ev in client.responses.create(model=MODEL, input="Tell a 1-line story", stream=True):
    if ev.type == "response.output_text.delta":
        print(ev.delta, end="", flush=True)
with client.responses.stream(model=MODEL, input="Again") as stream:   # helper; also takes text_format
    for ev in stream:
        pass                                                         # same typed events
    final = stream.get_final_response()                              # ParsedResponse
```
verified by: introspection (`lib/streaming/responses/_responses.py`); mock SSE run; https://developers.openai.com/api/docs/guides/streaming-responses.md
- Typed events: `response.created`, `response.output_item.added`, `response.output_text.delta` (`.delta`), `response.function_call_arguments.delta`/`.done`, `response.completed`, `error`. Chat-style `chunk.choices[0].delta` handlers don't work here.
### 1.8 Token counting (exact) vs tiktoken (approximate)
```python
n = client.responses.input_tokens.count(model=MODEL, instructions="Be terse.", input="Hello, Atlas!")
print(n.input_tokens)              # exact, includes role/format tokens; also accepts tools=, text=, images, files
import tiktoken                    # local + offline after first download of the BPE file
enc = tiktoken.get_encoding("o200k_base")   # NOT encoding_for_model("gpt-6-luna") → KeyError
print(len(enc.encode("Hello, Atlas!")))     # label it "approximate" for GPT-6
```
verified by: introspection (`InputTokens.count` signature, `InputTokenCountResponse{input_tokens, object}`); local run of tiktoken 0.14.0; https://developers.openai.com/api/docs/guides/token-counting.md ; https://raw.githubusercontent.com/openai/tiktoken/main/tiktoken/model.py
- Endpoint: `POST /v1/responses/input_tokens`. It takes the same payload shape as `create` (no `max_output_tokens`/`store`).
- tiktoken 0.14.0 (and `main`) has **no `gpt-6*` mapping**. `encoding_for_model` raises `KeyError: Could not automatically map gpt-6-luna to a tokeniser`. The `gpt-5` prefix maps to `o200k_base`, and `gpt-oss-*` maps to `o200k_harmony`. Which tokenizer GPT-6 actually uses is **UNVERIFIED**, so use the endpoint for real numbers.
### 1.9 Prompt caching (automatic; GPT-5.6+ rules)
```python
POLICY = open("policy.md").read()   # stable prefix first; >=1,024 tokens to be cacheable
r = client.responses.create(model=MODEL, prompt_cache_key="tenant-42",       # optional accounting key
    prompt_cache_options={"ttl": "30m"},                                      # default; or "12h"
    input=[{"role": "developer", "content": [{"type": "input_text", "text": POLICY,
            "prompt_cache_breakpoint": {"mode": "explicit", "ttl": "12h"}}]},  # optional explicit breakpoint
           {"role": "user", "content": "Where is order #12?"}])
d = r.usage.input_tokens_details
print(d.cached_tokens, d.cache_write_tokens, d.cache_write_tokens_details.ttl_12h_tokens)
```
verified by: introspection (`PromptCacheOptions`, `PromptCacheBreakpoint`, usage details); mock run; https://developers.openai.com/api/docs/guides/prompt-caching.md
- On by default with no code needed. GPT-5.6+ (all GPT-6): minimum prefix **1,024** visible tokens, and by default one implicit breakpoint at the end of the latest eligible message. A request can write up to 4 breakpoints. `prompt_cache_options.mode="explicit"` disables the implicit one (and with no breakpoints there's no caching).
- **Billing (GPT-5.6+):** writes cost **1.25×** input (30m TTL, the default) or **2.5×** (12h TTL; Responses only). Reads cost **0.1×**, or **0.05×** on gpt-6.1-sol/gpt-6.1-terra. `cached_tokens` excludes tokens billed as writes.
- `prompt_cache_retention` is **deprecated** (pre-5.6: `"in_memory"`/`"24h"`). Migrating from ≤5.5 means switching to `prompt_cache_options.ttl`. `prompt_cache_key` only optimises routing on pre-5.6 models; on 5.6+ it is just for separate cache accounting. Changing tools, effort or instructions changes the prefix, so use `configuration_update` items and `allowed_tools` to keep it stable.
### 1.10 Batch and Flex
```python
lines = [{"custom_id": f"t-{i}", "method": "POST", "url": "/v1/responses",   # qs: list[str]
          "body": {"model": MODEL, "input": q, "reasoning": {"effort": "none"}}} for i, q in enumerate(qs)]
f = client.files.create(file=("batch.jsonl", "\n".join(map(json.dumps, lines)).encode()), purpose="batch")
b = client.batches.create(input_file_id=f.id, endpoint="/v1/responses", completion_window="24h")
b = client.batches.retrieve(b.id)   # poll: validating→in_progress→finalizing→completed|failed|expired
if b.status == "completed":
    rows = [json.loads(x) for x in client.files.content(b.output_file_id).text.splitlines()]
    by_id = {r["custom_id"]: r["response"]["body"] for r in rows}    # output order != input order
flex = client.with_options(timeout=900.0).responses.create(model=MODEL, input="...", service_tier="flex")
```
verified by: introspection (`Batches.create`: `completion_window: Literal['24h']`, `endpoint` Literal incl. `/v1/responses`); mock run; https://developers.openai.com/api/docs/guides/batch.md ; …/guides/flex-processing.md
- Batch: 50% off, 24h window, separate rate-limit pool, up to 50,000 requests or 200 MB per file, one model per file. Failed lines go to `error_file_id`, and unfinished work at expiry is cancelled (completed lines are billed). The output file is deleted after 30 days.
- Flex: `service_tier="flex"` gets Batch rates on synchronous calls (beta). Expect `429 Resource Unavailable`, which isn't billed. Retry with backoff, or retry with `service_tier="auto"`. Raise the timeout as shown.
### 1.11 LEGACY / compatibility box: Chat Completions (D12 only)
```python
cc = client.chat.completions.create(model=MODEL, reasoning_effort="none",   # flat param here
    messages=[{"role": "developer", "content": "Be terse."}, {"role": "user", "content": "Hi"}])
print(cc.choices[0].message.content)   # vs resp.output_text; usage.prompt_tokens/completion_tokens
```
verified by: introspection (`chat.completions.create` has `reasoning_effort`, `max_completion_tokens`, `response_format`); README
- Supported "indefinitely" (README), but Responses is recommended for new work. **Tool calling on gpt-6-astra, gpt-6.1-sol and gpt-6.1-terra requires Responses.** On gpt-6-luna and gpt-6-sol, Chat tools work only with `reasoning_effort="none"`.

## 2. IDS / VERSIONS / PRICES (as of 2026-11-06; verify at https://developers.openai.com/api/docs/pricing)
Standard tier, USD per 1M tokens, prompts ≤272K input tokens. Source: model pages `…/docs/models/<id>.md` plus the pricing page.
| Model ID | Role | Effort values | Input | Cached read | 30m write | Output | Cutoff |
|---|---|---|---|---|---|---|---|
| `gpt-6-luna` | **cheapest; course default** | none…max | $0.10 | $0.01 | $0.125 | $0.50 | 2026-05-18 |
| `gpt-6.1-terra` | fast mid tier, vision/computer use | none…max | $1.00 | $0.05 | $1.25 | $5.00 | 2026-06-01 |
| `gpt-6.1-sol` | balanced / strong | low…max | $2.00 | $0.10 | $2.50 | $10.00 | 2026-04-30 |
| `gpt-6-astra` | flagship (docs' example model) | low…max | $10.00 | $1.00 | $12.50 | $50.00 | 2026-04-30 |
| `gpt-6-sol` | previous Sol (6.1 Sol supersedes) | none…max | $2.00 | $0.20 | $2.50 | $10.00 | 2026-04-20 |
- All five: 1,050,000-token context window, **max input 922,000**, max output 128,000, text+image in, text out.
- **Long-context surcharge:** a prompt with >272K input tokens is priced at **2× input and cache rates and 1.5× output for the whole request** (e.g. Luna becomes $0.20 in / $0.75 out).
- 12h cache write = 2.5× input (Luna $0.25). **Batch and Flex = 50% of Standard**, Fast mode = 2×, regional processing adds +10%.
- **Aliases vs snapshots:** a bare ID is an alias that points at a dated "default snapshot" (e.g. `gpt-5.5` → `gpt-5.5-2026-04-23`, `gpt-4o` → `gpt-4o-2024-08-06`). The text guide says to pin snapshots in production. **Every GPT-6 model currently lists only its bare ID as a snapshot**, so there is nothing dated to pin yet. Read `client.models.list()` → `Model.shutdown_date` (`"YYYY-MM-DD"` or None) to monitor retirements.
- Notice policy (deprecations page): GA models get ≥6 months, specialised variants ≥3 months, `*-preview` models can go with about 2 weeks' notice.
- Shutdowns (deprecations page). Lessons may use these only as history/lifecycle examples:
  - **2026-12-11:** `gpt-5`, `gpt-5-mini`, `gpt-5-nano`, `gpt-5-pro`, `o3`, `o3-pro` (replacements: gpt-5.6-sol/terra/luna).
  - **2027-01-14:** `gpt-4o` (2024-08-06, 2024-11-20), `gpt-4o-mini` (2024-07-18), `gpt-4.1`, `gpt-4.1-mini`. Replacement: **`gpt-6-luna`**.
  - **2027-04-01:** `gpt-5.1`, `gpt-5.4-nano`, `gpt-5.3-codex`.
  - **Already gone (2026-10-23):** `gpt-4.1-nano`, `gpt-4o-2024-05-13`, `o1`, `o3-mini`, `o4-mini`, `gpt-4-turbo`, `gpt-3.5-turbo`.
- Legacy list prices (still on the pricing page): gpt-4o $2.50/$10, gpt-4o-mini $0.15/$0.60, gpt-4.1 $2/$8, gpt-4.1-mini $0.40/$1.60, o3 $2/$8, gpt-5 $1.25/$10.
- SDK: openai **3.46.0** on PyPI (2026-11-05), Python ≥3.10. tiktoken **0.14.0** (2026-08-17). Source: https://pypi.org/pypi/openai/json, https://pypi.org/pypi/tiktoken/json

## 3. DON'T USE (→ replacement)
- `openai.ChatCompletion.create` / `openai.Completion` (pre-v1 module level) → `client.responses.create`. In the legacy box only: `client.chat.completions.create`.
- `response_format=` on Responses → `text={"format": {...}}` or `responses.parse(text_format=Model)`. Chat-style nested `{"type": "function", "function": {...}}` tools on Responses → flat tool dicts (§1.5).
- `resp.output[0].content[0].text` → `resp.output_text`, or iterate items by `.type`. `choices[0].message.content` belongs to Chat only.
- `temperature`/`top_p`/`top_logprobs`/logprobs with effort ≠ `none` → remove them, or use effort `none` on Luna/6.1 Terra. `effort="minimal"` and (on Astra/6.1 Sol) `"none"` → `"low"`.
- `prompt_cache_retention` (deprecated) → `prompt_cache_options={"ttl": "30m" | "12h"}`. `user=` → `safety_identifier=` plus `prompt_cache_key=`. Chat `max_tokens` (deprecated) → `max_completion_tokens`.
- `prompt=` reusable prompt objects (`v1/prompts`, **shut down 2026-11-30**) → keep prompts in code. **Evals platform** (`client.evals`; read-only since 2026-10-31, shut down 2026-11-30) → pytest harness or Promptfoo. **Assistants API** (`client.beta.assistants/threads`, shut down 2026-08-26) → Responses + Conversations. **Agent Builder** (shut down 2026-11-30) → Agents SDK.
- `client.fine_tuning.jobs` → closed to new orgs since 2026-05-07, and to everyone from 2027-01-06. Teach open-weight fine-tuning instead.
- `tiktoken.encoding_for_model("gpt-6-…")` raises `KeyError` → `tiktoken.get_encoding("o200k_base")` (approximate) or `client.responses.input_tokens.count`.
- `import httpx` + `http_client=httpx.Client(...)`, `httpx.Timeout`, `httpx.MockTransport` → the `httpx2.*` equivalents or `openai.DefaultHttpx2Client(...)`.
- Retired/closing IDs (`gpt-4o`, `gpt-4o-mini`, `gpt-4.1*`, `o1`, `o3*`, `o4-mini`, `gpt-5`, `gpt-5-mini/nano`, `gpt-3.5-turbo`, `whisper-1`) → `gpt-6-luna` via `ATLAS_MODEL`.

## 4. ⚠ VERIFY RESOLUTIONS (openai_core scope)
- D002 | whole-course budget estimate (prices) | CONFIRMED prices (§2). There is no official course total, so writers compute one from §2 with "as of 2026-11, verify at …/pricing". Don't invent a figure.
- D004 | exact counts from the token-count endpoint | CONFIRMED: `client.responses.input_tokens.count(model=, input=, instructions=, tools=…)` → `.input_tokens` (`POST /v1/responses/input_tokens`).
- D005 | >272K long-context surcharge | CONFIRMED: >272K input tokens → 2× input and cache rates, 1.5× output, for the full request (all GPT-6, 5.6, 5.5, 5.4). Add: max input is 922K of the 1.05M window.
- D006 | live sampling only with effort `none`, on which models | CONFIRMED: `gpt-6-luna`, `gpt-6.1-terra`, `gpt-6-sol` accept `none`. `gpt-6-astra` (HTTP 400) and `gpt-6.1-sol` don't. Use `gpt-6-luna`.
- D007 | aliases vs snapshots, gpt-4o retires 2027-01-14 | CONFIRMED with nuance: `gpt-4o` alias → `gpt-4o-2024-08-06`, shutdown 2027-01-14, replacement `gpt-6-luna`. GPT-6 models have **no dated snapshots** yet (bare ID only), so use `gpt-5.5` → `gpt-5.5-2026-04-23` as the pin example.
- D008 | `store` defaults to true | CONFIRMED (SDK docstring + migration guide). Retention is 30 days; Conversation items have no TTL. Also, SYLLABUS says "compaction (preview)" but the compaction guide carries no preview/beta label, so CORRECTED: drop "(preview)".
- D011 | CoT prompting only matters with effort `none` | UNVERIFIABLE as a hard rule. Docs only advise giving reasoning models "a clear goal, strong constraints, and an explicit output contract without prescribing every intermediate step". Teach it as a heuristic and measure on evals (⚠ verify note).
- D012 | httpx2 note | CONFIRMED + extended: openai 3.0.0 (2026-08-12) uses httpx2 and no longer installs `httpx`. Custom clients, transports and mocks must use `httpx2`. **TLS now uses the OS trust store (no certifi)**, so set `SSL_CERT_FILE` behind corporate proxies.
- D018 | prompt caching: prefix ordering, billed writes, TTLs | CONFIRMED: automatic, ≥1,024-token prefix, writes 1.25× (30m) / 2.5× (12h), reads 0.1× (0.05× on 6.1 Sol/Terra), `prompt_cache_options` + `prompt_cache_breakpoint`.
- D049 | server-side compaction | CONFIRMED: `context_management=[{"type": "compaction", "compact_threshold": N}]` on `responses.create`, plus standalone `client.responses.compact(model=, input=)`.

## 5. VERIFIED LINKS (all returned HTTP 200 on 2026-11-06; append `.md` to developers.openai.com pages for raw markdown)
- https://developers.openai.com/api/docs/guides/migrate-to-responses : Chat Completions → Responses: items, state, store default, common migration errors
- https://developers.openai.com/api/docs/guides/text : Text generation, `instructions` vs roles, `output_text`, pinning snapshots
- https://developers.openai.com/api/docs/guides/structured-outputs : `responses.parse`/`text_format`, `json_schema` strict, refusals, schema limits
- https://developers.openai.com/api/docs/guides/function-calling : Tool shapes, `function_call_output`/`call_id`, `tool_choice`, strict defaults
- https://developers.openai.com/api/docs/guides/conversation-state : Manual history, `previous_response_id` billing, Conversations API, 30-day retention
- https://developers.openai.com/api/docs/guides/compaction : Server-side compaction (`context_management`) and `/responses/compact`
- https://developers.openai.com/api/docs/guides/reasoning : Effort values, 25K headroom, `incomplete` handling, encrypted reasoning
- https://developers.openai.com/api/docs/guides/latest-model : GPT-6 family: which models accept `none`, sampling-param removal, Chat tool limits
- https://developers.openai.com/api/docs/guides/streaming-responses : Typed SSE streaming events
- https://developers.openai.com/api/docs/guides/token-counting : Input token count endpoint
- https://developers.openai.com/api/docs/guides/prompt-caching : Caching rules, write/read multipliers, TTLs, breakpoints
- https://developers.openai.com/api/docs/guides/batch : Batch API: JSONL format, limits, statuses, output mapping
- https://developers.openai.com/api/docs/guides/flex-processing : Flex tier: `service_tier="flex"`, timeouts, 429 handling
- https://developers.openai.com/api/docs/guides/error-codes : API error codes and meanings
- https://developers.openai.com/api/docs/models : Model catalog overview
- https://developers.openai.com/api/docs/models/gpt-6-luna : Course default model: specs, prices, effort values
- https://developers.openai.com/api/docs/models/gpt-6.1-terra : Mid-tier model page (accepts `none`)
- https://developers.openai.com/api/docs/pricing : All prices: standard/batch/flex/fast, long-context columns
- https://developers.openai.com/api/docs/deprecations : Shutdown dates and replacements (gpt-4o, o3, gpt-5, Evals, prompts, fine-tuning)
- https://developers.openai.com/api/docs/libraries : Official SDKs
- https://github.com/openai/openai-python/blob/main/httpx2.md : SDK httpx2 migration guide (custom clients, TLS trust store)
- https://github.com/openai/openai-python/blob/main/CHANGELOG.md : SDK changelog (3.0.0 breaking change)
- https://pypi.org/project/openai/ : openai on PyPI (version and Python requirement)
- https://github.com/openai/tiktoken/blob/main/tiktoken/model.py : tiktoken model→encoding map (no gpt-6 entry)
