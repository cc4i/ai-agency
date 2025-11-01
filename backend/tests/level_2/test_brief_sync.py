"""Level 2 Integration Tests - Brief Synchronization.

Tests real-time project brief updates via WebSocket:
- WebSocket connection management
- Brief update broadcasting
- Agent status updates
- Asset additions
- Multi-client synchronization
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from typing import Dict, Any
import json

from app.services.brief_sync import WebSocketManager, BriefSyncManager
from app.models.brief import ProjectBrief


@pytest.mark.asyncio
async def test_websocket_connect():
    """Test WebSocket connection registration."""
    ws_manager = WebSocketManager()

    mock_websocket = Mock()
    mock_websocket.accept = AsyncMock()

    await ws_manager.connect("test_project_001", mock_websocket)

    # Verify connection registered
    assert "test_project_001" in ws_manager.active_connections
    assert mock_websocket in ws_manager.active_connections["test_project_001"]
    mock_websocket.accept.assert_called_once()


@pytest.mark.asyncio
async def test_websocket_disconnect():
    """Test WebSocket disconnection."""
    ws_manager = WebSocketManager()

    mock_websocket = Mock()
    mock_websocket.accept = AsyncMock()

    # Connect then disconnect
    await ws_manager.connect("test_project_001", mock_websocket)
    ws_manager.disconnect("test_project_001", mock_websocket)

    # Verify connection removed
    assert "test_project_001" not in ws_manager.active_connections


@pytest.mark.asyncio
async def test_multiple_websocket_connections():
    """Test multiple WebSocket connections for same project."""
    ws_manager = WebSocketManager()

    # Create 3 mock WebSocket connections
    websockets = []
    for i in range(3):
        ws = Mock()
        ws.accept = AsyncMock()
        websockets.append(ws)
        await ws_manager.connect("test_project_001", ws)

    # Verify all registered
    assert len(ws_manager.active_connections["test_project_001"]) == 3


@pytest.mark.asyncio
async def test_broadcast_to_single_client():
    """Test broadcasting message to single client."""
    ws_manager = WebSocketManager()

    mock_websocket = Mock()
    mock_websocket.accept = AsyncMock()
    mock_websocket.send_json = AsyncMock()

    await ws_manager.connect("test_project_001", mock_websocket)

    # Broadcast message
    message = {"type": "brief_update", "data": {"status": "updated"}}
    await ws_manager.broadcast("test_project_001", message)

    # Verify message sent
    mock_websocket.send_json.assert_called_once_with(message)


@pytest.mark.asyncio
async def test_broadcast_to_multiple_clients():
    """Test broadcasting to all connected clients."""
    ws_manager = WebSocketManager()

    # Connect 3 clients
    websockets = []
    for i in range(3):
        ws = Mock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        websockets.append(ws)
        await ws_manager.connect("test_project_001", ws)

    # Broadcast message
    message = {"type": "agent_status", "agent": "strategy", "status": "working"}
    await ws_manager.broadcast("test_project_001", message)

    # Verify all clients received message
    for ws in websockets:
        ws.send_json.assert_called_once_with(message)


@pytest.mark.asyncio
async def test_broadcast_no_active_connections():
    """Test broadcast gracefully handles no connections."""
    ws_manager = WebSocketManager()

    # No connections for this project
    message = {"type": "test"}

    # Should not raise error
    await ws_manager.broadcast("nonexistent_project", message)


@pytest.mark.asyncio
async def test_brief_sync_agent_status_update(mock_project_brief, mock_redis_client):
    """Test syncing agent status updates."""
    brief_sync = BriefSyncManager()

    # Mock global WebSocket manager
    with patch('app.services.brief_sync.websocket_manager') as mock_ws_manager:
        mock_ws_manager.broadcast = AsyncMock()

        # Update agent status
        await brief_sync.sync_agent_status("test_project_001", "strategy", "working")

    # Verify broadcast was called
    mock_ws_manager.broadcast.assert_called_once()
    call_args = mock_ws_manager.broadcast.call_args
    assert call_args[0][0] == "test_project_001"
    message = call_args[0][1]
    assert message["type"] == "agent_status"
    assert message["agent_id"] == "strategy"
    assert message["status"] == "working"


@pytest.mark.asyncio
async def test_brief_sync_asset_addition(mock_project_brief):
    """Test syncing when asset is added."""
    brief_sync = BriefSyncManager()

    # Mock global WebSocket manager
    with patch('app.services.brief_sync.websocket_manager') as mock_ws_manager:
        mock_ws_manager.broadcast = AsyncMock()

        # Add asset
        asset = {
            "asset_id": "img_001",
            "type": "image",
            "url": "gs://bucket/image.png",
        }

        await brief_sync.sync_asset_added("test_project_001", "art_director", asset)

    # Verify broadcast was called
    mock_ws_manager.broadcast.assert_called_once()
    call_args = mock_ws_manager.broadcast.call_args
    assert call_args[0][0] == "test_project_001"
    message = call_args[0][1]
    assert message["type"] == "art_director_complete"
    assert message["agent_id"] == "art_director"
    assert message["asset"] == asset


@pytest.mark.asyncio
async def test_brief_sync_complete_workflow(mock_project_brief):
    """Test complete brief sync workflow with multiple updates."""
    brief_sync = BriefSyncManager()

    # Mock global WebSocket manager
    with patch('app.services.brief_sync.websocket_manager') as mock_ws_manager:
        mock_ws_manager.broadcast = AsyncMock()

        # Simulate workflow: Strategy → Art Director → Asset added
        await brief_sync.sync_agent_status("test_project_001", "strategy", "working")
        await brief_sync.sync_agent_status("test_project_001", "strategy", "completed")
        await brief_sync.sync_agent_status("test_project_001", "art_director", "working")

        asset = {"asset_id": "img_001", "type": "image", "url": "gs://image.png"}
        await brief_sync.sync_asset_added("test_project_001", "art_director", asset)

        await brief_sync.sync_agent_status("test_project_001", "art_director", "completed")

    # Verify multiple broadcasts (5 total)
    assert mock_ws_manager.broadcast.call_count == 5


@pytest.mark.asyncio
async def test_brief_sync_message_format():
    """Test brief sync message format."""
    brief_sync = BriefSyncManager()

    broadcast_messages = []

    # Capture broadcast messages
    async def capture_broadcast(project_id, message):
        broadcast_messages.append(message)

    # Mock global WebSocket manager
    with patch('app.services.brief_sync.websocket_manager') as mock_ws_manager:
        mock_ws_manager.broadcast = capture_broadcast

        await brief_sync.sync_agent_status("test_001", "strategy", "working")

    # Verify message format
    assert len(broadcast_messages) == 1
    message = broadcast_messages[0]
    assert "type" in message
    assert message["type"] == "agent_status"
    assert message["agent_id"] == "strategy"
    assert message["status"] == "working"
    assert "timestamp" in message


@pytest.mark.asyncio
async def test_isolated_project_broadcasts():
    """Test broadcasts are isolated per project."""
    ws_manager = WebSocketManager()

    # Create connections for two different projects
    ws_project1 = Mock()
    ws_project1.accept = AsyncMock()
    ws_project1.send_json = AsyncMock()

    ws_project2 = Mock()
    ws_project2.accept = AsyncMock()
    ws_project2.send_json = AsyncMock()

    await ws_manager.connect("project_001", ws_project1)
    await ws_manager.connect("project_002", ws_project2)

    # Broadcast to project_001 only
    await ws_manager.broadcast("project_001", {"message": "test"})

    # Verify only project_001 client received message
    ws_project1.send_json.assert_called_once()
    ws_project2.send_json.assert_not_called()


print("✅ Brief Synchronization Level 2 tests created")
