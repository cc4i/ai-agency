# Gemini Live Session Extension Fix

## Problem

When Gemini Live sessions approach expiration (after ~30 minutes), the API sends a `go_away` message with a `time_left` countdown. The session extension logic was causing `ConnectionClosedOK` exceptions to be logged as errors.

### Error Log
```
ERROR - [Session: session_...] [Turn: 25] ✗ Gemini to Frontend error: sent 1000 (OK); then received 1000 (OK)
websockets.exceptions.ConnectionClosedOK: sent 1000 (OK); then received 1000 (OK)
```

### Root Cause

**Before:**
1. `go_away` message received in receive loop
2. `_extend_session()` scheduled as background task (`asyncio.create_task`)
3. Background task closes old session while receive loop still active
4. Old session's WebSocket closes with code 1000 (normal close)
5. Receive loop raises `ConnectionClosedOK` exception
6. Exception logged as ERROR and breaks session

## Solution

### 1. Synchronous Session Extension
**File**: `gemini_live.py:867-876`

**Before:**
```python
if hasattr(response, 'go_away') and response.go_away:
    # Schedule reconnection before expiration
    asyncio.create_task(self._extend_session())  # ❌ Background task
```

**After:**
```python
if hasattr(response, 'go_away') and response.go_away:
    # Extend session synchronously and break from receive loop
    await self._extend_session()  # ✅ Synchronous
    # Break from receive loop to restart with new session
    self._log("info", "🔄 Breaking receive loop to use new session")
    break
```

**Why This Works:**
- Extends session synchronously before continuing
- Breaks cleanly from receive loop
- Outer `while self.is_connected:` loop restarts with new session
- No race condition between close and receive

### 2. Handle ConnectionClosedOK Gracefully
**File**: `gemini_live.py:952-974`

**Before:**
```python
except Exception as e:
    # All exceptions logged as errors
    self._log("error", f"✗ Gemini to Frontend error: {e}")
    self.is_connected = False  # ❌ Breaks session
```

**After:**
```python
except Exception as e:
    # Handle normal WebSocket close during session extension
    if "ConnectionClosedOK" in str(type(e).__name__) or "1000 (OK)" in error_msg:
        self._log("info", "🔄 WebSocket closed normally (likely during session extension)")
        # Don't break the main loop - let it continue and restart
        pass  # ✅ Continue while loop

    # Other errors still break the session
    elif "1011" in error_msg:
        # ... error handling
        self.is_connected = False
    else:
        # ... error handling
        self.is_connected = False
```

**Why This Works:**
- `ConnectionClosedOK` (code 1000) is a normal close, not an error
- Doesn't set `is_connected = False`
- Allows while loop to continue and restart with new session
- Only actual errors break the session

## Flow Diagram

### Before (Broken)
```
┌─────────────────────────────────────────────────────────────┐
│ Receive Loop Active                                         │
│   async for response in session.receive():                  │
│     if go_away:                                             │
│       asyncio.create_task(_extend_session())  ← Background  │
│     # Loop continues...                                     │
└─────────────────────────────────────────────────────────────┘
                    ↓ (race condition)
┌─────────────────────────────────────────────────────────────┐
│ Background Task                                             │
│   _extend_session():                                        │
│     session.__aexit__()  ← Closes WebSocket                │
└─────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────┐
│ Receive Loop Still Active                                   │
│   response = await session.receive()                        │
│   ✗ ConnectionClosedOK: 1000 (OK)  ← ERROR logged          │
│   ✗ is_connected = False           ← Session dies          │
└─────────────────────────────────────────────────────────────┘
```

### After (Fixed)
```
┌─────────────────────────────────────────────────────────────┐
│ Receive Loop Active                                         │
│   async for response in session.receive():                  │
│     if go_away:                                             │
│       await _extend_session()  ← Synchronous               │
│       break                    ← Exit receive loop         │
└─────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────┐
│ Session Extension                                           │
│   _extend_session():                                        │
│     session.__aexit__()  ← Closes old session              │
│     new_session = connect(resume_handle)                    │
│     self.gemini_session = new_session                       │
└─────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────┐
│ While Loop Restarts                                         │
│   while self.is_connected:  ← Still True                    │
│     async for response in new_session.receive():            │
│       # Continue with new session ✅                        │
└─────────────────────────────────────────────────────────────┘
```

## Expected Behavior

### Before Fix
```
[Turn: 25] ⏰ Session expiring in 60s - will reconnect with resumption...
[Turn: 25] 🔄 Extending session with resumption...
[Turn: 25] ✓ Session extended successfully
[Turn: 25] ✗ Gemini to Frontend error: sent 1000 (OK); then received 1000 (OK)  ← ERROR
```

### After Fix
```
[Turn: 25] ⏰ Session expiring in 60s - will reconnect with resumption...
[Turn: 25] 🔄 Extending session with resumption...
[Turn: 25] ✓ Session extended successfully
[Turn: 25] 🔄 Breaking receive loop to use new session
[Turn: 25] 🎧 Starting new listener for Gemini responses...  ← Clean restart
```

If ConnectionClosedOK still occurs (unlikely):
```
[Turn: 25] 🔄 WebSocket closed normally (likely during session extension)  ← INFO not ERROR
[Turn: 25] 🎧 Starting new listener for Gemini responses...  ← Session continues
```

## Testing

### Reproduce Issue
1. Start Gemini Live session
2. Keep session active for ~25-30 minutes
3. Wait for `go_away` message
4. Observe logs during extension

### Verify Fix
1. Session extends without errors
2. Conversation continues seamlessly
3. No `ConnectionClosedOK` errors logged
4. Turn counter continues incrementing

## Session Resumption Notes

### How It Works
1. Gemini sends `setup_complete` with session `handle` (captured at line 864)
2. Before expiration, Gemini sends `go_away` with `time_left`
3. Client calls `:connect` with `resume_handle` parameter
4. New session resumes conversation state from old session

### What's Preserved
- ✅ Conversation history
- ✅ Turn state
- ✅ Context

### What's NOT Preserved (Known Issue)
- ⚠️ Function calling tools may not be preserved
- ⚠️ System instructions may not be preserved
- See warnings in `gemini_live.py:596-598`

### Alternative (If Resumption Fails)
- Don't use resumption, start fresh session
- Loss of conversation history
- But tools will work correctly

## Related Files

**Modified:**
- `app/services/gemini_live.py:867-876` - Synchronous extension + break
- `app/services/gemini_live.py:952-974` - Handle ConnectionClosedOK

**Referenced:**
- `app/services/gemini_live.py:559-583` - `_extend_session()` method
- `app/services/gemini_live.py:585-674` - `_connect_to_gemini_live()` method

## References

- [WebSocket Close Codes](https://developer.mozilla.org/en-US/docs/Web/API/CloseEvent/code)
- Code 1000 = Normal close (not an error)
- Code 1011 = Internal server error (actual error)
