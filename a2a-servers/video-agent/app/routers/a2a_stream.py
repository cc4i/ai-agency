"""A2A SSE Streaming Endpoint.

Handles A2A message/stream requests with Server-Sent Events for real-time updates.
"""

import asyncio
import json

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from app.core.auth import verify_bearer_token
from app.models.a2a import JSONRPCRequest
from app.services.task_manager import task_manager

router = APIRouter()


@router.post("/a2a/stream")
async def handle_stream(
    request: Request,
    _: str = Depends(verify_bearer_token),
) -> EventSourceResponse:
    """
    Handle A2A message/stream with SSE response.

    Returns Server-Sent Events for real-time task progress updates.
    This is the preferred method when streaming is needed.

    Event types emitted:
    - task_created: Task accepted and queued
    - task_status: Progress updates (0-100%)
    - task_artifact: Generated artifact
    - task_completed: Final result with all artifacts
    - task_failed: Error occurred
    - task_cancelled: Task was cancelled
    - done: Stream ended marker

    Args:
        request: FastAPI request containing JSON-RPC body
        _: Verified bearer token (authentication)

    Returns:
        Server-Sent Events stream
    """
    body = await request.json()
    rpc_request = JSONRPCRequest(**body)

    if rpc_request.method != "message/stream":
        # Return error as SSE event for non-stream methods
        async def error_generator():
            yield {
                "event": "error",
                "data": json.dumps({
                    "error": {
                        "code": -32601,
                        "message": "Only message/stream supported on this endpoint",
                    }
                }),
            }

        return EventSourceResponse(error_generator())

    async def event_generator():
        """Generate SSE events from task execution stream."""
        try:
            async for event in task_manager.stream_task_execution(rpc_request.params):
                yield {
                    "event": event["event"],
                    "data": json.dumps(event["data"]),
                }

            # Final done marker
            yield {
                "event": "done",
                "data": "[DONE]",
            }

        except asyncio.CancelledError:
            # Client disconnected
            pass
        except Exception as e:
            yield {
                "event": "task_failed",
                "data": json.dumps({
                    "error": str(e),
                }),
            }

    return EventSourceResponse(event_generator())
