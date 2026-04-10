# Wrapping Agents in APIs with FastAPI

Your AI agents work great locally. Now let's make them accessible to the world! In this guide, you'll learn to expose your agents as **REST APIs** using FastAPI.

> **Coming from Software Engineering?** This is 100% your wheelhouse. FastAPI is just a Python web framework — if you've used Flask, Express, Spring Boot, or any REST framework, you already know how to do this. The only AI-specific consideration is that LLM calls are slow (seconds, not milliseconds), so you need async handlers and streaming responses. Your API design, error handling, and middleware skills transfer completely.

---

## Why FastAPI?

```mermaid
flowchart LR
    A["Your Agent"] --> B["FastAPI"]
    B --> C["REST API"]
    C --> D["Web Apps"]
    C --> E["Mobile Apps"]
    C --> F["Other Services"]

    style B fill:#90EE90
```

FastAPI is perfect for AI applications:
- **Fast**: High performance with async support
- **Type hints**: Automatic validation
- **Docs**: Auto-generated API documentation
- **Async**: Handle concurrent requests

---

## Basic Setup

```bash
pip install fastapi uvicorn python-multipart
```

### Simple Agent API

```python
# script_id: day_083_fastapi_agents/simple_agent_api
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI

app = FastAPI(title="AI Agent API")
client = OpenAI()

class QueryRequest(BaseModel):
    message: str
    system_prompt: str = "You are a helpful assistant."

class QueryResponse(BaseModel):
    response: str
    tokens_used: int

@app.post("/chat", response_model=QueryResponse)
async def chat(request: QueryRequest):
    """Simple chat endpoint."""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.message}
            ]
        )

        return QueryResponse(
            response=response.choices[0].message.content,
            tokens_used=response.usage.total_tokens
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Run with: uvicorn main:app --reload
```

---

## Complete Agent API

```python
# script_id: day_083_fastapi_agents/complete_agent_api
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List
from openai import OpenAI
import uuid
from datetime import datetime

app = FastAPI(
    title="Agent API",
    description="REST API for AI agents",
    version="1.0.0"
)

client = OpenAI()

# In-memory storage (use Redis/DB in production)
conversations = {}
tasks = {}

# Models
class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    system_prompt: str = "You are a helpful AI assistant."
    temperature: float = Field(0.7, ge=0, le=2)
    max_tokens: int = Field(1000, ge=1, le=4000)

class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    tokens_used: int
    timestamp: str

class TaskStatus(BaseModel):
    task_id: str
    status: str  # pending, running, completed, failed
    result: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None

# Endpoints
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Synchronous chat endpoint."""
    # Get or create conversation
    conv_id = request.conversation_id or str(uuid.uuid4())

    if conv_id not in conversations:
        conversations[conv_id] = [
            {"role": "system", "content": request.system_prompt}
        ]

    # Add user message
    conversations[conv_id].append({
        "role": "user",
        "content": request.message
    })

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=conversations[conv_id],
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )

        assistant_message = response.choices[0].message.content

        # Store assistant response
        conversations[conv_id].append({
            "role": "assistant",
            "content": assistant_message
        })

        return ChatResponse(
            response=assistant_message,
            conversation_id=conv_id,
            tokens_used=response.usage.total_tokens,
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/conversation/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get conversation history."""
    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {
        "conversation_id": conversation_id,
        "messages": conversations[conversation_id],
        "message_count": len(conversations[conversation_id])
    }

@app.delete("/conversation/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation."""
    if conversation_id in conversations:
        del conversations[conversation_id]
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Conversation not found")

# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_conversations": len(conversations)
    }
```

---

## Handling Long-Running Tasks

AI tasks can take a while. Use background tasks:

```python
# script_id: day_083_fastapi_agents/complete_agent_api
from fastapi import BackgroundTasks
import asyncio

class LongTaskRequest(BaseModel):
    prompt: str
    task_type: str = "analysis"

@app.post("/task", response_model=TaskStatus)
async def create_task(request: LongTaskRequest, background_tasks: BackgroundTasks):
    """Create a long-running task."""
    task_id = str(uuid.uuid4())

    tasks[task_id] = {
        "status": "pending",
        "result": None,
        "created_at": datetime.now().isoformat(),
        "completed_at": None
    }

    # Run in background
    background_tasks.add_task(run_agent_task, task_id, request.prompt)

    return TaskStatus(
        task_id=task_id,
        status="pending",
        created_at=tasks[task_id]["created_at"]
    )

async def run_agent_task(task_id: str, prompt: str):
    """Execute the agent task in background."""
    tasks[task_id]["status"] = "running"

    try:
        # Simulate long-running task
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000
        )

        tasks[task_id]["status"] = "completed"
        tasks[task_id]["result"] = response.choices[0].message.content
        tasks[task_id]["completed_at"] = datetime.now().isoformat()

    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["result"] = str(e)
        tasks[task_id]["completed_at"] = datetime.now().isoformat()

@app.get("/task/{task_id}", response_model=TaskStatus)
async def get_task(task_id: str):
    """Get task status."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[task_id]
    return TaskStatus(
        task_id=task_id,
        status=task["status"],
        result=task["result"],
        created_at=task["created_at"],
        completed_at=task["completed_at"]
    )
```

---

## Streaming Responses

```python
# script_id: day_083_fastapi_agents/complete_agent_api
from fastapi.responses import StreamingResponse
import json

class StreamRequest(BaseModel):
    message: str
    system_prompt: str = "You are a helpful assistant."

@app.post("/chat/stream")
async def chat_stream(request: StreamRequest):
    """Streaming chat endpoint."""

    async def generate():
        stream = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.message}
            ],
            stream=True
        )

        for chunk in stream:
            if chunk.choices[0].delta.content:
                data = {"content": chunk.choices[0].delta.content}
                yield f"data: {json.dumps(data)}\n\n"

        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )
```

---

## WebSocket for Real-Time Chat

```python
# script_id: day_083_fastapi_agents/complete_agent_api
from fastapi import WebSocket, WebSocketDisconnect
import json

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]

    async def send_message(self, message: str, client_id: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_text(message)

manager = ConnectionManager()

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time chat."""
    await manager.connect(websocket, client_id)

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)

            # Stream response back
            stream = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": message_data["message"]}],
                stream=True
            )

            for chunk in stream:
                if chunk.choices[0].delta.content:
                    await manager.send_message(
                        json.dumps({"content": chunk.choices[0].delta.content}),
                        client_id
                    )

            await manager.send_message(
                json.dumps({"done": True}),
                client_id
            )

    except WebSocketDisconnect:
        manager.disconnect(client_id)
```

---

## Adding Authentication

```python
# script_id: day_083_fastapi_agents/complete_agent_api
from fastapi import Security, Depends
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key")
VALID_API_KEYS = {"key1": "user1", "key2": "user2"}  # Use database in production

async def verify_api_key(api_key: str = Security(API_KEY_HEADER)):
    """Verify API key."""
    if api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return VALID_API_KEYS[api_key]

@app.post("/secure/chat")
async def secure_chat(
    request: ChatRequest,
    user: str = Depends(verify_api_key)
):
    """Authenticated chat endpoint."""
    # User is verified, process request
    return {"user": user, "message": "Authenticated!"}
```

---

## Rate Limiting

```python
# script_id: day_083_fastapi_agents/complete_agent_api
from fastapi import Request
from collections import defaultdict
import time

# Simple in-memory rate limiter
request_counts = defaultdict(list)
RATE_LIMIT = 10  # requests per minute

async def rate_limit(request: Request):
    """Rate limiting middleware."""
    client_ip = request.client.host
    now = time.time()

    # Clean old requests
    request_counts[client_ip] = [
        t for t in request_counts[client_ip]
        if now - t < 60
    ]

    if len(request_counts[client_ip]) >= RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Try again later."
        )

    request_counts[client_ip].append(now)

@app.post("/chat/limited")
async def limited_chat(request: ChatRequest, _: None = Depends(rate_limit)):
    """Rate-limited chat endpoint."""
    # Process normally
    pass
```

---

## Streaming Responses with SSE

Server-Sent Events (SSE) is the standard pattern for streaming LLM output over HTTP. Unlike WebSockets, SSE is unidirectional (server to client), uses plain HTTP, and works through most proxies and CDNs without special configuration. This is how ChatGPT, Claude, and most LLM-powered UIs stream responses to the browser.

```python
# script_id: day_083_fastapi_agents/sse_streaming
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from openai import OpenAI

app = FastAPI()
client = OpenAI()

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Stream LLM responses using Server-Sent Events."""
    async def generate():
        stream = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": request.message}],
            stream=True,
        )
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield f"data: {chunk.choices[0].delta.content}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

On the client side, you consume SSE with the `EventSource` API in JavaScript or any HTTP client that supports streaming. The `data:` prefix and double newline are part of the SSE protocol -- each `data:` line is one event delivered to the client in real time.

---

## Streaming Responses with SSE

Server-Sent Events (SSE) is the standard pattern for streaming LLM output over HTTP. Unlike WebSockets, SSE is unidirectional (server to client), which is a natural fit for LLM generation where the client sends a prompt and the server streams back tokens. Most LLM frontend libraries (including the OpenAI JS SDK) expect SSE format.

```python
# script_id: day_083_fastapi_agents/sse_streaming_detailed
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from openai import OpenAI

app = FastAPI()
client = OpenAI()

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Stream LLM responses using Server-Sent Events."""
    async def generate():
        stream = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": request.message}],
            stream=True,
        )
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield f"data: {chunk.choices[0].delta.content}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

The `text/event-stream` media type tells the client to expect an SSE stream. Each chunk is prefixed with `data: ` and terminated with a double newline, following the SSE specification. The `[DONE]` sentinel signals the end of the stream -- this convention is also used by the OpenAI API itself.

---

## Summary

```mermaid
mindmap
  root((FastAPI Agent))
    Endpoints
      Sync chat
      Async tasks
      Streaming
      WebSockets
    Features
      Authentication
      Rate limiting
      Error handling
    Patterns
      Background tasks
      Connection manager
      Health checks
```

---

## Quick Reference

```python
# script_id: day_083_fastapi_agents/quick_reference
# Basic endpoint
@app.post("/chat")
async def chat(request: ChatRequest):
    return {"response": "..."}

# Streaming
@app.post("/stream")
async def stream():
    return StreamingResponse(generate(), media_type="text/event-stream")

# Background task
@app.post("/task")
async def task(background_tasks: BackgroundTasks):
    background_tasks.add_task(long_running_func)
    return {"task_id": "..."}

# Run server
# uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

## What's Next?

Now let's build beautiful **Agent UIs** with Streamlit and Gradio!
