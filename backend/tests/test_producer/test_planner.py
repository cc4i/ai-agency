"""Unit tests for Campaign Planner."""

import pytest

from app.models.brief import ProjectBrief
from app.producer.planner import CampaignPlanner


@pytest.fixture
def sample_brief():
    """Create sample project brief."""
    from datetime import datetime

    return ProjectBrief(
        project_id="test_project",
        session_id="test_session",
        product_name="Test Product",
        product_category="electronics",
        theme="futuristic",
        key_features=["smart", "connected", "innovative"],
        brand_tone="professional",
        target_market="tech enthusiasts",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.mark.asyncio
async def test_generate_plan(sample_brief):
    """Test campaign plan generation."""
    planner = CampaignPlanner()

    plan = await planner.generate_plan(sample_brief)

    # Verify plan structure
    assert plan.phases
    assert len(plan.phases) == 5
    assert plan.approval_status == "pending"
    assert plan.description

    # Verify phase sequence
    assert plan.phases[0].phase_number == 1
    assert "Strategy Agent" in plan.phases[0].agent
    assert len(plan.phases[0].dependencies) == 0  # First phase has no dependencies

    assert plan.phases[1].phase_number == 2
    assert "Art Director" in plan.phases[1].agent
    assert 1 in plan.phases[1].dependencies  # Depends on Strategy


def test_format_plan_for_display(sample_brief):
    """Test plan formatting."""
    import asyncio

    planner = CampaignPlanner()
    plan = asyncio.run(planner.generate_plan(sample_brief))

    formatted = planner.format_plan_for_display(plan)

    assert isinstance(formatted, str)
    assert "Phase 1" in formatted
    assert "Phase 5" in formatted
    assert "Strategy Agent" in formatted


def test_default_plan_description(sample_brief):
    """Test default plan description generation."""
    planner = CampaignPlanner()

    description = planner._get_default_plan_description(sample_brief)

    assert sample_brief.product_name in description
    assert sample_brief.theme in description
    assert sample_brief.brand_tone in description
    assert "Strategy Agent" in description
    assert "Art Director" in description
    assert "Video Producer" in description
    assert "Audio Team" in description
    assert "Web Dev Agent" in description
