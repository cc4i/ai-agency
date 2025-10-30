# Audio Playback Fix - Gapless & Noise-Free

## Problem
Audio from Gemini Live was playing back with:
- **Choppy/stuttering sound** - Gaps between audio chunks
- **Noise/artifacts** - Potential byte order issues
- **Not smooth** - Inconsistent playback timing

## Root Causes

### 1. **Gaps Between Audio Chunks**
**Old approach:**
```typescript
source.start();
source.onended = () => {
  playNextAudioBuffer(); // Gap here!
};
```

**Problem**: Using `onended` callbacks creates small gaps between chunks because:
- Callback execution takes time
- Next buffer starts AFTER previous buffer ends
- Results in ~5-10ms gaps that sound like clicks/pops

### 2. **No AudioContext State Handling**
```typescript
// Old code didn't check if suspended
const audioContext = new AudioContext({ sampleRate: 16000 });
```

**Problem**: Browser autoplay policies can suspend AudioContext, preventing playback.

### 3. **Potential Byte Order Issues**
```typescript
// Old code - direct conversion
const pcm16 = new Int16Array(bytes.buffer);
```

**Problem**: Doesn't explicitly handle endianness, might cause distortion on some systems.

## Solutions Implemented

### 1. **Gapless Playback with Scheduled Timing**

**New approach:**
```typescript
const currentTime = audioContextRef.current.currentTime;
const playTime = Math.max(currentTime, nextPlayTimeRef.current);

source.start(playTime);

// Schedule next chunk to start exactly when this one ends
nextPlayTimeRef.current = playTime + audioBuffer.duration;
```

**Benefits:**
- ✅ **Zero gaps** - Next chunk scheduled to start exactly when previous ends
- ✅ **Smooth transitions** - Web Audio API handles timing precisely
- ✅ **Pre-scheduling** - Buffers can be scheduled in advance

**How it works:**
```
Chunk 1: Start at 0.000s, duration 0.128s → ends at 0.128s
Chunk 2: Start at 0.128s, duration 0.128s → ends at 0.256s
Chunk 3: Start at 0.256s, duration 0.128s → ends at 0.384s
         ↑
         No gap! Perfectly continuous
```

### 2. **AudioContext State Management**

```typescript
// Resume AudioContext if suspended (browser autoplay policy)
if (audioContextRef.current.state === 'suspended') {
  audioContextRef.current.resume().then(() => {
    console.log('[Audio Context] Resumed from suspended state');
  });
}
```

**Benefits:**
- ✅ Handles browser autoplay restrictions
- ✅ Audio plays even on first interaction
- ✅ No silent failures

### 3. **Explicit Byte Order Handling**

```typescript
// Use DataView for explicit little-endian byte order handling
const dataView = new DataView(bytes.buffer);
const numSamples = bytes.length / 2; // 2 bytes per sample
const pcm16 = new Int16Array(numSamples);

for (let i = 0; i < numSamples; i++) {
  // Read little-endian int16 (Gemini sends little-endian)
  pcm16[i] = dataView.getInt16(i * 2, true); // true = little-endian
}
```

**Benefits:**
- ✅ **Explicit endianness** - No platform-dependent behavior
- ✅ **Correct decoding** - Matches Gemini's little-endian format
- ✅ **No distortion** - Proper byte order ensures clean audio

### 4. **Proper Normalization with Clamping**

```typescript
// Convert to Float32 for Web Audio API with proper normalization
const float32 = new Float32Array(pcm16.length);
for (let i = 0; i < pcm16.length; i++) {
  // Proper normalization: -32768 to 32767 → -1.0 to 1.0
  float32[i] = Math.max(-1, Math.min(1, pcm16[i] / 32768.0));
}
```

**Benefits:**
- ✅ **Prevents clipping** - Values clamped to [-1, 1]
- ✅ **Clean conversion** - Proper range mapping
- ✅ **No overflow artifacts**

### 5. **Reset Timing on Completion**

```typescript
source.onended = () => {
  if (audioQueueRef.current.length > 0) {
    playNextAudioBuffer();
  } else {
    // Reset timing for next turn
    nextPlayTimeRef.current = 0;
    isPlayingRef.current = false;
    setProducerSpeaking(false);
  }
};
```

**Benefits:**
- ✅ **Clean state** - Each turn starts fresh
- ✅ **No timing drift** - Reset prevents accumulation
- ✅ **Proper turn separation**

## Expected Results

### Before (Choppy & Noisy)
```
Audio waveform:
████ .... ████ .... ████ .... ████
     ↑         ↑         ↑
    Gaps     Clicks    Pops
```

### After (Smooth & Clean)
```
Audio waveform:
████████████████████████████████
Continuous, gapless playback
```

## Technical Details

### Sample Rate: 16kHz
- Matches Gemini Live output
- AudioContext forced to 16000 Hz
- AudioBuffer created with 16000 Hz

### Buffer Duration
- Typical chunk: ~0.128 seconds (2048 samples at 16kHz)
- Multiple chunks queued and scheduled in advance
- Smooth continuous playback

### Playback Pipeline
1. **Receive** base64 audio from WebSocket
2. **Decode** base64 → Uint8Array
3. **Convert** Uint8Array → Int16Array (little-endian)
4. **Normalize** Int16Array → Float32Array (-1.0 to 1.0)
5. **Create** AudioBuffer with Float32 data
6. **Queue** buffer for playback
7. **Schedule** with precise timing
8. **Play** gaplessly

## Testing

### How to Verify Smooth Playback
1. Restart frontend: `npm run dev`
2. Speak to the microphone
3. Listen to Gemini's response

**Expected:**
- ✅ Smooth, continuous voice
- ✅ No clicks or pops
- ✅ No stuttering
- ✅ Clear audio quality
- ✅ Natural speech rhythm

**If still having issues:**
- Check console for "Resumed from suspended state" (browser autoplay)
- Verify "PCM16 samples" matches "Float32Array length"
- Check buffer duration logs (should be ~0.128s per chunk)

## Console Logs to Monitor

```
[Audio Context] Created with sample rate: 16000
[Audio] ⬇ Received chunk: 5464 chars, mime: audio/pcm
[Audio] Decoded to 4096 bytes
[Audio] PCM16 samples: 2048
[Audio] ✓ PCM buffer created, duration: 0.13 s, samples: 2048
[Audio Queue] Added to queue, total buffers: 1
[Audio Queue] ▶ Playing buffer (duration: 0.13 s) at time: 0.000, queue size: 0
```

## Code Files Modified

- `frontend/src/hooks/useWebSocket.ts`:
  - Added `nextPlayTimeRef` for scheduled playback
  - Implemented gapless playback with `source.start(playTime)`
  - Added AudioContext state management
  - Fixed PCM16 byte order with DataView
  - Added proper normalization with clamping
  - Added timing reset on completion

## Additional Benefits

- **Lower latency** - Scheduled playback can start immediately
- **Better buffering** - Can queue multiple chunks in advance
- **More reliable** - Handles edge cases (suspended context, timing drift)
- **Industry standard** - Uses Web Audio API best practices
