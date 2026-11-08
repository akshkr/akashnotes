#!/usr/bin/env python3
"""
Cut over from the v1 course (root Phase_* folders) to the v2 course (staged under v2/).

Usage:
    python3 tools/cutover_v2.py            # DRY RUN (default): print every move, then simulate the
                                           # final layout in /tmp/cutover_sim and run the full QA there
    python3 tools/cutover_v2.py --apply    # perform the moves in this repo (no git commands are run)

What --apply does (file moves only; nothing is deleted, and git is not touched):
  1. archive/v1/  <- the old root Phase_* folders, index.md and GLOSSARY.md. These hold the v1
     lessons, including any uncommitted edits (e.g. the Phase-1 reorder).
  2. repo root    <- v2/Phase_*, v2/Appendix_Primers, v2/datasets, v2/index.md, v2/GLOSSARY.md
  3. .restructure/v2/DAY_MAP.json paths lose their "v2/" prefix; the empty v2/ folder is removed.
Afterwards: update CLAUDE.md and CI (drafts are in .restructure/v2/cutover/), add a CHANGELOG entry,
and hand the old->new URL map (.restructure/v2/cutover/old_to_new_map.csv) to the frontend.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V2 = ROOT / "v2"
ARCHIVE = ROOT / "archive" / "v1"
MOVE_IN = ["Appendix_Primers", "datasets", "index.md", "GLOSSARY.md"]


def plan() -> list[tuple[Path, Path]]:
    moves = []
    for p in sorted(ROOT.glob("Phase_*")):
        moves.append((p, ARCHIVE / p.name))
    for name in ("index.md", "GLOSSARY.md"):
        if (ROOT / name).exists():
            moves.append((ROOT / name, ARCHIVE / name))
    for p in sorted(V2.glob("Phase_*")):
        moves.append((p, ROOT / p.name))
    for name in MOVE_IN:
        if (V2 / name).exists():
            moves.append((V2 / name, ROOT / name))
    return moves


def simulate() -> int:
    sim = Path("/tmp/cutover_sim")
    shutil.rmtree(sim, ignore_errors=True)
    (sim / ".restructure/v2").mkdir(parents=True)
    for p in V2.iterdir():
        dst = sim / p.name
        (shutil.copytree if p.is_dir() else shutil.copy2)(p, dst)
    shutil.copytree(ROOT / "tools", sim / "tools")
    shutil.copy2(ROOT / "SYLLABUS_V2.md", sim / "SYLLABUS_V2.md")
    dm = json.loads((ROOT / ".restructure/v2/DAY_MAP.json").read_text())
    for d in dm:
        d["path"] = d["path"].removeprefix("v2/")
    (sim / ".restructure/v2/DAY_MAP.json").write_text(json.dumps(dm, indent=1))
    print(f"\n--- simulated post-cutover layout in {sim} ---")
    qa = subprocess.run([sys.executable, str(sim / "tools/course_qa.py")], capture_output=True, text=True)
    print(qa.stdout.strip())
    chk = subprocess.run([sys.executable, str(sim / "tools/lesson_check.py"), str(sim), "--quiet", "--budget"],
                         capture_output=True, text=True)
    print(chk.stdout.strip().splitlines()[-1] if chk.stdout.strip() else chk.stderr[-300:])
    return qa.returncode or chk.returncode


def main(argv: list[str]) -> int:
    if not V2.is_dir():
        print("v2/ not found: the cutover was already applied, or nothing is staged.")
        return 2
    moves = plan()
    print(f"{'APPLY' if '--apply' in argv else 'DRY RUN'}: {len(moves)} moves")
    for src, dst in moves:
        print(f"  {src.relative_to(ROOT)}  ->  {dst.relative_to(ROOT)}")
    if "--apply" not in argv:
        return simulate()
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    for src, dst in moves:
        if dst.exists():
            print(f"refusing to overwrite {dst}")
            return 1
        shutil.move(str(src), str(dst))
    dm_path = ROOT / ".restructure/v2/DAY_MAP.json"
    dm = json.loads(dm_path.read_text())
    for d in dm:
        d["path"] = d["path"].removeprefix("v2/")
    dm_path.write_text(json.dumps(dm, indent=1))
    leftover = [p for p in V2.iterdir()]
    if leftover:
        print("v2/ still contains:", [p.name for p in leftover])
    else:
        V2.rmdir()
    print("Done. Next: apply the CLAUDE.md and CI drafts, add a CHANGELOG entry, then run tools/course_qa.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
