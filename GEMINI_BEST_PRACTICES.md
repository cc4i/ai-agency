# Gemini Live API Best Practices (Learned from Google's Official Examples)

## Critical Lessons from Google's Reference Implementations

### 1. **DO NOT Send Explicit Turn Complete Messages for Audio**

**❌ WRONG** (causes 1007 errors):
```python
# Backend
message = {
    "client_content": {
        "turn_complete": True  # INVALID for audio!
    }
}
```

**❌ WRONG** (also causes 1007 errors):
```python
# Sending silence frames
message = {
    "realtime_input": {
        "media_chunks": [
            {"data": silence_base64, "mime_type": "audio/pcm"}
        ]
    }
}
```

**✅ CORRECT**:
```python
# Do nothing! Gemini Live has built-in VAD (Voice Activity Detection)
# It automatically detects when you stop speaking from silence in the audio stream
```

### 2. **Send ALL Audio (Including Silence)**

**❌ WRONG**:
```typescript
// Frontend VAD filtering
if (rms < threshold) {
  return; // Don't send silence
}
onAudioData(pcm16.buffer);
```

**✅ CORRECT**:
```typescript
// Always send audio - Gemini needs silence to detect turn completion
onAudioData(pcm16.buffer);
```

**Why**: Gemini's VAD analyzes the complete audio stream. If you filter silence on the frontend, Gemini never sees the pause and doesn't know when to respond.

### 3. **Audio Format**

**Google's Implementation**:
- Sample Rate: **16000 Hz** (16 kHz)
- Format: **PCM16** (16-bit linear PCM)
- Channels: **Mono** (1 channel)
- Encoding: Base64 for WebSocket transmission

**Message Format**:
```json
{
  "realtime_input": {
    "media_chunks": [
      {
        "data": "base64_encoded_pcm16_data",
        "mime_type": "audio/pcm"
      }
    ]
  }
}
```

### 4. **Audio Playback**

**Google's Pattern**:
```typescript
// Use AudioStreamer class for queueing
audioStreamer.addPCM16(new Uint8Array(audioData));

// AudioContext must match the incoming sample rate
const audioContext = new AudioContext({ sampleRate: 16000 });
```

### 5. **Connection Lifecycle**

**Google's Pattern**:
```typescript
const client = new GenAILiveClient();

// Event-driven architecture
client
  .on("open", onOpen)
  .on("close", onClose)
  .on("error", onError)
  .on("audio", onAudio)
  .on("interrupted", stopAudioStreamer);

// Cleanup
return () => {
  client
    .off("open", onOpen)
    .off("close", onClose)
    // ... remove all listeners
    .disconnect();
};
```

### 6. **React StrictMode Handling**

**Issue**: React 18 StrictMode mounts components twice in development

**Google's Solution**: Proper cleanup in useEffect return
```typescript
useEffect(() => {
  connect();

  return () => {
    disconnect(); // Always cleanup
  };
}, [/* stable dependencies */]);
```

**Our Fix**:
```typescript
// Only depend on sessionId and projectId (stable values)
// Don't depend on connect/disconnect functions
useEffect(() => {
  if (sessionId && projectId) {
    connect();
  }
  return () => disconnect();
}, [sessionId, projectId]);
```

### 7. **Turn-Taking**

**Pattern**:
```typescript
// Don't send audio when model is speaking
if (isModelSpeaking) {
  return; // Pause user audio
}

// Send user audio
onAudioData(audioBuffer);
```

## Common Mistakes We Made

### Mistake 1: Frontend VAD Filtering
```typescript
// ❌ WRONG: Filtered silence on frontend
if (rms < vadThreshold) {
  return; // Don't send
}
```

**Fix**: Send all audio, let Gemini's VAD handle it

### Mistake 2: Explicit Turn Complete Messages
```python
# ❌ WRONG: Sent turn_complete message
message = {"client_content": {"turn_complete": True}}
```

**Fix**: Do nothing, Gemini auto-detects from silence

### Mistake 3: Sending Silence Frames
```python
# ❌ WRONG: Sent explicit silence
silence = bytes(8000 * 2)
message = {"realtime_input": {"media_chunks": [...]}}
```

**Fix**: Frontend sends real silence from microphone, no need to inject

### Mistake 4: Sample Rate Mismatch
```typescript
// ❌ WRONG: Used browser default
const audioContext = new AudioContext(); // 44.1kHz or 48kHz
```

**Fix**: Force 16kHz
```typescript
const audioContext = new AudioContext({ sampleRate: 16000 });
```

### Mistake 5: Multiple Connections
```typescript
// ❌ WRONG: useEffect dependencies caused reconnections
useEffect(() => {
  connect();
  return () => disconnect();
}, [connect, disconnect]); // These change every render!
```

**Fix**: Stable dependencies
```typescript
useEffect(() => {
  if (sessionId && projectId) connect();
  return () => disconnect();
}, [sessionId, projectId]); // Only change when IDs change
```

## Our Updated Architecture

### Backend
```python
# gemini_live.py

# 1. Send audio chunks as-is
async def _send_audio_to_gemini(self, audio_base64: str):
    message = {
        "realtime_input": {
            "media_chunks": [
                {"data": audio_base64, "mime_type": "audio/pcm"}
            ]
        }
    }
    await self.gemini_ws.send(json.dumps(message))

# 2. Do NOT send turn_complete
async def _send_turn_complete(self):
    # DEPRECATED - Gemini's VAD handles it
    pass

# 3. Process responses
async def _process_server_content(self, content):
    if "modelTurn" in content:
        for part in content["modelTurn"].get("parts", []):
            if "inlineData" in part:
                audio_b64 = part["inlineData"]["data"]
                await self._send_audio_to_frontend(audio_b64)
```

### Frontend
```typescript
// useMicrophone.ts

// 1. Disable frontend VAD
const { isRecording } = useMicrophone({
  onAudioData: sendAudio,
  vadEnabled: false, // Let Gemini handle it
  sampleRate: 16000,
});

// 2. Send all audio
processor.onaudioprocess = (e) => {
  const inputData = e.inputBuffer.getChannelData(0);

  // Turn-taking only (don't filter silence)
  if (isModelSpeaking) return;

  // Convert and send ALL audio
  const pcm16 = convertToPCM16(inputData);
  onAudioData(pcm16.buffer);
};

// useWebSocket.ts

// 3. Force 16kHz for playback
const audioContext = new AudioContext({ sampleRate: 16000 });

// 4. Create buffer with matching sample rate
const audioBuffer = audioContext.createBuffer(
  1,
  float32.length,
  audioContext.sampleRate // Must match!
);
```

## Testing Checklist

- [ ] No `/ws//` errors in backend logs
- [ ] Only 1-2 WebSocket connections (StrictMode remount is OK)
- [ ] Audio plays at normal speed (not slow motion)
- [ ] Can have multiple conversation turns
- [ ] No 1007 "invalid argument" errors
- [ ] Connection stays open between turns
- [ ] Backend logs show turn count incrementing
- [ ] Sample rate is 16000 Hz in console logs

## Key Takeaways

1. **Trust Gemini's VAD** - It's designed for this
2. **Send continuous audio stream** - Don't filter or modify
3. **No explicit turn signals** - Silence is the signal
4. **Match sample rates** - 16kHz everywhere
5. **Clean up properly** - Prevent multiple connections
6. **Event-driven > Polling** - Use WebSocket events

## References

- [Google's Jupyter Notebook](https://github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/multimodal-live-api/intro_live_api_native_audio.ipynb)
- [Google's Web Console](https://github.com/google-gemini/live-api-web-console)
- [Gemini Live API Docs](https://ai.google.dev/gemini-api/docs/live-api)
