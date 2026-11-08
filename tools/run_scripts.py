#!/usr/bin/env python3
"""
Extract a lesson's stitched scripts and run every one that needs no API key or network service.

Usage:
    python3 tools/run_scripts.py <lesson.md> [--python PATH] [--timeout SECONDS]

- Extracts each script_id group (via lesson_check.py --extract) into /tmp/run_scripts/<Day_NNN>/.
- Runs EVERY script. Failures caused only by a missing API key or an unavailable service
  (Postgres/Redis/Docker/Ollama, network) are reported as "needs key/service", not as failures.
  Introspect the SDK calls in those scripts instead.
- Sets ORBIT_DATA to the course dataset. A timeout is reported separately: servers are
  supposed to keep running.
Exit code is 1 if any runnable script fails.
"""
from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Failures caused only by the missing API key / unreachable service are reported separately.
NEEDS_ENV_RE = re.compile(r"OPENAI_API_KEY|ANTHROPIC_API_KEY|api_key|Missing credentials|AuthenticationError|"
                          r"LMNotConfiguredError|APIConnectionError|Connection refused|ConnectionRefusedError|"
                          r"could not connect to server|Name or service not known|nodename nor servname|"
                          r"password authentication failed|connection failed: connection to server|"
                          r"Error 61 connecting|Cannot connect to the Docker daemon|DockerException|Failed to connect to Ollama|Docker isn't reachable|ConnectError|All connection attempts failed|"
                          r"No module named '(?:sentence_transformers|torch|transformers|vllm|unsloth|presidio_analyzer|spacy)'")
API_RE = re.compile(r"OpenAI\(|AsyncOpenAI\(|client\.responses|Anthropic\(|AsyncAnthropic\(")


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    lesson = Path(args[0]).resolve()
    py = next((a.split("=", 1)[1] for a in argv if a.startswith("--python=")),
              str(ROOT / ".restructure/v2/venv/bin/python") if (ROOT / ".restructure/v2/venv/bin/python").exists()
              else sys.executable)
    tmo = int(next((a.split("=", 1)[1] for a in argv if a.startswith("--timeout=")), "45"))
    tag = (re.search(r"Day_\d{3}", str(lesson)) or re.search(r"[^/]+(?=\.md$)", str(lesson))).group(0)
    out = Path("/tmp/run_scripts") / tag
    shutil.rmtree(out, ignore_errors=True)
    subprocess.run([sys.executable, str(ROOT / "tools/lesson_check.py"), str(lesson), "--no-template",
                    "--quiet", f"--extract={out}"], capture_output=True, text=True)
    course = ROOT / "v2" if (ROOT / "v2").is_dir() else ROOT   # staging tree before cutover, repo root after
    env = dict(os.environ, ORBIT_DATA=str(course / "datasets/orbit"))
    ok, failed, timed, api = [], [], [], []
    # Run in DOCUMENT order (first appearance of each script_id), the order a learner follows;
    # later scripts often read files that earlier ones wrote (e.g. runs/cases.jsonl).
    order = []
    for sid in re.findall(r"^# script_id: (\S+)", lesson.read_text(encoding="utf-8"), re.M):
        if sid not in order:
            order.append(sid)
    rank = {sid: i for i, sid in enumerate(order)}
    scripts = sorted(out.rglob("*.py"),
                     key=lambda p: rank.get(str(p.relative_to(out).with_suffix("")), len(rank)))
    src = {s: s.read_text(encoding="utf-8") for s in scripts}
    # API-calling = builds a client itself, or imports a lesson-local module that does (transitively).
    api_set = {s for s in scripts if API_RE.search(src[s])}
    grew = True
    while grew:
        stems = "|".join(re.escape(s.stem) for s in api_set)
        imp = re.compile(rf"^\s*(?:from|import)\s+(?:{stems})\b", re.M) if stems else None
        new = {s for s in scripts if s not in api_set and imp and imp.search(src[s])}
        api_set |= new
        grew = bool(new)
    # Run EVERY script. A script that needs a key or service fails fast without one, and its
    # error text is matched by NEEDS_ENV_RE ("needs key/service"). api_set is informational only.
    for s in scripts:
        try:
            # Run from the lesson's project root (out/<day_prefix>/) so multi-file
            # script_ids like day_042_x/atlas/rag import each other as `atlas.rag`.
            base = out / s.relative_to(out).parts[0]
            run_env = dict(env, PYTHONPATH=f"{base}{os.pathsep}{s.parent}")
            # New session so a timed-out server (and anything it spawned) is killed as a group,
            # instead of being orphaned and holding a port for later runs.
            proc = subprocess.Popen([py, str(s)], cwd=base, env=run_env, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, text=True,
                                    start_new_session=True)
            try:
                out_s, err_s = proc.communicate(timeout=tmo)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.communicate()
                raise
            r = subprocess.CompletedProcess(proc.args, proc.returncode, out_s, err_s)
            if r.returncode == 0:
                ok.append(s.name)
            else:
                last = (r.stderr.strip().splitlines() or ["(no stderr)"])[-1][:200]
                if NEEDS_ENV_RE.search(r.stderr):
                    api.append(f"{s.name} (needs key/service: {last[:80]})")
                else:
                    failed.append(f"{s.name}: {last}")
        except subprocess.TimeoutExpired:
            timed.append(s.name)
    print(f"extracted to {out}")
    print(f"ran OK ({len(ok)}): {', '.join(ok) or '-'}")
    for f in failed:
        print(f"FAILED: {f}")
    if timed:
        print(f"timed out after {tmo}s (expected only for servers): {', '.join(timed)}")
    print(f"API-calling, not run (introspect their SDK calls) ({len(api)}): {', '.join(api) or '-'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
