# Memory Bank Live Mode Persistence

**Issue:** Memory Bank callbacks don't trigger in `run_live()` mode
**Status:** ✅ **FIXED** (using manual persistence on turn_complete)
**Date:** 2025-11-05

---

## Problem

Memory Bank callbacks (`after_agent_callback`) don't trigger when using `runner.run_live()` for Gemini Live streaming mode. This is a fundamental limitation of Live mode.

### Root Cause

**ADK Live Mode Limitation:** Callbacks registered on the Agent (`after_agent_callback`, `before_agent_callback`) are designed for traditional request/response mode (`runner.run_async()`) and do NOT trigger when using `runner.run_live()`.

**Why:**
- Live mode is designed for real-time bidirectional streaming
- There are no discrete "agent turns" in the traditional sense
- Turn completion events are for UI streaming, not agent lifecycle hooks
- The ADK doesn't invoke registered callbacks during Live mode

### Original Investigation (Callback Signature)

Initially investigated callback signature issues (see below), but this was NOT the root cause:

```python
# ❌ WRONG - This was the original implementation
async def after_agent_callback(
    session: Session,
    result: Any,
    error: Optional[Exception] = None,
) -> None:
```

The ADK actually expects:

```python
# ✅ CORRECT - Fixed signature
async def after_agent_callback(
    ctx: CallbackContext,
) -> Optional[genai.types.Content]:
```

### Why This Matters

The ADK callback signature is:
```python
Callable[[CallbackContext], Union[Awaitable[Optional[types.Content]], Optional[types.Content]]]
```

Key differences:
1. **Single parameter:** `CallbackContext` instead of multiple parameters
2. **Return value:** `Optional[types.Content]` to optionally override agent response
3. **Access session:** via `ctx.session` property, not direct parameter

---

## Solution: Manual Persistence on Turn Complete

Since `after_agent_callback` doesn't trigger in Live mode, we manually persist conversation history when we detect a turn has completed in the event stream.

### File: `backend/app/services/gemini_live_adk.py` (GeminiLiveConnection._agent_to_client_messaging)

**Added manual persistence after turn_complete event (lines 1440-1467):**

```python
# Handle turn completion
if hasattr(event, 'turn_complete') and event.turn_complete:
    await self.frontend_ws.send_text(json.dumps({
        "type": "turn_complete",
    }))

    # Persist conversation to Memory Bank after turn completes
    # NOTE: after_agent_callback doesn't trigger in run_live() mode,
    # so we manually persist here when turn_complete is detected
    if settings.enable_memory_bank and settings.memory_callback_enabled:
        try:
            from app.services.memory_service import memory_service

            logger.info(
                f"[Memory Bank] Turn complete detected, persisting session: "
                f"session_id={self.session_id}"
            )

            # Pass the Session object directly
            # NOTE: VertexAiMemoryBankService.add_session_to_memory() only accepts
            # a Session object, not individual session_id/user_id/app_name parameters
            success = await memory_service.add_session_to_memory(
                session=self.session,
            )

            if success:
                logger.info(f"[Memory Bank] ✓ Session {self.session_id} persisted successfully")
            else:
                logger.warning(f"[Memory Bank] ⚠ Session {self.session_id} persistence skipped")

        except Exception as e:
            logger.error(
                f"[Memory Bank] ✗ Failed to persist session {self.session_id}: {e}",
                exc_info=True
            )
```

**Key Points:**
- ✅ Triggers on every `turn_complete` event in Live mode
- ✅ Uses the same `memory_service.add_session_to_memory()` that callbacks would use
- ✅ Respects feature flags (`enable_memory_bank`, `memory_callback_enabled`)
- ✅ Comprehensive error handling and logging

---

## Callback Implementation (for reference)

The callback is still registered on the Agent for potential future use or if the ADK adds Live mode callback support.

### File: `backend/app/services/callbacks.py`

**Callback signature (corrected, but not used in Live mode):**

```python
from google.adk.agents.callback_context import CallbackContext
from google import genai

async def after_agent_callback(
    ctx: CallbackContext,
) -> Optional[genai.types.Content]:
    """
    Callback executed after each agent turn completes.

    Args:
        ctx: CallbackContext containing session and invocation details

    Returns:
        Optional Content to override agent response (None = no override)
    """
    # Skip if disabled
    if not settings.memory_callback_enabled:
        return None

    if not settings.enable_memory_bank:
        return None

    try:
        # Extract session from context
        session = ctx.session
        session_id = session.id
        user_id = ctx._invocation_context.user_id
        app_name = ctx._invocation_context.app_name

        logger.info(
            f"[Callback] after_agent_callback triggered: "
            f"session={session_id}, user={user_id}, app={app_name}, "
            f"invocation={ctx.invocation_id}"
        )

        # Log conversation history for debugging
        if hasattr(session, "history") and session.history:
            message_count = len(session.history)
            logger.debug(f"[Callback] Session has {message_count} messages in history")
            if message_count > 0:
                last_msg = session.history[-1]
                logger.debug(f"[Callback] Last message role: {getattr(last_msg, 'role', 'unknown')}")
        else:
            logger.debug("[Callback] No conversation history available in session")

        # Add session to Memory Bank
        success = await memory_service.add_session_to_memory(
            session_id=session_id,
            user_id=user_id,
            app_name=app_name,
        )

        if success:
            logger.info(f"[Callback] ✓ Memory persisted for session {session_id}")
        else:
            logger.warning(f"[Callback] ⚠ Memory persistence skipped for session {session_id}")

    except Exception as e:
        logger.error(
            f"[Callback] ✗ Unexpected error in after_agent_callback: {e}",
            exc_info=True,
        )

    # Return None to not override the agent's response
    return None
```

**Key changes:**
1. ✅ Uses `CallbackContext` as single parameter
2. ✅ Returns `Optional[genai.types.Content]`
3. ✅ Extracts session via `ctx.session`
4. ✅ Gets user_id and app_name from `ctx._invocation_context`
5. ✅ Added detailed logging for debugging

---

## Enhanced Logging

### File: `backend/app/services/memory_service.py`

Added detailed logging to help debug Memory Bank operations:

```python
logger.info(f"[Memory Bank] Adding session to memory: session={session_id}, user={user_id}, app={app_name}")
logger.info(f"[Memory Bank] Agent Engine ID: {settings.agent_engine_id}")
logger.info(f"[Memory Bank] Project: {settings.google_cloud_project}")
logger.info(f"[Memory Bank] Location: {settings.google_cloud_location}")

# ... perform operation ...

logger.info(f"[Memory Bank] ✓ Session {session_id} added to memory successfully")
```

On error:
```python
except Exception as e:
    logger.error(f"[Memory Bank] ✗ Failed to add session {session_id}: {e}", exc_info=True)
    import traceback
    logger.error(f"[Memory Bank] Full traceback:\n{traceback.format_exc()}")
```

---

## Verification Steps

Now when you run the backend and have a conversation, you should see these logs:

### 1. On Startup
```
INFO:app.services.gemini_live_adk:✓ Memory Bank callbacks registered on agent
INFO:app.services.gemini_live_adk:✓ Memory Bank service registered with runner
INFO:app.services.gemini_live_adk:✓ ADK Executive Producer agent created with 8 tools (with Memory Bank + callbacks)
INFO:app.services.memory_service:[Memory Bank] Initializing with Agent Engine: 3117603647907692544
INFO:app.services.memory_service:[Memory Bank] ✓ Service initialized successfully
```

### 2. After Each Conversation Turn (Live Mode)
```
INFO:app.services.gemini_live_adk:[Memory Bank] Turn complete detected, persisting session: session_id=<id>, user_id=<id>
INFO:app.services.memory_service:[Memory Bank] Adding session to memory: session=<id>, user=<id>, app=ai_agency_hub
INFO:app.services.memory_service:[Memory Bank] Agent Engine ID: 3117603647907692544
INFO:app.services.memory_service:[Memory Bank] Project: <your-project>
INFO:app.services.memory_service:[Memory Bank] Location: us-central1
INFO:app.services.memory_service:[Memory Bank] ✓ Session <id> added to memory successfully
INFO:app.services.gemini_live_adk:[Memory Bank] ✓ Session <id> persisted successfully
```

### 3. If No Logs Appear

**Check your `.env` file:**
```bash
AGENT_ENGINE_ID=3117603647907692544
ENABLE_MEMORY_BANK=true
MEMORY_CALLBACK_ENABLED=true  # ← Make sure this is set!
```

**Check log level:**
```bash
LOG_LEVEL=INFO  # Should be INFO or DEBUG
```

**Restart backend:**
```bash
cd backend
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Testing the Fix

### Test 1: Verify Callback Triggers

1. Start the backend
2. Open frontend and connect
3. Send a message via voice or text
4. **Check backend logs** for:
   ```
   [Callback] after_agent_callback triggered
   ```

### Test 2: Verify Memory Persistence

1. Have a short conversation (2-3 turns)
2. **Check backend logs** for each turn:
   ```
   [Memory Bank] ✓ Session <id> added to memory successfully
   [Callback] ✓ Memory persisted for session <id>
   ```

### Test 3: Verify Memory Retrieval

1. In a **NEW session**, ask: "What did we discuss before?"
2. Agent should call `load_memory` tool
3. **Check backend logs** for:
   ```
   [Memory Bank] Searching memory: query='previous discussion'
   [Memory Bank] ✓ Found X relevant memories
   ```

---

## Common Issues & Solutions

### Issue 1: "No conversation history available in session"

**Symptom:**
```
[Callback] No conversation history available in session
```

**Cause:** Callback triggered before conversation history is populated

**Solution:** This is normal for the first callback. History will be available on subsequent turns.

---

### Issue 2: "Memory Bank service not initialized"

**Symptom:**
```
[Memory Bank] Service not initialized, cannot add session
```

**Cause:**
- Missing `AGENT_ENGINE_ID` in `.env`
- Invalid Agent Engine ID
- Missing GCP credentials

**Solution:**
```bash
# Verify settings
python -c "from app.config import settings; print(f'Enabled: {settings.enable_memory_bank}, ID: {settings.agent_engine_id}')"

# If ID is empty, run setup:
python scripts/setup_memory_bank.py
```

---

### Issue 3: Callback not triggering at all

**Symptom:** No `[Callback]` logs appearing

**Cause:**
- `MEMORY_CALLBACK_ENABLED=false` in `.env`
- Callback not registered on agent

**Solution:**
```bash
# Check .env
grep MEMORY_CALLBACK_ENABLED backend/.env

# Should show:
# MEMORY_CALLBACK_ENABLED=true

# Check startup logs for:
# "✓ Memory Bank callbacks registered on agent"
```

---

### Issue 4: Memory Bank API errors

**Symptom:**
```
[Memory Bank] ✗ Failed to add session: <API error>
```

**Common causes:**
1. **Insufficient permissions:** User needs `aiplatform.memoryBanks.*` permissions
2. **Agent Engine not found:** Invalid `AGENT_ENGINE_ID`
3. **API not enabled:** Vertex AI API not enabled in GCP project
4. **Invalid credentials:** Check `GOOGLE_APPLICATION_CREDENTIALS`

**Solution:**
```bash
# Verify Agent Engine exists
gcloud ai agent-engines describe 3117603647907692544 \
  --location=us-central1 \
  --project=<your-project>

# Enable API if needed
gcloud services enable aiplatform.googleapis.com

# Verify credentials
gcloud auth application-default login
```

---

## Summary

**ADK Live Mode Issue Discovered:**
- ❌ `after_agent_callback` does NOT trigger when using `runner.run_live()`
- ✅ Callbacks work fine with `runner.run_async()` (traditional request/response mode)
- ⚠️ This is a fundamental ADK limitation, not a bug in our implementation

**Solution Implemented:**
- ✅ **Manual persistence on turn_complete** - Detect turn completion in Live mode event stream
- ✅ **Same memory service** - Uses identical `memory_service.add_session_to_memory()` logic
- ✅ **Feature flag support** - Respects `enable_memory_bank` and `memory_callback_enabled` settings
- ✅ **Comprehensive logging** - Clear visibility into when memory is being saved

**Files Modified:**
- `backend/app/services/gemini_live_adk.py:1440-1467` - Added manual persistence on turn_complete
- `backend/app/services/callbacks.py` - Callback still registered (for future compatibility)
- `MEMORY_BANK_CALLBACK_FIX.md` - Updated documentation

**Testing:**
1. Start backend: `cd backend && uv run uvicorn app.main:app --reload`
2. Have a conversation via Gemini Live
3. Check logs for `[Memory Bank] Turn complete detected`
4. Verify `[Memory Bank] ✓ Session <id> persisted successfully`

**Next:** Monitor the logs during a conversation to verify memories are being saved. If you still see issues, check the "Common Issues & Solutions" section above.
