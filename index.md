### Month 1: The LLM Interface & Python Integration

Goal: Understand how to communicate programmatically with LLMs and force them to return predictable, usable data.

* **Week 1: Mental Models for LLMs**
* High-level Transformer intuition (no heavy math, just concepts: self-attention, context windows).
* Tokenization (how LLMs see text, calculating token costs).
* Temperature, Top-P, and frequency penalties.


* **Week 2: Advanced Prompting Techniques**
* Zero-shot vs. Few-shot prompting.
* Chain of Thought (CoT) and Step-by-Step reasoning.
* System prompts vs. User prompts.


* **Week 3: Python API Mastery**
* Using the `openai` and `anthropic` Python SDKs.
* Handling asynchronous LLM calls with `asyncio` for faster processing.
* Streaming responses (handling server-sent events in Python).


* **Week 4: Structured Output & Data Parsing**
* Using **Pydantic** to define strict data schemas.
* Forcing LLMs to return valid JSON.
* Building retry loops for when the LLM hallucinates the data structure.



### Month 2: External Knowledge & Tool Calling

Goal: Give your LLM the ability to read your proprietary data and trigger your Python functions.

* **Week 1: Embeddings & Vector Math Intuition**
* What are embeddings? (Translating text to arrays of numbers).
* Cosine similarity and Euclidean distance in Python (using `numpy`).
* Generating embeddings via API.


* **Week 2: Vector Databases**
* Setting up local vector stores in Python (ChromaDB or FAISS).
* Indexing, querying, and updating vector databases.


* **Week 3: Retrieval-Augmented Generation (RAG)**
* Document parsing (PDFs, text files, web scraping).
* Text chunking strategies (recursive character splitting, semantic splitting).
* Injecting retrieved context into the prompt dynamically.


* **Week 4: Native Tool Calling (Function Calling)**
* Writing clean, single-purpose Python functions for the LLM.
* Generating JSON schemas for your Python functions.
* Parsing the LLM's tool-call request, executing the Python function, and returning the result back to the LLM.



### Month 3: Single-Agent Architectures & State Machines

Goal: Move from linear scripts to cyclical agents that can plan, execute, and correct their own mistakes.

* **Week 1: The "From Scratch" Agent**
* Building the ReAct (Reason + Act) loop using a pure Python `while` loop.
* Managing conversational history (lists of dictionaries) manually.
* Implementing a hard stop (max iterations) to prevent infinite loops.


* **Week 2: Introduction to LangChain & LlamaIndex**
* LangChain Expression Language (LCEL) syntax.
* Using LlamaIndex for advanced data ingestion and query engines.
* Understanding the abstraction trade-offs (when to use a framework vs. vanilla Python).


* **Week 3: Stateful Agents with LangGraph**
* The concept of treating agents as state machines.
* Defining Nodes (Python functions) and Edges (conditional routing).
* Compiling a basic graph agent.


* **Week 4: Advanced Memory & Persistence**
* Adding checkpoints to LangGraph to save agent state.
* Time-travel debugging (rewinding an agent to a previous state).
* Storing conversation threads in SQLite or PostgreSQL.



### Month 4: Multi-Agent Systems

Goal: Design teams of specialized agents that collaborate to solve complex problems.

* **Week 1: Multi-Agent Topologies**
* Supervisor/Worker (Hierarchical) routing.
* Networked (peer-to-peer) collaboration.
* Adversarial debate (agents critiquing each other's work).


* **Week 2: Task-Oriented Frameworks (CrewAI)**
* Defining Agents (role, backstory, goal).
* Defining Tasks (expected output, assigned agent).
* Running sequential and parallel processes in CrewAI.


* **Week 3: Code-Execution Frameworks (Microsoft AutoGen)**
* Conversational programming with AutoGen.
* Creating user proxy agents and assistant agents.
* Setting up local code execution environments.


* **Week 4: Human-in-the-Loop (HITL)**
* Designing breakpoints in your code.
* Pausing graph execution to wait for user input (e.g., "Do you approve this API call?").
* Injecting human feedback back into the agent's state.



### Month 5: Evaluation, Observability, and Security

Goal: Ensure your AI systems are reliable, measurable, and safe for real-world use.

* **Week 1: Observability & Tracing**
* Integrating **LangSmith** or **Phoenix** into your Python code.
* Visualizing the exact prompt, token count, and latency of every agent step.


* **Week 2: Automated Evaluation**
* Using the "LLM-as-a-judge" pattern.
* Evaluating RAG systems (context precision, context recall) using frameworks like **Ragas**.
* Evaluating agent trajectories (did it take the most efficient path?).


* **Week 3: Security & Guardrails**
* Understanding and mitigating Prompt Injection attacks.
* Implementing output sanitization.
* Using libraries like `NeMo-Guardrails` or `guardrails-ai`.


* **Week 4: Safe Sandboxing**
* Using Docker to containerize the environment where your agents write or execute code.
* Managing API key security within agent workflows.



### Month 6: Open Source, Local Models & Production

Goal: Take your agents out of the terminal and into a scalable, production-ready environment.

* **Week 1: Local & Open-Source Models**
* Running models locally using **Ollama** or **vLLM**.
* Understanding quantization (GGUF, AWQ) to run large models on consumer hardware.
* Swapping out OpenAI for local Llama 3 or Mistral in your Python code.


* **Week 2: Wrapping Agents in APIs**
* Using **FastAPI** to create endpoints for your agents.
* Handling long-running agent tasks asynchronously in a web server.
* Implementing WebSockets for real-time streaming of agent thoughts.


* **Week 3: Building Agent UIs**
* Creating rapid prototypes using **Streamlit** or **Gradio**.
* Displaying markdown, tables, and agent reasoning steps in the UI.


* **Week 4: Cloud Deployment & Reliability**
* Dockerizing your Python agent application.
* Handling rate limits, exponential backoffs, and circuit breakers in production.
* Deploying to AWS, GCP, or platforms like Render/Railway.