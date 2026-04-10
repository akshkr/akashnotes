# Streaming Responses: Real-Time LLM Output

Have you noticed how ChatGPT types out responses word by word instead of making you wait for the complete answer? That's **streaming**! In this guide, you'll learn to implement the same experience in your applications.

> **Coming from Software Engineering?** LLM streaming is Server-Sent Events (SSE) — the same protocol used in real-time dashboards, stock tickers, and notification systems. If you've consumed webhooks or WebSocket streams, you already know how to handle streaming data. The only difference is you're getting text tokens instead of JSON events.

---

## Why Streaming Matters

```mermaid
flowchart LR
    subgraph "Without Streaming"
        A["Request"] --> B["Wait 5-10s..."]
        B --> C["Complete response\nappears at once"]
    end

    subgraph "With Streaming"
        D["Request"] --> E["Words appear\nimmediately"]
        E --> F["Continues\nflowing..."]
        F --> G["Done!"]
    end

    style B fill:#ff6b6b
    style E fill:#90EE90
```

### Benefits of Streaming

| Aspect | Without Streaming | With Streaming |
|--------|------------------|----------------|
| Time to first token | 5-10 seconds | ~0.5 seconds |
| User experience | Feels slow | Feels responsive |
| UI feedback | Loading spinner | Live text |
| Can cancel early? | No | Yes! |

---

## OpenAI Streaming Basics

```python
# script_id: day_012_streaming_responses_part1/basic_stream_chat
from openai import OpenAI

client = OpenAI()

def stream_chat(prompt: str):
    """Stream a chat response word by word."""
    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        stream=True  # Enable streaming!
    )

    print("Response: ", end="", flush=True)

    for chunk in stream:
        # Each chunk contains a small piece of the response
        if chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            print(content, end="", flush=True)

    print()  # New line at the end

# Try it!
stream_chat("Write a short poem about coding")
```

### Understanding Stream Chunks

```python
# script_id: day_012_streaming_responses_part1/inspect_stream_chunks
from openai import OpenAI

client = OpenAI()

def inspect_stream(prompt: str):
    """Inspect what's in each stream chunk."""
    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        stream=True
    )

    for i, chunk in enumerate(stream):
        print(f"\n--- Chunk {i} ---")
        print(f"ID: {chunk.id}")
        print(f"Model: {chunk.model}")
        print(f"Delta content: {repr(chunk.choices[0].delta.content)}")
        print(f"Finish reason: {chunk.choices[0].finish_reason}")

        if i >= 5:  # Just show first few chunks
            print("\n... (more chunks follow)")
            break

inspect_stream("Say hello")
```

**Output:**
```
--- Chunk 0 ---
ID: chatcmpl-abc123
Model: gpt-4o-mini
Delta content: ''
Finish reason: None

--- Chunk 1 ---
ID: chatcmpl-abc123
Model: gpt-4o-mini
Delta content: 'Hello'
Finish reason: None

--- Chunk 2 ---
ID: chatcmpl-abc123
Model: gpt-4o-mini
Delta content: '!'
Finish reason: None

--- Chunk 3 ---
ID: chatcmpl-abc123
Model: gpt-4o-mini
Delta content: ' How'
Finish reason: None
...
```

```mermaid
flowchart TB
    subgraph "Stream Chunks"
        C1["Chunk 1: 'Hello'"]
        C2["Chunk 2: ' world'"]
        C3["Chunk 3: '!'"]
        C4["Chunk 4: ' How'"]
        C5["Chunk N: finish_reason='stop'"]
    end

    C1 --> C2 --> C3 --> C4 --> C5

    style C5 fill:#90EE90
```

---

## Anthropic Streaming

```python
# script_id: day_012_streaming_responses_part1/anthropic_basic_stream
from anthropic import Anthropic

client = Anthropic()

def stream_claude(prompt: str):
    """Stream a Claude response."""
    with client.messages.stream(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        print("Response: ", end="", flush=True)
        for text in stream.text_stream:
            print(text, end="", flush=True)
        print()

stream_claude("Write a haiku about Python")
```

### Anthropic Stream Events

```python
# script_id: day_012_streaming_responses_part1/anthropic_stream_events
from anthropic import Anthropic

client = Anthropic()

def detailed_claude_stream(prompt: str):
    """Show detailed stream events from Claude."""
    with client.messages.stream(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        for event in stream:
            print(f"Event type: {type(event).__name__}")

            # Different event types have different attributes
            if hasattr(event, 'type'):
                print(f"  Type: {event.type}")
            if hasattr(event, 'delta'):
                print(f"  Delta: {event.delta}")

detailed_claude_stream("Hi")
```

---

## Collecting Streamed Content

Sometimes you want to both stream to the user AND collect the full response:

```python
# script_id: day_012_streaming_responses_part1/stream_and_collect
from openai import OpenAI

client = OpenAI()

def stream_and_collect(prompt: str) -> str:
    """Stream response while collecting full text."""
    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        stream=True
    )

    collected_content = []

    print("Streaming: ", end="", flush=True)
    for chunk in stream:
        content = chunk.choices[0].delta.content
        if content:
            print(content, end="", flush=True)
            collected_content.append(content)
    print()

    full_response = "".join(collected_content)
    return full_response

# Usage
response = stream_and_collect("List 3 programming languages")
print(f"\n--- Full collected response ({len(response)} chars) ---")
print(response)
```

---

## Async Streaming

Combine async with streaming for maximum responsiveness:

```python
# script_id: day_012_streaming_responses_part1/async_stream
import asyncio
from openai import AsyncOpenAI

client = AsyncOpenAI()

async def async_stream(prompt: str) -> str:
    """Async streaming with collection."""
    stream = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        stream=True
    )

    collected = []
    async for chunk in stream:
        content = chunk.choices[0].delta.content
        if content:
            print(content, end="", flush=True)
            collected.append(content)

    print()
    return "".join(collected)

async def main():
    result = await async_stream("Explain async streaming in one paragraph")
    print(f"\nCollected {len(result)} characters")

asyncio.run(main())
```

### Parallel Async Streams

```python
# script_id: day_012_streaming_responses_part1/parallel_async_streams
import asyncio
from openai import AsyncOpenAI

client = AsyncOpenAI()

async def stream_one(prompt: str, label: str) -> str:
    """Stream a single prompt with a label."""
    stream = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
        max_tokens=100
    )

    collected = []
    async for chunk in stream:
        content = chunk.choices[0].delta.content
        if content:
            collected.append(content)
            # Print with label for clarity
            print(f"[{label}] {content}", end="", flush=True)

    print(f"\n[{label}] --- Done ---")
    return "".join(collected)

async def parallel_streams():
    """Run multiple streams in parallel."""
    prompts = [
        ("What is Python?", "PY"),
        ("What is JavaScript?", "JS"),
        ("What is Rust?", "RS")
    ]

    tasks = [stream_one(prompt, label) for prompt, label in prompts]
    results = await asyncio.gather(*tasks)

    print("\n=== All streams complete ===")
    for (prompt, label), result in zip(prompts, results):
        print(f"{label}: {len(result)} chars")

asyncio.run(parallel_streams())
```

---
