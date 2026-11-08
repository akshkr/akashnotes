# LangGraph II: Durable Execution, Checkpoints & Time Travel

At step 4 of 6 the worker is redeployed. Everything the agent knew is gone, the tokens are spent again, and the comment it posted at step 3 gets posted a second time when the run restarts. Today you make the Atlas Issue Investigator durable: it saves its state after every step, resumes where it died, lets you rewind a bad run to debug it, and makes its side effects safe to repeat.

## At a Glance

- **Time:** ~2 h core (+ optional Go Deeper) · **Depth:** working
- **Prerequisites:** [Day 53: LangGraph I: Graphs, State & Routing](../Day_053_langgraph_graphs/langgraph_graphs.md); helpful: [Day 37: Robust Tool Execution: Parallel Calls, Errors & Approvals](../../Phase_4_Tools_and_MCP/Day_037_robust_tool_execution/robust_tool_execution.md) (`MockTracker`, `side_effect` flags), [Primer: SQL & Postgres](../../Appendix_Primers/A07_sql_postgres.md)
- **You'll build:** a durable Atlas graph (`make_checkpointer`, `thread_config`, `run_once`, `replay_from`), a crash-and-resume demo that ends with 0 duplicate comments, and a time-travel drill that forks a bad run.
- **Stops at:** checkpoint internals (serializers, encryption), distributed locking, and background workers/queues ([Day 78](../../Phase_9_Production/Day_078_async_jobs/async_jobs.md)).
- **Fast path:** Already know LangGraph checkpointers? Read "Idempotent Side Effects" and "Replay and Fork", run the crash demo, then do Exercise 3 (~45 min).
- **Cost:** $0 by default: every script uses a scripted model and no key. The optional live run (`ATLAS_LIVE=1`, four model calls) costs well under $0.01 on `gpt-6-luna` (prices as of 2026-11, [verify](https://developers.openai.com/api/docs/pricing)). Replays and forks call the model again, so they cost again.
- **New terms:** checkpointer / checkpoint, `thread_id`, state history (replay / fork), idempotency key, at-least-once vs exactly-once effect

> **Coming from Software Engineering?** A checkpoint is a database savepoint plus a git commit for agent state: every step is committed, you can `git log` the run, and you can check out an old commit and branch from it. `thread_id` is a session key. Resuming after a crash is a job queue's *at-least-once* redelivery: the step that was running when the process died runs again. So handlers with side effects must be **idempotent**, exactly like a webhook receiver that dedupes on the event id, or a payment API that accepts an `Idempotency-Key` header so a retried charge isn't charged twice.

## The Run That Died at Step 4

Take the Day 53 investigator on Orbit issue #96 ("`orbit worker --concurrency 8` is ignored when orbit.toml sets [worker] concurrency"). It searches past issues, reads a doc page, posts a comment and writes a diagnosis, all in process memory. Kill the process after the comment and the state is gone: a restart pays for every model call again and posts the comment twice. Deploys, out-of-memory kills and spot-instance reclaims all cause this, and long agent runs make it likely.

## Autosave and Save Slots

Think of a video game with autosave. Your **save slot** holds one playthrough, and the game **autosaves** each time you enter a room. After a crash you load the slot and continue from the last room, not the title screen.

In LangGraph the slot is a `thread_id` and the autosave is a **checkpoint**: a saved copy of the graph's state after each step. The game also teaches the catch: if you picked up the sword *after* the last autosave, you pick it up again. In an agent, the sword might be a posted comment.

## A Crash on Paper

Here is a four-step run with a checkpoint after each step. The crash hits during step 3: the comment is already posted, but checkpoint c3 never gets written.

| Step | Node does | Effect in the world | Checkpoint saved |
|---|---|---|---|
| 1 | search issues | none | c1 ✓ |
| 2 | read doc page | none | c2 ✓ |
| 3 | post comment | **comment #1 posted** | c3 ✗ (crash) |
| resume | load c2, run step 3 again | **comment #2 posted** | c3 ✓ |
| 4 | write diagnosis | none | c4 ✓ |

Check it in your head: the resume starts from the newest checkpoint that exists, c2, so step 3 runs twice. Steps 1 and 2 don't rerun, which saves tokens. The duplicate is the price of *at-least-once* execution (a step may run again after a crash). Getting *exactly-once* effects (the world sees each effect once) takes extra work at the effect itself, which is most of today.

## Name the Parts

- **Checkpointer:** the storage backend that writes and reads checkpoints. `InMemorySaver` (tests), `SqliteSaver` (one machine), `PostgresSaver` (many workers). You pass it to `compile(checkpointer=...)`.
- **Checkpoint:** one saved state, written after each step (LangGraph calls a step a *super-step*: every node that runs in one tick of the graph). Each has a `checkpoint_id` and a parent.
- **Thread:** all checkpoints filed under one `thread_id`. Config: `{"configurable": {"thread_id": "issue-96"}}`.
- **`StateSnapshot`:** what `app.get_state(cfg)` returns: `.values` (the state), `.next` (the nodes that run next), `.config` (points at this checkpoint), `.metadata["step"]`.
- **State history:** `app.get_state_history(cfg)` lists every snapshot, newest first. **Replay** re-runs from an old checkpoint. **Fork** writes an edited checkpoint with `update_state` and runs from that, creating a new branch.
- **Idempotency key:** a stable id for one intended effect, so a repeat with the same key is recognised and skipped.

```mermaid
flowchart LR
    S(["START"]) --> c0["c0: input"] --> c1["c1: searched"] --> c2["c2: read doc"] --> c3["c3: commented"] --> E(["END"])
    c1 -.->|"update_state (fork)"| f2["c2': read the right doc"] --> f3["c3': commented"] --> E2(["END"])
    T["thread_id = issue-96 (the save slot)"] --- c0
```

A fork adds a branch; it never overwrites.

## Save and Reload in 20 Lines

Install the SQLite checkpointer. It is a separate package from `langgraph`:

```bash
uv add langgraph langgraph-checkpoint-sqlite
```

This graph appends a step name per node. You run it, throw the graph object away, build a fresh one on the same file, and read the state back.

```python
# script_id: day_054_langgraph_durability/checkpoint_min
# Save a graph's state to SQLite, then read it back from a brand-new graph object.
# Install: uv add langgraph langgraph-checkpoint-sqlite · no API key, no services
import operator, sqlite3
from pathlib import Path
from typing import Annotated, TypedDict
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

class State(TypedDict):
    steps: Annotated[list[str], operator.add]   # reducer: node outputs are appended

def build(path: str):
    g = StateGraph(State)
    g.add_node("a", lambda s: {"steps": ["a"]})
    g.add_node("b", lambda s: {"steps": ["b"]})
    g.add_edge(START, "a"); g.add_edge("a", "b"); g.add_edge("b", END)
    saver = SqliteSaver(sqlite3.connect(path, check_same_thread=False))
    return g.compile(checkpointer=saver)

for old in Path(".").glob("ckpt.db*"):   # start clean: reruns would CONTINUE the old thread
    old.unlink()

cfg = {"configurable": {"thread_id": "t1"}, "recursion_limit": 25}
build("ckpt.db").invoke({"steps": []}, cfg)      # first "process" runs the graph
fresh = build("ckpt.db")                         # second "process": new objects, same file
print("t1", fresh.get_state(cfg).values, "· next:", fresh.get_state(cfg).next)
```

```text
t1 {'steps': ['a', 'b']} · next: ()
```

`next: ()` means the thread finished: no node is pending. The second graph object never ran anything, yet it sees the state, because the state lives in `ckpt.db`, not in the process.

## Break It

Four mistakes cause most first-day checkpoint bugs. Three of them are reproduced here:

```python
# script_id: day_054_langgraph_durability/break_it
# Three ways to get checkpointing wrong, each caught and printed. No API key, no services.
import operator, sqlite3
from pathlib import Path
from typing import Annotated, TypedDict
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

class State(TypedDict):
    steps: Annotated[list[str], operator.add]

for old in Path(".").glob("break.db*"):   # start clean: reruns would CONTINUE the old thread
    old.unlink()

g = StateGraph(State)
g.add_node("a", lambda s: {"steps": ["a"]})
g.add_edge(START, "a"); g.add_edge("a", END)

# 1. from_conn_string returns a context manager, not a saver.
try:
    g.compile(checkpointer=SqliteSaver.from_conn_string("break.db"))
except TypeError as e:
    print("1.", str(e)[:70])
with SqliteSaver.from_conn_string("break.db") as saver:   # the right way to use it
    app = g.compile(checkpointer=saver)
    # 2. A checkpointer with no thread_id has nowhere to file the save.
    try:
        app.invoke({"steps": []})
    except ValueError as e:
        print("2.", str(e)[:70])
    # 3. Two users sharing one thread_id read and write the SAME state.
    shared = {"configurable": {"thread_id": "support"}, "recursion_limit": 25}
    app.invoke({"steps": ["alice-secret"]}, shared)
    print("3. bob sees:", app.invoke({"steps": ["bob"]}, shared)["steps"])
```

```text
1. Invalid checkpointer provided. Expected an instance of `BaseCheckpoint
2. Checkpointer requires one or more of the following 'configurable' keys
3. bob sees: ['alice-secret', 'a', 'bob', 'a']
```

1. **`from_conn_string` is a context manager**, not a saver, so `compile` raises `TypeError: Invalid checkpointer provided...`. Use `with ... as saver:` or the direct form `SqliteSaver(sqlite3.connect(path, check_same_thread=False))` that `make_checkpointer` uses below.
2. **No `thread_id`.** `ValueError: Checkpointer requires one or more of the following 'configurable' keys: thread_id, checkpoint_ns, checkpoint_id`.
3. **Shared `thread_id`.** Bob's run continued Alice's state and can read her data. Thread ids are an isolation boundary: derive them from the entity you're working on, never from a constant.
4. **Missing package.** With only `langgraph` installed, the import fails with `ModuleNotFoundError: No module named 'langgraph.checkpoint.sqlite'`. Add `langgraph-checkpoint-sqlite`.

Notice that `checkpoint_min` first deletes old `ckpt.db` files: invoking with an input on an existing thread *continues* it (the reducer appends again). That's correct, and it surprises everyone once.

## Crash and Resume the Real Agent

Now the same idea on the Atlas investigator. The code below is one script, `durable_graph.py`, split into blocks that share a `script_id`; save it once and the later scripts import from it. The first block adds the two helpers every durable run needs:

```python
# script_id: day_054_langgraph_durability/durable_graph
# Day 54 additions to atlas/graph.py: a durable Issue Investigator you can crash, resume and fork.
# Install: uv add langgraph langgraph-checkpoint-sqlite langchain-core (live mode also: langchain langchain-openai)
# Env: ORBIT_DATA (default datasets/orbit) · ATLAS_DIR (default .atlas) · ATLAS_LEDGER (optional)
#      ATLAS_CRASH_AT (demo only) · ATLAS_LIVE=1 + OPENAI_API_KEY for a real model (optional)
# Services: none; everything is SQLite files under ATLAS_DIR.
import hashlib, json, os, sqlite3
from pathlib import Path
from typing import Any, Callable
from langgraph.checkpoint.sqlite import SqliteSaver

DATA_DIR = Path(os.environ.get("ORBIT_DATA", "datasets/orbit"))
ATLAS_DIR = Path(os.environ.get("ATLAS_DIR", ".atlas"))
MODEL = os.environ.get("ATLAS_MODEL", "gpt-6-luna")


def make_checkpointer(path: str | Path) -> SqliteSaver:
    """A SqliteSaver that lives as long as the process, so no `with` block is needed."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False because LangGraph may use the connection from worker threads.
    return SqliteSaver(sqlite3.connect(str(path), check_same_thread=False))


def thread_config(thread_id: str, recursion_limit: int = 25) -> dict:
    """The config for every invoke/get_state call. The default limit is 10007, so set your own."""
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": recursion_limit}
```

`thread_config` exists because the default `recursion_limit` (the maximum number of steps per invoke) is 10007, not 25. A resumed thread with a looping bug would burn a lot of tokens before hitting that, so you pass a real limit on every call.

Next come compact copies of the Day 37 tracker and the Day 35 tools. The tracker writes each comment as one JSONL line, so a duplicate is a second line you can count:

```python
# script_id: day_054_langgraph_durability/durable_graph
# built on Day 37 (MockTracker) and Day 35 (tools): compact copies, not imports.
class MockTracker:
    """A fake issue tracker. Each side effect is one JSONL line, so duplicates are easy to see."""
    def __init__(self, path: str | Path):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)

    def post_comment(self, issue_id: int, body: str, idempotency_key: str | None = None) -> dict:
        # Like most real APIs without key support, this one ignores idempotency_key.
        return self._append({"action": "post_comment", "issue_id": issue_id, "body": body})

    def _append(self, rec: dict) -> dict:
        with self.path.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        return {"ok": True, "comment_no": len(self.actions())}

    def actions(self) -> list[dict]:
        lines = self.path.read_text().splitlines() if self.path.exists() else []
        return [json.loads(line) for line in lines if line]


def load_issue(issue_id: int) -> dict:
    for line in (DATA_DIR / "issues" / "issues.jsonl").read_text().splitlines():
        if json.loads(line)["id"] == issue_id:
            return json.loads(line)
    raise KeyError(issue_id)


def search_issues(query: str, k: int = 3) -> list[dict]:
    """Keyword stand-in for Day 35's search: the issues sharing the most words with the query."""
    words = set(query.lower().split())
    rows = [json.loads(l) for l in (DATA_DIR / "issues" / "issues.jsonl").read_text().splitlines()]
    scored = sorted(rows, key=lambda r: -len(words & set(r["title"].lower().split())))
    return [{"id": r["id"], "title": r["title"]} for r in scored[:k]]


def get_doc_section(doc_id: str, max_chars: int = 400) -> str:
    """Read the start of one Orbit doc page by id, e.g. 'configuration-reference'."""
    path = DATA_DIR / "docs" / f"{Path(doc_id).name}.md"   # .name blocks "../" escapes
    return path.read_text()[:max_chars] if path.exists() else f"ERROR: no doc '{doc_id}'"
```

The model is pluggable. `ScriptedModel` has the same `.invoke(messages) -> AIMessage` shape as a LangChain chat model, so the graph can't tell them apart. It always does the same thing: search, read one doc, comment, answer. That makes the crash demo deterministic and keyless:

```python
# script_id: day_054_langgraph_durability/durable_graph
# built on Day 53: the same three-node graph, now with a checkpointer and a pluggable model.
from typing import Annotated, TypedDict
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    messages: Annotated[list, add_messages]   # reducer: appends, or replaces a message by id
    issue_id: int
    answer: str


class ScriptedModel:
    """Keyless stand-in for the LLM: search, read one doc, comment, answer. Same .invoke() shape."""
    def __init__(self, doc_id: str = "configuration-reference"):
        self.doc_id = doc_id

    def invoke(self, messages: list) -> AIMessage:
        n = sum(isinstance(m, ToolMessage) for m in messages)
        issue_id = int(messages[0].content.split("#")[1].split(":")[0])
        last_doc = next((c["args"]["doc_id"] for m in reversed(messages)
                         if isinstance(m, AIMessage) for c in m.tool_calls
                         if c["name"] == "get_doc_section"), self.doc_id)
        plan = [("search_issues", {"query": messages[0].content}),
                ("get_doc_section", {"doc_id": self.doc_id}),
                ("post_comment", {"issue_id": issue_id, "body": f"Likely config precedence; see {last_doc}."})]
        if n < len(plan):
            name, args = plan[n]
            return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"call_{n}"}])
        return AIMessage(content=f"Diagnosis for #{issue_id}: see {last_doc}.")
```

The graph is the Day 53 three-node loop (`call_model → run_tools → call_model … → finalize`), with the checkpointer passed to `compile`:

```python
# script_id: day_054_langgraph_durability/durable_graph
def build_agent_graph(tools: dict[str, Callable], *, model: Any = None, checkpointer: Any = None):
    model = model or ScriptedModel()

    def call_model(state: AgentState) -> dict:
        return {"messages": [model.invoke(state["messages"])]}

    def run_tools(state: AgentState) -> dict:
        out = []
        for call in state["messages"][-1].tool_calls:
            fn = tools.get(call["name"])
            result = fn(**call["args"]) if fn else f"ERROR: unknown tool {call['name']}"
            out.append(ToolMessage(json.dumps(result), tool_call_id=call["id"], name=call["name"]))
        return {"messages": out}

    def finalize(state: AgentState) -> dict:
        # .text, not .content: a live Responses API reply's content is a list of blocks.
        return {"answer": str(state["messages"][-1].text)}

    g = StateGraph(AgentState)
    g.add_node("call_model", call_model)
    g.add_node("run_tools", run_tools)
    g.add_node("finalize", finalize)
    g.add_edge(START, "call_model")
    g.add_conditional_edges("call_model",
                            lambda s: "run_tools" if s["messages"][-1].tool_calls else "finalize",
                            ["run_tools", "finalize"])
    g.add_edge("run_tools", "call_model")
    g.add_edge("finalize", END)
    return g.compile(checkpointer=checkpointer)


def start_input(issue_id: int) -> dict:
    issue = load_issue(issue_id)
    return {"issue_id": issue_id, "messages": [HumanMessage(f"Investigate issue #{issue_id}: {issue['title']}")]}
```

Run the module once to see a normal run (your checkpoint count may differ if you change the graph):

```text
Diagnosis for #96: see configuration-reference. · checkpoints: 10 · tracker lines: 1
```

Here is what happens when the process dies inside `run_tools`, right after the comment tool returns. The checkpoint for step 5 (`call_model` produced the `post_comment` call) is on disk. The checkpoint for step 6 never will be:

```mermaid
sequenceDiagram
    participant W as Worker process
    participant G as Graph
    participant T as MockTracker
    participant DB as SQLite checkpoints
    G->>DB: save step 5 (next = run_tools)
    G->>T: post_comment(96, ...)
    T-->>G: comment #1 written
    W--xW: os._exit(1) before step 6 is saved
    Note over W: redeploy, new process
    W->>DB: get_state(issue-96)
    DB-->>G: step 5, next = run_tools
    G->>T: post_comment(96, ...) again
    T-->>G: comment #2 (duplicate)
```

Two details make this demo honest. The crash uses `os._exit(1)`, which kills the process without any cleanup, like a `SIGKILL`. And the runs use `invoke(..., durability="sync")`, which writes each checkpoint *before* the next step starts, so the result never depends on timing (the other modes are in Go Deeper). To resume, call `invoke(None, cfg)`: `None` means "continue this thread", while passing the original input again would add a second copy of the issue to the state.

## Idempotent Side Effects

This day owns the fix that Day 55 and the R3 capstone reuse. An effect is **idempotent** when doing it twice has the same result as doing it once. Reading a doc is naturally idempotent. Posting a comment is not, which is why Day 37 flags it `side_effect=True, idempotent=False`. To make it safe, you give each intended effect an **idempotency key** and record it in a ledger:

```python
# script_id: day_054_langgraph_durability/durable_graph
def effect_key(action: str, args: dict, scope: str = "") -> str:
    """Same action + same args (+ same scope, e.g. a thread_id) gives the same key."""
    blob = json.dumps({"action": action, "args": args, "scope": scope}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def run_once(key: str, fn: Callable[[], Any]) -> Any:
    """Run fn at most once per key. A repeat returns the stored result and skips fn."""
    ledger = Path(os.environ.get("ATLAS_LEDGER", ATLAS_DIR / "effects.sqlite"))
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(ledger) as db:
        db.execute("CREATE TABLE IF NOT EXISTS effects (key TEXT PRIMARY KEY, result TEXT)")
        row = db.execute("SELECT result FROM effects WHERE key = ?", (key,)).fetchone()
    if row:
        return json.loads(row[0])
    result = fn()   # a crash after fn() but before the INSERT below still repeats the effect
    with sqlite3.connect(ledger) as db:
        db.execute("INSERT OR REPLACE INTO effects VALUES (?, ?)", (key, json.dumps(result)))
    return result


def crash_if(point: str) -> None:
    """Demo switch: simulate a redeploy at a named point (os._exit skips all cleanup)."""
    if os.environ.get("ATLAS_CRASH_AT") == point:
        os._exit(1)
```

`run_once` checks the ledger, runs the effect only if the key is new, and stores the result so a repeat returns the same answer. The key is a hash of the action, its arguments and a *scope*. You'll pick the scope in Exercise 3.

Read the comment in the middle of `run_once` carefully. If the process dies after `fn()` posts the comment but before the `INSERT`, the ledger never learns about it, and the resume posts again. A local ledger can't close that window, because the effect and the ledger write are two separate systems. The real fix is on the remote side: send the key with the request and let the API refuse a repeat. Stripe-style payment APIs do this with an `Idempotency-Key` header. `KeyedTracker` simulates such an API, and `make_tools` wires the key through, plus the crash switch for the demo:

```python
# script_id: day_054_langgraph_durability/durable_graph
class KeyedTracker(MockTracker):
    """A tracker that honours idempotency keys, like an API with an Idempotency-Key header."""
    def post_comment(self, issue_id: int, body: str, idempotency_key: str | None = None) -> dict:
        if idempotency_key and any(a.get("key") == idempotency_key for a in self.actions()):
            return {"ok": True, "deduplicated": True}
        return self._append({"action": "post_comment", "issue_id": issue_id, "body": body,
                             "key": idempotency_key})


def make_tools(tracker: MockTracker, *, safe: bool = True, scope: str = "") -> dict[str, Callable]:
    def post_comment(issue_id: int, body: str) -> dict:
        """Post a comment on an Orbit issue (a side effect: safe to repeat only via run_once)."""
        key = effect_key("post_comment", {"issue_id": issue_id, "body": body}, scope)
        def effect() -> dict:
            crash_if("before_effect")
            out = tracker.post_comment(issue_id, body, idempotency_key=key)
            crash_if("mid_effect")          # effect done, ledger not written yet
            return out
        result = run_once(key, effect) if safe else effect()
        crash_if("after_tool")              # tool finished, checkpoint not written yet
        return result
    return {"search_issues": search_issues, "get_doc_section": get_doc_section,
            "post_comment": post_comment}
```

The last two blocks add `replay_from` (used in the next section), an optional live model, and a builder that wires everything together:

```python
# script_id: day_054_langgraph_durability/durable_graph
def replay_from(cfg: dict, checkpoint_id: str) -> dict:
    """A config that makes app.invoke(None, it) re-run every step AFTER that checkpoint."""
    return {**cfg, "configurable": {**cfg["configurable"], "checkpoint_id": checkpoint_id}}


def make_live_model(tools: dict[str, Callable]) -> Any:
    """Optional real model (needs OPENAI_API_KEY). Imported lazily so the demo stays keyless."""
    from langchain.chat_models import init_chat_model
    return init_chat_model(f"openai:{MODEL}", use_responses_api=True).bind_tools(list(tools.values()))


def build_durable_agent(run_dir: str | Path, *, safe: bool = True, thread_id: str = "issue-96",
                        tracker: MockTracker | None = None):
    run_dir = Path(run_dir)
    tracker = tracker or MockTracker(run_dir / "tracker.jsonl")
    tools = make_tools(tracker, safe=safe, scope=thread_id)
    model = make_live_model(tools) if os.environ.get("ATLAS_LIVE") == "1" else None
    app = build_agent_graph(tools, model=model, checkpointer=make_checkpointer(run_dir / "ckpt.sqlite"))
    return app, thread_config(thread_id), tracker
```

```python
# script_id: day_054_langgraph_durability/durable_graph
def fresh_run_dir(name: str) -> Path:
    """An empty demo folder with its own effects ledger, so every rerun starts clean."""
    import shutil
    run_dir = ATLAS_DIR / name
    shutil.rmtree(run_dir, ignore_errors=True)
    run_dir.mkdir(parents=True)
    os.environ["ATLAS_LEDGER"] = str(run_dir / "effects.sqlite")   # children inherit it
    return run_dir


if __name__ == "__main__":
    app, cfg, tracker = build_durable_agent(fresh_run_dir("smoke"))
    out = app.invoke(start_input(96), cfg, durability="sync")
    print(out["answer"], "· checkpoints:", len(list(app.get_state_history(cfg))),
          "· tracker lines:", len(tracker.actions()))
```

Now the demo. It starts the agent in a child process with a crash point set, lets it die, then resumes it in a second process and counts tracker lines. Four rows, one change each:

```python
# script_id: day_054_langgraph_durability/crash_resume_demo
# Kill the agent mid-run in a child process, restart it, and count the comments it posted.
# Usage: python crash_resume_demo.py            (all four rows)
# Needs durable_graph.py from this lesson next to it. No API key, no services.
import os, subprocess, sys
from durable_graph import (KeyedTracker, MockTracker, build_durable_agent, fresh_run_dir,
                           start_input)

ROWS = [  # name, safe (run_once), crash point, tracker class
    ("naive", False, "after_tool", "MockTracker"),
    ("run_once", True, "after_tool", "MockTracker"),
    ("run_once, crash mid-effect", True, "mid_effect", "MockTracker"),
    ("run_once + keyed API", True, "mid_effect", "KeyedTracker"),
]


def child(run_dir: str, safe: str, tracker_cls: str, phase: str) -> None:
    tracker = {"MockTracker": MockTracker, "KeyedTracker": KeyedTracker}[tracker_cls](
        f"{run_dir}/tracker.jsonl")
    app, cfg, _ = build_durable_agent(run_dir, safe=safe == "1", tracker=tracker)
    if phase == "start":
        app.invoke(start_input(96), cfg, durability="sync")   # sync: each checkpoint hits disk first
    else:
        snap = app.get_state(cfg)
        print(f"   resuming at step {snap.metadata['step']}, next={snap.next}")
        app.invoke(None, cfg, durability="sync")              # None = continue, don't restart


def main(rows: list[tuple] = ROWS) -> None:
    for i, (name, safe, point, tracker_cls) in enumerate(rows):
        run_dir = str(fresh_run_dir(f"crash_{i}"))
        args = [sys.executable, os.path.abspath(__file__), "child", run_dir,
                "1" if safe else "0", tracker_cls]
        died = subprocess.run(args + ["start"], env={**os.environ, "ATLAS_CRASH_AT": point}).returncode
        subprocess.run(args + ["resume"], check=True)
        comments = len(MockTracker(f"{run_dir}/tracker.jsonl").actions())
        print(f"{name:28} crash at {point:10} exit={died} · comments={comments}")


if __name__ == "__main__":
    child(*sys.argv[2:]) if sys.argv[1:2] == ["child"] else main()
```

```text
   resuming at step 5, next=('run_tools',)
naive                        crash at after_tool exit=1 · comments=2
   resuming at step 5, next=('run_tools',)
run_once                     crash at after_tool exit=1 · comments=1
   resuming at step 5, next=('run_tools',)
run_once, crash mid-effect   crash at mid_effect exit=1 · comments=2
   resuming at step 5, next=('run_tools',)
run_once + keyed API         crash at mid_effect exit=1 · comments=1
```

Row by row: the naive run duplicates; `run_once` fixes the common case; a crash between the effect and the ledger write still duplicates; only an API that honours the key gets back to one comment. That last row is today's Atlas scoreboard entry: **duplicate side effects after a crash = 0**. Without remote idempotency support the window stays open; the next best mitigation is to check for the effect before repeating it (for example, search the issue's comments for your key).

## Replay and Fork

Durability gives you debugging for free: every step is on disk. `get_state_history` lists the snapshots newest first. Pick one, and `replay_from` builds a config that points at it; `invoke(None, that_config)` re-runs every step after it.

```python
# script_id: day_054_langgraph_durability/history_replay
# List a finished run's checkpoints, then replay from the one just before the comment.
# Needs durable_graph.py from this lesson next to it. No API key, no services.
from durable_graph import build_durable_agent, fresh_run_dir, replay_from, start_input

app, cfg, tracker = build_durable_agent(fresh_run_dir("history"))
app.invoke(start_input(96), cfg)

history = list(app.get_state_history(cfg))           # newest first
print(f"{'step':>4}  {'next':<15} msgs  checkpoint_id (tail)")
for snap in reversed(history):
    print(f"{snap.metadata['step']:>4}  {str(snap.next):<15} {len(snap.values.get('messages', [])):>4}"
          f"  {snap.config['configurable']['checkpoint_id'][-8:]}")

# The checkpoint whose next step runs the post_comment tool call.
before_comment = next(s for s in history if s.next == ("run_tools",)
                      and s.values["messages"][-1].tool_calls[0]["name"] == "post_comment")
cid = before_comment.config["configurable"]["checkpoint_id"]
app.invoke(None, replay_from(cfg, cid))                # re-runs run_tools → call_model → finalize
print("replayed from step", before_comment.metadata["step"],
      "· checkpoints now:", len(list(app.get_state_history(cfg))),
      "· tracker lines:", len(tracker.actions()))      # still 1: run_once caught the repeat
```

```text
step  next            msgs  checkpoint_id (tail)
  -1  ('__start__',)     0  d1f80671
   0  ('call_model',)    1  b2691925
   1  ('run_tools',)     2  f9c93268
   2  ('call_model',)    3  4b23aed8
   3  ('run_tools',)     4  771d2239
   4  ('call_model',)    5  ec0d579b
   5  ('run_tools',)     6  60799de7
   6  ('call_model',)    7  2343edc6
   7  ('finalize',)      8  81f2f407
   8  ()                 8  7b9a7fb7
replayed from step 5 · checkpoints now: 14 · tracker lines: 1
```

Your ids will differ. A replay **re-executes** nodes: the tools run again, and a live model is called and charged again. The tracker still has one line only because `run_once` caught the repeat. And history only grows: the replay added four checkpoints (10 → 14) instead of rewriting old ones.

A **fork** goes one step further: you change the state before continuing. `app.update_state(snapshot.config, values, as_node=...)` does **not** edit the old checkpoint in place. It writes a *new* checkpoint whose parent is the one you gave, passes your values through the reducers, and returns the new config. You must invoke *that* config. `as_node="call_model"` tells LangGraph to treat the update as if `call_model` produced it, so routing continues to `run_tools`.

## Drill: Debug a Bad Step by Time Travel

A recorded run on issue #96 gave a wrong diagnosis. It's a 3.x issue, but the model read `environment-variables-2x`, a 2.x page. Your job: find the step, fork with the right doc, rerun only the tail, and compare.

```python
# script_id: day_054_langgraph_durability/time_travel_drill
# A recorded bad run read a 2.x doc for a 3.x issue. Find the step, fork with a fix, compare.
# Needs durable_graph.py from this lesson next to it. No API key, no services.
from langchain_core.messages import AIMessage
from durable_graph import (MockTracker, ScriptedModel, build_agent_graph, fresh_run_dir,
                           make_checkpointer, make_tools, start_input, thread_config)

run_dir = fresh_run_dir("drill")
tracker = MockTracker(run_dir / "tracker.jsonl")
app = build_agent_graph(make_tools(tracker, scope="issue-96"),
                        model=ScriptedModel(doc_id="environment-variables-2x"),   # the bug
                        checkpointer=make_checkpointer(run_dir / "ckpt.sqlite"))
cfg = thread_config("issue-96")
bad = app.invoke(start_input(96), cfg)
print("bad run:  ", bad["answer"])

# 1. Find the checkpoint where the model had just asked for the wrong doc.
history = list(app.get_state_history(cfg))
snap = next(s for s in history if s.next == ("run_tools",)
            and s.values["messages"][-1].tool_calls[0]["name"] == "get_doc_section")
wrong = snap.values["messages"][-1]
print("culprit:   step", snap.metadata["step"], wrong.tool_calls[0]["args"])

# 2. Fork: same message id, so add_messages REPLACES it instead of appending.
fixed = AIMessage(id=wrong.id, content="", tool_calls=[
    {**wrong.tool_calls[0], "args": {"doc_id": "configuration-reference"}}])
fork_cfg = app.update_state(snap.config, {"messages": [fixed]}, as_node="call_model")
good = app.invoke(None, fork_cfg)
print("fork run: ", good["answer"])
print("checkpoints:", len(history), "→", len(list(app.get_state_history(cfg))),
      "· comments:", [a["body"] for a in tracker.actions()])
```

```text
bad run:   Diagnosis for #96: see environment-variables-2x.
culprit:   step 3 {'doc_id': 'environment-variables-2x'}
fork run:  Diagnosis for #96: see configuration-reference.
checkpoints: 10 → 16 · comments: ['Likely config precedence; see environment-variables-2x.', 'Likely config precedence; see configuration-reference.']
```

The trick is the message `id`. The `add_messages` reducer appends new messages but **replaces** a message with the same id, so the corrected `AIMessage` takes the place of the bad tool call instead of sitting next to it. The fork skipped steps 0–2, which is where long runs save tokens.

Look at the comments: the fork posted a corrected one, and the bad one is still there. Time travel rewinds *your* state, never the outside world. Undoing an effect needs its own action, and an approval gate before posting is what [Day 55](../Day_055_human_in_the_loop/human_in_the_loop.md) adds. [Day 58](../Day_058_debugging_agents/debugging_agents.md) builds its failure detectors on the same `get_state_history`.

## Picking a Checkpointer and Thread IDs

All three savers implement the same interface, so swapping one is a one-line change at `compile`.

| Checkpointer | Package | Survives a restart? | Many workers? | Use it for |
|---|---|---|---|---|
| `InMemorySaver` | `langgraph` | no | no | unit tests, notebooks, `interrupt()` demos |
| `SqliteSaver` | `langgraph-checkpoint-sqlite` | yes | one machine, one writer | local dev, single-box tools, this lesson |
| `PostgresSaver` | `langgraph-checkpoint-postgres` + `psycopg[binary]` | yes | yes | production with several workers |

```mermaid
flowchart TD
    Q1{"Must a run survive a restart?"} -- no --> M["InMemorySaver (tests)"]
    Q1 -- yes --> Q2{"More than one worker process or machine?"}
    Q2 -- no --> S["SqliteSaver (one file)"]
    Q2 -- yes --> P["PostgresSaver (shared DB)"]
    P --> L["Effects ledger must be shared too"]
```

The Postgres version, against the database from [Day 26](../../Phase_3_RAG/Day_026_pgvector_search/pgvector_search.md), is shown as a fragment because no Postgres runs in this lesson:

```python
# script_id: day_054_langgraph_durability/postgres_fragment
# fragment
# uv add langgraph-checkpoint-postgres "psycopg[binary]" · needs Postgres (compose.yaml, Day 26)
# Env: DATABASE_URL, e.g. postgresql://user:password@localhost:5432/atlas
import os
from langgraph.checkpoint.postgres import PostgresSaver
from durable_graph import MockTracker, build_agent_graph, make_tools, start_input, thread_config

with PostgresSaver.from_conn_string(os.environ["DATABASE_URL"]) as saver:
    saver.setup()   # once per database: creates the checkpoint tables (safe to call again)
    tools = make_tools(MockTracker(".atlas/pg/tracker.jsonl"), scope="issue-96")
    app = build_agent_graph(tools, checkpointer=saver)
    app.invoke(start_input(96), thread_config("issue-96"), durability="sync")
```

**Thread ids are a design decision.** Use the business entity plus the attempt: `thread_id = f"issue-{issue_id}"` if one issue has one long-lived investigation, or `f"issue-{issue_id}-{attempt}"` if each re-investigation should start clean. Never share an id across users or tenants. Resume and replay reuse the same id; a new investigation gets a new one.

## Trade-offs and When NOT to Use It

| Situation | Checkpoint every step? | Why |
|---|---|---|
| One model call, a few seconds | no | a retry is cheaper than the machinery |
| Multi-step agent, tools, minutes | yes | resume saves tokens and avoids redoing effects |
| Needs human approval (Day 55) | yes, required | `interrupt()` pauses by saving a checkpoint |
| Huge state (whole documents in state) | yes, but slim it | every step stores a full copy; keep ids in state, content in storage |

Checkpoints cost one write per step and disk that grows with steps × state size.

### In production

- Use Postgres for more than one worker, and run **one worker per thread at a time**: two workers resuming the same thread would both execute the pending step. Use a queue or a lock ([Day 78](../../Phase_9_Production/Day_078_async_jobs/async_jobs.md)).
- Checkpoints contain everything in state, including user text and PII. Set retention and delete old threads (`SqliteSaver` has `delete_thread(thread_id)`); [Day 73](../../Phase_8_Safety_and_Security/Day_073_privacy_pii/privacy_pii.md) covers the policy.
- State-schema changes break old checkpoints. Add a `schema_version` field to state, and migrate or start new threads after a deploy that changes the shape.
- Emit a metric and a trace attribute for every resume ([Day 42](../../Phase_5_Evaluation_and_Observability/Day_042_tracing_observability/tracing_observability.md)); a spike in resumes means something keeps crashing.
- Every tool with `side_effect=True` goes through `run_once` with a key the remote API honours, wherever it supports one.

## Go Deeper (optional)

<details><summary>Go deeper: what is inside the checkpoint file</summary>

The SQLite checkpointer uses two tables. `checkpoints` has one row per checkpoint: ids, the parent id, the serialized state blob and JSON metadata. `writes` holds *pending writes*: the outputs each task produced within a step, keyed by task. They let LangGraph keep the work of nodes that finished in a step even if a sibling node in the same step failed. This script runs the agent and prints the schema (column names verified against `langgraph-checkpoint-sqlite` 3.1.3; treat them as an implementation detail that can change):

```python
# script_id: day_054_langgraph_durability/inspect_sqlite
# Look inside a checkpoint file: two tables, one row per checkpoint, one row per pending write.
# Needs durable_graph.py from this lesson next to it. No API key, no services.
import json, sqlite3
from durable_graph import build_durable_agent, fresh_run_dir, start_input

run_dir = fresh_run_dir("inspect")
app, cfg, _ = build_durable_agent(run_dir)
app.invoke(start_input(96), cfg)

db = sqlite3.connect(run_dir / "ckpt.sqlite")
for (table,) in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'"):
    cols = [c[1] for c in db.execute(f"PRAGMA table_info({table})")]
    count = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"{table:12} rows={count:<3} cols={cols}")

cid, parent, meta = db.execute(
    "SELECT checkpoint_id, parent_checkpoint_id, metadata FROM checkpoints "
    "WHERE thread_id = ? ORDER BY checkpoint_id DESC LIMIT 1", (cfg["configurable"]["thread_id"],)
).fetchone()
print("newest:", cid[-8:], "parent:", parent[-8:], "metadata:", json.loads(meta))
```

```text
checkpoints  rows=10  cols=['thread_id', 'checkpoint_ns', 'checkpoint_id', 'parent_checkpoint_id', 'type', 'checkpoint', 'metadata']
writes       rows=18  cols=['thread_id', 'checkpoint_ns', 'checkpoint_id', 'task_id', 'task_path', 'idx', 'channel', 'type', 'value']
newest: 377bf249 parent: 32285c41 metadata: {'source': 'loop', 'step': 8, 'parents': {}}
```

`checkpoint_ns` is the namespace for subgraphs (empty for the top-level graph). Don't query these tables in application code: use `get_state` and `get_state_history`, which deserialize for you.

</details>

<details><summary>Go deeper: the three durability modes</summary>

`invoke`, `stream` and their async versions take `durability=` with three values (the `Durability` literal in `langgraph.types`, 1.2.20):

| Mode | When the checkpoint is written | Crash cost |
|---|---|---|
| `"sync"` | before the next step starts | lose at most the step that was running |
| `"async"` (default) | while the next step runs | usually the same; a crash can also land before the previous save completes |
| `"exit"` | only when the graph exits (finish, error or interrupt) | lose the whole run in progress |

`"sync"` adds the write latency to every step; `"async"` hides it. `"exit"` is the fastest and suits short graphs where you only want the final state for history. For crash tests, use `"sync"` so the result doesn't depend on timing. Production agents with side effects usually keep the default and rely on idempotency keys, since no mode removes the effect-then-crash window.

</details>

<details><summary>Go deeper: tool-call ids as idempotency keys</summary>

Another natural key is the model's tool-call id (`call["id"]` in `run_tools`). It's stable across a **resume**, because the `AIMessage` that holds it was checkpointed before the crash. It is *not* stable across a **replay** from an earlier step or a fork, because `call_model` runs again and a live model returns a new id. So a call-id key prevents crash duplicates but lets a replay post again, while a content-hash key dedupes replays but also dedupes legitimate repeats (Exercise 3). Many teams combine them: scope by thread, hash the content, and log the call id for tracing. A live model also rewords its comment on replay, which changes the content hash; if replays must never post again, key on the *intent* (action + issue + thread), not the exact text.

</details>

## Common Pitfalls

- **`TypeError: Invalid checkpointer provided ... Received _GeneratorContextManager`.** You passed `SqliteSaver.from_conn_string(...)` directly. Use `with ... as saver:` or `make_checkpointer(path)`.
- **The resumed run starts over, or has no history.** The `thread_id` differs from the crashed run, or you called `invoke(input, cfg)` instead of `invoke(None, cfg)`. Resume with `None` on the same thread.
- **A duplicate comment after resume.** The node re-ran after the effect but before its checkpoint. Route the effect through `run_once` and send the key to the remote API; use `durability="sync"` when testing crashes.
- **`update_state` "didn't change anything".** It returns a *new* config; invoking the old one ignores the fork. Values go through reducers, so a message without the old `id` is appended, not replaced.
- **Old threads fail after a deploy** with a key error or validation error inside a node. The state shape changed. Version the state and migrate, or start new threads.
- **A resumed thread loops for thousands of steps.** The default `recursion_limit` is 10007. Pass `thread_config(..., recursion_limit=N)` on every call; overruns raise `GraphRecursionError`.

> **Where we stop:** we don't cover how checkpoints are serialized, custom serializers, encryption at rest, distributed locking or queue workers; the first four are framework internals (see the [checkpoint-sqlite source](https://github.com/langchain-ai/langgraph/tree/main/libs/checkpoint-sqlite)), and workers are [Day 78](../../Phase_9_Production/Day_078_async_jobs/async_jobs.md).

## Key Takeaways

- A crash loses in-memory state, re-spends tokens and repeats side effects; a checkpointer plus a `thread_id` saves the state after every step so a run resumes with `invoke(None, cfg)`.
- Resume is at-least-once: the step that was running reruns, so on paper a crash after an effect but before its checkpoint always repeats that effect.
- The parts are checkpointer, checkpoint, thread, `StateSnapshot` and history; `from_conn_string` is a context manager, a missing `thread_id` is a `ValueError`, and a shared `thread_id` leaks state between users.
- `run_once` with an idempotency key takes the crash demo from 2 comments to 1, but only a remote API that honours the key closes the effect-then-record window.
- Replay and fork re-execute nodes (cost, effects) and only ever add checkpoints; `update_state` returns a new config you must invoke. Use `InMemorySaver` for tests, SQLite on one box, and Postgres plus a shared ledger for many workers.

## Quick Reference

| API / pattern | What it does | When to use | Gotcha |
|---|---|---|---|
| `g.compile(checkpointer=saver)` | saves state after every step | any run that must resume, pause or be debugged | needs a `thread_id` in every config |
| `SqliteSaver(sqlite3.connect(p, check_same_thread=False))` | file-backed saver | one machine | `from_conn_string` needs `with` |
| `{"configurable": {"thread_id": t}, "recursion_limit": n}` | selects the save slot | every call | default limit 10007 |
| `app.invoke(None, cfg, durability="sync")` | resume from the last checkpoint | after a crash or interrupt | passing the input again adds it twice |
| `app.get_state(cfg)` / `get_state_history(cfg)` | latest snapshot / all snapshots, newest first | resume checks, debugging | snapshots are read-only |
| `cfg` + `checkpoint_id` → `invoke(None, ...)` | replay from an old step | reproduce a run | re-runs tools and the LLM |
| `app.update_state(snap.config, values, as_node=...)` | fork: writes a new checkpoint | fix a bad step and rerun | returns a new config; reducers apply |
| `run_once(key, fn)` + remote key | dedupes side effects | every `side_effect=True` tool | local ledger alone leaves a window |

## Exercises

1. **Warm-up: two save slots.** Run two `thread_id`s through the same graph and file, invoke one of them twice, and show with `get_state` that their states are isolated.

<details><summary>Solution</summary>

```python
# script_id: day_054_langgraph_durability/solution_ex1
# Two save slots on one graph and one file: each thread_id keeps its own state.
import operator, sqlite3
from pathlib import Path
from typing import Annotated, TypedDict
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

class State(TypedDict):
    steps: Annotated[list[str], operator.add]

Path("ex1.db").unlink(missing_ok=True)
g = StateGraph(State)
g.add_node("work", lambda s: {"steps": ["work"]})
g.add_edge(START, "work"); g.add_edge("work", END)
app = g.compile(checkpointer=SqliteSaver(sqlite3.connect("ex1.db", check_same_thread=False)))

alice = {"configurable": {"thread_id": "user-alice"}, "recursion_limit": 25}
bob = {"configurable": {"thread_id": "user-bob"}, "recursion_limit": 25}
app.invoke({"steps": ["alice-1"]}, alice)
app.invoke({"steps": ["alice-2"]}, alice)   # same slot: continues alice's state
app.invoke({"steps": ["bob-1"]}, bob)
print("alice:", app.get_state(alice).values["steps"])
print("bob:  ", app.get_state(bob).values["steps"])
```

```text
alice: ['alice-1', 'work', 'alice-2', 'work']
bob:   ['bob-1', 'work']
```

</details>

2. **Core: crash before the effect.** Use `ATLAS_CRASH_AT=before_effect` with the naive tools. Show that resuming is already safe here, and explain why in one sentence.

<details><summary>Solution</summary>

```python
# script_id: day_054_langgraph_durability/solution_ex2
# Crash BEFORE the effect: naive resume is already safe, because nothing happened yet.
# Needs crash_resume_demo.py and durable_graph.py from this lesson next to it.
from crash_resume_demo import main

main([
    ("naive, crash before effect", False, "before_effect", "MockTracker"),
    ("naive, crash after tool", False, "after_tool", "MockTracker"),
])
```

```text
   resuming at step 5, next=('run_tools',)
naive, crash before effect   crash at before_effect exit=1 · comments=1
   resuming at step 5, next=('run_tools',)
naive, crash after tool      crash at after_tool exit=1 · comments=2
```

Nothing happened in the world before the crash, so re-running the step performs the effect for the first time. Only effects that complete before the checkpoint can be duplicated.

</details>

3. **Core: key design.** A pure content hash dedupes two *legitimate* identical comments (issue #96 is reopened weeks later and Atlas greets it again). Show the problem, then choose a scope that keeps resume-safety but allows a new investigation to comment.

<details><summary>Solution</summary>

```python
# script_id: day_054_langgraph_durability/solution_ex3
# Key design: a pure content hash dedupes legitimate repeats; scoping it to a thread does not.
# Needs durable_graph.py from this lesson next to it.
from durable_graph import MockTracker, fresh_run_dir, make_tools

BODY = "Thanks, looking into it."
run_dir = fresh_run_dir("ex3")

# A) Content hash only: issue 96 is reopened two weeks later and Atlas greets it again.
tracker = MockTracker(run_dir / "a.jsonl")
for _investigation in range(2):
    make_tools(tracker, scope="")["post_comment"](96, BODY)
print("A content hash only: comments =", len(tracker.actions()))   # 1: a real comment was lost

# B) Scope = thread_id, one thread per investigation; a resume reuses the same thread.
tracker = MockTracker(run_dir / "b.jsonl")
for thread_id in ["issue-96-a1", "issue-96-a2", "issue-96-a2"]:   # last one = a resume
    make_tools(tracker, scope=thread_id)["post_comment"](96, BODY)
print("B scoped to thread:  comments =", len(tracker.actions()))   # 2: one per investigation
```

```text
A content hash only: comments = 1
B scoped to thread:  comments = 2
```

Scope the key to the `thread_id` and give each investigation its own thread (`issue-96-a1`, `issue-96-a2`). A resume or replay reuses the thread, so it is still deduplicated.

</details>

4. **Stretch (past the stop line): two workers on Postgres.** Swap in `PostgresSaver` on the Day 26 compose Postgres, move the effects ledger into Postgres too, crash worker A, and resume the thread from worker B (a different process). Confirm one comment.

<details><summary>Solution</summary>

```python
# script_id: day_054_langgraph_durability/solution_ex4
# fragment
# Needs Postgres (Day 26 compose.yaml), DATABASE_URL, durable_graph.py next to this file, and
# uv add langgraph-checkpoint-postgres "psycopg[binary]". Usage: python solution_ex4.py start|resume
import json, os, sys
import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
import durable_graph as dg

DB = os.environ["DATABASE_URL"]


def pg_run_once(key: str, fn):
    """Shared ledger: every worker sees every key. ON CONFLICT makes the record race-safe."""
    with psycopg.connect(DB, autocommit=True) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS effects (key TEXT PRIMARY KEY, result TEXT)")
        row = conn.execute("SELECT result FROM effects WHERE key = %s", (key,)).fetchone()
        if row:
            return json.loads(row[0])
        result = fn()
        conn.execute("INSERT INTO effects VALUES (%s, %s) ON CONFLICT (key) DO NOTHING",
                     (key, json.dumps(result)))
        return result


dg.run_once = pg_run_once   # make_tools looks run_once up at call time, so this swaps the ledger
with PostgresSaver.from_conn_string(DB) as saver:
    saver.setup()
    tools = dg.make_tools(dg.MockTracker(".atlas/pg/tracker.jsonl"), scope="issue-96")
    app = dg.build_agent_graph(tools, checkpointer=saver)
    cfg = dg.thread_config("issue-96")
    if sys.argv[1] == "start":
        app.invoke(dg.start_input(96), cfg, durability="sync")
    else:
        app.invoke(None, cfg, durability="sync")
    print("comments:", len(dg.MockTracker(".atlas/pg/tracker.jsonl").actions()))
```

Start worker A with `ATLAS_CRASH_AT=after_tool` and `start`, then run worker B with `resume`. B finds the checkpoint in Postgres and the key in the shared ledger, so the tracker shows one comment. With the SQLite ledger, B on another machine would not see A's record.

</details>

## References & Further Reading

- [LangGraph on GitHub](https://github.com/langchain-ai/langgraph): source and README for graphs, checkpointers and time travel; read `libs/langgraph/langgraph/types.py` for `Durability`.
- [langgraph-checkpoint-sqlite](https://github.com/langchain-ai/langgraph/tree/main/libs/checkpoint-sqlite): the `SqliteSaver` package used today, including the async saver.
- [langgraph-checkpoint-postgres](https://github.com/langchain-ai/langgraph/tree/main/libs/checkpoint-postgres): `PostgresSaver` and its `setup()` migration.
- [langgraph on PyPI](https://pypi.org/project/langgraph/): version pins (this lesson: `langgraph==1.2.20`).
- [langgraph-checkpoint-sqlite on PyPI](https://pypi.org/project/langgraph-checkpoint-sqlite/): the separate distribution you must install.
- [LangChain on GitHub](https://github.com/langchain-ai/langchain): `langchain_core.messages` and `add_messages`-compatible message types.

## What's Next

Your agent now survives crashes and its comments are safe to repeat, but it still posts without asking anyone. In [Day 55: Human-in-the-Loop: Approvals, Edits & Feedback](../Day_055_human_in_the_loop/human_in_the_loop.md) you pause the graph with `interrupt()` before risky tools, let a maintainer approve, edit or reject the call, and resume with `Command(resume=...)`. That pause is a checkpoint, and the interrupted node re-runs from its top, so `run_once` comes with you.
