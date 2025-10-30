# Audio Noise Fix - Subsequent Responses

## Problem

- **First response**: Clear, good audio ✅
- **Subsequent responses**: Noisy audio ❌

## Root Cause

**Filter and Compressor nodes were being created for EVERY audio buffer** but never cleaned up!

### What Was Happening:

```
Turn 1:
  Create filter #1 → Create compressor #1 → Play audio ✅ (sounds good)
  (But filter #1 and compressor #1 stay in memory!)

Turn 2:
  Create filter #2 → Create compressor #2 → Play audio
  (Now TWO filters + TWO compressors are active!) ❌
  Result: Noise/distortion

Turn 3:
  Create filter #3 → Create compressor #3 → Play audio
  (Now THREE filters + THREE compressors!) ❌❌
  Result: More noise
```

The filters were **accumulating** and interfering with each other!

## Solution

**Create the audio processing chain ONCE and REUSE it for all audio**

### Before (Bad):
```typescript
const playNextAudioBuffer = () => {
  const source = audioContext.createBufferSource();

  // Creating NEW filters every time! ❌
  const filter = audioContext.createBiquadFilter();
  const compressor = audioContext.createDynamicsCompressor();

  source.connect(filter);
  filter.connect(compressor);
  compressor.connect(destination);
}
```

### After (Good):
```typescript
// Create filter chain ONCE at initialization ✅
const initAudioChain = () => {
  if (!audioFilterRef.current) {
    // Create filter ONCE
    audioFilterRef.current = audioContext.createBiquadFilter();
    audioCompressorRef.current = audioContext.createDynamicsCompressor();

    // Connect ONCE: filter → compressor → destination
    audioFilterRef.current.connect(audioCompressorRef.current);
    audioCompressorRef.current.connect(destination);
  }
};

const playNextAudioBuffer = () => {
  const source = audioContext.createBufferSource();

  // Reuse the SAME filter chain ✅
  source.connect(audioFilterRef.current);
}
```

## What Changed

**File**: `frontend/src/hooks/useWebSocket.ts`

### 1. Added Refs for Audio Chain
```typescript
const audioFilterRef = useRef<BiquadFilterNode | null>(null);
const audioCompressorRef = useRef<DynamicsCompressorNode | null>(null);
```

### 2. Created Initialization Function
```typescript
const initAudioChain = useCallback(() => {
  if (!audioContextRef.current) {
    audioContextRef.current = new AudioContext({ sampleRate: 24000 });
  }

  // Create filter and compressor ONCE
  if (!audioFilterRef.current && audioContextRef.current) {
    audioFilterRef.current = audioContextRef.current.createBiquadFilter();
    audioFilterRef.current.type = 'lowpass';
    audioFilterRef.current.frequency.value = 8000;

    audioCompressorRef.current = audioContextRef.current.createDynamicsCompressor();
    audioCompressorRef.current.threshold.value = -24;
    // ... other settings

    // Connect permanently: filter → compressor → destination
    audioFilterRef.current.connect(audioCompressorRef.current);
    audioCompressorRef.current.connect(audioContextRef.current.destination);
  }
}, []);
```

### 3. Updated Playback to Reuse Chain
```typescript
const playNextAudioBuffer = useCallback(() => {
  // Initialize once if needed
  initAudioChain();

  const source = audioContextRef.current.createBufferSource();
  source.buffer = audioBuffer;

  // Connect to REUSED filter (not creating new!) ✅
  source.connect(audioFilterRef.current);

  source.start(playTime);
}, [initAudioChain]);
```

### 4. Cleanup on Disconnect
```typescript
const disconnect = useCallback(() => {
  // Properly disconnect and clean up
  if (audioFilterRef.current) {
    audioFilterRef.current.disconnect();
    audioFilterRef.current = null;
  }
  if (audioCompressorRef.current) {
    audioCompressorRef.current.disconnect();
    audioCompressorRef.current = null;
  }
  if (audioContextRef.current) {
    audioContextRef.current.close();
    audioContextRef.current = null;
  }
}, []);
```

## How It Works Now

```
Session Start:
  Create AudioContext (once) ✅
  Create Filter (once) ✅
  Create Compressor (once) ✅
  Connect: filter → compressor → speakers ✅

Turn 1:
  Create source buffer
  Connect: source → [existing filter chain] ✅
  Play → Clear audio ✅

Turn 2:
  Create source buffer
  Connect: source → [same filter chain] ✅
  Play → Clear audio ✅

Turn 3:
  Create source buffer
  Connect: source → [same filter chain] ✅
  Play → Clear audio ✅

Session End:
  Disconnect filter ✅
  Disconnect compressor ✅
  Close AudioContext ✅
```

## Testing

**Refresh the page and test**:

1. Speak to Gemini
2. Wait for first response - should be clear ✅
3. Speak again
4. Wait for second response - should ALSO be clear now! ✅
5. Continue conversation - all responses should be clear ✅

**Console logs to look for**:
```
[Audio Chain] Created filter + compressor chain  ← Should appear ONCE
[Audio Queue] ▶ Playing buffer...  ← Multiple times, but same chain
```

## Why This Fix Works

### Audio Processing Chain is Stateless
- Each audio buffer is independent
- Filter and compressor just process samples as they pass through
- No need to recreate them for each buffer

### Benefits:
- ✅ **No accumulation** - Only ONE filter, ONE compressor
- ✅ **Better performance** - Not creating nodes constantly
- ✅ **Consistent quality** - Same processing for all audio
- ✅ **Proper cleanup** - Disconnected when session ends

### Technical Explanation:

Web Audio API nodes work like this:
```
Source1 → Filter → Compressor → Speakers
Source2 → Filter → Compressor → Speakers  (same filter/compressor!)
Source3 → Filter → Compressor → Speakers  (same filter/compressor!)
```

NOT like this (which was causing the problem):
```
Source1 → Filter1 → Compressor1 → Speakers
Source2 → Filter2 → Compressor2 → Speakers  (Filter1 still active!)
Source3 → Filter3 → Compressor3 → Speakers  (Filter1+2 still active!)
```

## Summary

✅ **Problem**: Creating new filters for every audio buffer
✅ **Solution**: Create filter chain once, reuse for all buffers
✅ **Result**: All responses should now have clear audio, not just the first one!

**Test it now - refresh the page and have a multi-turn conversation!**
