"""Redis client and data schema management.

Redis Data Schema:

Session Management:
- session:{session_id} -> Hash {user_id, created_at, last_active, status}
- session:{session_id}:conversation -> List [message_1, message_2, ...]

Project Brief:
- project:{project_id} -> Hash {name, status, created_at, updated_at}
- project:{project_id}:brief -> Hash {theme, slogan, selected_assets, ...}
- project:{project_id}:assets -> Sorted Set {score=timestamp, value=asset_id}

Agent State:
- agent:{agent_id}:status -> String {idle, working, completed, failed}
- agent:{agent_id}:tasks -> List [task_1, task_2, ...]
- agent:{agent_id}:result:{task_id} -> Hash {output, metadata, timestamp}

Event Streaming:
- events:{project_id} -> Stream {event_type, agent_id, data, timestamp}

Asset Storage:
- asset:{asset_id} -> Hash {type, url, metadata, created_at}
- asset:{asset_id}:versions -> Sorted Set {score=version, value=data}
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import redis.asyncio as redis

from app.config import settings
from app.models.brief import ConversationMessage, ProjectBrief, SessionState


class RedisClient:
    """Async Redis client for managing application state."""

    def __init__(self) -> None:
        """Initialize Redis client."""
        self.client: Optional[redis.Redis] = None

    async def connect(self) -> None:
        """Establish Redis connection."""
        self.client = redis.Redis.from_url(
            settings.redis_url, encoding="utf-8", decode_responses=True
        )

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self.client:
            await self.client.close()

    # Session Management

    async def create_session(self, session: SessionState) -> None:
        """Create a new session in Redis."""
        await self.client.hset(  # type: ignore
            f"session:{session.session_id}", mapping=session.model_dump(mode="json")
        )

    async def get_session(self, session_id: str) -> Optional[SessionState]:
        """Retrieve session from Redis."""
        data = await self.client.hgetall(f"session:{session_id}")  # type: ignore
        if not data:
            return None
        return SessionState(**data)

    async def update_session_activity(self, session_id: str) -> None:
        """Update session's last_active timestamp."""
        await self.client.hset(  # type: ignore
            f"session:{session_id}",
            "last_active",
            datetime.utcnow().isoformat(),
        )

    # Conversation History

    async def add_conversation_message(
        self, session_id: str, message: ConversationMessage
    ) -> None:
        """Add message to conversation history."""
        await self.client.lpush(  # type: ignore
            f"session:{session_id}:conversation", message.model_dump_json()
        )

    async def get_conversation_history(
        self, session_id: str, limit: int = 100
    ) -> List[ConversationMessage]:
        """Retrieve conversation history."""
        messages = await self.client.lrange(  # type: ignore
            f"session:{session_id}:conversation", 0, limit - 1
        )
        return [ConversationMessage(**json.loads(msg)) for msg in messages]

    # Project Brief Management

    async def save_project_brief(self, brief: ProjectBrief) -> None:
        """Save project brief to Redis."""
        await self.client.hset(  # type: ignore
            f"project:{brief.project_id}:brief", mapping=brief.model_dump(mode="json")
        )

    async def get_project_brief(self, project_id: str) -> Optional[ProjectBrief]:
        """Retrieve project brief from Redis."""
        data = await self.client.hgetall(f"project:{project_id}:brief")  # type: ignore
        if not data:
            return None
        return ProjectBrief(**data)

    async def update_project_brief(
        self, project_id: str, updates: Dict[str, Any]
    ) -> ProjectBrief:
        """Update project brief with new data and increment version."""
        brief = await self.get_project_brief(project_id)
        if not brief:
            raise ValueError(f"Project {project_id} not found")

        # Apply updates
        for key, value in updates.items():
            setattr(brief, key, value)

        brief.version += 1
        brief.updated_at = datetime.utcnow()

        # Save to Redis
        await self.save_project_brief(brief)

        return brief

    # Asset Management

    async def register_asset(
        self, project_id: str, asset_id: str, asset_data: Dict[str, Any]
    ) -> None:
        """Register an asset and link it to a project."""
        # Store asset data
        await self.client.hset(f"asset:{asset_id}", mapping=asset_data)  # type: ignore

        # Add to project's asset list with timestamp
        timestamp = datetime.utcnow().timestamp()
        await self.client.zadd(  # type: ignore
            f"project:{project_id}:assets", {asset_id: timestamp}
        )

    async def get_asset(self, asset_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve asset data."""
        return await self.client.hgetall(f"asset:{asset_id}")  # type: ignore

    async def get_project_assets(self, project_id: str) -> List[str]:
        """Get all asset IDs for a project, sorted by timestamp."""
        return await self.client.zrange(f"project:{project_id}:assets", 0, -1)  # type: ignore

    # Agent State Management

    async def set_agent_status(self, agent_id: str, status: str) -> None:
        """Set agent status."""
        await self.client.set(f"agent:{agent_id}:status", status)  # type: ignore

    async def get_agent_status(self, agent_id: str) -> Optional[str]:
        """Get agent status."""
        return await self.client.get(f"agent:{agent_id}:status")  # type: ignore

    async def store_agent_result(
        self, agent_id: str, task_id: str, result: Dict[str, Any]
    ) -> None:
        """Store agent execution result."""
        await self.client.hset(  # type: ignore
            f"agent:{agent_id}:result:{task_id}", mapping=result
        )

    async def get_agent_result(
        self, agent_id: str, task_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve agent execution result."""
        return await self.client.hgetall(f"agent:{agent_id}:result:{task_id}")  # type: ignore

    # Event Publishing (Pub/Sub)

    async def publish_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Publish event to Redis Pub/Sub."""
        await self.client.publish(  # type: ignore
            f"events:{event_type}", json.dumps(data)
        )

    async def subscribe_to_events(self, event_types: List[str]):
        """Subscribe to Redis Pub/Sub events."""
        pubsub = self.client.pubsub()  # type: ignore
        channels = [f"events:{event_type}" for event_type in event_types]
        await pubsub.subscribe(*channels)
        return pubsub


# Global Redis client instance
redis_client = RedisClient()
