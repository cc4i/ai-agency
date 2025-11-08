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


from unittest.mock import AsyncMock, patch
import json

@pytest.mark.asyncio
async def test_strategy_agent_execute(strategy_agent, sample_task, sample_context):
    """Test Strategy Agent execution."""
    mock_response = {
        "personas": [
            {"name": "p1", "age_range": "20-30", "description": "d1", "pain_points": [], "motivations": [], "product_usage_context": ""},
            {"name": "p2", "age_range": "30-40", "description": "d2", "pain_points": [], "motivations": [], "product_usage_context": ""},
            {"name": "p3", "age_range": "40-50", "description": "d3", "pain_points": [], "motivations": [], "product_usage_context": ""},
        ],
        "slogans": ["s1", "s2", "s3", "s4", "s5"],
        "market_analysis": "ma",
        "visual_theme_extracted": "vte",
        "category_insights": "ci",
    }
    with patch('app.agents.strategy.gemini_vision_client') as mock_vision, \
         patch('app.agents.strategy.gemini_pro_client') as mock_gemini:
        mock_vision.analyze_image = AsyncMock(return_value="visual analysis")
        mock_gemini.generate_content = AsyncMock(return_value=json.dumps(mock_response))
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
    mock_response = {
        "personas": [
            {"name": "p1", "age_range": "20-30", "description": "d1", "pain_points": [], "motivations": [], "product_usage_context": "electronics"},
            {"name": "p2", "age_range": "30-40", "description": "d2", "pain_points": [], "motivations": [], "product_usage_context": "electronics"},
            {"name": "p3", "age_range": "40-50", "description": "d3", "pain_points": [], "motivations": [], "product_usage_context": "electronics"},
        ],
        "slogans": ["s1", "s2", "s3", "s4", "s5"],
        "market_analysis": "ma",
        "visual_theme_extracted": "vte",
        "category_insights": "ci",
    }
    with patch('app.agents.strategy.gemini_vision_client') as mock_vision, \
         patch('app.agents.strategy.gemini_pro_client') as mock_gemini:
        mock_vision.analyze_image = AsyncMock(return_value="visual analysis")
        mock_gemini.generate_content = AsyncMock(return_value=json.dumps(mock_response))
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
async def test_strategy_agent_critique_invalid(strategy_agent):
    """Test critique with invalid output."""
    # Invalid output - product category not mentioned in personas
    invalid_result = {
        "personas": [
            {"name": "p1", "age_range": "20-30", "description": "d1", "pain_points": [], "motivations": [], "product_usage_context": ""},
            {"name": "p2", "age_range": "30-40", "description": "d2", "pain_points": [], "motivations": [], "product_usage_context": ""},
            {"name": "p3", "age_range": "40-50", "description": "d3", "pain_points": [], "motivations": [], "product_usage_context": ""},
        ],
        "slogans": ["test"] * 5,
        "market_analysis": "test",
        "visual_theme_extracted": "test",
        "category_insights": "test",
    }

    brief = {"product_category": "electronics", "brand_tone": "professional"}
    critique = await strategy_agent.critique(invalid_result, brief)

    assert critique.status == "REVISE"
    assert len(critique.issues) == 1
    assert "Personas should reference electronics category" in critique.issues


def test_strategy_agent_initialization():
    """Test Strategy Agent initialization."""
    agent = StrategyAgent()

    assert agent.agent_id == "strategy"
    assert agent.max_revisions == 2
