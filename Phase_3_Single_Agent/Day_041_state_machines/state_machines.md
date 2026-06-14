# State Machines with LangGraph

You've built agents with simple loops. Now let's level up with **LangGraph** - a framework for building agents as **state machines** with explicit control flow.

> **Coming from Software Engineering?** LangGraph state machines are like Redux reducers or finite state machines in embedded systems. If you've modeled workflows as state machines (order status: pending → paid → shipped) or used XState/Redux, you already think in states and transitions — LangGraph just applies this to AI agents.

---

## Why State Machines?

```mermaid
flowchart TB
    subgraph "Simple Loop Agent"
        A["Start"] --> B["Think"]
        B --> C["Act"]
        C --> D{"Done?"}
        D -->|No| B
        D -->|Yes| E["End"]
    end

    subgraph "State Machine Agent"
        F["Start"] --> G["Research"]
        G --> H{"Enough\ninfo?"}
        H -->|No| G
        H -->|Yes| I["Plan"]
        I --> J["Execute"]
        J --> K{"Success?"}
        K -->|No| L["Debug"]
        L --> J
        K -->|Yes| M["End"]
    end

    style M fill:#90EE90
```

State machines give you **explicit control** over agent behavior!

---

## Installing LangGraph

```bash
pip install langgraph langchain langchain-openai
```

---

## Core Concepts

### 1. State

A TypedDict that holds all information the agent needs:

```python
# script_id: day_041_state_machines/state_definition
from typing import TypedDict, Annotated
from operator import add

class AgentState(TypedDict):
    messages: list              # Conversation history
    current_step: str           # Which step we're on
    results: Annotated[list, add]  # Accumulated results
    iteration: int              # Loop counter
```

A normal field gets **overwritten** when a node returns it — like assigning a variable (`results = new`). Wrapping a field in `Annotated[list, add]` tells LangGraph to **merge** updates instead: it appends the node's returned list to the existing one (`results += new`, not `results = new`). `add` here is just `operator.add`. This is how history/results accumulate across steps instead of being replaced. (Unlike a Redux reducer that returns the full next state, a LangGraph node returns only the keys it changes and LangGraph merges them in.)

### 2. Nodes

Functions that process the state:

```python
# script_id: day_041_state_machines/node_example
# fragment
# Illustrates the SHAPE of a node function — do_research is a placeholder
# you'd implement; the first complete runnable graph is below.
def research_node(state: AgentState) -> dict:
    """Do research and update state."""
    # Process state
    result = do_research(state["messages"])
    return {"results": [result], "iteration": state["iteration"] + 1}
```

### 3. Edges

Connections between nodes (can be conditional):

```python
# script_id: day_041_state_machines/edge_example
# fragment
# Illustrates the SHAPE of an edge function — needs_more_research is a placeholder;
# the first complete runnable graph is below.
def should_continue(state: AgentState) -> str:
    """Decide which node to go to next."""
    if state["iteration"] >= 5:
        return "end"
    elif needs_more_research(state):
        return "research"
    else:
        return "summarize"
```

---

## Building Your First Graph

```python
# script_id: day_041_state_machines/first_graph
from typing import TypedDict, Annotated
from operator import add
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage

# Define state — reducers (Annotated[list, add]) make these fields ACCUMULATE,
# so each node returns only the NEW items and LangGraph appends them.
class ResearchState(TypedDict):
    messages: Annotated[list, add]
    research_results: Annotated[list, add]
    final_answer: str

# Initialize LLM
llm = ChatOpenAI(model="gpt-4o", temperature=0)  # deterministic / most predictable output (covered earlier)

# Define nodes
def researcher(state: ResearchState) -> dict:
    """Research node - gathers information."""
    messages = state["messages"]

    response = llm.invoke([
        HumanMessage(content="Based on the question, what key facts should we research?"),
        *messages
    ])

    # Return only the NEW items — the reducers append them to existing state.
    return {
        "research_results": [response.content],
        "messages": [response]
    }

def synthesizer(state: ResearchState) -> dict:
    """Synthesize research into final answer."""
    research = "\n".join(state["research_results"])

    response = llm.invoke([
        HumanMessage(content=f"Based on this research:\n{research}\n\nProvide a comprehensive answer.")
    ])

    return {"final_answer": response.content}

# Define routing logic
def should_continue(state: ResearchState) -> str:
    """Decide if we need more research."""
    if len(state["research_results"]) >= 2:
        return "synthesize"
    return "research"

# Build the graph
workflow = StateGraph(ResearchState)

# Add nodes
workflow.add_node("research", researcher)
workflow.add_node("synthesize", synthesizer)

# Add edges
workflow.set_entry_point("research")
workflow.add_conditional_edges(
    "research",
    should_continue,
    {
        "research": "research",
        "synthesize": "synthesize"
    }
)
workflow.add_edge("synthesize", END)

# Compile
app = workflow.compile()

# Run it!
result = app.invoke({
    "messages": [HumanMessage(content="What is quantum computing?")],
    "research_results": [],
    "final_answer": ""
})

print(result["final_answer"])
```

---

## Visualizing Your Graph

```python
# script_id: day_041_state_machines/first_graph
# Print the graph structure
print(app.get_graph().draw_mermaid())
```

Roughly renders as (conceptual view — the router function isn't drawn as its own node; LangGraph draws conditional edges as dashed, labeled edges straight from the source node to each possible target):
```mermaid
flowchart TD
    __start__ --> research
    research -.->|research| research
    research -.->|synthesize| synthesize
    synthesize --> __end__
```

---

## Agent with Tools

```python
# script_id: day_041_state_machines/agent_with_tools
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END, add_messages
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

# Define tools
@tool
def search(query: str) -> str:
    """Search for information."""
    return f"Search results for: {query}"

@tool
def calculate(expression: str) -> str:
    """Evaluate a simple math expression."""
    # Tool internals aren't the point — the point is how the agent loops
    # tools -> agent. Simplified; use a real expression parser in production.
    import ast
    return str(ast.literal_eval(expression))

tools = [search, calculate]

# State — add_messages is LangGraph's built-in reducer for chat history; it
# appends each node's returned messages so the full HumanMessage + AIMessage
# (tool_calls) + ToolMessage ordering is preserved (the API requires it).
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

# LLM with tools
llm = ChatOpenAI(model="gpt-4o").bind_tools(tools)

# Nodes
def agent(state: AgentState) -> dict:
    """The main agent node."""
    response = llm.invoke(state["messages"])
    return {"messages": [response]}

def should_continue(state: AgentState) -> str:
    """Check if we should use tools or end."""
    last_message = state["messages"][-1]
    # When the model decides to use a tool, its response carries a populated
    # tool_calls list; if it's empty/absent the model answered directly, so we stop.
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "end"

# Build graph
workflow = StateGraph(AgentState)

workflow.add_node("agent", agent)
workflow.add_node("tools", ToolNode(tools))

workflow.set_entry_point("agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {"tools": "tools", "end": END}
)
workflow.add_edge("tools", "agent")  # Go back to agent after tools

app = workflow.compile()

# Run
from langchain_core.messages import HumanMessage

result = app.invoke({
    "messages": [HumanMessage(content="What is 25 * 17? Also search for Python.")]
})

for msg in result["messages"]:
    print(f"{msg.type}: {msg.content[:100]}...")
```

---

## Branching Workflows

```python
# script_id: day_041_state_machines/branching_workflows
from langgraph.graph import StateGraph, END

class TaskState(TypedDict):
    task: str
    task_type: str
    result: str

def classifier(state: TaskState) -> dict:
    """Classify the task type."""
    task = state["task"].lower()
    if "calculate" in task or "math" in task:
        return {"task_type": "math"}
    elif "search" in task or "find" in task:
        return {"task_type": "search"}
    else:
        return {"task_type": "general"}

def math_handler(state: TaskState) -> dict:
    """Handle math tasks."""
    return {"result": f"Math result for: {state['task']}"}

def search_handler(state: TaskState) -> dict:
    """Handle search tasks."""
    return {"result": f"Search result for: {state['task']}"}

def general_handler(state: TaskState) -> dict:
    """Handle general tasks."""
    return {"result": f"General result for: {state['task']}"}

def route_task(state: TaskState) -> str:
    """Route based on task type."""
    return state["task_type"]

# Build branching graph
workflow = StateGraph(TaskState)

workflow.add_node("classify", classifier)
workflow.add_node("math", math_handler)
workflow.add_node("search", search_handler)
workflow.add_node("general", general_handler)

workflow.set_entry_point("classify")
workflow.add_conditional_edges(
    "classify",
    route_task,
    {
        "math": "math",
        "search": "search",
        "general": "general"
    }
)

# All handlers go to END
workflow.add_edge("math", END)
workflow.add_edge("search", END)
workflow.add_edge("general", END)

app = workflow.compile()
```

```mermaid
flowchart TD
    Start["classify"] --> Route{"task_type?"}
    Route -->|math| Math["math_handler"]
    Route -->|search| Search["search_handler"]
    Route -->|general| General["general_handler"]
    Math --> End["END"]
    Search --> End
    General --> End
```

---

## Cycles and Iteration

```python
# script_id: day_041_state_machines/cycles_and_iteration
class IterativeState(TypedDict):
    content: str
    quality_score: float
    iterations: int
    max_iterations: int

def improve_content(state: IterativeState) -> dict:
    """Improve content quality."""
    # Simulate improvement
    new_score = state["quality_score"] + 0.15
    improved = f"{state['content']} [improved v{state['iterations'] + 1}]"

    return {
        "content": improved,
        "quality_score": min(new_score, 1.0),
        "iterations": state["iterations"] + 1
    }

def should_improve_more(state: IterativeState) -> str:
    """Check if we should continue improving."""
    if state["iterations"] >= state["max_iterations"]:
        return "done"
    if state["quality_score"] >= 0.9:
        return "done"
    return "improve"

workflow = StateGraph(IterativeState)

workflow.add_node("improve", improve_content)

workflow.set_entry_point("improve")
workflow.add_conditional_edges(
    "improve",
    should_improve_more,
    {
        "improve": "improve",  # Loop back
        "done": END
    }
)

app = workflow.compile()

result = app.invoke({
    "content": "Initial draft",
    "quality_score": 0.3,
    "iterations": 0,
    "max_iterations": 5
})

print(f"Final: {result['content']}")
print(f"Quality: {result['quality_score']:.2f}")
print(f"Iterations: {result['iterations']}")
```

---

## Checkpoint

Run the Cycles and Iteration example with an initial `quality_score` of `0.3` and `max_iterations` of `5`. The `improve` node should loop back into itself, bumping the score by `0.15` each pass, and exit once it crosses `0.9` (or hits the iteration cap) — printing a final score around `0.9` after roughly four iterations. If it exits immediately after one pass, check your `should_improve_more` router: it has to return `"improve"` (mapped back to the same node) until a stop condition is met.

---

## Summary

```mermaid
mindmap
  root((LangGraph))
    Core
      State (TypedDict)
      Nodes (functions)
      Edges (connections)
    Patterns
      Sequential
      Branching
      Cycles
    Features
      Tool integration
      Checkpoints
      Visualization
```

---

## Quick Reference

```python
# script_id: day_041_state_machines/quick_reference
from langgraph.graph import StateGraph, END

# 1. Define state
class MyState(TypedDict):
    data: str

# 2. Define nodes
def my_node(state: MyState) -> dict:
    return {"data": "processed"}

# 3. Build graph
graph = StateGraph(MyState)
graph.add_node("node1", my_node)
graph.set_entry_point("node1")
graph.add_edge("node1", END)

# 4. Compile and run
app = graph.compile()
result = app.invoke({"data": "input"})
```

---

## Exercises

1. Define a `TypedDict` state with `count: int` and `messages: list`, then build a two-node graph that increments `count` and appends a string — run it and inspect the final state.
2. Add a conditional edge: after node A, route to `node_b` if `count < 3` else to `END`, creating a controlled loop.
3. Make one node deliberately raise, then wrap `app.invoke` in try/except and confirm the state up to the failure is what you expected.
4. Draw the graph: call `app.get_graph().draw_mermaid()` (or `.print_ascii()`) and check the diagram matches your mental model.

<details><summary>Solutions (approaches)</summary>

1. Each node returns a partial dict (`return {"count": state["count"] + 1}`); LangGraph merges it into state. Print `app.invoke({"count": 0, "messages": []})`.
2. Use `graph.add_conditional_edges("A", lambda s: "loop" if s["count"] < 3 else "stop", {"loop": "node_b", "stop": END})`.
3. The exception propagates out of `invoke`; without a checkpointer the in-memory state is lost, which motivates Day 44's persistence.
4. `print(app.get_graph().draw_mermaid())` returns Mermaid text you can paste into the rendered page or any Mermaid viewer.
</details>

---

## What's Next?

Now let's go deeper on LangGraph's building blocks: **Nodes and Edges** — how to structure node functions and route between them with simple and conditional edges.
