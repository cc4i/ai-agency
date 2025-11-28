"""A2A JSON-RPC Endpoint.

Handles A2A protocol JSON-RPC 2.0 requests for task management.
"""

from fastapi import APIRouter, Depends

from app.core.auth import verify_bearer_token
from app.models.a2a import JSONRPCError, JSONRPCRequest, JSONRPCResponse
from app.services.task_manager import task_manager

router = APIRouter()


@router.post("/a2a", response_model=JSONRPCResponse)
async def handle_jsonrpc(
    request: JSONRPCRequest,
    _: str = Depends(verify_bearer_token),
) -> JSONRPCResponse:
    """
    Handle A2A JSON-RPC 2.0 requests.

    Supported methods:
    - message/send: Submit a new task or continue an existing one
    - tasks/get: Get task status and artifacts by ID
    - tasks/cancel: Cancel a running task

    Args:
        request: JSON-RPC 2.0 request
        _: Verified bearer token (authentication)

    Returns:
        JSON-RPC 2.0 response with result or error
    """
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
                    message=f"Method not found: {request.method}",
                ),
            )

    except ValueError as e:
        return JSONRPCResponse(
            id=request.id,
            error=JSONRPCError(code=-32602, message=str(e)),
        )
    except Exception as e:
        return JSONRPCResponse(
            id=request.id,
            error=JSONRPCError(code=-32000, message=str(e)),
        )
