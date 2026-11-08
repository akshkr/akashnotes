# Course Reference: Models, Pricing, Library Notes and the Day Map (v2)

This is the **single source of truth** for fast-moving facts. When a lesson states a model ID, a
price or "see Day N", it must agree with this file. **Update this file first**, then any lesson
that restates the value.

> ⚠️ **Everything below moves fast.** It was verified on **2026-11-06** against the provider docs
> and the installed packages (details in `docs/facts_pack/`). Before relying on a number,
> check it at the provider's pricing and model pages. Every price shown in a lesson must carry
> "as of 2026-11, verify".
> The v1 version of this file is archived in `.restructure/v2/REFERENCE.v1.md`.

---

## OpenAI (primary provider): Responses API, SDK `openai` 3.x

| Model ID | Role | Reasoning effort | Input $/1M | Cached read | Output $/1M |
|---|---|---|---|---|---|
| `gpt-6-luna` | cheapest; **course default** (`ATLAS_MODEL`) | none…max | $0.10 | $0.01 | $0.50 |
| `gpt-6.1-terra` | fast mid tier, vision, computer use | none…max | $1.00 | $0.05 | $5.00 |
| `gpt-6.1-sol` | balanced / strong | low…max (no `none`) | $2.00 | $0.10 | $10.00 |
| `gpt-6-astra` | flagship | low…max (`none` returns 400) | $10.00 | $1.00 | $50.00 |

- **Limits:** a 1.05M-token context window, max input 922K, max output 128K.
- **Long-context surcharge:** above 272K input tokens, the **whole request** is billed at 2× input and 1.5× output.
- **Price tiers:** Batch and Flex cost 50% of standard.
- **Prompt caching:** automatic. Cache writes cost 1.25× input (30-minute TTL) or 2.5× (12-hour TTL); reads cost 0.1×.
- **Sampling:** `temperature`, `top_p` and logprobs only work with `reasoning={"effort": "none"}`, on Luna or 6.1 Terra.
- **Snapshots:** GPT-6 models are **alias-only** (no dated snapshots yet). `gpt-5.5 → gpt-5.5-2026-04-23` illustrates pinning. Watch `Model.shutdown_date` for retirements.
- **Retired or retiring:**

  | Shutdown date | Models |
  |---|---|
  | already shut down (2026-10-23) | `gpt-3.5-turbo`, `gpt-4.1-nano`, `o1`, `o3-mini`, `o4-mini` |
  | 2026-12-11 | `gpt-5`, `gpt-5-mini`, `gpt-5-nano`, `gpt-5-pro`, `o3`, `o3-pro` |
  | 2027-01-14 | `gpt-4o`, `gpt-4o-mini`, `gpt-4.1`, `gpt-4.1-mini` (replacement: `gpt-6-luna`) |
- **Closing products (never teach them):**
  - the Evals platform (shut down 2026-11-30)
  - reusable prompt objects (2026-11-30)
  - Agent Builder (2026-11-30)
  - the Assistants API (shut down 2026-08-26)
  - self-serve fine-tuning (closed to new orgs since 2026-05-07; closed to everyone from 2027-01-06)

| Capability | ID | Price (as of 2026-11, verify) |
|---|---|---|
| Embeddings | `text-embedding-3-small` (1536-d), `text-embedding-3-large` (3072-d) | $0.02 / $0.13 per 1M |
| Transcription | `gpt-transcribe` (files), `gpt-live-transcribe` (live) | $0.0045/min (files) |
| Realtime / speech out | `gpt-realtime-2.1`, `gpt-realtime-2.1-mini` | see the pricing page |
| Moderation | `omni-moderation-latest` | free |
| Web search tool | `{"type": "web_search"}` | $10 per 1k calls + content tokens |
| File search tool | `file_search` + vector stores | $2.50 per 1k calls; storage $0.10/GB-day (1 GB free) |
| Open-weight | `gpt-oss-20b`, `gpt-oss-120b` | self-hosted |

Retiring audio models: `whisper-1` and `gpt-4o-*-transcribe` shut down on 2027-02-26. `tts-1`,
`tts-1-hd` and `gpt-4o-mini-tts` shut down on 2027-01-06; use the Realtime models instead.
`gpt-realtime` and `gpt-realtime-mini` shut down on 2027-01-20.

## Anthropic (introduction only: D2 and D7), SDK `anthropic` 2.6

| ID | Role | Input / Output per 1M (⚠ verify) |
|---|---|---|
| `claude-haiku-5-5` | cheapest; the D2 "hello" | $0.10 / $0.50 (prompts ≤100K tokens) |
| `claude-sonnet-5-5` | balanced | $2 / $10 |
| `claude-opus-5-5` | flagship | $4 / $20 |
| `claude-fable-5-1` | premium | $10 / $50 |

- Use bare IDs only; never append a date suffix.
- `messages.create` requires `max_tokens` and takes `system` as a top-level parameter. It has **no** `temperature` or `top_p`.
- Depth is set with `output_config={"effort": …}`. Never teach `budget_tokens`.
- Older IDs that are still valid: `claude-opus-4-8`, `claude-opus-4-6`, `claude-sonnet-4-6`, `claude-haiku-4-5`.

---

## Library notes (common drift points, as of 2026-11-06)

**LLM SDKs**
- **openai 3.46:**
  - Use `client.responses.create/parse/stream`.
  - Chat Completions appears only in D12's legacy box. Tool calling on Astra, 6.1 Sol and 6.1 Terra requires Responses.
  - The SDK uses **httpx2**, so a custom client must come from `httpx2` or `openai.DefaultHttpx2Client`. It uses the OS trust store, not certifi.
  - `output_text` can include commentary text.
  - `previous_response_id` can't be combined with `conversation`.
- **tiktoken 0.14:** has no gpt-6 mapping. Use `get_encoding("o200k_base")` as an approximation, or `client.responses.input_tokens.count` for exact counts.
- **Pydantic v2:** `@field_validator` / `@model_validator`, `Field(default_factory=...)`.

**Agent frameworks**
- **LangGraph 1.2:**
  - Human-in-the-loop uses `interrupt()` + `Command(resume=)`.
  - `InMemorySaver` is the in-memory checkpointer. `SqliteSaver` and `PostgresSaver` ship as separate `langgraph-checkpoint-*` packages.
  - `update_state` forks a new checkpoint rather than editing the old one.
- **LangChain 1.x:**
  - Agents come from `from langchain.agents import create_agent`.
  - Always pass `model=` and `use_responses_api=True` to `ChatOpenAI`. Its default model, `gpt-3.5-turbo`, is retired.
- **openai-agents 0.24.0:** pin this exact version. The managed "Agents API" isn't in the SDK.
- **MCP:**
  - **SDK `mcp` 2.3** uses `MCPServer`. Spec revision 2026-07-28 is stateless.
  - The Inspector needs Node 22.19 or later.
  - The Responses `mcp` tool needs a **public URL** (or `tunnel_id`), not localhost.
  - For OAuth resource servers, set `validate_token_resource=True`.

**RAG and data**
- **pgvector-python 0.5:**
  - Use psycopg 3 with `register_vector`.
  - Queries return `pgvector.Vector`, not numpy arrays.
  - PG 18 images mount the volume at `/var/lib/postgresql`.
- **Postgres full-text** (`ts_rank_cd`) is **not BM25**.
- **Rerankers:**
  - Cohere: `rerank-v5.0-pro` / `rerank-v5.0-fast`.
  - Cross-encoder: `cross-encoder/ms-marco-MiniLM-L6-v2`.
- **pypdf 7.0:** import with `from pypdf import PdfReader`.
- **Presidio:** `AnalyzerEngine()` auto-downloads a 401 MB spaCy model.
- **SQLite read-only safety:** `mode=ro` + `setlimit(SQLITE_LIMIT_ATTACHED, 0)` + a sqlglot SELECT-only check.

**Evals, observability, safety**
- **Tracing:**
  - Phoenix/OpenInference **does** trace `responses.create` (as `llm.*` attributes).
  - `opentelemetry-instrumentation-openai-v2` does **not** trace Responses yet.
  - The OTel GenAI conventions (Development status) now live in the `semantic-conventions-genai` repo.
- **Not installed in the course:**
  - `ragas` 0.4.3: a fresh install breaks and downgrades `openai`.
  - `guardrails-ai` and `garak`: both require `openai<3`.

  Mention them in comparison rows only.
- **Promptfoo:** now part of OpenAI. Needs Node 22.22 or later. Red-team probes are generated on its hosted service unless that's disabled.
- **DeepEval 4.x:** `LLMTestCaseParams` was renamed to `SingleTurnParams`.

**Serving, UI, deployment**
- **FastAPI:** use `lifespan`, not `@app.on_event`.
- **`python:3.12-slim`:** has no curl, so write healthchecks in Python.
- **Gradio 6:** `ChatInterface`/`Chatbot` have **no `type=`** (passing it raises `TypeError`). History content is a list of parts.
- **Free hosting:**
  - Free HF Spaces no longer host CPU Gradio apps; that needs PRO.
  - Fly.io has no free tier.
  - Prefer Gradio's `share=True` link or local staging.
- **Queues and gateways:**
  - **RQ is 3.x.**
  - **LiteLLM:** 1.82.7 and 1.82.8 were compromised on PyPI (2026-03). Always pin versions and verify hashes.

**Local models and fine-tuning**
- **llama.cpp:** the tools are `llama-server` (default port 9931), `llama-quantize` and `convert_hf_to_gguf.py`.
- **ollama:** the Python API is `ollama.embed(model=..., input=...)`. The OpenAI-compatible endpoint is `http://localhost:11434/v1`.
- **Phase 10 local model:** `qwen3:4b-instruct-2507-q4_K_M` (2.5 GB). This is the Ollama build of `Qwen/Qwen3-4B-Instruct-2507`, the model D95 fine-tunes. Plain `qwen3:4b` is a **different** model.
- **TRL 1.x:**
  - `SFTConfig(max_length=...)`; `max_seq_length` raises TypeError.
  - `SFTTrainer(processing_class=...)`; `tokenizer=` no longer exists.
- **Unsloth:** the official Colab T4 notebooks (including gpt-oss-20B) pin their own stack.
- **autoawq** has been replaced by `llm-compressor`. **transformers v5** takes `quantization_config=BitsAndBytesConfig(...)`.

---

## Canonical day map (v2)

| Phase | Days | Title |
|---|---|---|
| 0 | 1–2 | Start Here |
| 1 | 3–7 | How LLMs Work |
| 2 | 8–22 | Building with LLM APIs *(capstone R1, D22)* |
| 3 | 23–34 | Retrieval (RAG) *(capstone R2, D34)* |
| 4 | 35–41 | Tools & MCP |
| 5 | 42–47 | Evaluation & Observability |
| 6 | 48–63 | Agents *(capstone R3, D61–62; career checkpoint D63)* |
| 7 | 64–67 | Multi-Agent Systems |
| 8 | 68–76 | Safety & Security *(capstone R4, D76)* |
| 9 | 77–90 | Production *(capstone R5, D89–90)* |
| 10 | 91–96 | Open Models & Fine-Tuning (advanced) |
| 11 | 97–100 | Career Launch |

Capstone releases: **R1 D22 · R2 D34 · R3 D61–62 · R4 D76 · R5 D89–90**. Exact paths and slugs
are in `tools/day_map.json`. Before writing a cross-reference or a What's Next footer,
check the target day against this table.
