"""Conversation Manager - Manages conversation state and flow.

Handles:
- Conversation history persistence
- Turn-taking logic
- User intent recognition
- Context maintenance
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from app.models.brief import ConversationMessage
from app.services.redis_client import redis_client

logger = logging.getLogger(__name__)


class ConversationState(str, Enum):
    """Conversation flow states."""

    WELCOME = "welcome"
    PLANNING = "planning"
    PLAN_APPROVAL = "plan_approval"
    STRATEGY_REVIEW = "strategy_review"
    SLOGAN_SELECTION = "slogan_selection"
    ART_REVIEW = "art_review"
    IMAGE_SELECTION = "image_selection"
    FINAL_PRODUCTION = "final_production"
    COMPLETION = "completion"


class ConversationManager:
    """
    Manages conversation state and user interactions.

    Tracks where the user is in the campaign workflow and
    what actions are expected next.
    """

    def __init__(self, session_id: str, project_id: str):
        """
        Initialize conversation manager.

        Args:
            session_id: Session identifier
            project_id: Project identifier
        """
        self.session_id = session_id
        self.project_id = project_id
        self.current_state = ConversationState.WELCOME
        self.conversation_history: List[ConversationMessage] = []

    async def initialize(self) -> None:
        """Load conversation history from Redis."""
        self.conversation_history = await redis_client.get_conversation_history(
            self.session_id, limit=100
        )
        logger.info(
            f"Conversation initialized with {len(self.conversation_history)} messages"
        )

    async def add_message(
        self, role: str, text: str, is_partial: bool = False
    ) -> None:
        """
        Add message to conversation history.

        Args:
            role: Message role (user or assistant)
            text: Message text
            is_partial: Whether this is a partial (streaming) message
        """
        message = ConversationMessage(
            role=role, text=text, timestamp=datetime.utcnow(), is_partial=is_partial
        )

        self.conversation_history.append(message)

        # Save to Redis (skip partial messages)
        if not is_partial:
            await redis_client.add_conversation_message(self.session_id, message)

    def set_state(self, state: ConversationState) -> None:
        """
        Update conversation state.

        Args:
            state: New conversation state
        """
        logger.info(f"Conversation state: {self.current_state} → {state}")
        self.current_state = state

    async def recognize_intent(self, user_text: str) -> Dict[str, Any]:
        """
        Recognize user intent from text.

        Args:
            user_text: User's input text

        Returns:
            Intent dictionary with type and parameters
        """
        text_lower = user_text.lower()

        # Plan approval
        if self.current_state == ConversationState.PLAN_APPROVAL:
            if any(
                word in text_lower
                for word in ["yes", "sure", "okay", "go ahead", "proceed", "begin"]
            ):
                return {"type": "plan_approved", "approved": True}
            elif any(word in text_lower for word in ["no", "not yet", "wait"]):
                return {"type": "plan_approved", "approved": False}

        # Slogan selection
        if self.current_state == ConversationState.SLOGAN_SELECTION:
            # Look for numbers or keywords
            for i in range(1, 6):  # 5 slogans
                if f"slogan {i}" in text_lower or f"number {i}" in text_lower:
                    return {"type": "slogan_selected", "number": i}
                # Handle ordinals
                ordinals = ["first", "second", "third", "fourth", "fifth"]
                if i <= len(ordinals) and ordinals[i - 1] in text_lower:
                    return {"type": "slogan_selected", "number": i}

        # Image selection
        if self.current_state == ConversationState.IMAGE_SELECTION:
            # Look for position descriptors or numbers
            for i in range(1, 5):  # 4 images
                if f"image {i}" in text_lower or f"number {i}" in text_lower:
                    return {"type": "image_selected", "number": i}

            # Position-based
            positions = {
                "top left": 1,
                "top right": 2,
                "bottom left": 3,
                "bottom right": 4,
                "first": 1,
                "second": 2,
                "third": 3,
                "fourth": 4,
            }
            for position, number in positions.items():
                if position in text_lower:
                    return {"type": "image_selected", "number": number}

        # General commands
        if "start" in text_lower or "begin" in text_lower:
            return {"type": "start_campaign"}

        if "help" in text_lower:
            return {"type": "help_requested"}

        # Default: general conversation
        return {"type": "general", "text": user_text}

    def get_expected_response(self) -> str:
        """
        Get prompt for what the Producer should say based on current state.

        Returns:
            Guidance for Producer's response
        """
        prompts = {
            ConversationState.WELCOME: "Greet the user and introduce yourself as the Executive Producer. Mention the product and ask if they're ready to start.",
            ConversationState.PLANNING: "You're generating the campaign plan. Announce that you're breaking it into 5 phases.",
            ConversationState.PLAN_APPROVAL: "Present the plan and ask if the user approves. End with 'Shall I task the Strategy Agent to begin?'",
            ConversationState.STRATEGY_REVIEW: "Announce that the Strategy Agent has completed and generated personas and slogans. Ask the user to review them.",
            ConversationState.SLOGAN_SELECTION: "The user should select a slogan. Prompt them if needed: 'Which slogan resonates with you?'",
            ConversationState.ART_REVIEW: "Announce that the Art Director has generated hero images. Ask the user to review them.",
            ConversationState.IMAGE_SELECTION: "The user should select an image. Prompt them: 'Which image would you like to use?'",
            ConversationState.FINAL_PRODUCTION: "Announce that the final agents (Video, Audio, Web) are working in parallel. Provide status updates as they complete.",
            ConversationState.COMPLETION: "Announce campaign completion. Summarize all assets delivered.",
        }

        return prompts.get(
            self.current_state, "Continue the professional conversation as Executive Producer."
        )

    async def get_context_for_producer(self) -> Dict[str, Any]:
        """
        Get conversation context for Producer.

        Returns:
            Context dictionary with history and state
        """
        # Get recent messages
        recent_messages = self.conversation_history[-10:]

        return {
            "session_id": self.session_id,
            "project_id": self.project_id,
            "current_state": self.current_state.value,
            "recent_messages": [
                {"role": msg.role, "text": msg.text} for msg in recent_messages
            ],
            "expected_response": self.get_expected_response(),
        }

    def format_history_for_display(self) -> List[Dict[str, str]]:
        """
        Format conversation history for UI display.

        Returns:
            List of message dictionaries
        """
        return [
            {
                "role": msg.role,
                "text": msg.text,
                "timestamp": msg.timestamp.isoformat(),
            }
            for msg in self.conversation_history
            if not msg.is_partial
        ]
