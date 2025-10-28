"""Event Bus - Redis Pub/Sub event system for agent coordination.

Implements event-driven architecture for proactive agent collaboration.
"""

import asyncio
import json
import logging
from typing import Any, Callable, Dict, List

from app.services.redis_client import redis_client

logger = logging.getLogger(__name__)


class EventBus:
    """
    Event bus using Redis Pub/Sub for real-time agent coordination.

    Features:
    - Event publishing to multiple subscribers
    - Async event listeners
    - Event filtering by type
    - Message queuing and buffering
    """

    def __init__(self):
        """Initialize event bus."""
        self.listeners: Dict[str, List[Callable]] = {}
        self.running = False

    async def publish(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Publish event to all subscribers.

        Args:
            event_type: Event type (e.g., "slogan_selected", "image_selected")
            data: Event payload
        """
        logger.info(f"Publishing event: {event_type}")
        logger.debug(f"Event data: {data}")

        await redis_client.publish_event(event_type, data)

    async def subscribe(
        self, event_types: List[str], callback: Callable[[str, Dict[str, Any]], None]
    ) -> None:
        """
        Subscribe to events.

        Args:
            event_types: List of event types to listen for
            callback: Async function to call when event received
        """
        logger.info(f"Subscribing to events: {event_types}")

        for event_type in event_types:
            if event_type not in self.listeners:
                self.listeners[event_type] = []
            self.listeners[event_type].append(callback)

    async def start_listening(self) -> None:
        """Start event listener loop."""
        if self.running:
            logger.warning("Event bus already running")
            return

        self.running = True
        logger.info("Event bus started")

        # Get all event types we're listening for
        event_types = list(self.listeners.keys())
        if not event_types:
            logger.warning("No event listeners registered")
            return

        # Subscribe to Redis Pub/Sub
        pubsub = await redis_client.subscribe_to_events(event_types)

        try:
            async for message in pubsub.listen():
                if not self.running:
                    break

                if message["type"] == "message":
                    channel = message["channel"]
                    # Extract event type from channel name (events:{event_type})
                    event_type = channel.split(":")[-1]

                    # Parse message data
                    try:
                        data = json.loads(message["data"])
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON in event: {message['data']}")
                        continue

                    # Call all listeners for this event type
                    listeners = self.listeners.get(event_type, [])
                    for callback in listeners:
                        try:
                            # Call callback asynchronously
                            if asyncio.iscoroutinefunction(callback):
                                await callback(event_type, data)
                            else:
                                callback(event_type, data)
                        except Exception as e:
                            logger.error(
                                f"Event listener error for {event_type}: {e}"
                            )

        except Exception as e:
            logger.error(f"Event bus error: {e}")
        finally:
            await pubsub.unsubscribe()
            self.running = False
            logger.info("Event bus stopped")

    async def stop_listening(self) -> None:
        """Stop event listener loop."""
        self.running = False
        logger.info("Stopping event bus...")


# Global event bus instance
event_bus = EventBus()


# Convenience functions for common events

async def publish_slogan_selected(project_id: str, slogan: str) -> None:
    """Publish slogan_selected event."""
    await event_bus.publish(
        "slogan_selected", {"project_id": project_id, "slogan": slogan}
    )


async def publish_image_selected(project_id: str, image: Dict[str, Any]) -> None:
    """Publish image_selected event."""
    await event_bus.publish(
        "image_selected", {"project_id": project_id, "image": image}
    )


async def publish_brief_updated(project_id: str, version: int) -> None:
    """Publish brief_updated event."""
    await event_bus.publish(
        "brief_updated", {"project_id": project_id, "version": version}
    )


async def publish_agent_completed(agent_id: str, project_id: str, task_id: str) -> None:
    """Publish agent_completed event."""
    await event_bus.publish(
        "agent_completed",
        {"agent_id": agent_id, "project_id": project_id, "task_id": task_id},
    )
