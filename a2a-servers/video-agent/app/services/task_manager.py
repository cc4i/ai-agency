"""Task Manager Service.

Manages A2A task lifecycle with support for both synchronous and streaming execution.
In mock mode, simulates video generation with progress updates.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any, AsyncIterator, Dict, Optional

from app.config import settings
from app.models.a2a import (
    Artifact,
    FilePart,
    Message,
    Task,
    TaskState,
    TaskStatus,
    TextPart,
)


class TaskManager:
    """
    Manages A2A task lifecycle.

    In mock mode: Simulates video generation with progress updates.
    In production: Would integrate with real video generation APIs.
    """

    def __init__(self):
        """Initialize task manager with in-memory storage."""
        self._tasks: Dict[str, Task] = {}
        self._cancelled: set = set()

    def _generate_task_id(self) -> str:
        """Generate unique task ID."""
        return f"task_{uuid.uuid4().hex[:12]}"

    def _generate_context_id(self) -> str:
        """Generate unique context ID."""
        return f"ctx_{uuid.uuid4().hex[:8]}"

    def _generate_artifact_id(self) -> str:
        """Generate unique artifact ID."""
        return f"art_{uuid.uuid4().hex[:8]}"

    def _generate_message_id(self) -> str:
        """Generate unique message ID."""
        return f"msg_{uuid.uuid4().hex[:8]}"

    def _parse_message(self, message_data: Dict[str, Any]) -> Message:
        """Parse message data into Message model."""
        parts = []
        for part in message_data.get("parts", []):
            if part.get("type") == "text":
                parts.append(TextPart(text=part["text"]))
            elif part.get("type") == "file":
                parts.append(
                    FilePart(
                        uri=part["uri"],
                        mimeType=part["mimeType"],
                        name=part.get("name"),
                    )
                )
            else:
                # Default to text part for unknown types
                parts.append(TextPart(text=str(part.get("data", part))))

        return Message(
            messageId=message_data.get("messageId", self._generate_message_id()),
            role=message_data.get("role", "user"),
            parts=parts,
            timestamp=datetime.utcnow(),
        )

    def _create_video_artifact(self, task_id: str) -> Artifact:
        """Create mock video artifact."""
        return Artifact(
            id=self._generate_artifact_id(),
            name="generated_video.mp4",
            mimeType="video/mp4",
            parts=[
                FilePart(
                    type="file",
                    uri=settings.mock_video_url,
                    mimeType="video/mp4",
                    name="generated_video.mp4",
                )
            ],
            metadata={
                "duration_seconds": 15,
                "resolution": "1920x1080",
                "generated_at": datetime.utcnow().isoformat(),
                "task_id": task_id,
            },
        )

    async def handle_message_send(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle message/send - create and process task synchronously.

        For non-streaming: Processes and returns complete result.

        Args:
            params: Request parameters containing message and optional taskId

        Returns:
            Complete task as dictionary
        """
        message_data = params.get("message", {})
        task_id = params.get("taskId")  # For continuing existing task

        if task_id and task_id in self._tasks:
            # Continue existing task (revision)
            task = self._tasks[task_id]
            message = self._parse_message(message_data)
            task.history.append(message)
        else:
            # Create new task
            task_id = self._generate_task_id()
            message = self._parse_message(message_data)
            task = Task(
                id=task_id,
                contextId=self._generate_context_id(),
                status=TaskStatus(state=TaskState.SUBMITTED),
                history=[message],
            )
            self._tasks[task_id] = task

        # Process task synchronously
        await self._process_task(task)

        return task.model_dump(mode="json")

    async def _process_task(self, task: Task) -> None:
        """
        Process task synchronously (for non-streaming).

        Args:
            task: Task to process
        """
        task.status = TaskStatus(state=TaskState.WORKING, progress=0)

        # Simulate processing time
        await asyncio.sleep(2)

        # Check for cancellation
        if task.id in self._cancelled:
            task.status = TaskStatus(state=TaskState.CANCELLED)
            return

        # Generate artifact
        artifact = self._create_video_artifact(task.id)
        task.artifacts = [artifact]
        task.status = TaskStatus(state=TaskState.COMPLETED)

    async def stream_task_execution(
        self, params: Dict[str, Any]
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream task execution via SSE events.

        Yields events for real-time progress updates:
        - task_created: Task accepted and queued
        - task_status: Progress updates with percentage
        - task_artifact: Generated artifact
        - task_completed: Final result
        - task_failed: Error occurred
        - task_cancelled: Task was cancelled

        Args:
            params: Request parameters containing message and configuration

        Yields:
            SSE events as dictionaries with 'event' and 'data' keys
        """
        message_data = params.get("message", {})
        # config = params.get("configuration", {})  # Available for future use

        # Create task
        task_id = self._generate_task_id()
        message = self._parse_message(message_data)
        task = Task(
            id=task_id,
            contextId=self._generate_context_id(),
            status=TaskStatus(state=TaskState.SUBMITTED),
            history=[message],
        )
        self._tasks[task_id] = task

        # Emit task_created
        yield {
            "event": "task_created",
            "data": {
                "id": task_id,
                "contextId": task.contextId,
                "status": {
                    "state": "submitted",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            },
        }

        # Simulate processing with progress updates
        try:
            # Phase 1: Initializing
            task.status = TaskStatus(
                state=TaskState.WORKING,
                progress=0,
                message="Initializing video generation...",
            )
            yield {
                "event": "task_status",
                "data": {
                    "id": task_id,
                    "status": {
                        "state": "working",
                        "progress": 0,
                        "message": "Initializing video generation...",
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                },
            }
            await asyncio.sleep(settings.mock_processing_delay)

            if task_id in self._cancelled:
                raise asyncio.CancelledError()

            # Phase 2: Scene generation (4 scenes)
            for i in range(1, 5):
                if task_id in self._cancelled:
                    raise asyncio.CancelledError()

                progress = i * 20
                message = f"Generating scene {i}/4..."
                task.status = TaskStatus(
                    state=TaskState.WORKING,
                    progress=progress,
                    message=message,
                )
                yield {
                    "event": "task_status",
                    "data": {
                        "id": task_id,
                        "status": {
                            "state": "working",
                            "progress": progress,
                            "message": message,
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    },
                }
                await asyncio.sleep(settings.mock_processing_delay)

            # Phase 3: Rendering
            task.status = TaskStatus(
                state=TaskState.WORKING,
                progress=90,
                message="Rendering final video...",
            )
            yield {
                "event": "task_status",
                "data": {
                    "id": task_id,
                    "status": {
                        "state": "working",
                        "progress": 90,
                        "message": "Rendering final video...",
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                },
            }
            await asyncio.sleep(settings.mock_processing_delay)

            if task_id in self._cancelled:
                raise asyncio.CancelledError()

            # Generate artifact
            artifact = self._create_video_artifact(task_id)
            task.artifacts = [artifact]

            # Emit artifact
            yield {
                "event": "task_artifact",
                "data": {
                    "id": task_id,
                    "artifact": artifact.model_dump(mode="json"),
                },
            }

            # Complete
            task.status = TaskStatus(state=TaskState.COMPLETED)
            yield {
                "event": "task_completed",
                "data": task.model_dump(mode="json"),
            }

        except asyncio.CancelledError:
            task.status = TaskStatus(state=TaskState.CANCELLED)
            yield {
                "event": "task_cancelled",
                "data": {
                    "id": task_id,
                    "status": {
                        "state": "cancelled",
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                },
            }

    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """
        Get task by ID.

        Args:
            task_id: Task identifier

        Returns:
            Task as dictionary

        Raises:
            ValueError: If task not found
        """
        if task_id not in self._tasks:
            raise ValueError(f"Task not found: {task_id}")
        return self._tasks[task_id].model_dump(mode="json")

    async def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """
        Cancel a running task.

        Args:
            task_id: Task identifier

        Returns:
            Cancelled task as dictionary

        Raises:
            ValueError: If task not found
        """
        if task_id not in self._tasks:
            raise ValueError(f"Task not found: {task_id}")

        self._cancelled.add(task_id)
        task = self._tasks[task_id]
        task.status = TaskStatus(state=TaskState.CANCELLED)
        return task.model_dump(mode="json")

    def get_task_sync(self, task_id: str) -> Optional[Task]:
        """
        Get task by ID synchronously (for internal use).

        Args:
            task_id: Task identifier

        Returns:
            Task or None if not found
        """
        return self._tasks.get(task_id)


# Global task manager instance
task_manager = TaskManager()
