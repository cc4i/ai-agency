# A2A Implementation Plan

Based on the A2A Design Document review and codebase analysis, this document outlines the implementation steps for integrating A2A (Agent-to-Agent) protocol support.

## Implementation Decisions

Based on user preferences:
- **Streaming**: SSE streaming (preferred) with polling fallback
- **API Key Storage**: Direct to Redis (frontend sends key, stored in Redis with config)
- **Scope**: Full A2A spec
- **First Target**: Standalone A2A Video Agent Server (deployable independently)

---

## Project Structure

The A2A server will be a **standalone project** in a separate folder, designed to be deployed independently and later converted to a real implementation.

```
ai-agency/
├── backend/                          # Existing AI Agency backend
│   ├── app/
│   │   ├── agents/
│   │   │   └── remote_a2a_adapter.py # A2A client adapter
│   │   ├── models/
│   │   │   └── a2a.py                # Shared A2A models
│   │   └── services/
│   │       └── a2a_client.py         # A2A HTTP/SSE client
│   └── ...
│
├── a2a-servers/                      # NEW: Standalone A2A servers
│   └── video-agent/                  # Video Producer A2A Server
│       ├── README.md
│       ├── pyproject.toml            # Independent Python project
│       ├── Dockerfile
│       ├── docker-compose.yml
│       ├── .env.example
│       ├── app/
│       │   ├── __init__.py
│       │   ├── main.py               # FastAPI app
│       │   ├── config.py             # Settings
│       │   ├── models/
│       │   │   ├── __init__.py
│       │   │   ├── a2a.py            # A2A protocol models
│       │   │   └── video.py          # Video-specific models
│       │   ├── routers/
│       │   │   ├── __init__.py
│       │   │   ├── agent_card.py     # /.well-known/agent.json
│       │   │   ├── a2a.py            # /a2a JSON-RPC endpoint
│       │   │   └── a2a_stream.py     # /a2a/stream SSE endpoint
│       │   ├── services/
│       │   │   ├── __init__.py
│       │   │   ├── task_manager.py   # Task lifecycle management
│       │   │   ├── video_generator.py # Mock/real video generation
│       │   │   └── storage.py        # Artifact storage
│       │   └── core/
│       │       ├── __init__.py
│       │       ├── sse.py            # SSE event streaming utilities
│       │       └── auth.py           # Bearer token auth
│       └── tests/
│           ├── __init__.py
│           ├── test_agent_card.py
│           ├── test_a2a_endpoint.py
│           └── test_sse_stream.py
│
└── frontend/                         # Existing frontend
```

---

## Phase 1: Standalone A2A Video Agent Server

### 1.1 Project Setup

Create `a2a-servers/video-agent/`:

**pyproject.toml:**
```toml
[project]
name = "a2a-video-agent"
version = "0.1.0"
description = "A2A-compliant Video Producer Agent Server"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "httpx>=0.26.0",
    "python-multipart>=0.0.6",
    "sse-starlette>=1.8.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.26.0",
]
```

### 1.2 A2A Protocol Models

Create `a2a-servers/video-agent/app/models/a2a.py`:

```python
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field


# ============ Enums ============

class TaskState(str, Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PartType(str, Enum):
    TEXT = "text"
    FILE = "file"
    DATA = "data"


# ============ Message Parts ============

class TextPart(BaseModel):
    type: Literal["text"] = "text"
    text: str


class FilePart(BaseModel):
    type: Literal["file"] = "file"
    uri: str
    mimeType: str
    name: Optional[str] = None


class DataPart(BaseModel):
    type: Literal["data"] = "data"
    mimeType: str = "application/json"
    data: Dict[str, Any]


Part = Union[TextPart, FilePart, DataPart]


# ============ Messages ============

class Message(BaseModel):
    messageId: str
    role: Literal["user", "agent"]
    parts: List[Part]
    timestamp: Optional[datetime] = None


# ============ Artifacts ============

class Artifact(BaseModel):
    id: str
    name: str
    mimeType: str
    parts: List[Part]
    metadata: Optional[Dict[str, Any]] = None


# ============ Task Status ============

class TaskStatus(BaseModel):
    state: TaskState
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    progress: Optional[int] = None  # 0-100
    message: Optional[Union[str, Message]] = None


class Task(BaseModel):
    id: str
    contextId: Optional[str] = None
    status: TaskStatus
    artifacts: List[Artifact] = []
    history: List[Message] = []


# ============ Agent Card ============

class AgentSkill(BaseModel):
    id: str
    name: str
    description: str
    inputModes: List[str] = ["text/plain"]
    outputModes: List[str] = ["application/json"]
    examples: Optional[List[Dict[str, str]]] = None


class AgentProvider(BaseModel):
    name: str
    url: Optional[str] = None


class AgentCapabilities(BaseModel):
    streaming: bool = False
    pushNotifications: bool = False


class SecurityScheme(BaseModel):
    type: str
    scheme: Optional[str] = None
    description: Optional[str] = None


class AgentCard(BaseModel):
    id: str
    name: str
    description: str
    protocolVersion: str = "1.0"
    url: str
    provider: Optional[AgentProvider] = None
    capabilities: AgentCapabilities = AgentCapabilities()
    skills: List[AgentSkill] = []
    securitySchemes: Optional[Dict[str, SecurityScheme]] = None
    security: Optional[List[str]] = None
    defaultInputModes: List[str] = ["text/plain"]
    defaultOutputModes: List[str] = ["application/json"]


# ============ JSON-RPC ============

class JSONRPCRequest(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str
    method: str
    params: Dict[str, Any] = {}


class JSONRPCError(BaseModel):
    code: int
    message: str
    data: Optional[Any] = None


class JSONRPCResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str
    result: Optional[Any] = None
    error: Optional[JSONRPCError] = None


# ============ SSE Events ============

class SSEEvent(BaseModel):
    """Server-Sent Event wrapper."""
    event: str  # task_created, task_status, task_artifact, task_completed, etc.
    data: Dict[str, Any]
```

### 1.3 Agent Card Endpoint

Create `a2a-servers/video-agent/app/routers/agent_card.py`:

```python
from fastapi import APIRouter
from app.config import settings
from app.models.a2a import AgentCard, AgentSkill, AgentCapabilities, AgentProvider

router = APIRouter()


@router.get("/.well-known/agent.json", response_model=AgentCard)
async def get_agent_card():
    """Return the Agent Card for this A2A server."""
    return AgentCard(
        id="video_producer_a2a",
        name="Video Producer Agent",
        description="A2A-compliant video generation agent. Creates 15-second social media videos from text prompts and brand guidelines.",
        protocolVersion="1.0",
        url=f"{settings.base_url}/a2a",
        provider=AgentProvider(
            name="AI Agency",
            url="https://ai-agency.example.com"
        ),
        capabilities=AgentCapabilities(
            streaming=True,
            pushNotifications=False
        ),
        skills=[
            AgentSkill(
                id="video_generation",
                name="Video Generation",
                description="Creates 15-second social media videos from text prompts and brand guidelines",
                inputModes=["text/plain", "application/json"],
                outputModes=["video/mp4", "video/webm"],
                examples=[
                    {
                        "input": "Create a 15s video showcasing sneakers with Tokyo neon aesthetic",
                        "output": "video/mp4 artifact with neon-lit urban footage"
                    }
                ]
            )
        ],
        securitySchemes={
            "bearer": {
                "type": "http",
                "scheme": "bearer",
                "description": "API key authentication"
            }
        },
        security=["bearer"],
        defaultInputModes=["text/plain", "application/json"],
        defaultOutputModes=["video/mp4"]
    )
```

### 1.4 A2A JSON-RPC Endpoint

Create `a2a-servers/video-agent/app/routers/a2a.py`:

```python
from fastapi import APIRouter, HTTPException, Depends
from app.models.a2a import JSONRPCRequest, JSONRPCResponse, JSONRPCError, Task
from app.services.task_manager import TaskManager
from app.core.auth import verify_bearer_token

router = APIRouter()
task_manager = TaskManager()


@router.post("/a2a", response_model=JSONRPCResponse)
async def handle_jsonrpc(
    request: JSONRPCRequest,
    _: str = Depends(verify_bearer_token)
):
    """Handle A2A JSON-RPC 2.0 requests."""
    try:
        if request.method == "message/send":
            result = await task_manager.handle_message_send(request.params)
            return JSONRPCResponse(id=request.id, result=result)

        elif request.method == "tasks/get":
            task_id = request.params.get("taskId")
            if not task_id:
                raise ValueError("taskId is required")
            result = await task_manager.get_task(task_id)
            return JSONRPCResponse(id=request.id, result=result)

        elif request.method == "tasks/cancel":
            task_id = request.params.get("taskId")
            if not task_id:
                raise ValueError("taskId is required")
            result = await task_manager.cancel_task(task_id)
            return JSONRPCResponse(id=request.id, result=result)

        else:
            return JSONRPCResponse(
                id=request.id,
                error=JSONRPCError(
                    code=-32601,
                    message=f"Method not found: {request.method}"
                )
            )

    except ValueError as e:
        return JSONRPCResponse(
            id=request.id,
            error=JSONRPCError(code=-32602, message=str(e))
        )
    except Exception as e:
        return JSONRPCResponse(
            id=request.id,
            error=JSONRPCError(code=-32000, message=str(e))
        )
```

### 1.5 SSE Streaming Endpoint

Create `a2a-servers/video-agent/app/routers/a2a_stream.py`:

```python
import asyncio
import json
from fastapi import APIRouter, Request, Depends
from sse_starlette.sse import EventSourceResponse
from app.models.a2a import JSONRPCRequest
from app.services.task_manager import TaskManager
from app.core.auth import verify_bearer_token

router = APIRouter()
task_manager = TaskManager()


@router.post("/a2a/stream")
async def handle_stream(
    request: Request,
    _: str = Depends(verify_bearer_token)
):
    """
    Handle A2A message/stream with SSE response.

    Returns Server-Sent Events for real-time task progress.
    """
    body = await request.json()
    rpc_request = JSONRPCRequest(**body)

    if rpc_request.method != "message/stream":
        return {"error": "Only message/stream supported on this endpoint"}

    async def event_generator():
        try:
            # Create task and start processing
            async for event in task_manager.stream_task_execution(rpc_request.params):
                yield {
                    "event": event["event"],
                    "data": json.dumps(event["data"])
                }

            # Final done marker
            yield {
                "event": "done",
                "data": "[DONE]"
            }

        except asyncio.CancelledError:
            # Client disconnected
            pass
        except Exception as e:
            yield {
                "event": "task_failed",
                "data": json.dumps({
                    "error": str(e)
                })
            }

    return EventSourceResponse(event_generator())
```

### 1.6 Task Manager Service

Create `a2a-servers/video-agent/app/services/task_manager.py`:

```python
import asyncio
import uuid
from datetime import datetime
from typing import Any, AsyncIterator, Dict, Optional
from app.models.a2a import (
    Task, TaskState, TaskStatus, Message, Artifact,
    TextPart, FilePart, DataPart
)


class TaskManager:
    """
    Manages A2A task lifecycle.

    In mock mode: Simulates video generation with progress updates.
    In production: Integrates with real video generation APIs.
    """

    def __init__(self):
        self._tasks: Dict[str, Task] = {}
        self._cancelled: set = set()

    async def handle_message_send(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle message/send - create and process task.

        For non-streaming: Processes synchronously and returns result.
        """
        message = params.get("message", {})
        task_id = params.get("taskId")  # Continue existing task

        if task_id and task_id in self._tasks:
            # Continue existing task (revision)
            task = self._tasks[task_id]
            task.history.append(Message(**message))
        else:
            # Create new task
            task_id = f"task_{uuid.uuid4().hex[:12]}"
            task = Task(
                id=task_id,
                contextId=f"ctx_{uuid.uuid4().hex[:8]}",
                status=TaskStatus(state=TaskState.SUBMITTED),
                history=[Message(**message)]
            )
            self._tasks[task_id] = task

        # Start processing (simulated)
        await self._process_task(task)

        return task.model_dump()

    async def stream_task_execution(
        self, params: Dict[str, Any]
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream task execution via SSE events.

        Yields events:
        - task_created
        - task_status (progress updates)
        - task_artifact
        - task_completed / task_failed
        """
        message = params.get("message", {})
        config = params.get("configuration", {})

        # Create task
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        task = Task(
            id=task_id,
            contextId=f"ctx_{uuid.uuid4().hex[:8]}",
            status=TaskStatus(state=TaskState.SUBMITTED),
            history=[Message(**message)]
        )
        self._tasks[task_id] = task

        # Emit task_created
        yield {
            "event": "task_created",
            "data": {
                "id": task_id,
                "contextId": task.contextId,
                "status": {"state": "submitted", "timestamp": datetime.utcnow().isoformat()}
            }
        }

        # Simulate processing with progress updates
        try:
            # Phase 1: Initializing
            task.status = TaskStatus(
                state=TaskState.WORKING,
                progress=0,
                message="Initializing video generation..."
            )
            yield {
                "event": "task_status",
                "data": {"id": task_id, "status": task.status.model_dump()}
            }
            await asyncio.sleep(1)

            if task_id in self._cancelled:
                raise asyncio.CancelledError()

            # Phase 2: Scene generation
            for i in range(1, 5):
                if task_id in self._cancelled:
                    raise asyncio.CancelledError()

                progress = i * 20
                task.status = TaskStatus(
                    state=TaskState.WORKING,
                    progress=progress,
                    message=f"Generating scene {i}/4..."
                )
                yield {
                    "event": "task_status",
                    "data": {"id": task_id, "status": task.status.model_dump()}
                }
                await asyncio.sleep(0.8)

            # Phase 3: Rendering
            task.status = TaskStatus(
                state=TaskState.WORKING,
                progress=90,
                message="Rendering final video..."
            )
            yield {
                "event": "task_status",
                "data": {"id": task_id, "status": task.status.model_dump()}
            }
            await asyncio.sleep(1)

            # Generate artifact
            artifact = Artifact(
                id=f"art_{uuid.uuid4().hex[:8]}",
                name="generated_video.mp4",
                mimeType="video/mp4",
                parts=[
                    FilePart(
                        type="file",
                        uri="https://storage.example.com/videos/sample.mp4",
                        mimeType="video/mp4",
                        name="generated_video.mp4"
                    )
                ],
                metadata={
                    "duration_seconds": 15,
                    "resolution": "1920x1080",
                    "generated_at": datetime.utcnow().isoformat()
                }
            )
            task.artifacts = [artifact]

            # Emit artifact
            yield {
                "event": "task_artifact",
                "data": {"id": task_id, "artifact": artifact.model_dump()}
            }

            # Complete
            task.status = TaskStatus(state=TaskState.COMPLETED)
            yield {
                "event": "task_completed",
                "data": task.model_dump()
            }

        except asyncio.CancelledError:
            task.status = TaskStatus(state=TaskState.CANCELLED)
            yield {
                "event": "task_cancelled",
                "data": {"id": task_id, "status": task.status.model_dump()}
            }

    async def _process_task(self, task: Task) -> None:
        """Process task synchronously (for non-streaming)."""
        task.status = TaskStatus(state=TaskState.WORKING, progress=0)

        # Simulate processing
        await asyncio.sleep(2)

        # Generate artifact
        artifact = Artifact(
            id=f"art_{uuid.uuid4().hex[:8]}",
            name="generated_video.mp4",
            mimeType="video/mp4",
            parts=[
                FilePart(
                    type="file",
                    uri="https://storage.example.com/videos/sample.mp4",
                    mimeType="video/mp4"
                )
            ],
            metadata={"duration_seconds": 15, "resolution": "1920x1080"}
        )
        task.artifacts = [artifact]
        task.status = TaskStatus(state=TaskState.COMPLETED)

    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """Get task by ID."""
        if task_id not in self._tasks:
            raise ValueError(f"Task not found: {task_id}")
        return self._tasks[task_id].model_dump()

    async def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """Cancel a running task."""
        if task_id not in self._tasks:
            raise ValueError(f"Task not found: {task_id}")

        self._cancelled.add(task_id)
        task = self._tasks[task_id]
        task.status = TaskStatus(state=TaskState.CANCELLED)
        return task.model_dump()
```

### 1.7 Main Application

Create `a2a-servers/video-agent/app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import agent_card, a2a, a2a_stream
from app.config import settings

app = FastAPI(
    title="A2A Video Producer Agent",
    description="A2A-compliant video generation agent with SSE streaming support",
    version="0.1.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(agent_card.router, tags=["Agent Card"])
app.include_router(a2a.router, tags=["A2A JSON-RPC"])
app.include_router(a2a_stream.router, tags=["A2A Streaming"])


@app.get("/health")
async def health_check():
    return {"status": "healthy", "agent": "video_producer_a2a"}
```

### 1.8 Docker Configuration

Create `a2a-servers/video-agent/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml .
COPY app/ app/

# Install dependencies
RUN uv pip install --system -e .

# Expose port
EXPOSE 8001

# Run server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

Create `a2a-servers/video-agent/docker-compose.yml`:

```yaml
version: '3.8'

services:
  video-agent:
    build: .
    ports:
      - "8001:8001"
    environment:
      - BASE_URL=http://localhost:8001
      - API_KEY=test_api_key_123
      - CORS_ORIGINS=["http://localhost:3000","http://localhost:8000"]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

---

## Phase 2: A2A Client in Backend

### 2.1 Shared A2A Models

Copy models to `backend/app/models/a2a.py` (or use shared package).

### 2.2 A2A Client with SSE Support

Create `backend/app/services/a2a_client.py`:

```python
import json
from typing import Any, AsyncIterator, Callable, Dict, Optional
import httpx
from app.models.a2a import AgentCard, Task, JSONRPCRequest, JSONRPCResponse


class A2AClient:
    """
    Low-level A2A protocol client with SSE streaming support.
    """

    def __init__(
        self,
        api_key: str,
        timeout: Optional[Dict[str, int]] = None
    ):
        self._api_key = api_key
        self._timeout = timeout or {"connect": 10, "read": 300}
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(
                connect=self._timeout["connect"],
                read=self._timeout["read"]
            )
        )

    async def fetch_agent_card(self, url: str) -> AgentCard:
        """Fetch Agent Card from URL."""
        response = await self._client.get(url)
        response.raise_for_status()
        return AgentCard.model_validate(response.json())

    async def send_message(
        self,
        endpoint: str,
        params: Dict[str, Any]
    ) -> Task:
        """Send message/send request."""
        payload = {
            "jsonrpc": "2.0",
            "id": f"req_{id(params)}",
            "method": "message/send",
            "params": params
        }
        response = await self._client.post(endpoint, json=payload)
        response.raise_for_status()
        result = response.json()
        if "error" in result:
            raise Exception(result["error"]["message"])
        return Task.model_validate(result["result"])

    async def stream_message(
        self,
        stream_endpoint: str,
        params: Dict[str, Any],
        on_event: Optional[Callable[[str, Dict], None]] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream message execution via SSE.

        Args:
            stream_endpoint: SSE endpoint URL
            params: Request parameters
            on_event: Optional callback for each event

        Yields:
            SSE events as dictionaries
        """
        payload = {
            "jsonrpc": "2.0",
            "id": f"req_{id(params)}",
            "method": "message/stream",
            "params": params
        }

        async with self._client.stream(
            "POST",
            stream_endpoint,
            json=payload,
            headers={
                "Accept": "text/event-stream",
                "Authorization": f"Bearer {self._api_key}"
            }
        ) as response:
            response.raise_for_status()

            event_type = None
            data_buffer = []

            async for line in response.aiter_lines():
                line = line.strip()

                if line.startswith("event:"):
                    event_type = line[6:].strip()
                elif line.startswith("data:"):
                    data_buffer.append(line[5:].strip())
                elif line == "" and event_type and data_buffer:
                    data_str = "\n".join(data_buffer)
                    if data_str != "[DONE]":
                        event = {
                            "event": event_type,
                            "data": json.loads(data_str)
                        }
                        if on_event:
                            on_event(event_type, event["data"])
                        yield event
                    event_type = None
                    data_buffer = []

    async def get_task(self, endpoint: str, task_id: str) -> Task:
        """Get task by ID (polling)."""
        payload = {
            "jsonrpc": "2.0",
            "id": f"req_get_{task_id}",
            "method": "tasks/get",
            "params": {"taskId": task_id}
        }
        response = await self._client.post(endpoint, json=payload)
        response.raise_for_status()
        result = response.json()
        if "error" in result:
            raise Exception(result["error"]["message"])
        return Task.model_validate(result["result"])

    async def cancel_task(self, endpoint: str, task_id: str) -> Task:
        """Cancel a running task."""
        payload = {
            "jsonrpc": "2.0",
            "id": f"req_cancel_{task_id}",
            "method": "tasks/cancel",
            "params": {"taskId": task_id}
        }
        response = await self._client.post(endpoint, json=payload)
        response.raise_for_status()
        result = response.json()
        return Task.model_validate(result["result"])

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
```

### 2.3 RemoteA2AAgentAdapter

Create `backend/app/agents/remote_a2a_adapter.py` with SSE support (as shown in updated design doc).

---

## Phase 3: AgentRegistry Enhancement

Update `backend/app/services/agent_registry.py` to support remote A2A agents with Redis configuration.

---

## Phase 4: API Endpoints

Create `backend/app/routers/agents.py` for agent management.

---

## Phase 5: Frontend Integration

### 5.1 AgentStatusBar Updates

- Show "Remote" badge with SSE streaming indicator
- Display real-time progress from SSE events
- "ACTIVE" / "STANDBY" status

### 5.2 Add Agent Modal

- Validate Agent Card URL
- Preview capabilities including streaming support
- Store API key in Redis

---

## File Structure Summary

```
ai-agency/
├── a2a-servers/                      # Standalone A2A servers
│   └── video-agent/                  # Video Producer A2A Server
│       ├── README.md
│       ├── pyproject.toml
│       ├── Dockerfile
│       ├── docker-compose.yml
│       ├── .env.example
│       ├── app/
│       │   ├── main.py
│       │   ├── config.py
│       │   ├── models/
│       │   │   ├── a2a.py
│       │   │   └── video.py
│       │   ├── routers/
│       │   │   ├── agent_card.py
│       │   │   ├── a2a.py
│       │   │   └── a2a_stream.py
│       │   ├── services/
│       │   │   ├── task_manager.py
│       │   │   └── video_generator.py
│       │   └── core/
│       │       ├── sse.py
│       │       └── auth.py
│       └── tests/
│
├── backend/
│   └── app/
│       ├── agents/
│       │   └── remote_a2a_adapter.py
│       ├── models/
│       │   └── a2a.py
│       ├── routers/
│       │   └── agents.py
│       └── services/
│           ├── a2a_client.py
│           ├── agent_registry.py (modified)
│           └── circuit_breaker.py
│
└── frontend/
    └── src/
        ├── components/
        │   ├── AgentStatusBar.tsx (modified)
        │   ├── AddAgentModal.tsx
        │   └── AgentManagementPanel.tsx
        └── stores/
            └── useProjectStore.ts (modified)
```

---

## Implementation Order

1. **Day 1-2**: Create standalone video-agent project structure
2. **Day 3-4**: Implement A2A models, Agent Card, JSON-RPC endpoint
3. **Day 5-6**: Implement SSE streaming endpoint and task manager
4. **Day 7**: Docker setup, test standalone server
5. **Day 8-9**: A2AClient with SSE support in backend
6. **Day 10-11**: RemoteA2AAgentAdapter integration
7. **Day 12-13**: AgentRegistry updates, Redis schema
8. **Day 14-15**: API endpoints and frontend components
9. **Day 16**: Integration testing

---

## Deployment Notes

### Standalone A2A Server Deployment

The video-agent can be deployed independently:

```bash
# Local development
cd a2a-servers/video-agent
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8001

# Docker
docker build -t a2a-video-agent .
docker run -p 8001:8001 a2a-video-agent

# Cloud Run
gcloud run deploy a2a-video-agent \
  --source . \
  --port 8001 \
  --allow-unauthenticated
```

### Converting Mock to Real Implementation

To convert the mock server to real video generation:

1. Add real video generation service in `app/services/video_generator.py`
2. Integrate with Veo API or other video generation APIs
3. Update `task_manager.py` to call real service
4. Add GCS/S3 storage for artifacts
5. Update environment configuration

The A2A protocol interface remains unchanged - only the internal implementation changes.
