"""Pytest configuration and shared fixtures for all tests.

This file provides common test fixtures and configuration
used across both unit and integration tests.
"""

import asyncio
import os
import pytest
from unittest.mock import MagicMock

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
