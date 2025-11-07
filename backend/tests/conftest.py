"""Pytest configuration and shared fixtures for all tests.

This file provides common test fixtures and configuration
used across both unit and integration tests.
"""

import asyncio
import os
import sys
import pytest
from unittest.mock import MagicMock

# Add the project root directory to the Python path to resolve import errors.
# This ensures that the 'app' module and its sub-packages are discoverable
# by pytest when running tests from the 'backend/tests' directory.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Set test environment variables
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("LOG_LEVEL", "WARNING")


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for unit tests."""
    mock = MagicMock()
    mock.hset = MagicMock(return_value=None)
    mock.hgetall = MagicMock(return_value={})
    mock.set = MagicMock(return_value=None)
    mock.get = MagicMock(return_value=None)
    mock.publish = MagicMock(return_value=None)
    return mock


@pytest.fixture
def sample_project_brief():
    """Sample project brief for testing."""
    from datetime import datetime

    return {
        "project_id": "test_project_123",
        "session_id": "test_session_456",
        "product_name": "Aura Smart Sneaker",
        "product_category": "footwear",
        "theme": "futuristic urban athlete",
        "key_features": ["glowing sole", "smart tracking", "adaptive cushioning"],
        "brand_tone": "innovative",
        "target_market": "Urban athletes and tech-savvy fitness enthusiasts",
        "personas": [],
        "slogans": [],
        "selected_slogan": None,
        "hero_images": [],
        "selected_image": None,
        "campaign_plan": None,
        "plan_approved": False,
        "completed_assets": {},
        "version": 1,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "status": "planning",
    }


@pytest.fixture
def sample_strategy_task():
    """Sample task for Strategy Agent testing."""
    return {
        "task_id": "strategy_test_001",
        "description": "Generate personas and slogans",
        "product_name": "Aura Smart Sneaker",
        "product_category": "footwear",
        "theme": "Tokyo neon",
        "brand_tone": "futuristic, energetic, tech-forward",
        "target_market": "Urban athletes aged 18-35",
        "key_features": ["glowing sole", "smart tracking", "adaptive cushioning"],
        "sketch_url": "https://example.com/sketch.png",
    }


@pytest.fixture
def sample_art_task():
    """Sample task for Art Director Agent testing."""
    return {
        "task_id": "art_test_001",
        "description": "Generate hero images",
        "product_name": "Aura Smart Sneaker",
        "product_category": "footwear",
        "slogan": "Run on Light",
        "theme": "Tokyo neon",
        "brand_tone": "futuristic, energetic, tech-forward",
        "key_features": ["glowing sole", "smart tracking"],
    }


@pytest.fixture
def sample_video_task():
    """Sample task for Video Producer Agent testing."""
    return {
        "task_id": "video_test_001",
        "description": "Generate social media video",
        "product_name": "Aura Smart Sneaker",
        "product_category": "footwear",
        "theme": "Tokyo neon",
        "key_features": ["glowing sole", "smart tracking"],
        "image_url": "https://example.com/hero_image.png",
    }


@pytest.fixture
def sample_audio_task():
    """Sample task for Audio Team Agent testing."""
    return {
        "task_id": "audio_test_001",
        "description": "Generate audio assets",
        "product_name": "Aura Smart Sneaker",
        "product_category": "footwear",
        "theme": "Tokyo neon",
        "slogan": "Run on Light",
        "brand_tone": "futuristic, energetic",
    }


@pytest.fixture
def sample_web_task():
    """Sample task for Web Dev Agent testing."""
    return {
        "task_id": "web_test_001",
        "description": "Generate landing page",
        "product_name": "Aura Smart Sneaker",
        "product_category": "footwear",
        "slogan": "Run on Light",
        "theme": "Tokyo neon",
        "brand_tone": "futuristic",
        "key_features": ["glowing sole", "smart tracking"],
        "image_url": "https://example.com/hero_image.png",
    }


# Integration test configuration
def pytest_configure(config):
    """Configure pytest with custom settings."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test requiring real API access"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow (execution time > 10 seconds)"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to handle markers properly."""
    # Skip integration tests if credentials not available
    skip_integration = pytest.mark.skip(
        reason="GOOGLE_APPLICATION_CREDENTIALS not set - skipping integration tests"
    )

    for item in items:
        if "integration" in item.keywords:
            if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
                item.add_marker(skip_integration)
