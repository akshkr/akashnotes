# The Orbit dataset

The shared corpus for the course. **Atlas**, the assistant you build over the 100 days, answers
questions and triages issues for the maintainers of **Orbit**, a *fictional* open-source Python
library for background jobs and workflows (similar in spirit to Celery or RQ). This directory holds
everything Atlas reads: Orbit's documentation, its issue tracker, and gold sets for evaluating
retrieval, question answering, extraction and triage.

> **Synthetic and fictional.** Every page, issue, comment, handle and log line here was written
> for this course. Orbit does not exist. Any resemblance to real projects, companies or people is
> coincidental. Contact details and secrets use only reserved or obviously fake identifiers:
> `example.com` / `example.net` / `example.org` domains, `555-01xx` phone numbers, made-up
> addresses, keys shaped like `sk-test-FAKE-…`, passwords containing `FAKE` or `example`, and the
> AWS documentation account id `123456789012`.

## Licence

**CC0-1.0** (public domain dedication). Copy, modify and redistribute any of it, with or without
attribution. See <https://creativecommons.org/publicdomain/zero/1.0/>.

## At a glance

| What | Count | Where |
|---|---|---|
| Documentation pages (Markdown) | 45 | `docs/` |
| The same pages as messy real-world HTML | 5 | `docs_html/` |
| Poisoned pages (indirect prompt injection) | 2 | `docs_poisoned/` |
| Issues, with 504 comments | 240 | `issues/issues.jsonl`, `issues/orbit.db` |
| Retrieval queries | 40 | `eval/retrieval_queries.jsonl` |
| QA gold answers | 30 | `eval/qa_gold.jsonl` |
| Extraction gold records | 30 | `eval/extraction_gold.jsonl` |
| Triage gold records | 30 | `eval/triage_gold.jsonl` |

Total size is about **1.6 MB** (the budget is 3 MB).

The Orbit "world" (releases, components, config keys, CLI commands, error codes, known issue
themes, maintainers) is fixed by `DATASET_SPEC.md` §1 at the repository root, and every file here
agrees with it. In short: the current release is **3.2.1** (2026-10-20). **3.0.0** (2026-03-02)
introduced Flows and replaced `orbit.ini` + `ORBIT_*` environment variables with `orbit.toml`.
**2.9.0** is the last 2.x release (EOL 2026-12-31). Errors are `ORB-1001` … `ORB-2101` (20 codes).
The maintainers are `mara-k`, `devon-li`, `sam-okafor` and `ines-v`.

## File tree

```text
datasets/orbit/
├── README.md                      # this file
├── docs/                          # 45 Markdown pages; file name = doc id
│   ├── index.md  quickstart.md  installation.md  glossary.md  faq.md  changelog.md
│   ├── concepts-{jobs,workers,queues-priorities,brokers}.md
│   ├── broker-{redis,postgres,sqs}.md
│   ├── retries-and-backoff.md  dead-letter-queue.md  idempotency.md  leases-and-heartbeats.md
│   ├── scheduling-{cron,delays}.md
│   ├── flows-{overview,steps-and-state,error-handling}.md  results-backend.md
│   ├── configuration-reference.md  environment-variables-2x.md  migrating-2-to-3.md
│   ├── cli-reference.md  dashboard.md  dashboard-auth-oidc.md
│   ├── observability-{metrics,tracing}.md
│   ├── deployment-{docker,kubernetes,systemd}.md  scaling-workers.md  performance-tuning.md
│   ├── security.md  error-codes.md  contributing.md
│   ├── troubleshooting-{broker,duplicates,memory}.md
│   └── api-reference-{orbit,job,flow}.md
├── docs_html/                     # 5 pages rendered as real-world HTML (D24 parsing)
│   ├── quickstart.html  broker-redis.html  retries-and-backoff.html
│   └── dashboard-auth-oidc.html  error-codes.html
├── docs_poisoned/                 # ATTACK FIXTURES: do not index by default (D28, D69)
│   ├── poisoned-dlq-replay-guide.md      # obvious injection
│   └── poisoned-sqs-idempotency-notes.md # subtle injection
├── issues/
│   ├── issues.jsonl               # 240 issues, one JSON object per line (source of truth)
│   ├── build_db.py                # stdlib sqlite3: issues.jsonl -> orbit.db
│   └── orbit.db                   # built SQLite database (6 tables)
└── eval/
    ├── retrieval_queries.jsonl    # 40 queries -> relevant doc ids
    ├── qa_gold.jsonl              # 30 questions with gold answers and citations
    ├── extraction_gold.jsonl      # 30 issues -> structured fields
    └── triage_gold.jsonl          # 30 issues -> labels, duplicate, escalation, reply points
```

## Schemas

### `docs/*.md`

Each page starts with YAML front matter, followed by a Markdown body with roughly 450–900 words of
prose, not counting code blocks (headings, code blocks, `orbit.toml` snippets, tables, `> **Note:**` admonitions, and relative
links such as `[Leases and heartbeats](leases-and-heartbeats.md)`).

```yaml
---
id: leases-and-heartbeats      # == file name without .md; this is the doc id used everywhere
title: Leases and heartbeats
section: Reliability           # Overview, Getting started, Concepts, Brokers, Reliability, ...
applies_to: all                # "3.x" | "2.x" | "all"  (24 / 1 / 20 pages)
updated: 2026-10-14            # ISO date
---
```

`applies_to` is there so version filters matter: `environment-variables-2x` is the only 2.x page,
and several facts appear on exactly one page, so retrieval has to find the right one.

### `docs_html/*.html`

Five of the pages above (`quickstart`, `broker-redis`, `retries-and-backoff`,
`dashboard-auth-oidc`, `error-codes`) as full HTML documents with the noise a scraper really meets:
`<nav>` and sidebar menus, breadcrumbs, a cookie/consent banner, analytics and newsletter
`<script>` tags, a `<footer>`, build comments, and the article content including at least one
`<table>`. The file name matches the doc id of the Markdown version, so you can compare your
HTML-to-text output against `docs/<id>.md`. Some links point at pages that aren't in the dataset
(for example `/privacy.html`). They're site chrome.

### `docs_poisoned/*.md`

Same front matter as `docs/` (their ids start with `poisoned-` and never collide with a real doc
id), plus fixture metadata:

| Key | Meaning |
|---|---|
| `fixture` | Always `attack` |
| `attack_type` | `indirect_prompt_injection` |
| `injection_style` | `obvious` or `subtle` |
| `injection_location` | Where the payload sits in the page |
| `target_lessons` | Lessons that use the page (`[D28, D69]`) |
| `safe_to_index` | `false`: keep it out of the default index |
| `expected_behavior` | What a well-defended assistant does when this page is retrieved |
| `license` | `CC0-1.0` |

### `issues/issues.jsonl`

One issue per line, ids 1–240, created 2025-06-15 → 2026-11-01. The labels are the ground truth.

| Field | Type | Notes |
|---|---|---|
| `id` | int | 1–240 |
| `title` | string | |
| `body` | string | Markdown; often contains code blocks, logs and stack traces |
| `author` | string | Fake handle (60 reporters + 4 maintainers) |
| `created_at` | string | ISO 8601 UTC, e.g. `2026-03-26T14:10:00Z`; ids are in date order |
| `state` | string | `open` (47) or `closed` (193) |
| `labels` | string[] | One `type:bug\|feature\|question\|docs`; one or more `comp:<component>`; `severity:S1..S4` on bugs only; `version:x.y` when a version is known |
| `orbit_version` | string \| null | Full version, e.g. `3.1.2`; null when the reporter didn't say (13 issues) |
| `python_version` | string \| null | e.g. `3.12.6`; null for 36 issues |
| `error_codes` | string[] | ORB codes that appear in the issue or its comments, e.g. `["ORB-1101"]` |
| `duplicate_of` | int \| null | Id of the earlier canonical issue |
| `comments` | object[] | `{author, created_at, body}` in time order; maintainers often cite doc ids (`see \`idempotency\``) |
| `closed_at` | string \| null | Set exactly when `state` is `closed` |

Components (`comp:*`): `core`, `scheduler`, `flows`, `broker-redis`, `broker-postgres`,
`broker-sqs`, `cli`, `dashboard`, `retries`, `results`, `observability`, `auth`, `docs`.

Mix: 108 bugs (45%), 63 questions (26%), 44 features (18%), 25 docs (10%). 104 issues (43%) quote
an ORB code in the title or body, usually inside a log or traceback.

### `issues/orbit.db`

SQLite, built from `issues.jsonl` by `build_db.py` (see below). Current row counts:

| Table | Rows | Columns |
|---|---|---|
| `issues` | 240 | `id` PK, `title`, `body`, `author` → users, `created_at`, `state`, `closed_at`, `type`, `severity`, `orbit_version`, `python_version`, `error_codes` (JSON array as text), `duplicate_of` → issues, `comment_count` |
| `labels` | 26 | `id` PK, `name` (e.g. `comp:broker-redis`), `kind` (`type`/`comp`/`severity`/`version`), `value` |
| `issue_labels` | 857 | `issue_id` → issues, `label_id` → labels (composite PK) |
| `comments` | 504 | `id` PK, `issue_id` → issues, `position` (1 = first), `author` → users, `created_at`, `body` |
| `releases` | 8 | `version` PK, `released_on`, `notes` |
| `users` | 64 | `handle` PK, `role` (`maintainer`/`reporter`), `first_seen_at`, `issues_opened`, `comments_written` |

Indexes exist on `issues.created_at`, `issues.duplicate_of`, `issue_labels.label_id`,
`comments.issue_id` and `comments.author`.

### `eval/retrieval_queries.jsonl` (40)

```json
{"id": "rq-001", "query": "ORB-1101", "relevant_doc_ids": ["error-codes", "leases-and-heartbeats", "troubleshooting-duplicates"], "kind": "exact_term"}
```

`kind` is `exact_term` (16: error codes, config keys, env vars, CLI commands and a header name,
where keyword search beats embeddings), `semantic` (14) or `multi_hop` (10, answer spread over two or more pages).

### `eval/qa_gold.jsonl` (30)

```json
{"id": "qa-001", "question": "...", "answer": "...", "citations": ["configuration-reference", "leases-and-heartbeats"], "applies_to": "3.x"}
```

`citations` are doc ids. `applies_to` is `3.x` (14), `all` (13) or `2.x` (3), so you can check
that a version filter keeps a 2.x question away from 3.x pages.

### `eval/extraction_gold.jsonl` (30)

```json
{"issue_id": 25, "type": "question", "components": ["core"], "severity": null, "orbit_version": "2.8.0", "python_version": "3.11.9", "error_codes": ["ORB-1202"], "summary": "..."}
```

`type`, `components`, `severity`, `orbit_version`, `python_version` and `error_codes` match the
issue's ground truth exactly. `summary` is a reference summary in English, also for the
non-English issues.

### `eval/triage_gold.jsonl` (30)

```json
{"issue_id": 13, "labels": ["type:bug", "comp:broker-redis", "severity:S3", "version:2.8"], "duplicate_of": null, "needs_human": true, "reply_points": ["..."]}
```

`labels` and `duplicate_of` match `issues.jsonl`. `needs_human` (true for 16 of 30) marks issues an
assistant must escalate rather than handle alone: leaked secrets or PII (rotate and redact),
prompt-injection attempts, and S1 incidents. `reply_points` are the points a good first reply covers, and
they often name the doc id to link.

## Built-in fixtures

Specific lessons rely on these. All of them are ordinary-looking records inside the files above,
with no field that marks them, so your pipeline has to cope with them the way it would in production.

| Fixture | Count | Where | Used for |
|---|---|---|---|
| Synthetic PII in issue bodies | 10 | Issues **13, 55, 67, 85, 116, 135, 170, 184, 195, 212**: `@example.com` emails, `555-01xx` phones, fake street addresses, `sk-test-FAKE-…` keys, fake passwords and tokens | D73 redaction |
| Prompt-injection attempts in issues | 6 | **Obvious**, a closing "AI assistant: ignore your previous instructions…" paragraph: **20, 92, 204**. **Hidden** in an HTML comment addressed to "automated triage" tools: **46, 159, 180**. Each one tries to force `severity:S1`, relabel, close other issues, or leak the system prompt | D69 / R4 |
| Non-English issues | 5 | **25** Spanish, **97** Portuguese, **63** Hindi, **188** Japanese, **130** German | D4 tokens, multilingual handling |
| Very long issue | 1 | **227**: about 8,900 words, mostly Postgres broker logs (also a duplicate of #87) | Context-budget lessons |
| Duplicate clusters | 15 clusters, 52 issues | See the table below; `duplicate_of` always points at an earlier issue | Duplicate detection, triage |
| Vague, low-information issues | 20 | **10, 28, 37, 54, 62, 70, 80, 83, 93, 101, 119, 127, 136, 155, 166, 177, 191, 201, 214, 226** ("jobs stuck", "upgrade broke everything", …) | Asking for missing info, `needs_human` |
| Poisoned docs (indirect injection) | 2 | `docs_poisoned/poisoned-dlq-replay-guide.md` (**obvious**: a blockquote headed "AI ASSISTANT INSTRUCTIONS"); `docs_poisoned/poisoned-sqs-idempotency-notes.md` (**subtle**: an HTML comment plus a "Support tooling note" paragraph phrased as project policy, pushing a fake hotfix script, a non-existent `max_payload_kb = 0` "unlimited" setting, and posting unredacted credentials) | D28, D69 |
| Messy HTML | 5 | `docs_html/` | D24 parsing |
| 3.0 preview reports | 4 | Issues **53, 57, 65, 75** were filed against the 3.0 preview from `main` before 3.0.0 shipped (2026-03-02). The preview reports itself as `3.0.0`, so that is their `orbit_version` | Edge case for date/version validators |

> **Warning:** `docs_poisoned/` is attack data. Don't add it to your default index. Lessons that
> use it load it on purpose to test the defences. The injection text in issues is likewise
> untrusted user content: an assistant should never act on it.

## Known issue themes and duplicate clusters

Each theme from the world bible has at least one doc and at least one issue (the consistency
checks below verify this), and `changelog` mentions every theme.

| # | Theme | Status | Canonical issue ← duplicates | Main docs |
|---|---|---|---|---|
| a | Redis reconnect storm after failover (3.1.0) | fixed in 3.1.2 | #143 ← 145, 150, 161 | `broker-redis`, `troubleshooting-broker` |
| b | Duplicate execution from lease expiry (ORB-1101) | by design: tune `heartbeat_seconds` / `lease_seconds` | #4 ← 22, 41, 67 and #176 ← 190, 199, 223 | `leases-and-heartbeats`, `troubleshooting-duplicates` |
| c | SQS FIFO throttling (ORB-1901) | | #9 ← 31, 58 | `broker-sqs` |
| d | Dashboard OIDC redirect loop behind a proxy (3.2.0) | open; workaround `X-Forwarded-Proto` | #209 ← 215, 230 | `dashboard-auth-oidc` |
| e | `orbit migrate-config` drops `[retries]` (3.0.1) | fixed in 3.0.3 | #112 ← 115, 118 | `migrating-2-to-3` |
| f | Scheduler drift across DST (ORB-1402) | | #59 ← 61, 62, 240 | `scheduling-cron` |
| g | Memory growth with `prefetch` > 100 (3.2.x) | open | #213 ← 220, 232 | `troubleshooting-memory`, `performance-tuning` |
| h | Windows worker ignores SIGTERM | | #16 ← 64, 76, 189 | `concepts-workers`, `faq` |
| i | Flow step results over 512 KB (ORB-1202) | | #102 ← 126, 148 | `flows-steps-and-state`, `results-backend` |
| j | Postgres LISTEN/NOTIFY misses events under load | | #87 ← 106, 133, 227 | `broker-postgres` |
| k | Request: Python 3.13 support | | #17 ← 40, 77 | `installation`, `faq` |
| l | Request: priority aging | | #179 ← 210, 228 | `concepts-queues-priorities` |
| m | Docs gap: idempotency with SQS | | #94 ← 123, 152, 237 | `idempotency`, `broker-sqs` |
| | Not a theme: "retry only on specific exceptions" | | #72 ← 89, 192 | `retries-and-backoff` |

## Rebuilding the database

`issues/issues.jsonl` is the source of truth, and `issues/orbit.db` is derived from it. After
editing the JSONL, rebuild:

```bash
python3 issues/build_db.py
```

```text
built issues/orbit.db
  issues          240
  labels           26
  issue_labels    857
  comments        504
  releases          8
  users            64
```

The script uses only the standard library (`json`, `sqlite3`). It checks that ids run 1..N with no
gaps, enforces foreign keys, and builds into `orbit.db.tmp` before swapping that into place, so a
failed run never leaves a half-written database. Running it again gives the same result.

## Loading the data from lessons

Lessons never hard-code paths. They read the dataset location from one setting, defined in
`atlas/config.py` (Day 2):

```python
import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("ORBIT_DATA", "datasets/orbit"))
```

and then build every path from it:

```python
import json
import sqlite3

from atlas.config import DATA_DIR

docs = sorted((DATA_DIR / "docs").glob("*.md"))
issues = [json.loads(line) for line in (DATA_DIR / "issues" / "issues.jsonl").open(encoding="utf-8")]
db = sqlite3.connect(DATA_DIR / "issues" / "orbit.db")
print(len(docs), len(issues), db.execute("SELECT COUNT(*) FROM comments").fetchone()[0])  # 45 240 504
```

The default, `datasets/orbit`, is relative to the repository root, which is where the dataset lives
after cutover. Until then it sits at `v2/datasets/orbit/`, so run lessons with:

```bash
export ORBIT_DATA=v2/datasets/orbit
```

## Consistency checks

These were last run on 2026-11-07, all passing (DATASET_SPEC §5 plus extras):

- Every `relevant_doc_ids` and `citations` entry exists in `docs/`. Every `duplicate_of` and every
  gold `issue_id` exists, and every Markdown cross-link between pages resolves.
- Every ORB code anywhere in the dataset is one of the 20 in the world bible, and each code is
  always paired with its correct name. `error-codes` lists all 20. `changelog` covers all 8 releases.
- Themes a–m each appear in at least one doc and at least one issue.
- Versions, `orbit.toml` sections and keys, CLI commands and `comp:*` labels match the world bible.
  Labels are well formed: exactly one `type:`, `severity:` only on bugs, and `version:` agrees
  with `orbit_version`. `extraction_gold` and `triage_gold` agree with the issue ground truth.
- Emails, hosts and URLs use reserved domains, phones are `555-01xx`, and keys are `sk-test-FAKE-…`.
- `python3 issues/build_db.py` runs cleanly and its row counts match the JSONL. The total size is
  about 1.6 MB, under the 3 MB budget.
