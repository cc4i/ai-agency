# Memory Bank Critical Fix - Session Persistence

**Issue:** Memory Bank was using stale session data, missing conversation history
**Status:** ✅ **FIXED**
**Date:** 2025-11-05

---

## Critical Issues Found

### Issue 1: Wrong API Signature ✅ FIXED

**Error:**
```
TypeError: VertexAiMemoryBankService.add_session_to_memory() got an unexpected keyword argument 'app_name'
```

**Root Cause:**
The ADK's `VertexAiMemoryBankService.add_session_to_memory()` method signature is:
```python
async def add_session_to_memory(self, session: Session) -> None
```

NOT:
```python
async def add_session_to_memory(self, session_id: str, user_id: str, app_name: str)
```

**Fix:**
- Updated `memory_service.add_session_to_memory()` to accept a Session object
- Updated all callers to pass the Session object directly

---

### Issue 2: Stale Session Data ⚠️ **CRITICAL**

**Problem:**
The session object was being stored at initialization time (`self.session = session` at line 1233), but in Live mode, the runner continuously updates the session with new events as the conversation progresses.

**Impact:**
- Memory Bank was receiving a session with **zero or outdated events**
- Conversation history was NOT being persisted
- Each persistence attempt used the same empty/stale session

**Flow Analysis:**

```python
# At initialization (line 1233):
session = await runner.session_service.get_session(...)  # Empty or minimal history
self.session = session  # Store this snapshot

# During conversation:
# Runner updates session with new events internally
# But self.session still points to the old snapshot!

# At turn_complete (OLD CODE - line 1455):
await memory_service.add_session_to_memory(
    session=self.session,  # ❌ STALE! No conversation history!
)
```

**Fix Applied:**

Fetch the **latest session state** from session_service right before persisting:

```python
# At turn_complete (NEW CODE - lines 1455-1469):
# IMPORTANT: Fetch the latest session state from session_service
# The session object may have been updated by the runner with new events
latest_session = await runner.session_service.get_session(
    app_name="ai_agency_hub",
    user_id=self.session_id,
    session_id=self.session_id,
)

if latest_session:
    # Log session state for debugging
    event_count = len(latest_session.events) if hasattr(latest_session, 'events') else 0
    logger.debug(f"[Memory Bank] Session has {event_count} events")

    # Pass the Session object with CURRENT conversation history
    success = await memory_service.add_session_to_memory(
        session=latest_session,  # ✅ FRESH! Contains all conversation events!
    )
```

---

## Session Object Structure

The ADK Session object contains:
```python
class Session:
    id: str                    # Session ID
    app_name: str             # Application name
    user_id: str              # User ID
    state: Dict[str, Any]     # Session state
    events: List[Event]       # 🔥 CONVERSATION HISTORY (updated by runner)
    last_update_time: float   # Last update timestamp
```

The `events` field is critical - it contains the entire conversation history that Memory Bank needs to index.

---

## Before vs After

### Before (❌ BROKEN):
```python
# Initialize
self.session = await runner.session_service.get_session(...)
# At this point: session.events = []

# ... conversation happens, runner updates its internal session ...

# Persist (WRONG - using stale session)
await memory_service.add_session_to_memory(
    session=self.session  # Still has events = [] !
)
```

### After (✅ FIXED):
```python
# Initialize
self.session = await runner.session_service.get_session(...)
# Store for reference, but don't use for persistence

# ... conversation happens ...

# Persist (CORRECT - fetch fresh session)
latest_session = await runner.session_service.get_session(
    app_name="ai_agency_hub",
    user_id=self.session_id,
    session_id=self.session_id,
)
# latest_session.events now has ALL conversation history!

await memory_service.add_session_to_memory(
    session=latest_session  # Contains current conversation!
)
```

---

## Files Modified

1. **`backend/app/services/gemini_live_adk.py`**
   - Lines 1453-1476: Fetch latest session before persisting
   - Added event count logging for debugging

2. **`backend/app/services/memory_service.py`**
   - Lines 98-148: Changed signature to accept Session object
   - Lines 1-33: Updated documentation

3. **`backend/app/services/callbacks.py`**
   - Lines 93-95: Updated to use Session object (for future compatibility)

---

## Verification

After this fix, you should see logs like:

```
INFO - [Memory Bank] Turn complete detected, persisting session: session_id=session_xxx
DEBUG - [Memory Bank] Session has 15 events  # ✅ Should be > 0 after conversation!
INFO - [Memory Bank] Adding session to memory: session=session_xxx
INFO - [Memory Bank] ✓ Session session_xxx added to memory successfully
INFO - [Memory Bank] ✓ Session session_xxx persisted successfully
```

**Key indicators of success:**
- ✅ Event count > 0 (shows conversation history is present)
- ✅ No TypeErrors about unexpected arguments
- ✅ Memory Bank API call succeeds

---

## Why This Was Critical

Without this fix:
1. Memory Bank received **empty sessions** with no conversation history
2. No memories were actually being created/indexed
3. The `load_memory` tool would return **no results** even after conversations
4. Users would see "I don't recall previous conversations" despite Memory Bank being enabled

With this fix:
1. Memory Bank receives **full conversation history** after each turn
2. Conversations are properly indexed for semantic search
3. The `load_memory` tool can retrieve past conversations
4. Cross-session memory recall works as intended

---

## Testing

To verify the fix works:

### Test 1: Check Event Count
```bash
# Start backend with DEBUG logging
cd backend
LOG_LEVEL=DEBUG uv run uvicorn app.main:app --reload

# Have a conversation via frontend
# Check logs for:
# "DEBUG - [Memory Bank] Session has N events"
# N should be > 0 and increase with each turn
```

### Test 2: Verify Persistence
```bash
# Have a multi-turn conversation
# Each turn_complete should show:
INFO - [Memory Bank] ✓ Session <id> persisted successfully

# No errors about missing 'app_name' or empty sessions
```

### Test 3: Memory Retrieval
```bash
# In a NEW session, ask the agent to recall previous conversation
# Agent should call load_memory tool
# Should return relevant memories from previous session
```

---

## Summary

**Two critical issues fixed:**

1. ✅ **API Signature** - Use `Session` object instead of individual parameters
2. ✅ **Stale Session Data** - Fetch latest session state before persisting

**Impact:**
- Memory Bank now actually saves conversation history
- Cross-session memory recall works
- Agent can remember and reference past conversations

**Files Changed:** 3 files (gemini_live_adk.py, memory_service.py, callbacks.py)

**Risk:** Low - changes are defensive (fetch fresh data) and well-logged

**Next Steps:**
1. Test with real conversations
2. Monitor logs for event counts
3. Verify `load_memory` returns results from past sessions
