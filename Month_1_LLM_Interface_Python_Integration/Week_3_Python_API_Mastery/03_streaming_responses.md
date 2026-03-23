# Streaming Responses: Real-Time LLM Output

Have you noticed how ChatGPT types out responses word by word instead of making you wait for the complete answer? That's **streaming**! In this guide, you'll learn to implement the same experience in your applications.

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
from openai import OpenAI

client = OpenAI()

def stream_chat(prompt: str):
    """Stream a chat response word by word."""
    stream = client.chat.completions.create(
        model="gpt-3.5-turbo",
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
from openai import OpenAI

client = OpenAI()

def inspect_stream(prompt: str):
    """Inspect what's in each stream chunk."""
    stream = client.chat.completions.create(
        model="gpt-3.5-turbo",
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
Model: gpt-3.5-turbo
Delta content: ''
Finish reason: None

--- Chunk 1 ---
ID: chatcmpl-abc123
Model: gpt-3.5-turbo
Delta content: 'Hello'
Finish reason: None

--- Chunk 2 ---
ID: chatcmpl-abc123
Model: gpt-3.5-turbo
Delta content: '!'
Finish reason: None

--- Chunk 3 ---
ID: chatcmpl-abc123
Model: gpt-3.5-turbo
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
from anthropic import Anthropic

client = Anthropic()

def stream_claude(prompt: str):
    """Stream a Claude response."""
    with client.messages.stream(
        model="claude-sonnet-4-20250514",
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
from anthropic import Anthropic

client = Anthropic()

def detailed_claude_stream(prompt: str):
    """Show detailed stream events from Claude."""
    with client.messages.stream(
        model="claude-sonnet-4-20250514",
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
from openai import OpenAI

client = OpenAI()

def stream_and_collect(prompt: str) -> str:
    """Stream response while collecting full text."""
    stream = client.chat.completions.create(
        model="gpt-3.5-turbo",
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
import asyncio
from openai import AsyncOpenAI

client = AsyncOpenAI()

async def async_stream(prompt: str) -> str:
    """Async streaming with collection."""
    stream = await client.chat.completions.create(
        model="gpt-3.5-turbo",
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
import asyncio
from openai import AsyncOpenAI

client = AsyncOpenAI()

async def stream_one(prompt: str, label: str) -> str:
    """Stream a single prompt with a label."""
    stream = await client.chat.completions.create(
        model="gpt-3.5-turbo",
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

## Building a Streaming Chat Interface

Here's a complete streaming chat implementation:

```python
from openai import OpenAI

client = OpenAI()

class StreamingChat:
    """A streaming chat interface."""

    def __init__(self, system_prompt: str = "You are a helpful assistant."):
        self.system_prompt = system_prompt
        self.messages = []

    def chat(self, user_input: str) -> str:
        """Send a message and stream the response."""
        # Add user message
        self.messages.append({"role": "user", "content": user_input})

        # Build full message list
        full_messages = [
            {"role": "system", "content": self.system_prompt}
        ] + self.messages

        # Stream response
        stream = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=full_messages,
            stream=True
        )

        print("Assistant: ", end="", flush=True)
        collected = []

        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                print(content, end="", flush=True)
                collected.append(content)

        print()  # New line

        # Add assistant response to history
        full_response = "".join(collected)
        self.messages.append({"role": "assistant", "content": full_response})

        return full_response

    def clear_history(self):
        """Clear conversation history."""
        self.messages = []

# Interactive usage
def run_chat():
    chat = StreamingChat(
        system_prompt="You are a friendly coding tutor. Keep responses concise."
    )

    print("Streaming Chat (type 'quit' to exit, 'clear' to reset)")
    print("-" * 50)

    while True:
        user_input = input("\nYou: ").strip()

        if user_input.lower() == 'quit':
            break
        elif user_input.lower() == 'clear':
            chat.clear_history()
            print("History cleared!")
            continue
        elif not user_input:
            continue

        chat.chat(user_input)

if __name__ == "__main__":
    run_chat()
```

---

## Streaming with Callbacks

For frameworks and UIs, use callbacks:

```python
from openai import OpenAI
from typing import Callable

client = OpenAI()

def stream_with_callbacks(
    prompt: str,
    on_token: Callable[[str], None],
    on_complete: Callable[[str], None],
    on_error: Callable[[Exception], None] = None
):
    """
    Stream with callback functions for integration with UIs.

    Args:
        prompt: The user's prompt
        on_token: Called for each new token
        on_complete: Called when streaming finishes
        on_error: Called if an error occurs
    """
    try:
        stream = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            stream=True
        )

        collected = []
        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                collected.append(content)
                on_token(content)

        full_response = "".join(collected)
        on_complete(full_response)

    except Exception as e:
        if on_error:
            on_error(e)
        else:
            raise

# Example usage with simple callbacks
def my_token_handler(token: str):
    print(token, end="", flush=True)

def my_complete_handler(full_text: str):
    print(f"\n\n[Complete! {len(full_text)} chars]")

def my_error_handler(error: Exception):
    print(f"\n[Error: {error}]")

stream_with_callbacks(
    "Write a 2-line poem",
    on_token=my_token_handler,
    on_complete=my_complete_handler,
    on_error=my_error_handler
)
```

---

## Server-Sent Events (SSE) for Web Apps

When building web APIs, use SSE to stream to browsers:

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from openai import OpenAI
import json

app = FastAPI()
client = OpenAI()

async def generate_stream(prompt: str):
    """Generator for SSE streaming."""
    stream = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        stream=True
    )

    for chunk in stream:
        content = chunk.choices[0].delta.content
        if content:
            # SSE format: data: {json}\n\n
            data = json.dumps({"content": content})
            yield f"data: {data}\n\n"

    # Send completion signal
    yield f"data: {json.dumps({'done': True})}\n\n"

@app.get("/stream")
async def stream_endpoint(prompt: str):
    """SSE endpoint for streaming responses."""
    return StreamingResponse(
        generate_stream(prompt),
        media_type="text/event-stream"
    )

# Frontend JavaScript to consume this:
"""
const eventSource = new EventSource('/stream?prompt=Hello');
eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.done) {
        eventSource.close();
    } else {
        document.getElementById('output').textContent += data.content;
    }
};
"""
```

```mermaid
sequenceDiagram
    participant Browser
    participant Server
    participant LLM

    Browser->>Server: GET /stream?prompt=Hello
    Server->>LLM: Create stream
    LLM-->>Server: Chunk 1
    Server-->>Browser: data: {"content": "Hi"}
    LLM-->>Server: Chunk 2
    Server-->>Browser: data: {"content": " there"}
    LLM-->>Server: Chunk 3
    Server-->>Browser: data: {"content": "!"}
    LLM-->>Server: Done
    Server-->>Browser: data: {"done": true}
```

---

## Handling Stream Interruption

Allow users to cancel streams:

```python
import asyncio
from openai import AsyncOpenAI

client = AsyncOpenAI()

class CancellableStream:
    """A stream that can be cancelled."""

    def __init__(self):
        self.cancelled = False

    def cancel(self):
        """Cancel the stream."""
        self.cancelled = True

    async def stream(self, prompt: str) -> str:
        """Stream with cancellation support."""
        stream = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            stream=True
        )

        collected = []
        async for chunk in stream:
            if self.cancelled:
                print("\n[Stream cancelled]")
                break

            content = chunk.choices[0].delta.content
            if content:
                print(content, end="", flush=True)
                collected.append(content)

        return "".join(collected)

async def demo_cancellation():
    """Demo cancelling a stream."""
    streamer = CancellableStream()

    # Start streaming in background
    stream_task = asyncio.create_task(
        streamer.stream("Write a very long story about a dragon")
    )

    # Cancel after 2 seconds
    await asyncio.sleep(2)
    streamer.cancel()

    result = await stream_task
    print(f"\n\nGot {len(result)} chars before cancellation")

asyncio.run(demo_cancellation())
```

---

## Measuring Streaming Performance

```python
import time
from openai import OpenAI

client = OpenAI()

def measure_streaming(prompt: str) -> dict:
    """Measure streaming performance metrics."""
    start_time = time.time()
    first_token_time = None
    token_count = 0
    char_count = 0

    stream = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        stream=True
    )

    for chunk in stream:
        content = chunk.choices[0].delta.content
        if content:
            if first_token_time is None:
                first_token_time = time.time()
            token_count += 1
            char_count += len(content)

    end_time = time.time()

    return {
        "total_time": end_time - start_time,
        "time_to_first_token": first_token_time - start_time if first_token_time else None,
        "streaming_time": end_time - first_token_time if first_token_time else None,
        "chunk_count": token_count,
        "char_count": char_count,
        "chars_per_second": char_count / (end_time - first_token_time) if first_token_time else 0
    }

# Test it
metrics = measure_streaming("Write a paragraph about streaming APIs")
print("\n--- Streaming Metrics ---")
for key, value in metrics.items():
    if isinstance(value, float):
        print(f"{key}: {value:.3f}")
    else:
        print(f"{key}: {value}")
```

---

## Summary

```mermaid
mindmap
  root((Streaming))
    Why
      Faster perceived response
      Better UX
      Cancellation support
    OpenAI
      stream=True
      chunk.choices[0].delta.content
    Anthropic
      messages.stream()
      stream.text_stream
    Patterns
      Collect while streaming
      Callbacks for UIs
      SSE for web apps
      Cancellation handling
```

---

## Quick Reference

```python
# OpenAI Streaming
from openai import OpenAI
client = OpenAI()

stream = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Hi"}],
    stream=True
)
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")

# Anthropic Streaming
from anthropic import Anthropic
client = Anthropic()

with client.messages.stream(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hi"}]
) as stream:
    for text in stream.text_stream:
        print(text, end="")
```

---

## Exercises

1. **Typing Effect**: Implement a "typewriter" effect that adds a small delay between chunks for a more natural feel

2. **Progress Estimator**: Build a system that estimates completion percentage based on expected output length

3. **Stream Merger**: Create a function that streams from multiple prompts simultaneously and merges the output

---

## What's Next?

You now have complete API mastery! Next week, we'll learn about **Structured Output & Data Parsing** - forcing LLMs to return valid JSON using Pydantic!
