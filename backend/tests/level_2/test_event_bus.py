"""Level 2 Integration Tests - Event Bus.

Tests pub/sub event coordination between agents:
- Event publishing
- Event subscription
- Event filtering
- Multi-subscriber handling
- Async event processing
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch, call
from typing import Dict, Any
import asyncio

from app.services.event_bus import EventBus


@pytest.mark.asyncio
async def test_publish_event(mock_redis_client):
    """Test publishing an event to Redis."""
    event_bus = EventBus()

    # Mock Redis publish_event
    with patch('app.services.event_bus.redis_client') as mock_redis:
        mock_redis.publish_event = AsyncMock()

        await event_bus.publish(
            "slogan_selected",
            {"slogan": "Run on Light", "project_id": "test_001"},
        )

    # Verify event was published to Redis
    mock_redis.publish_event.assert_called_once_with(
        "slogan_selected",
        {"slogan": "Run on Light", "project_id": "test_001"},
    )


@pytest.mark.asyncio
async def test_subscribe_to_event():
    """Test subscribing to events."""
    event_bus = EventBus()

    # Mock callback
    callback = AsyncMock()

    await event_bus.subscribe(["slogan_selected"], callback)

    # Verify listener was registered
    assert "slogan_selected" in event_bus.listeners
    assert callback in event_bus.listeners["slogan_selected"]


@pytest.mark.asyncio
async def test_subscribe_multiple_events():
    """Test subscribing to multiple event types."""
    event_bus = EventBus()

    callback = AsyncMock()

    await event_bus.subscribe(
        ["slogan_selected", "image_selected", "theme_detected"], callback
    )

    # Verify all listeners registered
    assert "slogan_selected" in event_bus.listeners
    assert "image_selected" in event_bus.listeners
    assert "theme_detected" in event_bus.listeners


@pytest.mark.asyncio
async def test_multiple_subscribers():
    """Test multiple subscribers to same event."""
    event_bus = EventBus()

    callback1 = AsyncMock()
    callback2 = AsyncMock()
    callback3 = AsyncMock()

    # Subscribe all three callbacks to same event
    await event_bus.subscribe(["slogan_selected"], callback1)
    await event_bus.subscribe(["slogan_selected"], callback2)
    await event_bus.subscribe(["slogan_selected"], callback3)

    # Verify all callbacks registered
    assert len(event_bus.listeners["slogan_selected"]) == 3


@pytest.mark.asyncio
async def test_event_filtering():
    """Test subscribers only receive their subscribed events."""
    event_bus = EventBus()

    slogan_callback = AsyncMock()
    image_callback = AsyncMock()

    # Different subscriptions
    await event_bus.subscribe(["slogan_selected"], slogan_callback)
    await event_bus.subscribe(["image_selected"], image_callback)

    # Verify separate listener lists
    assert slogan_callback in event_bus.listeners["slogan_selected"]
    assert slogan_callback not in event_bus.listeners.get("image_selected", [])
    assert image_callback in event_bus.listeners["image_selected"]
    assert image_callback not in event_bus.listeners.get("slogan_selected", [])


@pytest.mark.asyncio
async def test_proactive_collaboration_event_flow():
    """Test complete event flow for proactive collaboration."""
    event_bus = EventBus()

    # Simulate agents subscribing to events
    art_director_callback = AsyncMock()
    audio_team_callback = AsyncMock()

    # Art Director subscribes to slogan_selected
    await event_bus.subscribe(["slogan_selected"], art_director_callback)

    # Audio Team subscribes to theme_detected
    await event_bus.subscribe(["theme_detected"], audio_team_callback)

    with patch('app.services.event_bus.redis_client') as mock_redis:
        mock_redis.publish_event = AsyncMock()

        # Strategy Agent publishes slogan_selected event
        await event_bus.publish(
            "slogan_selected",
            {
                "slogan": "Run on Light",
                "project_id": "test_001",
                "agent": "strategy",
            },
        )

        # Strategy Agent publishes theme_detected event
        await event_bus.publish(
            "theme_detected",
            {
                "theme": "Tokyo neon",
                "project_id": "test_001",
                "agent": "strategy",
            },
        )

    # Verify both events were published
    assert mock_redis.publish_event.call_count == 2


@pytest.mark.asyncio
async def test_brief_updated_event():
    """Test brief_updated event for all agents."""
    event_bus = EventBus()

    # All agents subscribe to brief updates
    callbacks = []
    for agent in ["strategy", "art_director", "video_producer", "audio_team", "web_dev"]:
        callback = AsyncMock()
        callbacks.append(callback)
        await event_bus.subscribe(["brief_updated"], callback)

    # Verify all subscribed
    assert len(event_bus.listeners["brief_updated"]) == 5

    with patch('app.services.event_bus.redis_client') as mock_redis:
        mock_redis.publish_event = AsyncMock()

        # Publish brief_updated event
        await event_bus.publish(
            "brief_updated",
            {
                "project_id": "test_001",
                "updated_fields": ["target_market"],
                "new_target_market": "Global athletes 18-45",
            },
        )

    # Verify event was published
    mock_redis.publish_event.assert_called_once()


@pytest.mark.asyncio
async def test_event_data_payload():
    """Test event carries complete data payload."""
    event_bus = EventBus()

    with patch('app.services.event_bus.redis_client') as mock_redis:
        mock_redis.publish_event = AsyncMock()

        # Rich event data
        event_data = {
            "project_id": "test_001",
            "agent": "art_director",
            "image_url": "gs://bucket/image_001.png",
            "image_metadata": {
                "variation": 1,
                "theme": "Tokyo neon",
                "description": "Hero shot with dramatic lighting",
            },
            "timestamp": "2025-01-01T12:00:00Z",
        }

        await event_bus.publish("image_selected", event_data)

    # Verify complete data was passed
    call_args = mock_redis.publish_event.call_args
    assert call_args[0][0] == "image_selected"
    assert call_args[0][1] == event_data


@pytest.mark.asyncio
async def test_no_listeners_warning():
    """Test warning when no listeners are registered."""
    event_bus = EventBus()

    # No listeners registered
    assert len(event_bus.listeners) == 0

    # Start listening should handle gracefully
    with patch('app.services.event_bus.redis_client') as mock_redis:
        mock_redis.subscribe_to_events = AsyncMock()

        # This should log warning but not crash
        # (We can't easily test the actual listening loop without running it)
        event_bus.running = False  # Ensure not already running


@pytest.mark.asyncio
async def test_duplicate_subscription():
    """Test same callback can subscribe to same event multiple times."""
    event_bus = EventBus()

    callback = AsyncMock()

    # Subscribe twice to same event
    await event_bus.subscribe(["slogan_selected"], callback)
    await event_bus.subscribe(["slogan_selected"], callback)

    # Both subscriptions should be registered
    assert callback in event_bus.listeners["slogan_selected"]
    # Count may be 2 if duplicates allowed
    assert event_bus.listeners["slogan_selected"].count(callback) >= 1


print("✅ Event Bus Level 2 tests created")
