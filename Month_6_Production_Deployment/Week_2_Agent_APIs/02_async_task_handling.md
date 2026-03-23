# Handling Long-Running Agent Tasks Asynchronously

Agent tasks can take minutes. Users can't wait that long! This guide shows you how to handle long-running tasks asynchronously in web servers.

---

## The Problem

```mermaid
flowchart LR
    subgraph "Synchronous (Bad)"
        A1["Request"] --> A2["Agent runs..."]
        A2 --> A3["30 seconds later"]
        A3 --> A4["Timeout! ❌"]
    end

    subgraph "Asynchronous (Good)"
        B1["Request"] --> B2["Start task"]
        B2 --> B3["Return task ID ✅"]
        B4["Poll status"] --> B5["Get result"]
    end
```

Issues with synchronous:
- HTTP timeouts (usually 30s)
- Blocked workers
- Poor user experience
- No progress updates

---

## Pattern 1: Background Tasks

FastAPI's built-in background tasks:

```python
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
import uuid
import asyncio

app = FastAPI()

# Store task results
task_results = {}

class TaskRequest(BaseModel):
    prompt: str

class TaskResponse(BaseModel):
    task_id: str
    status: str

def run_agent_task(task_id: str, prompt: str):
    """Run the agent task in background."""
    task_results[task_id] = {"status": "running", "result": None}

    # Simulate long-running agent
    import time
    time.sleep(10)  # Agent work

    # Store result
    task_results[task_id] = {
        "status": "completed",
        "result": f"Agent response to: {prompt}"
    }

@app.post("/agent/start", response_model=TaskResponse)
async def start_agent_task(request: TaskRequest, background_tasks: BackgroundTasks):
    """Start a long-running agent task."""

    task_id = str(uuid.uuid4())
    task_results[task_id] = {"status": "pending", "result": None}

    # Add to background tasks
    background_tasks.add_task(run_agent_task, task_id, request.prompt)

    return TaskResponse(task_id=task_id, status="pending")

@app.get("/agent/status/{task_id}")
async def get_task_status(task_id: str):
    """Get status of a task."""

    if task_id not in task_results:
        return {"error": "Task not found"}

    return task_results[task_id]
```

---

## Pattern 2: Task Queue with Redis

For production, use a proper task queue:

```python
from fastapi import FastAPI
from celery import Celery
from pydantic import BaseModel
import os

# Setup Celery
celery_app = Celery(
    "agent_tasks",
    broker=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("REDIS_URL", "redis://localhost:6379/0")
)

app = FastAPI()

@celery_app.task(bind=True)
def run_agent(self, prompt: str):
    """Celery task for running agent."""

    # Update progress
    self.update_state(state="RUNNING", meta={"progress": 0})

    # Simulate agent work
    import time
    for i in range(5):
        time.sleep(2)
        self.update_state(state="RUNNING", meta={"progress": (i+1) * 20})

    return {"result": f"Completed: {prompt}"}

class AgentRequest(BaseModel):
    prompt: str

@app.post("/agent/start")
async def start_task(request: AgentRequest):
    """Start agent task."""
    task = run_agent.delay(request.prompt)
    return {"task_id": task.id}

@app.get("/agent/status/{task_id}")
async def get_status(task_id: str):
    """Get task status."""
    task = run_agent.AsyncResult(task_id)

    if task.state == "PENDING":
        return {"status": "pending", "progress": 0}
    elif task.state == "RUNNING":
        return {"status": "running", "progress": task.info.get("progress", 0)}
    elif task.state == "SUCCESS":
        return {"status": "completed", "result": task.result}
    else:
        return {"status": "failed", "error": str(task.info)}
```

---

## Pattern 3: In-Memory Queue

Simple queue for single-server deployments:

```python
from fastapi import FastAPI
from pydantic import BaseModel
import asyncio
import uuid
from datetime import datetime
from typing import Dict
from enum import Enum

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class Task:
    def __init__(self, task_id: str, prompt: str):
        self.id = task_id
        self.prompt = prompt
        self.status = TaskStatus.PENDING
        self.result = None
        self.error = None
        self.created_at = datetime.now()
        self.completed_at = None
        self.progress = 0

class TaskQueue:
    def __init__(self, max_workers: int = 3):
        self.tasks: Dict[str, Task] = {}
        self.queue = asyncio.Queue()
        self.max_workers = max_workers
        self.workers_started = False

    async def start_workers(self):
        """Start background workers."""
        if self.workers_started:
            return

        for i in range(self.max_workers):
            asyncio.create_task(self._worker(i))

        self.workers_started = True

    async def _worker(self, worker_id: int):
        """Process tasks from queue."""
        while True:
            task_id = await self.queue.get()
            task = self.tasks.get(task_id)

            if not task:
                continue

            try:
                task.status = TaskStatus.RUNNING
                task.result = await self._run_agent(task)
                task.status = TaskStatus.COMPLETED
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error = str(e)
            finally:
                task.completed_at = datetime.now()
                self.queue.task_done()

    async def _run_agent(self, task: Task) -> str:
        """Run the actual agent (your implementation)."""
        # Simulate long-running work with progress
        for i in range(10):
            await asyncio.sleep(1)
            task.progress = (i + 1) * 10

        return f"Agent completed: {task.prompt}"

    async def submit(self, prompt: str) -> str:
        """Submit a new task."""
        task_id = str(uuid.uuid4())
        task = Task(task_id, prompt)
        self.tasks[task_id] = task

        await self.queue.put(task_id)
        return task_id

    def get_status(self, task_id: str) -> dict:
        """Get task status."""
        task = self.tasks.get(task_id)
        if not task:
            return {"error": "Task not found"}

        return {
            "id": task.id,
            "status": task.status.value,
            "progress": task.progress,
            "result": task.result,
            "error": task.error
        }

# FastAPI app
app = FastAPI()
task_queue = TaskQueue(max_workers=3)

@app.on_event("startup")
async def startup():
    await task_queue.start_workers()

class PromptRequest(BaseModel):
    prompt: str

@app.post("/agent/submit")
async def submit_task(request: PromptRequest):
    task_id = await task_queue.submit(request.prompt)
    return {"task_id": task_id}

@app.get("/agent/status/{task_id}")
async def get_status(task_id: str):
    return task_queue.get_status(task_id)
```

---

## Pattern 4: Polling Client

Client-side polling for results:

```python
import httpx
import asyncio

async def run_agent_with_polling(prompt: str, poll_interval: float = 1.0):
    """Submit task and poll until complete."""

    async with httpx.AsyncClient() as client:
        # Submit task
        response = await client.post(
            "http://localhost:8000/agent/submit",
            json={"prompt": prompt}
        )
        task_id = response.json()["task_id"]
        print(f"Task submitted: {task_id}")

        # Poll for completion
        while True:
            status_response = await client.get(
                f"http://localhost:8000/agent/status/{task_id}"
            )
            status = status_response.json()

            print(f"Status: {status['status']}, Progress: {status.get('progress', 0)}%")

            if status["status"] == "completed":
                return status["result"]
            elif status["status"] == "failed":
                raise Exception(status.get("error", "Unknown error"))

            await asyncio.sleep(poll_interval)

# Usage
result = asyncio.run(run_agent_with_polling("Analyze this document"))
print(f"Result: {result}")
```

---

## Pattern 5: Callback/Webhook

Notify when complete:

```python
from fastapi import FastAPI
from pydantic import BaseModel
import httpx
import asyncio

app = FastAPI()

class TaskWithCallback(BaseModel):
    prompt: str
    callback_url: str  # Where to POST result

async def run_agent_with_callback(task_id: str, prompt: str, callback_url: str):
    """Run agent and call webhook on completion."""

    try:
        # Simulate agent work
        await asyncio.sleep(10)
        result = f"Completed: {prompt}"

        # Send callback
        async with httpx.AsyncClient() as client:
            await client.post(callback_url, json={
                "task_id": task_id,
                "status": "completed",
                "result": result
            })
    except Exception as e:
        async with httpx.AsyncClient() as client:
            await client.post(callback_url, json={
                "task_id": task_id,
                "status": "failed",
                "error": str(e)
            })

@app.post("/agent/submit-with-callback")
async def submit_with_callback(request: TaskWithCallback):
    task_id = str(uuid.uuid4())

    # Start task in background
    asyncio.create_task(
        run_agent_with_callback(task_id, request.prompt, request.callback_url)
    )

    return {"task_id": task_id, "status": "submitted"}

# Client receives POST to callback_url when done
```

---

## Best Practices

### 1. Task Timeouts

```python
async def run_with_timeout(task: Task, timeout: int = 300):
    """Run task with timeout."""
    try:
        result = await asyncio.wait_for(
            run_agent(task),
            timeout=timeout
        )
        return result
    except asyncio.TimeoutError:
        task.status = TaskStatus.FAILED
        task.error = f"Task timed out after {timeout}s"
        raise
```

### 2. Progress Updates

```python
async def run_agent_with_progress(task: Task):
    """Run agent with progress updates."""

    task.progress = 10
    documents = await fetch_documents()

    task.progress = 30
    embeddings = await generate_embeddings(documents)

    task.progress = 60
    result = await query_llm(embeddings)

    task.progress = 100
    return result
```

### 3. Cleanup Old Tasks

```python
async def cleanup_old_tasks(task_queue: TaskQueue, max_age_hours: int = 24):
    """Remove old completed tasks."""
    cutoff = datetime.now() - timedelta(hours=max_age_hours)

    to_remove = [
        task_id for task_id, task in task_queue.tasks.items()
        if task.completed_at and task.completed_at < cutoff
    ]

    for task_id in to_remove:
        del task_queue.tasks[task_id]
```

---

## Summary

```mermaid
mindmap
  root((Async Tasks))
    Patterns
      Background tasks
      Task queues
      Polling
      Webhooks
    Components
      Submit endpoint
      Status endpoint
      Worker pool
    Best Practices
      Timeouts
      Progress tracking
      Cleanup
```

---

## Quick Reference

```python
# Submit task
POST /agent/submit
{"prompt": "..."}
-> {"task_id": "abc123"}

# Check status
GET /agent/status/abc123
-> {"status": "running", "progress": 50}
-> {"status": "completed", "result": "..."}

# With Celery
task = run_agent.delay(prompt)
task.id  # Get task ID
task.state  # Check status
task.result  # Get result
```

---

## What's Next?

Now let's implement **WebSockets for real-time streaming** of agent thoughts!
