# Understanding Transformers: The Brain Behind LLMs

Welcome to your AI journey! In this guide, we'll demystify the Transformer architecture - the revolutionary technology powering ChatGPT, Claude, and other Large Language Models (LLMs).

Don't worry - we're keeping the math minimal and focusing on building solid intuition.

> **Coming from Software Engineering?** Think of Transformers like a highly optimized search algorithm — instead of querying a database, they query their own training data using attention patterns. If you've built search engines or worked with information retrieval, the attention mechanism will feel intuitive: it's essentially a weighted lookup where every word 'queries' every other word.

---

## What is a Transformer?

Think of a Transformer as a super-smart reading machine. When you give it text, it doesn't just read word by word like we do. Instead, it looks at ALL words simultaneously and figures out how they relate to each other.

```mermaid
flowchart LR
    subgraph Input
        A[The] --> B[cat]
        B --> C[sat]
        C --> D[on]
        D --> E[the]
        E --> F[mat]
    end

    subgraph Transformer
        G[Process All Words\nAt Once]
    end

    subgraph Output
        H[Understanding of\nEntire Sentence]
    end

    Input --> Transformer --> Output
```

### Before Transformers: The Old Way

Before Transformers (2017), we used models called RNNs (Recurrent Neural Networks) that processed text one word at a time - like reading a book character by character. This was:

- **Slow**: Had to wait for each word to be processed
- **Forgetful**: By the time it reached word 100, it might forget word 1
- **Sequential**: Couldn't use modern parallel computing effectively

### The Transformer Revolution

Transformers changed everything by introducing **parallel processing** - reading the entire text at once, like seeing a whole page in one glance.

---

## The Secret Sauce: Self-Attention

Here's where the magic happens. Self-attention is how the model figures out which words are important for understanding other words.

### A Simple Example

Consider the sentence: *"The cat sat on the mat because it was tired."*

What does "it" refer to? You instantly know it's "the cat" - but how?

Your brain automatically connected "it" with "cat" because:
1. "it" is a pronoun that needs a reference
2. "cat" is the most logical subject
3. "mat" doesn't get tired

**Self-attention does exactly this!** It calculates a "relevance score" between every pair of words.

```mermaid
flowchart TD
    subgraph Attention Scores
        A["it"] -->|High Attention| B["cat"]
        A -->|Low Attention| C["mat"]
        A -->|Medium Attention| D["sat"]
        A -->|Low Attention| E["the"]
    end

    style A fill:#ff6b6b
    style B fill:#4ecdc4
```

### How Self-Attention Works (Simplified)

Imagine each word asking three questions:
1. **Query (Q)**: "What am I looking for?"
2. **Key (K)**: "What do I contain?"
3. **Value (V)**: "What information can I give?"

```mermaid
flowchart LR
    subgraph "Word: 'it'"
        Q["Query: I need\nmy reference"]
    end

    subgraph "Word: 'cat'"
        K["Key: I'm a\nnoun/subject"]
        V["Value: Animal that\ncan be tired"]
    end

    Q -->|"Match!"| K
    K --> V
    V -->|"Send info to 'it'"| Result["'it' now knows\nit refers to 'cat'"]
```

The model computes attention scores for every word pair. Words that are relevant to each other get high scores.

---

## Context Windows: The Model's Memory Limit

Every LLM has a **context window** - the maximum amount of text it can "see" at once.

### What is a Context Window?

Think of it as the model's working memory or desk space. Just like you can only fit so many papers on your desk, an LLM can only process a certain number of tokens at once.

```mermaid
flowchart TB
    subgraph "Context Window (e.g., 8,000 tokens)"
        A["System Prompt\n(500 tokens)"]
        B["Conversation History\n(3,000 tokens)"]
        C["Your Current Question\n(200 tokens)"]
        D["Space for Response\n(4,300 tokens remaining)"]
    end

    style D fill:#90EE90
```

### Common Context Window Sizes

| Model | Context Window |
|-------|---------------|
| GPT-4o | 128,000 tokens |
| GPT-4o mini | 128,000 tokens |
| Claude Opus 4.x / Sonnet 4.6 | 1,000,000 tokens |
| Claude Haiku 4.5 | 200,000 tokens |
| Llama 3.1 (8B/70B) | 128,000 tokens |
| Gemini 2.0 | 1,000,000 tokens |

*(Context windows and model lineups change often — treat these as ballpark figures and check the provider's docs for current limits.)*

### Why Context Windows Matter

```python
# script_id: day_002_transformer_intuition/context_window_example
# Example: When your conversation exceeds the context window

conversation_so_far = """
[5000 tokens of previous chat]
User: What was the first thing I told you?
"""

# If context window is 4096 tokens, the model literally
# CANNOT see the beginning of your conversation anymore!

# Solution: Summarization or chunking strategies (we'll cover later)
```

### The Sliding Window Problem

```mermaid
flowchart LR
    subgraph "Full Conversation"
        A["Message 1"]
        B["Message 2"]
        C["Message 3"]
        D["Message 4"]
        E["Message 5"]
        F["Message 6"]
    end

    subgraph "What Model Sees (Window = 4)"
        C2["Message 3"]
        D2["Message 4"]
        E2["Message 5"]
        F2["Message 6"]
    end

    A -.->|"Lost!"| X["Cannot access"]
    B -.->|"Lost!"| X

    style A fill:#ff6b6b
    style B fill:#ff6b6b
    style X fill:#ff6b6b
```

---

## The Architecture: Putting It All Together

Here's how a Transformer processes your text:

```mermaid
flowchart TB
    subgraph Input
        A["Your Text Input"]
    end

    subgraph Tokenization
        B["Split into Tokens"]
    end

    subgraph Embedding
        C["Convert to Numbers\n(Vectors)"]
    end

    subgraph "Transformer Layers (x12 to x96)"
        D["Self-Attention"]
        E["Feed Forward\nNeural Network"]
        D --> E
    end

    subgraph Output
        F["Predict Next Token"]
    end

    A --> B --> C --> D
    E --> F

    F -->|"Loop: Generate\nmore tokens"| D
```

### Key Components

1. **Input Embedding**: Converts text to numbers the model can process
2. **Positional Encoding**: Tells the model where each word is in the sentence
3. **Multi-Head Attention**: Multiple attention mechanisms working in parallel (like having multiple readers analyzing the text)
4. **Feed-Forward Network**: Processes the attention output
5. **Output Layer**: Predicts the next token

---

## Multi-Head Attention: Multiple Perspectives

Instead of one attention mechanism, Transformers use multiple "heads" - each looking for different patterns:

```mermaid
flowchart TB
    subgraph "Multi-Head Attention"
        Input["Input Text"]

        subgraph "Head 1"
            H1["Looks for:\nGrammar patterns"]
        end

        subgraph "Head 2"
            H2["Looks for:\nSemantic meaning"]
        end

        subgraph "Head 3"
            H3["Looks for:\nEntity references"]
        end

        subgraph "Head 4"
            H4["Looks for:\nTemporal relations"]
        end

        Combined["Combine All\nPerspectives"]
    end

    Input --> H1 & H2 & H3 & H4
    H1 & H2 & H3 & H4 --> Combined
```

Think of it like having a team of editors, each specializing in different aspects of writing!

---

## Why This Matters for You as a Developer

Understanding Transformers helps you:

1. **Write better prompts**: Knowing the model processes everything at once helps you structure prompts effectively

2. **Manage context wisely**: Understanding context windows helps you design systems that don't lose important information

3. **Debug weird behavior**: When the model "forgets" something, you'll know it might be a context window issue

4. **Choose the right model**: Different context windows and capabilities for different use cases

---

## Quick Recap

| Concept | What It Does | Why It Matters |
|---------|--------------|----------------|
| Self-Attention | Connects related words | Enables understanding of context and references |
| Context Window | Limits visible text | Determines how much history/context model can use |
| Multi-Head Attention | Multiple parallel attention | Captures different types of relationships |
| Parallel Processing | Processes all at once | Makes LLMs fast and efficient |

---

## What's Next?

Now that you understand how Transformers "think," let's dive into **Tokenization** - how LLMs actually see and process your text at the character level.

---

## Try It Yourself!

Here's a simple mental exercise:

```python
# script_id: day_002_transformer_intuition/self_attention_exercise
# Think about this sentence:
sentence = "The bank by the river was overgrown with grass."

# Questions to ponder:
# 1. What does "bank" mean here?
# 2. How would self-attention help disambiguate?
# 3. Which words would have high attention scores with "bank"?

# Answer: "river", "overgrown", and "grass" would all have high attention
# with "bank" — helping the model understand it's a riverbank,
# not a financial bank!
```

Understanding these concepts will make you a much more effective AI developer. You're building the foundation for everything that comes next!

---

## Summary

```mermaid
mindmap
  root((Transformers))
    Self-attention
      Words look at other words
      Resolves references like "it"
      High scores = strong relation
    Context window
      The model's working memory
      Everything must fit in tokens
      Bigger window = more history
    Multi-head attention
      Several attention "views" at once
      Grammar, meaning, references
      Combined into one understanding
    Parallel processing
      All tokens at once, not left-to-right
      Fast on GPUs
      Why transformers scaled
```

## Quick Reference

| Concept | One-liner | SWE analogy |
|---|---|---|
| Self-attention | Each token weighs every other token | A join where rows score their relevance to each other |
| Attention score | Strength of relation between two tokens | A similarity weight |
| Context window | Max tokens the model can see at once | A fixed-size buffer / RAM limit |
| Multi-head attention | Several attention computations in parallel | Running multiple indexes over the same data |
| Parallelism | All positions processed together | SIMD / vectorized ops vs. a serial loop |

## Exercises

1. **Disambiguate by attention.** Take the sentence `"The trophy didn't fit in the suitcase because it was too big."` Write down which word `it` refers to, and list the 2–3 words you'd expect to have the highest attention with `it`.
2. **Estimate a context budget.** A model has a 128K-token window. If a chat keeps ~750 tokens per turn, roughly how many turns fit before you must trim history? What strategy would you use when it fills?
3. **Spot the heads.** For `"The river bank was muddy after the storm,"` describe two *different* relationships separate attention heads might capture (e.g. one for meaning, one for grammar).
4. **Extend the mental model.** Explain in two sentences why parallel processing makes transformers faster to train than older left-to-right RNNs.

<details><summary>Solutions (approaches)</summary>

1. `it` = the trophy (the thing that didn't fit). Expect high attention between `it` and `trophy`, plus `big` / `fit`.
2. `128000 / 750` ≈ **170 turns**. Past that, summarize older turns or drop the oldest (sliding window) — both covered in later days.
3. One head might link `bank` ↔ `river`/`muddy` (meaning → riverbank), another might link the article `The` ↔ `bank` (grammatical structure).
4. RNNs process token *t* only after *t-1*, so work is serial; transformers compute all positions' attention simultaneously, which maps cleanly onto GPU parallelism.
</details>
