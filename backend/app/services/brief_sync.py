"""Project Brief Sync - Real-time synchronization to frontend.

The Project Brief is a user-visible living document that updates in real-time.
This module manages WebSocket broadcasting of brief updates to the frontend.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Set

from fastapi import WebSocket

from app.models.brief import ProjectBrief
from app.services.redis_client import redis_client

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Manages WebSocket connections for real-time updates.

    Tracks all active WebSocket connections for each project
    and broadcasts updates to all subscribers.
    """

    def __init__(self):
        """Initialize WebSocket manager."""
        # Map of project_id -> set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, project_id: str, websocket: WebSocket) -> None:
        """
        Register new WebSocket connection.

        Args:
            project_id: Project identifier
            websocket: WebSocket connection
        """
        await websocket.accept()

        if project_id not in self.active_connections:
            self.active_connections[project_id] = set()

        self.active_connections[project_id].add(websocket)
        logger.info(
            f"WebSocket connected for project {project_id}. Total: {len(self.active_connections[project_id])}"
        )

    def disconnect(self, project_id: str, websocket: WebSocket) -> None:
        """
        Unregister WebSocket connection.

        Args:
            project_id: Project identifier
            websocket: WebSocket connection
        """
        if project_id in self.active_connections:
            self.active_connections[project_id].discard(websocket)

            if not self.active_connections[project_id]:
                del self.active_connections[project_id]

            logger.info(f"WebSocket disconnected for project {project_id}")

    async def broadcast(
        self, project_id: str, message: Dict[str, Any]
    ) -> None:
        """
        Broadcast message to all connections for a project.

        Args:
            project_id: Project identifier
            message: Message to broadcast
        """
        if project_id not in self.active_connections:
            logger.debug(f"No active connections for project {project_id}")
            return

        connections = self.active_connections[project_id].copy()
        disconnected = []

        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to WebSocket: {e}")
                disconnected.append(connection)

        # Remove disconnected connections
        for conn in disconnected:
            self.disconnect(project_id, conn)

        logger.info(
            f"Broadcasted to {len(connections) - len(disconnected)}/{len(connections)} connections"
        )


# Global WebSocket manager instance
websocket_manager = WebSocketManager()


class BriefSyncManager:
    """
    Manages real-time Project Brief synchronization.

    Features:
    - Brief update detection
    - Field-level change tracking
    - WebSocket broadcasting
    - Visual highlight animations for changed fields
    """

    async def update_and_sync(
        self, project_id: str, updates: Dict[str, Any]
    ) -> ProjectBrief:
        """
        Update project brief and broadcast changes.

        This is the key method for real-time UI updates.
        When the Producer updates the brief, the UI immediately reflects changes.

        Args:
            project_id: Project identifier
            updates: Dictionary of fields to update

        Returns:
            Updated project brief
        """
        logger.info(f"Updating and syncing brief for project {project_id}")
        logger.debug(f"Updates: {list(updates.keys())}")

        # Update brief in Redis
        brief = await redis_client.update_project_brief(project_id, updates)

        # Broadcast update to all connected clients
        await self._broadcast_brief_update(
            project_id, brief, changed_fields=list(updates.keys())
        )

        return brief

    async def _broadcast_brief_update(
        self, project_id: str, brief: ProjectBrief, changed_fields: List[str]
    ) -> None:
        """
        Broadcast brief update to WebSocket clients.

        Args:
            project_id: Project identifier
            brief: Updated project brief
            changed_fields: List of fields that changed
        """
        message = {
            "type": "brief_updated",
            "brief": brief.model_dump(mode="json"),
            "changed_fields": changed_fields,
            "version": brief.version,
            "timestamp": datetime.utcnow().isoformat(),
        }

        await websocket_manager.broadcast(project_id, message)

        # Also publish to Redis Pub/Sub for agent notifications
        await redis_client.publish_event(
            "brief_updated", {"project_id": project_id, "version": brief.version}
        )

    async def sync_asset_added(
        self, project_id: str, agent_id: str, asset: Dict[str, Any]
    ) -> None:
        """
        Broadcast asset completion event.

        Args:
            project_id: Project identifier
            agent_id: Agent that created the asset
            asset: Asset data
        """
        logger.info(f"Syncing asset from {agent_id} to project {project_id}")

        message = {
            "type": f"{agent_id}_complete",
            "agent_id": agent_id,
            "asset": asset,
            "timestamp": datetime.utcnow().isoformat(),
        }

        await websocket_manager.broadcast(project_id, message)

    async def sync_agent_status(
        self, project_id: str, agent_id: str, status: str
    ) -> None:
        """
        Broadcast agent status update.

        Args:
            project_id: Project identifier
            agent_id: Agent identifier
            status: Agent status (thinking, completed, etc.)
        """
        message = {
            "type": "agent_status",
            "agent_id": agent_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
        }

        await websocket_manager.broadcast(project_id, message)

    async def sync_producer_announcement(
        self, project_id: str, announcement: str, announcement_type: str = "info"
    ) -> None:
        """
        Broadcast Producer announcement.

        Args:
            project_id: Project identifier
            announcement: Announcement text
            announcement_type: Type of announcement (info, success, warning)
        """
        message = {
            "type": "producer_announcement",
            "text": announcement,
            "announcement_type": announcement_type,
            "timestamp": datetime.utcnow().isoformat(),
        }

        await websocket_manager.broadcast(project_id, message)


# Global brief sync manager instance
brief_sync_manager = BriefSyncManager()
