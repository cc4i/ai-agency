"""
Vertex AI Memory Bank Service

This service wraps the Google ADK VertexAiMemoryBankService to provide
long-term semantic memory storage for conversations.

Key features:
- Automatic conversation history persistence on turn_complete (Live mode)
- Semantic search across past conversations
- Cross-session memory retrieval
- Integration with PreloadMemoryTool for automatic memory loading

Architecture (Live Mode):
    Agent → turn_complete event → MemoryBankService → Vertex AI Memory Bank
                ↓
            Manual persistence after each turn (callbacks don't work in Live mode)

Usage:
    from app.services.memory_service import memory_service

    # Add a session to memory (called on turn_complete in Live mode)
    await memory_service.add_session_to_memory(
        session=adk_session_object
    )

    # Search memory (called via load_memory tool)
    results = await memory_service.search_memory(
        query="What did we discuss about sneaker campaigns?",
        user_id="user_456",
        app_name="ai_agency_hub",
        limit=5
    )
"""

import logging
from typing import Any, Dict, List, Optional

from google.adk.memory import VertexAiMemoryBankService
from google.adk.sessions import Session

from app.config import settings

logger = logging.getLogger(__name__)


class MemoryBankService:
    """
    Wrapper for Vertex AI Memory Bank integration.

    Provides methods for storing and retrieving conversation history
    using semantic search across sessions.
    """

    def __init__(self):
        """Initialize the Memory Bank service."""
        self._service: Optional[VertexAiMemoryBankService] = None
        self._initialized = False

    def _initialize(self):
        """
        Lazy initialization of Memory Bank service.

        Only initializes if Memory Bank is enabled in settings.
        """
        if self._initialized:
            return

        if not settings.enable_memory_bank:
            logger.info("[Memory Bank] Feature is disabled (ENABLE_MEMORY_BANK=false)")
            return

        if not settings.agent_engine_id:
            logger.error(
                "[Memory Bank] AGENT_ENGINE_ID not set. "
                "Run 'python backend/scripts/setup_memory_bank.py' to create an Agent Engine."
            )
            return

        try:
            logger.info(
                f"[Memory Bank] Initializing with Agent Engine: {settings.agent_engine_id}"
            )

            self._service = VertexAiMemoryBankService(
                agent_engine_id=settings.agent_engine_id,
                project=settings.google_cloud_project,
                location=settings.google_cloud_location,
            )

            self._initialized = True
            logger.info("[Memory Bank] ✓ Service initialized successfully")

        except Exception as e:
            logger.error(f"[Memory Bank] ✗ Initialization failed: {e}", exc_info=True)
            self._service = None

    async def add_session_to_memory(
        self,
        session: Session,
    ) -> bool:
        """
        Add a completed session to Memory Bank.

        This should be called after each conversation turn completes in Live mode.

        Args:
            session: ADK Session object containing conversation history

        Returns:
            True if successful, False otherwise
        """
        if not settings.enable_memory_bank:
            logger.debug("[Memory Bank] Skipping add_session (feature disabled)")
            return False

        self._initialize()

        if not self._service:
            logger.warning("[Memory Bank] Service not initialized, cannot add session")
            return False

        try:
            session_id = session.id if hasattr(session, 'id') else 'unknown'

            logger.info(
                f"[Memory Bank] Adding session to memory: session={session_id}"
            )
            logger.info(f"[Memory Bank] Agent Engine ID: {settings.agent_engine_id}")
            logger.info(f"[Memory Bank] Project: {settings.google_cloud_project}")
            logger.info(f"[Memory Bank] Location: {settings.google_cloud_location}")

            # Debug: Log session structure
            logger.info(f"[Memory Bank] Session app_name: {session.app_name}")
            logger.info(f"[Memory Bank] Session user_id: {session.user_id}")

            # Check events
            if hasattr(session, 'events'):
                event_count = len(session.events)
                logger.info(f"[Memory Bank] Session has {event_count} events")

                # Count ALL events with content (not just first 5)
                events_with_content = sum(
                    1 for e in session.events
                    if hasattr(e, 'content') and e.content is not None
                )

                logger.info(f"[Memory Bank] Events with content: {events_with_content}/{event_count}")

                # If there are events with content, log a sample
                if events_with_content > 0:
                    # Find first event with content
                    for idx, e in enumerate(session.events):
                        if hasattr(e, 'content') and e.content is not None:
                            logger.info(f"[Memory Bank] First content event at index {idx}")
                            logger.info(f"[Memory Bank] Sample content: {str(e.content)[:300]}")
                            break

                # Log details of first few events for debugging
                for i, event in enumerate(session.events[:5]):  # First 5 events
                    has_content = hasattr(event, 'content') and event.content is not None

                    # Debug: Show what's actually in the event
                    event_attrs = [attr for attr in dir(event) if not attr.startswith('_')]
                    logger.debug(
                        f"[Memory Bank] Event {i}: has_content={has_content}, "
                        f"type={type(event).__name__}, "
                        f"attributes={event_attrs[:10]}"  # First 10 attributes
                    )

                    # Check if content exists but is empty/None
                    if hasattr(event, 'content'):
                        content_value = str(event.content)[:200] if event.content else 'None'
                        logger.debug(
                            f"[Memory Bank] Event {i}.content: "
                            f"type={type(event.content).__name__ if event.content else 'NoneType'}, "
                            f"value={content_value}"
                        )

                if event_count == 0:
                    logger.error("[Memory Bank] ⚠️ Session has ZERO events - nothing to persist!")
                    return False

                if events_with_content == 0:
                    logger.error("[Memory Bank] ⚠️ Session has events but ZERO have content - nothing to persist!")
                    return False
            else:
                logger.error("[Memory Bank] ⚠️ Session has no 'events' attribute!")
                return False

            # Add session to Memory Bank
            # The service will automatically extract and index the conversation
            logger.info(f"[Memory Bank] Calling VertexAiMemoryBankService.add_session_to_memory()...")
            await self._service.add_session_to_memory(session=session)
            logger.info(f"[Memory Bank] ✓ ADK call completed without error")

            logger.info(f"[Memory Bank] ✓ Session {session_id} added to memory successfully")
            return True

        except Exception as e:
            logger.error(
                f"[Memory Bank] ✗ Failed to add session: {e}",
                exc_info=True,
            )
            # Log the full stack trace for debugging
            import traceback
            logger.error(f"[Memory Bank] Full traceback:\n{traceback.format_exc()}")
            return False

    async def search_memory(
        self,
        query: str,
        user_id: str,
        app_name: str = "ai_agency_hub",
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search memory bank for relevant past conversations.

        This is called by the load_memory tool when the agent needs to recall
        information from previous sessions.

        Args:
            query: Semantic search query
            user_id: User identifier
            app_name: Application name
            limit: Maximum number of results to return

        Returns:
            List of memory results with relevance scores
        """
        if not settings.enable_memory_bank:
            logger.debug("[Memory Bank] Skipping search (feature disabled)")
            return []

        self._initialize()

        if not self._service:
            logger.warning("[Memory Bank] Service not initialized, cannot search")
            return []

        try:
            logger.info(
                f"[Memory Bank] Searching memory: "
                f"query='{query[:50]}...', user={user_id}, limit={limit}"
            )

            # Perform semantic search
            results = await self._service.search_memory(
                app_name=app_name,
                user_id=user_id,
                query=query,
                limit=limit,
            )

            logger.info(f"[Memory Bank] ✓ Found {len(results)} relevant memories")

            # Log first result for debugging
            if results:
                first_result = results[0]
                logger.debug(
                    f"[Memory Bank] Top result: "
                    f"relevance={first_result.get('relevance_score', 0):.2f}, "
                    f"content='{str(first_result.get('content', ''))[:100]}...'"
                )

            return results

        except Exception as e:
            logger.error(f"[Memory Bank] ✗ Search failed: {e}", exc_info=True)
            return []

    async def get_memory_for_session(
        self,
        session_id: str,
        user_id: str,
        app_name: str = "ai_agency_hub",
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all memories associated with a specific session.

        Args:
            session_id: Session identifier
            user_id: User identifier
            app_name: Application name

        Returns:
            List of memory entries for the session
        """
        if not settings.enable_memory_bank:
            logger.debug("[Memory Bank] Skipping get_memory (feature disabled)")
            return []

        self._initialize()

        if not self._service:
            logger.warning("[Memory Bank] Service not initialized")
            return []

        try:
            logger.info(
                f"[Memory Bank] Retrieving memories for session: {session_id}"
            )

            # Search for memories from this specific session
            results = await self.search_memory(
                query=f"session:{session_id}",
                user_id=user_id,
                app_name=app_name,
                limit=100,  # Get all memories from session
            )

            logger.info(f"[Memory Bank] ✓ Found {len(results)} memories for session")
            return results

        except Exception as e:
            logger.error(
                f"[Memory Bank] ✗ Failed to get session memories: {e}",
                exc_info=True,
            )
            return []

    def is_enabled(self) -> bool:
        """
        Check if Memory Bank is enabled and initialized.

        Returns:
            True if Memory Bank is ready to use
        """
        return settings.enable_memory_bank and self._initialized


# Global singleton instance
memory_service = MemoryBankService()
