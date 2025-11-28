"""Tests for Agent Card endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_agent_card():
    """Test that Agent Card is returned correctly."""
    response = client.get("/.well-known/agent.json")
    assert response.status_code == 200

    card = response.json()
    assert card["id"] == "video_producer_a2a"
    assert card["name"] == "Video Producer Agent"
    assert card["protocolVersion"] == "1.0"
    assert "url" in card
    assert card["capabilities"]["streaming"] is True


def test_agent_card_has_skills():
    """Test that Agent Card includes video generation skill."""
    response = client.get("/.well-known/agent.json")
    card = response.json()

    assert len(card["skills"]) >= 1
    skill = card["skills"][0]
    assert skill["id"] == "video_generation"
    assert "video/mp4" in skill["outputModes"]


def test_agent_card_has_security():
    """Test that Agent Card declares security schemes."""
    response = client.get("/.well-known/agent.json")
    card = response.json()

    assert "securitySchemes" in card
    assert "bearer" in card["securitySchemes"]
    assert card["security"] == ["bearer"]
