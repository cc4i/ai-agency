"""Level 2 Integration Test Fixtures."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any


@pytest.fixture
def mock_project_brief() -> Dict[str, Any]:
    """Sample project brief for integration tests."""
    return {
        "project_id": "test_project_001",
        "product_name": "Aura Smart Sneaker",
        "product_category": "footwear",
        "theme": "Tokyo neon",
        "brand_tone": "futuristic, energetic, tech-forward",
        "target_market": "Urban athletes aged 18-35",
        "key_features": ["glowing sole", "smart tracking", "adaptive cushioning"],
        "sketch_url": "gs://ai-agency-demo/aura_sketch.png",
        "status": "in_progress",
        "agents": {
            "strategy": {"status": "pending"},
            "art_director": {"status": "pending"},
            "video_producer": {"status": "pending"},
            "audio_team": {"status": "pending"},
            "web_dev": {"status": "pending"},
        },
        "assets": [],
    }


@pytest.fixture
def mock_strategy_output() -> Dict[str, Any]:
    """Sample Strategy Agent output."""
    return {
        "personas": [
            {
                "name": "Alex 'Night Runner'",
                "age_range": "25-32",
                "description": "Urban professional",
                "pain_points": ["visibility", "safety"],
                "motivations": ["fitness", "technology"],
                "product_usage_context": "Night running in cities",
            },
            {
                "name": "Maya 'Tech Explorer'",
                "age_range": "18-24",
                "description": "Early adopter",
                "pain_points": ["boredom", "sameness"],
                "motivations": ["innovation", "social status"],
                "product_usage_context": "Social fitness events",
            },
            {
                "name": "Jordan 'Competitor'",
                "age_range": "28-35",
                "description": "Performance athlete",
                "pain_points": ["tracking", "optimization"],
                "motivations": ["competition", "data"],
                "product_usage_context": "Training and races",
            },
        ],
        "slogans": [
            "Run on Light",
            "Light Up Your Run",
            "Step Into Tomorrow",
            "Glow Forward",
            "Future at Your Feet",
        ],
        "market_analysis": "Strong demand in urban athletic market",
        "visual_theme_extracted": "Tokyo neon aesthetic with blue/purple lighting",
        "category_insights": "Footwear market values innovation and technology",
    }


@pytest.fixture
def mock_art_director_output() -> Dict[str, Any]:
    """Sample Art Director output."""
    return {
        "images": [
            {
                "asset_id": "img_001",
                "url": "data:image/png;base64,abc123",
                "description": "Hero shot with dramatic lighting",
                "generation_params": {"variation": 1},
            },
            {
                "asset_id": "img_002",
                "url": "data:image/png;base64,def456",
                "description": "Lifestyle context shot",
                "generation_params": {"variation": 2},
            },
            {
                "asset_id": "img_003",
                "url": "data:image/png;base64,ghi789",
                "description": "Close-up detail shot",
                "generation_params": {"variation": 3},
            },
            {
                "asset_id": "img_004",
                "url": "data:image/png;base64,jkl012",
                "description": "Environmental action shot",
                "generation_params": {"variation": 4},
            },
        ],
        "style_guide": "Tokyo neon style guide with futuristic aesthetic",
    }


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing."""
    with patch('app.services.redis_client.redis_client') as mock_redis:
        # Mock Redis methods
        mock_redis.get = Mock(return_value=None)
        mock_redis.set = Mock(return_value=True)
        mock_redis.publish = Mock(return_value=1)
        mock_redis.hset = Mock(return_value=1)
        mock_redis.hgetall = Mock(return_value={})
        mock_redis.lpush = Mock(return_value=1)
        mock_redis.lrange = Mock(return_value=[])
        yield mock_redis


@pytest.fixture
def mock_event_bus():
    """Mock Event Bus for testing."""
    with patch('app.services.event_bus.event_bus') as mock_bus:
        mock_bus.publish = AsyncMock()
        mock_bus.subscribe = AsyncMock()
        yield mock_bus
