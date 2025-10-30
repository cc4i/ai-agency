# Audio Diagnostics Guide - Identifying Noise Sources

This guide helps you diagnose and fix audio noise issues in Gemini Live responses.

## Quick Start: Test Audio Processing

### Step 1: Test with Processing Disabled

1. Open `frontend/src/hooks/useWebSocket.ts`
2. Find line ~48: `const enableAudioProcessing = useRef<boolean>(true);`
3. Change to: `const enableAudioProcessing = useRef<boolean>(false);`
4. Restart frontend: `npm run dev`
5. Test audio and listen for noise

**If noise disappears:** Problem is in local playback processing (filter/compressor)
**If noise remains:** Problem is in Gemini response or data decoding

### Step 2: Test with Gentler Processing

1. Set `enableAudioProcessing` back to `true`
2. The compressor is now less aggressive (updated settings):
   - Threshold: -18dB (was -24dB)
   - Ratio: 4:1 (was 12:1)
3. Test audio and compare quality

## Understanding the Diagnostic Logs

When audio plays, you'll see detailed quality analysis in the browser console:

### Example Output

```
[Audio] 📊 Quality Analysis:
  - Max amplitude: 8234 (+) / Min: -7891 (-)
  - Range: 16125 / 65536 possible
  - RMS level: 2456.3 (-22.4 dB)
  - Clipped samples: 0 (0.00%)
  - Silent samples: 42 (2.05%)
  - Zero-crossing rate: 0.1234 (noise indicator: >0.5 = likely noise)
  - First 10 samples: 123, -456, 789, -234, 567, ...
[Audio] Quality verdict: ✅ GOOD
```

### What Each Metric Means

#### 1. Max/Min Amplitude
- **Range**: -32768 to +32767 (16-bit signed integer)
- **Good**: Between ±2000 and ±15000
- **Bad**: Near ±32767 (clipping), or near 0 (silence)

**Example:**
- ✅ Max: 8234, Min: -7891 (healthy range)
- ⚠️ Max: 32500, Min: -31200 (clipping)
- ❌ Max: 150, Min: -180 (very low volume)

#### 2. Range
- **What**: Difference between max and min
- **Good**: 10,000 - 30,000 (healthy dynamic range)
- **Bad**: < 1,000 (flat audio) or > 60,000 (clipping)

#### 3. RMS Level (Root Mean Square)
- **What**: Average loudness of the audio
- **Good**: 1,000 - 8,000 (clear speech)
- **Too low**: < 500 (barely audible)
- **Too high**: > 15,000 (distorted/clipping)

**dB value:**
- -30 to -15 dB: Good speech levels
- < -40 dB: Very quiet
- > -10 dB: Very loud, risk of distortion

#### 4. Clipped Samples
- **What**: Samples that hit the maximum value (±32767)
- **Good**: < 0.1% (few or no clipped samples)
- **Bad**: > 1% (audio is distorted at source)

**If you see high clipping:**
- 🔴 **Problem is in Gemini response** (audio sent is already distorted)
- Not a local playback issue

#### 5. Silent Samples
- **What**: Samples near zero (< 10)
- **Good**: 5-20% for speech (pauses between words)
- **Bad**: > 90% (mostly silence) or 0% (no variation)

#### 6. Zero-Crossing Rate (ZCR)
- **What**: How often the waveform crosses zero
- **Speech**: 0.1 - 0.3 (normal)
- **Noise**: > 0.5 (high-frequency noise/artifacts)
- **Tone**: < 0.05 (pure tone, not speech)

**This is a key noise indicator!**
- ✅ ZCR: 0.15 (clean speech)
- ⚠️ ZCR: 0.65 (noisy, lots of high-frequency artifacts)

#### 7. First 10 Samples
- **What**: First 10 PCM16 values
- **Good**: Varied numbers (positive and negative)
- **Bad**: All same value, or pattern like 0, 0, 0, ...

**Use this to check:**
- Data is being decoded correctly
- Not all zeros or all same value
- Shows natural audio variation

#### 8. Quality Verdict
Automatic assessment based on all metrics:
- ✅ **GOOD**: RMS 500-10000, clipping < 1%, ZCR < 0.3
- ⚠️ **NEEDS INVESTIGATION**: One or more issues detected

## Diagnostic Decision Tree

### Scenario 1: High Zero-Crossing Rate (ZCR > 0.5)
```
[Audio] Zero-crossing rate: 0.68 (noise indicator: >0.5 = likely noise)
⚠️ [Audio] HIGH ZERO-CROSSING RATE
```

**This indicates high-frequency noise or artifacts**

**Test:**
1. Disable audio processing: `enableAudioProcessing = false`
2. If ZCR still high → **Gemini response is noisy**
3. If ZCR drops → **Filter/compressor causing artifacts**

**Fix options:**
- If local processing: Adjust filter cutoff or disable
- If Gemini: Report to Google (API issue)

### Scenario 2: High Clipping
```
⚠️ [Audio] HIGH CLIPPING DETECTED - Audio may be distorted!
  - Clipped samples: 245 (12.00%)
```

**Clipping means audio is hitting max values**

**This happens BEFORE local playback** (it's in the received data)

**Fix:**
- 🔴 **Gemini is sending distorted audio** (not your code)
- Try different voice (change `voice_name` in backend)
- Or report issue to Google

### Scenario 3: Very Low Volume
```
⚠️ [Audio] VERY LOW VOLUME - Audio may be barely audible
  - RMS level: 87.3 (-51.7 dB)
```

**Audio is too quiet**

**Test:**
1. Check speaker volume (system level)
2. Disable compressor (it might be reducing gain)
3. Check if all chunks are low or just some

**Fix:**
- Add gain node before playback
- Adjust compressor threshold

### Scenario 4: Flat Audio (No Variation)
```
❌ [Audio] NO VARIATION - Audio is completely flat
  - Max: 125, Min: 125 (same value!)
```

**Audio is completely flat (DC offset or decoding error)**

**This is a decoding problem**

**Check:**
- First 10 samples: All same value?
- Byte order (little-endian vs big-endian)
- PCM format mismatch

**Fix:**
- Already using DataView with little-endian (should be correct)
- Check Gemini is sending `audio/pcm` format

### Scenario 5: Processing Artifacts
```
[Audio Queue] 🔊 Using audio processing (filter + compressor)
[Audio] Quality verdict: ⚠️ NEEDS INVESTIGATION
```

**Audio quality degrades with processing enabled**

**Compare:**
1. With processing: Listen to quality
2. Without processing: `enableAudioProcessing = false`
3. If better without → Processing is adding artifacts

**Tuning options:**

```typescript
// Disable filter
audioFilterRef.current.frequency.value = 24000; // No filtering

// Disable compressor
audioCompressorRef.current.ratio.value = 1; // No compression

// Or bypass entirely
enableAudioProcessing.current = false;
```

## Testing Workflow

### Test 1: Baseline (Raw Audio)
1. Set `enableAudioProcessing = false`
2. Clear browser console
3. Speak and get response
4. Check quality verdict in console
5. Listen to audio quality

**Record:**
- Quality verdict: ✅ GOOD or ⚠️ NEEDS INVESTIGATION
- ZCR value: _____
- RMS level: _____
- Subjective quality: Clear / Noisy / Distorted

### Test 2: With Gentle Processing (Default)
1. Set `enableAudioProcessing = true`
2. Clear browser console
3. Speak and get response
4. Check quality verdict in console
5. Listen to audio quality

**Compare to Test 1:**
- Better? Same? Worse?
- Check if ZCR increased
- Check console for processing logs

### Test 3: Multiple Turns
1. Have a 3-turn conversation
2. Check if quality degrades over turns
3. Look for "Created filter + compressor chain" (should appear ONCE)

**If quality degrades:**
- Check for multiple chains being created
- Verify refs are being reused

## Console Logs Reference

### Normal Operation
```
[Audio Context] Created with sample rate: 24000
[Audio Chain] ✓ Created filter + compressor chain (threshold: -18dB, ratio: 4:1)
[Audio] ⬇ Received chunk: 5464 chars, mime: audio/pcm
[Audio] Decoded to 4096 bytes
[Audio] PCM16 samples converted: 2048
[Audio] 📊 Quality Analysis:
  - Max amplitude: 6234 (+) / Min: -5891 (-)
  - Range: 12125 / 65536 possible
  - RMS level: 2156.3 (-23.4 dB)
  - Clipped samples: 0 (0.00%)
  - Silent samples: 38 (1.85%)
  - Zero-crossing rate: 0.1456 (noise indicator: >0.5 = likely noise)
[Audio] Quality verdict: ✅ GOOD
[Audio Queue] Added to queue, total buffers: 1
[Audio Queue] 🔊 Using audio processing (filter + compressor)
[Audio Queue] ▶ Playing buffer (duration: 0.09 s) at time: 0.000, queue size: 0
```

### Warning: Processing Disabled
```
[Audio Chain] ⚠️ Audio processing DISABLED - using raw audio
[Audio Queue] 🔊 Bypassing audio processing (raw audio)
```

### Error: High Noise
```
[Audio] Zero-crossing rate: 0.6823 (noise indicator: >0.5 = likely noise)
⚠️ [Audio] HIGH ZERO-CROSSING RATE - May indicate noise or high-frequency artifacts
[Audio] Quality verdict: ⚠️ NEEDS INVESTIGATION
```

## Advanced: Custom Processing Settings

### Location
File: `frontend/src/hooks/useWebSocket.ts`, line ~170

### Option 1: Disable Filter Only
```typescript
// Skip creating filter
if (enableAudioProcessing.current && !audioFilterRef.current && audioContextRef.current) {
  // Comment out filter creation
  // audioFilterRef.current = audioContextRef.current.createBiquadFilter();

  // Only create compressor
  audioCompressorRef.current = audioContextRef.current.createDynamicsCompressor();
  // ... compressor settings

  // Connect directly: compressor → destination (no filter)
  audioCompressorRef.current.connect(audioContextRef.current.destination);
}

// In playNextAudioBuffer, connect to compressor instead of filter
source.connect(audioCompressorRef.current);
```

### Option 2: Disable Compressor Only
```typescript
// Only create filter
audioFilterRef.current = audioContextRef.current.createBiquadFilter();
// ... filter settings

// Connect directly: filter → destination (no compressor)
audioFilterRef.current.connect(audioContextRef.current.destination);

// In playNextAudioBuffer, connect stays the same
source.connect(audioFilterRef.current);
```

### Option 3: Adjust Filter Cutoff
```typescript
// Less aggressive filtering (allow more high frequencies)
audioFilterRef.current.frequency.value = 12000; // was 8000

// Or no filtering
audioFilterRef.current.frequency.value = 24000; // Nyquist frequency
```

### Option 4: Adjust Compressor Settings
```typescript
// Even gentler compression
audioCompressorRef.current.threshold.value = -12; // was -18
audioCompressorRef.current.ratio.value = 2; // was 4

// Or no compression
audioCompressorRef.current.ratio.value = 1; // 1:1 = no compression
```

## Summary: What Changed

### 1. Compressor Settings (Less Aggressive)
- **Threshold**: -24dB → **-18dB** (kicks in later)
- **Ratio**: 12:1 → **4:1** (gentler compression)
- **Effect**: Less likely to introduce pumping/breathing artifacts

### 2. Audio Processing Toggle
- **Variable**: `enableAudioProcessing.current`
- **Set to `true`**: Uses filter + compressor (default)
- **Set to `false`**: Raw audio, no processing
- **Use**: Quick A/B testing to isolate noise source

### 3. Enhanced Diagnostics
- **Zero-Crossing Rate**: Detects high-frequency noise
- **First 10 Samples**: Verify decoding correctness
- **Quality Verdict**: Automatic assessment
- **Detailed Warnings**: Specific issues flagged

## Next Steps

1. **Run Test 1 & 2** (with and without processing)
2. **Share console output** from both tests
3. **Describe the noise**:
   - Static/hiss (high-frequency noise)
   - Crackling/popping (clipping or gaps)
   - Muffled (over-filtering)
   - Robotic/metallic (compression artifacts)

Based on the diagnostic output, we can pinpoint the exact issue and fix it.
