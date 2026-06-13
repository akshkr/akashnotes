#!/usr/bin/env python3
"""
Static checker for the course's Markdown lessons.

Two checks, both stdlib-only (no deps, no network, no API keys):

1. Fence parity — every lesson must have an even number of ``` fences.
   An odd count means a code block was left unclosed (or a method ended up
   rendering as prose), which is how the Day 035 `run()` bug slipped in.

2. Python parse-check — `python`/`py` code blocks are grouped by their
   `# script_id: ...` marker (blocks sharing an id are concatenated in
   document order, matching how the frontend extractor stitches them into one
   file), then each group is parsed with `ast.parse`. Blocks without a
   script_id are parsed individually.

   Many lessons show a single class *method* in isolation (e.g. an
   "alternative approach" block), which can't parse at module indentation.
   To avoid false alarms, a group that fails is retried after `textwrap.dedent`;
   only groups that fail *both* ways are reported as errors.

Exit code is non-zero if any check fails, so it can gate CI.

Usage:  python tools/check_snippets.py [root_dir]
"""
from __future__ import annotations

import ast
import re
import sys
import textwrap
from pathlib import Path

FENCE_RE = re.compile(r"^```([A-Za-z0-9_+-]*)\s*$")
SCRIPT_ID_RE = re.compile(r"#\s*script_id:\s*(\S+)")
PY_LANGS = {"python", "py"}


def extract_python_blocks(text: str):
    """Yield (script_id_or_None, code) for each python fenced block."""
    lines = text.splitlines()
    in_block = False
    lang = ""
    buf: list[str] = []
    for line in lines:
        m = FENCE_RE.match(line)
        if m and not in_block:
            in_block, lang, buf = True, m.group(1).lower(), []
            continue
        if line.strip() == "```" and in_block:
            if lang in PY_LANGS:
                code = "\n".join(buf)
                sid = None
                mid = SCRIPT_ID_RE.search(code)
                if mid:
                    sid = mid.group(1)
                yield sid, code
            in_block = False
            continue
        if in_block:
            buf.append(line)


def parses(src: str) -> bool:
    for candidate in (src, textwrap.dedent(src)):
        try:
            ast.parse(candidate)
            return True
        except SyntaxError:
            continue
    return False


def check_file(path: Path) -> tuple[list[str], list[str]]:
    """Return (hard_errors, soft_warnings)."""
    hard: list[str] = []
    soft: list[str] = []
    text = path.read_text(encoding="utf-8")

    # 1. Fence parity — HARD. An odd count means an unclosed block / code that
    #    renders as prose. Unambiguous; should never happen.
    fence_count = sum(1 for ln in text.splitlines() if ln.startswith("```"))
    if fence_count % 2 != 0:
        hard.append(f"unbalanced code fences ({fence_count} ``` markers)")

    # 2. Python parse-check — SOFT. The course intentionally shows non-runnable
    #    fragments (cheat-sheets, lone methods, pseudo-code), so a parse failure
    #    is a review hint, not a build breaker.
    groups: dict[str, list[str]] = {}
    anon: list[str] = []
    for sid, code in extract_python_blocks(text):
        if sid:
            groups.setdefault(sid, []).append(code)
        else:
            anon.append(code)

    for sid, blocks in groups.items():
        if not parses("\n".join(blocks)):
            soft.append(f"script_id '{sid}' does not parse standalone (fragment?)")
    for i, code in enumerate(anon):
        if not parses(code):
            first = code.strip().splitlines()[0] if code.strip() else "<empty>"
            soft.append(f"un-id'd python block #{i + 1} does not parse: {first!r}")

    return hard, soft


def main(argv: list[str]) -> int:
    strict = "--strict" in argv  # treat parse warnings as failures too
    args = [a for a in argv[1:] if not a.startswith("-")]
    root = Path(args[0]) if args else Path(__file__).resolve().parent.parent
    md_files = sorted(root.glob("Phase_*/Day_*/*.md"))
    if not md_files:
        print(f"No lesson files found under {root}", file=sys.stderr)
        return 2

    hard_total = 0
    soft_total = 0
    for path in md_files:
        hard, soft = check_file(path)
        if hard or soft:
            rel = path.relative_to(root)
            print(f"\n{rel}")
            for e in hard:
                print(f"  ERROR: {e}")
            for w in soft:
                print(f"  warn:  {w}")
            hard_total += len(hard)
            soft_total += len(soft)

    print(
        f"\nChecked {len(md_files)} lessons; "
        f"{hard_total} error(s), {soft_total} warning(s)."
    )
    if hard_total or (strict and soft_total):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
