"""Unit tests for Strategy Agent."""

import pytest

from app.agents.strategy import StrategyAgent
from app.models.assets import CritiqueResult, StrategyAgentOutput


@pytest.fixture
def strategy_agent():
    """Create Strategy Agent instance."""
    return StrategyAgent()


@pytest.fixture
def sample_task():
    """Sample task for Strategy Agent."""
    return {
        "product_name": "Test Product",
        "product_category": "electronics",
        "theme": "futuristic",
        "brand_tone": "professional",
        "target_market": "tech enthusiasts",
        "key_features": ["smart", "connected", "innovative"],
        "sketch_url": "gs://test/sketch.png",
    }


@pytest.fixture
def sample_context():
    """Sample context."""
    return {"project_id": "test_project"}


@pytest.mark.asyncio
async def test_strategy_agent_execute(strategy_agent, sample_task, sample_context):
    """Test Strategy Agent execution."""
    result = await strategy_agent.execute(sample_task, sample_context)

    # Verify result structure
    assert "personas" in result
    assert "slogans" in result
    assert "market_analysis" in result

    # Verify counts
    output = StrategyAgentOutput(**result)
    assert len(output.personas) == 3
    assert len(output.slogans) == 5


@pytest.mark.asyncio
async def test_strategy_agent_critique_valid(strategy_agent, sample_task):
    """Test critique with valid output."""
    # Create valid output
    result = await strategy_agent.execute(sample_task, {})

    # Critique should pass
    brief = {
        "product_category": "electronics",
        "brand_tone": "professional",
    }
    critique = await strategy_agent.critique(result, brief)

    assert critique.status == "PASS"
    assert critique.score == 1.0


@pytest.mark.asyncio
async def test_strategy_agent_critique_invalid():
    """Test critique with invalid output."""
    agent = StrategyAgent()

    # Invalid output - wrong number of personas
    invalid_result = {
        "personas": [],  # Should have 3
        "slogans": ["test"] * 5,
        "market_analysis": "test",
        "visual_theme_extracted": "test",
        "category_insights": "test",
    }

    brief = {"product_category": "electronics", "brand_tone": "professional"}
    critique = await agent.critique(invalid_result, brief)

    assert critique.status == "REVISE"
    assert len(critique.issues) > 0


def test_strategy_agent_initialization():
    """Test Strategy Agent initialization."""
    agent = StrategyAgent()

    assert agent.agent_id == "strategy"
    assert agent.max_revisions == 2
