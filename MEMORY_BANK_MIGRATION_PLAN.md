# AI Agency Session Management Upgrade Plan
## Migrating from Redis to Vertex AI Memory Bank

**Last Updated:** 2025-01-04
**Status:** Ready for Implementation
**Estimated Timeline:** 4 weeks

---

## Executive Summary

This plan outlines the migration from Redis-based conversation history storage to **Vertex AI Memory Bank** with automated memory management through ADK callbacks and built-in memory tools.

**Key Benefits:**
- ✅ **Persistent long-term memory** across sessions
- ✅ **Automatic memory extraction** via callbacks (no manual save calls)
- ✅ **Semantic memory search** instead of chronological retrieval
- ✅ **Reduced Redis storage** (conversation history moves to Memory Bank)
- ✅ **Built-in memory tools** (PreloadMemoryTool, load_memory) already imported in your code
- ✅ **Seamless ADK integration** with minimal code changes

---

## Current State Analysis

### What We're Replacing

**Current Implementation (backend/app/services/gemini_live_adk.py):**

```python
# Line 1029: Currently using InMemorySessionService
session_service = InMemorySessionService()

# Lines 1380-1387: Manual transcript saving to Redis
async def _save_transcript(self, role: str, text: str):
    message = ConversationMessage(role=role, text=text, timestamp=datetime.now())
    await redis_client.add_conversation_message(self.session_id, message)
```

**Redis Schema (backend/app/services/redis_client.py):**
```
session:{session_id}:conversation -> List [message_1, message_2, ...]
```

**Methods to Replace:**
- `redis_client.add_conversation_message()` (line 80-86)
- `redis_client.get_conversation_history()` (line 88-95)
- `ConversationManager` conversation history logic

### What We're Keeping in Redis

✅ **Project Brief** (`project:{project_id}:brief`)
✅ **Assets** (`asset:{asset_id}`, `project:{project_id}:assets`)
✅ **Agent Status** (`agent:{agent_id}:status`)
✅ **Event Streaming** (Pub/Sub)
✅ **Session Metadata** (`session:{session_id}` - user_id, created_at, status)

---

## Architecture Design

### New Data Flow

```
┌──────────────┐         ┌─────────────────┐         ┌──────────────────┐
│   Frontend   │◄───────►│  FastAPI        │◄───────►│  Vertex AI       │
│   (Audio)    │ WebSocket│  Backend        │   ADK   │  Memory Bank     │
└──────────────┘         └─────────────────┘         └──────────────────┘
                                │                              │
                                │                              │
                         ┌──────▼──────┐             ┌────────▼─────────┐
                         │    Redis    │             │  ADK Runner      │
                         │  (State &   │             │  + Callback      │
                         │   Pub/Sub)  │             │  (Auto-save)     │
                         └─────────────┘             └──────────────────┘
```

### Memory Lifecycle

```
1. User speaks → ADK session receives audio → Events logged to session
                              │
2. Agent responds → Turn completes → after_agent_callback triggered
                              │
3. Callback → memory_service.add_session_to_memory(session)
                              │
4. Memory Bank → Extracts semantic memories from session events
                              │
5. Next session → PreloadMemoryTool → Retrieves relevant memories
                              │
6. Agent context → Enriched with past conversation memories
```

---

## Implementation Plan

### Phase 1: Infrastructure Setup (Week 1)

#### 1.1 Create Agent Engine Instance

```bash
# Set environment variables
export GOOGLE_CLOUD_PROJECT="your-project-id"
export GOOGLE_CLOUD_LOCATION="us-central1"  # or your preferred region

# Python script to create Agent Engine
```

**File: `backend/scripts/setup_memory_bank.py`**

```python
import os
import vertexai
from google.adk.memory import VertexAiMemoryBankService

os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
os.environ["GOOGLE_CLOUD_PROJECT"] = "your-project-id"
os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"

# Create client and agent engine
client = vertexai.Client(
    project=os.environ["GOOGLE_CLOUD_PROJECT"],
    location=os.environ["GOOGLE_CLOUD_LOCATION"]
)

# Create agent engine for Memory Bank
agent_engine = client.agent_engines.create()
agent_engine_id = agent_engine.api_resource.name.split("/")[-1]

print(f"✅ Agent Engine created: {agent_engine_id}")
print(f"Save this ID to your .env file as AGENT_ENGINE_ID={agent_engine_id}")
```

#### 1.2 Update Configuration

**File: `backend/app/config.py`**

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # ... existing settings ...

    # Memory Bank configuration
    agent_engine_id: str  # Add this new field
    enable_memory_bank: bool = True  # Feature flag for gradual rollout
    memory_callback_enabled: bool = True  # Enable auto-save via callback
    enable_redis_transcript_backup: bool = False  # Backup to Redis during transition

    class Config:
        env_file = ".env"
```

**File: `backend/.env`**

```bash
# Existing config...

# Memory Bank Configuration
AGENT_ENGINE_ID=your-agent-engine-id-here
ENABLE_MEMORY_BANK=true
MEMORY_CALLBACK_ENABLED=true
ENABLE_REDIS_TRANSCRIPT_BACKUP=false
```

#### 1.3 Install Dependencies

```bash
# All ADK memory dependencies should already be installed
# Verify with:
cd backend
uv pip list | grep google-adk
uv pip list | grep vertexai
```

---

### Phase 2: Implement Memory Bank Service (Week 1-2)

#### 2.1 Create Memory Service Module

**File: `backend/app/services/memory_service.py`**

```python
"""Vertex AI Memory Bank service integration."""

import logging
import os
from typing import Optional

from google.adk.memory import VertexAiMemoryBankService
import vertexai

from app.config import settings

logger = logging.getLogger(__name__)


class MemoryBankService:
    """Wrapper for Vertex AI Memory Bank operations."""

    def __init__(self):
        self._service: Optional[VertexAiMemoryBankService] = None
        self._initialized = False

    async def initialize(self):
        """Initialize Memory Bank service."""
        if not settings.enable_memory_bank:
            logger.info("Memory Bank disabled via settings")
            return

        try:
            # Ensure environment variables are set
            os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
            os.environ["GOOGLE_CLOUD_PROJECT"] = settings.google_cloud_project
            os.environ["GOOGLE_CLOUD_LOCATION"] = settings.google_cloud_location

            # Initialize Memory Bank service
            self._service = VertexAiMemoryBankService(
                project=settings.google_cloud_project,
                location=settings.google_cloud_location,
                agent_engine_id=settings.agent_engine_id
            )

            self._initialized = True
            logger.info(f"✅ Memory Bank initialized: project={settings.google_cloud_project}, "
                       f"location={settings.google_cloud_location}, "
                       f"agent_engine={settings.agent_engine_id}")

        except Exception as e:
            logger.error(f"❌ Failed to initialize Memory Bank: {e}", exc_info=True)
            raise

    @property
    def service(self) -> VertexAiMemoryBankService:
        """Get the underlying Memory Bank service."""
        if not self._initialized or not self._service:
            raise RuntimeError("Memory Bank service not initialized. Call initialize() first.")
        return self._service

    async def save_session_to_memory(self, session) -> None:
        """
        Save session events to Memory Bank.

        This triggers memory extraction from the conversation.
        """
        if not self._initialized:
            logger.warning("Memory Bank not initialized, skipping save")
            return

        try:
            await self._service.add_session_to_memory(session)
            logger.info(f"✅ Session saved to Memory Bank: session_id={session.session_id}")
        except Exception as e:
            logger.error(f"❌ Failed to save session to Memory Bank: {e}", exc_info=True)
            # Don't raise - memory save failures shouldn't break the conversation

    async def search_memory(self, app_name: str, user_id: str, query: str):
        """
        Search Memory Bank for relevant past conversations.

        Args:
            app_name: Application name
            user_id: User identifier
            query: Search query

        Returns:
            SearchMemoryResponse with relevant MemoryResult objects
        """
        if not self._initialized:
            logger.warning("Memory Bank not initialized, returning empty results")
            return None

        try:
            results = await self._service.search_memory(
                app_name=app_name,
                user_id=user_id,
                query=query
            )
            logger.info(f"✅ Memory search completed: {len(results.results) if results else 0} results")
            return results
        except Exception as e:
            logger.error(f"❌ Memory search failed: {e}", exc_info=True)
            return None


# Global instance
memory_bank_service = MemoryBankService()
```

#### 2.2 Implement Auto-Save Callback

**File: `backend/app/services/callbacks.py`**

```python
"""ADK callbacks for automatic memory management."""

import logging
from typing import Any

from app.services.memory_service import memory_bank_service
from app.config import settings

logger = logging.getLogger(__name__)


async def auto_save_session_to_memory_callback(callback_context: Any) -> None:
    """
    Callback that automatically saves session to Memory Bank after agent response.

    This is triggered after each agent turn completes.

    Args:
        callback_context: ADK callback context with access to session
    """
    if not settings.memory_callback_enabled:
        logger.debug("Memory callback disabled via settings")
        return

    try:
        # Access session from callback context
        session = callback_context._invocation_context.session
        memory_service = callback_context._invocation_context.memory_service

        # Save session to Memory Bank
        await memory_service.add_session_to_memory(session)

        logger.info(f"[Callback] ✅ Auto-saved session to Memory Bank: session_id={session.session_id}")

    except Exception as e:
        logger.error(f"[Callback] ❌ Failed to auto-save session: {e}", exc_info=True)
        # Don't raise - callback failures shouldn't break the conversation


async def log_agent_completion_callback(callback_context: Any) -> None:
    """
    Optional callback to log agent completion events.

    Can be chained with auto_save_session_to_memory_callback.
    """
    try:
        session_id = callback_context._invocation_context.session.session_id
        logger.info(f"[Callback] Agent turn completed: session_id={session_id}")
    except Exception as e:
        logger.error(f"[Callback] Failed to log completion: {e}")
```

---

### Phase 3: Migrate gemini_live_adk.py (Week 2)

#### 3.1 Replace InMemorySessionService

**File: `backend/app/services/gemini_live_adk.py`**

**Changes:**

```python
# BEFORE (Line 1029):
session_service = InMemorySessionService()

# AFTER:
from app.services.memory_service import memory_bank_service
from app.services.callbacks import auto_save_session_to_memory_callback

# Initialize Memory Bank service at startup (add to module initialization)
# This should be called when the app starts
import asyncio
asyncio.create_task(memory_bank_service.initialize())

# Use session service with Memory Bank
# Note: Session service manages sessions, Memory Bank manages long-term memories
session_service = InMemorySessionService()  # Keep for session state
# Memory Bank will be accessed via callback
```

#### 3.2 Add Memory Tools to Agent

**Update executive_producer_agent (Line 1013-1026):**

```python
# BEFORE:
executive_producer_agent = Agent(
    name="executive_producer",
    model="gemini-live-2.5-flash-preview-native-audio-09-2025",
    description="Executive Producer for AI Agency Hub",
    instruction="",  # Set dynamically
    tools=[
        update_project_brief,
        create_campaign_strategy,
        generate_hero_images,
        generate_social_video,
        generate_audio_assets,
        generate_landing_page,
    ],
)

# AFTER:
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.adk.tools import load_memory
from app.services.callbacks import auto_save_session_to_memory_callback

executive_producer_agent = Agent(
    name="executive_producer",
    model="gemini-live-2.5-flash-preview-native-audio-09-2025",
    description="Executive Producer for AI Agency Hub",
    instruction="",  # Set dynamically
    tools=[
        # Memory tools (add at the beginning)
        PreloadMemoryTool(),  # Auto-retrieves memory at each turn
        load_memory,          # Manual memory retrieval when needed

        # Existing tools
        update_project_brief,
        create_campaign_strategy,
        generate_hero_images,
        generate_social_video,
        generate_audio_assets,
        generate_landing_page,
    ],

    # Add callback for automatic memory saving
    after_agent_callback=auto_save_session_to_memory_callback,
)
```

#### 3.3 Update Runner Initialization

**Update runner (Line 1030-1034):**

```python
# BEFORE:
runner = Runner(
    app_name="ai_agency_hub",
    agent=executive_producer_agent,
    session_service=session_service,
)

# AFTER:
from app.services.memory_service import memory_bank_service

runner = Runner(
    app_name="ai_agency_hub",
    agent=executive_producer_agent,
    session_service=session_service,
    memory_service=memory_bank_service.service,  # Add Memory Bank service
)
```

#### 3.4 Update _save_transcript Method

**Modify _save_transcript (Lines 1380-1387):**

```python
# BEFORE:
async def _save_transcript(self, role: str, text: str):
    """Save conversation transcript to Redis."""
    message = ConversationMessage(role=role, text=text, timestamp=datetime.now())
    await redis_client.add_conversation_message(self.session_id, message)

# AFTER:
async def _save_transcript(self, role: str, text: str):
    """
    Save conversation transcript.

    Note: With Memory Bank callbacks enabled, transcripts are automatically
    saved to Memory Bank via after_agent_callback. This method is kept for
    backwards compatibility and optional Redis logging.
    """
    # Optional: Keep Redis logging for debugging/audit trail
    if settings.enable_redis_transcript_backup:
        message = ConversationMessage(role=role, text=text, timestamp=datetime.now())
        await redis_client.add_conversation_message(self.session_id, message)

    # Memory Bank saving is now handled by after_agent_callback
    # No manual save needed here
```

---

### Phase 4: Update System Prompt (Week 2)

#### 4.1 Enhance Executive Producer Prompt

**Update create_system_prompt() (Line 875):**

```python
def create_system_prompt(project_id: str) -> str:
    """Create the Executive Producer system prompt."""
    return f"""
# IDENTITY & ROLE
You are the **Executive Producer** of an AI-powered creative agency called "AI Agency Hub." As a voice-first assistant, your primary interface with the user is conversational audio.

**IMPORTANT - Memory Capabilities:**
- You have access to **long-term memory** from past conversations with this user
- The PreloadMemoryTool automatically loads relevant memories at the start of each turn
- Use the `load_memory` tool to manually search for specific past information when needed
- Reference past conversations naturally (e.g., "I remember you mentioned..." or "Based on our previous discussion about...")

Your role is to:
1. **Remember user preferences** across sessions (brand preferences, past feedback, design choices)
2. **Understand the client's vision** through natural conversation
3. Coordinate the creative process by calling functions
4. **Present work thoughtfully** with context and critique
5. **Guide the creative process** from brief to final deliverables

---

# MEMORY USAGE GUIDELINES

## When to Use Memory
- **Automatically loaded**: Every turn starts with PreloadMemoryTool retrieving relevant memories
- **Manual retrieval**: Use `load_memory` tool when you need specific past information:
  - User asks about previous campaigns
  - Need to recall user's brand preferences
  - Want to reference past feedback or decisions
  - Building on earlier creative work

## How to Reference Memory
- **Natural integration**: "Based on our previous conversation about urban aesthetics..."
- **Preference recall**: "I remember you prefer bold, minimalist designs..."
- **Continuity**: "Following up on the Aura campaign we worked on..."

---

# WORKFLOW STAGES
[... existing workflow stages ...]

# CURRENT PROJECT
Project ID: `{project_id}`

When you call functions, they will automatically use this project context.
**Your memory tools will search for conversations related to this user across all sessions.**

---

**Your first message should warmly greet the user and ask about their product vision.**
"""
```

---

### Phase 5: Deprecate Redis Conversation History (Week 3)

#### 5.1 Update redis_client.py

**File: `backend/app/services/redis_client.py`**

```python
# Mark conversation methods as deprecated

async def add_conversation_message(
    self, session_id: str, message: ConversationMessage
) -> None:
    """
    Add message to conversation history.

    DEPRECATED: This method is deprecated in favor of Vertex AI Memory Bank.
    Only used when ENABLE_REDIS_TRANSCRIPT_BACKUP=true for debugging.
    """
    if not settings.enable_redis_transcript_backup:
        logger.debug("Redis transcript backup disabled, skipping save")
        return

    await self.client.lpush(
        f"session:{session_id}:conversation", message.model_dump_json()
    )
    logger.debug(f"[Redis Backup] Saved message: session={session_id}")


async def get_conversation_history(
    self, session_id: str, limit: int = 100
) -> List[ConversationMessage]:
    """
    Retrieve conversation history.

    DEPRECATED: This method is deprecated in favor of Vertex AI Memory Bank.
    Use memory_bank_service.search_memory() instead.
    """
    logger.warning("get_conversation_history() is deprecated. Use Memory Bank search instead.")

    messages = await self.client.lrange(
        f"session:{session_id}:conversation", 0, limit - 1
    )
    return [ConversationMessage(**json.loads(msg)) for msg in messages]
```

#### 5.2 Update ConversationManager

**File: `backend/app/services/conversation_manager.py`**

```python
# Update imports
from app.services.memory_service import memory_bank_service

class ConversationManager:
    """
    Manages conversation state and user interactions.

    Note: Conversation history is now managed by Vertex AI Memory Bank.
    This class focuses on conversation state and flow only.
    """

    def __init__(self, session_id: str, project_id: str):
        self.session_id = session_id
        self.project_id = project_id
        self.current_state = ConversationState.WELCOME
        # Remove: self.conversation_history: List[ConversationMessage] = []

    async def initialize(self) -> None:
        """Initialize conversation manager."""
        logger.info(f"Conversation manager initialized: session={self.session_id}")
        # Remove Redis history loading - Memory Bank handles this via PreloadMemoryTool

    async def add_message(
        self, role: str, text: str, is_partial: bool = False
    ) -> None:
        """
        Add message to conversation.

        Note: Messages are automatically saved to Memory Bank via callbacks.
        This method is kept for API compatibility.
        """
        # Remove local history tracking
        # Memory Bank callback handles persistence
        logger.debug(f"Message logged: role={role}, partial={is_partial}")

    async def get_context_for_producer(self) -> Dict[str, Any]:
        """
        Get conversation context for Producer.

        Note: Memory is now retrieved via PreloadMemoryTool and load_memory.
        """
        return {
            "session_id": self.session_id,
            "project_id": self.project_id,
            "current_state": self.current_state.value,
            "expected_response": self.get_expected_response(),
            # Note: Recent messages are available via Memory Bank tools
        }
```

---

### Phase 6: Testing & Validation (Week 3-4)

#### 6.1 Unit Tests

**File: `backend/tests/test_memory_bank.py`**

```python
"""Tests for Memory Bank integration."""

import pytest
from app.services.memory_service import MemoryBankService, memory_bank_service
from app.services.callbacks import auto_save_session_to_memory_callback


@pytest.mark.asyncio
async def test_memory_bank_initialization():
    """Test Memory Bank service initialization."""
    service = MemoryBankService()
    await service.initialize()
    assert service._initialized is True
    assert service.service is not None


@pytest.mark.asyncio
async def test_memory_search(mock_session):
    """Test memory search functionality."""
    await memory_bank_service.initialize()

    results = await memory_bank_service.search_memory(
        app_name="ai_agency_hub",
        user_id="test_user",
        query="What are my brand preferences?"
    )

    # Results may be empty for new user, but should not error
    assert results is not None


@pytest.mark.asyncio
async def test_auto_save_callback(mock_callback_context):
    """Test automatic session save callback."""
    await auto_save_session_to_memory_callback(mock_callback_context)
    # Should not raise exceptions
```

#### 6.2 Integration Tests

**File: `backend/tests/integration/test_memory_flow.py`**

```python
"""Integration tests for Memory Bank conversation flow."""

import pytest
from google.adk import Runner
from app.services.gemini_live_adk import executive_producer_agent, runner


@pytest.mark.asyncio
async def test_multi_turn_conversation_with_memory():
    """Test that memories are saved and retrieved across turns."""

    # Turn 1: User provides brand preference
    # ... (test conversation simulation)

    # Turn 2: Verify agent recalls preference
    # ... (verify memory retrieval via PreloadMemoryTool)

    pass


@pytest.mark.asyncio
async def test_memory_persistence_across_sessions():
    """Test that memories persist between different sessions."""

    # Session 1: Create campaign
    # ...

    # Session 2: Agent should recall details from Session 1
    # ...

    pass
```

#### 6.3 Manual Testing Checklist

- [ ] Create new conversation → Verify session events logged
- [ ] Complete first turn → Check callback fires and saves to Memory Bank
- [ ] Start second turn → Verify PreloadMemoryTool retrieves memories
- [ ] Test load_memory tool → Manually trigger memory search
- [ ] Close and reopen session → Verify memories persist
- [ ] Test with multiple users → Verify memory isolation
- [ ] Disable Memory Bank (feature flag) → Verify graceful fallback
- [ ] Check Redis → Verify conversation history no longer stored (unless backup enabled)

---

### Phase 7: Rollout & Migration (Week 4)

#### 7.1 Feature Flag Rollout

```python
# .env configuration for gradual rollout

# Phase 1: Parallel mode (both Redis and Memory Bank)
ENABLE_MEMORY_BANK=true
MEMORY_CALLBACK_ENABLED=true
ENABLE_REDIS_TRANSCRIPT_BACKUP=true  # Keep Redis as backup

# Phase 2: Memory Bank primary (Redis backup only)
ENABLE_MEMORY_BANK=true
MEMORY_CALLBACK_ENABLED=true
ENABLE_REDIS_TRANSCRIPT_BACKUP=true

# Phase 3: Memory Bank only
ENABLE_MEMORY_BANK=true
MEMORY_CALLBACK_ENABLED=true
ENABLE_REDIS_TRANSCRIPT_BACKUP=false  # Disable Redis backups
```

#### 7.2 Data Migration Script

**File: `backend/scripts/migrate_redis_to_memory_bank.py`**

```python
"""
Optional: Migrate existing Redis conversation history to Memory Bank.

This script reads existing Redis conversation histories and saves them
to Memory Bank for continuity.
"""

import asyncio
from app.services.redis_client import redis_client
from app.services.memory_service import memory_bank_service


async def migrate_session_history(session_id: str):
    """Migrate a single session's history to Memory Bank."""

    # Get conversation history from Redis
    messages = await redis_client.get_conversation_history(session_id)

    if not messages:
        print(f"No messages found for session: {session_id}")
        return

    # Create a session object from messages
    # ... (implementation depends on ADK session format)

    # Save to Memory Bank
    await memory_bank_service.save_session_to_memory(session)

    print(f"✅ Migrated {len(messages)} messages from session: {session_id}")


async def migrate_all_sessions():
    """Migrate all sessions from Redis to Memory Bank."""

    # Initialize services
    await redis_client.connect()
    await memory_bank_service.initialize()

    # Get all session keys
    session_keys = await redis_client.client.keys("session:*:conversation")

    print(f"Found {len(session_keys)} sessions to migrate")

    for key in session_keys:
        session_id = key.split(":")[1]
        try:
            await migrate_session_history(session_id)
        except Exception as e:
            print(f"❌ Failed to migrate session {session_id}: {e}")

    await redis_client.disconnect()

    print("✅ Migration complete")


if __name__ == "__main__":
    asyncio.run(migrate_all_sessions())
```

---

## Configuration Summary

### Environment Variables

```bash
# backend/.env

# Existing Vertex AI config
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json

# New Memory Bank config
AGENT_ENGINE_ID=your-agent-engine-id
ENABLE_MEMORY_BANK=true
MEMORY_CALLBACK_ENABLED=true
ENABLE_REDIS_TRANSCRIPT_BACKUP=false  # Set true during transition period
```

---

## Code Changes Summary

### Files to Create

1. ✅ `backend/app/services/memory_service.py` - Memory Bank service wrapper
2. ✅ `backend/app/services/callbacks.py` - ADK callback functions
3. ✅ `backend/scripts/setup_memory_bank.py` - Setup script
4. ✅ `backend/scripts/migrate_redis_to_memory_bank.py` - Migration script
5. ✅ `backend/tests/test_memory_bank.py` - Unit tests
6. ✅ `backend/tests/integration/test_memory_flow.py` - Integration tests

### Files to Modify

1. ✅ `backend/app/config.py` - Add Memory Bank settings
2. ✅ `backend/app/services/gemini_live_adk.py` - Add memory tools, callback, and runner config
3. ✅ `backend/app/services/redis_client.py` - Deprecate conversation methods
4. ✅ `backend/app/services/conversation_manager.py` - Remove local history tracking
5. ✅ `backend/.env` - Add Memory Bank configuration

### Key Code Additions

**gemini_live_adk.py:**
```python
# Add imports
from app.services.memory_service import memory_bank_service
from app.services.callbacks import auto_save_session_to_memory_callback

# Update agent
executive_producer_agent = Agent(
    tools=[PreloadMemoryTool(), load_memory, ...],
    after_agent_callback=auto_save_session_to_memory_callback,
)

# Update runner
runner = Runner(
    memory_service=memory_bank_service.service,
    ...
)
```

---

## Benefits Analysis

### Before (Redis)

- ❌ Conversation history stored chronologically in Redis lists
- ❌ Manual save calls required (`add_conversation_message`)
- ❌ Limited to retrieving by session ID + offset
- ❌ No semantic search capabilities
- ❌ History limited to single session (no cross-session memory)
- ❌ Requires manual context construction for agent

### After (Memory Bank)

- ✅ **Automatic memory extraction** via callbacks (no manual saves)
- ✅ **Semantic memory search** (search by meaning, not just keywords)
- ✅ **Cross-session memory** (agent remembers user across sessions)
- ✅ **Built-in ADK integration** (PreloadMemoryTool, load_memory)
- ✅ **Reduced Redis storage** (conversation history moved to Memory Bank)
- ✅ **Better agent context** (memories automatically loaded each turn)
- ✅ **Long-term knowledge** (memories persist indefinitely)

---

## Risk Mitigation

### Potential Issues & Solutions

| Risk | Mitigation |
|------|-----------|
| **Memory Bank API limits** | Implement rate limiting and exponential backoff in memory_service.py |
| **Callback failures** | Wrap callback in try/except, don't raise exceptions that break conversation |
| **Memory Bank downtime** | Use feature flags to fall back to Redis temporarily |
| **Cost concerns** | Monitor Memory Bank API usage, implement memory pruning if needed |
| **Data loss during migration** | Keep Redis backup enabled during transition (`ENABLE_REDIS_TRANSCRIPT_BACKUP=true`) |
| **Session compatibility** | Test session resumption thoroughly with Memory Bank |

---

## Success Metrics

### Phase 1-2 (Weeks 1-2)
- [ ] Agent Engine created successfully
- [ ] Memory Bank service initialized without errors
- [ ] Callbacks firing correctly after each agent turn
- [ ] PreloadMemoryTool retrieving memories

### Phase 3-4 (Weeks 3-4)
- [ ] Zero conversation history entries in Redis (when backup disabled)
- [ ] Memories persisting across sessions
- [ ] Agent referencing past conversations naturally
- [ ] All integration tests passing

### Phase 5 (Week 4+)
- [ ] Feature flag rollout complete
- [ ] Redis conversation storage deprecated
- [ ] Production traffic running on Memory Bank
- [ ] User satisfaction with "agent remembers me"

---

## Next Steps

1. **Immediate**: Run `backend/scripts/setup_memory_bank.py` to create Agent Engine
2. **Week 1**: Implement `memory_service.py` and `callbacks.py`
3. **Week 2**: Update `gemini_live_adk.py` with memory tools
4. **Week 3**: Test thoroughly, enable feature flags
5. **Week 4**: Rollout to production, monitor metrics

---

## Questions & Decisions

Before starting implementation, confirm:

1. **Region**: Which GCP region for Memory Bank? (Recommend: us-central1)
2. **Feature Flags**: Start with both Redis and Memory Bank in parallel?
3. **Migration**: Migrate existing Redis histories or start fresh?
4. **Backup Strategy**: Keep Redis backups enabled long-term or disable after validation?
5. **Memory Pruning**: Implement memory cleanup/expiration policies?

---

## References

- [Vertex AI Memory Bank Documentation](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/memory-bank/overview)
- [ADK Memory Guide](https://google.github.io/adk-docs/sessions/memory/)
- [Memory Bank Quickstart with ADK](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/memory-bank/quickstart-adk)
- [ADK PreloadMemoryTool API](https://google.github.io/adk-docs/sessions/memory/)
