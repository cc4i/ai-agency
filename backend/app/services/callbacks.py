"""
ADK Callback Functions for Memory Bank Integration

Callbacks are triggered automatically by the ADK Runner at specific points
in the conversation lifecycle. This module implements callbacks for:

1. after_agent_callback: Called after each agent turn completes
   - Automatically saves conversation history to Memory Bank
   - No manual intervention required

2. Error handling and logging for debugging

Architecture:
    ADK Runner → after_agent_callback → memory_service.add_session_to_memory
                        ↓
                Automatic persistence to Vertex AI Memory Bank

Usage:
    from app.services.callbacks import after_agent_callback

    # Register callback on the Agent, not Runner
    agent = Agent(
        name="executive_producer",
        after_agent_callback=after_agent_callback,  # ← Register here
        ...
    )
"""

import logging
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google import genai

from app.config import settings
from app.services.memory_service import memory_service

logger = logging.getLogger(__name__)


async def after_agent_callback(
    ctx: CallbackContext,
) -> Optional[genai.types.Content]:
    """
    Callback executed after each agent turn completes.

    This callback automatically saves the conversation history to Memory Bank
    when enabled via MEMORY_CALLBACK_ENABLED setting.

    Args:
        ctx: CallbackContext containing session and invocation details

    Returns:
        Optional Content to override agent response (None = no override)

    Note:
        This callback is non-blocking and will not prevent the conversation
        from continuing even if memory persistence fails.
    """
    # Skip if callback feature is disabled
    if not settings.memory_callback_enabled:
        logger.debug("[Callback] Memory callbacks disabled (MEMORY_CALLBACK_ENABLED=false)")
        return None

    # Skip if Memory Bank is disabled
    if not settings.enable_memory_bank:
        logger.debug("[Callback] Memory Bank disabled (ENABLE_MEMORY_BANK=false)")
        return None

    try:
        # Extract session from context
        session = ctx.session
        session_id = session.id if hasattr(session, 'id') else 'unknown'

        logger.info(
            f"[Callback] after_agent_callback triggered: "
            f"session={session_id}, invocation={ctx.invocation_id}"
        )

        # Log conversation state for debugging
        if hasattr(session, "history") and session.history:
            message_count = len(session.history)
            logger.debug(f"[Callback] Session has {message_count} messages in history")
            # Log last message for debugging
            if message_count > 0:
                last_msg = session.history[-1]
                logger.debug(f"[Callback] Last message role: {getattr(last_msg, 'role', 'unknown')}")
        else:
            logger.debug("[Callback] No conversation history available in session")

        # Add session to Memory Bank
        # This persists the entire conversation history for semantic search
        success = await memory_service.add_session_to_memory(
            session=session,
        )

        if success:
            logger.info(f"[Callback] ✓ Memory persisted for session {session_id}")
        else:
            logger.warning(f"[Callback] ⚠ Memory persistence skipped for session {session_id}")

    except Exception as e:
        # Catch all exceptions to prevent callback from breaking the conversation
        logger.error(
            f"[Callback] ✗ Unexpected error in after_agent_callback: {e}",
            exc_info=True,
        )
        # Don't raise - we don't want memory failures to break the conversation

    # Return None to not override the agent's response
    return None


async def before_agent_callback(
    ctx: CallbackContext,
) -> Optional[genai.types.Content]:
    """
    Callback executed before each agent turn starts.

    Currently not used, but available for future features like:
    - Preprocessing user input
    - Loading context from Memory Bank
    - Rate limiting
    - User authentication

    Args:
        ctx: CallbackContext containing session and invocation details

    Returns:
        Optional Content to override agent behavior (None = proceed normally)
    """
    logger.debug(
        f"[Callback] before_agent_callback triggered: "
        f"session={ctx.session.id}, invocation={ctx.invocation_id}"
    )

    # Future: Could preload relevant memories here
    # For now, we use PreloadMemoryTool which handles this automatically
    return None
