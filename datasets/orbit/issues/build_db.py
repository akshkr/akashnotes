#!/usr/bin/env python3
"""Build issues/orbit.db from issues/issues.jsonl.

Standard library only. Safe to run any number of times: the database is built in a temporary
file next to the target and then swapped into place, so a failed run never leaves a
half-written orbit.db behind.

    python3 issues/build_db.py

Tables: issues, labels, issue_labels, comments, releases, users.
All data is synthetic and fictional (CC0-1.0). See the dataset README.
"""
import json
import os
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "issues.jsonl"
TARGET = HERE / "orbit.db"

MAINTAINERS = ("mara-k", "devon-li", "sam-okafor", "ines-v")

# The release table from the Orbit world bible (DATASET_SPEC §1), mirrored in docs/changelog.md.
RELEASES = [
    ("2.8.0", "2025-06-10", None),
    ("2.9.0", "2025-11-20", "Last 2.x release; end of life 2026-12-31"),
    ("3.0.0", "2026-03-02", "Introduced Flows and orbit.toml (replacing orbit.ini and ORBIT_* env vars)"),
    ("3.0.3", "2026-04-14", None),
    ("3.1.0", "2026-06-01", None),
    ("3.1.2", "2026-07-08", None),
    ("3.2.0", "2026-09-15", None),
    ("3.2.1", "2026-10-20", "Current release"),
]

SCHEMA = """
CREATE TABLE users (
    handle            TEXT PRIMARY KEY,
    role              TEXT NOT NULL CHECK (role IN ('maintainer', 'reporter')),
    first_seen_at     TEXT NOT NULL,
    issues_opened     INTEGER NOT NULL,
    comments_written  INTEGER NOT NULL
);

CREATE TABLE releases (
    version      TEXT PRIMARY KEY,
    released_on  TEXT NOT NULL,
    notes        TEXT
);

CREATE TABLE issues (
    id              INTEGER PRIMARY KEY,
    title           TEXT NOT NULL,
    body            TEXT NOT NULL,
    author          TEXT NOT NULL REFERENCES users(handle),
    created_at      TEXT NOT NULL,
    state           TEXT NOT NULL CHECK (state IN ('open', 'closed')),
    closed_at       TEXT,
    type            TEXT NOT NULL CHECK (type IN ('bug', 'feature', 'question', 'docs')),
    severity        TEXT CHECK (severity IN ('S1', 'S2', 'S3', 'S4')),
    orbit_version   TEXT,
    python_version  TEXT,
    error_codes     TEXT NOT NULL,   -- JSON array, e.g. ["ORB-1001"]
    duplicate_of    INTEGER REFERENCES issues(id),
    comment_count   INTEGER NOT NULL
);

CREATE TABLE labels (
    id     INTEGER PRIMARY KEY,
    name   TEXT NOT NULL UNIQUE,     -- e.g. "comp:broker-redis"
    kind   TEXT NOT NULL CHECK (kind IN ('type', 'comp', 'severity', 'version')),
    value  TEXT NOT NULL             -- e.g. "broker-redis"
);

CREATE TABLE issue_labels (
    issue_id  INTEGER NOT NULL REFERENCES issues(id),
    label_id  INTEGER NOT NULL REFERENCES labels(id),
    PRIMARY KEY (issue_id, label_id)
);

CREATE TABLE comments (
    id          INTEGER PRIMARY KEY,
    issue_id    INTEGER NOT NULL REFERENCES issues(id),
    position    INTEGER NOT NULL,    -- 1 = first comment on the issue
    author      TEXT NOT NULL REFERENCES users(handle),
    created_at  TEXT NOT NULL,
    body        TEXT NOT NULL,
    UNIQUE (issue_id, position)
);

CREATE INDEX idx_issues_created_at   ON issues(created_at);
CREATE INDEX idx_issues_duplicate_of ON issues(duplicate_of);
CREATE INDEX idx_issue_labels_label  ON issue_labels(label_id);
CREATE INDEX idx_comments_issue      ON comments(issue_id);
CREATE INDEX idx_comments_author     ON comments(author);
"""

LABEL_ORDER = {"type": 0, "comp": 1, "severity": 2, "version": 3}


def load_issues(path):
    issues = []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                issues.append(json.loads(line))
            except json.JSONDecodeError as exc:
                sys.exit(f"{path.name}:{lineno}: invalid JSON ({exc})")
    issues.sort(key=lambda r: r["id"])
    ids = [r["id"] for r in issues]
    if ids != list(range(1, len(ids) + 1)):
        sys.exit(f"{path.name}: issue ids must be 1..N without gaps or repeats")
    return issues


def label_value(labels, kind):
    for name in labels:
        if name.startswith(kind + ":"):
            return name.split(":", 1)[1]
    return None


def build(conn, issues):
    conn.executescript(SCHEMA)

    # users: every handle that opened an issue or wrote a comment
    users = {}
    def seen(handle, ts, opened=0, commented=0):
        u = users.setdefault(handle, {"first": ts, "opened": 0, "comments": 0})
        u["first"] = min(u["first"], ts)
        u["opened"] += opened
        u["comments"] += commented
    for r in issues:
        seen(r["author"], r["created_at"], opened=1)
        for c in r["comments"]:
            seen(c["author"], c["created_at"], commented=1)
    conn.executemany(
        "INSERT INTO users VALUES (?, ?, ?, ?, ?)",
        [(h, "maintainer" if h in MAINTAINERS else "reporter", u["first"], u["opened"], u["comments"])
         for h, u in sorted(users.items())],
    )

    conn.executemany("INSERT INTO releases VALUES (?, ?, ?)", RELEASES)

    # labels: one row per distinct label name, ordered by kind then name
    names = sorted({l for r in issues for l in r["labels"]},
                   key=lambda n: (LABEL_ORDER[n.split(":", 1)[0]], n))
    label_id = {}
    for i, name in enumerate(names, 1):
        kind, value = name.split(":", 1)
        label_id[name] = i
        conn.execute("INSERT INTO labels VALUES (?, ?, ?, ?)", (i, name, kind, value))

    # issues first (duplicate_of always points at an earlier id), then their labels and comments
    comment_id = 0
    for r in issues:
        conn.execute(
            "INSERT INTO issues VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (r["id"], r["title"], r["body"], r["author"], r["created_at"], r["state"], r["closed_at"],
             label_value(r["labels"], "type"), label_value(r["labels"], "severity"),
             r["orbit_version"], r["python_version"], json.dumps(r["error_codes"]),
             r["duplicate_of"], len(r["comments"])),
        )
        conn.executemany("INSERT INTO issue_labels VALUES (?, ?)",
                         [(r["id"], label_id[l]) for l in r["labels"]])
        for pos, c in enumerate(r["comments"], 1):
            comment_id += 1
            conn.execute("INSERT INTO comments VALUES (?, ?, ?, ?, ?, ?)",
                         (comment_id, r["id"], pos, c["author"], c["created_at"], c["body"]))

    problems = conn.execute("PRAGMA foreign_key_check").fetchall()
    if problems:
        sys.exit(f"foreign key violations: {problems[:5]}")


def main():
    if not SOURCE.exists():
        sys.exit(f"missing {SOURCE}")
    issues = load_issues(SOURCE)

    tmp = TARGET.with_name(TARGET.name + ".tmp")
    if tmp.exists():
        tmp.unlink()
    conn = sqlite3.connect(tmp)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        with conn:
            build(conn, issues)
        counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                  for t in ("issues", "labels", "issue_labels", "comments", "releases", "users")}
    finally:
        conn.close()
    os.replace(tmp, TARGET)

    print(f"built {TARGET.relative_to(HERE.parent)}")
    for table, n in counts.items():
        print(f"  {table:<13}{n:>6}")


if __name__ == "__main__":
    main()
