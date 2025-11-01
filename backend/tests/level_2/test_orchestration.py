"""Level 2 Integration Tests - Agent Orchestration.

Tests orchestrator coordinating multiple agents:
- Sequential agent execution
- Parallel agent execution
- Dependency management
- Context sharing
- Critique loop orchestration
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from typing import Dict, Any

from app.services.orchestration import AgentOrchestrator, AGENT_DEPENDENCIES


@pytest.mark.asyncio
async def test_execute_single_agent(mock_project_brief, mock_redis_client):
    """Test executing a single agent."""
    orchestrator = AgentOrchestrator()

    task = {
        "task_id": "test_001",
        "description": "Generate strategy",
        **mock_project_brief,
    }

    # Mock agent execution
    with patch('app.services.orchestration.agent_registry') as mock_registry, \
         patch('app.services.orchestration.redis_client') as mock_redis:

        mock_agent = Mock()
        mock_agent.agent_id = "strategy"
        mock_agent.execute = AsyncMock(return_value={"personas": [], "slogans": []})
        mock_registry.get_agent.return_value = mock_agent

        # Mock Redis client methods
        mock_redis.set_agent_status = AsyncMock()
        mock_redis.store_agent_result = AsyncMock()
        mock_redis.publish_event = AsyncMock()
        mock_redis.get_project_brief = AsyncMock(
            return_value=Mock(model_dump=Mock(return_value=mock_project_brief))
        )

        result = await orchestrator.execute_agent(
            agent_id="strategy",
            task=task,
            project_id="test_project_001",
        )

    # Verify agent was executed
    assert result is not None
    mock_agent.execute.assert_called_once()


@pytest.mark.asyncio
async def test_execute_agent_with_critique(mock_project_brief, mock_redis_client):
    """Test executing agent with critique loop."""
    orchestrator = AgentOrchestrator()

    task = {"task_id": "test_002", **mock_project_brief}

    # Mock agent with critique
    with patch('app.services.orchestration.agent_registry') as mock_registry, \
         patch('app.services.orchestration.redis_client') as mock_redis:

        mock_agent = Mock()
        mock_agent.agent_id = "video_producer"
        mock_agent.execute_with_critique = AsyncMock(
            return_value={
                "video": {"url": "gs://video.mp4", "revision_number": 1},
                "critique_notes": "Revised to show glowing sole",
            }
        )
        mock_registry.get_agent.return_value = mock_agent

        # Mock Redis
        mock_redis.set_agent_status = AsyncMock()
        mock_redis.store_agent_result = AsyncMock()
        mock_redis.publish_event = AsyncMock()
        mock_redis.get_project_brief = AsyncMock(
            return_value=Mock(model_dump=Mock(return_value=mock_project_brief))
        )

        result = await orchestrator.execute_agent(
            agent_id="video_producer",
            task=task,
            project_id="test_project_001",
            with_critique=True,
        )

    # Verify critique was executed
    assert result is not None
    assert "critique_notes" in result
    mock_agent.execute_with_critique.assert_called_once()


@pytest.mark.asyncio
async def test_parallel_agent_execution(mock_project_brief, mock_redis_client):
    """Test executing multiple agents in parallel."""
    orchestrator = AgentOrchestrator()

    # Mock multiple agents
    with patch('app.services.orchestration.agent_registry') as mock_registry, \
         patch('app.services.orchestration.redis_client') as mock_redis:

        # Create mock agents
        agents = {}
        for agent_id in ["art_director", "web_dev"]:
            mock_agent = Mock()
            mock_agent.agent_id = agent_id
            mock_agent.execute = AsyncMock(return_value={f"{agent_id}_output": "data"})
            agents[agent_id] = mock_agent

        mock_registry.get_agent.side_effect = lambda aid: agents.get(aid)

        # Mock Redis
        mock_redis.set_agent_status = AsyncMock()
        mock_redis.store_agent_result = AsyncMock()
        mock_redis.publish_event = AsyncMock()
        mock_redis.get_project_brief = AsyncMock(
            return_value=Mock(model_dump=Mock(return_value=mock_project_brief))
        )

        # Execute agents in parallel
        import asyncio

        results = await asyncio.gather(
            orchestrator.execute_agent(
                "art_director", {"task_id": "art_001"}, "test_project_001"
            ),
            orchestrator.execute_agent(
                "web_dev", {"task_id": "web_001"}, "test_project_001"
            ),
        )

    # Verify both agents executed
    assert len(results) == 2
    assert results[0] is not None
    assert results[1] is not None


@pytest.mark.asyncio
async def test_agent_dependency_chain(mock_project_brief, mock_redis_client):
    """Test sequential execution respecting dependencies."""
    orchestrator = AgentOrchestrator()

    # Verify dependency configuration
    assert AGENT_DEPENDENCIES["strategy"] == []
    assert "strategy" in AGENT_DEPENDENCIES["art_director"]
    assert "art_director" in AGENT_DEPENDENCIES["video_producer"]

    # Mock agents
    with patch('app.services.orchestration.agent_registry') as mock_registry, \
         patch('app.services.orchestration.redis_client') as mock_redis:

        # Strategy agent (no dependencies)
        strategy_agent = Mock()
        strategy_agent.agent_id = "strategy"
        strategy_agent.execute = AsyncMock(
            return_value={"slogans": ["Run on Light"], "personas": []}
        )

        # Art Director (depends on Strategy)
        art_agent = Mock()
        art_agent.agent_id = "art_director"
        art_agent.execute = AsyncMock(
            return_value={"images": [{"url": "img.png"}], "style_guide": "guide"}
        )

        # Video Producer (depends on Art Director)
        video_agent = Mock()
        video_agent.agent_id = "video_producer"
        video_agent.execute = AsyncMock(
            return_value={"video": {"url": "video.mp4", "duration_seconds": 8}}
        )

        agents = {
            "strategy": strategy_agent,
            "art_director": art_agent,
            "video_producer": video_agent,
        }
        mock_registry.get_agent.side_effect = lambda aid: agents.get(aid)

        # Mock Redis
        mock_redis.set_agent_status = AsyncMock()
        mock_redis.store_agent_result = AsyncMock()
        mock_redis.publish_event = AsyncMock()
        mock_redis.get_project_brief = AsyncMock(
            return_value=Mock(model_dump=Mock(return_value=mock_project_brief))
        )

        # Execute in correct order: Strategy → Art Director → Video Producer
        strategy_result = await orchestrator.execute_agent(
            "strategy", {"task_id": "s1"}, "test_project_001"
        )
        assert "slogans" in strategy_result

        art_result = await orchestrator.execute_agent(
            "art_director",
            {"task_id": "a1", "slogan": strategy_result["slogans"][0]},
            "test_project_001",
        )
        assert "images" in art_result

        video_result = await orchestrator.execute_agent(
            "video_producer",
            {"task_id": "v1", "image_url": art_result["images"][0]["url"]},
            "test_project_001",
        )
        assert "video" in video_result


@pytest.mark.asyncio
async def test_context_sharing_via_brief(mock_project_brief, mock_redis_client):
    """Test agents share context via project brief."""
    orchestrator = AgentOrchestrator()

    # Mock agent
    with patch('app.services.orchestration.agent_registry') as mock_registry, \
         patch('app.services.orchestration.redis_client') as mock_redis:

        mock_agent = Mock()
        mock_agent.agent_id = "strategy"
        mock_agent.execute = AsyncMock(return_value={"output": "data"})
        mock_registry.get_agent.return_value = mock_agent

        # Mock Redis to return brief
        mock_redis.set_agent_status = AsyncMock()
        mock_redis.store_agent_result = AsyncMock()
        mock_redis.publish_event = AsyncMock()
        mock_redis.get_project_brief = AsyncMock(
            return_value=Mock(model_dump=Mock(return_value=mock_project_brief))
        )

        await orchestrator.execute_agent(
            "strategy", {"task_id": "test"}, "test_project_001"
        )

        # Verify brief was fetched for context
        mock_redis.get_project_brief.assert_called_once_with("test_project_001")

        # Verify agent received context with brief
        call_args = mock_agent.execute.call_args
        assert call_args is not None
        _, kwargs = call_args
        context = kwargs.get("context", call_args[0][1] if len(call_args[0]) > 1 else {})
        assert "brief" in context


@pytest.mark.asyncio
async def test_agent_not_found_error():
    """Test error handling when agent doesn't exist."""
    orchestrator = AgentOrchestrator()

    with patch('app.services.orchestration.agent_registry') as mock_registry:
        mock_registry.get_agent.return_value = None

        with pytest.raises(ValueError, match="Agent not found"):
            await orchestrator.execute_agent(
                "nonexistent_agent", {"task_id": "test"}, "test_project_001"
            )


@pytest.mark.asyncio
async def test_announcement_callback(mock_project_brief, mock_redis_client):
    """Test announcement callback is called during execution."""
    orchestrator = AgentOrchestrator()

    # Mock announcement callback
    announcement_callback = AsyncMock()

    with patch('app.services.orchestration.agent_registry') as mock_registry, \
         patch('app.services.orchestration.redis_client') as mock_redis:

        mock_agent = Mock()
        mock_agent.agent_id = "strategy"
        mock_agent.execute = AsyncMock(return_value={"output": "data"})
        mock_registry.get_agent.return_value = mock_agent

        # Mock Redis
        mock_redis.set_agent_status = AsyncMock()
        mock_redis.store_agent_result = AsyncMock()
        mock_redis.publish_event = AsyncMock()
        mock_redis.get_project_brief = AsyncMock(
            return_value=Mock(model_dump=Mock(return_value=mock_project_brief))
        )

        await orchestrator.execute_agent(
            "strategy",
            {"task_id": "test"},
            "test_project_001",
            announcement_callback=announcement_callback,
        )

    # Verify announcement was made
    announcement_callback.assert_called()


print("✅ Agent Orchestration Level 2 tests created")
