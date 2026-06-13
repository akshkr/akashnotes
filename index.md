# 100-Day AI Engineering Challenge — Day-by-Day Index

> **Maintainers:** [`REFERENCE.md`](REFERENCE.md) is the single source of truth for model IDs, pricing, library-version gotchas, and the canonical day map — update it before editing values restated in lessons. See [`CHANGELOG.md`](CHANGELOG.md) for the change history.

---

## Phase 0: Getting Started (Day 1)

**Day 001: The AI Engineering Career Map**
Overview of AI engineering vs ML engineering vs data science roles, skills audit, and the 100-day journey structure. Maps how existing SWE skills transfer to AI engineering.

---

## Phase 1: LLM Foundations (Days 2-18)

**Day 002: Understanding Transformers**
Self-attention mechanisms, multi-head attention, context windows, and how transformers process text in parallel to understand meaning and relationships between words.

**Day 003: Tokenization**
Breaking text into tokens using Byte-Pair Encoding, token economics, cost calculations per token, efficiency tips, and how token counts vary by language (non-English uses 2-4x more tokens).

**Day 004: Temperature and Sampling Part 1**
How LLMs generate text probabilistically, temperature as a creativity dial (0=deterministic, high=creative), and how temperature reshapes probability distributions.

**Day 005: Temperature and Sampling Part 2**
Top-P (nucleus sampling) for filtering unlikely tokens, frequency/presence penalties to reduce repetition, and decision trees for choosing sampling parameters by use case.

**Day 006: Zero-Shot vs Few-Shot Prompting**
Zero-shot (no examples) vs few-shot (provide examples) approaches, side-by-side comparison on messy data extraction, dynamic few-shot selection by similarity, and cost-quality tradeoffs.

**Day 007: Chain of Thought Part 1**
Step-by-step reasoning to improve accuracy on complex problems (math, logic), magic phrases that trigger CoT ("let's think step by step"), and few-shot CoT examples.

**Day 008: Chain of Thought Part 2**
When CoT helps most (math, multi-step reasoning) vs when it doesn't (simple Q&A), self-consistency voting (multiple chains), and structured CoT formats.

**Day 009: System vs User Prompts**
Three message roles (system/user/assistant), system prompt as job description, the message array in conversations, dynamic system prompts, managing long conversations, and prompt injection awareness.

**Day 010: OpenAI and Anthropic SDKs Part 1**
Installation, API key setup, understanding response objects (tokens, costs), async basics with AsyncOpenAI/AsyncAnthropic, and complete examples with all parameters.

**Day 011: OpenAI and Anthropic SDKs Part 2**
Key differences between SDKs (system message placement, response structure), unified wrappers for multi-provider support, async batch patterns, error handling, and model selection.

**Day 012: Streaming Responses Part 1**
Why streaming matters (perceived speed), how to consume streamed chunks, and understanding stream events from both OpenAI and Anthropic.

**Day 013: Streaming Responses Part 2**
Collecting streamed content while displaying, async streaming, parallel async streams, and building streaming chat interfaces with callbacks.

**Day 014: Pydantic Schemas for LLMs**
Using Pydantic to define strict data schemas, type coercion, validation, nested models, field descriptions. Using Pydantic with LLMs: JSON schema generation, prompt injection, response parsing, and complete extraction workflows.

**Day 015: Testing LLM Applications**
Why LLM testing differs (non-deterministic outputs), testing pyramid (unit with mocks, integration, end-to-end), mocking LLM responses, and CI/CD strategy.

**Day 016: Retry Loops and Error Handling**
Basic retry patterns, intelligent feedback (telling the LLM what went wrong), exponential backoff for rate limits, complete production retry systems, async retry patterns, and batch processing.

**Day 017: DSPy — Programmatic Prompt Optimization**
Declarative prompt programming with signatures, compiling prompts with optimizers (BootstrapFewShot, MIPRO), replacing manual prompt engineering with data-driven optimization, and signature-based modules.

**Day 018: Capstone — Data Extraction Pipeline**
Building a real ETL pipeline with LLMs: parsing unstructured text (job postings, reviews, articles), extracting to Pydantic models, retry logic, async batch processing, and cost tracking.

---

## Phase 2: RAG & Tool Calling (Days 19-34)

**Day 019: What Are Embeddings**
Text represented as vectors capturing semantic meaning, similarity metrics, generating embeddings via API, batch processing, and finding similar content programmatically.

**Day 020: Cosine Similarity and Euclidean Distance**
Measuring similarity between embeddings using cosine (angle) and euclidean (distance), when to use each, normalized vectors, and efficient matrix operations with numpy.

**Day 021: Generating Embeddings via API**
OpenAI embedding models (3-small/3-large), batching for efficiency, async generation, alternative providers (Cohere, Voyage, local sentence-transformers), caching, and cost optimization.

**Day 022: pgvector — Embeddings in PostgreSQL**
Setting up pgvector extension, vector columns, distance operators (<->, <=>, <#>), IVFFlat vs HNSW indexing, hybrid search combining vector similarity with tsvector full-text search. ChromaDB mentioned as lightweight alternative.

**Day 023: Indexing, Querying, and Updating**
Batch indexing, deduplication, semantic search, filtered search, hybrid search (keyword + semantic), upsert operations, deletion, and retrieval quality metrics (precision/recall/NDCG).

**Day 024: Document Parsing**
Extracting text from PDFs (PyMuPDF, pdfplumber, PyPDF2), text files, web pages (BeautifulSoup), and building a universal document loader supporting multiple formats.

**Day 025: Text Chunking Strategies**
Why chunking matters for retrieval precision, fixed-size chunking, recursive character splitting at natural boundaries, semantic chunking by topic, and markdown-aware chunking.

**Day 026: Context Injection into Prompts**
Basic RAG flow (search, retrieve, build prompt, answer), structured prompt templates with context, token budget management, multi-query RAG, reranking, and long-context model alternatives.

**Day 027: GraphRAG and Knowledge Graphs**
Why vector RAG fails for multi-hop reasoning, knowledge graph construction with LLM entity extraction, Neo4j and Cypher queries, combining graph traversal with vector similarity, and the GraphRAG pipeline.

**Day 028: Function Calling Basics**
LLMs calling your Python functions for real-time data, tool calling flow with Pydantic-based schema generation, OpenAI and Anthropic implementations, and the complete tool calling loop.

**Day 029: Tool Schemas — Pydantic to LLM-Ready**
Modern SDK auto-schema generation: OpenAI `pydantic_function_tool()`, Anthropic `model_json_schema()`, LangChain `@tool` decorator. Provider format differences and Pydantic constraint mapping.

**Day 030: Tool Execution Handling Part 1**
Complete tool execution loop: detecting tool calls, parsing arguments, executing Python functions via registry, returning results to the LLM, and building a multi-tool agent.

**Day 031: Tool Execution Handling Part 2**
Parallel tool call handling, error categorization (transient vs permanent), timeout handling with ThreadPoolExecutor, smart retry with exponential backoff, and Anthropic tool calling patterns.

**Day 032: Multimodal Agent Inputs — Vision and Audio**
Vision models (GPT-4o, Claude) for analyzing screenshots, charts, and documents. Audio transcription with Whisper. Building multimodal agents that process images + text. Cost considerations for image tokens.

**Day 033: Cost Engineering for LLMs**
Token pricing across providers, counting tokens with tiktoken, model routing by query complexity, exact-match and semantic caching, Anthropic prompt caching, OpenAI Batch API (50% savings), and per-user cost tracking.

**Day 034: Capstone — RAG Chatbot**
Building a complete RAG chatbot: document ingestion, pgvector store, retrieval with reranking, conversation history, tool calling for citations, cost tracking, and evaluation.

---

## Phase 3: Single Agent Architectures (Days 35-49)

**Day 035: The ReAct Loop**
Core ReAct pattern with Thought-Action-Observation cycles, regex-based and structured JSON parsing of agent responses, safe tool execution with iteration limits and token budgets.

**Day 036: Conversation History**
Sliding window history with deques, token-aware history management using tiktoken, structured history classes, tool-aware history handling, and conversation branching.

**Day 037: Max Iterations and Stop Conditions**
Hard stops through iteration counters, multiple stop conditions, graceful shutdown handling, signal-based timeouts, and async cancellation tokens for long-running operations.

**Day 038: LangChain Basics**
LangChain fundamentals: Chat Models, Prompt Templates, Output Parsers, and LCEL (LangChain Expression Language) for composable chains. Includes RAG chain building, streaming, and async.

**Day 039: LlamaIndex and Framework Comparison**
LlamaIndex for data-focused workflows with VectorStoreIndex, document loaders, node parsers, query engines, persistence, custom vector stores, and composable indices with routing.

**Day 040: PydanticAI — Code-First Agents**
Lightweight agent framework from the Pydantic team. Agents as typed Python functions with dependency injection, structured results, tool decoration, and comparison with LangChain/LangGraph and OpenAI Agents SDK.

**Day 041: State Machines with LangGraph**
LangGraph state machines with TypedDict states, conditional edges, tool binding, and visualization. Covers branching and cycling workflow patterns.

**Day 042: Nodes and Edges in LangGraph**
Node creation as Python functions, simple vs conditional edges, routing patterns, and best practices for focused nodes with clear routing logic and type hints.

**Day 043: Compiling and Running Graphs**
Graph compilation, `invoke()` for complete execution, `stream()` for step-by-step monitoring, checkpointing with MemorySaver, and human-in-the-loop interrupts.

**Day 044: Checkpoints and Persistence**
Conversation memory patterns, summary memory for long contexts, LangGraph checkpointing with MemorySaver, state history access, and time-travel debugging to replay from checkpoints.

**Day 045: Time-Travel Debugging**
Recording checkpoints with thread IDs, listing and rewinding to previous states, replaying execution with modified inputs, and an interactive TimeTraceDebugger class.

**Day 046: Database Storage**
Storing conversations in SQLite for development or PostgreSQL for production, with complete persistence patterns for multi-process safe agent conversation history.

**Day 047: Debugging AI Agents**
Structured logging with AgentStep/AgentTrace dataclasses, LangGraph state inspection, automated debugging checklists, and common failure modes (infinite loops, hallucinations, context overflow).

**Day 048: Capstone — Autonomous Research Agent**
Full-stack research agent using LangGraph state machine, web search and document tools, iteration limits, SQLite persistence, streaming execution, and progress reporting.

**Day 049: Career Checkpoint**
Mid-journey career review: skills comparison (Day 1 vs Day 49), mapping projects to job requirements, resume/LinkedIn updates, and strategies for starting job applications.

---

## Phase 4: Multi-Agent Systems (Days 50-55)

**Day 050: Agent Topologies**
Three multi-agent topologies: Hierarchical (supervisor delegates), Networked (peer-to-peer), and Adversarial (generator vs critic). Decision matrix for choosing topology.

**Day 051: Supervisor-Worker Pattern**
Supervisor agents making routing decisions, multi-worker delegation with dependencies, LangGraph hierarchical implementation, parallel worker execution, and specialized patterns.

**Day 052: Adversarial Debate**
Proposer-critic-judge patterns, multi-round debates, red team/blue team format, Socratic questioning, and consensus building through iterative agent refinement.

**Day 053: CrewAI Basics**
CrewAI with role-based agents, task definitions, crew orchestration, sequential vs hierarchical processes, custom tools, and a complete content creation pipeline.

**Day 054: Task Definitions in CrewAI**
Task properties (description, expected_output, agent, context), dependency chaining, multiple context sources, file output, structured Pydantic output, and task templates.

**Day 055: Sequential and Parallel Processes**
Sequential process (one after another), hierarchical process (manager delegates), async task execution, and hybrid approaches mixing sequential and parallel phases.

---

## Phase 5: Evaluation & Security (Days 56-73)

**Day 056: LangSmith and Phoenix**
LangSmith for production tracing with @traceable decorators, Phoenix for open-source tracing with OpenTelemetry, custom spans, metrics collection, and Streamlit dashboards.

**Day 057: Token and Latency Visualization**
Token metrics capture from API responses, MetricsCollector for aggregation, terminal ASCII histograms, Streamlit dashboards with Plotly, cost estimation, and real-time monitoring.

**Day 058: LLM-as-Judge Part 1**
Automated evaluation using LLMs as judges, structured scoring with JSON output, pairwise comparison, and core Ragas metrics (faithfulness, relevancy, precision, recall).

**Day 059: LLM-as-Judge Part 2**
Position bias detection, calibration with anchor examples, Cohen's Kappa for judge reliability, multi-judge consensus with tiebreakers, and cost-efficient evaluation strategies.

**Day 060: RAGAS Evaluation**
Ragas framework with EvaluationDataset, metric deep-dives (faithfulness, relevancy, precision, recall), custom evaluation pipelines, and integration with existing RAG systems.

**Day 061: Trajectory Evaluation**
Capturing agent steps with AgentTrajectory, efficiency metrics, step relevance evaluation, action correctness checking, goal achievement scoring, and trajectory comparison.

**Day 062: Prompt Injection**
Direct and indirect prompt injection attacks, input validation with regex patterns, prompt hardening, input/output separation with delimiters, output filtering, and RAG sandwich defense.

**Day 063: Output Sanitization**
Sanitizing agent outputs using pattern matching, LLM moderation, and multi-layer validation to remove PII, harmful content, and prompt injection echoes before reaching users.

**Day 064: LLM Guardrails**
Guardrails AI framework with pre-built validators for input/output safety, topic restriction, structured output validation, and custom validators. Built-in model safety APIs (OpenAI Moderation, Claude).

**Day 065: Docker Sandboxing Part 1**
Running agent-generated code safely in isolated Docker containers with resource limits (memory, CPU, processes) and read-only filesystems to prevent system compromise.

**Day 066: Docker Sandboxing Part 2**
Securing API keys using environment variables and secrets managers, injecting them safely into containers without exposing credentials in logs or code.

**Day 067: API Key Security**
Never hardcode keys, use environment variables or secrets managers, rotate regularly, mask in logs/monitoring, and implement key scoping with least-privilege access.

**Day 068: Production Hardening**
Production resilience patterns: retry with exponential backoff, circuit breakers, graceful degradation, rate limiting, timeouts, and structured logging for observability.

**Day 069: HITL Patterns Part 1**
Human-in-the-loop approval gates using LangGraph breakpoints or basic approval flows to pause agents before critical actions for human review.

**Day 070: HITL Patterns Part 2**
Multi-stage approval pipelines with escalation levels, LangGraph-based team review, and termination conditions for structured human oversight.

**Day 071: Breakpoints Design**
Strategically placing conditional and risk-based breakpoints in workflows to pause execution only when high-risk operations are detected or manual review is needed.

**Day 072: Injecting Feedback**
Injecting human feedback back into agent state for iterative refinement, supporting iterative loops, structured feedback forms, and real-time guidance during execution.

**Day 073: Capstone — Multi-Agent Pipeline**
Production content creation pipeline with research agent, writer, reviewer, LLM-as-judge evaluation, human approval checkpoint, and prompt injection defenses.

---

## Phase 6: Advanced — Fine-tuning & Optimization (Days 74-82)

**Day 074: Ollama and Local Models**
Ollama installation, model pulling (llama3.2, phi4, qwen2.5-coder), quantization concepts (F16/Q8/Q4), local API usage with OpenAI-compatible interface, and GPU acceleration.

**Day 075: Quantization and Model Swapping**
Quantization formats (GGUF, AWQ, GPTQ) with bit-level tradeoffs (2-8 bits), llama.cpp usage, choosing the right format based on hardware (CPU vs GPU), and quality comparison.

**Day 076: vLLM for Production Inference**
PagedAttention, continuous batching, serving open-weight models at scale, OpenAI-compatible API, benchmarking vs Ollama, tensor parallelism, and when to use vLLM vs Ollama vs cloud APIs.

**Day 077: Synthetic Data Generation**
Using frontier models (GPT-4o, Claude) to generate training datasets, self-instruct pattern, quality filtering, deduplication, formatting for SFT (Alpaca/Chat/ShareGPT), and ethical considerations.

**Day 078: Fine-tuning Fundamentals (LoRA, QLoRA)**
Full fine-tuning vs PEFT, LoRA rank selection and target modules, QLoRA for consumer GPUs (4-bit quantization + LoRA), learning rate scheduling, and when fine-tuning beats prompting.

**Day 079: Hands-on Fine-tuning with Unsloth**
End-to-end fine-tuning of Llama 3.2 8B using Unsloth/SFTTrainer, single GPU workflow, dataset preparation, LoRA configuration, Weights & Biases logging, saving adapters, and GGUF export.

**Day 080: Fine-tuning for Agentic Tasks**
Fine-tuning SLMs for reliable tool calling, JSON schema adherence, domain-specific function calling, training data format for tool-use, and evaluating tool-call accuracy.

**Day 081: Evaluating Fine-tuned Models**
Automated metrics (perplexity, exact match), task-specific benchmarks, A/B testing against frontier models, human evaluation, regression testing, and go/no-go criteria for shipping.

**Day 082: Model Distillation and Routing**
Distilling frontier model behavior into SLMs, building routers (cheap model for easy tasks, expensive for hard), cost savings analysis (5-10x), and production routing patterns.

---

## Phase 7: Production Deployment (Days 83-97)

**Day 083: FastAPI for AI Agents**
FastAPI setup for agents with conversation endpoints, background tasks, SSE streaming responses, WebSocket support, authentication, rate limiting, and health checks.

**Day 084: Async Task Handling**
Async patterns for long-running agent tasks: background tasks, Celery with Redis, in-memory queues, polling, webhook callbacks, progress tracking, and task cleanup.

**Day 085: WebSockets for Streaming**
Real-time streaming via WebSockets with agent thought streaming, connection manager for multiple clients, JavaScript/Python clients, error handling, and authentication.

**Day 086: Streamlit and Gradio UIs**
Chat UIs, RAG dashboards, agent dashboards with metrics, multi-modal interfaces. Comparison: Streamlit for data apps/dashboards, Gradio for ML demos/quick sharing.

**Day 087: Agentic UI / Generative UI**
Streaming React components from agent tool calls (Vercel AI SDK pattern), dynamic widget rendering, beyond markdown streaming, and comparison with Streamlit/Gradio approach.

**Day 088: Displaying Content in UIs**
Markdown rendering, interactive tables with progress columns, expandable reasoning steps, timeline views, code display with syntax highlighting, and streaming content.

**Day 089: Docker Deployment**
Dockerfile configuration, Docker Compose for multi-service setup, rate limit handling with backoff, circuit breaker pattern, and deployment checklist with health/readiness probes.

**Day 090: Rate Limits and Backoffs**
Retry with exponential backoff and jitter, token bucket rate limiting, circuit breaker state machine (closed/open/half-open), tenacity library, and per-user token budget management.

**Day 091: Semantic Caching**
Exact-match caching with Redis, semantic caching using embeddings for fuzzy matching, similarity threshold tuning, cache invalidation, native prompt caching (OpenAI/Anthropic), and cost analysis.

**Day 092: Model Fallback Strategies**
Simple fallback chains, health checking with latency tracking, cost-aware routing by query complexity, circuit breaker per provider, and degraded mode with static responses.

**Day 093: Cloud Deployment**
Deployment to Render, Railway, AWS (App Runner/ECS/Lambda), GCP (Cloud Run/GKE), environment config, structured logging, CI/CD with GitHub Actions, and observability integration.

**Day 094: Prompt Engineering Discipline**
Prompts as versioned files, PromptManager and PromptRegistry for version control, A/B testing with traffic splitting, LLM-as-judge evaluation, failure analysis, and anti-patterns.

**Day 095: Model Context Protocol (MCP)**
MCP as standardized tool integration (USB-C for AI), building MCP servers for database and filesystem access, connecting to Claude Desktop, and architecture shift to standalone tool services.

**Day 096: Claude Agent SDK**
Agent SDK core concepts (Agent, Tool, Runner, Handoff, Guardrail), building agents with decorated functions, multi-agent orchestration with specialist routing, guardrails, and tracing.

**Day 097: Capstone — Deploy to Production**
Deploying the content pipeline with FastAPI backend, Streamlit UI, Docker containerization, rate limiting middleware, cost tracking in SQLite, and cloud deployment to Render.

---

## Phase 8: Career Launch (Days 98-100)

**Day 098: AI Engineering Interview Prep**
System design questions (RAG, multi-agent, eval frameworks), coding patterns (structured output, tool calling), take-home projects, behavioral questions, and SWE-to-AI skill mapping.

**Day 099: Building Your Portfolio**
Structuring 5 capstone projects with READMEs, live demos on HuggingFace Spaces/Railway, Docker Compose reproducibility, technical blog posts, and GitHub/LinkedIn optimization.

**Day 100: Career Launch — What's Next**
Skills summary, portfolio of 5 projects, specialization paths (agents, RAG, evaluation, infrastructure), job search timeline, community engagement, and AI engineering market context.
