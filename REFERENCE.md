# Course Reference — Models, Pricing, and the Day Map

This is the **single source of truth** for fast-moving facts that otherwise drift across 100 lessons: model IDs, rough pricing, and the canonical day/phase map. When a lesson states a model name, a price, or "see Day N," it should agree with this file. **Update this file first**, then any lesson that restates a value.

> ⚠️ **Everything below moves fast.** Model lineups, context windows, and prices change every few months. Treat these as *directional* and verify against the provider's official pricing/model pages before relying on a number in production. "As of" date: **2026-06**.

---

## Anthropic (Claude) models

| Friendly name | Model ID (use this exact string) | Context | Input $/1M | Output $/1M |
|---|---|---|---|---|
| Claude Opus 4.8 | `claude-opus-4-8` | 1M | $5.00 | $25.00 |
| Claude Opus 4.6 | `claude-opus-4-6` | 1M | $5.00 | $25.00 |
| Claude Sonnet 4.6 | `claude-sonnet-4-6` | 1M | $3.00 | $15.00 |
| Claude Haiku 4.5 | `claude-haiku-4-5` | 200K | $1.00 | $5.00 |

Notes:
- Use the **exact, bare** model-ID string — do **not** append date suffixes to the alias (e.g. `claude-sonnet-4-6`, never `claude-sonnet-4-6-20251114`).
- `claude-sonnet-4-5` / `claude-opus-4-5` are older but still valid; prefer the 4.6+ IDs for new content.
- Recent Claude models use **adaptive thinking** (`thinking={"type": "adaptive"}`) rather than a fixed `budget_tokens`, and `output_config={"effort": ...}` for depth. Avoid teaching `budget_tokens` for new code.

## OpenAI models (used in many lessons)

| Friendly name | Model ID | Context | Input $/1M | Output $/1M |
|---|---|---|---|---|
| GPT-4o | `gpt-4o` | 128K | $2.50 | $10.00 |
| GPT-4o mini | `gpt-4o-mini` | 128K | $0.15 | $0.60 |

- The OpenAI SDK is **v1+**: call methods on a client instance (`client = OpenAI(); client.chat.completions.create(...)`), never the deprecated module-level `openai.ChatCompletion.create`.
- Vision is built into `gpt-4o` / `gpt-4o-mini`; the standalone `gpt-4-vision-preview` is deprecated.

## Embedding models

| Model | Dim | Notes |
|---|---|---|
| `text-embedding-3-small` | 1536 | OpenAI default; cheap |
| `text-embedding-3-large` | 3072 | Higher quality |
| Voyage `voyage-3` / `voyage-3-lite` | — | `voyage-2` is legacy |
| Cohere `embed-english-v3.0` | 1024 | SDK v5 uses `ClientV2`, `embedding_types=["float"]`, `response.embeddings.float_` |

---

## Library version notes (common drift points)

- **Pydantic v2**: `@field_validator` + `@classmethod` (not v1 `@validator`); per-instance defaults via `Field(default_factory=...)`.
- **pypdf** (not the unmaintained `PyPDF2`): `from pypdf import PdfReader`.
- **llama.cpp** binaries renamed: `llama-cli` (was `main`), `llama-quantize` (was `quantize`), `convert_hf_to_gguf.py` (was `convert.py`).
- **Gradio 5**: `gr.ChatInterface(..., type="messages")` passes OpenAI-style `{role, content}` dicts.
- **RAGAS 0.2+**: `EvaluationDataset.from_list([...])` with fields `user_input` / `response` / `retrieved_contexts` / `reference`.
- **FastAPI**: prefer the `lifespan` context manager over the deprecated `@app.on_event("startup")`.
- **ollama** Python client: `ollama.embed(model=..., input=...)` → `response["embeddings"][0]`.

---

## Canonical Day Map

| Phase | Days | Title |
|---|---|---|
| 0 | 1 | Getting Started |
| 1 | 2–18 | LLM Foundations *(capstone: Data Extraction Pipeline, Day 18)* |
| 2 | 19–34 | RAG & Tool Calling *(capstone: RAG Chatbot, Day 34)* |
| 3 | 35–49 | Single Agent Architectures *(capstone: Research Agent, Day 48; Career Checkpoint, Day 49)* |
| 4 | 50–55 | Multi-Agent Systems |
| 5 | 56–73 | Evaluation & Security *(capstone: Multi-Agent Content Pipeline, Day 73)* |
| 6 | 74–82 | Fine-tuning & Optimization |
| 7 | 83–97 | Production Deployment *(capstone: Deploy to Production, Day 97)* |
| 8 | 98–100 | Career Launch |

The five portfolio capstones: **Day 18, Day 34, Day 48, Day 73, Day 97**.

When writing a cross-reference or "What's Next" footer, check the target day number against this table.
