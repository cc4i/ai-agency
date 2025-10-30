# Turn Complete Fix - No Response from Model

## Problems Fixed

### 1. Model Not Responding (Interrupted)
Gemini Live was not responding to user input because it never received a signal that the user had finished speaking. The logs showed:
```
Model turn was interrupted
```

### 2. Invalid Argument Error (1007)
After attempting to fix #1, got WebSocket error:
```
ERROR - Gemini Live connection closed: 1007 Request contains an invalid argument.
```

This happened because we sent an invalid `turn_complete` message format.

## Root Causes

### Problem 1: No Turn Signal
In Gemini Live API, there are two ways to send content:
1. **realtime_input**: Streams audio chunks as they're captured
2. **client_content with turn_complete**: For text messages only

The original implementation only sent `realtime_input` without signaling end of turn.

### Problem 2: Invalid Message Format
First attempted fix sent:
```json
{
  "client_content": {
    "turn_complete": true
  }
}
```

**This is INVALID**. The `turn_complete` field can ONLY be used with text `turns`, not for audio streaming.

### Problem 3: VAD Filtering Silence
Our Voice Activity Detection (VAD) filters out silence on the frontend, so Gemini never receives the silence it needs to detect natural pauses.

## Solution

Implemented a complete turn-taking flow:

### 1. Frontend: Silence Duration Tracking

**File**: `frontend/src/hooks/useMicrophone.ts`

Added silence duration tracking to detect when the user stops speaking:

```typescript
// Track silence start time
const silenceStartRef = useRef<number | null>(null);

// In audio processing loop
if (rms < vadThreshold) {
  // Silence detected
  if (isSpeaking) {
    if (!silenceStartRef.current) {
      silenceStartRef.current = Date.now();
    } else {
      const silenceDurationMs = Date.now() - silenceStartRef.current;

      // After 1.5 seconds of silence, mark turn complete
      if (silenceDurationMs >= 1500 && !turnCompleteSent) {
        turnCompleteSent = true;
        onTurnComplete(); // Notify
      }
    }
  }
}
```

**Key parameters**:
- `vadThreshold`: 0.02 (increased from 0.01 to reduce false positives)
- `silenceDuration`: 1500ms (1.5 seconds)

### 2. Frontend: Turn Complete Signaling

**File**: `frontend/src/hooks/useWebSocket.ts`

Added function to send turn complete signal:

```typescript
const sendTurnComplete = useCallback(() => {
  console.log('[Turn Complete] Sending turn_complete signal to backend');
  if (wsRef.current?.readyState === WebSocket.OPEN) {
    wsRef.current.send(JSON.stringify({ type: 'turn_complete' }));
  }
}, []);
```

### 3. Backend: Turn Complete Handling

**File**: `backend/app/services/gemini_live.py`

Added handler for turn complete message:

```python
elif message_type == "turn_complete":
    # User finished speaking - signal to Gemini
    logger.info("Received turn_complete from frontend")
    if self.gemini_ws:
        await self._send_turn_complete()
```

Added function to send **silence frames** (CORRECT approach for audio):

```python
async def _send_turn_complete(self) -> None:
    """
    Send turn complete signal via silence frames.

    Since we use VAD and filter silence, Gemini needs explicit
    silence frames to detect turn completion.
    """
    # Generate 500ms of silence (16kHz, mono, PCM16 = 8000 samples)
    silence_samples = 8000
    silence_bytes = bytes(silence_samples * 2)  # 16-bit = 2 bytes/sample
    silence_b64 = base64.b64encode(silence_bytes).decode('utf-8')

    # Send silence as realtime_input (NOT client_content)
    message = {
        "realtime_input": {
            "media_chunks": [
                {"data": silence_b64, "mime_type": "audio/pcm"}
            ]
        }
    }
    await self.gemini_ws.send(json.dumps(message))
    logger.info("Sent silence frames to signal turn complete")
```

**Why this works**:
- Sends actual audio data (silence) via `realtime_input`
- Gemini's built-in VAD detects the silence and knows the turn is complete
- No invalid API messages

### 4. Wiring: Connect Everything

**File**: `frontend/src/components/WorkspaceClient.tsx`

Connected the callbacks:

```typescript
const { sendAudio, sendTurnComplete } = useWebSocket(sessionId, projectId);

const { isRecording, toggleRecording } = useMicrophone({
  onAudioData: sendAudio,
  onTurnComplete: sendTurnComplete, // ✓ Connected
  vadThreshold: 0.02,
  silenceDuration: 1500,
});
```

## How It Works Now

### Complete Flow:

1. **User starts speaking**:
   - VAD detects voice (RMS > 0.02)
   - Audio chunks sent to backend as `realtime_input`
   - Backend forwards to Gemini Live

2. **User stops speaking**:
   - VAD detects silence (RMS < 0.02)
   - Silence timer starts

3. **After 1.5 seconds of silence**:
   - Frontend: Calls `onTurnComplete()`
   - Frontend: Sends `{ type: 'turn_complete' }` to backend
   - Backend: Sends `{ client_content: { turn_complete: true } }` to Gemini
   - **Gemini knows it's safe to respond**

4. **Gemini responds**:
   - Sends audio chunks back
   - `producerSpeaking` state set to `true`
   - User audio transmission paused (turn-taking)

5. **Gemini finishes**:
   - Audio queue empties
   - `producerSpeaking` set to `false`
   - User can speak again

## Console Logs to Verify

### ✅ Successful Flow:

```
[VAD] Voice detected, starting transmission (RMS: 0.0234)
[WebSocket] Sending audio chunk...
[VAD] Silence started (RMS: 0.0089)
[Turn Complete] Silence duration: 1502 ms
[Turn Complete] Sending turn_complete signal to backend
[Audio] Received audio chunk from Gemini
[Audio Queue] Playing buffer, queue size: 3
[Turn-Taking] Gemini speaking, pausing user audio
[Audio Queue] Queue empty, producer finished speaking
```

### ❌ Problem (Before Fix):

```
[VAD] Voice detected, starting transmission
[WebSocket] Sending audio chunk...
[VAD] Voice detected, starting transmission
[WebSocket] Sending audio chunk...
(continuous, never stops)
Backend: Model turn was interrupted
```

## Testing

1. Start backend and frontend
2. Click microphone button
3. Say: "Hello, tell me about the Aura sneaker"
4. **Stop speaking and wait 1.5 seconds**
5. Check console for `[Turn Complete]` log
6. Gemini should respond within 2-3 seconds

## Configuration

Adjust these parameters in `WorkspaceClient.tsx` if needed:

```typescript
const microphone = useMicrophone({
  vadThreshold: 0.02,      // Higher = less sensitive (0.01-0.05)
  silenceDuration: 1500,   // ms to wait before turn complete (1000-2000)
});
```

**If Gemini responds too quickly**:
- Increase `silenceDuration` to 2000ms
- User has more time to pause mid-sentence

**If Gemini takes too long to respond**:
- Decrease `silenceDuration` to 1000ms
- Faster turn-taking but might cut off pauses

**If background noise triggers false starts**:
- Increase `vadThreshold` to 0.03 or 0.04
- Reduces sensitivity to quiet sounds

## API Reference

### Gemini Live Message Types

**✅ CORRECT: Sending audio chunks**:
```json
{
  "realtime_input": {
    "media_chunks": [
      { "data": "base64...", "mime_type": "audio/pcm" }
    ]
  }
}
```

**✅ CORRECT: Signaling turn complete for audio (send silence)**:
```json
{
  "realtime_input": {
    "media_chunks": [
      { "data": "AAAAAAA...", "mime_type": "audio/pcm" }
    ]
  }
}
```
*Where data is base64-encoded silence (zeros)*

**❌ INVALID: Standalone turn_complete (DO NOT USE)**:
```json
{
  "client_content": {
    "turn_complete": true
  }
}
```
*This will cause 1007 "invalid argument" error*

**✅ CORRECT: Sending text with turn complete**:
```json
{
  "client_content": {
    "turns": [
      { "role": "user", "parts": [{ "text": "Hello" }] }
    ],
    "turn_complete": true
  }
}
```
*turn_complete is ONLY valid when sending text turns*

## Related Documentation

- [AUDIO_IMPROVEMENTS.md](../frontend/AUDIO_IMPROVEMENTS.md) - VAD and audio quality fixes
- [SETUP_API_KEYS.md](backend/SETUP_API_KEYS.md) - API key configuration
- [Gemini Live API Docs](https://ai.google.dev/gemini-api/docs/live-api) - Official documentation

## Future Improvements

- [ ] Add visual indicator showing when turn complete is sent
- [ ] Add manual "I'm done speaking" button as fallback
- [ ] Add dynamic silence duration based on speech cadence
- [ ] Add barge-in support (interrupt Gemini mid-response)
