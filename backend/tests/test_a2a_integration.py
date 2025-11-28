"""Tests for A2A Integration.

Tests the A2A client, RemoteA2AAgentAdapter, and AgentRegistry
with remote agent support.
"""

import asyncio
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.a2a import (
    AgentCard,
    AgentCapabilities,
    AgentProvider,
    AgentSkill,
    RemoteAgentConfig,
    Task,
    TaskState,
    TaskStatus,
    Artifact,
    FilePart,
)
from app.services.a2a_client import A2AClient, A2AError, A2AConnectionError
from app.services.circuit_breaker import CircuitBreaker, CircuitState
from app.agents.remote_a2a_adapter import RemoteA2AAgentAdapter


# ============ Fixtures ============


@pytest.fixture
def mock_agent_card():
    """Create a mock Agent Card."""
    return AgentCard(
        id="video_producer_a2a",
        name="Video Producer Agent",
        description="A2A-compliant video generation agent",
        protocolVersion="1.0",
        url="http://localhost:8001/a2a",
        provider=AgentProvider(name="AI Agency"),
        capabilities=AgentCapabilities(streaming=True, pushNotifications=False),
        skills=[
            AgentSkill(
                id="video_generation",
                name="Video Generation",
                description="Creates 15-second videos",
                inputModes=["text/plain"],
                outputModes=["video/mp4"],
            )
        ],
    )


@pytest.fixture
def mock_task():
    """Create a mock completed task."""
    return Task(
        id="task_abc123",
        contextId="ctx_xyz789",
        status=TaskStatus(state=TaskState.COMPLETED),
        artifacts=[
            Artifact(
                id="art_001",
                name="generated_video.mp4",
                mimeType="video/mp4",
                parts=[
                    FilePart(
                        type="file",
                        uri="https://storage.example.com/videos/sample.mp4",
                        mimeType="video/mp4",
                    )
                ],
            )
        ],
    )


# ============ A2AClient Tests ============


class TestA2AClient:
    """Tests for A2AClient."""

    @pytest.mark.asyncio
    async def test_fetch_agent_card(self, mock_agent_card):
        """Test fetching Agent Card."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_agent_card.model_dump()
            mock_response.raise_for_status = MagicMock()

            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.aclose = AsyncMock()
            mock_client_class.return_value = mock_instance

            async with A2AClient(api_key="test_key") as client:
                # Override the internal client
                client._client = mock_instance
                card = await client.fetch_agent_card(
                    "http://localhost:8001/.well-known/agent.json"
                )

                assert card.id == "video_producer_a2a"
                assert card.capabilities.streaming is True

    @pytest.mark.asyncio
    async def test_send_message(self, mock_task):
        """Test sending message via JSON-RPC."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "jsonrpc": "2.0",
                "id": "req_1",
                "result": mock_task.model_dump(),
            }
            mock_response.raise_for_status = MagicMock()

            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_instance.aclose = AsyncMock()
            mock_client_class.return_value = mock_instance

            async with A2AClient(api_key="test_key") as client:
                client._client = mock_instance
                result = await client.send_message(
                    "http://localhost:8001/a2a",
                    {
                        "message": {
                            "messageId": "msg_001",
                            "role": "user",
                            "parts": [{"type": "text", "text": "Create a video"}],
                        }
                    },
                )

                assert result.id == "task_abc123"
                assert result.status.state == TaskState.COMPLETED


# ============ CircuitBreaker Tests ============


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    @pytest.mark.asyncio
    async def test_initial_state_closed(self):
        """Test that circuit starts in closed state."""
        breaker = CircuitBreaker()
        assert await breaker.can_execute("agent_1") is True

    @pytest.mark.asyncio
    async def test_opens_after_failures(self):
        """Test that circuit opens after reaching failure threshold."""
        breaker = CircuitBreaker(failure_threshold=3)

        # Record 3 failures
        for _ in range(3):
            await breaker.record_failure("agent_1")

        # Circuit should now be open
        assert await breaker.can_execute("agent_1") is False

    @pytest.mark.asyncio
    async def test_success_resets_failures(self):
        """Test that success resets failure count."""
        breaker = CircuitBreaker(failure_threshold=3)

        # Record 2 failures
        await breaker.record_failure("agent_1")
        await breaker.record_failure("agent_1")

        # Record success
        await breaker.record_success("agent_1")

        # Record 2 more failures (should not open)
        await breaker.record_failure("agent_1")
        await breaker.record_failure("agent_1")

        assert await breaker.can_execute("agent_1") is True

    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self):
        """Test transition to half-open after recovery timeout."""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0)

        # Open the circuit
        await breaker.record_failure("agent_1")
        await breaker.record_failure("agent_1")

        # With recovery_timeout=0, it transitions immediately to half-open
        # So can_execute returns True (allowing one test call)
        # Check state first
        status = breaker.get_status("agent_1")
        # It's open until we call can_execute which triggers transition
        assert status["state"] == "open"

        # Wait a tiny bit for timing
        await asyncio.sleep(0.01)

        # Now can_execute triggers the half-open transition
        can_exec = await breaker.can_execute("agent_1")
        assert can_exec is True  # Allows one call in half-open

        status = breaker.get_status("agent_1")
        assert status["state"] == "half_open"

    @pytest.mark.asyncio
    async def test_manual_reset(self):
        """Test manual circuit reset."""
        breaker = CircuitBreaker(failure_threshold=2)

        # Open the circuit
        await breaker.record_failure("agent_1")
        await breaker.record_failure("agent_1")
        assert await breaker.can_execute("agent_1") is False

        # Reset
        await breaker.reset("agent_1")
        assert await breaker.can_execute("agent_1") is True


# ============ RemoteA2AAgentAdapter Tests ============


class TestRemoteA2AAgentAdapter:
    """Tests for RemoteA2AAgentAdapter."""

    @pytest.mark.asyncio
    async def test_adapter_creation(self):
        """Test adapter creation."""
        adapter = RemoteA2AAgentAdapter(
            agent_id="test_agent",
            agent_card_url="http://localhost:8001/.well-known/agent.json",
            api_key="test_key",
        )

        assert adapter.agent_id == "test_agent"
        assert adapter.agent_card_url == "http://localhost:8001/.well-known/agent.json"

    @pytest.mark.asyncio
    async def test_supports_streaming_detection(self, mock_agent_card):
        """Test streaming capability detection."""
        adapter = RemoteA2AAgentAdapter(
            agent_id="test_agent",
            agent_card_url="http://localhost:8001/.well-known/agent.json",
            api_key="test_key",
        )

        # Before loading card
        assert adapter._supports_streaming() is False

        # Set agent card
        adapter._agent_card = mock_agent_card
        assert adapter._supports_streaming() is True

    @pytest.mark.asyncio
    async def test_get_stream_endpoint(self, mock_agent_card):
        """Test stream endpoint generation."""
        adapter = RemoteA2AAgentAdapter(
            agent_id="test_agent",
            agent_card_url="http://localhost:8001/.well-known/agent.json",
            api_key="test_key",
        )
        adapter._agent_card = mock_agent_card

        endpoint = adapter._get_stream_endpoint()
        assert endpoint == "http://localhost:8001/a2a/stream"

    @pytest.mark.asyncio
    async def test_build_message(self):
        """Test message building from task."""
        adapter = RemoteA2AAgentAdapter(
            agent_id="test_agent",
            agent_card_url="http://localhost:8001/.well-known/agent.json",
            api_key="test_key",
        )

        task = {"description": "Create a video", "style": "neon"}
        context = {"brand": "Test Brand"}

        message = adapter._build_message(task, context)

        assert message["role"] == "user"
        assert len(message["parts"]) == 2
        assert message["parts"][0]["type"] == "text"
        assert message["parts"][1]["type"] == "data"


# ============ Integration Test (requires running video-agent) ============


@pytest.mark.integration
class TestA2AIntegration:
    """Integration tests that require the video-agent server running."""

    @pytest.mark.asyncio
    async def test_real_connection(self):
        """Test real connection to video-agent server."""
        # Skip if server not running
        import httpx

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get("http://localhost:8001/health")
                if response.status_code != 200:
                    pytest.skip("Video-agent server not running")
        except Exception:
            pytest.skip("Video-agent server not running")

        # Test with real server
        async with A2AClient(api_key="test_api_key_123") as a2a_client:
            card = await a2a_client.fetch_agent_card(
                "http://localhost:8001/.well-known/agent.json"
            )
            assert card.id == "video_producer_a2a"
            assert card.capabilities.streaming is True
