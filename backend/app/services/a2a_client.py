"""A2A Protocol Client with SSE Streaming Support.

Low-level client for communicating with A2A-compliant remote agents.
Supports both synchronous JSON-RPC calls and SSE streaming for real-time updates.
"""

import json
import logging
import uuid
from typing import Any, AsyncIterator, Callable, Dict, Optional

import httpx

from app.models.a2a import AgentCard, Artifact, Task, TaskState

logger = logging.getLogger(__name__)


class A2AError(Exception):
    """Base exception for A2A protocol errors."""

    def __init__(self, message: str, code: int = -32000, data: Any = None):
        super().__init__(message)
        self.code = code
        self.data = data


class A2ATaskError(A2AError):
    """Exception for task execution errors."""

    pass


class A2AConnectionError(A2AError):
    """Exception for connection/network errors."""

    pass


class A2AClient:
    """
    Low-level A2A protocol client with SSE streaming support.

    Features:
    - Fetch and cache Agent Cards
    - Send messages via JSON-RPC 2.0
    - Stream task execution via SSE
    - Poll for task status (fallback)
    - Cancel running tasks
    """

    def __init__(
        self,
        api_key: str,
        timeout: Optional[Dict[str, int]] = None,
        on_progress: Optional[Callable[[str, int, str], None]] = None,
    ):
        """
        Initialize A2A client.

        Args:
            api_key: API key for Bearer authentication
            timeout: Timeout configuration (connect, read, total)
            on_progress: Optional callback for progress updates (task_id, progress, message)
        """
        self._api_key = api_key
        self._timeout = timeout or {"connect": 10, "read": 300, "total": 600}
        self._on_progress = on_progress
        self._request_id = 0
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(
                timeout=self._timeout.get("total", 600),
                connect=self._timeout["connect"],
                read=self._timeout["read"],
                write=self._timeout.get("write", 30),
                pool=self._timeout.get("pool", 60),
            ),
        )

    def _next_request_id(self) -> str:
        """Generate next request ID."""
        self._request_id += 1
        return f"req_{self._request_id}_{uuid.uuid4().hex[:8]}"

    async def fetch_agent_card(self, url: str) -> AgentCard:
        """
        Fetch Agent Card from URL.

        Args:
            url: URL to the Agent Card (e.g., /.well-known/agent.json)

        Returns:
            Parsed AgentCard

        Raises:
            A2AConnectionError: If unable to fetch
        """
        try:
            response = await self._client.get(url)
            response.raise_for_status()
            return AgentCard.model_validate(response.json())
        except httpx.HTTPError as e:
            raise A2AConnectionError(f"Failed to fetch Agent Card: {e}") from e

    async def send_message(
        self,
        endpoint: str,
        params: Dict[str, Any],
    ) -> Task:
        """
        Send message/send request (synchronous).

        Args:
            endpoint: A2A endpoint URL
            params: Request parameters (message, configuration, etc.)

        Returns:
            Task with result

        Raises:
            A2AError: If request fails
        """
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "message/send",
            "params": params,
        }

        try:
            response = await self._client.post(endpoint, json=payload)
            response.raise_for_status()
            result = response.json()

            if "error" in result and result["error"]:
                error = result["error"]
                raise A2AError(
                    message=error.get("message", "Unknown error"),
                    code=error.get("code", -32000),
                    data=error.get("data"),
                )

            return Task.model_validate(result["result"])

        except httpx.HTTPError as e:
            raise A2AConnectionError(f"HTTP error during message/send: {e}") from e

    async def stream_message(
        self,
        stream_endpoint: str,
        params: Dict[str, Any],
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream message execution via SSE.

        Args:
            stream_endpoint: SSE endpoint URL (e.g., /a2a/stream)
            params: Request parameters

        Yields:
            SSE events as dictionaries with 'event' and 'data' keys

        Event types:
            - task_created: Task accepted
            - task_status: Progress update
            - task_artifact: Artifact generated
            - task_input_required: Needs user input
            - task_completed: Task finished
            - task_failed: Error occurred
            - task_cancelled: Task cancelled
        """
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "message/stream",
            "params": params,
        }

        try:
            async with self._client.stream(
                "POST",
                stream_endpoint,
                json=payload,
                headers={
                    "Accept": "text/event-stream",
                    "Authorization": f"Bearer {self._api_key}",
                },
            ) as response:
                response.raise_for_status()

                event_type: Optional[str] = None
                data_buffer: list = []

                async for line in response.aiter_lines():
                    line = line.strip()

                    if line.startswith("event:"):
                        event_type = line[6:].strip()
                    elif line.startswith("data:"):
                        data_buffer.append(line[5:].strip())
                    elif line == "" and event_type and data_buffer:
                        # Empty line = end of event
                        data_str = "\n".join(data_buffer)
                        if data_str != "[DONE]":
                            try:
                                event = {
                                    "event": event_type,
                                    "data": json.loads(data_str),
                                }

                                # Call progress callback if available
                                if (
                                    self._on_progress
                                    and event_type == "task_status"
                                ):
                                    status = event["data"].get("status", {})
                                    self._on_progress(
                                        event["data"].get("id", ""),
                                        status.get("progress", 0),
                                        status.get("message", ""),
                                    )

                                yield event
                            except json.JSONDecodeError:
                                logger.warning(f"Failed to parse SSE data: {data_str}")

                        event_type = None
                        data_buffer = []

        except httpx.HTTPError as e:
            raise A2AConnectionError(f"HTTP error during streaming: {e}") from e

    async def get_task(self, endpoint: str, task_id: str) -> Task:
        """
        Get task by ID (polling).

        Args:
            endpoint: A2A endpoint URL
            task_id: Task identifier

        Returns:
            Task with current status

        Raises:
            A2AError: If request fails
        """
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "tasks/get",
            "params": {"taskId": task_id},
        }

        try:
            response = await self._client.post(endpoint, json=payload)
            response.raise_for_status()
            result = response.json()

            if "error" in result and result["error"]:
                error = result["error"]
                raise A2AError(
                    message=error.get("message", "Unknown error"),
                    code=error.get("code", -32000),
                )

            return Task.model_validate(result["result"])

        except httpx.HTTPError as e:
            raise A2AConnectionError(f"HTTP error during tasks/get: {e}") from e

    async def cancel_task(self, endpoint: str, task_id: str) -> Task:
        """
        Cancel a running task.

        Args:
            endpoint: A2A endpoint URL
            task_id: Task identifier

        Returns:
            Task with cancelled status

        Raises:
            A2AError: If request fails
        """
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "tasks/cancel",
            "params": {"taskId": task_id},
        }

        try:
            response = await self._client.post(endpoint, json=payload)
            response.raise_for_status()
            result = response.json()

            if "error" in result and result["error"]:
                error = result["error"]
                raise A2AError(
                    message=error.get("message", "Unknown error"),
                    code=error.get("code", -32000),
                )

            return Task.model_validate(result["result"])

        except httpx.HTTPError as e:
            raise A2AConnectionError(f"HTTP error during tasks/cancel: {e}") from e

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
