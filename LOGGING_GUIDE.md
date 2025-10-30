# Logging Guide - Debug Audio and Connection Issues

## 🆕 NEW: File-Based Logging

### Backend Logs → File
**Location**: `backend/logs/backend.log`

All backend logs now automatically write to both:
- **Console** (terminal output)
- **File** (`backend/logs/backend.log`)

**Access logs**:
```bash
# View last 100 lines
tail -n 100 backend/logs/backend.log

# View in real-time
tail -f backend/logs/backend.log

# Search for specific text
grep "Audio" backend/logs/backend.log

# Copy to desktop
cp backend/logs/backend.log ~/Desktop/backend-logs.txt
```

### Frontend Logs → Downloadable File
**New logger utility** accumulates all logs in memory and allows download.

**In browser console (F12)**:
```javascript
// Download logs as text file
logger.downloadLogs('text')

// Download logs as JSON file
logger.downloadLogs('json')

// View log count
logger.getLogCount()

// View last 10 logs
logger.getRecentLogs(10)

// Clear all logs
logger.clear()
```

**The logger is available globally** as `window.logger` for easy access.

## Improved Logging

### Backend Logs (with Session Context)

All backend logs now include:
- **Session ID**: First 8 characters to identify the conversation
- **Turn count**: Which turn in the conversation
- **Emoji icons**: Quick visual identification of log types

**Example**:
```
[Session: session_1...] [Turn: 1] 🔌 Establishing Gemini Live connection
[Session: session_1...] [Turn: 1] ✓ Gemini Live connection established
[Session: session_1...] [Turn: 1] 🔄 Turn 1 complete from frontend
[Session: session_1...] [Turn: 1] 🔇 Sent 500ms silence to signal turn complete
[Session: session_1...] [Turn: 1] 📨 Processing server content (audio/text)
[Session: session_1...] [Turn: 1] ✓ Gemini turn complete
```

### Frontend Logs (with Session Context)

All frontend console logs now include:
- **Session ID**: First 8 characters
- **Project ID**: Current project
- **Emoji icons**: Visual indicators

**Example**:
```
[Session: session_1...][Project: aura_smart_sneaker] [WebSocket] ✓ Connected to backend
[Session: session_1...][Project: aura_smart_sneaker] [Audio] ⬇ Received chunk: 12345 chars
[Session: session_1...][Project: aura_smart_sneaker] [Audio Context] Created with sample rate: 16000
[Session: session_1...][Project: aura_smart_sneaker] [Audio] PCM16 samples: 8000
[Session: session_1...][Project: aura_smart_sneaker] [Audio Queue] ▶ Playing buffer (duration: 0.50 s)
```

## Log Emoji Legend

### Backend (Python)
- 🔌 Connection establishing
- 🔗 Connecting to external service
- ✓ Success / Complete
- ✗ Error / Failed
- ⚠ Warning
- 📤 Sending data
- 📥 Receiving data
- 📨 Processing message
- 🔄 Turn transition
- 🔇 Silence/mute action
- 🔧 Tool/function call

### Frontend (TypeScript)
- ✓ Success
- ✗ Error
- ⚠ Warning
- ⬇ Receiving data
- ⬆ Sending data
- ▶ Playing audio
- ⏸ Pausing
- 🔄 Reconnecting

## Audio Issues - What to Look For

### Slow Motion Audio

**Symptoms**:
- Voice sounds slowed down
- Long pauses between words
- Robotic/distorted sound

**Logs to check**:
```
[Audio Context] Created with sample rate: XXXX
```

**Expected**: Should be `16000` (16kHz)

**If wrong**:
- Browser default sample rate (usually 44.1kHz or 48kHz)
- Creates sample rate mismatch
- Audio plays at wrong speed

**Fixed in**: `frontend/src/hooks/useWebSocket.ts:162,185`
```typescript
audioContextRef.current = new AudioContext({ sampleRate: 16000 });
```

### Only One Response

**Symptoms**:
- First response works fine
- Subsequent questions get no response
- WebSocket still shows "connected"

**Logs to check**:
```
[Session: ...] 🔌 Gemini Live connection closed: XXXX reason
[WebSocket] ✗ Disconnected (code: XXXX, reason: ...)
```

**Possible causes**:
1. **Silence frames breaking connection** - Backend sends silence to signal turn complete
2. **Gemini API rate limiting** - Too many requests too quickly
3. **Invalid message format** - Sending wrong message type
4. **Connection timeout** - No activity for too long

**Debug steps**:
1. Check backend logs for connection close reason
2. Check frontend logs for WebSocket disconnect
3. Look for errors between turns
4. Verify audio is still being sent

### No Audio Playback

**Symptoms**:
- Text responses appear
- No sound from speaker
- Audio queue shows buffers

**Logs to check**:
```
[Audio Queue] Added to queue, total buffers: X
[Audio Queue] ▶ Playing buffer (duration: X.XX s)
```

**If you see "Added" but not "Playing"**:
- Check `isPlayingRef.current` state
- Verify `playNextAudioBuffer()` is called
- Check browser audio permissions

**If duration is 0.00s**:
- Audio buffer is empty/corrupt
- Check PCM16 conversion

## Common Error Codes

### WebSocket Close Codes

- **1000**: Normal closure (clean disconnect)
- **1001**: Going away (page refresh/close)
- **1006**: Abnormal closure (no close frame)
- **1007**: Invalid frame payload data (bad message format)
- **1008**: Policy violation
- **1011**: Internal server error

### What Each Means

**1007 - Invalid frame payload**:
```
✗ Gemini Live connection closed: 1007 Request contains an invalid argument
```

**Cause**: Sent invalid message format to Gemini API

**Solution**: Check message structure matches API docs

**1006 - Abnormal closure**:
```
✗ Disconnected (code: 1006, reason: )
```

**Cause**: Connection dropped without proper close handshake

**Possible reasons**:
- Network issue
- Server crashed
- Timeout
- API quota exceeded

## Debugging Workflow

### Step 1: Check Session Context

Look for session ID in logs:
```bash
# Backend
grep "Session: session_" logs.txt

# Frontend
# Open browser console, filter by session ID
```

### Step 2: Follow Audio Flow

**Expected flow**:
1. Frontend: `[VAD] Voice detected`
2. Frontend: `[WebSocket] Sending audio chunk`
3. Backend: `📤 Sent X bytes audio`
4. Backend: `📥 Gemini message keys: ['serverContent']`
5. Backend: `📨 Processing server content`
6. Frontend: `[Audio] ⬇ Received chunk`
7. Frontend: `[Audio Queue] ▶ Playing buffer`
8. Frontend: `[Audio Queue] ✓ Queue empty, producer finished`

**If flow breaks**:
- Note where it stops
- Check for errors in that component
- Look for WebSocket disconnect

### Step 3: Check Turn Cycle

**Complete turn cycle**:
1. User speaks
2. VAD detects voice
3. Audio sent to Gemini
4. User stops (silence detected)
5. `turn_complete` sent
6. Gemini responds
7. Audio plays back
8. Next turn ready

**If cycle breaks**:
```bash
# Look for turn count progression
grep "Turn:" logs.txt

# Should increment: Turn: 1, Turn: 2, Turn: 3...
# If stuck at Turn: 1, connection issue
```

### Step 4: Audio Playback Check

**In browser console**:
```javascript
// Check AudioContext state
audioContext.state  // Should be "running"

// Check queue
audioQueueRef.current.length  // Should increase when receiving

// Check playback
isPlayingRef.current  // Should be true during playback
```

## Troubleshooting Commands

### Backend

```bash
# Start with debug logging
cd backend
LOG_LEVEL=DEBUG uv run uvicorn app.main:app --reload

# Watch logs in real-time
tail -f logs/*.log | grep -E "Session|Turn|Gemini"

# Count turns per session
grep "Turn:" logs/*.log | cut -d']' -f2 | sort | uniq -c
```

### Frontend

```bash
# Start dev server
cd frontend
npm run dev

# In browser console:
# - Open DevTools (F12)
# - Go to Console tab
# - Filter by "Session" to see all session logs
# - Filter by "Audio" to see audio processing
# - Filter by "WebSocket" to see connection
```

## Log Files

**Backend**: Logs to stdout (terminal) by default

**Frontend**: Browser console only

**To save logs**:

Backend:
```bash
uv run uvicorn app.main:app --reload 2>&1 | tee backend.log
```

Frontend:
- Right-click in console → "Save as..."
- Or copy from console

## Common Issues and Their Logs

### Issue: Slow motion audio

**Logs**:
```
[Audio Context] Created with sample rate: 48000
[Audio] ✓ PCM buffer created, duration: 0.50 s
```

**Problem**: Sample rate is 48000, not 16000

**Fix**: Already fixed, restart frontend

### Issue: No response after first turn

**Logs**:
```
[Session: ...] [Turn: 1] ✓ Gemini turn complete
[Session: ...] [Turn: 2] 🔄 Turn 2 complete from frontend
[Session: ...] 🔌 Gemini Live connection closed: 1006
```

**Problem**: Connection closes after turn 1

**Debug**: Check what happened between turn complete and disconnect

### Issue: Connection keeps reconnecting

**Logs**:
```
[WebSocket] ✓ Connected to backend
[WebSocket] ✗ Disconnected (code: 1006, reason: )
[WebSocket] 🔄 Attempting to reconnect...
```

**Problem**: Backend or Gemini API connection unstable

**Check**:
1. API key valid?
2. Network connection stable?
3. Backend running?

## Next Steps if Still Broken

1. **Capture full logs**:
   - Backend: Save terminal output
   - Frontend: Save console output
   - Include session ID

2. **Note exact behavior**:
   - What works?
   - What doesn't?
   - When does it break?

3. **Check network**:
   - Browser DevTools → Network tab
   - Look for failed requests
   - Check WebSocket frame data

4. **Test minimal case**:
   - Say one word
   - Wait for response
   - Say another word
   - Check logs between each step
