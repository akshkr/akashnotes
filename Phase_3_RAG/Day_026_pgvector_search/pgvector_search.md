# Vector Search with pgvector

Your Day 25 search re-embeds the whole corpus every run, lives in RAM, and forgets everything when the process exits. Vector search is a table with a vector column and `ORDER BY distance LIMIT k`, and Postgres already gives you durability, transactions and `WHERE`. Today Atlas gets a real index that survives restarts and pays only for the chunks that changed.

## At a Glance

- **Time:** ~2 h core (+ optional Go Deeper) · **Depth:** working
- **Prerequisites:** [Day 23: Embeddings & Semantic Similarity](../../Phase_3_RAG/Day_023_embeddings/embeddings.md), [Day 25: Chunking Strategies](../../Phase_3_RAG/Day_025_chunking/chunking.md); primers [SQL & Postgres](../../Appendix_Primers/A07_sql_postgres.md) and [Docker & compose](../../Appendix_Primers/A08_docker_compose.md)
- **You'll build:** `atlas/index.py`: an `Index` over Postgres + pgvector with content-hash ids, idempotent upserts, stale-row deletes and a filtered `search()`, plus a `MemoryIndex` with the same methods for machines without Docker
- **Stops at:** ANN internals (graph layers, quantization theory)
- **Fast path:** Already run Postgres and know embeddings? Read [The Atlas Index](#the-atlas-index), [ANN Indexes and Tuning](#ann-indexes-and-tuning), then do Exercise 2 (≈50 min)
- **Cost:** ≈ $0.01 on `text-embedding-3-small` for one corpus embed; re-runs ≈ $0; the benchmark is synthetic and free (prices as of 2026-11, [verify](https://developers.openai.com/api/docs/pricing))
- **New terms:** vector column, distance operator, ANN index (HNSW / IVFFlat), upsert, content-hash id

> **Coming from Software Engineering?** A vector store is an indexed column that ranks rows by similarity instead of matching them with `=`. Everything else is CRUD you already know: insert, update, delete, filter, all inside a transaction. The one new idea is the ANN index. A B-tree is always exact; an approximate index trades a little recall (the share of the true best results it actually returns) for a lot of speed, a trade a B-tree never makes. Content-hash ids work like HTTP ETags (a fingerprint of the content): if the fingerprint didn't change, you skip the expensive work.

## Search That Forgets

On Day 25 every run did the same thing: load 45 pages, chunk them, embed every chunk, hold the matrix in a numpy array, search. That has three problems. You pay to re-embed text that hasn't changed. Nothing survives a restart, so a web server would re-embed on every deploy. And there's no clean way to say "only pages for Orbit 3.x" without writing your own filter loop. A database solves all three, and you probably run one already.

## A Catalogue Sorted by Closeness

Picture a library card catalogue. A normal catalogue finds cards by exact match: author = "Le Guin". Now imagine you could hand the librarian a question and say "give me the five cards closest in meaning". That's a vector column: every card carries a list of numbers (its embedding from [Day 23](../../Phase_3_RAG/Day_023_embeddings/embeddings.md)), and the database can sort cards by how close those numbers are to your question's numbers.

Sorting every card on every question is slow once you have millions. So the library adds a shortcut index: a map that sends you straight to the right drawers. It's much faster and almost always right, though it occasionally misses a card in a neighbouring drawer. That shortcut is an ANN index, and you'll measure the "almost always" today.

## Three Rows by Hand

Take three 2-D vectors and the query `q = [1, 0]`. Cosine distance is `1 − cosine similarity`, so 0 means "same direction" and 2 means "opposite".

| Row | Vector | Cosine similarity with `q` | Cosine distance |
|---|---|---|---|
| a | `[1, 0]` | 1.0 | 0.0 |
| b | `[0.6, 0.8]` | 0.6 | 0.4 |
| c | `[0, 1]` | 0.0 | 1.0 |

`ORDER BY distance LIMIT 2` returns `a`, then `b`. Check it in numpy before you touch a database:

```python
# script_id: day_026_pgvector_search/hand_example
# Cosine distance by hand for three toy rows. Install: uv add numpy
import numpy as np

rows = {"a": [1.0, 0.0], "b": [0.6, 0.8], "c": [0.0, 1.0]}
q = np.array([1.0, 0.0])
for name, vec in rows.items():
    v = np.array(vec)
    cos = float(v @ q / (np.linalg.norm(v) * np.linalg.norm(q)))
    print(f"{name}  similarity={cos:.2f}  distance={1 - cos:.2f}")
```

```text
a  similarity=1.00  distance=0.00
b  similarity=0.60  distance=0.40
c  similarity=0.00  distance=1.00
```

## Name the Parts

pgvector is a Postgres extension that adds a few things:

- **Vector column:** a column type `vector(n)` that holds exactly `n` floats. Pick `n` to match your embedding model: 1536 for `text-embedding-3-small`.
- **Distance operator:** an SQL operator that returns how far apart two vectors are. Lower is closer.

| Operator | Measures | Note |
|---|---|---|
| `<=>` | cosine distance | similarity = `1 − distance`. Only cosine has this tidy relationship |
| `<->` | Euclidean (L2) distance | straight-line distance |
| `<#>` | **negative** inner product | negative so that `ORDER BY` ascending still means "best first" |

- **ANN index (approximate nearest neighbour):** a fast search that may miss a few true neighbours. pgvector offers HNSW and IVFFlat. Each index is built for one operator through its operator class (opclass): `vector_cosine_ops` for `<=>`, `vector_l2_ops` for `<->`, `vector_ip_ops` for `<#>`. If the query's operator doesn't match the opclass, the index is silently skipped.
- **Upsert:** insert, or update if the row already exists. In Postgres that's `INSERT … ON CONFLICT (id) DO UPDATE`.
- **Content-hash id:** a row id computed from the content itself (a SHA-256 hash), so the same text always gets the same id.

OpenAI embeddings are unit-length, and for unit vectors all three operators produce the same ranking. Atlas uses `<=>` because its score converts cleanly to a 0-to-1 similarity.

```mermaid
flowchart LR
    App["Atlas code"] -->|"SQL + numpy vector"| Driver["psycopg 3 + register_vector"]
    Driver --> Table["chunks table: id, doc_id, body, applies_to, embedding"]
    Table -->|"ORDER BY embedding <=> q"| Plan{"Planner"}
    Plan -->|"no ANN index"| Exact["Exact scan: every row"]
    Plan -->|"matching HNSW index"| HNSW["HNSW index: approximate"]
    Exact -->|"LIMIT k"| Rows["Top-k rows + distance"]
    HNSW -->|"LIMIT k"| Rows
    Rows --> App
```

It really is a table: `WHERE`, `JOIN`, transactions and backups work as always.

## Postgres in One Command

You don't need to administer Postgres today. Compose describes the services you need in one file. Save this as `compose.yaml` and run `docker compose up -d`. It pins pgvector 0.8.7 on Postgres 18. (No Docker yet? Read the [Docker & compose primer](../../Appendix_Primers/A08_docker_compose.md), or skip to the [in-memory fallback](#no-docker-the-same-index-in-memory).)

```yaml
# compose.yaml: Postgres 18 + pgvector 0.8.7 for Atlas. Start: docker compose up -d
services:
  db:
    image: pgvector/pgvector:0.8.7-pg18-trixie
    environment:
      POSTGRES_USER: atlas
      POSTGRES_PASSWORD: atlas   # local dev only; never reuse this password anywhere real
      POSTGRES_DB: atlas
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql   # PG 18 images keep data here, not in .../data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U atlas -d atlas"]
      interval: 2s
      timeout: 5s
      retries: 15
volumes:
  pgdata:
```

`docker compose ps` should show the service as `healthy`. Now the smallest useful program: create the extension, register the type with the driver, store the three toy rows and ask for the nearest two.

```python
# script_id: day_026_pgvector_search/hello_pgvector
# Minimal pgvector round trip: extension, table, three rows, one nearest-neighbour query.
# Install: uv add "psycopg[binary]" pgvector numpy
# Env: DATABASE_URL (default matches compose.yaml). Services: Postgres from compose.yaml
import os

import numpy as np
import psycopg
from pgvector.psycopg import register_vector

url = os.environ.get("DATABASE_URL", "postgresql://atlas:atlas@localhost:5432/atlas")
with psycopg.connect(url, autocommit=True) as conn:
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")  # once per database
    register_vector(conn)  # once per connection, and only after the extension exists
    conn.execute("DROP TABLE IF EXISTS toy")
    conn.execute("CREATE TABLE toy (id text PRIMARY KEY, embedding vector(2))")
    for name, vec in [("a", [1, 0]), ("b", [0.6, 0.8]), ("c", [0, 1])]:
        conn.execute("INSERT INTO toy VALUES (%s, %s)", (name, np.array(vec, dtype=np.float32)))
    q = np.array([1, 0], dtype=np.float32)
    rows = conn.execute("SELECT id, embedding <=> %s AS dist FROM toy ORDER BY dist LIMIT 2", (q,)).fetchall()
    for id_, dist in rows:
        print(f"{id_}  distance={dist:.2f}  similarity={1 - dist:.2f}")
```

```text
a  distance=0.00  similarity=1.00
b  distance=0.40  similarity=0.60
```

Same answer as your hand calculation. `register_vector` teaches psycopg to send numpy arrays as `vector` values and to read them back as `pgvector.Vector` objects (call `.to_numpy()` when you need an array).

## Break It: Three Errors You Will Meet

Run these on purpose so you recognise the text later. The script reuses the `toy` table.

```python
# script_id: day_026_pgvector_search/break_it
# Three common pgvector failures, caught and printed. Run hello_pgvector first (it creates `toy`).
# Install: uv add "psycopg[binary]" pgvector numpy · Services: Postgres from compose.yaml
import os

import numpy as np
import psycopg
from pgvector.psycopg import register_vector

url = os.environ.get("DATABASE_URL", "postgresql://atlas:atlas@localhost:5432/atlas")
conn = psycopg.connect(url, autocommit=True)  # autocommit: one failed statement doesn't poison the rest
register_vector(conn)


def attempt(label: str, sql: str, params: tuple) -> None:
    try:
        conn.execute(sql, params).fetchall()
        print(f"{label}: no error")
    except psycopg.Error as exc:
        print(f"{label}: {type(exc).__name__}: {str(exc).splitlines()[0]}")


# 1. A plain Python list is sent as a float array, not a vector.
attempt("plain list", "SELECT id FROM toy ORDER BY embedding <=> %s LIMIT 1", ([1.0, 0.0],))
# 2. Wrong size on insert: a 3-d vector into the vector(2) column (same error for 256-d into 1536-d).
attempt("insert 3-d", "INSERT INTO toy VALUES ('d', %s) RETURNING id", (np.zeros(3, dtype=np.float32),))
# 3. Query embedded with a different model or `dimensions=` than the stored rows (3-d vs 2-d here).
attempt("query 3-d", "SELECT id FROM toy ORDER BY embedding <=> %s LIMIT 1", (np.ones(3, dtype=np.float32),))
conn.close()
```

```text
plain list: UndefinedFunction: operator does not exist: vector <=> double precision[]
insert 3-d: DataException: expected 2 dimensions, not 3
query 3-d: DataException: different vector dimensions 2 and 3
```

The fixes: pass an `np.ndarray` or `pgvector.Vector` (or write `%s::vector`); make the column width equal the model's output size; and embed queries with exactly the model and `dimensions` you indexed with. A fourth error appears if you call `register_vector` on a database where nobody has run `CREATE EXTENSION`: `psycopg.ProgrammingError: vector type not found in the database`. That's why `connect()` below always creates the extension first.

## One Support File for the Index

The scripts from here on import a compact `support.py` with helpers from earlier days (the toy scripts above do not need it). Save it next to the other scripts and run everything from that folder. It holds config, the `DocChunk` model, a front-matter loader and a Markdown chunker.

```python
# script_id: day_026_pgvector_search/support
# support.py: compact copies of earlier helpers so today's files stay self-contained.
# built on Day 23 (embed, hit_rate), Day 24 (load_corpus), Day 25 (DocChunk fields, chunk), Day 12 (cost)
# Install: uv add "openai>=3.46,<4" pydantic numpy
# Env: ORBIT_DATA (path to datasets/orbit); OPENAI_API_KEY only when embed() is called
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np
from pydantic import BaseModel, Field

DATA_DIR = Path(os.environ.get("ORBIT_DATA", "datasets/orbit"))
EMBED_MODEL = os.environ.get("ATLAS_EMBED_MODEL", "text-embedding-3-small")
EMBED_DIM = 1536  # text-embedding-3-small's default size; the vector(n) column must match it
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://atlas:atlas@localhost:5432/atlas")
```

Next come the two data types: `DocChunk` (one searchable piece of a page, from Day 25) and `Document` (one whole page).

```python
# script_id: day_026_pgvector_search/support
class DocChunk(BaseModel):
    id: str
    doc_id: str
    section: str = ""
    applies_to: str = "all"
    text: str
    position: int = 0
    n_tokens: int = 0
    header: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


@dataclass
class Document:
    id: str
    title: str
    text: str
    metadata: dict[str, str]
```

The second block loads pages and cuts them at `##` headings, the Markdown strategy from Day 25 in compact form.

```python
# script_id: day_026_pgvector_search/support
def load_corpus(root: Path = DATA_DIR / "docs") -> list[Document]:
    docs = []
    for path in sorted(root.glob("*.md")):
        _, front, body = path.read_text(encoding="utf-8").split("---", 2)
        meta = {}
        for line in front.strip().splitlines():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.split(" #")[0].strip().strip('"')  # drop inline comments, quotes
        docs.append(Document(meta.get("id", path.stem), meta.get("title", path.stem), body.strip(), meta))
    return docs


def chunk(doc: Document, *, max_chars: int = 1600) -> list[DocChunk]:
    """Split at H2 headings (outside code fences), then pack paragraphs up to max_chars."""
    sections: list[tuple[str, list[str]]] = [("", [])]
    in_fence = False
    for line in doc.text.splitlines():
        in_fence ^= line.startswith("```")
        if line.startswith("## ") and not in_fence:
            sections.append((line[3:].strip(), []))
        else:
            sections[-1][1].append(line)
    out: list[DocChunk] = []
    for heading, lines in sections:
        pieces, buf = [], ""
        for para in "\n".join(lines).split("\n\n"):
            if buf and len(buf) + len(para) > max_chars:
                pieces.append(buf)
                buf = ""
            buf = f"{buf}\n\n{para}" if buf else para
        for text in (p.strip() for p in pieces + [buf]):
            if text:
                out.append(DocChunk(
                    id=f"{doc.id}#{len(out)}", doc_id=doc.id, position=len(out), text=text,
                    section=doc.metadata.get("section", ""), applies_to=doc.metadata.get("applies_to", "all"),
                    header=f"{doc.title} > {heading}" if heading else doc.title))
    return out
```

`embed_text()` builds the exact string that gets embedded (heading breadcrumb plus body). Remember it: the content-hash id below is computed from this same string.

```python
# script_id: day_026_pgvector_search/support
def embed_text(c: DocChunk) -> str:
    return f"{c.header}\n\n{c.text}" if c.header else c.text
```

The third block embeds text and scores retrieval. `fake_embed()` is a free, offline stand-in (a hashed bag of words) so you can test the plumbing without a key, the same trick as Day 19's mocks. It's fine for plumbing and useless for measuring quality.

```python
# script_id: day_026_pgvector_search/support
EMBED_PRICE_PER_1M = {"text-embedding-3-small": 0.02, "text-embedding-3-large": 0.13}  # USD, as of 2026-11, verify


@dataclass
class CostTracker:
    tokens: int = 0
    total_usd: float = 0.0

    def record(self, model: str, tokens: int) -> None:
        self.tokens += tokens
        self.total_usd += tokens * EMBED_PRICE_PER_1M.get(model, 0.0) / 1_000_000


TRACKER = CostTracker()
_client = None


def embed(texts: Sequence[str], *, model: str = EMBED_MODEL, batch_size: int = 256) -> np.ndarray:
    """(n, d) float32 rows in input order. OpenAI embeddings come back unit-length."""
    global _client
    if _client is None:
        from openai import OpenAI  # lazy, so offline demos never need a key
        _client = OpenAI()
    rows: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        resp = _client.embeddings.create(model=model, input=list(texts[i:i + batch_size]))
        TRACKER.record(model, resp.usage.prompt_tokens)
        rows += [d.embedding for d in sorted(resp.data, key=lambda d: d.index)]
    return np.asarray(rows, dtype=np.float32)


def fake_embed(texts: Sequence[str], dim: int = EMBED_DIM) -> np.ndarray:
    out = np.zeros((len(texts), dim), dtype=np.float32)
    for row, text in enumerate(texts):
        for word in re.findall(r"[a-z0-9_]+", text.lower()):
            out[row, int(hashlib.md5(word.encode()).hexdigest(), 16) % dim] += 1.0
    norms = np.linalg.norm(out, axis=1, keepdims=True)
    return out / np.where(norms == 0, 1, norms)  # unit length, like real embeddings
```

```python
# script_id: day_026_pgvector_search/support
@dataclass
class RetrievalCase:
    id: str
    query: str
    relevant_doc_ids: list[str]
    kind: str


def load_retrieval_cases(split: str = "dev") -> list[RetrievalCase]:
    """Day 23's deterministic split: alternate cases by id within each kind."""
    lines = (DATA_DIR / "eval" / "retrieval_queries.jsonl").read_text(encoding="utf-8").splitlines()
    by_kind: dict[str, list[RetrievalCase]] = {}
    for case in sorted((RetrievalCase(**json.loads(l)) for l in lines if l.strip()), key=lambda c: c.id):
        by_kind.setdefault(case.kind, []).append(case)
    keep = 0 if split == "dev" else 1
    return [c for g in by_kind.values() for i, c in enumerate(g) if split == "all" or i % 2 == keep]


def ranked_doc_ids(chunks: Sequence[DocChunk]) -> list[str]:
    return list(dict.fromkeys(c.doc_id for c in chunks))  # dedupe, keep rank order


def hit_rate(cases: Sequence[RetrievalCase], search_fn: Callable[[str, int], list[str]],
             k: int = 5) -> dict[str, float]:
    results: dict[str, list[bool]] = {}
    for case in cases:
        hit = bool(set(search_fn(case.query, k)[:k]) & set(case.relevant_doc_ids))
        for key in ("overall", case.kind):
            results.setdefault(key, []).append(hit)
    return {key: round(sum(v) / len(v), 2) for key, v in results.items()}


if __name__ == "__main__":
    docs = load_corpus()
    chunks = [c for d in docs for c in chunk(d)]
    print(f"{len(docs)} pages · {len(chunks)} chunks · {len(load_retrieval_cases())} dev cases")
```

```text
45 pages · 367 chunks · 20 dev cases
```

## The Atlas Index

Now the real thing: `atlas/index.py`. The design follows one rule: **the database is the cache.** Each chunk's id is a hash of its document id and the exact text that gets embedded. On re-ingest you ask Postgres which ids it already has, embed only the missing ones, and delete rows whose ids no longer appear. Because the id is derived from content, running the same ingest twice changes nothing. It's idempotent (running it twice gives the same result as running it once).

```mermaid
sequenceDiagram
    participant C as Caller
    participant I as Index.upsert
    participant DB as Postgres
    participant E as Embeddings API
    C->>I: chunks for some docs
    I->>I: chunk_id = sha256(doc_id + text)
    I->>DB: SELECT id WHERE doc_id = ANY(docs)
    DB-->>I: ids already stored
    I->>E: embed only ids not stored yet
    E-->>I: vectors (cost only for new text)
    I->>DB: BEGIN, INSERT ... ON CONFLICT, UPDATE positions, DELETE stale ids, COMMIT
    I-->>C: UpsertStats(inserted, unchanged, deleted, cost)
```

The first block holds the small types and `connect()`. `Index` takes an `embed_fn`, so you can swap in `fake_embed`, another provider or a local model without touching the SQL.

```python
# script_id: day_026_pgvector_search/index
# index.py: Atlas's durable vector index (atlas/index.py in the capstone).
# Install: uv add "psycopg[binary]" pgvector numpy "openai>=3.46,<4" pydantic
# Env: DATABASE_URL, OPENAI_API_KEY (for embed), ORBIT_DATA. Services: Postgres from compose.yaml
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np
import psycopg
from pgvector.psycopg import register_vector
from psycopg.types.json import Jsonb

from support import DATABASE_URL, EMBED_DIM, TRACKER, DocChunk, embed, embed_text

EmbedFn = Callable[[Sequence[str]], np.ndarray]


@dataclass(frozen=True)
class Hit:
    chunk: DocChunk
    score: float  # 1 - cosine distance: higher is better


@dataclass
class UpsertStats:
    inserted: int = 0
    unchanged: int = 0
    deleted: int = 0
    cost_usd: float = 0.0

    def __str__(self) -> str:
        return f"{self.inserted} inserted · {self.unchanged} unchanged · {self.deleted} deleted · ${self.cost_usd:.5f}"


def chunk_id(doc_id: str, text: str) -> str:
    """Same doc + same embedded text -> same id, like an ETag."""
    return hashlib.sha256(f"{doc_id}\n{text}".encode()).hexdigest()[:16]
```

`connect()` is the one place that enforces the order the Break It section taught: create the extension first, then register the type.

```python
# script_id: day_026_pgvector_search/index
def connect(url: str = DATABASE_URL) -> psycopg.Connection:
    conn = psycopg.connect(url, autocommit=True)
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")  # must exist before register_vector
    register_vector(conn)
    conn.execute("SET hnsw.iterative_scan = relaxed_order")  # pgvector 0.8+: see "ANN Indexes and Tuning"
    return conn
```

The schema stores the chunk fields as plain columns so you can filter on them, and keeps the rest in a `jsonb` column. Table names can't be bound as `%s` parameters, so the constructor validates the name before it goes into any SQL string.

```python
# script_id: day_026_pgvector_search/index
SCHEMA = [
    """CREATE TABLE IF NOT EXISTS {t} (
         id text PRIMARY KEY, doc_id text NOT NULL, position int NOT NULL,
         section text NOT NULL, applies_to text NOT NULL, header text NOT NULL, body text NOT NULL,
         metadata jsonb NOT NULL DEFAULT '{{}}', embedding vector({dim}) NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS {t}_doc_id ON {t} (doc_id)",
]
HNSW = "CREATE INDEX IF NOT EXISTS {t}_hnsw ON {t} USING hnsw (embedding vector_cosine_ops)"
UPSERT = """INSERT INTO {t} (id, doc_id, position, section, applies_to, header, body, metadata, embedding)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (id) DO UPDATE SET position = EXCLUDED.position, metadata = EXCLUDED.metadata,
                                   embedding = EXCLUDED.embedding"""
REFRESH = "UPDATE {t} SET position = %s, section = %s, applies_to = %s WHERE id = %s"


class Index:
    """Durable chunk store + vector search on Postgres/pgvector."""

    def __init__(self, conn: psycopg.Connection, *, table: str = "chunks", dim: int = EMBED_DIM,
                 embed_fn: EmbedFn = embed) -> None:
        if not table.isidentifier():
            raise ValueError(f"bad table name: {table!r}")
        self.conn, self.table, self.dim, self.embed_fn = conn, table, dim, embed_fn

    def create(self, hnsw: bool = True) -> None:
        for stmt in SCHEMA + ([HNSW] if hnsw else []):
            self.conn.execute(stmt.format(t=self.table, dim=self.dim))

    def count(self) -> int:
        return self.conn.execute(f"SELECT count(*) FROM {self.table}").fetchone()[0]
```

`upsert()` is the heart of it. Every write happens in one transaction, so a crash halfway leaves the old version intact. Unchanged chunks get a cheap `UPDATE` because their position can shift when you edit text above them.

```python
# script_id: day_026_pgvector_search/index
    def upsert(self, chunks: Sequence[DocChunk]) -> UpsertStats:
        keyed = {chunk_id(c.doc_id, embed_text(c)): c for c in chunks}
        doc_ids = sorted({c.doc_id for c in chunks})
        existing = {row[0] for row in self.conn.execute(
            f"SELECT id FROM {self.table} WHERE doc_id = ANY(%s)", (doc_ids,))}
        new = [cid for cid in keyed if cid not in existing]
        kept = [cid for cid in keyed if cid in existing]
        stale = sorted(existing - keyed.keys())  # rows of these docs that the new version no longer has
        before = TRACKER.total_usd
        vectors = self.embed_fn([embed_text(keyed[cid]) for cid in new]) if new else []
        with self.conn.transaction(), self.conn.cursor() as cur:
            if new:
                cur.executemany(UPSERT.format(t=self.table), [
                    (cid, c.doc_id, c.position, c.section, c.applies_to, c.header, c.text, Jsonb(c.metadata), vec)
                    for cid, vec in zip(new, vectors) for c in [keyed[cid]]])
            if kept:
                cur.executemany(REFRESH.format(t=self.table), [
                    (keyed[cid].position, keyed[cid].section, keyed[cid].applies_to, cid) for cid in kept])
            if stale:
                cur.execute(f"DELETE FROM {self.table} WHERE id = ANY(%s)", (stale,))
        return UpsertStats(len(new), len(kept), len(stale), TRACKER.total_usd - before)

    def delete(self, doc_id: str) -> int:
        return self.conn.execute(f"DELETE FROM {self.table} WHERE doc_id = %s", (doc_id,)).rowcount
```

`search()` embeds the query, applies an optional filter, and orders by cosine distance. Today the filter handles equality or "any of" on three known columns. [Day 27](../../Phase_3_RAG/Day_027_hybrid_search/hybrid_search.md) generalises it into `where_clause()` and adds access control.

```python
# script_id: day_026_pgvector_search/index
    def search(self, query: str, k: int = 5, *,
               filters: dict[str, str | list[str]] | None = None) -> list[Hit]:
        where, params = _where(filters)
        rows = self.conn.execute(
            f"""SELECT id, doc_id, position, section, applies_to, header, body, metadata,
                       embedding <=> %(q)s AS distance
                FROM {self.table} {where} ORDER BY embedding <=> %(q)s LIMIT %(k)s""",
            {"q": self.embed_fn([query])[0], "k": k, **params}).fetchall()
        hits = [Hit(DocChunk(id=r[0], doc_id=r[1], position=r[2], section=r[3], applies_to=r[4],
                             header=r[5], text=r[6], metadata=r[7]), 1.0 - r[8]) for r in rows]
        return sorted(hits, key=lambda h: h.score, reverse=True)  # iterative scans may return near-sorted rows


FILTERABLE = ("doc_id", "section", "applies_to")


def _where(filters: dict[str, str | list[str]] | None) -> tuple[str, dict]:
    clauses, params = [], {}
    for i, (col, value) in enumerate((filters or {}).items()):
        if col not in FILTERABLE:  # column names go into SQL text, so allowlist them
            raise ValueError(f"cannot filter on {col!r}")
        params[f"f{i}"] = [value] if isinstance(value, str) else list(value)
        clauses.append(f"{col} = ANY(%(f{i})s)")
    return ("WHERE " + " AND ".join(clauses)) if clauses else "", params


if __name__ == "__main__":
    import support  # module import keeps the function support.chunk apart from the field Hit.chunk

    index = Index(connect())
    index.create()
    print(index.upsert([c for doc in support.load_corpus() for c in support.chunk(doc)]), f"· {index.count()} rows")
    for hit in index.search("why does my job run twice?", k=3, filters={"applies_to": ["3.x", "all"]}):
        print(f"{hit.score:.3f}  {hit.chunk.doc_id:28} {hit.chunk.header[:45]}")
    search_docs = lambda q, k: support.ranked_doc_ids([h.chunk for h in index.search(q, k=4 * k)])
    print("hit@5", support.hit_rate(support.load_retrieval_cases("dev"), search_docs))
```

Run it twice. The first run prints this (your numbers will differ):

```text
367 inserted · 0 unchanged · 0 deleted · $0.00131 · 367 rows
0.684  troubleshooting-duplicates   Troubleshooting: jobs running twice > Cause 1
0.641  leases-and-heartbeats        Leases and heartbeats > Why duplicate executi
0.612  idempotency                  Idempotency > What happens on delivery
hit@5 {'overall': 0.9, 'exact_term': 0.75, 'semantic': 1.0, 'multi_hop': 1.0}
```

The second run starts with this line (the search lines repeat):

```text
0 inserted · 367 unchanged · 0 deleted · $0.00000 · 367 rows
```

The second run costs nothing: every id was already stored. The `hit@5` figure (the share of dev queries whose correct page is in the top 5, from [Day 23](../../Phase_3_RAG/Day_023_embeddings/embeddings.md)) should match Day 25's numpy search. Postgres uses the HNSW index even at 367 rows, but at this size it's near-exact (99.75% of the exact top 20 in a test run). A mismatch means a plumbing bug (wrong model, wrong dimensions, a lost header), not "the database is worse".

## No Docker? The Same Index in Memory

`MemoryIndex` has the same methods with numpy underneath. Use it on machines without Docker, in unit tests, and later for the public demo in Capstone R2. Because both classes share method names and return types, code that calls `.upsert()` and `.search()` doesn't care which one it holds.

```python
# script_id: day_026_pgvector_search/memory_index
# memory_index.py: same interface as Index, in RAM. No Postgres; runs offline with fake_embed.
# Install: uv add numpy pydantic "psycopg[binary]" pgvector (index.py imports them). Env: ORBIT_DATA
from __future__ import annotations

from typing import Sequence

import numpy as np

from index import EmbedFn, Hit, UpsertStats, chunk_id
from support import EMBED_DIM, TRACKER, DocChunk, embed, embed_text


class MemoryIndex:
    def __init__(self, *, dim: int = EMBED_DIM, embed_fn: EmbedFn = embed) -> None:
        self.dim, self.embed_fn = dim, embed_fn
        self.rows: dict[str, tuple[DocChunk, np.ndarray]] = {}

    def create(self, hnsw: bool = True) -> None:
        """Nothing to create; kept so callers can treat both indexes the same way."""

    def count(self) -> int:
        return len(self.rows)

    def upsert(self, chunks: Sequence[DocChunk]) -> UpsertStats:
        keyed = {chunk_id(c.doc_id, embed_text(c)): c for c in chunks}
        doc_ids = {c.doc_id for c in chunks}
        existing = {cid for cid, (c, _) in self.rows.items() if c.doc_id in doc_ids}
        new = [cid for cid in keyed if cid not in existing]
        before = TRACKER.total_usd
        vectors = self.embed_fn([embed_text(keyed[cid]) for cid in new]) if new else []
        for cid, vec in zip(new, vectors):
            self.rows[cid] = (keyed[cid].model_copy(update={"id": cid}), np.asarray(vec))
        for cid in existing & keyed.keys():  # refresh position/metadata, keep the vector
            self.rows[cid] = (keyed[cid].model_copy(update={"id": cid}), self.rows[cid][1])
        stale = existing - keyed.keys()
        for cid in stale:
            del self.rows[cid]
        return UpsertStats(len(new), len(keyed) - len(new), len(stale), TRACKER.total_usd - before)
```

```python
# script_id: day_026_pgvector_search/memory_index
    def delete(self, doc_id: str) -> int:
        gone = [cid for cid, (c, _) in self.rows.items() if c.doc_id == doc_id]
        for cid in gone:
            del self.rows[cid]
        return len(gone)

    def search(self, query: str, k: int = 5, *,
               filters: dict[str, str | list[str]] | None = None) -> list[Hit]:
        allowed = {col: {v} if isinstance(v, str) else set(v) for col, v in (filters or {}).items()}
        items = [(c, v) for c, v in self.rows.values()
                 if all(getattr(c, col) in vals for col, vals in allowed.items())]
        if not items:
            return []
        sims = np.stack([v for _, v in items]) @ self.embed_fn([query])[0]  # unit vectors: dot = cosine
        return [Hit(items[i][0], float(sims[i])) for i in np.argsort(-sims)[:k]]


if __name__ == "__main__":
    from support import chunk, fake_embed, hit_rate, load_corpus, load_retrieval_cases, ranked_doc_ids

    index = MemoryIndex(embed_fn=fake_embed)  # swap in embed for real numbers
    chunks = [c for doc in load_corpus() for c in chunk(doc)]
    print(index.upsert(chunks))
    print(index.upsert(chunks))  # idempotent: nothing new to embed
    for hit in index.search("ORB-1301 RetryExhausted", k=3, filters={"applies_to": ["3.x", "all"]}):
        print(f"{hit.score:.3f}  {hit.chunk.doc_id}")
    search_docs = lambda q, k: ranked_doc_ids([h.chunk for h in index.search(q, k=4 * k)])
    print("hit@5 (fake_embed)", hit_rate(load_retrieval_cases("dev"), search_docs))
```

```text
367 inserted · 0 unchanged · 0 deleted · $0.00000
0 inserted · 367 unchanged · 0 deleted · $0.00000
0.299  troubleshooting-broker
0.239  dead-letter-queue
0.233  migrating-2-to-3
hit@5 (fake_embed) {'overall': 1.0, 'exact_term': 1.0, 'semantic': 1.0, 'multi_hop': 1.0}
```

This output is real and offline. `ORB-1301 RetryExhausted` is defined in `error-codes` and explained in `retries-and-backoff`, yet word hashing ranks neither in the top 3, so don't trust `fake_embed` for quality. It still scores 1.0 at hit@5 because 20 dev queries over 45 pages is a forgiving test. With `embed`, `MemoryIndex` and `Index` should return the same hit@5.

## Re-ingest Without Paying Twice

Docs change. Here you copy the Orbit pages to a scratch folder, edit one sentence in `retries-and-backoff.md`, and re-ingest. Set `ATLAS_INDEX=memory` to run it without Postgres.

```python
# script_id: day_026_pgvector_search/reingest
# Edit one page, re-ingest, and watch only the changed chunk get re-embedded. Then restore it.
# Env: ATLAS_INDEX=memory (no Postgres) or DATABASE_URL; OPENAI_API_KEY; ORBIT_DATA
import os
import shutil
import tempfile
from pathlib import Path

from index import Index, connect
from memory_index import MemoryIndex
from support import DATA_DIR, chunk, load_corpus


def build_index() -> Index | MemoryIndex:
    if os.environ.get("ATLAS_INDEX") == "memory":
        return MemoryIndex()
    index = Index(connect())
    index.create()
    return index


def ingest(index: Index | MemoryIndex, docs_dir: Path, label: str) -> None:
    print(f"{label:9}", index.upsert([c for doc in load_corpus(docs_dir) for c in chunk(doc)]))


with tempfile.TemporaryDirectory() as tmp:
    docs = Path(tmp) / "docs"
    shutil.copytree(DATA_DIR / "docs", docs)
    index = build_index()
    ingest(index, docs, "baseline")
    page = docs / "retries-and-backoff.md"
    original = page.read_text(encoding="utf-8")
    edited = original.replace("These are also the built-in defaults", "These match the built-in defaults", 1)
    assert edited != original, "sentence not found; pick another one to edit"
    page.write_text(edited, encoding="utf-8")
    ingest(index, docs, "edited")
    page.write_text(original, encoding="utf-8")
    ingest(index, docs, "restored")
```

```text
baseline  0 inserted · 367 unchanged · 0 deleted · $0.00000
edited    1 inserted · 366 unchanged · 1 deleted · $0.00000
restored  1 inserted · 366 unchanged · 1 deleted · $0.00000
```

One sentence changed, so one chunk got a new id: one embed (~120 tokens, under $0.00001), one stale row deleted. (With `ATLAS_INDEX=memory` the baseline shows `367 inserted`, because RAM starts empty.) Teams re-ingest folders on a schedule; this makes that cheap. Pages deleted from disk are a separate case, handled in Exercise 2.

## ANN Indexes and Tuning

Without an index, Postgres compares the query with every row. For Atlas's 367 chunks that takes well under a millisecond, and it's exact. Past roughly 100k rows the scan starts to hurt, and you add an ANN index. pgvector has two:

| | HNSW (default choice) | IVFFlat |
|---|---|---|
| How it finds neighbours | walks a graph of "near" links | searches only the closest few clusters |
| Build | slower, more memory | faster, less memory |
| Query speed / recall | better | good, once you tune `probes` |
| Empty table | can be built empty; grows with inserts | build **after** loading data (clusters come from existing rows) |
| Main query knob | `hnsw.ef_search` (default 40) | `ivfflat.probes` (default 1; start near `sqrt(lists)`) |
| Build knobs | `m = 16`, `ef_construction = 64` (defaults) | `lists`: start at `rows / 1000` up to 1M rows |

**Recall** here means: of the true top 10 (from an exact scan), what fraction did the index return? You can't eyeball it, so measure it. Atlas's table is too small for an index to matter, so this benchmark uses 50,000 synthetic clustered vectors and compares each setting with numpy's exact answer.

```python
# script_id: day_026_pgvector_search/ann_bench
# Synthetic ANN benchmark: recall@10 vs exact numpy search, ms/query, and the filtered-query gotcha.
# ~1 minute on a laptop. Synthetic data, so your numbers will differ.
# Install: uv add "psycopg[binary]" pgvector numpy · Env: DATABASE_URL · Services: Postgres (compose.yaml)
import os
import time

import numpy as np
import psycopg
from pgvector.psycopg import register_vector

N, DIM, K, N_QUERIES = 50_000, 128, 10, 50
rng = np.random.default_rng(0)
centers = rng.normal(size=(1000, DIM))
X = centers[rng.integers(0, 1000, N)] + 0.3 * rng.normal(size=(N, DIM))  # clustered, like real embeddings
X = (X / np.linalg.norm(X, axis=1, keepdims=True)).astype(np.float32)
Q = X[rng.choice(N, N_QUERIES, replace=False)] + 0.1 * rng.normal(size=(N_QUERIES, DIM))
Q = (Q / np.linalg.norm(Q, axis=1, keepdims=True)).astype(np.float32)
tags = rng.integers(0, 10, N)  # each tag value matches ~10% of rows
tag3 = np.flatnonzero(tags == 3)
truth = [set(np.argsort(-(X @ q))[:K].tolist()) for q in Q]  # exact top-10 by cosine
truth_tag3 = [set(tag3[np.argsort(-(X[tag3] @ q))[:K]].tolist()) for q in Q]

conn = psycopg.connect(os.environ.get("DATABASE_URL", "postgresql://atlas:atlas@localhost:5432/atlas"),
                       autocommit=True)
conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
register_vector(conn)
conn.execute("DROP TABLE IF EXISTS bench")
conn.execute(f"CREATE TABLE bench (id int PRIMARY KEY, tag int NOT NULL, embedding vector({DIM}) NOT NULL)")
with conn.transaction(), conn.cursor() as cur:  # one commit for all rows, not 50,000
    cur.executemany("INSERT INTO bench VALUES (%s, %s, %s)", [(i, int(tags[i]), X[i]) for i in range(N)])
```

```python
# script_id: day_026_pgvector_search/ann_bench
TOP10 = "SELECT id FROM bench ORDER BY embedding <=> %s LIMIT 10"
TOP10_TAG3 = "SELECT id FROM bench WHERE tag = 3 ORDER BY embedding <=> %s LIMIT 10"


def run(label: str, expected: list[set[int]], sql: str = TOP10) -> None:
    start, recalls, counts = time.perf_counter(), [], []
    for q, want in zip(Q, expected):
        got = {row[0] for row in conn.execute(sql, (q,))}
        recalls.append(len(want & got) / K)
        counts.append(len(got))
    ms = (time.perf_counter() - start) * 1000 / len(Q)
    print(f"{label:30} recall@10={np.mean(recalls):.2f}  rows={np.mean(counts):4.1f}  {ms:6.2f} ms/query")


run("exact scan (no index)", truth)
conn.execute("CREATE INDEX bench_hnsw ON bench USING hnsw (embedding vector_cosine_ops)")
for ef in (10, 40, 100):
    conn.execute(f"SET hnsw.ef_search = {ef}")  # SET can't take %s parameters; ef is our own int
    run(f"hnsw ef_search={ef}", truth)
conn.execute("SET hnsw.ef_search = 40")
conn.execute("SET enable_seqscan = off")  # force the index so the filter gotcha shows on every machine
run("hnsw + WHERE tag = 3", truth_tag3, TOP10_TAG3)
conn.execute("SET hnsw.iterative_scan = relaxed_order")  # pgvector 0.8+
run("hnsw + WHERE + iterative scan", truth_tag3, TOP10_TAG3)
conn.execute("RESET ALL")
conn.execute("DROP INDEX bench_hnsw")
conn.execute("CREATE INDEX bench_ivf ON bench USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50)")
for probes in (1, 7, 20):
    conn.execute(f"SET ivfflat.probes = {probes}")
    run(f"ivfflat lists=50 probes={probes}", truth)
conn.close()
```

```text
exact scan (no index)          recall@10=1.00  rows=10.0    6.85 ms/query
hnsw ef_search=10              recall@10=0.54  rows=10.0    0.23 ms/query
hnsw ef_search=40              recall@10=0.70  rows=10.0    0.85 ms/query
hnsw ef_search=100             recall@10=0.88  rows=10.0    0.82 ms/query
hnsw + WHERE tag = 3           recall@10=0.32  rows= 3.9    0.29 ms/query
ivfflat lists=50 probes=1      recall@10=0.62  rows=10.0    0.22 ms/query
ivfflat lists=50 probes=7      recall@10=1.00  rows=10.0    1.14 ms/query
ivfflat lists=50 probes=20     recall@10=1.00  rows=10.0    3.22 ms/query
```

This run used pgvector 0.6.2, which predates iterative scans. On the compose image's 0.8.7 you also get a `hnsw + WHERE + iterative scan` line: expect `rows=10.0` at a higher ms/query, and compare its recall yourself. Reruns shift recall a few points. Tightly clustered synthetic data is a stress test for HNSW; the point is the shape of the trade-off, so rerun this on your own vectors before choosing settings.

Read it top to bottom:

- **The knob is a dial between speed and recall.** Raising `ef_search` or `probes` buys recall with latency. Pick the lowest setting that meets your eval, and re-check as data grows.
- **Filters apply after the ANN scan.** HNSW gathers about `ef_search` = 40 candidates, then `WHERE tag = 3` keeps only the ~10% that match: about 4 rows instead of 10. No error, only fewer results. `hnsw.iterative_scan = relaxed_order` (pgvector 0.8+) tells the index to keep scanning until the `LIMIT` is filled. With `relaxed_order`, rows can come back slightly out of order, which is why `Index.search()` re-sorts by score. That's also why `connect()` turns it on.
- **IVFFlat at `probes = 1` is fast and poor.** Searching one cluster of 50 misses neighbours that sit in the next cluster over. At `probes = 7` (about `sqrt(50)`) it recovers, and it beats HNSW on this data. That's why you measure instead of trusting the default-choice column.

Plain `SET` lasts for the session. `SET LOCAL` inside a transaction resets at commit, the safe way to tune one query on a pooled connection.

```mermaid
flowchart TD
    Start["How many rows?"] -->|"under ~100k (rough)"| Exact["No ANN index: exact scan"]
    Start -->|"more"| Static{"Data mostly static, memory tight?"}
    Static -->|"no"| H["HNSW, vector_cosine_ops"]
    Static -->|"yes"| I["IVFFlat, built after loading"]
    H --> Tune["Tune ef_search against exact-scan recall"]
    I --> TuneI["Tune probes against exact-scan recall"]
    Tune --> F{"Queries filter with WHERE?"}
    TuneI --> F
    F -->|"yes"| It["iterative_scan = relaxed_order"]
    F -->|"no"| Done["Re-measure as data grows"]
    It --> Done
```

## Trade-offs: Do You Need a Vector Database?

For most teams the first answer is "use the Postgres you have". Move off it when a specific limit bites, not because a dedicated product exists.

| Option | Ops burden | Filters and joins | Keyword + vector | Scale | Cost model |
|---|---|---|---|---|---|
| **pgvector** (today) | your existing Postgres: backups, roles, monitoring already exist | full SQL: `WHERE`, `JOIN`, transactions | full-text + vectors fused in SQL ([Day 27](../../Phase_3_RAG/Day_027_hybrid_search/hybrid_search.md)) | one Postgres node; measure recall and latency as rows grow | your database bill |
| **Chroma** (local, embedded) | none: a library writing to a folder | metadata `where` filters; no joins | vectors first; keyword search is limited | one machine | free |
| **Managed vector DB** | low: the vendor runs it | vendor filter syntax; data lives apart from your app tables | many offer it built in | built to scale out | per-vector storage and queries (⚠ verify with the vendor) |
| **Hosted `file_search`** ([Day 32](../../Phase_3_RAG/Day_032_long_context_vs_rag/long_context_vs_rag.md)) | lowest: upload files, done | attribute filters only | built in (hybrid ranking options) | provider-managed | per tool call + storage per GB-day (as of 2026-11, [verify](https://developers.openai.com/api/docs/pricing)) |

Rule of thumb: start on pgvector if you already run Postgres or need joins; Chroma for a laptop prototype; a managed vector DB when vector traffic dwarfs everything else your database does; `file_search` for zero infrastructure and less control.

### In production

- **Register the type on every connection.** With a pool, pass `configure=register_vector` so each new connection gets it.
- **Back it up like any table.** Your index is now data: include it in backups, and re-embedding from source docs is your disaster-recovery plan.
- **Load first, index second.** Bulk-load rows, then build the HNSW or IVFFlat index; building IVFFlat on an empty table gives bad clusters.
- **Mind the dimension limit.** Indexes on `vector` support up to 2,000 dimensions. For 3072-d `text-embedding-3-large`, use `halfvec(3072)` (up to 4,000) or request `dimensions=1536`.
- **Plan re-embedding.** A new embedding model means new vectors for every row, in a new column or table, swapped in after an eval. [Day 88](../../Phase_9_Production/Day_088_operating_ai_systems/operating_ai_systems.md) covers the migration.

## Go Deeper (optional)

<details><summary>Go deeper: why cosine, L2 and inner product agree on unit vectors</summary>

**In words:** if every vector has length 1, "pointing the same way" and "being close together" are the same thing, so all three operators produce the same order.

**Toy numbers:** take `q = [1, 0]` and `b = [0.6, 0.8]`. Both have length 1. Their dot product is 0.6, which is also the cosine. The straight-line distance is `sqrt((1 − 0.6)² + (0 − 0.8)²) = sqrt(0.16 + 0.64) = sqrt(0.8) ≈ 0.894`. Now check `2 − 2 × 0.6 = 0.8`, which is the squared distance.

**Formula:** for unit vectors, `‖q − b‖² = ‖q‖² + ‖b‖² − 2 q·b = 2 − 2 cos(q, b)`. Squared L2 distance is a decreasing function of cosine, and `<#>` returns `−q·b = −cos`. All three sort rows identically.

**Why you still pick one:** each index is built for one operator. An index built with `vector_l2_ops` does nothing for a query ordered by `<=>`. Choose one operator per column, use the matching opclass everywhere, and confirm with `EXPLAIN` (Exercise 3). If you ever truncate vectors yourself instead of using `dimensions=`, re-normalise them, or this equivalence breaks.

</details>

<details><summary>Go deeper: filtered search beyond iterative scans</summary>

Iterative scans fix "too few rows", but each extra pass costs time. When one filter value dominates your traffic, two Postgres features help more.

**Partial index:** an index over only the rows that match a condition. Queries with the same `WHERE` can use it, and every candidate already passes the filter.

```sql
CREATE INDEX chunks_hnsw_2x ON chunks USING hnsw (embedding vector_cosine_ops)
  WHERE applies_to = '2.x';
```

**Partitioning:** split the table by a column (for example per tenant, see [Day 83](../../Phase_9_Production/Day_083_auth_multitenancy_quotas/auth_multitenancy_quotas.md)), each partition with its own index. Good for many tenants of similar size.

**Re-sorting relaxed results in SQL:** if you'd rather not re-sort in Python, wrap the query and order again outside. The `MATERIALIZED` keyword stops Postgres from folding the inner query into the outer one:

```sql
WITH nearest AS MATERIALIZED (
  SELECT id, embedding <=> %(q)s AS distance FROM chunks
  WHERE applies_to = ANY(%(versions)s) ORDER BY distance LIMIT 20)
SELECT * FROM nearest ORDER BY distance LIMIT 5;
```

pgvector also offers `hnsw.iterative_scan = strict_order` (exact order, slower) and limits on how far an iterative scan goes. On pgvector older than 0.8 (common on managed Postgres), `SET hnsw.iterative_scan` fails with `invalid configuration parameter name "hnsw.iterative_scan"`, so `connect()` needs that line removed there; check `SELECT extversion FROM pg_extension WHERE extname = 'vector'`. Check the [pgvector README](https://github.com/pgvector/pgvector) for the current settings and defaults before relying on them (⚠ verify for your version).

</details>

<details><summary>Go deeper: the connection, async and bulk-load details teams hit next</summary>

- **Async code** (required from Day 22 onward in services) uses `psycopg.AsyncConnection` and `await register_vector_async(conn)` from `pgvector.psycopg`. Everything else in `Index` maps one-to-one onto `await conn.execute(...)`.
- **Pools:** install `psycopg-pool` and create `ConnectionPool(DATABASE_URL, configure=register_vector)`. The `configure` callback runs once per new physical connection. Check the psycopg pool docs for how `configure` interacts with transactions on your version (⚠ verify).
- **Reading vectors back:** `SELECT embedding` returns a `pgvector.Vector` (since pgvector-python 0.5). Call `.to_numpy()` or `.to_list()`. NumPy is no longer a pgvector dependency, so list it in your own project.
- **Metadata-only edits:** `chunk_id()` hashes the doc id and the embedded text. If a page's front matter changes but its text doesn't, `upsert()` keeps the vector and refreshes `section` and `applies_to` through `REFRESH`. Any field you add later and filter on needs the same treatment.
- **Concurrent ingests:** `ON CONFLICT (id) DO UPDATE` makes two workers inserting the same chunk safe: the second write updates instead of failing. Two workers ingesting *different versions* of one page can still race on the stale-row delete. Teams serialise ingest per document (one queue, or `SELECT … FOR UPDATE` on a documents table).
- **Storage maths:** a `vector(1536)` stores 4 bytes per dimension, about 6 KB per row before the index; `halfvec` halves it. A million chunks is roughly 6 GB of vectors plus the HNSW graph, so watch memory before you watch latency.

</details>

## Common Pitfalls

- **`psycopg.ProgrammingError: vector type not found in the database`.** You called `register_vector` before the extension existed in that database. Run `CREATE EXTENSION IF NOT EXISTS vector` first, as `connect()` does.
- **`operator does not exist: vector <=> double precision[]`.** You passed a Python list. Pass an `np.ndarray` or `pgvector.Vector`, or cast with `%s::vector`.
- **The index exists but queries stay slow.** The opclass doesn't match the operator (a `vector_l2_ops` index with an `<=>` query), so the planner ignores the index without any error. Run `EXPLAIN` and look for `Index Scan using …_hnsw`.
- **`column cannot have more than 2000 dimensions for hnsw index`.** You tried to index 3072-d `text-embedding-3-large` vectors. Use `halfvec(3072)` with `halfvec_cosine_ops`, or request `dimensions=1536`.
- **Data gone after `docker compose down` and `up`.** On Postgres 18 images, a volume mounted at `/var/lib/postgresql/data` misses the real data directory. Mount `/var/lib/postgresql`, as the compose file does.
- **`AttributeError: 'Vector' object has no attribute 'shape'`** (or similar) on selected embeddings. Since pgvector-python 0.5, reads return `pgvector.Vector`, not numpy. Call `.to_numpy()`.

> **Where we stop:** we use HNSW and IVFFlat as tuned black boxes and skip how the graph and cluster structures work inside; the [pgvector README](https://github.com/pgvector/pgvector) links the papers if you're curious.

## Key Takeaways

- A day-25-style in-memory search re-embeds everything and forgets on restart; a table with a `vector(n)` column fixes both and adds `WHERE` and transactions.
- `<=>` is cosine *distance*: similarity is `1 − distance`, the index opclass must match the operator, and for unit-length embeddings all three operators rank the same.
- Content-hash ids make the database the cache: `upsert()` embeds only unseen chunks, deletes stale rows in the same transaction, and a second run reports `0 inserted`.
- ANN indexes trade recall for speed. Measure recall@k against an exact scan and tune `hnsw.ef_search` (or `ivfflat.probes`) to the lowest value your eval tolerates.
- Filters run after the ANN scan, so a selective `WHERE` returns too few rows until you enable `hnsw.iterative_scan`; stay on pgvector until a measured limit, not a feature list, pushes you elsewhere.

## Quick Reference

| API / pattern | When to use | Gotcha |
|---|---|---|
| `CREATE EXTENSION IF NOT EXISTS vector` | once per database | must run before `register_vector` |
| `register_vector(conn)` | every connection (pool: `configure=register_vector`) | async: `await register_vector_async(conn)` |
| `embedding vector(1536)` | column for `text-embedding-3-small` | width must equal model output |
| `ORDER BY embedding <=> %s LIMIT k` | cosine nearest neighbours | pass `np.ndarray`/`Vector`, not a list |
| `INSERT … ON CONFLICT (id) DO UPDATE` | idempotent writes | pair with content-hash ids |
| `USING hnsw (embedding vector_cosine_ops)` | default ANN index | opclass must match operator |
| `SET hnsw.ef_search = 100` | raise recall (default 40) | `SET LOCAL` to scope to one transaction |
| `USING ivfflat … WITH (lists = N)` + `SET ivfflat.probes` | large, mostly static data | build after loading |
| `SET hnsw.iterative_scan = relaxed_order` | filtered queries | pgvector 0.8+; re-sort results |
| `halfvec(3072)` + `halfvec_cosine_ops` | 3072-d vectors | `vector` indexes stop at 2,000 dims |

## Exercises

1. **Warm-up.** Change the search printout so each hit also shows its `section`, `applies_to` and position, then search for "how do I cap the retry delay?" with `filters={"applies_to": ["3.x", "all"]}`.

<details>
<summary>Solution</summary>

```python
# script_id: day_026_pgvector_search/solution_ex1
# Warm-up: show metadata columns next to each hit. Needs Postgres (compose.yaml) + OPENAI_API_KEY,
# and a populated `chunks` table (run index.py once).
from index import Index, connect

index = Index(connect())
for hit in index.search("how do I cap the retry delay?", k=5, filters={"applies_to": ["3.x", "all"]}):
    c = hit.chunk
    print(f"{hit.score:.3f}  [{c.section} · {c.applies_to}]  {c.doc_id}#{c.position}  {c.header[:40]}")
```

Every column you stored comes back on `hit.chunk`, so showing metadata is a print change, not a schema change.

</details>

2. **Core.** `upsert()` only cleans up pages it's given. Add `delete_missing(keep_doc_ids)` that removes rows for pages no longer on disk, plus a `sync(docs_dir)` that upserts and then deletes missing pages. Test it by deleting `faq.md` from a scratch copy of the docs.

<details>
<summary>Solution</summary>

```python
# script_id: day_026_pgvector_search/solution_ex2
# Core: full folder sync (upsert changed pages + delete pages removed from disk).
# Needs Postgres + OPENAI_API_KEY (the first run embeds; later runs are ~free).
import shutil
import tempfile
from pathlib import Path

from index import Index, UpsertStats, connect
from support import DATA_DIR, chunk, load_corpus


class SyncedIndex(Index):
    def delete_missing(self, keep_doc_ids: set[str]) -> int:
        if not keep_doc_ids:  # an empty set would wipe the table: almost always a bug upstream
            raise ValueError("keep_doc_ids is empty; refusing to delete every row")
        cur = self.conn.execute(f"DELETE FROM {self.table} WHERE NOT (doc_id = ANY(%s))",
                                (sorted(keep_doc_ids),))
        return cur.rowcount

    def sync(self, docs_dir: Path) -> UpsertStats:
        docs = load_corpus(docs_dir)
        stats = self.upsert([c for d in docs for c in chunk(d)])
        stats.deleted += self.delete_missing({d.id for d in docs})
        return stats


with tempfile.TemporaryDirectory() as tmp:
    docs = Path(tmp) / "docs"
    shutil.copytree(DATA_DIR / "docs", docs)
    index = SyncedIndex(connect())
    index.create()
    print("full  ", index.sync(docs))
    (docs / "faq.md").unlink()
    print("no faq", index.sync(docs))  # e.g. 0 inserted · 360 unchanged · 7 deleted
    shutil.copy(DATA_DIR / "docs" / "faq.md", docs / "faq.md")
    print("faq back", index.sync(docs))
```

The guard on an empty set matters: a bug that loads zero pages would otherwise delete the whole index in one statement.

</details>

3. **Core.** On the `bench` table from the benchmark, use `EXPLAIN ANALYZE` to show (a) the HNSW index serving an `<=>` query, (b) the same index ignored for an `<->` query, and (c) an exact plan with index scans disabled. Compare execution times.

<details>
<summary>Solution</summary>

```python
# script_id: day_026_pgvector_search/solution_ex3
# Core: read query plans. Needs Postgres and the `bench` table from ann_bench.
import os

import numpy as np
import psycopg
from pgvector.psycopg import register_vector

conn = psycopg.connect(os.environ.get("DATABASE_URL", "postgresql://atlas:atlas@localhost:5432/atlas"),
                       autocommit=True)
register_vector(conn)
conn.execute("DROP INDEX IF EXISTS bench_ivf")
conn.execute("CREATE INDEX IF NOT EXISTS bench_hnsw ON bench USING hnsw (embedding vector_cosine_ops)")
q = np.random.default_rng(1).normal(size=128).astype(np.float32)


def plan(label: str, sql: str) -> None:
    lines = [row[0] for row in conn.execute("EXPLAIN ANALYZE " + sql, (q,))]
    scan = next(line.strip() for line in lines if "Scan" in line)
    total = next(line for line in lines if line.startswith("Execution Time"))
    print(f"{label:24} {scan[:55]:55} {total}")


plan("cosine (opclass match)", "SELECT id FROM bench ORDER BY embedding <=> %s LIMIT 10")
plan("L2 (opclass mismatch)", "SELECT id FROM bench ORDER BY embedding <-> %s LIMIT 10")
conn.execute("SET enable_indexscan = off")
plan("cosine, index disabled", "SELECT id FROM bench ORDER BY embedding <=> %s LIMIT 10")
```

```text
cosine (opclass match)   ->  Index Scan using bench_hnsw on bench  (cost=36.60.. Execution Time: 0.371 ms
L2 (opclass mismatch)    ->  Seq Scan on bench  (cost=0.00..4197.00 rows=50000 w Execution Time: 6.243 ms
cosine, index disabled   ->  Seq Scan on bench  (cost=0.00..4197.00 rows=50000 w Execution Time: 5.112 ms
```

Only the first plan says `Index Scan using bench_hnsw`. The `<->` query falls back to a sequential scan plus sort with no warning, which is why you check plans after creating an index.

</details>

4. **Stretch (optional).** Store `text-embedding-3-large` vectors (3072-d) for five Orbit pages. First show that an HNSW index on `vector(3072)` fails, then make it work with `halfvec(3072)`.

<details>
<summary>Solution</summary>

```python
# script_id: day_026_pgvector_search/solution_ex4
# Stretch: 3072-d vectors as halfvec with an HNSW index. Needs pgvector >= 0.7 (compose has 0.8.7),
# Postgres + OPENAI_API_KEY. Cost: a fraction of a cent.
import psycopg
from pgvector import HalfVector

from index import connect
from support import chunk, embed, embed_text, load_corpus

conn = connect()  # register_vector also registers halfvec when the type exists
conn.execute("DROP TABLE IF EXISTS chunks_large")
conn.execute("CREATE TABLE chunks_large (id text PRIMARY KEY, body text, embedding vector(3072))")
try:
    conn.execute("CREATE INDEX ON chunks_large USING hnsw (embedding vector_cosine_ops)")
except psycopg.Error as exc:
    print("vector(3072):", str(exc).splitlines()[0])
conn.execute("DROP TABLE chunks_large")
conn.execute("CREATE TABLE chunks_large (id text PRIMARY KEY, body text, embedding halfvec(3072))")
conn.execute("CREATE INDEX ON chunks_large USING hnsw (embedding halfvec_cosine_ops)")

chunks = [c for d in load_corpus()[:5] for c in chunk(d)]
vectors = embed([embed_text(c) for c in chunks], model="text-embedding-3-large")
with conn.cursor() as cur:
    cur.executemany("INSERT INTO chunks_large VALUES (%s, %s, %s)",
                    [(c.id, c.text, HalfVector(v)) for c, v in zip(chunks, vectors)])
q = HalfVector(embed(["how do retries back off?"], model="text-embedding-3-large")[0])
for id_, dist in conn.execute(
        "SELECT id, embedding <=> %s AS d FROM chunks_large ORDER BY d LIMIT 3", (q,)):
    print(f"{1 - dist:.3f}  {id_}")
```

`halfvec` stores 16-bit floats: half the storage, an index limit of 4,000 dimensions, and a tiny precision loss that rarely changes rankings. Measure it with hit@k before you switch.

</details>

## References & Further Reading

- [pgvector README](https://github.com/pgvector/pgvector): the source of truth for types, operators, HNSW/IVFFlat options and iterative scans.
- [pgvector CHANGELOG](https://github.com/pgvector/pgvector/blob/master/CHANGELOG.md): why the course pins 0.8.7 (IVFFlat fixes in 0.8.6–0.8.7).
- [pgvector-python CHANGELOG](https://github.com/pgvector/pgvector-python/blob/master/CHANGELOG.md): the 0.5.0 changes (`Vector` on read, top-level imports).
- [pgvector-python hybrid search example](https://github.com/pgvector/pgvector-python/blob/master/examples/hybrid_search/rrf.py): a preview of tomorrow's keyword + vector fusion.
- [pgvector on Docker Hub](https://hub.docker.com/r/pgvector/pgvector): image tags for each Postgres major version.
- [Official Postgres image docs](https://github.com/docker-library/docs/blob/master/postgres/content.md): the PG 18 data-directory and volume change.
- [OpenAI embeddings guide](https://developers.openai.com/api/docs/guides/embeddings): dimensions, `dimensions=` truncation and input limits.

## What's Next

Pure vector search is weak on exact strings such as `ORB-1202` or `max_payload_kb`: your exact-term hit rate trails the semantic one. In [Day 27: Hybrid Search: Keywords + Vectors](../../Phase_3_RAG/Day_027_hybrid_search/hybrid_search.md) you add full-text search to the same `chunks` table, fuse the two rankings with RRF (reciprocal rank fusion: merge lists by rank position), and give every search a permission filter.
