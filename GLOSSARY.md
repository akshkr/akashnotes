# Glossary

Plain-English definitions of the terms used across the course, each with the
software-engineering analogy this course leans on. Skim it any time a term feels
fuzzy.

| Term | What it means | SWE analogy |
|---|---|---|
| **Token** | The unit an LLM reads/bills in — a sub-word chunk, not a whole word. | A byte in an encoding: one char ≠ one byte. |
| **Context window** | Max tokens a model can consider at once (input + output). | A function's max argument size / a buffer limit. |
| **Temperature** | Randomness dial for sampling the next token (0 = deterministic-ish). | A seed/jitter knob on output variability. |
| **Embedding** | A text → vector mapping that captures meaning. | A hash that preserves similarity instead of being random. |
| **Vector database** | Stores embeddings and finds nearest neighbors. | A DB where lookups use similarity instead of `=`. |
| **Cosine similarity** | Closeness of two vectors by angle. | A normalized "how alike" score in `[-1, 1]`. |
| **Chunking** | Splitting documents into retrievable pieces. | Pagination/sharding, but for retrieval quality. |
| **RAG** | Retrieval-Augmented Generation: fetch relevant text, then answer. | A read-through cache / data-access layer for the LLM. |
| **Reranking** | A second, slower pass that re-scores retrieved candidates. | A precise sort after a cheap approximate filter. |
| **Tool / function calling** | The model emitting a structured request for your code to run. | An RPC the model issues; your app dispatches it. |
| **Tool-use loop** | Call model → run tool → feed result back → repeat. | An event loop / message-bus dispatch cycle. |
| **Structured output** | Forcing responses into a schema (JSON/Pydantic). | Response DTOs with validation. |
| **Agent** | An LLM that plans and acts via tools in a loop. | A worker that orchestrates calls toward a goal. |
| **ReAct** | Reason → Act → Observe agent pattern. | A control loop with logging between steps. |
| **State machine (LangGraph)** | Nodes + edges defining agent flow/state. | A workflow engine / explicit FSM. |
| **Checkpoint / persistence** | Saving agent state to resume or replay. | DB-backed sessions; event sourcing. |
| **Multi-agent** | Several specialized agents collaborating. | Microservices with routing/handoffs. |
| **Handoff / routing** | Triage agent passing work to a specialist. | A request router / load balancer by capability. |
| **Guardrail** | Validation before/after a model call. | Input-validation middleware / response interceptor. |
| **LLM-as-judge** | Using an LLM to score outputs. | An automated reviewer in CI. |
| **Eval / RAGAS** | Measuring quality (faithfulness, relevancy, recall…). | A test suite for non-deterministic output. |
| **Prompt injection** | Malicious input that hijacks the model's instructions. | Untrusted-input attacks (think XSS/SQLi for prompts). |
| **Fine-tuning (LoRA/QLoRA)** | Adapting a model's weights to your data. | Specializing a library fork vs. configuring it. |
| **Quantization** | Shrinking model weights to fewer bits. | Lossy compression to trade size/speed for accuracy. |
| **Distillation** | Training a small model to mimic a big one. | Caching an expensive computation in a cheaper form. |
| **Prompt caching** | Reusing a cached prefix to cut cost/latency. | HTTP/CDN caching for the prompt prefix. |
| **MCP** | Model Context Protocol — a standard tool/data interface. | A USB-C / standard plugin API for tools. |
| **Adaptive thinking** | Model decides how much to reason per request. | Auto-tuning compute by problem difficulty. |

See [`REFERENCE.md`](REFERENCE.md) for model IDs, pricing, and the day map.
