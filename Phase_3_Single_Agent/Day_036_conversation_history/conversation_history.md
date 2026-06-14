# Managing Conversation History

Agents need memory to maintain context. This guide shows you how to manage conversation history using simple Python data structures.

> **Coming from Software Engineering?** Conversation history management is just session state. If you've built web apps with server-side sessions or a Redis-backed session store, you already know how to manage conversational state. The `messages` array is your session object, and each LLM call resends the whole thing — the model keeps nothing between calls.

---

## Why Conversation History Matters

```mermaid
flowchart TB
    subgraph "Without History"
        A1["User: My name is Alice"]
        A2["Agent: Nice to meet you!"]
        A3["User: What's my name?"]
        A4["Agent: I don't know your name"]
    end

    subgraph "With History"
        B1["User: My name is Alice"]
        B2["Agent: Nice to meet you, Alice!"]
        B3["User: What's my name?"]
        B4["Agent: Your name is Alice!"]
    end

    style A4 fill:#ff6b6b
    style B4 fill:#90EE90
```

---

## Basic History: List of Dictionaries

The simplest approach - store messages as a list:

```python
# script_id: day_036_conversation_history/basic_chat_history
from openai import OpenAI

client = OpenAI()

# Initialize conversation history
history = []

def chat(user_message: str) -> str:
    """Send a message and maintain history."""

    # Add user message to history
    history.append({
        "role": "user",
        "content": user_message
    })

    # Call the LLM with full history
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."}
        ] + history
    )

    assistant_message = response.choices[0].message.content

    # Add assistant response to history
    history.append({
        "role": "assistant",
        "content": assistant_message
    })

    return assistant_message

# Usage
print(chat("My name is Alice"))
print(chat("What's my name?"))  # Remembers!
print(chat("What did I first tell you?"))  # Still remembers!
```

---

## Structured History Class

A cleaner, reusable approach:

```python
# script_id: day_036_conversation_history/structured_history_class
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime

@dataclass
class Message:
    role: str  # "user", "assistant", or "system"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)

class ConversationHistory:
    """Manage conversation history for an agent."""

    def __init__(self, system_prompt: str = "You are a helpful assistant."):
        self.system_prompt = system_prompt
        self.messages: List[Message] = []

    def add_user_message(self, content: str, metadata: dict = None):
        """Add a user message to history."""
        self.messages.append(Message(
            role="user",
            content=content,
            metadata=metadata or {}
        ))

    def add_assistant_message(self, content: str, metadata: dict = None):
        """Add an assistant message to history."""
        self.messages.append(Message(
            role="assistant",
            content=content,
            metadata=metadata or {}
        ))

    def get_messages_for_api(self) -> List[dict]:
        """Get messages formatted for API call."""
        api_messages = [{"role": "system", "content": self.system_prompt}]

        for msg in self.messages:
            api_messages.append({
                "role": msg.role,
                "content": msg.content
            })

        return api_messages

    def clear(self):
        """Clear all history."""
        self.messages = []

    def get_last_n_messages(self, n: int) -> List[Message]:
        """Get the last n messages."""
        return self.messages[-n:]

    def __len__(self):
        return len(self.messages)

# Usage
history = ConversationHistory(system_prompt="You are a coding assistant.")
history.add_user_message("How do I read a file in Python?")
history.add_assistant_message("You can use the open() function...")

messages = history.get_messages_for_api()
# Ready to send to LLM!
```

The rest of this lesson uses a generic `add(role, content)` for brevity; the interface is interchangeable — only the eviction/persistence behavior changes between sections.

---

## Sliding Window History

The model can only read a fixed amount of text per request — its *context window*. That text is measured in *tokens*, which are just chunks of characters (roughly 4 characters, or about 3/4 of a word, each). Because every message you resend counts against that limit, a long conversation eventually won't fit — that's what "token overflow" means. The fix is the same as any bounded cache: drop the oldest entries.

This is an LRU-style bounded cache for your session — `deque(maxlen=N)` evicts the oldest turn exactly like a capped session ring buffer. Prevent token overflow by keeping only recent messages:

```python
# script_id: day_036_conversation_history/sliding_window_history
from collections import deque

class SlidingWindowHistory:
    """Keep only the most recent N messages."""

    def __init__(self, max_messages: int = 20, system_prompt: str = "You are helpful."):
        self.max_messages = max_messages
        self.system_prompt = system_prompt
        self.messages = deque(maxlen=max_messages)

    def add(self, role: str, content: str):
        """Add a message (oldest messages auto-removed when full)."""
        self.messages.append({"role": role, "content": content})

    def get_messages(self) -> list:
        """Get all messages with system prompt."""
        return [
            {"role": "system", "content": self.system_prompt}
        ] + list(self.messages)

    def get_token_estimate(self) -> int:
        """Rough estimate of token count."""
        total_chars = sum(len(m["content"]) for m in self.messages)
        # Rough rule of thumb: ~4 characters per token for English text.
        # Only an estimate — use tiktoken (shown next) for the exact count.
        return total_chars // 4

# Usage
history = SlidingWindowHistory(max_messages=10)

for i in range(15):
    history.add("user", f"Message {i}")
    history.add("assistant", f"Response {i}")

print(f"Messages kept: {len(history.messages)}")  # 10, not 30
```

> **Heads-up:** frameworks like LangGraph (covered later in this phase) can manage the message list for you automatically. The hand-rolled versions here teach you what those frameworks do under the hood — worth understanding before you hand it off.

```mermaid
flowchart LR
    subgraph "Sliding Window (max=6)"
        M1["Msg 1"] --> M2["Msg 2"]
        M2 --> M3["Msg 3"]
        M3 --> M4["Msg 4"]
        M4 --> M5["Msg 5"]
        M5 --> M6["Msg 6"]
    end

    NEW["New Msg"] --> M6
    M1 -.->|"Removed"| X["🗑️"]

    style M1 fill:#ff6b6b
    style NEW fill:#90EE90
```

---

## Token-Aware History

Keep messages within a token budget. `tiktoken` is OpenAI's tokenizer — it counts tokens exactly the way the model does instead of guessing with chars/4. (`pip install tiktoken`. Token counts are model-specific; an Anthropic model would count differently.)

```python
# script_id: day_036_conversation_history/token_aware_history
import tiktoken

class TokenAwareHistory:
    """Manage history within a token budget."""

    def __init__(self, max_tokens: int = 4000, model: str = "gpt-4o-mini"):
        self.max_tokens = max_tokens
        self.model = model
        self.encoder = tiktoken.encoding_for_model(model)
        self.system_prompt = "You are a helpful assistant."
        self.messages = []

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoder.encode(text))

    def total_tokens(self) -> int:
        """Count total tokens in history."""
        total = self.count_tokens(self.system_prompt)
        for msg in self.messages:
            total += self.count_tokens(msg["content"])
            total += 4  # Overhead per message
        return total

    def add(self, role: str, content: str):
        """Add message, removing old ones if over budget."""
        new_tokens = self.count_tokens(content) + 4

        # Remove old messages until we have room
        while self.messages and (self.total_tokens() + new_tokens > self.max_tokens):
            removed = self.messages.pop(0)
            print("Removed old message to stay within budget")

        self.messages.append({"role": role, "content": content})

    def get_messages(self) -> list:
        """Get messages for API call."""
        return [
            {"role": "system", "content": self.system_prompt}
        ] + self.messages

# Usage
history = TokenAwareHistory(max_tokens=1000)

history.add("user", "Tell me about Python")
history.add("assistant", "Python is a programming language..." * 50)  # Long response
history.add("user", "What about JavaScript?")  # Might trigger cleanup

print(f"Current tokens: {history.total_tokens()}")
```

The `print` on each eviction is just so you can see the trimming happen — production code would log this at debug level rather than print to stdout.

---

## History with Tool Calls

Include tool calls in your history. When the model decides to call a tool (the ReAct pattern from Day 35), three things must land in history in order: the assistant's tool *request*, the *result* you fed back (as a `role: "tool"` message whose `tool_call_id` matches the request's `id`), and the assistant's final answer. The class below records that exact sequence so the model can see what it asked for and what came back.

```python
# script_id: day_036_conversation_history/tool_aware_history
class ToolAwareHistory:
    """History that handles tool calls."""

    def __init__(self):
        self.messages = []

    def add_user(self, content: str):
        self.messages.append({"role": "user", "content": content})

    def add_assistant(self, content: str = None, tool_calls: list = None):
        """Add assistant message, optionally with tool calls."""
        message = {"role": "assistant"}

        if content:
            message["content"] = content

        if tool_calls:
            message["tool_calls"] = tool_calls

        self.messages.append(message)

    def add_tool_result(self, tool_call_id: str, result: str):
        """Add a tool result."""
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": result
        })

    def get_messages(self) -> list:
        return self.messages.copy()

# Usage with tool calls
history = ToolAwareHistory()

history.add_user("What's the weather in Tokyo?")

# LLM responds with tool call
history.add_assistant(tool_calls=[{
    "id": "call_123",
    "type": "function",
    "function": {
        "name": "get_weather",
        "arguments": '{"city": "Tokyo"}'
    }
}])

# Add tool result
history.add_tool_result("call_123", '{"temp": 22, "condition": "sunny"}')

# LLM gives final response
history.add_assistant("The weather in Tokyo is 22°C and sunny!")
```

---

## Conversation Branching

Support for exploring different conversation paths:

```python
# script_id: day_036_conversation_history/branchable_history
from typing import Dict, List, Optional
import copy

class BranchableHistory:
    """History that supports branching and rollback."""

    def __init__(self):
        self.messages: List[dict] = []
        self.branches: Dict[str, List[dict]] = {}
        self.current_branch: str = "main"

    def add(self, role: str, content: str):
        """Add message to current branch."""
        self.messages.append({
            "role": role,
            "content": content,
            "branch": self.current_branch
        })

    def create_branch(self, name: str):
        """Fork the current state into a new, independent branch."""
        # Persist the branch we're leaving so it isn't lost...
        self.branches[self.current_branch] = self.messages
        # ...then start the new branch as a fork (independent copy).
        self.current_branch = name
        self.messages = copy.deepcopy(self.branches[name] if name in self.branches
                                      else self.messages)

    def switch_branch(self, name: str):
        """Switch to a different branch."""
        if name not in self.branches and name != self.current_branch:
            raise ValueError(f"Branch {name} not found")
        # Save current branch before swapping, so edits don't leak across branches.
        self.branches[self.current_branch] = self.messages
        self.messages = copy.deepcopy(self.branches[name])
        self.current_branch = name

    def rollback(self, n: int = 1):
        """Remove the last n messages."""
        if n <= 0:
            return
        self.messages = self.messages[:-n]

    def get_messages(self) -> list:
        """Get messages for API (without metadata)."""
        return [
            {"role": m["role"], "content": m["content"]}
            for m in self.messages
        ]

# Usage
history = BranchableHistory()

history.add("user", "Help me write a function")
history.add("assistant", "Sure! What should it do?")
history.add("user", "Calculate factorial")

# Fork off to try a recursive approach (this branch is independent)
history.create_branch("recursive")
history.add("assistant", "Here's a recursive approach...")

# Go back to the shared starting point and fork a separate iterative branch
history.switch_branch("main")
history.create_branch("iterative")
history.add("assistant", "Here's an iterative approach...")

# Branches are independent: "iterative" never sees the "recursive" turn.
history.switch_branch("recursive")  # back to the recursive line of thought
```

```mermaid
flowchart TB
    A["Start"] --> B["User: Help me"]
    B --> C["Assistant: Sure!"]
    C --> D["User: Calculate factorial"]

    D --> E["Branch: recursive"]
    D --> F["Branch: iterative"]

    E --> E1["Recursive solution"]
    F --> F1["Iterative solution"]

    style E fill:#87CEEB
    style F fill:#90EE90
```

---

## Persisting History

This is just serializing your session store — `json.dump`/`load` is the conversational equivalent of writing a Redis session to disk and rehydrating it. Save and load conversation history:

```python
# script_id: day_036_conversation_history/persistent_history
import json
from pathlib import Path
from datetime import datetime

class PersistentHistory:
    """History that can be saved to and loaded from disk."""

    def __init__(self, filepath: str = None):
        self.filepath = filepath
        self.messages = []
        self.metadata = {
            "created_at": datetime.now().isoformat(),
            "updated_at": None
        }

        if filepath and Path(filepath).exists():
            self.load()

    def add(self, role: str, content: str):
        """Add a message."""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        self.metadata["updated_at"] = datetime.now().isoformat()

    def save(self, filepath: str = None):
        """Save history to file."""
        path = filepath or self.filepath
        if not path:
            raise ValueError("No filepath specified")

        data = {
            "metadata": self.metadata,
            "messages": self.messages
        }

        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    def load(self, filepath: str = None):
        """Load history from file."""
        path = filepath or self.filepath
        if not path:
            raise ValueError("No filepath specified")

        with open(path, 'r') as f:
            data = json.load(f)

        self.metadata = data.get("metadata", {})
        self.messages = data.get("messages", [])

    def get_messages_for_api(self) -> list:
        """Get messages without timestamps."""
        return [
            {"role": m["role"], "content": m["content"]}
            for m in self.messages
        ]

# Usage
history = PersistentHistory("conversation.json")
history.add("user", "Hello!")
history.add("assistant", "Hi there!")
history.save()

# Later...
loaded_history = PersistentHistory("conversation.json")
print(loaded_history.messages)  # Previous conversation loaded!
```

---

## Summary

```mermaid
mindmap
  root((Conversation History))
    Basic
      List of dicts
      Append messages
      Simple & direct
    Windowed
      Max messages
      Token budget
      Auto cleanup
    Advanced
      Tool calls
      Branching
      Persistence
    Best Practices
      Include system prompt
      Track metadata
      Handle overflow
```

---

## Quick Reference

```python
# script_id: day_036_conversation_history/quick_reference
# Basic history
history = []
history.append({"role": "user", "content": "Hello"})
history.append({"role": "assistant", "content": "Hi!"})

# Sliding window
from collections import deque
history = deque(maxlen=20)

# Token-aware
while total_tokens > max_tokens:
    history.pop(0)

# Save/Load
json.dump(history, open("history.json", "w"))
history = json.load(open("history.json"))
```

---

## Exercises

1. Build a sliding-window history with `deque(maxlen=20)` and confirm that the oldest messages drop off after the 21st append — but make sure the system message never gets evicted.
2. Write a `token_budget_trim(history, max_tokens)` that removes the *oldest non-system* messages until the estimated token count fits, then test it on a long fake conversation.
3. Add `save(path)` / `load(path)` methods that round-trip the history to JSON and back, and verify the reloaded list equals the original.
4. Extend a history entry to carry a `tool_calls` field, then write a function that reconstructs only the user/assistant turns (dropping tool noise) for a clean transcript view.

<details><summary>Solutions (approaches)</summary>

1. Keep the system message separate: store it once, build the window from `deque(maxlen=19)` of the rest, and prepend system on read. Append 21 user turns and assert `len(window) == 19`.
2. Estimate tokens with `len(content) // 4` (or `tiktoken`); loop `while total > max_tokens: history.pop(1)` (index 1 skips system) and recompute.
3. `json.dump(self.messages, open(path, "w"))` and `self.messages = json.load(open(path))`; assert equality after reload.
4. Filter with `[m for m in history if m["role"] in ("user", "assistant") and not m.get("tool_calls")]`.
</details>

---

## Checkpoint

Run the `SlidingWindowHistory` example: add 15 user/assistant pairs to a window of `max_messages=10` and print `len(history.messages)`. You should see exactly `10`, not `30` — the oldest messages were silently evicted by `deque(maxlen=...)`, just like the system session stores you've capped before. If you see `30`, you're appending to a plain list somewhere instead of the bounded `deque`.

---

## What's Next?

Now let's learn about **implementing hard stops and max iterations** to prevent your agent from running forever!
