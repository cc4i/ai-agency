"""Unit tests for Conversation Manager."""

import pytest

from app.services.conversation_manager import ConversationManager, ConversationState


@pytest.fixture
def conversation_manager():
    """Create Conversation Manager instance."""
    return ConversationManager(session_id="test_session", project_id="test_project")


def test_conversation_manager_initialization(conversation_manager):
    """Test Conversation Manager initialization."""
    assert conversation_manager.session_id == "test_session"
    assert conversation_manager.project_id == "test_project"
    assert conversation_manager.current_state == ConversationState.WELCOME
    assert len(conversation_manager.conversation_history) == 0


def test_set_state(conversation_manager):
    """Test state transitions."""
    conversation_manager.set_state(ConversationState.PLANNING)

    assert conversation_manager.current_state == ConversationState.PLANNING


@pytest.mark.asyncio
async def test_recognize_intent_plan_approval(conversation_manager):
    """Test intent recognition for plan approval."""
    conversation_manager.set_state(ConversationState.PLAN_APPROVAL)

    # Test approval
    intent = await conversation_manager.recognize_intent("Yes, go ahead")
    assert intent["type"] == "plan_approved"
    assert intent["approved"] is True

    # Test rejection
    intent = await conversation_manager.recognize_intent("No, not yet")
    assert intent["type"] == "plan_approved"
    assert intent["approved"] is False


@pytest.mark.asyncio
async def test_recognize_intent_slogan_selection(conversation_manager):
    """Test intent recognition for slogan selection."""
    conversation_manager.set_state(ConversationState.SLOGAN_SELECTION)

    # Number
    intent = await conversation_manager.recognize_intent("I like slogan 3")
    assert intent["type"] == "slogan_selected"
    assert intent["number"] == 3

    # Ordinal
    intent = await conversation_manager.recognize_intent("The third one")
    assert intent["type"] == "slogan_selected"
    assert intent["number"] == 3


@pytest.mark.asyncio
async def test_recognize_intent_image_selection(conversation_manager):
    """Test intent recognition for image selection."""
    conversation_manager.set_state(ConversationState.IMAGE_SELECTION)

    # Position
    intent = await conversation_manager.recognize_intent("top right")
    assert intent["type"] == "image_selected"
    assert intent["number"] == 2

    # Number
    intent = await conversation_manager.recognize_intent("image 4")
    assert intent["type"] == "image_selected"
    assert intent["number"] == 4


def test_get_expected_response(conversation_manager):
    """Test expected response generation."""
    conversation_manager.set_state(ConversationState.WELCOME)
    response = conversation_manager.get_expected_response()

    assert "Executive Producer" in response or "introduce" in response.lower()

    conversation_manager.set_state(ConversationState.SLOGAN_SELECTION)
    response = conversation_manager.get_expected_response()

    assert "slogan" in response.lower()
