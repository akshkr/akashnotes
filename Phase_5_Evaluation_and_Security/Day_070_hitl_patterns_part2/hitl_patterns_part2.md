# Human-in-the-Loop (HITL) Patterns Part 2

> **Coming from Software Engineering?** Multi-stage approval pipelines are exactly like promotion gates in deployment pipelines: dev -> staging -> prod, each requiring sign-off. If you've configured GitHub Actions environments with required reviewers, or set up Spinnaker deployment stages with manual judgments, this is the same pattern applied to agent workflows.

## Multi-Stage Approval Pipeline

For critical workflows, require approval at multiple stages:

```python
# script_id: day_070_hitl_patterns_part2/multi_stage_approval_pipeline
from typing import Callable, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"

@dataclass
class Stage:
    name: str
    action: Callable
    requires_approval: bool = True
    approvers: List[str] = None

class ApprovalPipeline:
    """Multi-stage pipeline with human approvals."""

    def __init__(self, stages: List[Stage]):
        self.stages = stages
        self.results = {}
        self.current_stage = 0

    def run(self, initial_input: Any) -> Dict:
        """Run the pipeline with approval gates."""
        current_input = initial_input

        for i, stage in enumerate(self.stages):
            self.current_stage = i
            print(f"\n{'='*50}")
            print(f"Stage {i+1}: {stage.name}")
            print('='*50)

            # Execute stage action
            result = stage.action(current_input)
            print(f"\nOutput: {result}")

            # Check if approval needed
            if stage.requires_approval:
                status = self._get_approval(stage, result)

                if status == ApprovalStatus.REJECTED:
                    print(f"Stage '{stage.name}' rejected. Pipeline stopped.")
                    return {"status": "rejected", "stage": stage.name, "results": self.results}

                elif status == ApprovalStatus.NEEDS_REVISION:
                    revision = input("Enter revision instructions: ")
                    result = stage.action(f"{current_input}\nRevision: {revision}")
                    print(f"Revised output: {result}")

            self.results[stage.name] = result
            current_input = result

        print(f"\nPipeline completed successfully!")
        return {"status": "completed", "results": self.results}

    def _get_approval(self, stage: Stage, result: Any) -> ApprovalStatus:
        """Get human approval for a stage."""
        print(f"\nReview required for: {stage.name}")
        if stage.approvers:
            print(f"   Approvers: {', '.join(stage.approvers)}")

        print("\nOptions:")
        print("  [a] Approve")
        print("  [r] Reject")
        print("  [v] Request revision")

        while True:
            choice = input("\nYour choice: ").strip().lower()
            if choice == 'a':
                return ApprovalStatus.APPROVED
            elif choice == 'r':
                return ApprovalStatus.REJECTED
            elif choice == 'v':
                return ApprovalStatus.NEEDS_REVISION
            print("Invalid choice. Enter 'a', 'r', or 'v'")

# Example: Email drafting pipeline
def draft_email(task):
    return f"Draft email about: {task}"

def review_tone(draft):
    return f"Reviewed: {draft} [Tone: Professional]"

def add_signature(content):
    return f"{content}\n\nBest regards,\nThe Team"

pipeline = ApprovalPipeline([
    Stage("Draft", draft_email, requires_approval=True),
    Stage("Tone Review", review_tone, requires_approval=True, approvers=["manager"]),
    Stage("Finalize", add_signature, requires_approval=False)
])

# Run pipeline
result = pipeline.run("Project update for stakeholders")
```

---

## LangGraph Human-in-the-Loop

LangGraph provides built-in HITL support through **interrupt** nodes and **breakpoints** that pause graph execution for human review:

```python
# script_id: day_070_hitl_patterns_part2/langgraph_hitl_interrupt
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, Literal

class AgentState(TypedDict):
    task: str
    plan: str
    human_feedback: str
    result: str

def plan_step(state: AgentState) -> AgentState:
    """Agent creates a plan for human review."""
    # In practice, call an LLM here
    return {"plan": f"Proposed plan for: {state['task']}"}

def human_review(state: AgentState) -> AgentState:
    """This node is interrupted — human provides feedback."""
    # The graph pauses here; human input is injected via update_state()
    return state

def execute_step(state: AgentState) -> AgentState:
    """Execute after human approval."""
    return {"result": f"Executed: {state['plan']} with feedback: {state['human_feedback']}"}

def should_continue(state: AgentState) -> Literal["execute", "replan"]:
    """Route based on human feedback."""
    if state.get("human_feedback", "").lower().startswith("approved"):
        return "execute"
    return "replan"

# Build graph with interrupt
graph = StateGraph(AgentState)
graph.add_node("plan", plan_step)
graph.add_node("human_review", human_review)
graph.add_node("execute", execute_step)

graph.set_entry_point("plan")
graph.add_edge("plan", "human_review")
graph.add_conditional_edges("human_review", should_continue, {
    "execute": "execute",
    "replan": "plan"
})
graph.add_edge("execute", END)

# Compile with checkpointer and interrupt
memory = MemorySaver()
app = graph.compile(
    checkpointer=memory,
    interrupt_before=["human_review"]  # Pause before human review
)

# Run until interrupt
config = {"configurable": {"thread_id": "hitl-1"}}
result = app.invoke({"task": "Deploy to production"}, config)
# Graph pauses here — waiting for human input

# Human provides feedback
app.update_state(config, {"human_feedback": "Approved - proceed"})

# Resume execution
final = app.invoke(None, config)
```

### Multi-Stage Approval Pipeline

```python
# script_id: day_070_hitl_patterns_part2/risk_based_escalation
# Define escalation levels based on risk
def classify_risk(state: AgentState) -> Literal["low", "medium", "high"]:
    """Route to appropriate approval level."""
    # In practice, use an LLM or rule engine
    if "production" in state.get("task", "").lower():
        return "high"
    elif "staging" in state.get("task", "").lower():
        return "medium"
    return "low"

# Low risk: auto-approve
# Medium risk: single reviewer
# High risk: interrupt for senior approval
```

```mermaid
flowchart LR
    subgraph "Interrupt-based HITL"
        A1["Agent plans"] --> A2["Graph pauses"]
        A2 --> A3["Human reviews"]
        A3 --> A4["Resume or replan"]
    end

    subgraph "Risk-based Routing"
        R1["Low risk"] --> R2["Auto-approve"]
        R3["Medium risk"] --> R4["Single review"]
        R5["High risk"] --> R6["Senior approval"]
    end

    subgraph "Multi-stage Pipeline"
        M1["Plan"] --> M2["Review 1"]
        M2 --> M3["Review 2"]
        M3 --> M4["Execute"]
    end
```

---

## Best Practices

### 1. Clear Action Descriptions

```python
# script_id: day_070_hitl_patterns_part2/clear_action_descriptions
# Bad - vague
action = "do the thing"

# Good - specific and clear
action = {
    "type": "send_email",
    "recipient": "john@example.com",
    "subject": "Meeting Confirmation",
    "body": "Your meeting is confirmed for tomorrow at 2pm.",
    "impact": "Email will be sent immediately and cannot be unsent"
}
```

### 2. Provide Context

```python
# script_id: day_070_hitl_patterns_part2/provide_context
def format_approval_request(action: dict, context: dict) -> str:
    """Format a clear approval request."""
    return f"""
    ACTION APPROVAL REQUEST
    ========================

    What: {action['type']}
    Details: {action['details']}

    Context:
    - Task: {context['task']}
    - Step: {context['step']} of {context['total_steps']}
    - Previous actions: {context['history']}

    Impact: {action['impact']}
    Reversible: {action['reversible']}

    ========================
    """
```

### 3. Timeout Handling

```python
# script_id: day_070_hitl_patterns_part2/timeout_handling
import threading

def get_approval_with_timeout(action: str, timeout: int = 300) -> bool:
    """Get approval with timeout."""
    result = {"approved": None}

    def ask_human():
        response = input(f"Approve '{action}'? (yes/no): ")
        result["approved"] = response.lower() in ["yes", "y"]

    thread = threading.Thread(target=ask_human)
    thread.start()
    thread.join(timeout=timeout)

    if thread.is_alive():
        print(f"\nTimeout! No response in {timeout}s. Defaulting to reject.")
        return False

    return result["approved"]
```

---

## Summary

```mermaid
mindmap
  root((HITL))
    Patterns
      Basic approval
      Breakpoints
      Feedback injection
      Confidence-based
    Tools
      LangGraph interrupts
      LangGraph interrupt_before
      LangGraph update_state
      Custom pipelines
    Best Practices
      Clear descriptions
      Provide context
      Handle timeouts
      Log decisions
```

---

## Quick Reference

```python
# script_id: day_070_hitl_patterns_part2/quick_reference
# LangGraph Breakpoint
app = workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=["critical_node"]
)

# LangGraph HITL with interrupt + update_state
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()
app = graph.compile(checkpointer=memory, interrupt_before=["review"])

# Run until interrupt
config = {"configurable": {"thread_id": "1"}}
result = app.invoke({"task": "Deploy"}, config)

# Inject human feedback and resume
app.update_state(config, {"feedback": "Approved"})
final = app.invoke(None, config)

# Confidence-based HITL
if agent_confidence < threshold:
    human_feedback = get_human_input()
```

---

## What's Next?

You've mastered multi-agent systems! Next month, we'll explore **Evaluation & Observability** - measuring how well your agents perform!
