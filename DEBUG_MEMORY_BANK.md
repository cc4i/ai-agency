# Memory Bank Debugging Guide

**Issue:** Logs show "Session persisted successfully" but nothing appears in Cloud Console
**Status:** 🔍 **INVESTIGATING**
**Date:** 2025-11-05

---

## Root Cause Analysis

After examining the `VertexAiMemoryBankService.add_session_to_memory()` source code, found:

```python
events = []
for event in session.events:
  if _should_filter_out_event(event.content):
    continue
  if event.content:
    events.append({'content': event.content.model_dump(...)})

if events:
  # Actually persist to Memory Bank API
  client.agent_engines.memories.generate(...)
else:
  logger.info('No events to add to memory.')  # ← Silent failure!
```

**Critical Discovery:** If `session.events` is empty or events don't have `content`, the method returns silently without error!

---

## Hypothesis

**In Live mode (`run_live()`), the runner may not populate `session.events` the same way as in request/response mode (`run_async()`).**

This would explain:
- ✅ No errors (method completes successfully)
- ❌ No data in Cloud Console (nothing actually persisted)
- ❌ Silent failure (no events to persist)

---

## Diagnostic Logs Added

### In `memory_service.py` (lines 132-163):

```python
logger.info(f"[Memory Bank] Session has {event_count} events")
logger.info(f"[Memory Bank] Events with content: {events_with_content}/{event_count}")

if event_count == 0:
    logger.error("[Memory Bank] ⚠️ Session has ZERO events - nothing to persist!")
    return False

if events_with_content == 0:
    logger.error("[Memory Bank] ⚠️ Session has events but ZERO have content - nothing to persist!")
    return False
```

### In `gemini_live_adk.py` (lines 1464-1477):

```python
event_count = len(latest_session.events)
logger.info(f"[Memory Bank] Retrieved session has {event_count} events")
logger.info(f"[Memory Bank] Events with content: {events_with_content}/{event_count}")
```

---

## Testing Instructions

### Step 1: Enable DEBUG Logging

```bash
# In backend/.env
LOG_LEVEL=DEBUG

# Or start backend with:
LOG_LEVEL=DEBUG uv run uvicorn app.main:app --reload
```

### Step 2: Have a Conversation

1. Start the backend
2. Connect via frontend
3. Have a 2-3 turn conversation via voice
4. Watch the logs carefully

### Step 3: Check Logs

Look for these log patterns after each `turn_complete`:

**Expected logs if working:**
```
INFO - [Memory Bank] Turn complete detected, persisting session: session_id=session_xxx
INFO - [Memory Bank] Retrieved session has 5 events  # ← Should be > 0!
INFO - [Memory Bank] Events with content: 5/5  # ← Should be > 0!
INFO - [Memory Bank] Session has 5 events
INFO - [Memory Bank] Events with content: 5/5
INFO - [Memory Bank] ✓ Session session_xxx added to memory successfully
```

**If broken (current state):**
```
INFO - [Memory Bank] Turn complete detected, persisting session: session_id=session_xxx
INFO - [Memory Bank] Retrieved session has 0 events  # ❌ ZERO EVENTS!
ERROR - [Memory Bank] ⚠️ Session has ZERO events - nothing to persist!
WARNING - [Memory Bank] ⚠ Session session_xxx persistence skipped
```

**OR:**
```
INFO - [Memory Bank] Retrieved session has 10 events  # Has events
INFO - [Memory Bank] Events with content: 0/10  # ❌ But no content!
ERROR - [Memory Bank] ⚠️ Session has events but ZERO have content - nothing to persist!
```

---

## Possible Findings

### Finding 1: Session has 0 events

**Meaning:** In Live mode, the runner doesn't populate `session.events` automatically.

**Solution Options:**
1. Manually add events to session as conversation happens
2. Use a different approach to track conversation history
3. Check if there's a Runner flag to enable event tracking in Live mode
4. Build conversation history from the live event stream instead

### Finding 2: Events exist but have no content

**Meaning:** Live mode events have a different structure than expected.

**Solution:** Need to check what's in the events and convert them to the format Memory Bank expects.

### Finding 3: Events exist and have content

**Meaning:** Something else is wrong (permissions, Memory Bank setup, etc.)

**Next Steps:**
1. Check Cloud Console for Memory Bank logs
2. Verify Agent Engine permissions
3. Check if memories are being created but not visible

---

## Alternative Approaches to Consider

### Option 1: Track Conversation Manually

Instead of relying on session.events, manually build conversation history:

```python
# Store conversation messages as they happen
conversation_history = []

# When processing transcripts
conversation_history.append({
    'role': 'user',
    'content': user_transcript
})
conversation_history.append({
    'role': 'assistant',
    'content': assistant_transcript
})

# At turn_complete, create events from history
for msg in conversation_history:
    event = Event(content=Content(parts=[Part(text=msg['content'])]))
    session.events.append(event)
```

### Option 2: Use Memory Bank API Directly

Instead of using `VertexAiMemoryBankService.add_session_to_memory()`, call the Memory Bank API directly with conversation text:

```python
client = memory_service._get_api_client()
operation = client.agent_engines.memories.generate(
    name=f'reasoningEngines/{agent_engine_id}',
    direct_contents_source={
        'events': [
            {'content': {'role': 'user', 'parts': [{'text': 'user message'}]}},
            {'content': {'role': 'model', 'parts': [{'text': 'assistant response'}]}}
        ]
    },
    scope={'app_name': 'ai_agency_hub', 'user_id': user_id}
)
```

### Option 3: Disable Live Mode Memory, Use Periodic Snapshots

Instead of persisting after each turn in Live mode, periodically snapshot the conversation:

```python
# Every N turns or every M minutes
if should_snapshot():
    # Reconstruct conversation from Redis/logs
    conversation = await get_conversation_from_redis(session_id)
    # Manually create session with events
    await persist_conversation_snapshot(conversation)
```

---

## Next Actions

1. **Run the backend with DEBUG logging** and have a conversation
2. **Examine the logs** to see event count and content
3. **Report findings** - which scenario (0 events, events without content, or something else)
4. **Based on findings**, implement the appropriate solution

---

## Files Modified for Debugging

- `backend/app/services/memory_service.py:132-163` - Added event validation and logging
- `backend/app/services/gemini_live_adk.py:1464-1477` - Added session state logging

These changes will help diagnose the exact issue before implementing a fix.
