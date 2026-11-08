# FACTS_PACK: openai_tools_media
Scope: OpenAI hosted tools (web_search, file_search + vector stores, code_interpreter, remote MCP, computer use, programmatic tool calling), media inputs, audio (STT/TTS/realtime), embeddings, moderation, background mode, product status.
**As of 2026-11-06.** Verified against `openai==3.46.0` (PyPI latest; Python 3.12 venv `/tmp/facts_openai_tools_media`; requires Python >=3.10, depends on `httpx2`). Realtime needs `openai[realtime]` (adds `websockets<16,>=13`). Docs: developers.openai.com `.md` pages fetched 2026-11-06. No live API calls were made.
Model in snippets: `MODEL = os.environ.get("ATLAS_MODEL", "gpt-6-luna")`. All four GPT-6 models (luna, 6.1-terra, 6.1-sol, astra) list web_search, file_search, code_interpreter, hosted_shell, skills, computer_use, mcp, tool_search on their model pages.

## 1. VERIFIED API SHAPES
### 1.1 Web search (Responses tool)
```python
import os
from openai import OpenAI
MODEL = os.environ.get("ATLAS_MODEL", "gpt-6-luna")
client = OpenAI()                                   # later snippets reuse client + MODEL
resp = client.responses.create(
    model=MODEL,
    tools=[{"type": "web_search", "search_context_size": "low",     # low | medium (default) | high
            "filters": {"allowed_domains": ["docs.python.org"]}}],  # no scheme; subdomains included
    include=["web_search_call.action.sources"],     # full source list, not just citations
    input="What changed in the latest Python release? Cite sources.",
)
for item in (i for i in resp.output if i.type == "message"):
    for ann in (a for part in item.content if part.type == "output_text" for a in part.annotations):
        if ann.type == "url_citation":              # url, title, start_index, end_index
            print(ann.url, ann.title)
```
verified by: introspection `openai/types/responses/web_search_tool_param.py` (type `web_search`; keys `external_web_access`, `filters.allowed_domains`, `search_context_size`, `user_location`) + https://developers.openai.com/api/docs/guides/tools-web-search.md
Sharp edges: output = `web_search_call` item (`action.type` = `search` | `open_page` | `find_in_page`) + `message` with `url_citation` annotations. Search is optional under `tool_choice="auto"`; `"required"` forces it. Docs require UIs to show citations as clickable links. `external_web_access=False` = cache-only (default True). Web search context window capped at 128K. Docs also list `filters.blocked_domains`, `return_token_budget` ("default"|"unlimited"), `search_content_types`, `image_settings`; these are **absent from SDK 3.46.0 TypedDicts** (dicts still send them, but type-checkers flag them), so treat them as ⚠ verify / optional prose. `user_location={"type": "approximate", "country": "GB", "city": ..., "region": ..., "timezone": ...}` (defaults to US when omitted).
### 1.2 File search + vector stores
```python
vs = client.vector_stores.create(name="atlas-kb")            # also: file_ids=, expires_after=, chunking_strategy=
with open("handbook.pdf", "rb") as f:
    vs_file = client.vector_stores.files.upload_and_poll(vector_store_id=vs.id, file=f)
if vs_file.status != "completed":                            # indexing can fail; check before querying
    raise RuntimeError(f"indexing ended with {vs_file.status}")
resp = client.responses.create(
    model=MODEL,
    input="What is our refund window?",
    tools=[{"type": "file_search", "vector_store_ids": [vs.id], "max_num_results": 4}],
    include=["file_search_call.results"],                    # results are NOT returned by default
)
print(resp.output_text)
```
verified by: introspection (`vector_stores.create(chunking_strategy, description, expires_after, file_ids, metadata, name)`; `vector_stores.files.upload_and_poll(vector_store_id, file, attributes, poll_interval_ms, max_wait_seconds, chunking_strategy)`; `create_and_poll(file_id, vector_store_id, ...)`; `vector_stores.search(vector_store_id, query, filters, max_num_results, ranking_options, rewrite_query)`; `FileSearchToolParam` requires `type` + `vector_store_ids`) + https://developers.openai.com/api/docs/guides/tools-file-search.md
Sharp edges: two-step alternative is `client.files.create(file=f, purpose="assistants")` then `vector_stores.files.create_and_poll(vector_store_id=, file_id=)` (docs still use `purpose="assistants"` for this). Annotations are `file_citation` (`file_id`, `filename`, `index`). Metadata filter: `"filters": {"type": "in", "key": "category", "value": [...]}` on `attributes` set per file. Ranking: `ranking_options={"ranker": "auto", "score_threshold": 0.x, "hybrid_search": {"embedding_weight":, "text_weight":}}`. Docs: file listing can lag behind completed indexing. Rate limit 500 RPM (Build) / 1000 RPM (Launch, Grow).
### 1.3 Code interpreter (hosted Python sandbox)
```python
resp = client.responses.create(
    model=MODEL,
    tools=[{"type": "code_interpreter",
            "container": {"type": "auto", "memory_limit": "1g"}}],  # container is REQUIRED
    tool_choice="required",
    include=["code_interpreter_call.outputs"],                 # logs/images are opt-in
    input="Use the python tool to compute the 30th Fibonacci number.",
)
print(resp.output_text)
```
verified by: introspection (`CodeInterpreter`: `container: Required[str | {type:"auto", file_ids, memory_limit: "1g"|"4g"|"16g"|"64g", network_policy}]`; `client.containers.create(name, expires_after, file_ids, memory_limit, network_policy, skills)`) + https://developers.openai.com/api/docs/guides/tools-code-interpreter.md
Sharp edges: output has `code_interpreter_call` items (`container_id`, `code`, `outputs`, `status`). Explicit mode = `client.containers.create(name=..., memory_limit="4g")` then `"container": container.id`. Containers **expire after 20 min idle** and can't be revived, so download files while active. Generated files arrive as `container_file_citation` annotations (`container_id`, `file_id`, `filename`); fetch via the containers files content endpoint. Docs: the model knows it as "the python tool". Rate limit 100 RPM per org.
### 1.4 Remote MCP tool
```python
resp = client.responses.create(
    model=MODEL,
    tools=[{"type": "mcp",
            "server_label": "openai_docs",                     # REQUIRED
            "server_url": "https://developers.openai.com/mcp", # or tunnel_id (Secure MCP Tunnel)
            "allowed_tools": ["search_openai_docs"],           # list, or {"tool_names": [...], "read_only": True}
            "require_approval": "always",                      # "always" | "never" | {"never": {"tool_names": [...]}}
            # "authorization": os.environ["MCP_OAUTH_TOKEN"],  # OAuth bearer; never stored, resend every call
            }],
    input="Find the Responses API streaming guide.",
)
approvals = [i for i in resp.output if i.type == "mcp_approval_request"]
```
Approve with a new call: `previous_response_id=resp.id, input=[{"type": "mcp_approval_response", "approve": True, "approval_request_id": approvals[0].id}]` (same `tools`).
verified by: introspection (`Mcp`: `server_label` + `type` required; `server_url | connector_id | tunnel_id` (one required); `allowed_tools`, `require_approval`, `authorization: str`, `headers: Dict[str,str]` ("for authentication or other purposes"), `server_description`, `defer_loading`, `allowed_callers`) + https://developers.openai.com/api/docs/guides/tools-connectors-mcp.md
Sharp edges: **approvals default ON** (OpenAI asks before sharing data with a server). Output items: `mcp_list_tools`, `mcp_call` (`arguments`, `output`, `error` as JSON strings), `mcp_approval_request`. Keep the `mcp_list_tools` item in context to avoid re-listing. Transports: Streamable HTTP or HTTP/SSE. No per-call fee, only tokens. `connector_id` (Dropbox, Gmail, ...) is **deprecated for models released after 2026-09-01**. Prefer `authorization` over raw `headers` for OAuth tokens (docs only show `authorization`; `headers` is SDK-verified but its doc example is absent).
### 1.5 Computer use (GA `computer` tool; you run the environment)
```python
# fragment: loop sketch; png_b64 comes from your screenshot helper; repeat until no computer_call items
resp = client.responses.create(model=MODEL, tools=[{"type": "computer"}],
                               input="Open the Filters panel, then type penguin in search.")
for call in (i for i in resp.output if i.type == "computer_call"):
    for action in call.actions or []:        # click, double_click, drag, move, scroll, keypress, type, wait, screenshot
        ...                                  # your Playwright/VM handler executes it (behind an allowlist)
    resp = client.responses.create(
        model=MODEL, tools=[{"type": "computer"}], previous_response_id=resp.id,
        input=[{"type": "computer_call_output", "call_id": call.call_id,
                "output": {"type": "computer_screenshot",
                           "image_url": f"data:image/png;base64,{png_b64}", "detail": "original"}}])
```
verified by: introspection (`ComputerToolParam` = `{"type": "computer"}` only; `ResponseComputerToolCall.actions` (list; legacy single `action` also present), `.pending_safety_checks`; `computer_call_output` requires `call_id`, `output{type:"computer_screenshot", image_url|file_id}`, optional `acknowledged_safety_checks`) + https://developers.openai.com/api/docs/guides/tools-computer-use.md
Sharp edges: docs add `"detail": "original"` inside the screenshot object, but SDK 3.46.0's `ResponseComputerToolCallOutputScreenshotParam` has no `detail` key (sent as-is at runtime; type-checkers flag it). The first call may contain only a `screenshot` action. Models: all four GPT-6 models list `computer_use` (docs examples use `gpt-6.1-sol`; Terra is marketed for "precise computer use"). For `gpt-6-astra` OpenAI recommends the **code-execution** path (a function tool that runs Playwright/PyAutoGUI scripts) over the `computer` tool. The `computer-use-preview` model was **shut down 2026-07-23**; the `computer_use_preview` tool type (needs `display_width/height/environment`) is the legacy shape, so use `computer`. Pending safety checks need human acknowledgement.
### 1.6 Programmatic Tool Calling (exists on OpenAI)
Real feature: the model writes **JavaScript** that runs in an OpenAI-hosted, isolated V8 runtime (no Node, network, fs) and calls your tools in loops/parallel. Enable with `{"type": "programmatic_tool_calling"}` in `tools` and set `"allowed_callers": ["programmatic"]` (or `["direct","programmatic"]`) on eligible tools (function, custom, mcp, apply_patch, shell, code_interpreter). Output items: `program` (code, `call_id`), `function_call` with `caller.caller_id`, `program_output` (`result`, `status`). Return results as `function_call_output` **copying `caller` unchanged**. Supported on GPT-6 (latest-model guide: "GPT-6 also supports ... Programmatic Tool Calling"); enabled by default in the Agents API. Verified by: introspection (`ProgrammaticToolCalling` type, `allowed_callers` on `Mcp`/`CodeInterpreter`) + https://developers.openai.com/api/docs/guides/tools-programmatic-tool-calling.md. Teach as concept + one short loop at most; it is the newest surface (⚠ verify before a full lesson).
### 1.7 Media inputs: `input_image` and `input_file` (PDF)
```python
import base64, pathlib
pdf_b64 = base64.b64encode(pathlib.Path("invoice.pdf").read_bytes()).decode()
resp = client.responses.create(model=MODEL, input=[{"role": "user", "content": [
    {"type": "input_text", "text": "Extract the invoice total and the vendor."},
    {"type": "input_image", "image_url": "https://example.com/receipt.png", "detail": "low"},
    {"type": "input_file", "filename": "invoice.pdf",
     "file_data": f"data:application/pdf;base64,{pdf_b64}", "detail": "low"},
]}])
print(resp.output_text)
```
verified by: introspection (`ResponseInputImageParam`: `type`, `detail: Required["low"|"high"|"auto"|"original"]`, `image_url | file_id`; `ResponseInputFileParam`: `type`, `detail: "auto"|"low"|"high"` (default auto), `file_data | file_id | file_url`, `filename`) + https://developers.openai.com/api/docs/guides/images-vision.md + https://developers.openai.com/api/docs/guides/file-inputs.md
Sharp edges: images go in as a URL, a base64 data URL, or `file_id` (upload with `purpose="vision"`); PDFs uploaded for model input use `purpose="user_data"`. API default `detail` is `auto`, but the SDK TypedDict marks image `detail` **Required**, so always pass it. `original` exists only on newer models. PDFs: the API sends **extracted text + page images** (vision models), so tokens add up; each file <50 MB and the request total is 50 MB; on GPT-5.6+ `auto` = `high`. Non-PDF docs (.docx/.pptx/.txt) give text only, no embedded charts. Images: PNG/JPEG/WEBP/non-animated GIF; up to 1,500 images and 512 MB per request.
**Image token cost (patch-based, GPT-5.x/6):** `patches = ceil(w/32)*ceil(h/32)`, downscaled to fit the detail level's patch budget (high = 2,500), then `tokens = ceil(patches * multiplier)`. Only `gpt-6-astra` (multiplier 1.2; `low` fits 512x512) is in the published table. Worked example: 1024x1024 at `high` = 1024 patches = 1,229 tokens; >30,000 patches gets rejected. **Luna/Terra/Sol are not in the sizing table**, so get exact counts from `client.responses.input_tokens.count(...)` or the image cost calculator, never by hand-quoting a figure.
### 1.8 Audio: transcription, TTS, realtime
```python
with open("standup.wav", "rb") as f:                         # mp3/mp4/mpeg/mpga/m4a/wav/webm, <=25 MB
    tr = client.audio.transcriptions.create(
        model="gpt-transcribe", file=f,
        prompt="Engineering standup about the Atlas project.",
        keywords=["Atlas", "Orbit", "pgvector"],              # literal-term hints
        languages=["en"],                                     # replaces singular `language`; don't send both
    )
print(tr.text)                                                # response also carries detected `languages`
```
verified by: introspection (`audio.transcriptions.create(file, model, chunking_strategy, include, keywords, known_speaker_names, known_speaker_references, language, languages, prompt, response_format, stream, temperature, timestamp_granularities)`; docs show `keywords`/`languages` via `extra_body`, but SDK 3.46.0 has them as **first-class kwargs**) + https://developers.openai.com/api/docs/guides/speech-to-text.md
Sharp edges: keywords can't contain `<`, `>` or newlines (the whole request is rejected). `timestamp_granularities` and `verbose_json` word timestamps are **whisper-1 only**; diarization (`diarized_json`) needs `gpt-4o-transcribe-diarize`. All of those are deprecated (shutdown 2027-02-26), so don't teach word timestamps or diarization as a durable path. Live audio uses Realtime transcription (`gpt-live-transcribe`).

**TTS (status change):** `client.audio.speech.with_streaming_response.create(model="gpt-4o-mini-tts", voice="marin", input=..., instructions=...)` then `.stream_to_file(path)` still works (SDK verified: `speech.create(input, model, voice, instructions, response_format, speed, stream_format)`), **but `tts-1`, `tts-1-hd` and `gpt-4o-mini-tts` shut down 2027-01-06.** The replacement is `gpt-realtime-2.1-mini` on the **Realtime API** (it isn't accepted at `/v1/audio/speech`). So a "chained STT → LLM → TTS" lesson must either label `/v1/audio/speech` as retiring or do the TTS step in a Realtime session. Source: https://developers.openai.com/api/docs/guides/text-to-speech.md

**Realtime (GA; beta header `OpenAI-Beta: realtime=v1` removed 2026-05-12).** `uv add "openai[realtime]"`.
```python
import asyncio
from openai import AsyncOpenAI
async def main() -> None:
    client = AsyncOpenAI()
    async with client.realtime.connect(model="gpt-realtime-2.1-mini") as conn:
        await conn.session.update(session={"type": "realtime", "output_modalities": ["text"]})
        await conn.conversation.item.create(item={"type": "message", "role": "user",
                                                  "content": [{"type": "input_text", "text": "Say hello!"}]})
        await conn.response.create()
        async for event in conn:
            if event.type == "response.output_text.delta":
                print(event.delta, end="", flush=True)
            elif event.type in ("response.done", "error"):  # errors arrive as events, NOT exceptions
                break
asyncio.run(main())
```
verified by: introspection (`realtime.connect(call_id, model, ...)`; `conn.session.update(session=)`, `conn.conversation.item.create(item=)`, `conn.response.create(response=)`, `conn.input_audio_buffer.append/commit/clear`; session `type: Required["realtime"]`, `output_modalities: ["text"]|["audio"]`) + SDK README (dist-info METADATA) + https://developers.openai.com/api/docs/guides/realtime-conversations.md
Sharp edges: `output_modalities` is **either** `["audio"]` **or** `["text"]`, not both. Audio config sits under `session.audio.input` (`format: {"type": "audio/pcm", "rate": 24000}`, `turn_detection: {"type": "semantic_vad"}`) and `session.audio.output` (`voice`: alloy, ash, ballad, coral, echo, sage, shimmer, verse, marin, cedar; marin/cedar recommended; fixed after the first audio). Events: `response.output_audio.delta`, `response.output_audio_transcript.delta`. Sessions max out at **60 min**. Browsers get an ephemeral key from `client.realtime.client_secrets.create(session=...)` and connect over WebRTC (`/v1/realtime/calls`). **GPT-Live** (`gpt-live-1`, full-duplex with a delegated backend; `client.live`, `/v1/live/sessions`) is newer; describe it in prose only (⚠ verify).
### 1.9 Embeddings
```python
emb = client.embeddings.create(model="text-embedding-3-small",
                               input=["refund policy", "shipping times"],  # str or list[str]
                               dimensions=512)               # optional truncation (3-* models only)
vectors = [d.embedding for d in emb.data]                    # list[float]; emb.usage.prompt_tokens
```
verified by: introspection (`embeddings.create(input, model, dimensions, encoding_format, user)`) + https://developers.openai.com/api/docs/guides/embeddings.md
Sharp edges: default dims are **1536 (small) / 3072 (large)**; max input is 8,192 tokens per input. Changing the model or `dimensions` means re-indexing everything. If you truncate vectors yourself instead of using `dimensions=`, re-normalize them.
### 1.10 Moderation
```python
mod = client.moderations.create(model="omni-moderation-latest", input="text to check")
r = mod.results[0]; print(r.flagged, r.categories, r.category_scores)
# Inline, alongside generation:
resp = client.responses.create(model=MODEL, input="...", moderation={"model": "omni-moderation-latest"})
if resp.moderation.input.type == "error": raise RuntimeError(resp.moderation.input.message)
print(resp.moderation.input.flagged, resp.moderation.output.flagged)
```
verified by: introspection (`moderations.create(input, model)`; `responses.create(moderation={model: Required[str], policy})`; `Response.moderation.input/.output` = `moderation_result` | `error`) + https://developers.openai.com/api/docs/guides/moderation.md
Sharp edges: **free**. Text + images (image input: `[{"type":"text",...},{"type":"image_url","image_url":{"url":...}}]`, ≤20 MB); no audio. Inline moderation **does not block** output; the model generates normally and you must check the result before showing it. With streaming, scores arrive only after the full output. Moderation covers tool arguments/outputs but not tool schemas. The SDK also has `moderation.policy` with `mode: "score"|"block"`, but **it is undocumented in the guide; omit it**.
### 1.11 Background mode
```python
import time
resp = client.responses.create(model=MODEL, input="Write a long market report.", background=True)
while resp.status in {"queued", "in_progress"}:
    time.sleep(2)
    resp = client.responses.retrieve(resp.id)
print(resp.status, resp.output_text)          # completed | failed | cancelled | incomplete
```
verified by: introspection (`responses.create(background=...)`; `responses.retrieve(response_id, include, include_obfuscation, starting_after, stream)`; `responses.cancel(response_id)`; `Response.status` literals) + https://developers.openai.com/api/docs/guides/background.md
Sharp edges: cancel with `client.responses.cancel(resp.id)` (idempotent). Background works with `store=False`, but response data is still **stored temporarily (~10 min) for polling**, so poll promptly. ZDR projects always run background with `store=false`. Background + `stream=True` lets you resume a dropped stream: `client.responses.stream(response_id=..., starting_after=cursor)` (`sequence_number`; skip `keepalive` events). A stream can only be resumed if it was created with `stream=True`. Time to first token is higher than for synchronous calls. `store` defaults to **true** (≥30 days).
### 1.12 Product status (as of 2026-11-06)
| Surface | Status | Teach? |
|---|---|---|
| Agents API (managed Codex harness; `client.beta.agents`, sessions/environments) | **beta** namespace; billed at model + tool + container rates | prose/comparison row only (⚠ verify) |
| Skills (`SKILL.md`, Agent Skills standard; `client.skills.create(files=...)`; mounted via `{"type":"shell","environment":{"type":"container_auto","skills":[{"type":"skill_reference","skill_id":...}]}}`) | live; uploaded versions can 404 briefly after upload | concept + SKILL.md format; hosted-shell attach optional |
| ChatKit | **still available** (custom-server integration with ChatKit Python SDK) | overview OK |
| Agent Builder (hosted ChatKit workflows depend on it) | deprecated; **shuts down 2026-11-30** | no |
| Evals platform (dashboard + `client.evals`) | read-only since 2026-10-31; **shuts down 2026-11-30**; OpenAI points to Promptfoo | no |
| Reusable prompts (`v1/prompts`, `prompt={"id": "pmpt_..."}`) | **shuts down 2026-11-30**; move prompts into code | no |
| Assistants API (`client.beta.assistants/threads` still in SDK) | **shut down 2026-08-26** → Responses + Conversations | no |
| Self-serve fine-tuning | 2026-05-07 closed to orgs that never fine-tuned; 2026-07-02 closed to orgs with no fine-tuned inference in the last 60 days; **2027-01-06 no new jobs for anyone**; tunable bases (gpt-4.1, gpt-4.1-mini, gpt-4o, gpt-4o-mini) shut down 2027-01-14 | no (open-weight LoRA instead) |

Sources: https://developers.openai.com/api/docs/deprecations.md, …/guides/chatkit.md, …/guides/agents.md, …/guides/agents-api/overview.md, …/guides/tools-skills.md

## 2. IDS / VERSIONS / PRICES (as of 2026-11-06; verify at https://developers.openai.com/api/docs/pricing)
| Item | ID / value | Price | Source |
|---|---|---|---|
| Web search tool | `{"type":"web_search"}` | $10 / 1k calls + search content tokens at model rates | pricing |
| File search tool | `file_search` | $2.50 / 1k calls (Responses only); storage $0.10/GB-day, 1 GB free | pricing |
| Containers (code interpreter, hosted shell) | `memory_limit` 1g/4g/16g/64g | $0.03 / $0.12 / $0.48 / $1.92 per 20-min session (billed per minute, 5-min minimum) | pricing |
| Remote MCP tool | `mcp` | no per-call fee; tokens only | tools-connectors-mcp |
| Computer use | `computer` on gpt-6-luna / 6.1-terra / 6.1-sol / astra | model token rates | model pages |
| Transcription (file) | `gpt-transcribe` | $0.0045 / min | models/gpt-transcribe, pricing |
| Transcription (live) | `gpt-live-transcribe`, `gpt-realtime-whisper` | $0.017 / min | pricing |
| Realtime speech-to-speech | `gpt-realtime-2.1` | text $4 in / $24 out; audio $32 / $64 per 1M | models/gpt-realtime-2.1 |
| Realtime (cheap; TTS replacement) | `gpt-realtime-2.1-mini` | text $0.60 / $2.40; audio $10 / $20 per 1M | pricing |
| GPT-Live voice | `gpt-live-1` | $0.05 / min (+ backend usage) | pricing |
| TTS (retiring 2027-01-06) | `gpt-4o-mini-tts` | text in $0.60/1M; audio out $12/1M | pricing |
| Embeddings | `text-embedding-3-small` (1536-d) / `-3-large` (3072-d) | $0.02 / $0.13 per 1M tokens | pricing, embeddings guide |
| Moderation | `omni-moderation-latest` | free | pricing, moderation guide |
| SDK | `openai==3.46.0` (Python ≥3.10, httpx2) | — | https://pypi.org/pypi/openai/json |

## 3. DON'T USE
- `web_search_preview` → `web_search` (preview lacks filters/`external_web_access`; costs $25/1k on non-reasoning models). `gpt-4o(-mini)-search-preview` shut down 2026-07-23.
- `computer-use-preview` model / `computer_use_preview` tool → `{"type":"computer"}` on a GPT-6 model.
- MCP `connector_id` on models released after 2026-09-01 → `server_url` or `tunnel_id`.
- `whisper-1`, `gpt-4o-transcribe`, `gpt-4o-mini-transcribe`, `gpt-4o-transcribe-diarize`, `/v1/audio/translations` (shut down 2027-02-26) → `gpt-transcribe` (files) / `gpt-live-transcribe` (live) / `gpt-realtime-translate`.
- `tts-1`, `tts-1-hd`, `gpt-4o-mini-tts` (shut down 2027-01-06) → `gpt-realtime-2.1-mini` via the Realtime API.
- `gpt-realtime`, `gpt-realtime-mini`, `gpt-audio(-mini)` (shut down 2027-01-20) → `gpt-realtime-2.1` / `gpt-realtime-2.1-mini` / `gpt-audio-1.5`. `gpt-4o-realtime-preview*` already shut down; `OpenAI-Beta: realtime=v1` removed 2026-05-12 → GA `client.realtime`.
- `client.beta.realtime` → `client.realtime`. `text-moderation-*` (shut down) → `omni-moderation-latest`. `text-embedding-ada-002` (legacy) → `text-embedding-3-small`.
- Assistants/threads, Evals platform, reusable prompts, Agent Builder, `fine_tuning.jobs` → see 1.12.
- The `prompt={"id": ...}` param in Responses/Realtime `session.update` (it's prompt objects) → instructions in code.

## 4. ⚠ VERIFY RESOLUTIONS
- D014 | `input_image` + image token cost | CORRECTED: patch-based (32px patches × 1.2 on astra; 1024² `high` ≈ 1,229 tokens); luna/terra/sol aren't in the published table, so measure with `responses.input_tokens.count`, don't quote a number. `detail` = low/high/auto/original.
- D014 | `input_file` for PDFs | CONFIRMED: text + page images; `detail` low/high/auto (auto=high on 5.6+); 50 MB per request; `purpose="user_data"`. Also covers D024 (native file input as the parsing alternative; non-PDFs are text-only).
- D014 | transcription with `gpt-transcribe`; whisper-1 retires 2027-02-26 | CONFIRMED ($0.0045/min; `keywords`/`languages` are native kwargs in SDK 3.46). Note that word timestamps and diarization exist only on deprecated models.
- D032 | hosted `file_search` + vector stores pricing | CONFIRMED: $2.50/1k calls + $0.10/GB-day storage (1 GB free).
- D038 | web search $ per call | CONFIRMED: $10/1k calls + content tokens (preview tool on non-reasoning models: $25/1k).
- D038 | code interpreter / hosted execution | CONFIRMED: container required; $0.03–$1.92 per 20-min session by memory tier; 20-min idle expiry.
- D038 | programmatic tool calling | CONFIRMED (it exists): `{"type":"programmatic_tool_calling"}` + `allowed_callers`; JS in a hosted V8; GPT-6. Keep it as an aside.
- D056 | managed Agents API as a runtime choice | CONFIRMED as **beta** (`client.beta.agents`, Codex harness). Comparison row + prose only.
- D060 | Agent Skills (`SKILL.md`) | CONFIRMED: Responses shell tool `skill_reference`; compatible with the open Agent Skills standard (agentskills.io; not fetched).
- D070 | moderation API free | CONFIRMED; inline `moderation={"model": ...}` scores but doesn't block.
- D072 | computer-use model support | CONFIRMED: `computer` tool on all GPT-6 models; the preview model is shut down; astra prefers code execution.
- D073 + D078 | `store=False`, retention; background mode + polling | CONFIRMED (see 1.11): default true (≥30 days); background + `store=False` still keeps data ~10 min. ZDR forces `store=false`.
- D080 | ChatKit status | CORRECTED: ChatKit is **not** closing; only Agent Builder (and hosted Agent-Builder-backed ChatKit workflows) shut down 2026-11-30. Keep the overview, custom-server path.
- D081 | realtime model IDs | CORRECTED/extended: `gpt-realtime-2.1` / `gpt-realtime-2.1-mini` (GA, `client.realtime`); `gpt-realtime`/`-mini` retire 2027-01-20. **TTS models retire 2027-01-06**, so the chained STT→LLM→TTS path needs Realtime for the TTS step (or a "retiring" label). GPT-Live (`gpt-live-1`) is prose only.
- D095 (context) | hosted fine-tuning closure | CONFIRMED + one added date (2026-07-02 rule); all tunable bases shut down 2027-01-14.

## 5. VERIFIED LINKS (all returned HTTP 200 on 2026-11-06; append `.md` for the markdown form)
- https://developers.openai.com/api/docs/guides/tools-web-search: web_search config, citations, filters, sources
- https://developers.openai.com/api/docs/guides/tools-file-search: file_search tool + vector store setup
- https://developers.openai.com/api/docs/guides/retrieval: vector stores, attributes, metadata filters, chunking
- https://developers.openai.com/api/docs/guides/tools-code-interpreter: code interpreter, containers, expiry, file citations
- https://developers.openai.com/api/docs/guides/tools-connectors-mcp: remote MCP tool, approvals, auth, connectors
- https://developers.openai.com/api/docs/guides/tools-computer-use: computer tool loop, code-execution path, safety
- https://developers.openai.com/api/docs/guides/tools-programmatic-tool-calling: Programmatic Tool Calling
- https://developers.openai.com/api/docs/guides/tools-skills: Agent Skills (SKILL.md) with shell / Agents API
- https://developers.openai.com/api/docs/guides/images-vision: input_image, detail levels, image token math
- https://developers.openai.com/api/docs/guides/file-inputs: input_file / PDFs, limits, detail
- https://developers.openai.com/api/docs/guides/speech-to-text: file transcription with gpt-transcribe
- https://developers.openai.com/api/docs/guides/text-to-speech: Speech API + TTS deprecation notice
- https://developers.openai.com/api/docs/guides/realtime-conversations: session.update, events, voices, VAD
- https://developers.openai.com/api/docs/guides/voice-agents: GPT-Live vs Realtime vs chained pipeline
- https://developers.openai.com/api/docs/guides/embeddings: embeddings, dimensions, max input
- https://developers.openai.com/api/docs/guides/moderation: moderation endpoint + inline moderation
- https://developers.openai.com/api/docs/guides/background: background mode, polling, cancel, resume streams
- https://developers.openai.com/api/docs/guides/your-data: store/retention, ZDR, per-endpoint retention table
- https://developers.openai.com/api/docs/guides/agents: Agents API vs Agents SDK vs Responses comparison
- https://developers.openai.com/api/docs/guides/chatkit: ChatKit (still available) + Agent Builder shutdown note
- https://developers.openai.com/api/docs/pricing: all prices (models, built-in tools, audio, embeddings)
- https://developers.openai.com/api/docs/deprecations: shutdown dates (models, Evals, prompts, Agent Builder, fine-tuning)
- https://developers.openai.com/cookbook/examples/evaluation/moving-from-openai-evals-to-promptfoo: Evals → Promptfoo migration
