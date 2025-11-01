"""Level 1 Component Tests - Strategy Agent.

Tests individual Strategy Agent functionality:
- Output format validation
- Persona generation (exactly 3)
- Slogan generation (exactly 5)
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, patch, Mock
import json

from app.agents.strategy import StrategyAgent
from app.models.assets import StrategyAgentOutput


@pytest.mark.asyncio
async def test_strategy_agent_output_format(sample_strategy_task):
    """Test that Strategy Agent returns correct output format."""
    agent = StrategyAgent()

    # gemini_vision_client.analyze_image() returns str
    mock_visual_analysis = "Tokyo neon aesthetic with blue and purple lighting, athletic shoe design"

    # gemini_pro_client.generate_content() returns str (JSON)
    # Note: Current implementation doesn't parse this, but mock it anyway
    mock_response = {
        "personas": [
            {
                "name": "Alex 'The Night Runner'",
                "age_range": "25-32",
                "description": "Urban professional",
                "pain_points": ["Visibility"],
                "motivations": ["Fitness"],
                "product_usage_context": "Night running"
            },
            {
                "name": "Maya 'Tech Explorer'",
                "age_range": "18-24",
                "description": "Early adopter",
                "pain_points": ["Boredom"],
                "motivations": ["Technology"],
                "product_usage_context": "Social fitness"
            },
            {
                "name": "Jordan 'Innovator'",
                "age_range": "28-35",
                "description": "Fitness enthusiast",
                "pain_points": ["Plateaus"],
                "motivations": ["Competition"],
                "product_usage_context": "Training"
            }
        ],
        "slogans": [
            "Step Into Tomorrow",
            "Light Up Your Run",
            "Run on Light",
            "Glow Forward",
            "Future at Your Feet"
        ],
        "market_analysis": "Strong demand",
        "visual_theme_extracted": "Tokyo neon",
        "category_insights": "Urban footwear market"
    }

    with patch('app.agents.strategy.gemini_vision_client') as mock_vision, \
         patch('app.agents.strategy.gemini_pro_client') as mock_gemini:
        # Mock vision analysis
        mock_vision.analyze_image = AsyncMock(return_value=mock_visual_analysis)
        # Mock Gemini Pro content generation (not currently used by agent)
        mock_gemini.generate_content = AsyncMock(return_value=json.dumps(mock_response))

        result = await agent.execute(sample_strategy_task, {})

    # Verify output structure
    assert isinstance(result, dict)
    assert "personas" in result
    assert "slogans" in result
    assert "market_analysis" in result

    # Verify Pydantic validation
    output = StrategyAgentOutput(**result)
    assert output is not None


@pytest.mark.asyncio
async def test_strategy_agent_exactly_three_personas(sample_strategy_task):
    """Test that Strategy Agent generates exactly 3 personas."""
    agent = StrategyAgent()

    mock_visual_analysis = "Product visual analysis"

    with patch('app.agents.strategy.gemini_vision_client') as mock_vision, \
         patch('app.agents.strategy.gemini_pro_client') as mock_gemini:
        mock_vision.analyze_image = AsyncMock(return_value=mock_visual_analysis)
        mock_gemini.generate_content = AsyncMock(return_value="Mock response")

        result = await agent.execute(sample_strategy_task, {})

    # Verify exactly 3 personas
    assert len(result["personas"]) == 3

    # Verify each persona has required fields
    for persona in result["personas"]:
        assert "name" in persona
        assert "age_range" in persona
        assert "description" in persona
        assert "pain_points" in persona
        assert "motivations" in persona
        assert "product_usage_context" in persona


@pytest.mark.asyncio
async def test_strategy_agent_exactly_five_slogans(sample_strategy_task):
    """Test that Strategy Agent generates exactly 5 slogans."""
    agent = StrategyAgent()

    mock_visual_analysis = "Product visual analysis"

    with patch('app.agents.strategy.gemini_vision_client') as mock_vision, \
         patch('app.agents.strategy.gemini_pro_client') as mock_gemini:
        mock_vision.analyze_image = AsyncMock(return_value=mock_visual_analysis)
        mock_gemini.generate_content = AsyncMock(return_value="Mock response")

        result = await agent.execute(sample_strategy_task, {})

    # Verify exactly 5 slogans
    assert len(result["slogans"]) == 5

    # Verify slogans are non-empty strings
    for slogan in result["slogans"]:
        assert isinstance(slogan, str)
        assert len(slogan) > 0


@pytest.mark.asyncio
async def test_strategy_agent_product_category_adaptation(sample_strategy_task):
    """Test that Strategy Agent adapts to different product categories."""
    agent = StrategyAgent()

    # Test with different product category
    beverage_task = {
        **sample_strategy_task,
        "product_name": "Ember Energy Drink",
        "product_category": "beverage",
        "theme": "volcanic energy",
        "brand_tone": "edgy, intense"
    }

    mock_visual_analysis = "Volcanic energy aesthetic"

    with patch('app.agents.strategy.gemini_vision_client') as mock_vision, \
         patch('app.agents.strategy.gemini_pro_client') as mock_gemini:
        mock_vision.analyze_image = AsyncMock(return_value=mock_visual_analysis)
        mock_gemini.generate_content = AsyncMock(return_value="Mock response")

        result = await agent.execute(beverage_task, {})

    # Verify category-specific insights
    assert "category_insights" in result
    assert len(result["personas"]) == 3
    assert len(result["slogans"]) == 5


@pytest.mark.asyncio
async def test_strategy_agent_error_handling():
    """Test Strategy Agent error handling."""
    agent = StrategyAgent()

    task = {
        "task_id": "error_test",
        "description": "Test error handling",
        "sketch_url": "https://example.com/sketch.png"
        # Missing required fields
    }

    with patch('app.agents.strategy.gemini_vision_client') as mock_vision:
        mock_vision.analyze_image = AsyncMock(side_effect=Exception("Vision API Error"))

        with pytest.raises(Exception) as exc_info:
            await agent.execute(task, {})

        assert "vision" in str(exc_info.value).lower() or "api" in str(exc_info.value).lower() or "error" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_strategy_agent_critique():
    """Test Strategy Agent critique functionality."""
    from app.models.assets import CritiqueResult

    agent = StrategyAgent()

    result = {
        "personas": [
            {"name": "P1", "age_range": "25-32", "description": "D1",
             "pain_points": ["p1"], "motivations": ["m1"], "product_usage_context": "c1"},
            {"name": "P2", "age_range": "18-24", "description": "D2",
             "pain_points": ["p2"], "motivations": ["m2"], "product_usage_context": "c2"},
            {"name": "P3", "age_range": "28-35", "description": "D3",
             "pain_points": ["p3"], "motivations": ["m3"], "product_usage_context": "c3"}
        ],
        "slogans": ["S1", "S2", "S3", "S4", "S5"],
        "market_analysis": "Good analysis",
        "visual_theme_extracted": "Tokyo neon aesthetic",
        "category_insights": "Footwear market insights"
    }

    brief = {
        "product_category": "footwear",
        "theme": "Tokyo neon"
    }

    critique = await agent.critique(result, brief)

    # Verify critique is a CritiqueResult object
    assert isinstance(critique, CritiqueResult)
    assert critique.status in ["PASS", "REVISE"]

    # For Strategy Agent, should typically pass if format is correct
    if critique.status == "PASS":
        assert critique.score > 0.7


print("✅ Strategy Agent Level 1 tests created")
