"""Unit tests for Agent Registry."""

import pytest

from app.services.agent_registry import AgentRegistry, agent_registry


def test_agent_registry_initialization():
    """Test agent registry initialization."""
    registry = AgentRegistry()

    # Should have all 5 agents
    agents = registry.list_agents()
    assert len(agents) == 5

    expected_agents = [
        "strategy",
        "art_director",
        "video_producer",
        "audio_team",
        "web_dev",
    ]
    for agent_id in expected_agents:
        assert agent_id in agents


def test_get_agent():
    """Test getting agent by ID."""
    agent = agent_registry.get_agent("strategy")

    assert agent is not None
    assert agent.agent_id == "strategy"


def test_get_agent_not_found():
    """Test getting non-existent agent."""
    agent = agent_registry.get_agent("nonexistent")

    assert agent is None


def test_list_agents():
    """Test listing all agents."""
    agents = agent_registry.list_agents()

    assert isinstance(agents, list)
    assert len(agents) == 5
    assert "strategy" in agents


def test_get_agent_info():
    """Test getting agent metadata."""
    info = agent_registry.get_agent_info("strategy")

    assert info is not None
    assert info["agent_id"] == "strategy"
    assert "class_name" in info
    assert "max_revisions" in info


def test_get_agent_info_not_found():
    """Test getting info for non-existent agent."""
    info = agent_registry.get_agent_info("nonexistent")

    assert info is None


def test_global_registry():
    """Test global agent registry instance."""
    assert agent_registry is not None
    assert len(agent_registry.list_agents()) == 5
