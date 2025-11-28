"""Remote A2A Agent Adapter.

Implements AgentBase interface for remote A2A-compliant agents.
Provides transparent integration with the existing agent system.
"""

import asyncio
import logging
import uuid
from typing import Any, Callable, Dict, Optional

from app.agents.base import AgentBase
from app.models.a2a import (
    AgentCard,
    Artifact,
    DataPart,
    Task,
    TaskState,
    TextPart,
)
from app.models.assets import CritiqueResult
from app.services.a2a_client import (
    A2AClient,
    A2AConnectionError,
    A2AError,
    A2ATaskError,
)

logger = logging.getLogger(__name__)


class RemoteA2AAgentAdapter(AgentBase):
    """
    A2A-compliant adapter that implements AgentBase interface
    while communicating with remote agents via JSON-RPC 2.0.

    Features:
    - SSE streaming for real-time progress updates (preferred)
    - Polling fallback when streaming unavailable
    - Automatic capability detection from Agent Card
    - Transparent integration with existing critique/revise workflow
    """

    def __init__(
        self,
        agent_id: str,
        agent_card_url: str,
        api_key: str,
        timeout: Optional[Dict[str, int]] = None,
        on_progress: Optional[Callable[[str, int, str], None]] = None,
    ):
        """
        Initialize adapter.

        Args:
            agent_id: Local agent ID for this adapter
            agent_card_url: URL to fetch Agent Card
            api_key: API key for authentication
            timeout: Timeout configuration
            on_progress: Optional callback for progress updates (task_id, progress, message)
        """
        super().__init__(agent_id)
        self.agent_card_url = agent_card_url
        self._api_key = api_key
        self._timeout = timeout or {"connect": 10, "read": 300, "total": 600}
        self._on_progress = on_progress
        self._agent_card: Optional[AgentCard] = None
        self._client: Optional[A2AClient] = None

    async def _get_client(self) -> A2AClient:
        """Get or create A2A client."""
        if self._client is None:
            self._client = A2AClient(
                api_key=self._api_key,
                timeout=self._timeout,
                on_progress=self._on_progress,
            )
        return self._client

    async def _ensure_agent_card(self) -> AgentCard:
        """Fetch and cache Agent Card."""
        if self._agent_card is None:
            client = await self._get_client()
            self._agent_card = await client.fetch_agent_card(self.agent_card_url)
            logger.info(
                f"Fetched Agent Card for {self.agent_id}: "
                f"{self._agent_card.name} (streaming={self._supports_streaming()})"
            )
        return self._agent_card

    def _supports_streaming(self) -> bool:
        """Check if remote agent supports SSE streaming."""
        if self._agent_card is None:
            return False
        return self._agent_card.capabilities.streaming

    def _get_stream_endpoint(self) -> str:
        """Get SSE stream endpoint URL."""
        if self._agent_card is None:
            raise ValueError("Agent Card not loaded")
        # Convention: stream endpoint is /a2a/stream
        base_url = self._agent_card.url
        if base_url.endswith("/a2a"):
            return f"{base_url}/stream"
        return f"{base_url.rstrip('/')}/a2a/stream"

    def _build_message(
        self, task: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build A2A message from task and context."""
        message_id = f"msg_{uuid.uuid4().hex[:12]}"

        parts = [
            {"type": "text", "text": task.get("description", "Execute task")},
            {
                "type": "data",
                "mimeType": "application/json",
                "data": {"task": task, "context": context},
            },
        ]

        return {
            "messageId": message_id,
            "role": "user",
            "parts": parts,
        }

    def _extract_critique(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Extract critique data from A2A message parts."""
        critique = {"issues": [], "score": 0.5, "feedback": ""}

        if isinstance(message, str):
            critique["feedback"] = message
            return critique

        for part in message.get("parts", []):
            if part.get("type") == "data":
                data = part.get("data", {})
                if "critique" in str(data).lower() or "issues" in data:
                    critique.update(data)
            elif part.get("type") == "text":
                critique["feedback"] = part.get("text", "")

        return critique

    def _convert_artifacts_to_result(
        self, artifacts: list, task_id: str
    ) -> Dict[str, Any]:
        """Convert A2A artifacts to agent result format."""
        result = {
            "status": "completed",
            "task_id": task_id,
            "artifacts": [],
            "provider": "remote",
            "agent_id": self.agent_id,
        }

        for artifact in artifacts:
            if isinstance(artifact, dict):
                result["artifacts"].append(artifact)
            elif isinstance(artifact, Artifact):
                result["artifacts"].append(artifact.model_dump())
            else:
                result["artifacts"].append({"data": artifact})

        return result

    async def _execute_with_streaming(
        self, task: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute task using SSE streaming for real-time updates."""
        client = await self._get_client()
        card = await self._ensure_agent_card()

        message = self._build_message(task, context)
        config = {
            "acceptedOutputModes": task.get("output_modes", ["application/json"])
        }

        stream_endpoint = self._get_stream_endpoint()

        task_id: Optional[str] = None
        artifacts: list = []
        final_result: Optional[Dict[str, Any]] = None

        async for event in client.stream_message(
            stream_endpoint, {"message": message, "configuration": config}
        ):
            event_type = event["event"]
            data = event["data"]

            if event_type == "task_created":
                task_id = data.get("id")
                logger.debug(f"Task created: {task_id}")

            elif event_type == "task_status":
                # Progress is reported via callback in A2AClient
                pass

            elif event_type == "task_artifact":
                artifact = data.get("artifact", data)
                artifacts.append(artifact)
                logger.debug(f"Received artifact: {artifact.get('id', 'unknown')}")

            elif event_type == "task_input_required":
                # Agent needs user input (critique workflow)
                status = data.get("status", {})
                return {
                    "status": "needs_revision",
                    "task_id": task_id,
                    "critique": self._extract_critique(status.get("message", {})),
                    "provider": "remote",
                    "agent_id": self.agent_id,
                }

            elif event_type == "task_completed":
                final_result = data
                # Use artifacts from stream if available
                if not artifacts and "artifacts" in data:
                    artifacts = data["artifacts"]

            elif event_type == "task_failed":
                error_msg = data.get("error", data.get("status", {}).get("message", "Task failed"))
                raise A2ATaskError(str(error_msg))

            elif event_type == "task_cancelled":
                return {
                    "status": "cancelled",
                    "task_id": task_id,
                    "provider": "remote",
                    "agent_id": self.agent_id,
                }

        if final_result:
            return self._convert_artifacts_to_result(artifacts, task_id or "unknown")

        raise A2ATaskError("Stream ended without completion event")

    async def _execute_with_polling(
        self, task: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute task using polling fallback."""
        client = await self._get_client()
        card = await self._ensure_agent_card()

        message = self._build_message(task, context)
        config = {
            "acceptedOutputModes": task.get("output_modes", ["application/json"])
        }

        # Send initial message
        result = await client.send_message(
            card.url, {"message": message, "configuration": config}
        )

        task_id = result.id

        # Poll until terminal state
        poll_interval = 2  # seconds
        max_polls = 150  # 5 minutes max

        for _ in range(max_polls):
            if result.status.state in (TaskState.SUBMITTED, TaskState.WORKING):
                await asyncio.sleep(poll_interval)
                result = await client.get_task(card.url, task_id)

                # Report progress if available
                if self._on_progress and result.status.progress is not None:
                    msg = ""
                    if isinstance(result.status.message, str):
                        msg = result.status.message
                    self._on_progress(task_id, result.status.progress, msg)
            else:
                break

        # Handle terminal states
        if result.status.state == TaskState.COMPLETED:
            return self._convert_artifacts_to_result(
                [a.model_dump() for a in result.artifacts], task_id
            )

        elif result.status.state == TaskState.INPUT_REQUIRED:
            return {
                "status": "needs_revision",
                "task_id": task_id,
                "critique": self._extract_critique(
                    result.status.message if isinstance(result.status.message, dict)
                    else {"text": str(result.status.message)}
                ),
                "provider": "remote",
                "agent_id": self.agent_id,
            }

        elif result.status.state == TaskState.FAILED:
            msg = result.status.message
            if isinstance(msg, dict):
                msg = msg.get("text", str(msg))
            raise A2ATaskError(f"Task failed: {msg}")

        elif result.status.state == TaskState.CANCELLED:
            return {
                "status": "cancelled",
                "task_id": task_id,
                "provider": "remote",
                "agent_id": self.agent_id,
            }

        else:
            raise A2ATaskError(f"Unexpected state: {result.status.state}")

    async def execute(
        self, task: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute task via A2A protocol.

        Automatically uses SSE streaming if supported by remote agent,
        otherwise falls back to polling.

        Args:
            task: Task parameters
            context: Shared context

        Returns:
            Agent output dictionary
        """
        await self._ensure_agent_card()

        if self._supports_streaming():
            logger.info(f"Executing {self.agent_id} task via SSE streaming")
            return await self._execute_with_streaming(task, context)
        else:
            logger.info(f"Executing {self.agent_id} task via polling")
            return await self._execute_with_polling(task, context)

    async def critique(
        self, result: Dict[str, Any], brief: Dict[str, Any]
    ) -> CritiqueResult:
        """
        For remote A2A agents, critique is handled via input-required state.
        This method extracts critique from the A2A response.

        Args:
            result: Agent output to evaluate
            brief: Project brief for comparison

        Returns:
            CritiqueResult with status and revision instructions
        """
        if result.get("status") == "needs_revision":
            critique_data = result.get("critique", {})
            issues = critique_data.get("issues", [])

            # If we have feedback but no issues list, create one
            if not issues and critique_data.get("feedback"):
                issues = [critique_data["feedback"]]

            return CritiqueResult(
                status="REVISE" if issues else "PASS",
                score=critique_data.get("score", 0.5),
                issues=issues,
                revision_instructions=critique_data.get(
                    "suggested_revision", critique_data.get("feedback")
                ),
            )

        # Completed without input-required = passed critique
        return CritiqueResult(status="PASS", score=1.0, issues=[])

    async def revise(
        self, result: Dict[str, Any], critique: CritiqueResult
    ) -> Dict[str, Any]:
        """
        Continue A2A task with revision instructions.

        Args:
            result: Original agent output
            critique: Critique with revision instructions

        Returns:
            Revised agent output
        """
        task_id = result.get("task_id")
        if not task_id:
            raise ValueError("Cannot revise without task_id from input-required state")

        client = await self._get_client()
        card = await self._ensure_agent_card()

        # Send revision message to existing task
        message = {
            "messageId": f"msg_{uuid.uuid4().hex[:12]}",
            "role": "user",
            "parts": [
                {
                    "type": "text",
                    "text": critique.revision_instructions or "Please revise",
                },
                {
                    "type": "data",
                    "mimeType": "application/json",
                    "data": {
                        "action": "revise",
                        "critique": {
                            "status": critique.status,
                            "score": critique.score,
                            "issues": critique.issues,
                            "revision_instructions": critique.revision_instructions,
                        },
                    },
                },
            ],
        }

        # Send revision
        task_result = await client.send_message(
            card.url, {"taskId": task_id, "message": message}
        )

        # Poll until complete
        poll_interval = 2
        max_polls = 150

        for _ in range(max_polls):
            if task_result.status.state in (TaskState.SUBMITTED, TaskState.WORKING):
                await asyncio.sleep(poll_interval)
                task_result = await client.get_task(card.url, task_id)
            else:
                break

        if task_result.status.state == TaskState.COMPLETED:
            return self._convert_artifacts_to_result(
                [a.model_dump() for a in task_result.artifacts], task_id
            )
        else:
            raise A2ATaskError(f"Revision failed: {task_result.status.state}")

    async def get_skills(self) -> list:
        """Get skills from Agent Card for dynamic tool generation."""
        card = await self._ensure_agent_card()
        return [skill.model_dump() for skill in card.skills]

    async def get_agent_card(self) -> AgentCard:
        """Get the cached or fetched Agent Card."""
        return await self._ensure_agent_card()

    async def health_check(self) -> bool:
        """Check if remote agent is healthy."""
        try:
            await self._ensure_agent_card()
            return True
        except Exception as e:
            logger.warning(f"Health check failed for {self.agent_id}: {e}")
            return False

    async def close(self):
        """Close the underlying HTTP client."""
        if self._client:
            await self._client.close()
            self._client = None
