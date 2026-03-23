# Observability & Tracing with LangSmith and Phoenix

You've built agents and RAG systems. But how do you know they're working well? How do you debug when things go wrong? Welcome to **observability** - seeing exactly what your AI systems are doing.

---

## Why Observability Matters

```mermaid
flowchart TB
    subgraph "Without Observability"
        A["User Query"] --> B["Black Box"]
        B --> C["Output"]
        C --> D["Was it good? 🤷"]
    end

    subgraph "With Observability"
        E["User Query"] --> F["Traced Pipeline"]
        F --> G["Every step visible"]
        G --> H["Metrics & Insights"]
        H --> I["Confident improvements"]
    end

    style D fill:#ff6b6b
    style I fill:#90EE90
```

What you can see:
- Every LLM call (prompts, responses, tokens, latency)
- Tool executions
- Retrieval operations
- Error traces
- Cost breakdowns

---

## LangSmith: Production Tracing

### Setup

```bash
pip install langsmith langchain langchain-openai
```

```python
import os

# Set environment variables
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "your-langsmith-api-key"
os.environ["LANGCHAIN_PROJECT"] = "my-ai-project"
```

### Basic Tracing

```python
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

# LangSmith automatically traces LangChain operations!
llm = ChatOpenAI(model="gpt-3.5-turbo")

response = llm.invoke([HumanMessage(content="What is AI?")])
print(response.content)

# Check LangSmith dashboard to see the trace!
```

### Tracing Custom Functions

```python
from langsmith import traceable

@traceable(name="my_rag_pipeline")
def rag_query(question: str) -> str:
    """A traced RAG pipeline."""

    # Step 1: Embed
    embedding = embed_question(question)

    # Step 2: Retrieve
    docs = retrieve_documents(embedding)

    # Step 3: Generate
    answer = generate_answer(question, docs)

    return answer

@traceable(name="embed_question")
def embed_question(question: str) -> list:
    """Embed the question."""
    # Your embedding logic
    return [0.1, 0.2, 0.3]

@traceable(name="retrieve_documents")
def retrieve_documents(embedding: list) -> list:
    """Retrieve relevant documents."""
    # Your retrieval logic
    return ["doc1", "doc2"]

@traceable(name="generate_answer")
def generate_answer(question: str, docs: list) -> str:
    """Generate the final answer."""
    llm = ChatOpenAI(model="gpt-3.5-turbo")
    context = "\n".join(docs)
    response = llm.invoke([
        HumanMessage(content=f"Context: {context}\n\nQuestion: {question}")
    ])
    return response.content

# When you call this, all steps are traced!
answer = rag_query("What is machine learning?")
```

### Adding Metadata

```python
from langsmith import traceable

@traceable(
    name="production_query",
    tags=["production", "v2"],
    metadata={"version": "2.0", "team": "ml"}
)
def production_query(user_id: str, query: str) -> str:
    """Query with rich metadata for filtering."""
    # ...
    pass

# Or add run-time metadata
from langsmith.run_helpers import get_current_run_tree

@traceable
def process_query(query: str):
    run = get_current_run_tree()
    if run:
        run.metadata["query_length"] = len(query)
        run.tags.append("short" if len(query) < 50 else "long")
    # ...
```

---

## Phoenix: Open-Source Tracing

Phoenix is a free, open-source alternative:

### Setup

```bash
pip install arize-phoenix opentelemetry-sdk opentelemetry-exporter-otlp
```

```python
import phoenix as px

# Launch Phoenix (opens web UI)
session = px.launch_app()
print(f"Phoenix UI: {session.url}")
```

### Instrument OpenAI

```python
from phoenix.otel import register
from openinference.instrumentation.openai import OpenAIInstrumentor

# Setup tracing
tracer_provider = register(project_name="my-project")
OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)

# Now all OpenAI calls are traced!
from openai import OpenAI
client = OpenAI()

response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Hello!"}]
)
# Check Phoenix UI to see traces
```

### Custom Spans

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

def my_pipeline(query: str):
    with tracer.start_as_current_span("my_pipeline") as span:
        span.set_attribute("query", query)

        with tracer.start_as_current_span("step_1"):
            result1 = do_step_1(query)

        with tracer.start_as_current_span("step_2"):
            result2 = do_step_2(result1)

        span.set_attribute("success", True)
        return result2
```

---

## Key Metrics to Track

```mermaid
mindmap
  root((Metrics))
    Latency
      Time to first token
      Total response time
      Per-step latency
    Cost
      Tokens per request
      Cost per query
      Daily/monthly totals
    Quality
      User feedback
      Error rates
      Retrieval relevance
    Usage
      Requests per minute
      Unique users
      Popular queries
```

### Building a Metrics Dashboard

```python
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import statistics

@dataclass
class QueryMetrics:
    query_id: str
    timestamp: datetime
    latency_ms: float
    input_tokens: int
    output_tokens: int
    total_cost: float
    success: bool
    error: str = None

class MetricsCollector:
    """Collect and analyze metrics."""

    def __init__(self):
        self.metrics: list[QueryMetrics] = []

    def record(self, metrics: QueryMetrics):
        """Record a query's metrics."""
        self.metrics.append(metrics)

    def summary(self, last_n: int = None) -> dict:
        """Get summary statistics."""
        data = self.metrics[-last_n:] if last_n else self.metrics

        if not data:
            return {"error": "No data"}

        latencies = [m.latency_ms for m in data]
        costs = [m.total_cost for m in data]
        successes = [m.success for m in data]

        return {
            "total_queries": len(data),
            "success_rate": sum(successes) / len(successes),
            "latency": {
                "mean": statistics.mean(latencies),
                "median": statistics.median(latencies),
                "p95": sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 20 else max(latencies),
            },
            "cost": {
                "total": sum(costs),
                "average": statistics.mean(costs),
            },
            "tokens": {
                "input_total": sum(m.input_tokens for m in data),
                "output_total": sum(m.output_tokens for m in data),
            }
        }

# Usage
collector = MetricsCollector()

# After each query
collector.record(QueryMetrics(
    query_id="q123",
    timestamp=datetime.now(),
    latency_ms=1500,
    input_tokens=150,
    output_tokens=200,
    total_cost=0.001,
    success=True
))

print(collector.summary())
```

---

## Debugging with Traces

### Common Issues to Look For

```mermaid
flowchart TB
    A["Slow Response"] --> B{"Where's the\nbottleneck?"}
    B -->|"LLM"| C["Check model,\nreduce tokens"]
    B -->|"Retrieval"| D["Optimize vector DB,\ncheck indexing"]
    B -->|"Tool calls"| E["Cache results,\nparallelize"]

    F["Bad Quality"] --> G{"Which step\nfailed?"}
    G -->|"Retrieval"| H["Check chunk size,\nembedding quality"]
    G -->|"Generation"| I["Improve prompt,\nadd examples"]
    G -->|"Context"| J["Add more context,\nbetter ranking"]
```

### Trace Analysis Code

```python
def analyze_trace(trace: dict) -> dict:
    """Analyze a trace for issues."""
    issues = []

    # Check latency
    total_latency = trace.get("latency_ms", 0)
    if total_latency > 5000:
        issues.append({
            "type": "high_latency",
            "severity": "warning",
            "details": f"Total latency {total_latency}ms exceeds 5s threshold"
        })

    # Check token usage
    input_tokens = trace.get("input_tokens", 0)
    if input_tokens > 3000:
        issues.append({
            "type": "high_token_usage",
            "severity": "info",
            "details": f"Input tokens ({input_tokens}) are high, consider summarization"
        })

    # Check for errors
    if trace.get("error"):
        issues.append({
            "type": "error",
            "severity": "critical",
            "details": trace["error"]
        })

    # Check retrieval relevance
    retrieval_scores = trace.get("retrieval_scores", [])
    if retrieval_scores and max(retrieval_scores) < 0.7:
        issues.append({
            "type": "low_relevance",
            "severity": "warning",
            "details": f"Best retrieval score ({max(retrieval_scores):.2f}) is low"
        })

    return {
        "trace_id": trace.get("id"),
        "issues": issues,
        "issue_count": len(issues),
        "has_critical": any(i["severity"] == "critical" for i in issues)
    }
```

---

## Summary

```mermaid
mindmap
  root((Observability))
    Tools
      LangSmith (hosted)
      Phoenix (open-source)
      Custom logging
    Metrics
      Latency
      Tokens/Cost
      Success rate
    Debugging
      Trace analysis
      Bottleneck detection
      Quality issues
```

---

## Quick Reference

```python
# LangSmith
import os
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "key"

from langsmith import traceable
@traceable
def my_function(): pass

# Phoenix
import phoenix as px
px.launch_app()

from phoenix.otel import register
register(project_name="my-project")
```

---

## What's Next?

Now that you can see what's happening, let's learn how to **measure quality** with automated evaluation!
