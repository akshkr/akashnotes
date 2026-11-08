# FACTS_PACK: rag_data (RAG data stack)
As of **2026-11-06**. Python 3.12 venvs under `/tmp/facts_rag_*`. No API keys and no paid-API calls; public HF model downloads only.
**Installed + introspected:** pgvector 0.5.1 · psycopg[binary] 3.3.8 · chromadb 1.5.9 · cohere 7.3.1 · voyageai 0.5.0 · sentence-transformers 6.2.0
(torch 2.15.0, transformers 5.22.2) · pypdf 7.0.0 · pdfplumber 0.11.10 · beautifulsoup4 4.15.0 · markitdown 0.1.9 · presidio-analyzer/-anonymizer 2.2.366
· spacy 3.8.18 + en_core_web_sm 3.8.0 · neo4j 6.4.1 · redisvl 0.31.0 (redis 8.1.0) · sqlglot 30.30.0 · numpy 2.4.6 · pgserver 0.1.4 (test PG only). PyPI-only: docling 2.148.0 · unstructured 0.27.36 · psycopg-pool 3.3.3 · numpy 2.5.4 · bm25s 0.3.16.

## 1. VERIFIED API SHAPES
"Ran" means executed locally. The Postgres tests ran on embedded `pgserver` (PG 16.2 + pgvector **0.6.2**). Lessons pin **0.8.7**, and per the v0.8.7 README the SQL used below is the same.
### 1a. pgvector + psycopg 3
```python
import os, numpy as np, psycopg                   # vec/qvec: list[float] from your embedder
from pgvector import Vector                       # top-level import (0.5+)
from pgvector.psycopg import register_vector
conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
conn.execute("CREATE EXTENSION IF NOT EXISTS vector")  # BEFORE register_vector
register_vector(conn)                              # per connection; pools: configure=register_vector
conn.execute("""CREATE TABLE IF NOT EXISTS chunks (id text PRIMARY KEY, body text NOT NULL,
  embedding vector(1536), tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', body)) STORED)""")
conn.execute("""INSERT INTO chunks (id, body, embedding) VALUES (%s, %s, %s)
  ON CONFLICT (id) DO UPDATE SET body = EXCLUDED.body, embedding = EXCLUDED.embedding""",
  ("c1", "reset your password", np.array(vec, dtype=np.float32)))
rows = conn.execute("SELECT id, embedding <=> %s AS dist FROM chunks ORDER BY dist LIMIT 5",
                    (Vector(qvec),)).fetchall()
```
verified by: ran it; `pgvector/psycopg/register.py` and `vector.py` (0.5.1); pgvector-python README + CHANGELOG.
- Calling `register_vector` before `CREATE EXTENSION` raises `psycopg.ProgrammingError: vector type not found in the database`. For async: `await register_vector_async(conn)`. Pass an `np.ndarray` or a `pgvector.Vector`. A **plain Python list fails** with `<=>` (`psycopg.errors.UndefinedFunction: operator does not exist: vector <=> double precision[]`); write `%s::vector` if you must pass a list.
- Since pgvector-python **0.5.0** a selected `vector` comes back as **`pgvector.Vector`**, not numpy. Use `.to_list()`/`.to_numpy()`. NumPy is no longer a dependency, so add it yourself.
- Operators: `<->` L2 · `<=>` cosine **distance** (similarity = 1 − d) · `<#>` **negative** inner product · `<+>` L1. Each index's opclass must match its operator:
  `vector_cosine_ops`↔`<=>`, `vector_l2_ops`↔`<->`, `vector_ip_ops`↔`<#>` (`halfvec_*_ops` for halfvec). Unit-length vectors rank the same under all three.
### 1b. pgvector indexes and tuning (SQL)
```sql
CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
SET hnsw.ef_search = 100;            -- default 40; SET LOCAL inside a transaction scopes it to one query
CREATE INDEX ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);  -- build AFTER loading data
SET ivfflat.probes = 10;             -- default 1; start at sqrt(lists)
SET hnsw.iterative_scan = relaxed_order;   -- 0.8.0+: keeps filtered queries from returning too few rows
```
verified by: ran the index/`SET` lines (`SHOW hnsw.ef_search` → 40 by default; `SET LOCAL` reverted after commit). `iterative_scan` (0.8.0+) is from the README only.
- HNSW defaults are `m=16`, `ef_construction=64`, `ef_search=40`. For IVFFlat, start with `lists = rows/1000` (≤1M rows) or `sqrt(rows)`. Filters apply *after* the ANN scan: with `ef_search=40`, a `WHERE` that matches 10% of rows returns about 4 rows. Use `iterative_scan` or partial/partitioned indexes.
- **Dimension limit for indexes:** `vector` ≤ **2,000**, `halfvec` ≤ **4,000**. Observed: an HNSW index on `vector(3072)` fails with `column cannot have more than 2000 dimensions for hnsw index`.
  For `text-embedding-3-large` (3072-d) use `halfvec(3072)` + `halfvec_cosine_ops`, or request `dimensions=1536`. halfvec (pgvector ≥0.7) is confirmed by the README only.
- Docker: `pgvector/pgvector:0.8.7-pg18-trixie` (also `pg18`, `0.8.7-pg18`, `pg18-bookworm`, pg13–17). **PG 18 images moved the volume:** mount at
  `/var/lib/postgresql`, not `/var/lib/postgresql/data` (PGDATA=`/var/lib/postgresql/18/docker`). verified by: Docker Hub tags API; docker-library `18/trixie/Dockerfile` + `postgres/content.md`.
### 1c. Postgres full-text search + RRF (k = 60)
```sql
CREATE INDEX ON chunks USING gin (tsv);   -- tsv is the GENERATED tsvector column from 1a
WITH semantic AS (SELECT id, RANK() OVER (ORDER BY embedding <=> %(q)s) AS rank
                  FROM chunks ORDER BY embedding <=> %(q)s LIMIT 20),
keyword AS (SELECT id, RANK() OVER (ORDER BY ts_rank_cd(tsv, query) DESC) AS rank
            FROM chunks, websearch_to_tsquery('english', %(text)s) query
            WHERE tsv @@ query ORDER BY ts_rank_cd(tsv, query) DESC LIMIT 20)
SELECT COALESCE(s.id, k.id) AS id,
       COALESCE(1.0 / (%(k)s + s.rank), 0.0) + COALESCE(1.0 / (%(k)s + k.rank), 0.0) AS score
FROM semantic s FULL OUTER JOIN keyword k ON s.id = k.id ORDER BY score DESC LIMIT 5;
```
verified by: ran it with `{"q": np_array, "text": "password", "k": 60}`. Same shape as pgvector-python `examples/hybrid_search/rrf.py`. Postgres `textsearch.sgml`.
- `websearch_to_tsquery` accepts user syntax and never raises a syntax error: `"login page" or password -billing` → `'login' <-> 'page' | 'password' & !'bill'`.
  The RRF score is a **`decimal.Decimal`** (numeric). Cast it with `::float8` or `float()` before JSON.
- **`ts_rank`/`ts_rank_cd` are NOT BM25.** The docs say the ranking functions "do not use any global information" (no IDF), so call it "full-text ranking".
  Real BM25 needs an extension (e.g. ParadeDB `pg_search`) or a Python lib (§2). Neither is verified here, so cover them in prose only.
### 1d. chromadb 1.5 (comparison-table / local option)
```python
import chromadb
client = chromadb.PersistentClient(path="./chroma")
col = client.get_or_create_collection(name="docs", configuration={"hnsw": {"space": "cosine"}})
col.upsert(ids=["a", "b"], documents=["reset password", "billing"],
           embeddings=[[1.0, 0.0], [0.0, 1.0]], metadatas=[{"tenant": "t1"}, {"tenant": "t2"}])
r = col.query(query_embeddings=[[1.0, 0.0]], n_results=2, where={"tenant": "t1"},
              include=["documents", "distances", "metadatas"])
r["ids"][0], r["distances"][0]            # nested lists, one inner list per query
```
verified by: ran it on 1.5.9 (the result was `{'ids': [['a']], 'distances': [[0.0]], ...}`); `inspect.signature`.
- The default space is `l2`. Set cosine **at creation**: `col.modify(configuration={"hnsw": {"space": …}})` raises `InvalidArgumentError` (only `ef_search` etc. can be modified). The legacy
  `metadata={"hnsw:space": "cosine"}` still works, but teach `configuration=`. Defaults: `ef_construction=100`, `ef_search=100`, `max_neighbors=16`. Names must be 3–512 chars `[a-zA-Z0-9._-]`
  (`"x"` raises `chromadb.errors.InvalidArgumentError`). If you omit embeddings, `DefaultEmbeddingFunction` (local ONNX MiniLM, downloaded on first use) embeds the text, so pass your own.
### 1e. Rerankers
```python
import cohere                                   # cohere 7.3.1; reads CO_API_KEY
co = cohere.ClientV2()
resp = co.rerank(model="rerank-v5.0-fast", query=q, documents=docs, top_n=5)  # documents: list[str]
for r in resp.results:                          # sorted best-first; r.index, r.relevance_score, r.relevant_spans
    print(r.index, round(r.relevance_score, 3), docs[r.index][:60])
```
verified by: `inspect.signature(cohere.ClientV2.rerank)` → keyword-only `(*, model, query, documents: Sequence[str], top_n=, max_tokens_per_doc=, relevant_spans=, priority=,
request_options=)`; `V2RerankResponse` fields `id, results, meta`; Cohere docs source `models/rerank.mdx` + `changelog/2026-10-21-rerank-v5.mdx`. Not called live.
- Errors: `cohere.errors.TooManyRequestsError`, `UnauthorizedError`, `BadRequestError`. Rerank 5 scores are **calibrated 0–1**, so one threshold works across queries. Context Focus (`relevant_spans=cohere.RerankRelevantSpans(mode="enabled", threshold=0.3, max_spans=10)`) is Rerank 5 only, off by default, and returns char `start`/`end` spans.
```python
from sentence_transformers import CrossEncoder   # local, free; pulls torch
ce = CrossEncoder("cross-encoder/ms-marco-MiniLM-L6-v2")      # ~91 MB download on first use
scores = ce.predict([(q, d) for d in docs])                   # np.ndarray float32, RAW LOGITS (can be negative)
top = ce.rank(q, docs, top_k=3, return_documents=True)        # [{'corpus_id', 'score', 'text'}, ...] best-first
```
verified by: ran it on sentence-transformers 6.2.0 + torch 2.15.0. Output: `[-1.87, -11.12, -6.05]`; `rank` → corpus_id 0, then 2.
- **Both IDs resolve:** `…-L6-v2` is canonical and `…-L-6-v2` redirects to it (both loaded). Use **`L6`**. The scores are logits, so only their order matters.
  For 0–1, call `predict(..., activation_fn=torch.nn.Sigmoid())` (ran). `ce.max_length` is deprecated, so use `max_seq_length`. The window is 512 tokens.
- **torch weight:** sentence-transformers 6.2 hard-requires `torch>=2.2` and `transformers>=5`. Measured on macOS arm64: torch 566 MB, whole venv 839 MB. On Linux x86_64: a 539 MB wheel
  **plus NVIDIA CUDA 13 wheels** by default. For CPU-only, `uv pip install torch --torch-backend=cpu` (flag in uv 0.7.20 `--help`). The 8 GB-RAM path: managed reranker, or skip reranking.
### 1f. Parsing: pypdf 7, pdfplumber, BeautifulSoup, model-based parsers
```python
from pypdf import PdfReader                     # pypdf 7.0.0 (Python >=3.10). Never PyPDF2.
reader = PdfReader("handbook.pdf")              # str | Path | binary file; strict=False, password=None
pages = [p.extract_text() for p in reader.pages]            # extraction_mode="plain" (default) | "layout"
import pdfplumber                               # 0.11.10, built on pdfminer.six
with pdfplumber.open("handbook.pdf") as pdf:
    for page in pdf.pages:                      # page.page_number is 1-based
        text, tables = page.extract_text(), page.extract_tables()   # tables: list[list[list[str | None]]]
```
verified by: ran both on a generated 2-page PDF (`'Orbit Handbook\nRefund policy: 30 days.\n'`); `inspect.signature`; pypdf CHANGELOG 7.0.0 + PR #4306.
- **pypdf 7.0.0 (released 2026-11-06)** leaves `PdfReader`/`pages`/`extract_text`/`metadata` unchanged. It drops Python 3.9 and `cryptography<43` (encrypted PDFs need `pypdf[crypto]`).
  Every soft deprecation is now hard: `page.inline_images` raises `pypdf.errors.DeprecationError` ("Use PageObject.images"), and writer methods were removed (§3).
  Errors: `PdfReadError`, `FileNotDecryptedError`, `WrongPasswordError`, `EmptyFileError` (all `PyPdfError`). Scanned pages return `""`, so route them to OCR, a model parser, or `input_file` (D14).
```python
from bs4 import BeautifulSoup                   # beautifulsoup4 4.15.0; "lxml" also works if installed
soup = BeautifulSoup(html, "html.parser")
for tag in soup(["script", "style", "nav"]):
    tag.decompose()
text = soup.get_text(separator="\n", strip=True)
```
verified by: ran it. `findAll` and `find_all(text=...)` emit `DeprecationWarning`, so use `find_all` and `string=`.
- **markitdown** 0.1.9 (*Beta*, Py ≥3.10,<3.15). **Ran:** `MarkItDown().convert("f.pdf")` → `DocumentConverterResult` with `.markdown` (`.text_content` holds the same text) and `.title`;
  install `markitdown[pdf]` or `[all]`; PDF pages are separated by `\x0c`.
- From READMEs, not run: **docling** 2.148.0 (Stable, MIT; heavy layout/table models): `DocumentConverter().convert(src).document.export_to_markdown()`.
  **unstructured** 0.27.36 (*Beta*, **Py ≥3.11,<3.14**): `from unstructured.partition.auto import partition`; extras `[pdf]`/`[all-docs]`.
### 1g. Presidio (PII detection + redaction), 2.2.366
```python
from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
nlp = NlpEngineProvider(nlp_configuration={"nlp_engine_name": "spacy",
      "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}]}).create_engine()
analyzer = AnalyzerEngine(nlp_engine=nlp, supported_languages=["en"])
results = analyzer.analyze(text=text, language="en",            # language is REQUIRED (TypeError if omitted)
                           entities=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD"], score_threshold=0.4)
out = AnonymizerEngine().anonymize(text=text, analyzer_results=results,
      operators={"DEFAULT": OperatorConfig("replace", {"new_value": "<PII>"})})
print(out.text)     # EngineResult; out.items = list of replaced spans
```
verified by: ran it. `"Contact Jane Doe at jane.doe@example.com or 212-555-0199. Card 4111 1111 1111 1111."` → `"Contact <PII> at <PII> or <PII>. Card <PII>."`
- **spaCy model:** a bare `AnalyzerEngine()` loads `en_core_web_lg` (a **401 MB** wheel) and **auto-downloads it at runtime** if it's missing. With no pip, spaCy 3.8.18 shells out to
  `uv pip install` into whatever env it discovers (observed: it targeted the active conda env, and we killed it). Declare the model explicitly:
  `uv add "en_core_web_sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"` (13 MB, URL 200; lg = `en_core_web_lg-3.8.0`).
- **Expect false positives** (observed with sm): the US phone number was also tagged `UK_NHS` (1.0), `DATE_TIME` matched inside the card number, and `URL` matched inside the email. `PHONE_NUMBER` scored only 0.4.
  Restrict `entities=` and set `score_threshold`. With no `operators`, each span becomes `<ENTITY_TYPE>`. `mask` takes `{"masking_char", "chars_to_mask", "from_end"}`.
- The email recognizer fetches `publicsuffix.org` on first use. Offline, it logs an SSLError and uses its bundled list, with correct results. The repo moved to **data-privacy-stack/presidio**
  (microsoft/presidio redirects). Package names are unchanged. **Py ≥3.11,<3.15**; pins `numpy<2.5`.
### 1h. neo4j 6 driver (optional GraphRAG, D33)
```python
from neo4j import GraphDatabase, RoutingControl          # neo4j 6.4.1 (`uv add neo4j`, NOT neo4j-driver)
with GraphDatabase.driver(os.environ["NEO4J_URI"], auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"])) as driver:
    driver.verify_connectivity()
    records, summary, keys = driver.execute_query(
        "MATCH (c:Customer {id: $cid})-[:FILED]->(t:Ticket) RETURN t.title AS title LIMIT $n",
        {"cid": "c42", "n": 5}, routing_=RoutingControl.READ, database_="neo4j")
    titles = [r["title"] for r in records]
```
verified by: `inspect.signature` on 6.4.1: `driver(uri, *, auth=None, **config)`; `execute_query(query_, parameters_=None, routing_=RoutingControl.WRITE, database_=None, …)` → `EagerResult(records, summary, keys)`; 6.x `CHANGELOG.md`. Not run (no server).
- The config kwargs of `execute_query` end in `_`. **The default routing is WRITE**, so pass `RoutingControl.READ` for reads. Use `$params`, never f-strings. **6.0 breaking:** needs Python ≥3.10 (the next release drops 3.10). The `neo4j-driver` alias package and `session.read_transaction`/`write_transaction` are removed (use `execute_read`/`execute_write`).
  **Drivers and sessions are no longer closed in `__del__`** (use `with`/`.close()`). A closed driver raises `DriverError`, and bad `auth` raises `ConfigurationError` (it was `AuthError`).
  The `trust=` option is removed. 6.4 deprecates URIs that contain a path or fragment. Errors: `neo4j.exceptions.ServiceUnavailable`, `AuthError`, `CypherSyntaxError`, `ClientError`.
### 1i. redisvl SemanticCache (D85), redisvl 0.31.0 + redis-py 8.1.0
```python
from redisvl.extensions.cache.llm import SemanticCache
from redisvl.utils.vectorize import CustomVectorizer
from redisvl.query.filter import Tag
vec = CustomVectorizer(embed=embed_text)         # your fn: str -> list[float] (wraps client.embeddings.create)
cache = SemanticCache(name="atlas_cache", vectorizer=vec, distance_threshold=0.1, ttl=3600,
                      redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379"),
                      filterable_fields=[{"name": "tenant", "type": "tag"}])
hits = cache.check(prompt=q, filter_expression=Tag("tenant") == tenant)   # list[dict]; [] on miss
answer = hits[0]["response"] if hits else None
if answer is None:
    answer = call_llm(q)
    cache.store(prompt=q, response=answer, filters={"tenant": tenant})
```
verified by: `inspect.signature` (`__init__`, `check`, `store`); `extensions/cache/llm/semantic.py`; redis-vl-python README. `Tag("tenant") == "t1"` renders `@tenant:{t1}`. Against a closed port, `__init__` raised `redis.exceptions.ConnectionError`, so the cache connects and creates its index on construction. **The hit/miss round trip was not run** (no Redis).
- `distance_threshold` is Redis **cosine distance (0–2), lower is stricter**, default 0.1; a higher value gives more hits and more wrong answers. **The default vectorizer is
  `HFTextVectorizer("redis/langcache-embed-v1")`** (needs torch), so always pass `vectorizer=`. `OpenAITextVectorizer` defaults to the **legacy `text-embedding-ada-002`** and **makes a live
  embeddings call in `__init__`** (a "dimension check"). `CustomVectorizer` likewise calls your `embed` once at init. `CustomTextVectorizer` and `redisvl.extensions.llmcache` emit DeprecationWarning.
- Server: per the README, `docker run -d --name redis -p 6379:6379 redis:latest` ("Redis 8+ with built-in vector search"). Redis <8 without the Search module won't work.
### 1j. Text-to-SQL safety: sqlite3 read-only + sqlglot (D33)
```python
import sqlite3, sqlglot, sqlglot.expressions as exp          # sqlglot 30.30.0 (same as `from sqlglot import exp`)
FORBIDDEN = (exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Drop, exp.Create, exp.Alter, exp.Command, exp.Pragma, exp.Attach, exp.Detach, exp.TruncateTable, exp.Set)
def validate_select(sql: str, allowed: frozenset[str] = frozenset({"tickets", "customers"})) -> str:
    stmts = sqlglot.parse(sql, read="sqlite")                 # sqlglot.errors.ParseError on bad SQL
    if len(stmts) != 1 or not isinstance(stmts[0], exp.Query):  # Query covers Select and Union
        raise ValueError("exactly one SELECT statement allowed")
    if stmts[0].find(*FORBIDDEN):                             # catches WITH x AS (DELETE ...) SELECT
        raise ValueError("write/DDL inside query")
    tables = {t.name for t in stmts[0].find_all(exp.Table)} - {c.alias_or_name for c in stmts[0].find_all(exp.CTE)}
    if not tables <= allowed:
        raise ValueError(f"table not allowed: {sorted(tables - allowed)}")
    return stmts[0].sql(dialect="sqlite")                     # normalized SQL
conn = sqlite3.connect("file:orbit.db?mode=ro", uri=True)    # uri=True is REQUIRED
conn.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 0)              # Py 3.11+: blocks ATTACH (mode=ro doesn't)
rows = conn.execute(validate_select(llm_sql)).fetchmany(200)
```
verified by: ran it (Py 3.12, SQLite 3.45.3). `DELETE` → `sqlite3.OperationalError: attempt to write a readonly database`. `SELECT 1; DROP TABLE t`, `PRAGMA …`, `ATTACH …`, `VACUUM INTO …`
and `sqlite_master` are rejected, and `SELEC id FROM` → `ParseError`. `WITH x AS (DELETE … RETURNING *) SELECT …` is **`exp.Select`** at the root, so only `find(*FORBIDDEN)` catches it. CTEs and UNION pass.
- **`mode=ro` does NOT stop `ATTACH`.** On a read-only connection, `ATTACH DATABASE 'x2.db' AS x; CREATE TABLE x.evil(a)` **created and wrote a new file**. The `setlimit` line makes
  it fail (`too many attached databases - max 0`). An alternative is `conn.set_authorizer(fn)` returning `sqlite3.SQLITE_DENY` for `SQLITE_ATTACH`/`SQLITE_PRAGMA` (observed: `not authorized`).
- Without `uri=True`, `"file:orbit.db?mode=ro"` is a literal filename: sqlite **creates a new writable file** with that name (observed). sqlglot parses unmodelled syntax (`VACUUM INTO`) as `exp.Command`, so it stays denied.
### 1k. numpy cosine idiom
```python
import numpy as np
def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))
M = np.asarray(doc_vectors, dtype=np.float32)                 # (n_docs, dim)
Mn = M / np.linalg.norm(M, axis=1, keepdims=True)             # normalize once at index time
sims = Mn @ (q / np.linalg.norm(q))                           # (n_docs,) cosine similarities
top_k = np.argsort(-sims)[:5]                                 # indices, best first
```
verified by: ran it on numpy 2.4.6 (`cosine([1,0,0],[0.9,0.1,0])` → 0.99388). A zero vector gives `nan` plus a `RuntimeWarning`, so guard against it. OpenAI's embeddings guide:
"OpenAI embeddings are normalized to length 1", so `M @ q` alone is the cosine. Re-normalize any vectors you truncate yourself (prefer `dimensions=`).
- **numpy 2.5.x requires Python ≥3.12**, so Py 3.11 gets 2.4.x, and presidio-analyzer pins `numpy<2.5.0`. Don't pin numpy 2.5 in course lockfiles.

## 2. IDS / VERSIONS / PRICES (as of 2026-11-06)
| Item | Value | Source |
|---|---|---|
| pgvector image | `pgvector/pgvector:0.8.7-pg18-trixie` (ext 0.8.7, 2026-10-01). 0.8.6 and 0.8.7 fix IVFFlat buffer overflows, so pin **≥0.8.7** | Docker Hub tags API; pgvector CHANGELOG |
| Redis image | `redis:8` (newest is 8.10.3) | Docker Hub tags API |
| Cohere rerank | **`rerank-v5.0-pro`, `rerank-v5.0-fast`** (2026-10-21; 32k ctx; ~2B / ~500M params). Still listed: `rerank-v4.0-pro/-fast` (32k), `rerank-v3.5` (4k) | Cohere docs `models/rerank.mdx` |
| Cohere price | Billed **per search**. The $ figure is UNVERIFIED (cohere.com/pricing unreachable): "see cohere.com/pricing, ⚠ verify" | `how-does-cohere-pricing-work.mdx` |
| Voyage rerank IDs | **UNVERIFIED.** SDK 0.5.0 ships no model list (its tests use the stale `rerank-lite-1`) and the docs are unreachable. Omit, or prose + ⚠ verify | voyageai-python source |
| Local reranker | `cross-encoder/ms-marco-MiniLM-L6-v2` (90.9 MB safetensors) | HF API |
| spaCy models | `en_core_web_sm` 3.8.0 (13 MB), `en_core_web_lg` 3.8.0 (401 MB) | spacy-models releases API |
| Python BM25 | `bm25s` 0.3.16 (2026-10-28, active); `rank-bm25` 0.2.2 (last release 2022, stale). **API not verified** | PyPI JSON |

## 3. DON'T USE
- `PyPDF2` → `pypdf` 7. pypdf `page.inline_images` → `page.images`. Writer `add_js` → `add_open_action`; `remove_identicals`/`remove_orphans` → `remove_duplicates`/`remove_unreferenced`.
- `pgvector.utils` and classes re-exported from submodules (removed in 0.5.0) → `from pgvector import Vector, HalfVector`. Code expecting numpy from `SELECT embedding` → `.to_numpy()`. New `psycopg2` code → psycopg 3.
- pgvector images older than 0.8.7 → `0.8.7-pg18-trixie`. A PG 18 volume at `/var/lib/postgresql/data` → `/var/lib/postgresql`. Indexing `vector(n>2000)` → `halfvec(n)` or `dimensions=`.
- Calling Postgres `ts_rank` "BM25" → "full-text ranking". Chroma `metadata={"hnsw:space": …}` → `configuration={"hnsw": {"space": …}}`. `cohere.Client` (v1) rerank → `cohere.ClientV2().rerank`. `rerank-english/multilingual-v2.0` (retired 2025-04-30) and the `-v3.0` models → `rerank-v5.0-fast`/`-pro`.
- `cross-encoder/ms-marco-MiniLM-L-6-v2` (works only through a redirect) → `…-L6-v2`. `CrossEncoder.max_length` → `max_seq_length`. bs4 `findAll`/`text=` → `find_all`/`string=`.
- A bare `AnalyzerEngine()` with a runtime model download → an explicit `en_core_web_*` dependency + `NlpEngineProvider`. The `neo4j-driver` package → `neo4j`. `read_transaction`/`write_transaction` → `execute_read`/`execute_write` or `execute_query`. Relying on `__del__` to close → `with`.
- `redisvl.extensions.llmcache` → `redisvl.extensions.cache.llm`. `CustomTextVectorizer` → `CustomVectorizer`. `OpenAITextVectorizer()` with its ada-002 default → set `model=`, or use `CustomVectorizer`. GPTCache → redisvl.
- Using sqlite `mode=ro` as the *only* text-to-SQL boundary → sqlglot allowlist + `SQLITE_LIMIT_ATTACHED=0` or an authorizer (§1j).

## 4. ⚠ VERIFY RESOLUTIONS
- D024 | pypdf 7 | **CONFIRMED**: 7.0.0 shipped 2026-11-06 with the reader/extraction API unchanged. It drops Py 3.9 and cryptography<43, and soft deprecations now raise `DeprecationError` (§1f).
- D031 | reranker IDs | **CORRECTED**: current Cohere models are `rerank-v5.0-pro`/`rerank-v5.0-fast` (2026-10-21); B_currency listed only v4.0-pro/v3.5. Cross-encoder `ms-marco-MiniLM-L6-v2`
  is **CONFIRMED** (it ran, and `L-6` redirects). Voyage rerank IDs are **UNVERIFIABLE**: omit them, or prose + ⚠ verify.
- D033 | read-only connection, allowlists, query checks | **CONFIRMED + CORRECTED**: `mode=ro` does **not** block `ATTACH`, which wrote a new file. Add `SQLITE_LIMIT_ATTACHED=0` or an authorizer, plus the sqlglot check (§1j).
- D033 | neo4j 6 | **CONFIRMED**: 6.4.1, `execute_query` + `RoutingControl.READ`. The 6.0 breaking changes are in §1h. No query was executed (no server).
- D073 | Presidio | **CONFIRMED**: 2.2.366 ran end to end with `en_core_web_sm`. The repo moved to data-privacy-stack. Install the spaCy model explicitly (a bare engine auto-downloads the 401 MB `lg`).
- D085 | `redisvl` | **CONFIRMED** (signatures + source; no Redis server): 0.31.0 `redisvl.extensions.cache.llm.SemanticCache`, `filterable_fields` + `Tag` for tenant keys. Pass a vectorizer.
- D027 (not ⚠-tagged) | "full-text/BM25 search (`tsvector`)" | **CORRECTED**: `ts_rank(_cd)` is not BM25 (no corpus statistics), so call it full-text ranking. For BM25, use `bm25s` in prose + ⚠ verify (D031's "+ BM25" likewise).
- D026 (not ⚠-tagged) | pgvector compose | **CONFIRMED**: `pgvector/pgvector:0.8.7-pg18-trixie`. **CORRECTED**: the PG 18 volume path is `/var/lib/postgresql`.

## 5. VERIFIED LINKS (each returned HTTP 200 on 2026-11-06)
- https://github.com/pgvector/pgvector (pgvector README: types, operators, HNSW/IVFFlat, iterative scans, Docker)
- https://github.com/pgvector/pgvector/blob/master/CHANGELOG.md (extension releases, including the 0.8.7 fixes)
- https://github.com/pgvector/pgvector-python/blob/master/CHANGELOG.md (0.5.0 breaking changes)
- https://github.com/pgvector/pgvector-python/blob/master/examples/hybrid_search/rrf.py (the official RRF hybrid-search example)
- https://hub.docker.com/r/pgvector/pgvector (Docker image and tags)
- https://github.com/docker-library/docs/blob/master/postgres/content.md (official Postgres image docs: the PG 18 PGDATA/volume change)
- https://github.com/postgres/postgres/blob/master/doc/src/sgml/textsearch.sgml (Postgres full-text docs source; postgresql.org was unreachable)
- https://github.com/cohere-ai/cohere-developer-experience/blob/main/fern/pages/models/rerank.mdx (Cohere rerank model table)
- https://github.com/cohere-ai/cohere-developer-experience/blob/main/fern/pages/changelog/2026-10-21-rerank-v5.mdx (Rerank 5 announcement)
- https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2 (cross-encoder model card)
- https://github.com/py-pdf/pypdf/blob/main/CHANGELOG.md (pypdf changelog, 7.0.0)
- https://github.com/jsvine/pdfplumber (pdfplumber)
- https://github.com/microsoft/markitdown (MarkItDown)
- https://github.com/data-privacy-stack/presidio (Presidio, at its new repo home)
- https://github.com/data-privacy-stack/presidio/blob/main/docs/installation.md (Presidio install + spaCy models)
- https://github.com/explosion/spacy-models/releases/tag/en_core_web_sm-3.8.0 (spaCy small English model)
- https://github.com/neo4j/neo4j-python-driver/blob/6.x/CHANGELOG.md (neo4j 6 breaking changes)
- https://github.com/redis/redis-vl-python (redisvl README, SemanticCache)
- https://github.com/tobymao/sqlglot (sqlglot)
- https://developers.openai.com/api/docs/guides/embeddings.md (OpenAI embeddings: dims, `dimensions=`, "normalized to length 1")
