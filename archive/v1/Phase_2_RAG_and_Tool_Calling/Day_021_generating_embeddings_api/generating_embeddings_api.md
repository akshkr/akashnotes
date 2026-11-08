# Generating Embeddings via API

Now that you understand what embeddings are and how to compare them, let's dive deep into the practical side: **generating embeddings efficiently at scale** using various APIs.

> **Coming from Software Engineering?** Generating embeddings via API is just another API call — like calling Google's Geocoding API to convert addresses to coordinates. You're converting text to numerical coordinates in meaning-space. The same batching and caching patterns you use for any external API apply.

---

## OpenAI Embeddings API

### Basic Usage

```python
# script_id: day_021_generating_embeddings_api/basic_openai_usage
from openai import OpenAI

client = OpenAI()

def get_embedding(text: str, model: str = "text-embedding-3-small") -> list[float]:
    """Get embedding for a single text."""
    response = client.embeddings.create(
        model=model,
        input=text
    )
    return response.data[0].embedding

# Simple usage
embedding = get_embedding("Hello, world!")
print(f"Dimensions: {len(embedding)}")
print(f"First 5 values: {embedding[:5]}")
```

### Available Models

```mermaid
flowchart TB
    subgraph "OpenAI Embedding Models"
        A["text-embedding-3-small"]
        B["text-embedding-3-large"]
        C["text-embedding-ada-002"]
    end

    A -->|"1536 dims<br/>$0.02/1M tokens"| D["Best value"]
    B -->|"3072 dims<br/>$0.13/1M tokens"| E["Highest quality"]
    C -->|"1536 dims<br/>$0.10/1M tokens"| F["Legacy"]

    style D fill:#90EE90
```

Prices as of 2026-06 — verify current pricing at the provider; dimensions are stable.

### Batch Processing

Always batch your requests for efficiency:

```python
# script_id: day_021_generating_embeddings_api/batch_processing
from openai import OpenAI
from typing import List

client = OpenAI()

def get_embeddings_batch(
    texts: List[str],
    model: str = "text-embedding-3-small",
    batch_size: int = 100
) -> List[List[float]]:
    """
    Get embeddings for multiple texts efficiently.
    Handles batching automatically.
    """
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]

        response = client.embeddings.create(
            model=model,
            input=batch
        )

        # Sort by index to maintain order
        sorted_data = sorted(response.data, key=lambda x: x.index)
        batch_embeddings = [item.embedding for item in sorted_data]
        all_embeddings.extend(batch_embeddings)

        print(f"Processed {min(i + batch_size, len(texts))}/{len(texts)}")

    return all_embeddings

# Usage
documents = [f"Document number {i}" for i in range(250)]
embeddings = get_embeddings_batch(documents)
print(f"Generated {len(embeddings)} embeddings")
```

### Dimension Reduction

The new embedding models support dimension reduction:

These models are trained so the most important meaning is packed into the earliest numbers, so you can keep the first N and drop the rest. Fewer dimensions means less storage and faster search in exchange for slightly less accuracy — 512 is usually a good balance.

```python
# script_id: day_021_generating_embeddings_api/dimension_reduction
from openai import OpenAI

client = OpenAI()

def get_embedding_with_dimensions(
    text: str,
    dimensions: int = 512
) -> list[float]:
    """
    Get embedding with reduced dimensions.
    Useful for saving storage and speeding up similarity search.
    """
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
        dimensions=dimensions  # Reduce from 1536 to desired size
    )
    return response.data[0].embedding

# Compare different dimension sizes
text = "Machine learning is transforming industries"

for dims in [256, 512, 1024, 1536]:
    emb = get_embedding_with_dimensions(text, dims)
    print(f"{dims} dimensions: {len(emb)} values")
```

---

## Async Embedding Generation

For high throughput applications:

We cap how many requests run at once with a semaphore — like a connection pool — because the provider will rate-limit you if you fire hundreds of requests simultaneously (see the RateLimitError handling below).

```python
# script_id: day_021_generating_embeddings_api/async_embedding_generation
import asyncio
from openai import AsyncOpenAI
from typing import List

client = AsyncOpenAI()

async def get_embedding_async(text: str) -> list[float]:
    """Get single embedding asynchronously."""
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding

async def get_embeddings_parallel(
    texts: List[str],
    max_concurrent: int = 10
) -> List[List[float]]:
    """Get embeddings with controlled concurrency."""
    semaphore = asyncio.Semaphore(max_concurrent)

    async def limited_embed(text: str, index: int):
        async with semaphore:
            response = await client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            return index, response.data[0].embedding

    tasks = [limited_embed(text, i) for i, text in enumerate(texts)]
    results = await asyncio.gather(*tasks)

    # Sort by index to maintain order
    sorted_results = sorted(results, key=lambda x: x[0])
    return [emb for _, emb in sorted_results]

# Usage
async def main():
    texts = [f"Sample text number {i}" for i in range(50)]
    embeddings = await get_embeddings_parallel(texts)
    print(f"Generated {len(embeddings)} embeddings")

asyncio.run(main())
```

---

## Alternative Embedding Providers

### Cohere

Some providers want to know whether the text is a stored document or a user search query and embed each slightly differently so queries land near the documents they should match — like the difference between indexing and querying in a search engine. Use the document type when building your index and the query type at search time. OpenAI does not expose this distinction.

```python
# script_id: day_021_generating_embeddings_api/cohere_embeddings
import cohere

# Cohere SDK v5+ uses ClientV2. (The older `cohere.Client` still exists but the
# v2 client is the current API.)
co = cohere.ClientV2("YOUR_COHERE_API_KEY")

def get_cohere_embeddings(texts: list[str]) -> list[list[float]]:
    """Get embeddings from Cohere."""
    response = co.embed(
        texts=texts,
        model="embed-english-v3.0",
        input_type="search_document",   # or "search_query" for queries
        embedding_types=["float"],      # required in v2 — pick the embedding type
    )
    # In v5, embeddings are grouped by type; float vectors live under `.float_`
    return response.embeddings.float_

# Usage
texts = ["Hello world", "Machine learning"]
embeddings = get_cohere_embeddings(texts)
print(f"Cohere embedding dimensions: {len(embeddings[0])}")  # 1024
```

### Voyage AI

```python
# script_id: day_021_generating_embeddings_api/voyage_embeddings
import voyageai

vo = voyageai.Client()

def get_voyage_embeddings(texts: list[str]) -> list[list[float]]:
    """Get embeddings from Voyage AI."""
    result = vo.embed(
        texts,
        model="voyage-3",   # voyage-2 is legacy; voyage-3 / voyage-3-lite are current
        input_type="document"
    )
    return result.embeddings

# Usage
embeddings = get_voyage_embeddings(["Sample text"])
```

### Hugging Face (Local)

```python
# script_id: day_021_generating_embeddings_api/huggingface_local_embeddings
from sentence_transformers import SentenceTransformer

# Download model once, run locally
model = SentenceTransformer('all-MiniLM-L6-v2')

def get_local_embeddings(texts: list[str]) -> list[list[float]]:
    """Get embeddings using local model.
    
    Note: In sentence-transformers v3.0+, .encode() consistently returns
    numpy arrays regardless of input type, so .tolist() always works.
    """
    embeddings = model.encode(texts)
    return embeddings.tolist()

# Usage - no API calls needed!
embeddings = get_local_embeddings(["Hello world", "Local embeddings"])
print(f"Local embedding dimensions: {len(embeddings[0])}")  # 384
```

---

## Unified Embedding Interface

```python
# script_id: day_021_generating_embeddings_api/unified_embedding_interface
from abc import ABC, abstractmethod
from typing import List
from enum import Enum

class EmbeddingProvider(Enum):
    OPENAI = "openai"
    COHERE = "cohere"
    LOCAL = "local"

class EmbeddingClient(ABC):
    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        pass

class OpenAIEmbeddings(EmbeddingClient):
    def __init__(self, model: str = "text-embedding-3-small"):
        from openai import OpenAI
        self.client = OpenAI()
        self.model = model

    def embed(self, texts: List[str]) -> List[List[float]]:
        response = self.client.embeddings.create(
            model=self.model,
            input=texts
        )
        return [d.embedding for d in sorted(response.data, key=lambda x: x.index)]

class LocalEmbeddings(EmbeddingClient):
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)

    def embed(self, texts: List[str]) -> List[List[float]]:
        return self.model.encode(texts).tolist()

def get_embedding_client(provider: EmbeddingProvider) -> EmbeddingClient:
    """Factory function for embedding clients."""
    if provider == EmbeddingProvider.OPENAI:
        return OpenAIEmbeddings()
    elif provider == EmbeddingProvider.LOCAL:
        return LocalEmbeddings()
    else:
        raise ValueError(f"Unknown provider: {provider}")

# Usage
client = get_embedding_client(EmbeddingProvider.OPENAI)
embeddings = client.embed(["Hello", "World"])
```

---

## Cost Optimization

```mermaid
flowchart TB
    subgraph "Embedding Cost Strategies"
        A["Batch requests"]
        B["Cache results"]
        C["Use smaller models"]
        D["Reduce dimensions"]
        E["Use local models"]
    end

    A --> F["Save API calls"]
    B --> F
    C --> G["Lower cost/token"]
    D --> G
    E --> H["No API cost!"]
```

### Caching Embeddings

```python
# script_id: day_021_generating_embeddings_api/caching_embeddings
import hashlib
import json
from pathlib import Path
from openai import OpenAI

client = OpenAI()

class EmbeddingCache:
    """Cache embeddings to avoid redundant API calls."""

    def __init__(self, cache_dir: str = ".embedding_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

    def _hash_text(self, text: str, model: str) -> str:
        """Create unique hash for text+model combination."""
        content = f"{model}:{text}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def get(self, text: str, model: str) -> list[float] | None:
        """Get cached embedding if exists."""
        cache_file = self.cache_dir / f"{self._hash_text(text, model)}.json"
        if cache_file.exists():
            with open(cache_file) as f:
                return json.load(f)
        return None

    def set(self, text: str, model: str, embedding: list[float]):
        """Cache an embedding."""
        cache_file = self.cache_dir / f"{self._hash_text(text, model)}.json"
        with open(cache_file, 'w') as f:
            json.dump(embedding, f)

cache = EmbeddingCache()

def get_embedding_cached(text: str, model: str = "text-embedding-3-small") -> list[float]:
    """Get embedding with caching."""
    # Check cache first
    cached = cache.get(text, model)
    if cached:
        print("Cache hit!")
        return cached

    # Generate new embedding
    print("Cache miss, calling API...")
    response = client.embeddings.create(model=model, input=text)
    embedding = response.data[0].embedding

    # Cache for future use
    cache.set(text, model, embedding)
    return embedding

# First call - API
emb1 = get_embedding_cached("Hello world")  # Cache miss

# Second call - cached
emb2 = get_embedding_cached("Hello world")  # Cache hit!
```

### Cost Calculator

```python
# script_id: day_021_generating_embeddings_api/cost_calculator
def calculate_embedding_cost(
    texts: list[str],
    model: str = "text-embedding-3-small"
) -> dict:
    """Estimate embedding cost before making API calls."""
    import tiktoken

    # Approximate pricing per 1M tokens — as of 2026-06; verify at platform.openai.com/pricing
    pricing = {
        "text-embedding-3-small": 0.02,
        "text-embedding-3-large": 0.13,
        "text-embedding-ada-002": 0.10
    }

    # Count tokens
    try:
        encoder = tiktoken.encoding_for_model(model)
    except:
        encoder = tiktoken.get_encoding("cl100k_base")

    total_tokens = sum(len(encoder.encode(text)) for text in texts)

    cost = (total_tokens / 1_000_000) * pricing.get(model, 0.02)

    return {
        "total_texts": len(texts),
        "total_tokens": total_tokens,
        "model": model,
        "estimated_cost": f"${cost:.6f}",
        "cost_per_text": f"${cost/len(texts):.8f}"
    }

# Usage
texts = ["Sample text"] * 1000
cost_info = calculate_embedding_cost(texts)
print(cost_info)
```

---

## Error Handling

This is the same exponential-backoff-on-429 pattern you would write for any third-party REST API — nothing embedding-specific.

```python
# script_id: day_021_generating_embeddings_api/error_handling
from openai import OpenAI, RateLimitError, APIError
import time

client = OpenAI()

def get_embedding_robust(
    text: str,
    max_retries: int = 3,
    model: str = "text-embedding-3-small"
) -> list[float] | None:
    """Get embedding with robust error handling."""

    for attempt in range(max_retries):
        try:
            response = client.embeddings.create(
                model=model,
                input=text
            )
            return response.data[0].embedding

        except RateLimitError:
            wait_time = 2 ** attempt
            print(f"Rate limited, waiting {wait_time}s...")
            time.sleep(wait_time)

        except APIError as e:
            status = getattr(e, 'status_code', None)
            if status is not None and status >= 500:
                print(f"Server error, retrying...")
                time.sleep(1)
            else:
                print(f"API error: {e}")
                return None

        except Exception as e:
            print(f"Unexpected error: {e}")
            return None

    print("Max retries exceeded")
    return None

# Usage
embedding = get_embedding_robust("Test text")
if embedding:
    print(f"Success! Got {len(embedding)} dimensions")
```

---

## Checkpoint

Run the `EmbeddingCache` example twice on the same text and confirm: the first call prints "Cache miss" and hits the API, the second prints "Cache hit" and returns instantly with no API call. If it misses every time, check that your cache key hashes both the text *and* the model name consistently — a trailing newline or a different model id will look like a new entry.

---

## Summary

```mermaid
mindmap
  root((Embedding APIs))
    Providers
      OpenAI
      Cohere
      Voyage AI
      Local models
    Optimization
      Batching
      Caching
      Async
      Dimension reduction
    Best Practices
      Error handling
      Rate limiting
      Cost tracking
```

---

## Quick Reference

```python
# script_id: day_021_generating_embeddings_api/quick_reference
# OpenAI (recommended for most use cases)
from openai import OpenAI
client = OpenAI()
response = client.embeddings.create(
    model="text-embedding-3-small",
    input=["text1", "text2"],  # Batch!
    dimensions=512  # Optional: reduce dimensions
)
embeddings = [d.embedding for d in response.data]

# Local (free, no API needed)
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
embeddings = model.encode(["text1", "text2"]).tolist()
```

---

## Exercises

1. **Provider Comparison**: Compare embedding quality from OpenAI, Cohere, and local models on the same text set. (Note: each model produces vectors in its own space and often a different number of dimensions, so you cannot cosine-compare one model's vector against another's directly. Compare each model only against itself — e.g. which model ranks the right document highest for the same query.)

<details>
<summary>Solution</summary>

```python
# script_id: day_021_generating_embeddings_api/exercise_provider_comparison
from sentence_transformers.util import cos_sim

query = "How do I reset my password?"
docs = [
    "To reset your password, click 'Forgot password' on the login page.",
    "Our office is open Monday to Friday, 9am to 5pm.",
    "Refunds are processed within 5 business days.",
]

# Compare each model only against itself: does it rank the right doc (index 0) first?
for provider in [EmbeddingProvider.OPENAI, EmbeddingProvider.LOCAL]:
    client = get_embedding_client(provider)
    q_emb = client.embed([query])[0]
    doc_embs = client.embed(docs)
    scores = [float(cos_sim(q_emb, d)) for d in doc_embs]
    best = max(range(len(scores)), key=lambda i: scores[i])
    print(f"{provider.value}: best match = doc {best} (correct={best == 0})")
```

</details>

2. **Cost Optimizer**: Build a system that automatically chooses between cached, local, and API embeddings based on cost/quality tradeoffs

<details>
<summary>Solution</summary>

```python
# script_id: day_021_generating_embeddings_api/exercise_cost_optimizer
def embed_smart(text: str, quality: str = "low") -> list[float]:
    """Reuse the cache first, then pick local (free) or API (higher quality)."""
    model = "text-embedding-3-small"
    cached = cache.get(text, model)
    if cached:
        return cached

    if quality == "low":
        # Free local model — no API cost
        emb = get_embedding_client(EmbeddingProvider.LOCAL).embed([text])[0]
    else:
        # Paid API for higher quality
        emb = get_embedding_cached(text, model)

    cache.set(text, model, emb)
    return emb

print(len(embed_smart("Cheap path", quality="low")))
print(len(embed_smart("Quality path", quality="high")))
```

</details>

3. **Async Benchmarker**: Measure speedup from async vs sequential embedding generation for 100, 500, and 1000 texts

<details>
<summary>Solution</summary>

```python
# script_id: day_021_generating_embeddings_api/exercise_async_benchmarker
import asyncio
import time

async def benchmark(n: int):
    texts = [f"Benchmark text {i}" for i in range(n)]

    # Sequential
    start = time.perf_counter()
    for t in texts:
        await get_embedding_async(t)
    seq = time.perf_counter() - start

    # Parallel (reuses get_embeddings_parallel from the async section)
    start = time.perf_counter()
    await get_embeddings_parallel(texts)
    par = time.perf_counter() - start

    print(f"n={n}: sequential={seq:.2f}s, parallel={par:.2f}s, speedup={seq/par:.1f}x")

async def main():
    for n in [100, 500, 1000]:
        await benchmark(n)

asyncio.run(main())
```

</details>

---

## What's Next?

Now that you can generate embeddings efficiently, let's learn how to **store and search them at scale** with Vector Databases!
