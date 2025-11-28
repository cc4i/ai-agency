"""Tests for A2A JSON-RPC endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

AUTH_HEADER = {"Authorization": "Bearer test_api_key_123"}


def test_message_send_requires_auth():
    """Test that /a2a requires authentication."""
    response = client.post(
        "/a2a",
        json={
            "jsonrpc": "2.0",
            "id": "req_001",
            "method": "message/send",
            "params": {"message": {"messageId": "msg_001", "role": "user", "parts": []}},
        },
    )
    # HTTPBearer returns 401 or 403 when no auth header
    assert response.status_code in (401, 403)


def test_message_send_invalid_auth():
    """Test that invalid API key is rejected."""
    response = client.post(
        "/a2a",
        headers={"Authorization": "Bearer wrong_key"},
        json={
            "jsonrpc": "2.0",
            "id": "req_001",
            "method": "message/send",
            "params": {"message": {"messageId": "msg_001", "role": "user", "parts": []}},
        },
    )
    assert response.status_code == 401


def test_message_send_creates_task():
    """Test that message/send creates a task."""
    response = client.post(
        "/a2a",
        headers=AUTH_HEADER,
        json={
            "jsonrpc": "2.0",
            "id": "req_001",
            "method": "message/send",
            "params": {
                "message": {
                    "messageId": "msg_001",
                    "role": "user",
                    "parts": [{"type": "text", "text": "Create a video"}],
                }
            },
        },
    )
    assert response.status_code == 200

    result = response.json()
    assert result["jsonrpc"] == "2.0"
    assert result["id"] == "req_001"
    assert "result" in result
    assert result["result"]["status"]["state"] == "completed"
    assert len(result["result"]["artifacts"]) == 1


def test_tasks_get():
    """Test that tasks/get returns task status."""
    # First create a task
    create_response = client.post(
        "/a2a",
        headers=AUTH_HEADER,
        json={
            "jsonrpc": "2.0",
            "id": "req_create",
            "method": "message/send",
            "params": {
                "message": {
                    "messageId": "msg_001",
                    "role": "user",
                    "parts": [{"type": "text", "text": "Create a video"}],
                }
            },
        },
    )
    task_id = create_response.json()["result"]["id"]

    # Then get it
    get_response = client.post(
        "/a2a",
        headers=AUTH_HEADER,
        json={
            "jsonrpc": "2.0",
            "id": "req_get",
            "method": "tasks/get",
            "params": {"taskId": task_id},
        },
    )
    assert get_response.status_code == 200
    assert get_response.json()["result"]["id"] == task_id


def test_tasks_get_not_found():
    """Test that tasks/get returns error for unknown task."""
    response = client.post(
        "/a2a",
        headers=AUTH_HEADER,
        json={
            "jsonrpc": "2.0",
            "id": "req_001",
            "method": "tasks/get",
            "params": {"taskId": "nonexistent_task"},
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert "error" in result
    assert result["error"]["code"] == -32602


def test_method_not_found():
    """Test that unknown methods return error."""
    response = client.post(
        "/a2a",
        headers=AUTH_HEADER,
        json={
            "jsonrpc": "2.0",
            "id": "req_001",
            "method": "unknown/method",
            "params": {},
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert "error" in result
    assert result["error"]["code"] == -32601
