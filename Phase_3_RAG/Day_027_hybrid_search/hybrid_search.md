# Hybrid Search: Keywords + Vectors

A maintainer pastes `ORB-1202` into Atlas, and vector search comes back with pages about payloads in general, while the line that actually defines the code sits further down the list. Embeddings blur exact tokens such as error codes, config keys and CLI flags, and those are exactly what Orbit users paste. Today you add a keyword arm, fuse the two rankings with a rule that needs no tuning, and make sure community users can never see maintainer-only issue text.

## At a Glance

- **Time:** ~2 h core (+ optional Go Deeper) · **Depth:** working
- **Prerequisites:** [Day 26: Vector Search with pgvector](../../Phase_3_RAG/Day_026_pgvector_search/pgvector_search.md), [Day 23: Embeddings & Semantic Similarity](../../Phase_3_RAG/Day_023_embeddings/embeddings.md) (hit@k), [Day 25: Chunking Strategies](../../Phase_3_RAG/Day_025_chunking/chunking.md); primer [SQL & Postgres](../../Appendix_Primers/A07_sql_postgres.md)
- **You'll build:** `hybrid_search()` with reciprocal rank fusion, in Postgres and in memory, with metadata and permission filters inside both search arms, compared against vector-only and keyword-only search on hit@5
- **Stops at:** learned sparse retrieval (aside only)
- **Fast path:** Already know Postgres full-text search? Read [Fuse Two Lists by Hand](#fuse-two-lists-by-hand), [Filters and Permissions](#filters-and-permissions) and [Hybrid Search in Postgres](#hybrid-search-in-postgres), then do Exercise 2 (≈45 min)
- **Cost:** ≈ $0.01 on `text-embedding-3-small` to embed 45 docs, 240 issues and the eval queries (prices as of 2026-11, [verify](https://developers.openai.com/api/docs/pricing)). Every keyword-only script is free.
- **New terms:** full-text search, BM25, reciprocal rank fusion (RRF), metadata filter, ACL filter

> **Coming from Software Engineering?** Hybrid search is a `LIKE`-style full-text query and an `ORDER BY similarity` query run side by side, then merged like two sorted result sets. Reciprocal rank fusion merges them by *position*, not by score, so you never have to compare a cosine similarity with a text-match score (two numbers in different units). Permission filters are row-level security (the database only returns rows the caller may see): apply them inside the query, never in the UI after the fact.

## Vectors Miss Exact Terms

On Day 23 you split the 40 retrieval queries into three kinds: `semantic` ("why did my job run twice"), `multi_hop` (needs two pages) and `exact_term` (`ORB-1101`, `heartbeat_seconds`, `X-Forwarded-Proto`). The exact-term slice was the weakest for embeddings (scored by **hit@5**: does a relevant page appear in the top 5?), and that's not a bug in your code. An embedding model turns text into a point that captures *meaning*. `ORB-1202` and `ORB-1201` mean nearly the same thing to it ("some Orbit error"), so the page that defines exactly `ORB-1202 PayloadTooLarge` has no reason to beat a page that talks about payload sizes in general.

Search that can't match pasted error codes, config keys and CLI flags literally feels broken, however good it is at paraphrases.

## Two Librarians

Picture two librarians. The first one understands what you mean: ask about "jobs that run twice" and she brings the page on duplicate execution, even though it never uses your words. The second one only matches exact words, but he's precise: ask for `ORB-1202` and he brings every page that contains that string, nothing else. Neither is enough alone. So you ask both, and you trust books that *both* of them put near the top.

There's one more rule in this library. Some shelves are staff-only, and both librarians must skip them for a visitor. If only one librarian checks the badge, the other one hands over the staff-only book anyway.

That's the whole lesson: a **keyword arm**, a **vector arm**, a **fusion rule**, and **filters applied inside both arms**.

## Fuse Two Lists by Hand

The vector arm and the keyword arm each return a ranked list. Their scores are useless for comparison: cosine similarity lives around 0.3–0.8, and Postgres text ranks are small numbers with no fixed scale. **Reciprocal rank fusion (RRF)** ignores the scores and uses only positions. Each list gives every item a vote of `1 / (k + rank)`, and you add the votes up. The constant `k = 60` comes from the original RRF paper (Cormack, Clarke and Büttcher, 2009); it flattens the gap between rank 1 and rank 2, so agreement between lists beats one list's favourite.

Try it with two four-item lists for the query `max_payload_kb`:

| Rank | Vector arm | Keyword arm |
|---|---|---|
| 1 | concepts-jobs | error-codes |
| 2 | configuration-reference | configuration-reference |
| 3 | results-backend | broker-redis |
| 4 | flows-steps-and-state | concepts-jobs |

`configuration-reference` gets `1/62 + 1/62 = 0.03226`. `concepts-jobs` gets `1/61 + 1/64 = 0.03202`. `error-codes` gets only `1/61 = 0.01639`, because one list ignored it. The page that's second in *both* lists wins, even though it tops neither.

```mermaid
flowchart TD
    V["Vector list: concepts-jobs #1, configuration-reference #2"] --> S1["vote 1/(60+rank) per list"]
    K["Keyword list: error-codes #1, configuration-reference #2, concepts-jobs #4"] --> S1
    S1 --> A["configuration-reference: 1/62 + 1/62 = 0.03226"]
    S1 --> B["concepts-jobs: 1/61 + 1/64 = 0.03202"]
    S1 --> C["error-codes: 1/61 = 0.01639"]
    A --> F["Fused order: configuration-reference, concepts-jobs, error-codes, ..."]
    B --> F
    C --> F
```

The same arithmetic as code; save it as `fusion.py`, since later files import it.

```python
# script_id: day_027_hybrid_search/fusion
# fusion.py: reciprocal rank fusion (RRF). Pure Python: no installs, no API key.
from typing import Sequence


def rrf(rankings: Sequence[Sequence[str]], k: int = 60) -> list[tuple[str, float]]:
    """Each ranking votes 1/(k + rank) for every id in it; the highest total wins."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))  # ties break by id, so runs repeat


if __name__ == "__main__":
    vector = ["concepts-jobs", "configuration-reference", "results-backend", "flows-steps-and-state"]
    keyword = ["error-codes", "configuration-reference", "broker-redis", "concepts-jobs"]
    for doc_id, score in rrf([vector, keyword]):
        print(f"{score:.5f}  {doc_id}")
```

```text
0.03226  configuration-reference
0.03202  concepts-jobs
0.01639  error-codes
0.01587  broker-redis
0.01587  results-backend
0.01562  flows-steps-and-state
```

## Name the Parts

- **Full-text search** is word-based search with stemming. Postgres stores each text as a `tsvector`: a sorted list of **lexemes** (the normalized words it indexes, so "heartbeats" becomes `heartbeat`). A query becomes a `tsquery`, and `tsv @@ query` means "this text matches".
- A **GIN index** (generalized inverted index: a map from each lexeme to the rows containing it) makes `@@` fast.
- `websearch_to_tsquery('english', text)` turns raw user text into a `tsquery` and understands quotes, `or` and `-word`. It never raises a syntax error, which makes it the safe choice for anything a user typed.
- `ts_rank_cd(tsv, query)` scores a match by how often and how close together the query words appear. It is **not BM25**: the Postgres docs say the ranking functions "do not use any global information", so a word that appears on every page counts as much as a rare error code.
- **BM25** is a classic keyword-ranking formula that *does* use corpus statistics: rare words count more, and long pages don't win by repetition. You'll write one in 30 lines of stdlib Python.
- A **metadata filter** restricts results by a column, such as `applies_to = '3.x'`. An **ACL filter** (access-control list: who may see a row) restricts results to rows the caller's groups may read. Both must **fail closed** (deny when unsure).

```mermaid
flowchart LR
    Q["Query text + caller groups"] --> W["where_clause: filters + ACL, compiled once"]
    Q -->|embed| V["Vector arm: WHERE ... ORDER BY distance LIMIT 20"]
    Q -->|websearch_to_tsquery| K["Keyword arm: WHERE tsv @@ query ... LIMIT 20"]
    W -->|same SQL| V
    W -->|same SQL| K
    V -->|ranked ids| F["RRF: sum of 1/(60 + rank)"]
    K -->|ranked ids| F
    F -->|top k| R["Hits the caller may see"]
```

The filter sits inside each arm, *before* its `LIMIT`; that placement separates a correct system from a leaky one.

## Keyword Search in SQL

Start with the smallest useful change to Day 26's `chunks` table: a generated `tsvector` column, a GIN index on it, and one ranked query. A **generated column** is computed by Postgres from other columns, so every `INSERT` and every `ON CONFLICT DO UPDATE` refreshes it, and your upsert code can't forget to.

```python
# script_id: day_027_hybrid_search/keyword_sql
# Minimal keyword search on Day 26's `chunks` table: a generated tsvector column + GIN index.
# Install: uv add "psycopg[binary]"
# Env: DATABASE_URL (default matches Day 26's compose.yaml). Needs Postgres with Day 26's table loaded.
import json
import os

import psycopg

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://atlas:atlas@localhost:5432/atlas")
conn = psycopg.connect(DATABASE_URL, autocommit=True)
conn.execute("""ALTER TABLE chunks ADD COLUMN IF NOT EXISTS tsv tsvector
                GENERATED ALWAYS AS (to_tsvector('english', text)) STORED""")
conn.execute("CREATE INDEX IF NOT EXISTS chunks_tsv_gin ON chunks USING gin (tsv)")
rows = conn.execute("""
    SELECT id, ts_rank_cd(tsv, query)::float8 AS rank
    FROM chunks, websearch_to_tsquery('english', %s) AS query
    WHERE tsv @@ query ORDER BY rank DESC, id LIMIT 3""", ("ORB-1202",)).fetchall()
for chunk_id, rank in rows:
    print(f"{rank:.3f}  {chunk_id}")
```

Expected output (⚠ verify on your Postgres):

```text
0.200  concepts-jobs#2
0.200  flows-error-handling#4
0.200  troubleshooting-memory#3
```

Each row contains the code twice, and each adjacent `orb`, `-1202` match scores 0.1 at the default weight, so the ranks tie: `ts_rank_cd` has no idea the pair is rare. The keyword arm is precise about *which* rows match and weak at *ordering* them; RRF and the vector arm break the ties.

Write the config `'english'` out: it picks the stemmer and stop words, and a generated column needs an immutable expression, so `to_tsvector(text)` fails with `ERROR: generation expression is not immutable`.

## Break It: What Postgres Actually Indexes

This block continues the script: what Postgres stores for codes and keys, then the two errors teams hit first.

```python
# script_id: day_027_hybrid_search/keyword_sql
for text in ["ORB-1202 PayloadTooLarge", "heartbeat_seconds", "orbit.toml", "X-Forwarded-Proto"]:
    lexemes = conn.execute("SELECT to_tsvector('english', %s)::text", (text,)).fetchone()[0]
    print(f"{text!r:28} -> {lexemes}")
query = conn.execute("SELECT websearch_to_tsquery('english', %s)::text", ("what does ORB-1202 mean?",))
print("websearch:", query.fetchone()[0])
try:
    conn.execute("SELECT to_tsquery('english', %s)", ("lease seconds",))
except psycopg.errors.SyntaxError as err:
    print("to_tsquery:", err)
score = conn.execute("SELECT 1.0 / (60 + 1) + 1.0 / (60 + 3)").fetchone()[0]
try:
    json.dumps({"score": score})
except TypeError as err:
    print(f"{type(score).__name__}: {err}")
print(json.dumps({"score": float(score)}))
```

Expected output (⚠ verify on your Postgres; `SELECT * FROM ts_debug('english', 'ORB-1202')` shows how the parser splits a token):

```text
'ORB-1202 PayloadTooLarge'   -> '-1202':2 'orb':1 'payloadtoolarg':3
'heartbeat_seconds'          -> 'heartbeat':1 'second':2
'orbit.toml'                 -> 'orbit.toml':1
'X-Forwarded-Proto'          -> 'forward':3 'proto':4 'x':2 'x-forwarded-proto':1
websearch: 'orb' <-> '-1202' & 'mean'
to_tsquery: syntax error in tsquery: "lease seconds"
Decimal: Object of type Decimal is not JSON serializable
{"score": 0.032266458495966696}
```

Four lessons hide in that output:

1. **Codes split.** `ORB-1202` becomes `orb` plus `-1202` (Postgres reads the tail as a signed number). It still matches, because the query splits the same way and `<->` demands the two lexemes sit next to each other.
2. **snake_case splits too**, and the parts get stemmed: `heartbeat_seconds` is stored as `heartbeat` + `second`. A dotted file name such as `orbit.toml` stays whole, and a hyphenated header is stored both whole and in parts.
3. **`to_tsquery` is for programmers.** Two bare words raise `syntax error in tsquery`. User text goes through `websearch_to_tsquery`, which never raises, but ANDs the words: a question only matches pages containing *every* content word, including "mean" (see Go Deeper).
4. **SQL arithmetic returns `Decimal`.** `1.0 / (60 + 1)` is a `numeric`, which psycopg hands you as `decimal.Decimal`, and `json.dumps` refuses it. Cast to `float8` in SQL or call `float()`.

## Before You Build: Helpers from Earlier Days

Today's code is a handful of lesson-local modules: save each block under the file name in its first comment and run everything from one folder. This first file holds compact copies of helpers from Days 15 and 23–26; if you built those days, your versions have the same names and shapes.

```python
# script_id: day_027_hybrid_search/atlas_base
# atlas_base.py: compact copies of earlier days' helpers, so today's files stay self-contained.
# built on Day 15 (issues), Day 23 (embed, hit_rate), Day 24 (Document), Day 25 (chunk), Day 26 (Hit)
# Install: uv add "openai>=3.46,<4" numpy
# Env: ORBIT_DATA (path to datasets/orbit); OPENAI_API_KEY only when something calls embed().
import json
import os
import re
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Callable, Sequence

import numpy as np
from openai import OpenAI

DATA_DIR = Path(os.environ.get("ORBIT_DATA", "datasets/orbit"))
EMBED_MODEL = os.environ.get("ATLAS_EMBED_MODEL", "text-embedding-3-small")
EMBED_DIM = 1536


@dataclass
class Document:  # Day 24's contract
    id: str
    title: str
    text: str
    source: str
    metadata: dict = field(default_factory=dict)


@dataclass
class DocChunk:  # Day 15 fields + Day 25 metadata; today metadata also carries source + allowed_groups
    id: str
    doc_id: str
    section: str
    applies_to: str
    text: str
    metadata: dict = field(default_factory=dict)


@dataclass
class Hit:  # Day 26: higher score = better
    chunk: DocChunk
    score: float
```

Loading and chunking: Day 25's Markdown strategy with a character cap, because some issues carry tens of thousands of characters of pasted logs, more than one embedding input accepts.

```python
# script_id: day_027_hybrid_search/atlas_base
def parse_front_matter(raw: str) -> tuple[dict[str, str], str]:
    """Flat `key: value` front matter only (Day 24 uses a YAML parser)."""
    meta, body = {}, raw
    if raw.startswith("---\n"):
        head, _, body = raw[4:].partition("\n---\n")
        for line in head.splitlines():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.split("#")[0].strip().strip('"')
    return meta, body


def load_docs(root: Path = DATA_DIR) -> list[Document]:
    docs = []
    for path in sorted((root / "docs").glob("*.md")):
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        docs.append(Document(meta.get("id", path.stem), meta.get("title", path.stem), body, "docs", meta))
    return docs


def load_issues(root: Path = DATA_DIR) -> list[dict]:
    """Day 15 returns `Issue` models; plain dicts keep this copy short."""
    lines = (root / "issues" / "issues.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def chunk(doc: Document, max_chars: int = 6000) -> list[DocChunk]:
    """One chunk per `## ` section, title + heading as a header, long sections cut by characters."""
    chunks: list[DocChunk] = []
    for part in (p.strip() for p in re.split(r"(?m)^(?=## )", doc.text) if p.strip()):
        heading = part.splitlines()[0].lstrip("# ")
        for start in range(0, len(part), max_chars):
            text = f"{doc.title} > {heading}\n{part[start:start + max_chars]}"
            chunks.append(DocChunk(f"{doc.id}#{len(chunks)}", doc.id, doc.metadata.get("section", ""),
                                   doc.metadata.get("applies_to", "all"), text,
                                   {**doc.metadata, "source": doc.source}))
    return chunks
```

Embedding and evaluation. The OpenAI client is created on first use, so the keyword-only scripts below run without a key.

```python
# script_id: day_027_hybrid_search/atlas_base
@cache
def _client() -> OpenAI:
    return OpenAI()  # reads OPENAI_API_KEY from the environment


def embed(texts: Sequence[str], *, model: str = EMBED_MODEL, batch_size: int = 100) -> np.ndarray:
    """Day 23's embed() without its cache: float32 (n, d), unit length, input order."""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        resp = _client().embeddings.create(model=model, input=list(texts[start:start + batch_size]))
        vectors += [item.embedding for item in resp.data]
    return np.asarray(vectors, dtype=np.float32)  # OpenAI embeddings are unit length: dot = cosine


@dataclass
class RetrievalCase:
    id: str
    query: str
    relevant_doc_ids: list[str]
    kind: str


def load_retrieval_cases(split: str = "dev") -> list[RetrievalCase]:
    """Day 23's deterministic split: every other case by id within each kind."""
    lines = (DATA_DIR / "eval" / "retrieval_queries.jsonl").read_text(encoding="utf-8").splitlines()
    cases = sorted((RetrievalCase(**json.loads(line)) for line in lines if line.strip()), key=lambda c: c.id)
    if split == "all":
        return cases
    kinds = dict.fromkeys(c.kind for c in cases)
    return [c for kind in kinds for c in [x for x in cases if x.kind == kind][(split != "dev")::2]]


def ranked_doc_ids(hits: Sequence[Hit]) -> list[str]:
    return list(dict.fromkeys(h.chunk.doc_id for h in hits))  # Day 25: dedupe, keep order


def hit_rate(cases: Sequence[RetrievalCase], search_fn: Callable[[str, int], list[str]],
             k: int = 5) -> dict[str, float]:
    results: dict[str, list[bool]] = {}
    for case in cases:
        found = bool(set(search_fn(case.query, k)[:k]) & set(case.relevant_doc_ids))
        for key in ("overall", case.kind):
            results.setdefault(key, []).append(found)
    return {key: sum(v) / len(v) for key, v in results.items()}
```

## Filters and Permissions

Atlas is about to index Orbit's 240 issues too, and reporters paste emails, hostnames and tokens into them (ten issues hold synthetic PII fixtures). So the rule is: **docs are `public`, issues are `maintainers`-only.** Every chunk carries an `allowed_groups` list, every search takes the caller's `groups`, and a row is visible when the two overlap.

Three design choices make this safe:

- **One compiler for every arm.** `where_clause()` turns `filters` and `groups` into one SQL fragment that both arms paste in, so no arm can forget the ACL.
- **Filter before ranking.** The filter sits in each arm's `WHERE`, before `LIMIT`. Filtering after fusion returns fewer than `k` results.
- **Fail closed.** The default caller is `("public",)`, never "everyone". Empty `groups` raise, a source with no ACL rule gets no groups (invisible), and unknown filter keys raise because they become SQL column names.

```python
# script_id: day_027_hybrid_search/acl
# acl.py: metadata + permission filters, defined once and used by both arms of both indexes.
# Install: nothing beyond atlas_base. Env: ORBIT_DATA.
from typing import Sequence

from atlas_base import Document, DocChunk, chunk, load_docs, load_issues

FILTER_KEYS = ("applies_to", "doc_id", "source")  # allowlist: these keys become SQL column names
Filters = dict[str, str | list[str]]  # str = equals, list = any of


def acl_for(doc: Document) -> list[str]:
    # Issues quote reporter emails, hosts and pasted tokens, so only maintainers may read them.
    # An unknown source gets no groups: invisible to everyone until someone decides (fail closed).
    return {"docs": ["public"], "issue": ["maintainers"]}.get(doc.source, [])


def issue_to_document(issue: dict) -> Document:
    comments = "\n\n".join(f"{c['author']}: {c['body']}" for c in issue.get("comments", []))
    version = issue.get("orbit_version") or ""
    meta = {"labels": ",".join(issue["labels"]), "state": issue["state"],
            "applies_to": f"{version.split('.')[0]}.x" if version else "all"}
    return Document(f"issue-{issue['id']}", issue["title"],
                    f"{issue['title']}\n\n{issue['body']}\n\n{comments}", "issue", meta)


def load_corpus(include_issues: bool = False) -> list[DocChunk]:
    docs = load_docs() + ([issue_to_document(i) for i in load_issues()] if include_issues else [])
    for doc in docs:
        doc.metadata["allowed_groups"] = acl_for(doc)  # decided at ingest, stored on every chunk
    return [c for doc in docs for c in chunk(doc)]
```

The second half compiles the rule two ways: as SQL for Postgres and as a predicate for the in-memory index. Both start from the same validation.

```python
# script_id: day_027_hybrid_search/acl
def _check(filters: Filters | None, groups: Sequence[str]) -> Filters:
    if not groups or isinstance(groups, str):
        raise ValueError("groups must be a non-empty sequence such as ('public',)")  # fail closed
    unknown = set(filters or {}) - set(FILTER_KEYS)
    if unknown:
        raise ValueError(f"unknown filter keys {sorted(unknown)}; allowed: {FILTER_KEYS}")
    return filters or {}


def where_clause(filters: Filters | None, groups: Sequence[str]) -> tuple[str, dict]:
    """SQL version: one fragment + params, pasted into BOTH arms before their LIMIT."""
    filters = _check(filters, groups)
    parts, params = ["allowed_groups && %(acl_groups)s::text[]"], {"acl_groups": list(groups)}
    for i, (key, value) in enumerate(sorted(filters.items())):
        if isinstance(value, str):
            parts.append(f"{key} = %(f{i})s")
            params[f"f{i}"] = value
        else:
            parts.append(f"{key} = ANY(%(f{i})s::text[])")
            params[f"f{i}"] = list(value)
    return " AND ".join(parts), params


def matches(chunk: DocChunk, filters: Filters | None, groups: Sequence[str]) -> bool:
    """In-memory version of the same rule, for MemoryIndex."""
    filters = _check(filters, groups)
    if not set(chunk.metadata.get("allowed_groups", [])) & set(groups):
        return False  # a row with no groups is visible to nobody
    values = {"applies_to": chunk.applies_to, "doc_id": chunk.doc_id, "source": chunk.metadata.get("source")}
    return all(values[k] == v if isinstance(v, str) else values[k] in v for k, v in filters.items())
```

`&&` is Postgres's array-overlap operator ("do these arrays share an element?"), and a GIN index on a `text[]` column supports it. Here is the table after today's migration. Days 28–34 build on this schema.

```mermaid
classDiagram
    class chunks {
        +text id
        +text doc_id
        +text section
        +text applies_to
        +text text
        +vector embedding
        +tsvector tsv
        +text source
        +text_array allowed_groups
    }
    class GIN_tsv {
        lexeme to rows
    }
    class GIN_acl {
        group to rows
    }
    chunks <.. GIN_tsv : indexes tsv
    chunks <.. GIN_acl : indexes allowed_groups
```

The last three columns are new: `tsv` is generated from `text`, `source` is `docs` or `issue`, and `allowed_groups` is a `text[]` array.

## Hybrid Search in Postgres

Now the full build: Day 26's `Index`, compacted (the `WITH` blocks below are CTEs, common table expressions: named sub-queries), plus today's migration and both arms. It needs Day 26's Postgres and an API key. The migration backfills existing rows as `public` docs; new rows default to an empty group list, which means invisible.

```python
# script_id: day_027_hybrid_search/index
# index.py: Day 26's pgvector Index (compact) + today's keyword arm, RRF and ACL filters.
# Install: uv add "psycopg[binary]" pgvector numpy "openai>=3.46,<4"
# Env: DATABASE_URL, OPENAI_API_KEY, ORBIT_DATA. Needs Postgres + pgvector (Day 26's compose.yaml).
import os
from typing import Callable, Sequence

import numpy as np
import psycopg
from pgvector.psycopg import register_vector

from acl import Filters, load_corpus, where_clause
from atlas_base import EMBED_DIM, DocChunk, Hit, embed, hit_rate, load_retrieval_cases, ranked_doc_ids

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://atlas:atlas@localhost:5432/atlas")
SCHEMA = """CREATE TABLE IF NOT EXISTS {t} (id text PRIMARY KEY, doc_id text NOT NULL, section text,
    applies_to text, text text NOT NULL, embedding vector({dim}));
CREATE INDEX IF NOT EXISTS {t}_hnsw ON {t} USING hnsw (embedding vector_cosine_ops);"""
MIGRATION = """
ALTER TABLE {t} ADD COLUMN IF NOT EXISTS tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('english', text)) STORED;
ALTER TABLE {t} ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT 'docs';
ALTER TABLE {t} ADD COLUMN IF NOT EXISTS allowed_groups text[] NOT NULL DEFAULT '{{}}';
CREATE INDEX IF NOT EXISTS {t}_tsv_gin ON {t} USING gin (tsv);
CREATE INDEX IF NOT EXISTS {t}_acl_gin ON {t} USING gin (allowed_groups);
UPDATE {t} SET allowed_groups = '{{public}}' WHERE source = 'docs' AND allowed_groups = '{{}}';"""
COLS = "id, doc_id, section, applies_to, text, source, allowed_groups"


def connect(url: str = DATABASE_URL) -> psycopg.Connection:
    conn = psycopg.connect(url, autocommit=True)
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")  # must run before register_vector
    register_vector(conn)
    return conn
```

The embedder is a parameter, so tests can pass a fake one and you can swap providers without touching search code.

```python
# script_id: day_027_hybrid_search/index
class Index:
    def __init__(self, conn: psycopg.Connection, *, table: str = "chunks", dim: int = EMBED_DIM,
                 embed_fn: Callable[[Sequence[str]], np.ndarray] = embed):
        if not table.isidentifier():
            raise ValueError(f"bad table name {table!r}")  # it is formatted into SQL below
        self.conn, self.t, self.dim, self.embed_fn = conn, table, dim, embed_fn

    def create(self) -> None:
        self.conn.execute(SCHEMA.format(t=self.t, dim=self.dim))
        self.conn.execute(MIGRATION.format(t=self.t))  # today: tsv, source, allowed_groups

    def upsert(self, chunks: Sequence[DocChunk]) -> int:
        """Compact Day 26 upsert. Day 26's version embeds only new content-hash ids."""
        vectors = self.embed_fn([c.text for c in chunks])
        rows = [(c.id, c.doc_id, c.section, c.applies_to, c.text, v, c.metadata["source"],
                 c.metadata.get("allowed_groups", [])) for c, v in zip(chunks, vectors)]
        with self.conn.cursor() as cur:
            cur.executemany(f"""INSERT INTO {self.t}
                (id, doc_id, section, applies_to, text, embedding, source, allowed_groups)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET doc_id = EXCLUDED.doc_id, section = EXCLUDED.section,
                  applies_to = EXCLUDED.applies_to, text = EXCLUDED.text, embedding = EXCLUDED.embedding,
                  source = EXCLUDED.source, allowed_groups = EXCLUDED.allowed_groups""", rows)
        return len(rows)  # tsv is GENERATED, so the update above recomputes it

    def _hits(self, sql: str, params: dict) -> list[Hit]:
        return [Hit(DocChunk(r[0], r[1], r[2], r[3], r[4], {"source": r[5], "allowed_groups": r[6]}),
                    float(r[7])) for r in self.conn.execute(sql, params).fetchall()]
```

Each arm on its own. Both call `where_clause()` and paste the same fragment into their `WHERE`.

```python
# script_id: day_027_hybrid_search/index
    def search(self, query: str, k: int = 5, *, filters: Filters | None = None,
               groups: Sequence[str] = ("public",)) -> list[Hit]:
        where, params = where_clause(filters, groups)
        return self._hits(f"""SELECT {COLS}, 1 - (embedding <=> %(q)s) FROM {self.t}
            WHERE {where} ORDER BY embedding <=> %(q)s LIMIT %(k)s""",
            {**params, "q": self.embed_fn([query])[0], "k": k})

    def keyword_search(self, query: str, k: int = 5, *, filters: Filters | None = None,
                       groups: Sequence[str] = ("public",)) -> list[Hit]:
        where, params = where_clause(filters, groups)
        return self._hits(f"""SELECT {COLS}, ts_rank_cd(tsv, query)
            FROM {self.t}, websearch_to_tsquery('english', %(text)s) AS query
            WHERE tsv @@ query AND {where} ORDER BY ts_rank_cd(tsv, query) DESC, id LIMIT %(k)s""",
            {**params, "text": query, "k": k})
```

The hybrid query is the official pgvector-python RRF pattern with three changes: the filter sits inside both arms, the vector arm takes its `LIMIT` in an inner query (so the window function ranks 20 rows, not the whole table), and the score is cast to `float8`. `FULL OUTER JOIN` keeps rows only one arm found; a `LEFT JOIN` from the vector arm would drop every keyword-only hit, the exact-term win you came for.

```python
# script_id: day_027_hybrid_search/index
    def hybrid_search(self, query: str, k: int = 5, *, filters: Filters | None = None,
                      groups: Sequence[str] = ("public",), candidates: int = 20,
                      k_rrf: int = 60) -> list[Hit]:
        where, params = where_clause(filters, groups)  # ONE fragment, pasted into both arms
        sql = f"""
        WITH semantic AS (
            SELECT id, RANK() OVER (ORDER BY dist) AS rank FROM (
                SELECT id, embedding <=> %(q)s AS dist FROM {self.t}
                WHERE {where} ORDER BY embedding <=> %(q)s LIMIT %(n)s) AS nearest),
        keyword AS (
            SELECT id, RANK() OVER (ORDER BY ts_rank_cd(tsv, query) DESC) AS rank
            FROM {self.t}, websearch_to_tsquery('english', %(text)s) AS query
            WHERE tsv @@ query AND {where}
            ORDER BY ts_rank_cd(tsv, query) DESC LIMIT %(n)s),
        fused AS (
            SELECT COALESCE(s.id, kw.id) AS id,
                   COALESCE(1.0 / (%(k_rrf)s + s.rank), 0.0)
                 + COALESCE(1.0 / (%(k_rrf)s + kw.rank), 0.0) AS rrf
            FROM semantic s FULL OUTER JOIN keyword kw ON s.id = kw.id)
        SELECT {COLS}, rrf::float8 FROM fused JOIN {self.t} USING (id)
        ORDER BY rrf DESC, id LIMIT %(k)s"""
        params |= {"q": self.embed_fn([query])[0], "text": query, "n": candidates, "k_rrf": k_rrf, "k": k}
        return self._hits(sql, params)
```

Finally, compare the three searches on the dev split. Each fetches 20 chunks and keeps the first five distinct pages.

```python
# script_id: day_027_hybrid_search/index
if __name__ == "__main__":
    index = Index(connect())
    index.create()
    print(f"upserted {index.upsert(load_corpus())} doc chunks")  # issues join in the ACL demo
    cases = load_retrieval_cases("dev")
    arms = {"vector": index.search, "keyword": index.keyword_search, "hybrid": index.hybrid_search}
    rates = {name: hit_rate(cases, lambda q, k, fn=fn: ranked_doc_ids(fn(q, 20))[:k])
             for name, fn in arms.items()}
    print(f"{'hit@5':11}" + "".join(f"{name:>9}" for name in arms))
    for kind in ("exact_term", "semantic", "multi_hop", "overall"):
        print(f"{kind:11}" + "".join(f"{rates[name][kind]:9.2f}" for name in arms))
```

Expected output. The chunk count is fixed; every rate depends on your Postgres and embeddings, so fill in the `0.xx` from your run (your numbers will differ):

```text
upserted 349 doc chunks
hit@5         vector  keyword   hybrid
exact_term      0.xx     0.xx     0.xx
semantic        0.xx     0.xx     0.xx
multi_hop       0.xx     0.xx     0.xx
overall         0.xx     0.xx     0.xx
```

Expect keyword to be strong on `exact_term` and weak on questions, vector the reverse, and hybrid to keep most of both wins. If hybrid loses a slice, check which queries flipped before reaching for weights (Exercise 3).

## No Postgres? BM25 in 30 Lines

No Docker? The same design works in memory: a numpy vector arm (Day 26's `MemoryIndex`), the same `rrf()`, the same filter rule via `matches()`, and a keyword arm that is real **BM25**. For each query word on a page, BM25 multiplies how rare the word is in the corpus (IDF, inverse document frequency), how often it appears (with diminishing returns, `k1`) and a long-page penalty (`b`); Go Deeper has the formula. The tokenizer keeps `orb-1202` and `max_payload_kb` whole *and* adds their parts, so exact pastes match exactly.

```python
# script_id: day_027_hybrid_search/memory_index
# memory_index.py: no-Postgres fallback. Stdlib BM25 keyword arm + numpy vector arm + RRF + ACL filters.
# Install: uv add numpy "openai>=3.46,<4". Env: ORBIT_DATA; OPENAI_API_KEY optional (no key = keyword-only).
import math
import os
import re
from collections import Counter
from typing import Callable, Sequence

import numpy as np

from acl import Filters, load_corpus, matches
from atlas_base import DocChunk, Hit, embed, hit_rate, load_retrieval_cases, ranked_doc_ids
from fusion import rrf


def tokenize(text: str) -> list[str]:
    """Keep `orb-1202`, `orbit.toml`, `max_payload_kb` whole AND add their parts."""
    tokens: list[str] = []
    for word in re.findall(r"\w+(?:[-.]\w+)*", text.lower()):
        parts = [p for p in re.split(r"[-._]", word) if p]
        tokens += [word] + (parts if len(parts) > 1 else [])
    return tokens


class BM25:
    """Okapi BM25 with Lucene-style IDF (never negative); k1 and b are the usual defaults."""

    def __init__(self, texts: Sequence[str], k1: float = 1.5, b: float = 0.75):
        self.docs = [Counter(tokenize(t)) for t in texts]
        self.lens = [sum(d.values()) for d in self.docs]
        self.avg = sum(self.lens) / max(len(self.lens), 1)
        df = Counter(term for d in self.docs for term in d)
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.k1, self.b = k1, b

    def scores(self, query: str) -> list[float]:
        terms = set(tokenize(query))
        return [sum(self.idf[t] * d[t] * (self.k1 + 1)
                    / (d[t] + self.k1 * (1 - self.b + self.b * n / self.avg)) for t in terms & d.keys())
                for d, n in zip(self.docs, self.lens)]
```

`MemoryIndex` has the same methods as `Index`. With `embed_fn=None` it's keyword-only and needs no key; `hybrid_search` then returns the keyword ranking.

```python
# script_id: day_027_hybrid_search/memory_index
Embedder = Callable[[Sequence[str]], np.ndarray]


class MemoryIndex:
    """Same search API as the Postgres Index. embed_fn=None gives a keyword-only index."""

    def __init__(self, embed_fn: Embedder | None = embed):
        self.embed_fn = embed_fn
        self.chunks: dict[str, DocChunk] = {}
        self.vectors: dict[str, np.ndarray] = {}
        self.rows: list[DocChunk] = []
        self.bm25 = BM25([])

    def upsert(self, chunks: Sequence[DocChunk]) -> int:
        changed = [c for c in chunks if c.id not in self.chunks or self.chunks[c.id].text != c.text]
        if self.embed_fn and changed:  # embed only new or edited text
            self.vectors.update(zip((c.id for c in changed), self.embed_fn([c.text for c in changed])))
        self.chunks.update({c.id: c for c in chunks})
        self.rows = list(self.chunks.values())
        self.bm25 = BM25([c.text for c in self.rows])  # IDF is corpus-wide, so rebuild after writes
        return len(chunks)

    def search(self, query: str, k: int = 5, *, filters: Filters | None = None,
               groups: Sequence[str] = ("public",)) -> list[Hit]:
        allowed = [c for c in self.rows if matches(c, filters, groups)]  # filter BEFORE ranking
        if self.embed_fn is None or not allowed:
            return []
        sims = np.stack([self.vectors[c.id] for c in allowed]) @ self.embed_fn([query])[0]
        return [Hit(allowed[i], float(sims[i])) for i in np.argsort(-sims)[:k]]

    def keyword_search(self, query: str, k: int = 5, *, filters: Filters | None = None,
                       groups: Sequence[str] = ("public",)) -> list[Hit]:
        scores = self.bm25.scores(query)
        ranked = sorted((i for i, c in enumerate(self.rows) if matches(c, filters, groups) and scores[i] > 0),
                        key=lambda i: -scores[i])
        return [Hit(self.rows[i], scores[i]) for i in ranked[:k]]

    def hybrid_search(self, query: str, k: int = 5, *, filters: Filters | None = None,
                      groups: Sequence[str] = ("public",), candidates: int = 20, k_rrf: int = 60) -> list[Hit]:
        arms = [self.search(query, candidates, filters=filters, groups=groups),
                self.keyword_search(query, candidates, filters=filters, groups=groups)]
        fused = rrf([[h.chunk.id for h in arm] for arm in arms], k=k_rrf)
        return [Hit(self.chunks[cid], score) for cid, score in fused[:k]]
```

The same comparison table, with no database. Without a key it prints the keyword column only.

```python
# script_id: day_027_hybrid_search/memory_index
if __name__ == "__main__":
    use_vectors = bool(os.environ.get("OPENAI_API_KEY"))
    index = MemoryIndex(embed if use_vectors else None)
    index.upsert(load_corpus())
    arms: dict[str, Callable] = {"keyword": index.keyword_search}
    if use_vectors:
        arms |= {"vector": index.search, "hybrid": index.hybrid_search}
    else:
        print("OPENAI_API_KEY not set: BM25 keyword arm only")
    cases = load_retrieval_cases("dev")
    rates = {n: hit_rate(cases, lambda q, k, fn=fn: ranked_doc_ids(fn(q, 20))[:k]) for n, fn in arms.items()}
    print(f"{len(index.rows)} chunks · {len(cases)} dev cases")
    print(f"{'hit@5':11}" + "".join(f"{n:>9}" for n in rates))
    for kind in ("exact_term", "semantic", "multi_hop", "overall"):
        print(f"{kind:11}" + "".join(f"{r[kind]:9.2f}" for r in rates.values()))
```

Expected output without a key (with one you also get `vector` and `hybrid` columns; your numbers will differ):

```text
OPENAI_API_KEY not set: BM25 keyword arm only
349 chunks · 20 dev cases
hit@5        keyword
exact_term      1.00
semantic        0.86
multi_hop       1.00
overall         0.95
```

That keyword column is the day's most useful surprise: on a small corpus in one team's jargon, BM25 alone is a very strong baseline. Expect the Postgres keyword column to be lower on questions: `ts_rank_cd` has no IDF and `websearch_to_tsquery` requires every word. Measure a keyword baseline before you assume you need embeddings.

## Proving the ACL: Two Users, One Query

Add the issues as maintainer-only rows and ask one question as two people. It runs keyword-only without a key.

```python
# script_id: day_027_hybrid_search/acl_demo
# Two users, one query, and a leak count. Keyword-only without OPENAI_API_KEY.
# Env: ORBIT_DATA; OPENAI_API_KEY optional (embedding 240 issues ≈ $0.01, as of 2026-11, verify).
import os

from acl import load_corpus
from atlas_base import embed, load_retrieval_cases, ranked_doc_ids
from memory_index import MemoryIndex

index = MemoryIndex(embed if os.environ.get("OPENAI_API_KEY") else None)
index.upsert(load_corpus(include_issues=True))
USERS = {"anonymous": ("public",), "maintainer": ("public", "maintainers")}
QUERY = "redis reconnect storm"
for user, groups in USERS.items():
    pages = ranked_doc_ids(index.hybrid_search(QUERY, k=10, groups=groups))[:5]
    print(f"{user:10} {pages}")

# Leak test: no hit may carry only groups the caller lacks.
queries = [c.query for c in load_retrieval_cases("all")[:20]] + [QUERY]
anon = USERS["anonymous"]
leaks = sum(1 for q in queries for h in index.hybrid_search(q, k=10, groups=anon)
            if not set(h.chunk.metadata["allowed_groups"]) & set(anon))
print(f"anonymous leak test over {len(queries)} queries: leaks = {leaks}")

# Anti-pattern: rank everything, then filter. The caller asked for 5 rows.
top = index.hybrid_search(QUERY, k=5, groups=USERS["maintainer"])
visible = [h for h in top if "public" in h.chunk.metadata["allowed_groups"]]
print(f"filter after fusion: {len(visible)} of 5 rows left for an anonymous user")
try:
    index.hybrid_search(QUERY, groups=())
except ValueError as err:
    print("empty groups:", err)
```

Expected output without a key (your numbers will differ):

```text
anonymous  ['troubleshooting-broker', 'broker-redis', 'changelog', 'deployment-kubernetes', 'contributing']
maintainer ['troubleshooting-broker', 'broker-redis', 'changelog', 'issue-143', 'issue-161']
anonymous leak test over 21 queries: leaks = 0
filter after fusion: 4 of 5 rows left for an anonymous user
empty groups: groups must be a non-empty sequence such as ('public',)
```

The anonymous user gets docs only; the maintainer also gets the reconnect-storm issues. The leak test's job is to stay green when someone adds a cache or a new search path.

## When Keyword-Only Wins

Hybrid costs two queries per search, an embedding call per query and a second index to sync. Teams pick keyword-only search when:

| Situation | Better choice | Why |
|---|---|---|
| Lookups by ID, error code, SKU, ticket number | Keyword only (or an exact `=`) | There's one right answer and it's a literal string |
| Log and trace search | Keyword only | Users search for tokens they copied; meaning rarely helps |
| Small corpus in one team's vocabulary | Measure BM25 first | As you saw above, it may already be good enough |
| Strict latency or cost budget | Keyword only | No embedding call, no vector index |
| Paraphrased questions, multiple languages, synonyms | Hybrid (or vector) | Exact words rarely match how users ask |
| Mixed traffic, like Atlas | Hybrid | Pasted codes *and* questions in the same box |

Rule of thumb: copied queries → start with keywords; typed questions → start with hybrid; measure either way.

### In production

- Sync ACLs from the source of truth (tracker visibility, identity-provider groups) at ingest and on change.
- Evaluate and leak-test with real users' groups, not an admin account.
- Make every new search path call `where_clause()`; review SQL on `chunks` that doesn't.
- Watch latency per arm; the vector arm's HNSW settings usually dominate (Day 26).
- Many customers in one index is tenant isolation, a bigger topic than groups; see [Day 83: Auth, Multi-Tenancy & Usage Quotas](../../Phase_9_Production/Day_083_auth_multitenancy_quotas/auth_multitenancy_quotas.md).

## Go Deeper (optional)

<details><summary>Go deeper: BM25 versus ts_rank_cd, by the numbers</summary>

**In words.** Both reward a page for containing query words. BM25 also asks "how surprising is this word in *this* corpus?" and "is this page long?" `ts_rank_cd` asks neither. It looks at how many query words appear and how close together they are (the "cd" stands for cover density).

**Toy numbers.** Take 100 pages. The word `job` appears on 90 of them; `ORB-1202` appears on 4. With the IDF used in `BM25` above, `idf(job) = ln(1 + (100 − 90 + 0.5)/(90 + 0.5)) ≈ 0.11` and `idf(orb-1202) = ln(1 + (100 − 4 + 0.5)/(4 + 0.5)) ≈ 3.11`. One occurrence of the code outweighs a page full of `job`. In `ts_rank_cd`, both words count the same.

**Formula.** For query terms *t* and a page *d* of length |d|, with average length *avgdl*:

`score(d) = Σ idf(t) · tf(t, d) · (k1 + 1) / (tf(t, d) + k1 · (1 − b + b · |d| / avgdl))`

`k1` (commonly 1.2–2.0) caps how much repeating a word helps; `b` (commonly 0.75) sets how strongly long pages are penalised. Note that IDF is computed over *all* rows, including rows a caller can't see. That leaks no text, but per-tenant indexes (Day 83) also keep the statistics separate.

</details>

<details><summary>Go deeper: why the keyword arm misses questions (AND semantics)</summary>

`websearch_to_tsquery('english', 'what does ORB-1202 mean?')` produces `'orb' <-> '-1202' & 'mean'`. Stop words ("what", "does") vanish, but every remaining word is required, so a page that defines the code without the word "mean" doesn't match. Long questions almost never match anything, which is why the Postgres keyword arm tends to do poorly on `semantic` and `multi_hop` queries while BM25, which adds up whatever words match, did well.

In hybrid search this is mostly fine: when the keyword arm returns nothing, the `FULL OUTER JOIN` passes the vector ranking through unchanged. If you want a keyword arm that degrades gracefully, the options are an OR-style query built from the lexemes, a real BM25 engine, or a query rewriter such as multi-query ([Day 31](../../Phase_3_RAG/Day_031_reranking_contextual_retrieval/reranking_contextual_retrieval.md)). Measure before choosing; on Atlas the vector arm already covers questions.

</details>

<details><summary>Go deeper: real BM25 in Postgres, and learned sparse retrieval</summary>

Two directions go past today's stop line. Both are described here without code, because their current APIs weren't verified for this course (⚠ verify against current docs before you adopt either).

- **BM25 inside Postgres.** Extensions such as ParadeDB's `pg_search` add a BM25 index type to Postgres, so the keyword arm gets IDF and length normalisation without leaving SQL. Python libraries such as `bm25s` give you a faster in-memory BM25 than the 30-line version here.
- **Learned sparse retrieval.** Models in the SPLADE family produce a *sparse* vector per text: a weight for each vocabulary word, including related words that never appeared. It still behaves like keyword search (inverted index, exact terms count), but it also expands "OOM" toward "memory". It would replace the keyword arm, and RRF would stay the same, which is why `hybrid_search` takes ranked lists rather than caring how each arm works.

</details>

## Common Pitfalls

- **`TypeError: Object of type Decimal is not JSON serializable`.** SQL RRF arithmetic is `numeric`, returned as `Decimal`. Cast with `::float8` or `float()`.
- **Keyword-only hits vanish.** A `LEFT JOIN` from the vector top-N drops pages only the keyword arm found. Use `FULL OUTER JOIN` + `COALESCE`.
- **Filter in one arm, or after fusion.** One arm leaks; after fusion you return fewer than `k`. Paste one `where_clause()` into both arms before `LIMIT`.
- **`groups=None` treated as "everyone".** It leaks the first time a code path forgets groups. Default to `("public",)`, raise on empty, keep a leak test in CI.
- **`psycopg.errors.SyntaxError: syntax error in tsquery: "lease seconds"`.** Send user text through `websearch_to_tsquery`.
- **`ERROR: generation expression is not immutable`** on the `tsv` column. Write the config: `to_tsvector('english', text)`.

> **Where we stop:** today's keyword arms are Postgres full-text ranking and a stdlib BM25; BM25 extensions and learned sparse retrievers appear only in Go Deeper, because the fusion and filter mechanism you built stays the same when you swap an arm. Turning these filters into a security argument is [Day 28](../../Phase_3_RAG/Day_028_rag_pipeline/rag_pipeline.md); per-customer isolation is [Day 83](../../Phase_9_Production/Day_083_auth_multitenancy_quotas/auth_multitenancy_quotas.md).

## Key Takeaways

- Embeddings capture meaning, so they blur exact strings such as error codes, config keys and flags; a keyword arm restores literal matching.
- Reciprocal rank fusion adds `1/(k + rank)` votes from each list (k = 60), so you fuse rankings without comparing scores in different units, and items both arms like rise to the top.
- Postgres full-text search (`tsvector`, GIN, `websearch_to_tsquery`, `ts_rank_cd`) matches well but ranks without corpus statistics; it is not BM25. Check what it stores before trusting it with codes.
- Metadata and ACL filters are compiled once and applied inside both arms before `LIMIT`, failing closed: default groups `("public",)`, errors on empty groups, no groups means invisible.
- Keyword-only search wins for IDs, codes, logs, tight latency budgets and small single-vocabulary corpora; measure a BM25 baseline before assuming you need vectors.

## Quick Reference

| API / pattern | What it does | When to use | Gotcha |
|---|---|---|---|
| `tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED` | Keeps lexemes in sync with `text` | Every table you keyword-search | Config must be explicit, or "not immutable" |
| `websearch_to_tsquery('english', q)` | User text → `tsquery` | Anything a user typed | ANDs the words; questions often match nothing |
| `ts_rank_cd(tsv, query)` | Frequency + proximity rank | Ordering keyword matches | No IDF; ties are common |
| `rrf(rankings, k=60)` | Fuses ranked lists by position | Combining any retrievers | Scores are tiny (≈0.03); compare only to each other |
| `FULL OUTER JOIN` + `COALESCE` | Keeps hits from either arm | Fusing in SQL | `LEFT JOIN` drops keyword-only hits |
| `where_clause(filters, groups)` | One SQL fragment for filters + ACL | Inside both arms, before `LIMIT` | Keys are allowlisted; empty groups raise |
| `BM25(texts).scores(q)` | Stdlib keyword ranking with IDF | No-Postgres fallback, baselines | Rebuild after writes; IDF is corpus-wide |

## Exercises

1. **Warm-up: turn the fusion knobs.** Re-run the toy fusion with `k` = 1, 10, 60 and 600. With an API key, also compare `candidates=20` and `50` on the dev split.

<details><summary>Solution</summary>

A small `k` rewards the top of each list (at `k = 1`, `concepts-jobs` wins on its rank-1 vote); a large `k` rewards agreement. More candidates rarely change hit@5 here, because relevant pages already sit in the top 20.

```python
# script_id: day_027_hybrid_search/solution_ex1
import os

from fusion import rrf

vector = ["concepts-jobs", "configuration-reference", "results-backend", "flows-steps-and-state"]
keyword = ["error-codes", "configuration-reference", "broker-redis", "concepts-jobs"]
for k in (1, 10, 60, 600):
    print(f"k={k:<4}", [doc for doc, _ in rrf([vector, keyword], k=k)][:3])

if os.environ.get("OPENAI_API_KEY"):  # the candidates knob needs the vector arm
    from acl import load_corpus
    from atlas_base import hit_rate, load_retrieval_cases, ranked_doc_ids
    from memory_index import MemoryIndex

    index = MemoryIndex()
    index.upsert(load_corpus())
    for n in (20, 50):
        rate = hit_rate(load_retrieval_cases("dev"),
                        lambda q, k: ranked_doc_ids(index.hybrid_search(q, 20, candidates=n))[:k])
        print(f"candidates={n}", {kind: round(v, 2) for kind, v in rate.items()})
```

```text
k=1    ['concepts-jobs', 'configuration-reference', 'error-codes']
k=10   ['configuration-reference', 'concepts-jobs', 'error-codes']
k=60   ['configuration-reference', 'concepts-jobs', 'error-codes']
k=600  ['configuration-reference', 'concepts-jobs', 'error-codes']
```

</details>

2. **Core: ACLs as tested code.** Write pytest tests that prove (a) a `source` filter composes with `groups`: a maintainer asking for `source="issue"` gets only issues, an anonymous user gets an empty list rather than an error; (b) over 20 eval queries, an anonymous user never receives a maintainers-only row; (c) a planted "canary" row is findable by maintainers and never by anonymous users.

<details><summary>Solution</summary>

The canary is a unique string in a maintainer-only row: if it ever shows up for an anonymous caller, the test names the leak. Run with `pytest -q solution_ex2.py`, or as a script.

```python
# script_id: day_027_hybrid_search/solution_ex2
import pytest

from acl import load_corpus
from atlas_base import DocChunk, load_retrieval_cases
from memory_index import MemoryIndex

ANON, MAINT, CANARY = ("public",), ("public", "maintainers"), "zx-canary-7f3a"
index = MemoryIndex(None)  # keyword-only; the ACL logic is identical with embeddings
index.upsert(load_corpus(include_issues=True) + [DocChunk(
    "canary#0", "canary", "", "all", f"maintainer note {CANARY}", {"source": "issue", "allowed_groups": ["maintainers"]})])


def test_source_filter_composes_with_groups():
    hits = index.keyword_search("reconnect storm", k=10, filters={"source": "issue"}, groups=MAINT)
    assert hits and all(h.chunk.metadata["source"] == "issue" for h in hits)
    assert index.keyword_search("reconnect storm", filters={"source": "issue"}, groups=ANON) == []


def test_no_maintainer_rows_for_anonymous():
    for case in load_retrieval_cases("all")[:20]:
        for hit in index.hybrid_search(case.query, k=10, groups=ANON):
            assert set(hit.chunk.metadata["allowed_groups"]) & set(ANON), hit.chunk.id


def test_canary_only_for_maintainers():
    assert index.keyword_search(CANARY, groups=MAINT)[0].chunk.doc_id == "canary"
    assert all(h.chunk.doc_id != "canary" for h in index.hybrid_search(CANARY, groups=ANON))
    with pytest.raises(ValueError):
        index.hybrid_search(CANARY, groups=())


if __name__ == "__main__":
    for name, test in list(globals().items()):
        if name.startswith("test_"):
            test()
    print("3 tests passed")
```

```text
3 tests passed
```

</details>

3. **Core: query-aware fusion.** When the query contains an Orbit error code (`ORB-\d{4}`), count the keyword arm's votes twice. Re-measure the `exact_term` dev slice against plain `hybrid_search`.

<details><summary>Solution</summary>

A weight is a multiplier on each list's votes. Gate it on a pattern you can name; a global weight tuned on 8 dev queries mostly fits noise. Without a key the two rows are identical, since only the keyword arm runs.

```python
# script_id: day_027_hybrid_search/solution_ex3
import os
import re
from typing import Sequence

from acl import load_corpus
from atlas_base import Hit, embed, hit_rate, load_retrieval_cases, ranked_doc_ids
from memory_index import MemoryIndex

CODE = re.compile(r"\bORB-\d{4}\b", re.IGNORECASE)


def weighted_rrf(rankings: Sequence[Sequence[str]], weights: Sequence[float], k: int = 60):
    scores: dict[str, float] = {}
    for ranking, weight in zip(rankings, weights):
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + weight / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


def code_aware_search(index: MemoryIndex, query: str, k: int = 5, candidates: int = 20) -> list[Hit]:
    arms = [index.search(query, candidates), index.keyword_search(query, candidates)]
    weights = [1.0, 2.0 if CODE.search(query) else 1.0]  # pasted codes: trust literal matches more
    fused = weighted_rrf([[h.chunk.id for h in arm] for arm in arms], weights)
    return [Hit(index.chunks[cid], score) for cid, score in fused[:k]]


index = MemoryIndex(embed if os.environ.get("OPENAI_API_KEY") else None)
index.upsert(load_corpus())
cases = [c for c in load_retrieval_cases("dev") if c.kind == "exact_term"]
searches = {"hybrid": index.hybrid_search, "code-aware": lambda q, n: code_aware_search(index, q, n)}
for name, fn in searches.items():
    rate = hit_rate(cases, lambda q, k, fn=fn: ranked_doc_ids(fn(q, 20))[:k])
    print(f"{name:10} exact_term hit@5 = {rate['exact_term']:.2f}")
```

Without a key both rows run keyword-only, so they match:

```text
hybrid     exact_term hit@5 = 1.00
code-aware exact_term hit@5 = 1.00
```

</details>

4. **Stretch (past the stop line): make the arms pluggable.** Sketch a `hybrid()` that takes any list of retrievers, so a learned sparse retriever (Go Deeper) could replace the BM25 arm without touching fusion or filters.

<details><summary>Solution</summary>

Each arm is a function from `(query, n, groups)` to ranked hits, and each arm applies the filters itself. A sparse model would be one more function with the same signature.

```python
# script_id: day_027_hybrid_search/solution_ex4
from typing import Callable, Sequence

from acl import load_corpus
from atlas_base import Hit
from fusion import rrf
from memory_index import MemoryIndex

Arm = Callable[[str, int, Sequence[str]], list[Hit]]


def hybrid(arms: Sequence[Arm], query: str, k: int = 5, *, groups: Sequence[str] = ("public",),
           candidates: int = 20) -> list[Hit]:
    lists = [arm(query, candidates, groups) for arm in arms]  # every arm filters before ranking
    by_id = {h.chunk.id: h.chunk for hits in lists for h in hits}
    return [Hit(by_id[cid], score) for cid, score in rrf([[h.chunk.id for h in hits] for hits in lists])[:k]]


index = MemoryIndex(None)
index.upsert(load_corpus())
bm25_arm: Arm = lambda q, n, g: index.keyword_search(q, n, groups=g)
# sparse_arm: Arm = lambda q, n, g: my_sparse_index.search(q, n, groups=g)  # a SPLADE-style model
print([h.chunk.doc_id for h in hybrid([bm25_arm], "ORB-1202 PayloadTooLarge")])
```

```text
['api-reference-orbit', 'troubleshooting-memory', 'error-codes', 'configuration-reference', 'security']
```

</details>

## References & Further Reading

- [Postgres full-text search docs (source)](https://github.com/postgres/postgres/blob/master/doc/src/sgml/textsearch.sgml): `tsvector`, `websearch_to_tsquery`, and the ranking section that says ranking uses no global information.
- [pgvector-python RRF hybrid example](https://github.com/pgvector/pgvector-python/blob/master/examples/hybrid_search/rrf.py): the official pattern today's SQL is based on.
- [pgvector README](https://github.com/pgvector/pgvector): HNSW options and filtering with iterative scans, which matter once filters get selective.
- [OpenAI embeddings guide](https://developers.openai.com/api/docs/guides/embeddings.md): models, dimensions, and why the vectors are already unit length.
- Cormack, Clarke and Büttcher, "Reciprocal Rank Fusion outperforms Condorcet and individual rank learning methods" (SIGIR 2009): the source of RRF and k = 60; search for it by title.

## What's Next

Atlas now finds meanings and exact strings, and never shows callers rows they can't read. In [Day 28: Building the RAG Pipeline: Grounded Answers with Citations](../../Phase_3_RAG/Day_028_rag_pipeline/rag_pipeline.md) you put `hybrid_search()` behind `ask()`, feed the hits to the model with citations, teach Atlas to say "I don't know", and turn today's filter mechanism into a security rule: filter by authorization, then rank.
