#!/usr/bin/env python3
"""
Course-wide structural QA for the v2 tree (deterministic; no LLM, no network).

Usage:  python3 tools/course_qa.py [--digests DIR]

Checks:
  - every relative markdown link in every lesson and primer resolves (reports broken ones,
    separating links to lessons not written yet, by DAY_MAP, from genuinely wrong paths)
  - each lesson's "What's Next" links to the next day (D100 is exempt)
  - each lesson's At a Glance prerequisites link to earlier days only (no forward prereqs)
--digests DIR also writes one compact digest per lesson (title, At a Glance, H2 outline,
Key Takeaways, What's Next, script ids) for cheap flow review.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V2 = ROOT / "v2" if (ROOT / "v2").is_dir() else ROOT   # staging tree before cutover, repo root after
DAY_MAP = {d["day"]: d for d in json.loads((ROOT / "tools/day_map.json").read_text())}
_dm_path = lambda d: ROOT / (d["path"] if (ROOT / "v2").is_dir() else d["path"].removeprefix("v2/"))
PATH_TO_DAY = {str(_dm_path(d).resolve()): n for n, d in DAY_MAP.items()}
LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)\s#]+)(#[^)\s]*)?\)")


def section(text: str, title_rx: str) -> str:
    m = re.search(rf"^## +{title_rx}.*?$(.*?)(?=^## |\Z)", text, re.M | re.S | re.I)
    return m.group(1) if m else ""


def strip_code(text: str) -> str:
    out, inb = [], False
    for ln in text.splitlines():
        if ln.startswith("```"):
            inb = not inb
            continue
        if not inb:
            out.append(re.sub(r"`[^`]*`", "", ln))   # links inside inline code are not links
    return "\n".join(out)


def main(argv: list[str]) -> int:
    dig = next((Path(a.split("=", 1)[1]) for a in argv if a.startswith("--digests=")), None)
    files = [f for f in sorted(V2.rglob("Day_*/*.md")) + sorted((V2 / "Appendix_Primers").glob("*.md"))
             if not ({"archive", ".restructure"} & set(f.relative_to(V2).parts))]   # skip the archived v1 course
    broken, pending, next_bad, fwd = [], [], [], []
    for f in files:
        text = strip_code(f.read_text(encoding="utf-8"))
        m = re.search(r"Day_(\d{3})_", str(f))
        day = int(m.group(1)) if m else None
        for mm in LINK_RE.finditer(text):
            tgt = mm.group(2)
            if tgt.startswith(("http://", "https://", "mailto:")):
                continue
            p = (f.parent / tgt).resolve()
            if p.exists():
                continue
            (pending if str(p) in PATH_TO_DAY else broken).append(f"{f.relative_to(ROOT)} -> {tgt}")
        if day:
            nxt = section(text, r"What.s Next")
            if day < 100:
                want = str(_dm_path(DAY_MAP[day + 1]).resolve())
                linked = {str((f.parent / t).resolve()) for _, t, _ in LINK_RE.findall(nxt)}
                if want not in linked:
                    next_bad.append(f"D{day:03d}: What's Next does not link Day {day + 1} ({DAY_MAP[day + 1]['slug']})")
            glance = section(text, r"At a Glance")
            pre = next((ln for ln in glance.splitlines() if "Prerequisites" in ln), "")
            for _, t, _ in LINK_RE.findall(pre):
                n = PATH_TO_DAY.get(str((f.parent / t).resolve()))
                if n and n >= day:
                    fwd.append(f"D{day:03d}: prerequisite links forward to Day {n}")
            if dig:
                dig.mkdir(parents=True, exist_ok=True)
                h1 = (re.search(r"^# (.+)$", text, re.M) or [None, "?"])[1]
                h2 = [h for h in re.findall(r"^## (.+)$", text, re.M)]
                sids = sorted(set(re.findall(r"# script_id: (\S+)", f.read_text(encoding="utf-8"))))
                (dig / f"D{day:03d}.md").write_text(
                    f"# D{day:03d} · {h1}\n## At a Glance\n{glance.strip()}\n## Outline\n" + "\n".join(f"- {h}" for h in h2)
                    + f"\n## Key Takeaways\n{section(text, r'Key Takeaways').strip()}\n## What's Next\n{nxt.strip()}\n"
                    + "## Scripts\n" + ", ".join(s.split('/', 1)[1] for s in sids) + "\n", encoding="utf-8")
    print(f"files: {len(files)}")
    print(f"broken relative links (wrong path): {len(broken)}")
    for b in broken:
        print("  BROKEN", b)
    print(f"links to lessons not written yet: {len(pending)}")
    print(f"What's Next problems: {len(next_bad)}")
    for b in next_bad:
        print("  NEXT", b)
    print(f"forward prerequisites: {len(fwd)}")
    for b in fwd:
        print("  FWD", b)
    return 1 if broken or next_bad or fwd else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
