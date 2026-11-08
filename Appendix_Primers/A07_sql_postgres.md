# SQL & Postgres

Atlas keeps Orbit's 240 issues and their labels in a database. From [Day 26: Vector Search with pgvector](../Phase_3_RAG/Day_026_pgvector_search/pgvector_search.md) you store embeddings in Postgres, and in [Day 33: RAG over Structured Data: Text-to-SQL, Tables & Graphs](../Phase_3_RAG/Day_033_text_to_sql/text_to_sql.md) a model writes SQL for you, which you can only trust if you can read it. This primer teaches the SQL the course uses, first on SQLite (built into Python) and then on Postgres.

## Who this is for

- **Read this if** you have never written SQL, or have forgotten it. Read it before Day 26. It takes about 35 minutes, including running the code.
- **Skip it if** you can answer the five [Self-Check](#self-check) questions without peeking.
- **You need:** Python 3.11+. The SQLite sections need no installs, API keys or services. The Postgres section needs `uv add "psycopg[binary]"` and a running Postgres server; [Primer A08: Docker & compose](A08_docker_compose.md) shows how to start one.

> **Coming from Software Engineering?** You may know databases through an ORM (a library that maps classes to tables, such as SQLAlchemy or Django models). This primer drops one layer lower, because pgvector queries and model-written SQL are raw SQL. Fast path: read the placeholder pitfall in the reading section, the upsert in the writing section, and the sqlite3-vs-psycopg table at the end. Transactions work the way you expect: a `with` block commits on success and rolls back on an exception.

## Tables, rows and keys

**The problem.** Say the issues live in `issues.jsonl` and you want "open scheduler bugs, newest first". You load all 240 records, filter and sort them, and write a new loop for every new question. Two scripts writing the file at once can also corrupt it.

**The intuition.** A database is a set of spreadsheet tabs with strict rules. Every tab has fixed columns, every cell in a column holds the same type, and you ask questions in SQL (Structured Query Language) instead of writing the loop yourself. You describe *which* rows you want, and the database works out *how* to find them.

**A tiny example.** Here is a four-row `issues` table, a cut-down copy of Orbit's:

| id | title | state | orbit_version | created_at |
|---|---|---|---|---|
| 101 | Redis reconnect storm after failover | closed | 3.1.0 | 2026-06-12 |
| 102 | Job runs twice on long tasks (ORB-1101) | open | 3.2.0 | 2026-09-30 |
| 103 | Scheduler drifts an hour after DST | open | 3.1.2 | 2026-10-27 |
| 104 | Docs: idempotency keys with SQS | open | 3.2.1 | 2026-10-29 |

The query `SELECT id FROM issues WHERE state = 'open'` reads as "give me the id of every row whose state is open". Check it by eye: 102, 103 and 104.

**Name the parts.**

| Term | Plain meaning | Orbit example |
|---|---|---|
| table | a named grid of rows with fixed columns | `issues`, `labels` |
| row | one record | issue 102 |
| column | one named, typed field | `state`, stored as TEXT |
| primary key | a column that is unique per row, so it identifies the row | `issues.id` |
| foreign key | a column holding another table's primary key, which links the two tables | `issue_labels.issue_id` holds an `issues.id` |

An issue has many labels, and a label is used by many issues, so neither table can store the other's id in one column. A third table, `issue_labels`, holds one row per (issue, label) pair. The real `orbit.db` uses the same layout, plus `comments`, `releases` and `users` tables.

```mermaid
flowchart LR
    I["issues<br/>id (primary key), title, state, ..."]
    IL["issue_labels<br/>issue_id, label_id"]
    L["labels<br/>id (primary key), name"]
    IL -- "issue_id points at" --> I
    IL -- "label_id points at" --> L
```

**Look at the real database.** Run this from the repo root. It opens the course's SQLite file read-only, lists the tables, counts the issues, and tries a `DELETE` to prove the file is protected:

```python
# script_id: primer_a07/orbit_db_peek
# Install: nothing (sqlite3 ships with Python). Env: ORBIT_DATA (optional). Services: none.
import os
import sqlite3
from pathlib import Path

DATA_DIR = Path(os.environ.get("ORBIT_DATA", "datasets/orbit"))
db_path = DATA_DIR / "issues" / "orbit.db"
if not db_path.exists():
    raise SystemExit(f"{db_path} not found: build it with python {DATA_DIR}/issues/build_db.py")

# mode=ro opens the file read-only, so a typo here can't damage the shared course data
conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
tables = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
print([name for (name,) in tables])
print(conn.execute("SELECT COUNT(*) FROM issues").fetchone()[0], "issues")
try:
    conn.execute("DELETE FROM issues")
except sqlite3.OperationalError as exc:
    print(exc)
conn.close()
```

```text
['comments', 'issue_labels', 'issues', 'labels', 'releases', 'users']
240 issues
attempt to write a readonly database
```

To see a table's columns, run `PRAGMA table_info(issues)` the same way. The rest of this primer uses a scratch copy of three tables in memory, so you can update and delete rows without touching the course data.

## Reading data: SELECT, WHERE, ORDER BY, LIMIT

**The problem.** Atlas's daily digest needs "the two newest open issues". Rather than fetching every row and sorting in Python, you want the database to filter and sort, and send back only two rows.

**The intuition.** A `SELECT` is a funnel. You write the clauses in one order, but the database applies them in the order below: pick rows, choose columns, sort, cut.

```mermaid
flowchart LR
    F["FROM / JOIN<br/>pick the tables"] -- "all rows" --> W["WHERE<br/>keep matching rows"]
    W -- "fewer rows" --> G["GROUP BY<br/>bucket rows (optional)"]
    G --> S["SELECT<br/>choose columns"]
    S --> O["ORDER BY<br/>sort"]
    O -- "sorted rows" --> L["LIMIT<br/>keep the first N"]
```

**A tiny example.** Work through `SELECT id, title FROM issues WHERE state = 'open' ORDER BY created_at DESC LIMIT 2` on the four-row table. `WHERE` keeps 102, 103 and 104. `ORDER BY created_at DESC` (newest first) gives 104, 103, 102. `LIMIT 2` keeps 104 and 103.

**Name the parts.** `SELECT` lists the columns you want (`*` means all). `WHERE` takes a condition built from `=`, `<>` (not equal), `<`, `>`, `AND`, `OR`, `IN ('a', 'b')` and `LIKE 'comp:%'`, where `%` matches any text. `ORDER BY col DESC` sorts newest or largest first (`ASC`, the default, is the reverse). `LIMIT n` keeps the first n rows. Text values go in single quotes.

**Runnable code.** This block builds the scratch database. Every later block in this primer with the same `script_id` continues the same file.

```python
# script_id: primer_a07/orbit_sqlite
# Install: nothing (sqlite3 ships with Python 3.11+). Env: none. Services: none.
import sqlite3

conn = sqlite3.connect(":memory:")  # a throwaway DB that lives in RAM
conn.executescript("""
CREATE TABLE issues (
    id            INTEGER PRIMARY KEY,
    title         TEXT NOT NULL,
    state         TEXT NOT NULL,      -- 'open' or 'closed'
    orbit_version TEXT,
    created_at    TEXT NOT NULL       -- ISO-8601 text sorts in date order
);
CREATE TABLE labels (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE issue_labels (
    issue_id INTEGER NOT NULL REFERENCES issues (id),
    label_id INTEGER NOT NULL REFERENCES labels (id),
    PRIMARY KEY (issue_id, label_id)  -- one row per (issue, label) pair
);
""")
conn.executemany(
    "INSERT INTO issues (id, title, state, orbit_version, created_at) VALUES (?, ?, ?, ?, ?)",
    [
        (101, "Redis reconnect storm after failover", "closed", "3.1.0", "2026-06-12"),
        (102, "Job runs twice on long tasks (ORB-1101)", "open", "3.2.0", "2026-09-30"),
        (103, "Scheduler drifts an hour after DST", "open", "3.1.2", "2026-10-27"),
        (104, "Docs: idempotency keys with SQS", "open", "3.2.1", "2026-10-29"),
    ],
)
conn.executemany("INSERT INTO labels (id, name) VALUES (?, ?)",
                 [(1, "type:bug"), (2, "type:docs"), (3, "comp:scheduler"), (4, "comp:broker-redis")])
conn.executemany("INSERT INTO issue_labels (issue_id, label_id) VALUES (?, ?)",
                 [(101, 1), (101, 4), (102, 1), (103, 1), (103, 3), (104, 2)])
conn.commit()
print(conn.execute("SELECT COUNT(*) FROM issues").fetchone())
```

```text
(4,)
```

Now the digest query. The `?` marks are placeholders: the driver sends the values separately from the SQL text.

```python
# script_id: primer_a07/orbit_sqlite
def issues_by_state(state: str, limit: int = 2) -> list[tuple]:
    # ? placeholders keep values out of the SQL text, so input can't rewrite the query
    return conn.execute(
        "SELECT id, title FROM issues WHERE state = ? ORDER BY created_at DESC LIMIT ?",
        (state, limit),
    ).fetchall()

for row in issues_by_state("open"):
    print(row)
```

```text
(104, 'Docs: idempotency keys with SQS')
(103, 'Scheduler drifts an hour after DST')
```

Each row is a tuple in `SELECT` column order, and the answer matches your hand-worked one.

**Break it.** The parameters must be a tuple, even for one value. Pass `"open"` instead of `("open",)` and sqlite3 treats the string as four separate values, one per character:

```text
sqlite3.ProgrammingError: Incorrect number of bindings supplied. The current statement uses 1, and there are 4 supplied.
```

The worse mistake gives no error at all. Building SQL with an f-string lets the input become part of the query. This is SQL injection, and it matters again in Day 33, where a model writes the SQL:

```python
# script_id: primer_a07/orbit_sqlite
evil = "nope' OR '1'='1"
unsafe = conn.execute(f"SELECT id FROM issues WHERE state = '{evil}'").fetchall()
safe = conn.execute("SELECT id FROM issues WHERE state = ?", (evil,)).fetchall()
print("f-string:   ", unsafe)  # the input became part of the SQL
print("placeholder:", safe)    # the input stayed a value
```

```text
f-string:    [(101,), (102,), (103,), (104,)]
placeholder: []
```

The f-string turned the condition into `state = 'nope' OR '1'='1'`, which is true for every row. The placeholder version searched for that literal string and found nothing. Use placeholders for every value.

## Joining tables: JOIN and GROUP BY

**The problem.** Labels live in their own table. "Which component labels does each issue have?" needs data from three tables at once.

**The intuition.** A `JOIN` lays rows from two tables side by side wherever a condition holds, like a spreadsheet lookup that pulls a matching row from another tab.

**A tiny example.** Issue 103 appears twice in `issue_labels`, with label ids 1 and 3. Joining those rows to `labels` turns the ids into `type:bug` and `comp:scheduler`. Keep only names that start with `comp:` and you get one row: (103, 'comp:scheduler').

**Name the parts.** `JOIN other ON condition` is an inner join: it keeps only pairs of rows where the condition is true. `AS i` gives a table a short alias. `LEFT JOIN` also keeps rows from the left table that have no match, and fills the missing columns with `NULL`, SQL's marker for "no value". `GROUP BY col` puts rows into buckets, and `COUNT(*)` counts the rows in each bucket.

```python
# script_id: primer_a07/orbit_sqlite
rows = conn.execute("""
    SELECT i.id, l.name
    FROM issues AS i
    JOIN issue_labels AS il ON il.issue_id = i.id
    JOIN labels AS l        ON l.id = il.label_id
    WHERE l.name LIKE 'comp:%'
    ORDER BY i.id
""").fetchall()
print(rows)

per_label = conn.execute("""
    SELECT l.name, COUNT(*) AS n
    FROM labels AS l
    JOIN issue_labels AS il ON il.label_id = l.id
    GROUP BY l.name
    ORDER BY n DESC, l.name
""").fetchall()
print(per_label)
print(conn.execute("SELECT COUNT(*) FROM issues JOIN labels").fetchone())  # no ON: see below
```

```text
[(101, 'comp:broker-redis'), (103, 'comp:scheduler')]
[('type:bug', 3), ('comp:broker-redis', 1), ('comp:scheduler', 1), ('type:docs', 1)]
(16,)
```

**Break it.** The last line forgot the `ON` condition, so SQLite paired every issue with every label (4 × 4 = 16 rows) without an error. Postgres rejects a `JOIN` without `ON`, but the comma form `FROM issues, labels` gives the same product in both. When a join returns far more rows than expected, check the `ON` clauses first.

## Changing data: UPDATE, DELETE, transactions and upserts

**The problem.** Removing a spam issue takes two statements: delete its label rows, then the issue. If the script crashes between them, the database is left half-changed.

**The intuition.** A transaction is a bank transfer: the debit and the credit happen together, or neither happens.

**A tiny example.** Delete issue 103's two label rows, then issue 103, and crash before saving. After the rollback, all three rows are back.

**Name the parts.** `INSERT INTO t (cols) VALUES (...)` adds rows (you saw it above). `UPDATE t SET col = value WHERE ...` changes rows, and `DELETE FROM t WHERE ...` removes them. A **transaction** groups statements; **commit** saves them all and **rollback** undoes them all. In sqlite3, `with conn:` commits when the block finishes and rolls back if it raises.

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> InTransaction: first INSERT, UPDATE or DELETE (BEGIN)
    InTransaction --> InTransaction: more statements
    InTransaction --> Idle: COMMIT (changes saved)
    InTransaction --> Idle: ROLLBACK or exception (changes undone)
```

```python
# script_id: primer_a07/orbit_sqlite
with conn:  # commits if the block succeeds, rolls back if it raises
    conn.execute("UPDATE issues SET state = 'closed' WHERE id = ?", (104,))

try:
    with conn:
        conn.execute("DELETE FROM issue_labels WHERE issue_id = ?", (103,))
        conn.execute("DELETE FROM issues WHERE id = ?", (103,))
        raise RuntimeError("worker crashed before commit")  # simulate a failure
except RuntimeError as exc:
    print("rolled back:", exc)

print(conn.execute("SELECT id, state FROM issues ORDER BY id").fetchall())
```

```text
rolled back: worker crashed before commit
[(101, 'closed'), (102, 'open'), (103, 'open'), (104, 'closed')]
```

**Break it.** Drop the `WHERE` and `UPDATE issues SET state = 'closed'` closes every issue, with no warning. Write the `WHERE` first, and run it as a `SELECT` to see which rows it hits. Note that sqlite3's `with conn:` does not close the connection; call `conn.close()` when you are done.

**Upserts.** Atlas re-imports issues every night. A plain `INSERT` of an id that already exists fails with `sqlite3.IntegrityError: UNIQUE constraint failed: issues.id`. An upsert ("update or insert") inserts new rows and updates existing ones in one statement, like "save" in an editor:

```python
# script_id: primer_a07/orbit_sqlite
UPSERT = """
INSERT INTO issues (id, title, state, orbit_version, created_at)
VALUES (?, ?, ?, ?, ?)
ON CONFLICT (id) DO UPDATE SET
    state = excluded.state,   -- excluded = the row you tried to insert
    title = excluded.title
"""
with conn:
    conn.execute(UPSERT, (102, "Job runs twice on long tasks (ORB-1101)", "closed", "3.2.0", "2026-09-30"))
    conn.execute(UPSERT, (105, "Memory grows with prefetch > 100", "open", "3.2.1", "2026-11-01"))
print(conn.execute("SELECT id, state FROM issues WHERE id >= 102 ORDER BY id").fetchall())
```

```text
[(102, 'closed'), (103, 'open'), (104, 'closed'), (105, 'open')]
```

Issue 102 was updated and 105 was inserted. Use `ON CONFLICT (id) DO NOTHING` to insert only rows that are new. The conflict target must be a primary key or `UNIQUE` column; `ON CONFLICT (title)` fails with `ON CONFLICT clause does not match any PRIMARY KEY or UNIQUE constraint` (Postgres: `there is no unique or exclusion constraint matching the ON CONFLICT specification`).

## Indexes: why lookups get fast

**The problem.** To answer `WHERE state = 'open'`, the database reads every row. That full scan is fine at 240 rows and slow at 10 million.

**The intuition and a tiny example.** An index is the index at the back of a book. An index on `state` is a sorted list: `closed` → 101; `open` → 102, 103, 104. To find open issues, the database jumps to "open" instead of reading every page.

**Name the parts.** A **query plan** is the database's chosen route, which `EXPLAIN` shows you. SQLite reports a full scan as `SCAN` and an index lookup as `SEARCH`; Postgres calls them `Seq Scan` and `Index Scan`. Primary keys and `UNIQUE` columns get an index automatically.

```python
# script_id: primer_a07/orbit_sqlite
def plan(sql: str) -> str:
    # EXPLAIN QUERY PLAN asks SQLite how it would run a query, without running it
    return conn.execute("EXPLAIN QUERY PLAN " + sql).fetchall()[0][-1]

query = "SELECT id, title FROM issues WHERE state = 'open'"
print("before: ", plan(query))
conn.execute("CREATE INDEX idx_issues_state ON issues (state)")
print("after:  ", plan(query))
print("lower():", plan("SELECT id, title FROM issues WHERE lower(state) = 'open'"))
conn.close()
```

```text
before:  SCAN issues
after:   SEARCH issues USING INDEX idx_issues_state (state=?)
lower(): SCAN issues
```

**Break it.** The last query wraps the column in a function, so the index on `state` no longer applies and SQLite is back to a scan. Compare the raw column to a value instead.

**Trade-offs.** Every index speeds up reads but slows down every write and takes disk space. Index the columns you often filter, join or sort on, not every column. On a tiny table Postgres may still pick `Seq Scan`, because reading a few pages is cheaper than using the index. Day 26 adds a special index type for vectors.

## The same SQL on Postgres with psycopg 3

**The problem.** SQLite is a file inside one app. Atlas's API runs many workers that write at once and needs pgvector, so it needs a database server: Postgres. psycopg 3 (`import psycopg`) is the Python driver for it. Older tutorials use `psycopg2`; this course uses psycopg 3.

**The intuition.** Same language, different engine: SQLite is a notebook on your desk; Postgres is a shared library with a librarian who serves many visitors at once. Start a local server (see [Primer A08](A08_docker_compose.md)), then run the script:

```bash
docker run --name atlas-pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres:17
```

```python
# script_id: primer_a07/orbit_postgres
# Install: uv add "psycopg[binary]"
# Env: DATABASE_URL (optional; the default matches the docker command above)
# Services: a running Postgres server
import os
import psycopg

DSN = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")

with psycopg.connect(DSN) as conn:  # on exit: commit (or roll back on error), then close
    conn.execute("""
        CREATE TABLE IF NOT EXISTS issues (
            id         integer PRIMARY KEY,
            title      text NOT NULL,
            state      text NOT NULL,
            created_at date NOT NULL
        )""")
    upsert = """
        INSERT INTO issues (id, title, state, created_at) VALUES (%s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET state = EXCLUDED.state"""
    with conn.cursor() as cur:
        cur.executemany(upsert, [
            (102, "Job runs twice on long tasks (ORB-1101)", "open", "2026-09-30"),
            (103, "Scheduler drifts an hour after DST", "open", "2026-10-27"),
        ])
    with conn.transaction():  # an all-or-nothing block inside the connection
        conn.execute("UPDATE issues SET state = %s WHERE id = %s", ("closed", 102))
    for row in conn.execute("SELECT id, state, created_at FROM issues ORDER BY id"):
        print(row)
```

```text
(102, 'closed', datetime.date(2026, 9, 30))
(103, 'open', datetime.date(2026, 10, 27))
```

The upsert makes the script safe to re-run. Postgres returns a real `datetime.date` because the column is typed `date`.

| | sqlite3 | psycopg 3 |
|---|---|---|
| Install | built into Python | `uv add "psycopg[binary]"` |
| Placeholder | `?` | `%s` (for every type) |
| `with connect(...)` | commits or rolls back, stays open | commits or rolls back, then closes |
| Explicit transaction | `with conn:` | `with conn.transaction():` |
| Types come back as | what you stored (dates are text) | Python types (`date`, `datetime`, `Decimal`) |

**Break it.** Copy a `?` query into psycopg and it fails with `psycopg.ProgrammingError: the query has 0 placeholders but 1 parameters were passed`. A literal `%` in a query with parameters, such as `LIKE '%DST%'`, fails with `only '%s', '%b', '%t' are allowed as placeholders, got '%D'`; pass the pattern as a parameter instead (`LIKE %s` with `("%DST%",)`).

### In production

Teams reuse a pool of open connections per process (`psycopg[pool]`) instead of connecting on every request, and change schemas through migration scripts kept in git.

## Self-Check

1. Write a query for the titles of open issues that carry the `comp:scheduler` label, newest first.

<details><summary>Answer</summary>

```sql
SELECT i.title
FROM issues AS i
JOIN issue_labels AS il ON il.issue_id = i.id
JOIN labels AS l ON l.id = il.label_id
WHERE l.name = 'comp:scheduler' AND i.state = 'open'
ORDER BY i.created_at DESC;
```

</details>

2. Why is `conn.execute(f"SELECT * FROM issues WHERE author = '{name}'")` dangerous, and what is the fix in sqlite3 and in psycopg?

<details><summary>Answer</summary>

The input becomes part of the SQL text, so a value like `x' OR '1'='1` changes what the query does (SQL injection). Pass values as parameters: `WHERE author = ?` with `(name,)` in sqlite3, and `WHERE author = %s` with `(name,)` in psycopg.

</details>

3. A script runs `DELETE FROM issue_labels WHERE issue_id = 7` and then crashes before deleting issue 7. With `with conn:` around both statements, what is in the database afterwards?

<details><summary>Answer</summary>

Both the label rows and the issue are still there. The exception made the `with` block roll back the transaction, so the first `DELETE` was undone too.

</details>

4. A nightly import fails with `UNIQUE constraint failed: issues.id`. How do you make it update existing issues instead, and what does `excluded` mean?

<details><summary>Answer</summary>

Add `ON CONFLICT (id) DO UPDATE SET state = excluded.state, title = excluded.title` to the `INSERT`. `excluded` is the row you tried to insert, so the existing row takes its new values.

</details>

5. You created an index on `issues(state)`, but `EXPLAIN QUERY PLAN` for `WHERE lower(state) = 'open'` still says `SCAN issues`. Why, and what would you change?

<details><summary>Answer</summary>

The index stores raw `state` values, and wrapping the column in `lower()` means the database must compute the function for every row. Compare the raw column (`WHERE state = 'open'`) and store values in one consistent case.

</details>

## Learn More

- [SQLBolt](https://sqlbolt.com/): free interactive lessons in the browser. Lessons 1–15 practise the queries and writes in this primer.
- [PostgreSQL Tutorial (official docs)](https://www.postgresql.org/docs/current/tutorial.html): the official walk-through of tables, queries, joins and transactions.
- [Python docs: sqlite3](https://docs.python.org/3/library/sqlite3.html): placeholders, transaction control and the connection context manager.
- [psycopg 3: Basic module usage](https://www.psycopg.org/psycopg3/docs/basic/usage.html): connections, cursors and the `with` behaviour shown in the last section.
