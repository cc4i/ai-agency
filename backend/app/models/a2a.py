"""A2A Protocol Models for Backend.

Implements the A2A (Agent-to-Agent) protocol specification for
communicating with remote A2A-compliant agents.

See: https://a2a-protocol.org/latest/specification/
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


# ============ Enums ============


class TaskState(str, Enum):
    """Task lifecycle states per A2A specification."""

    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ============ Message Parts ============


class TextPart(BaseModel):
    """Text content part."""

    type: Literal["text"] = "text"
    text: str


class FilePart(BaseModel):
    """File reference part with URI."""

    type: Literal["file"] = "file"
    uri: str
    mimeType: str
    name: Optional[str] = None


class DataPart(BaseModel):
    """Structured JSON data part."""

    type: Literal["data"] = "data"
    mimeType: str = "application/json"
    data: Dict[str, Any]


Part = Union[TextPart, FilePart, DataPart]


# ============ Messages ============


class Message(BaseModel):
    """Conversational message containing parts."""

    messageId: str
    role: Literal["user", "agent"]
    parts: List[Part]
    timestamp: Optional[datetime] = None


# ============ Artifacts ============


class Artifact(BaseModel):
    """Task output artifact."""

    id: str
    name: str
    mimeType: str
    parts: List[Part]
    metadata: Optional[Dict[str, Any]] = None


# ============ Task Status ============


class TaskStatus(BaseModel):
    """Current status of a task."""

    state: TaskState
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    progress: Optional[int] = None  # 0-100
    message: Optional[Union[str, Message]] = None


class Task(BaseModel):
    """A2A Task representing a unit of work."""

    id: str
    contextId: Optional[str] = None
    status: TaskStatus
    artifacts: List[Artifact] = []
    history: List[Message] = []


# ============ Agent Card ============


class AgentSkill(BaseModel):
    """Declared capability that an agent can perform."""

    id: str
    name: str
    description: str
    inputModes: List[str] = ["text/plain"]
    outputModes: List[str] = ["application/json"]
    examples: Optional[List[Dict[str, str]]] = None


class AgentProvider(BaseModel):
    """Information about the agent provider."""

    name: str
    url: Optional[str] = None


class AgentCapabilities(BaseModel):
    """Agent capability flags."""

    streaming: bool = False
    pushNotifications: bool = False


class SecurityScheme(BaseModel):
    """Security scheme declaration."""

    type: str
    scheme: Optional[str] = None
    description: Optional[str] = None


class AgentCard(BaseModel):
    """Agent Card - JSON metadata describing agent capabilities.

    Hosted at /.well-known/agent.json per A2A specification.
    """

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
    """JSON-RPC 2.0 request."""

    jsonrpc: Literal["2.0"] = "2.0"
    id: str
    method: str
    params: Dict[str, Any] = {}


class JSONRPCError(BaseModel):
    """JSON-RPC 2.0 error object."""

    code: int
    message: str
    data: Optional[Any] = None


class JSONRPCResponse(BaseModel):
    """JSON-RPC 2.0 response."""

    jsonrpc: Literal["2.0"] = "2.0"
    id: str
    result: Optional[Any] = None
    error: Optional[JSONRPCError] = None


# ============ Remote Agent Configuration ============


class RemoteAgentConfig(BaseModel):
    """Configuration for a remote A2A agent stored in Redis."""

    provider: Literal["remote"] = "remote"
    agent_card_url: str
    api_key: str  # Actual API key (stored encrypted in Redis)
    fallback_to_local: bool = True
    timeout: Dict[str, int] = Field(
        default_factory=lambda: {"connect": 10, "read": 300, "total": 600}
    )
    circuit_breaker: Dict[str, int] = Field(
        default_factory=lambda: {"failure_threshold": 5, "recovery_timeout_seconds": 60}
    )


# ============ Agent Info (for registry) ============


class AgentInfo(BaseModel):
    """Agent information for listing and discovery."""

    agent_id: str
    name: str
    description: str
    provider: Literal["local", "remote"]
    status: Literal["ready", "working", "error", "offline"] = "ready"
    skills: List[Dict[str, Any]] = []
    is_active: bool = True
    overrides: Optional[str] = None  # ID of local agent this overrides
    overridden_by: Optional[str] = None  # ID of remote agent that overrides this


# ============ Task Execution Result ============


class ExecutionResult(BaseModel):
    """Result from executing a task via A2A."""

    status: Literal["completed", "needs_revision", "failed", "cancelled"]
    task_id: Optional[str] = None
    artifacts: List[Artifact] = []
    critique: Optional[Dict[str, Any]] = None
    provider: Literal["local", "remote"] = "remote"
    agent_id: str
    was_fallback: bool = False
    fallback_reason: Optional[str] = None
