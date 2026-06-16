# Track 6 — Repurpose specs (for sign-off before authoring)

Three days repurposed **in place** to close the highest-priority content gaps from
`CURRICULUM_REPORT.md`. **No renumbering** — each keeps its day number. Each repurpose
**deletes a working lesson** and authors a new one, so this needs your approval first.

Shared rules for all three:
- Full lesson structure per CLAUDE.md §4 (SWE callout → prose + 1 diagram → runnable
  code with `script_id` → Summary → Quick Reference → Exercises w/ collapsible solutions
  → Checkpoint → What's Next), 400–650 line band.
- **All code verified against current library docs before writing** (CLAUDE.md §5) —
  the APIs below are the intended surface, confirmed at authoring time, not assumed.
- Update the day's **folder slug + filename** to the new topic, the **`index.md`** entry,
  neighbour **"What's Next"** footers, and `REFERENCE.md`/`GLOSSARY.md` if terms are added.
- Add a CHANGELOG entry.

---

## Spec A — Day 046: `database_storage` → **Agent Memory & Context Budgeting**

**Why safe to repurpose:** D046 ("Storing Conversations in SQLite & PostgreSQL", 652 lines)
substantially duplicates **D044**'s `## Database Persistence` section (SQLite + Postgres
conversation stores). D044 remains the canonical home for persistence.

**What's lost:** D046's standalone SQLite/Postgres CRUD walkthrough. Mitigation: keep the
canonical version in D044; add a one-line pointer from D044 to "memory architecture (D46)".

**New topic:** multi-layer agent memory + token-budget allocation — a daily production
need only partially covered today (only conversation-window memory exists).

**Outline:**
1. SWE callout — memory tiers ≈ CPU registers / RAM / disk; context budget ≈ heap allocation.
2. The three layers: short-term (recent turns), working (session facts), long-term
   (persistent user/profile + domain facts). Diagram.
3. Token-budget allocation: given a 200K window, split system+tools / history / retrieved
   context / new query; detect overflow; shrink strategy (drop oldest, summarize, evict).
4. Summarize-history pattern (compress every N turns with an LLM call).
5. Production storage: Redis (low-latency working memory) vs SQLite (offline/dev) — brief.
6. Checkpoint, Summary, QR, Exercises.

**Libraries/APIs:** Python stdlib + `tiktoken` (OpenAI token counts) / provider
`count_tokens` for Claude; optional `redis` client shown minimally. No exotic APIs — low
verification risk. Reuses concepts from D33 (cost), D36 (history).

**Links:** from D044 footer ("memory architecture: D46"); D46 What's Next → D47.

---

## Spec B — Day 067: `api_key_security` → **PII & Data Privacy in RAG/Agents**

**Why safe to repurpose:** D067 ("API Key Security", 556 lines) overlaps **D066** (Docker
Sandboxing Pt 2), which already teaches secrets injection / env-vars / secrets managers.

**What's lost:** the dedicated API-key day. Mitigation: keep D066's secrets coverage; add
a short "don't hardcode keys; use env/secrets managers" recap there + a pointer.

**New topic:** PII handling across the RAG lifecycle — a hard requirement for
healthcare/fintech, currently only touched at output (D63 sanitization). Prevent at
ingestion/retrieval, not just output.

**Outline:**
1. SWE callout — PII handling ≈ input validation + data-retention policy + field-level
   encryption; "don't log secrets" generalized to "don't embed/retrieve PII you shouldn't."
2. PII detection: Microsoft **Presidio** (`AnalyzerEngine`/`AnonymizerEngine`) + spaCy NER.
3. Redaction strategies: pre-embedding masking (scrub before chunking) vs post-retrieval
   filtering (mask in context). Diagram of where each sits in the RAG flow.
4. Retrieval filtering by user scope / classification (don't retrieve another tenant's docs).
5. Retention & deletion: GDPR "delete my data" — purge source, embeddings, and caches.
6. Compliance checklist (GDPR/HIPAA/PCI) — directional, with "consult counsel" caveat.
7. Checkpoint, Summary, QR, Exercises.

**Libraries/APIs:** `presidio-analyzer`, `presidio-anonymizer`, `spacy` (en_core_web_lg).
**Verification needed:** confirm current Presidio `analyze()`/`anonymize()` signatures
before writing (flagged per CLAUDE.md §5). Ties into D22/D23 (pgvector), D62/D63 (security).

**Links:** from D062 (Prompt Injection) or D026 (Context Injection); D67 What's Next → D68.

---

## Spec C — Day 092: `model_fallback_strategies` → **Retrieval Evaluation & Reranking**

**Why safe to repurpose:** D092 ("Model Fallback Strategies", 494 lines) re-teaches the
circuit-breaker / resilience patterns that **D090** (Rate Limits & Backoffs) owns; the
unique "provider fallback chain" bit folds into D082 (Distillation & Routing) or D090.

**What's lost:** the standalone provider-fallback day. Mitigation: a brief
provider-fallback subsection + pointer in D090/D082.

**New topic:** a unified retrieval-evaluation workflow + reranking depth — currently
scattered across D23 (metrics in isolation), D26 (reranking sidebar), D60 (RAGAS).

**Outline:**
1. SWE callout — retrieval eval ≈ a test suite for search; reranking ≈ precise sort after a
   cheap approximate filter.
2. Metrics with worked examples: precision@k, recall@k, NDCG, MRR, MAP — and the answer-key
   (labeled relevant doc IDs) you measure against. Builds on D23.
3. Diagnosing "why is my RAG bad?" — is retrieval bad, or context injection bad? Decision tree.
4. Reranking: cross-encoder (`sentence-transformers` `CrossEncoder`), optional Cohere Rerank
   (managed); benchmark rerank vs no-rerank on the metrics above.
5. Hybrid search decision tree (BM25 / semantic / both).
6. Checkpoint, Summary, QR, Exercises.

**Libraries/APIs:** `numpy` (metrics), `sentence-transformers` `CrossEncoder(model).predict([(q,d),...])`,
optional `cohere` ClientV2 rerank. **Verification needed:** confirm current
`sentence-transformers` CrossEncoder + Cohere rerank signatures before writing. Note: D026's
reranking section then trims to a pointer here (also helps D026's length).

**Links:** from D026 (Context Injection) "What's Next" / reranking pointer; D92 What's Next → D93.

---

## Sequencing & effort

Suggested order: **C (D092 reranking)** → **A (D046 memory)** → **B (D067 PII)**.
C also unblocks the remaining D026 length trim. Each is ~1 lesson of authoring +
verification + checker + neighbour/index updates; I'll do them one at a time, commit each,
and you review per lesson. Folder-rename decision per day: **recommended** (slug should
match topic) — it changes the folder path + `index.md` link + `script_id` prefixes, all
contained to that day.
