#!/usr/bin/env python3
"""
Per-lesson quality gate for the v2 course (stdlib only; optional `mmdc` for diagrams).

Usage:
    python3 tools/lesson_check.py <lesson.md | dir> [--mermaid] [--online]
                                   [--links-final] [--no-template] [--quiet]
                                   [--extract=DIR]   # write each stitched script_id to DIR/<script_id>.py

Checks (HARD = non-zero exit, warn = printed only):
  HARD  fence parity: every ``` opener has a closer
  HARD  python: every block starts with `# script_id: day_NNN_<slug>/<name>` (or carries `# fragment`)
  HARD  python: script_id day prefix matches the lesson folder's day number
  HARD  python: each script_id group (blocks stitched in document order) parses
  HARD  python: a stitched script must not import a name from a "module" when that
        name is defined in the same stitched script (the old D018/D048 bug).
        Multi-file projects: give each file its own script_id whose last segment is
        the module name (…/schemas  <->  `from schemas import X`) — that is allowed.
  HARD  deprecated patterns inside code blocks (openai.ChatCompletion, PyPDF2, @validator,
        @app.on_event, gpt-4-vision-preview, budget_tokens, date-suffixed claude IDs, …)
  HARD  template sections present (skip with --no-template)
  HARD  --mermaid: every ```mermaid block renders with `mmdc`
  HARD  --links-final: every relative markdown link resolves to an existing file
  warn  relative links that don't resolve yet (lessons written in parallel)
  HARD  --online: every external http(s) link answers < 400 (HEAD, then GET)
  warn  exercises without a collapsible <details> solution
  --budget  enforce the v2 day budget (HARD with --budget, otherwise warnings):
        core prose (outside <details>) <= 3,300 words (target 2,000-3,000, ~2 h core path)
        "Go Deeper" prose (inside <details>, outside Exercises) <= 1,500 words
        body scripts (script_ids outside Exercises) <= 10 (target 7-8; more only if needed)
        exercises: <= 5 collapsible solutions (target 3 + 1 optional stretch); each solution script <= 60 lines
"""
from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import urllib.request
from pathlib import Path

FENCE_RE = re.compile(r"^```([A-Za-z0-9_+-]*)\s*$")
SCRIPT_ID_RE = re.compile(r"^#\s*script_id:\s*(\S+)\s*$")
DAY_DIR_RE = re.compile(r"Day_(\d{3})_")
LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")

# Template sections (case-insensitive substring match on headings / callout).
TEMPLATE = [
    ("H1 title", re.compile(r"^# \S", re.M)),
    ("At a glance", re.compile(r"^#{2,3} .*at a glance", re.I | re.M)),
    ("Coming from Software Engineering? callout", re.compile(r"^> \*\*Coming from Software Engineering\?", re.M)),
    ("Common Pitfalls", re.compile(r"^#{2,3} .*common pitfalls", re.I | re.M)),
    ("Key Takeaways", re.compile(r"^#{2,3} .*key takeaways", re.I | re.M)),
    ("Quick Reference", re.compile(r"^#{2,3} .*quick reference", re.I | re.M)),
    ("Exercises", re.compile(r"^#{2,3} .*exercises", re.I | re.M)),
    ("References", re.compile(r"^#{2,3} .*(references|further reading)", re.I | re.M)),
    ("What's Next", re.compile(r"^#{2,3} .*what.s next", re.I | re.M)),
]

# Deprecated / forbidden patterns inside CODE blocks (prose may mention them as warnings).
DEPRECATED = [
    (re.compile(r"openai\.ChatCompletion\b"), "module-level openai.ChatCompletion (SDK v0) — use client.chat.completions / client.responses"),
    (re.compile(r"openai\.Completion\b"), "legacy openai.Completion"),
    (re.compile(r"gpt-4-vision-preview"), "gpt-4-vision-preview is retired"),
    (re.compile(r"\bPyPDF2\b"), "PyPDF2 is unmaintained — use pypdf"),
    (re.compile(r"@validator\("), "Pydantic v1 @validator — use @field_validator"),
    (re.compile(r"@root_validator"), "Pydantic v1 @root_validator — use @model_validator"),
    (re.compile(r"@app\.on_event\("), "FastAPI @app.on_event — use lifespan"),
    (re.compile(r"budget_tokens"), "budget_tokens thinking — course uses adaptive thinking / effort"),
    (re.compile(r"claude-[a-z0-9.-]+-20\d{6}"), "date-suffixed Claude model ID — use the bare alias"),
    (re.compile(r"text-davinci|gpt-3\.5-turbo-instruct"), "legacy completion model"),
    (re.compile(r"from langchain\.agents import .*AgentExecutor"), "legacy LangChain AgentExecutor"),
    (re.compile(r"\./main -m|\bconvert\.py\b"), "old llama.cpp binary names"),
]

STDLIB = set(getattr(sys, "stdlib_module_names", ())) | {"__future__"}


# --------------------------------------------------------------------------- parsing
def blocks(text: str):
    """Yield (lang, start_line, code) for fenced blocks. Returns also fence parity."""
    out, in_block, lang, buf, start = [], False, "", [], 0
    for i, line in enumerate(text.splitlines(), 1):
        m = FENCE_RE.match(line)
        if not in_block and m:
            in_block, lang, buf, start = True, m.group(1).lower(), [], i
            continue
        if in_block and line.strip() == "```":
            out.append((lang, start, "\n".join(buf)))
            in_block = False
            continue
        if in_block:
            buf.append(line)
    return out, not in_block


def parses(src: str) -> str | None:
    err = None
    for cand in (src, textwrap.dedent(src)):
        try:
            ast.parse(cand)
            return None
        except SyntaxError as e:  # keep first error
            err = err or f"line {e.lineno}: {e.msg}"
    return err


def defined_names(tree: ast.AST) -> set[str]:
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def check_imports(sid: str, src: str, sibling_modules: set[str]) -> list[str]:
    """Flag `from X import Y` where Y is defined in this same stitched script."""
    try:
        tree = ast.parse(textwrap.dedent(src))
    except SyntaxError:
        return []
    defined = defined_names(tree)
    errs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            top = node.module.split(".")[0]
            if top in STDLIB:
                continue
            clash = [a.name for a in node.names if a.name in defined]
            if clash:
                errs.append(
                    f"script_id '{sid}' imports {clash} from '{node.module}' but defines them in the same "
                    f"stitched script — split into separate script_ids (…/{top}) or drop the import"
                )
            elif top not in sibling_modules and _looks_local(top):
                errs.append(
                    f"script_id '{sid}' imports from '{node.module}', which is neither installed-looking nor a "
                    f"sibling script_id in this lesson (multi-file project? name a script_id …/{top})"
                )
    return errs


KNOWN_THIRD_PARTY = {
    "openai", "anthropic", "tiktoken", "pydantic", "pydantic_ai", "numpy", "pandas", "sklearn", "scipy",
    "matplotlib", "plotly", "langchain", "langchain_core", "langchain_openai", "langchain_community",
    "langchain_chroma", "langchain_text_splitters", "langgraph", "llama_index", "dspy", "crewai", "crewai_tools",
    "chromadb", "psycopg", "psycopg2", "pgvector", "sqlalchemy", "ragas", "datasets", "langsmith", "phoenix",
    "openinference", "opentelemetry", "guardrails", "nemoguardrails", "presidio_analyzer", "presidio_anonymizer",
    "spacy", "docker", "ollama", "llama_cpp", "vllm", "unsloth", "trl", "peft", "transformers", "torch",
    "bitsandbytes", "accelerate", "fastapi", "uvicorn", "starlette", "httpx", "requests", "aiohttp", "celery",
    "redis", "streamlit", "gradio", "mcp", "fastmcp", "cohere", "voyageai", "sentence_transformers", "neo4j",
    "tenacity", "pytest", "syrupy", "dotenv", "bs4", "pypdf", "pdfplumber", "fitz", "pymupdf", "docling",
    "unstructured", "jwt", "websockets", "boto3", "hvac", "wandb", "rank_bm25", "jinja2", "yaml", "rich",
    "typer", "click", "tqdm", "deepeval", "promptfoo", "litellm", "instructor", "google", "mangum", "psutil",
    "agents", "a2a", "jsonschema", "pydantic_settings", "sse_starlette", "duckdb", "lancedb", "qdrant_client",
    "pinecone", "weaviate", "elasticsearch", "markdown", "PIL", "cv2", "pytesseract", "whisper", "soundfile",
    "evaluate", "rouge_score", "nltk", "networkx", "faiss", "annoy", "hnswlib", "llm_guard", "lakera",
    "opik", "langfuse", "arize", "mlflow", "prometheus_client", "structlog", "loguru", "orjson", "ujson",
    "awq", "gptcache", "langchain_ollama", "langchain_anthropic", "langchain_cohere", "mem0", "e2b",
    "e2b_code_interpreter", "modal", "tavily", "duckduckgo_search", "braintrust", "markitdown", "llama_parse",
    "huggingface_hub", "safetensors", "gguf", "openai_agents", "nest_asyncio", "anyio", "trio", "numba",
    "rq", "fakeredis", "redisvl", "fpdf",
}


def _looks_local(top: str) -> bool:
    if top in KNOWN_THIRD_PARTY:
        return False
    try:
        import importlib.util
        return importlib.util.find_spec(top) is None
    except (ImportError, ValueError):
        return True


# --------------------------------------------------------------------------- checks
def check_file(path: Path, opts: dict) -> tuple[list[str], list[str], dict]:
    hard, warn = [], []
    text = path.read_text(encoding="utf-8")
    bl, balanced = blocks(text)
    if not balanced or sum(1 for ln in text.splitlines() if ln.startswith("```")) % 2:
        hard.append("unbalanced code fences")

    m = DAY_DIR_RE.search(str(path))
    day = m.group(1) if m else None

    # ---- python
    groups: dict[str, list[tuple[int, str]]] = {}
    fragments = set()
    for lang, start, code in bl:
        if lang not in ("python", "py"):
            continue
        first = code.lstrip().splitlines()[0] if code.strip() else ""
        sm = SCRIPT_ID_RE.match(first.strip())
        is_frag = "# fragment" in code
        if not sm:
            if not is_frag:
                hard.append(f"L{start}: python block has no first-line `# script_id:` (or `# fragment`)")
            continue
        sid = sm.group(1)
        if day and not sid.startswith(f"day_{day}_"):
            hard.append(f"L{start}: script_id '{sid}' does not start with day_{day}_")
        groups.setdefault(sid, []).append((start, code))
        if is_frag:
            fragments.add(sid)
    # Multi-file projects: script_id = day_NNN_<slug>/<relative/module/path> (e.g. …/api/routers/health).
    # Both the top package ("api") and the leaf module ("health") count as importable siblings.
    sibling_modules = set()
    for sid in groups:
        rel = sid.split("/", 1)[1] if "/" in sid else sid
        segs = rel.split("/")
        sibling_modules |= {segs[0], segs[-1]}
    for sid, parts in groups.items():
        if sid in fragments:
            continue
        src = "\n".join(c for _, c in parts)
        err = parses(src)
        if err:
            hard.append(f"script_id '{sid}' (from L{parts[0][0]}) does not parse when stitched: {err}")
            continue
        hard.extend(check_imports(sid, src, sibling_modules))

    # ---- deprecated patterns in code
    for lang, start, code in bl:
        if lang in ("mermaid", "text", "markdown", "md"):
            continue
        for rx, why in DEPRECATED:
            for mm in rx.finditer(code):
                line = code.splitlines()[code[: mm.start()].count("\n")]
                if re.search(r"(deprecated|don't|do not|never|legacy|old:|❌)", line, re.I):
                    continue  # explicitly labelled as the anti-pattern
                hard.append(f"L{start}: deprecated pattern in code: {why}")

    # ---- mermaid
    mermaids = [(s, c) for lang, s, c in bl if lang == "mermaid"]
    if opts["mermaid"] and mermaids:
        mmdc = shutil.which("mmdc")
        if not mmdc:
            warn.append("--mermaid requested but `mmdc` not found")
        else:
            with tempfile.TemporaryDirectory() as td:
                for s, code in mermaids:
                    src, out = Path(td, f"d{s}.mmd"), Path(td, f"d{s}.svg")
                    src.write_text(code, encoding="utf-8")
                    extra = ["-p", os.environ["MMDC_PUPPETEER_CONFIG"]] if os.environ.get("MMDC_PUPPETEER_CONFIG") else []
                    r = subprocess.run([mmdc, "-q", "-i", str(src), "-o", str(out), *extra],
                                       capture_output=True, text=True, timeout=120)
                    if r.returncode != 0 or not out.exists():
                        msg = (r.stderr or r.stdout).strip().splitlines()
                        msg = " | ".join(x.strip() for x in msg[:3])
                        hard.append(f"L{s}: mermaid does not render: {msg[:240]}")

    # ---- links (skip links inside code blocks)
    prose = _strip_code(text)
    for mm in LINK_RE.finditer(prose):
        target = mm.group(2)
        if target.startswith(("http://", "https://")):
            if opts["online"]:
                bad = _url_bad(target)
                if bad:
                    hard.append(f"external link fails ({bad}): {target}")
            continue
        if target.startswith(("#", "mailto:")):
            continue
        rel = target.split("#", 1)[0]
        if not rel:
            continue
        if not (path.parent / rel).resolve().exists():
            (hard if opts["links_final"] else warn).append(f"relative link does not resolve (yet): {target}")

    # ---- template (lessons only; primers have their own anatomy)
    if opts["template"] and day:
        for name, rx in TEMPLATE:
            if not rx.search(prose):
                hard.append(f"template: missing section '{name}'")
        ex = re.search(r"^#{2,3} .*exercises.*$(.*?)(?=^#{2} |\Z)", prose, re.I | re.M | re.S)
        if ex and "<details" not in text[text.find(ex.group(0)[:40]):]:
            warn.append("exercises have no collapsible <details> solutions")

    if opts.get("budget") is not None and day:
        st = budget_stats(text)
        be, bw = check_budget(st, capstone=opts.get("capstone", False) or "capstone" in path.parent.name)
        (hard if opts["budget"] else warn).extend(be)
        warn.extend(bw)
        warn.append(f"budget stats: core={st['core_words']}w deeper={st['deeper_words']}w body_scripts={st['body_scripts']} deeper_scripts={st['deeper_scripts']} solutions={st['solutions']} longest_solution={st['longest_solution']}L")
    stats = {
        "words": len(re.findall(r"\b\w+\b", prose)),
        "py_scripts": len(groups),
        "mermaid": len(mermaids),
        "links": len(LINK_RE.findall(prose)),
    }
    return hard, warn, stats


def budget_stats(text: str) -> dict:
    """Split prose into core / go-deeper / exercise-solution buckets and count scripts."""
    core = deeper = sol_words = 0
    in_code = False; depth = 0; section = ""; ex_details = 0
    body_ids, deeper_ids, sol_lines, cur_sid, cur_in_ex = set(), set(), {}, None, False
    for line in text.splitlines():
        if line.startswith("```"):
            in_code = not in_code
            cur_sid = None
            continue
        if in_code:
            m = SCRIPT_ID_RE.match(line.strip())
            if m:
                cur_sid = m.group(1); cur_in_ex = section.lower().startswith("exercises")
                if cur_in_ex or cur_sid.rsplit("/", 1)[-1].startswith("solution"):
                    sol_lines.setdefault(cur_sid, 0)
                elif depth > 0:
                    deeper_ids.add(cur_sid)   # inside an optional Go Deeper <details>
                else:
                    body_ids.add(cur_sid)
            if cur_sid in sol_lines:
                sol_lines[cur_sid] += 1
            continue
        if line.startswith("## "):
            section = line[3:].strip()
        opens, closes = line.count("<details"), line.count("</details>")
        if opens and section.lower().startswith("exercises"):
            ex_details += opens
        words = len(re.findall(r"\b\w+\b", re.sub(r"<[^>]+>|`[^`]*`|\]\([^)]*\)", " ", line)))
        if depth > 0 or opens:
            if section.lower().startswith("exercises"):
                sol_words += words
            else:
                deeper += words
        else:
            core += words
        depth = max(0, depth + opens - closes)
    return {"core_words": core, "deeper_words": deeper, "solution_words": sol_words,
            "body_scripts": len(body_ids - deeper_ids), "deeper_scripts": len(deeper_ids), "solutions": ex_details,
            "longest_solution": max(sol_lines.values()) if sol_lines else 0}


def check_budget(st: dict, capstone: bool = False) -> tuple[list[str], list[str]]:
    errs, warns = [], []
    smax, swarn = (15, 12) if capstone else (10, 8)
    def rule(cond_err, cond_warn, msg):
        (errs if cond_err else warns if cond_warn else []).append(msg)
    rule(st["core_words"] > 3300, st["core_words"] > 3000 or st["core_words"] < 1800,
         f"budget: core prose {st['core_words']} words (target 2,000-3,000; move depth into a 'Go Deeper' <details>)")
    rule(st["deeper_words"] > 1500, st["deeper_words"] > 1200, f"budget: Go Deeper prose {st['deeper_words']} words (max 1,500)")
    rule(st["body_scripts"] > smax, st["body_scripts"] > swarn, f"budget: {st['body_scripts']} body scripts (target {'~12 for a capstone' if capstone else '7-8'}; max {smax})")
    rule(st["deeper_scripts"] > 3, False, f"budget: {st['deeper_scripts']} Go Deeper scripts (max 3)")
    rule(st["solutions"] > 5, st["solutions"] > 4, f"budget: {st['solutions']} exercise solutions (target 3 + 1 optional stretch)")
    rule(st["longest_solution"] > 60, st["longest_solution"] > 40, f"budget: longest solution script {st['longest_solution']} lines (keep <= 40)")
    return errs, warns


def _strip_code(text: str) -> str:
    out, in_block = [], False
    for line in text.splitlines():
        if line.startswith("```"):
            in_block = not in_block
            continue
        if not in_block:
            out.append(re.sub(r"`[^`]*`", "", line))
    return "\n".join(out)


_URL_CACHE: dict[str, str | None] = {}


def _url_bad(url: str) -> str | None:
    if url in _URL_CACHE:
        return _URL_CACHE[url]
    res = None
    headers = {"User-Agent": "Mozilla/5.0 (lesson-link-check)"}
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, method=method, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as r:
                res = None if r.status < 400 else f"HTTP {r.status}"
            break
        except urllib.error.HTTPError as e:
            res = f"HTTP {e.code}"
            if method == "HEAD" and e.code in (403, 405, 429, 501):
                continue  # some hosts reject HEAD / bots; retry with GET
            break
        except urllib.error.URLError as e:
            # Corporate TLS interception ("self-signed certificate in certificate chain") is an
            # environment problem, not a dead link: retry existence-only without verification.
            if "CERTIFICATE_VERIFY_FAILED" in str(e) or "certificate" in str(e).lower():
                try:
                    import ssl
                    req = urllib.request.Request(url, method="GET", headers=headers)
                    with urllib.request.urlopen(req, timeout=15, context=ssl._create_unverified_context()) as r:
                        res = None if r.status < 400 else f"HTTP {r.status}"
                    break
                except urllib.error.HTTPError as e2:
                    res = f"HTTP {e2.code}"
                    break
                except Exception as e2:
                    res = type(e2).__name__
            else:
                res = type(e).__name__
        except Exception as e:  # DNS, timeout
            res = type(e).__name__
    if res and res.startswith("HTTP 429"):
        res = None  # rate-limited is not "broken"
    _URL_CACHE[url] = res
    return res


def extract_scripts(path: Path, out_dir: Path) -> list[Path]:
    """Write each script_id group (stitched in document order) to out_dir/<script_id>.py."""
    text = path.read_text(encoding="utf-8")
    bl, _ = blocks(text)
    groups: dict[str, list[str]] = {}
    for lang, _start, code in bl:
        if lang not in ("python", "py"):
            continue
        first = code.lstrip().splitlines()[0] if code.strip() else ""
        sm = SCRIPT_ID_RE.match(first.strip())
        if sm and "# fragment" not in code:
            groups.setdefault(sm.group(1), []).append(code)
    written = []
    for sid, parts in groups.items():
        f = out_dir / f"{sid}.py"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
        written.append(f)
    return written


def main(argv: list[str]) -> int:
    flags = {a for a in argv[1:] if a.startswith("--")}
    extract_to = next((a.split("=", 1)[1] for a in flags if a.startswith("--extract=")), None)
    paths = [Path(a) for a in argv[1:] if not a.startswith("--")]
    if not paths:
        print(__doc__)
        return 2
    opts = {
        "mermaid": "--mermaid" in flags,
        "online": "--online" in flags,
        "links_final": "--links-final" in flags,
        "template": "--no-template" not in flags,
        "budget": True if "--budget" in flags else False,
        "capstone": "--capstone" in flags,
    }
    files: list[Path] = []
    for p in paths:
        if p.is_dir():
            found = sorted(p.rglob("Day_*/*.md")) + sorted(p.rglob("Appendix_Primers/*.md"))
            # never check the archived v1 course or scratch artifacts
            files += [f for f in found if not ({"archive", ".restructure"} & set(f.relative_to(p).parts))]
        else:
            files += [p]
    if extract_to:
        for f in files:
            for w in extract_scripts(f, Path(extract_to)):
                print(f"extracted: {w}")
    total_hard = 0
    for f in files:
        hard, warn, st = check_file(f, opts)
        total_hard += len(hard)
        if hard or warn or "--quiet" not in flags:
            print(f"{f}  [{st['words']}w, {st['py_scripts']} scripts, {st['mermaid']} diagrams, {st['links']} links]")
            for e in hard:
                print(f"  ERROR: {e}")
            for w in warn:
                print(f"  warn:  {w}")
    print(f"\n{len(files)} file(s); {total_hard} error(s).")
    return 1 if total_hard else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
