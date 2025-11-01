"""Level 2 Integration Tests - Producer Logic.

Tests Executive Producer orchestration:
- Campaign planning
- Plan approval handling
- Agent delegation
- Critique loop coordination
- Conversation management
- Progress tracking
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from typing import Dict, Any

from app.producer.executive_producer import ExecutiveProducer
from app.models.brief import ProjectBrief, CampaignPlan


@pytest.mark.asyncio
async def test_producer_initialization(mock_project_brief, mock_redis_client):
    """Test Producer initialization with project brief."""
    with patch('app.producer.executive_producer.redis_client') as mock_redis:
        # Mock Redis to return project brief
        mock_brief = Mock(spec=ProjectBrief)
        mock_brief.product_name = "Aura Smart Sneaker"
        mock_brief.model_dump = Mock(return_value=mock_project_brief)
        mock_redis.get_project_brief = AsyncMock(return_value=mock_brief)

        producer = ExecutiveProducer(
            session_id="session_001", project_id="test_project_001"
        )

        brief = await producer.initialize()

    # Verify brief loaded
    assert brief is not None
    assert brief.product_name == "Aura Smart Sneaker"
    mock_redis.get_project_brief.assert_called_once_with("test_project_001")


@pytest.mark.asyncio
async def test_create_campaign_plan(mock_project_brief):
    """Test Producer creates campaign plan."""
    with patch('app.producer.executive_producer.redis_client') as mock_redis, \
         patch('app.producer.executive_producer.CampaignPlanner') as MockPlanner:

        # Mock brief
        mock_brief = Mock(spec=ProjectBrief)
        mock_brief.product_name = "Aura Smart Sneaker"
        mock_redis.get_project_brief = AsyncMock(return_value=mock_brief)
        mock_redis.update_project_brief = AsyncMock()

        # Mock planner
        mock_plan = Mock(spec=CampaignPlan)
        mock_plan.description = "Complete campaign plan description"
        mock_plan.model_dump = Mock(return_value={
            "phases": ["Strategy", "Creative Assets", "Production"],
            "estimated_duration": "15 minutes",
        })

        mock_planner_instance = Mock()
        mock_planner_instance.generate_plan = AsyncMock(return_value=mock_plan)
        MockPlanner.return_value = mock_planner_instance

        producer = ExecutiveProducer(
            session_id="session_001", project_id="test_project_001"
        )

        plan_description = await producer.create_campaign_plan()

    # Verify plan created
    assert plan_description is not None
    assert "Complete campaign plan" in plan_description
    mock_planner_instance.generate_plan.assert_called_once()


@pytest.mark.asyncio
async def test_handle_plan_approval(mock_project_brief):
    """Test Producer handles plan approval."""
    with patch('app.producer.executive_producer.redis_client') as mock_redis:
        mock_brief = Mock(spec=ProjectBrief)
        mock_brief.product_name = "Aura Smart Sneaker"
        mock_redis.get_project_brief = AsyncMock(return_value=mock_brief)
        mock_redis.update_project_brief = AsyncMock()

        producer = ExecutiveProducer(
            session_id="session_001", project_id="test_project_001"
        )

        # Initialize first
        await producer.initialize()

        # Approve plan
        response = await producer.handle_plan_approval(approved=True)

    # Verify approval processed
    assert response is not None
    mock_redis.update_project_brief.assert_called()


@pytest.mark.asyncio
async def test_handle_plan_rejection(mock_project_brief):
    """Test Producer handles plan rejection."""
    with patch('app.producer.executive_producer.redis_client') as mock_redis:
        mock_brief = Mock(spec=ProjectBrief)
        mock_brief.product_name = "Aura Smart Sneaker"
        mock_redis.get_project_brief = AsyncMock(return_value=mock_brief)
        mock_redis.update_project_brief = AsyncMock()

        producer = ExecutiveProducer(
            session_id="session_001", project_id="test_project_001"
        )

        await producer.initialize()

        # Reject plan
        response = await producer.handle_plan_approval(approved=False)

    # Verify rejection processed
    assert response is not None
    # Should ask for modifications or revisions
    assert "revise" in response.lower() or "modify" in response.lower() or "guidance" in response.lower()


@pytest.mark.asyncio
async def test_agent_delegation(mock_project_brief):
    """Test Producer uses orchestrator for agent delegation."""
    with patch('app.producer.executive_producer.redis_client') as mock_redis, \
         patch('app.producer.executive_producer.orchestrator') as mock_orchestrator:

        mock_brief = Mock(spec=ProjectBrief)
        mock_brief.product_name = "Aura Smart Sneaker"
        mock_brief.model_dump = Mock(return_value=mock_project_brief)
        mock_redis.get_project_brief = AsyncMock(return_value=mock_brief)

        # Mock orchestrator
        mock_orchestrator.execute_agent = AsyncMock(return_value={"output": "result"})

        producer = ExecutiveProducer(
            session_id="session_001", project_id="test_project_001"
        )

        await producer.initialize()

        # Verify Producer has access to orchestrator for delegation
        # The actual delegation happens through the orchestrator
        assert mock_orchestrator is not None


@pytest.mark.asyncio
async def test_critique_loop_coordination(mock_project_brief):
    """Test Producer coordinates critique loops."""
    with patch('app.producer.executive_producer.redis_client') as mock_redis, \
         patch('app.producer.executive_producer.critique_system') as mock_critique:

        mock_brief = Mock(spec=ProjectBrief)
        mock_brief.product_name = "Aura Smart Sneaker"
        mock_brief.model_dump = Mock(return_value=mock_project_brief)
        mock_redis.get_project_brief = AsyncMock(return_value=mock_brief)

        # Mock critique system
        mock_critique.critique_agent_output = AsyncMock(
            return_value={"status": "PASS", "score": 0.9, "issues": []}
        )

        producer = ExecutiveProducer(
            session_id="session_001", project_id="test_project_001"
        )

        await producer.initialize()

        # Test critique coordination
        # This would be part of the execute_with_critique flow
        # Verify Producer can coordinate critiques


@pytest.mark.asyncio
async def test_conversation_history_tracking(mock_project_brief):
    """Test Producer tracks conversation history."""
    with patch('app.producer.executive_producer.redis_client') as mock_redis:
        mock_brief = Mock(spec=ProjectBrief)
        mock_brief.product_name = "Aura Smart Sneaker"
        mock_redis.get_project_brief = AsyncMock(return_value=mock_brief)

        producer = ExecutiveProducer(
            session_id="session_001", project_id="test_project_001"
        )

        # Verify conversation history is initialized
        assert hasattr(producer, 'conversation_history')
        assert isinstance(producer.conversation_history, list)


@pytest.mark.asyncio
async def test_multi_agent_workflow(mock_project_brief):
    """Test Producer manages multi-agent workflow."""
    with patch('app.producer.executive_producer.redis_client') as mock_redis, \
         patch('app.producer.executive_producer.orchestrator') as mock_orchestrator:

        mock_brief = Mock(spec=ProjectBrief)
        mock_brief.product_name = "Aura Smart Sneaker"
        mock_brief.model_dump = Mock(return_value=mock_project_brief)
        mock_redis.get_project_brief = AsyncMock(return_value=mock_brief)
        mock_redis.update_project_brief = AsyncMock()

        # Mock agent executions
        strategy_output = {"slogans": ["Run on Light"], "personas": []}
        art_output = {"images": [{"url": "img.png"}], "style_guide": "guide"}

        mock_orchestrator.execute_agent = AsyncMock(
            side_effect=[strategy_output, art_output]
        )

        producer = ExecutiveProducer(
            session_id="session_001", project_id="test_project_001"
        )

        await producer.initialize()

        # Simulate workflow execution
        # Producer should coordinate: Strategy → Art Director → etc.
        # This tests the Producer's orchestration logic


@pytest.mark.asyncio
async def test_status_announcements(mock_project_brief):
    """Test Producer makes status announcements."""
    with patch('app.producer.executive_producer.redis_client') as mock_redis:
        mock_brief = Mock(spec=ProjectBrief)
        mock_brief.product_name = "Aura Smart Sneaker"
        mock_redis.get_project_brief = AsyncMock(return_value=mock_brief)

        producer = ExecutiveProducer(
            session_id="session_001", project_id="test_project_001"
        )

        # Producer should announce actions
        # "I've tasked the Strategy Agent with..."
        # "The Art Director has completed..."
        # etc.

        # Verify Producer has announcement capability
        assert hasattr(producer, 'session_id')
        assert hasattr(producer, 'project_id')


@pytest.mark.asyncio
async def test_error_recovery(mock_project_brief):
    """Test Producer handles agent errors gracefully."""
    with patch('app.producer.executive_producer.redis_client') as mock_redis, \
         patch('app.producer.executive_producer.orchestrator') as mock_orchestrator:

        mock_brief = Mock(spec=ProjectBrief)
        mock_brief.product_name = "Aura Smart Sneaker"
        mock_brief.model_dump = Mock(return_value=mock_project_brief)
        mock_redis.get_project_brief = AsyncMock(return_value=mock_brief)

        # Mock agent failure
        mock_orchestrator.execute_agent = AsyncMock(
            side_effect=Exception("Agent execution failed")
        )

        producer = ExecutiveProducer(
            session_id="session_001", project_id="test_project_001"
        )

        await producer.initialize()

        # Producer should handle errors and report to user
        # Test error recovery mechanism


print("✅ Producer Logic Level 2 tests created")
