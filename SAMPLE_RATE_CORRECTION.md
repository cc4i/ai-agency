# Sample Rate Correction - Input vs Output

## Important Discovery

Gemini Live API uses **different sample rates** for input and output:

- **INPUT (Microphone → Gemini)**: **16kHz** (required)
- **OUTPUT (Gemini → Speakers)**: **24kHz** (always)

Source: Gemini Live API Documentation
> "Audio data in the Live API is always raw, little-endian, 16-bit PCM. Audio output always uses a sample rate of 24kHz."
> "Ensure audio conforms to API requirements (16-bit PCM, 16kHz, mono)"

## Changes Made

### ✅ Input: 16kHz (Microphone Capture)

**Files Updated:**
- `frontend/src/hooks/useMicrophone.ts`
- `frontend/src/components/WorkspaceClient.tsx`

**Configuration:**
```typescript
// Microphone captures at 16kHz (required by Gemini)
sampleRate = 16000
```

### ✅ Output: 24kHz (Audio Playback)

**Files Kept at 24kHz:**
- `frontend/src/hooks/useWebSocket.ts`

**Configuration:**
```typescript
// AudioContext for playback at 24kHz (matches Gemini's output)
audioContextRef.current = new AudioContext({ sampleRate: 24000 });
```

## Why Different Sample Rates?

### Input: 16kHz
- **Reason**: Gemini Live API specification
- **Standard**: Telephony/VoIP standard for voice input
- **Efficiency**: Smaller data size for transmission
- **Quality**: Sufficient for voice recognition (0-8 kHz frequency range)

### Output: 24kHz
- **Reason**: Gemini's internal processing upsamples to higher quality
- **Standard**: Professional audio quality
- **Quality**: Better voice reproduction (0-12 kHz frequency range)
- **Clarity**: Clearer, more natural-sounding speech

## Audio Pipeline

### Complete Flow

```
User Microphone
    ↓
Capture at 16kHz (required by Gemini)
    ↓
Convert to PCM16 (little-endian)
    ↓
Send to Gemini Live API
    ↓
Gemini processes & generates response
    ↓
Gemini outputs at 24kHz (always)
    ↓
Receive PCM16 audio (little-endian)
    ↓
Play at 24kHz (matches output)
    ↓
User Speakers
```

### Gemini's Internal Processing

1. Receives 16kHz audio input
2. Performs speech-to-text
3. Generates response
4. Synthesizes speech at 24kHz (higher quality)
5. Sends 24kHz audio back

**Why upsampling?**
- Gemini's TTS (text-to-speech) models generate at 24kHz
- Higher quality output than input
- Better user experience

## Technical Details

### Input Chunks (16kHz)
- Buffer size: 4096 samples
- Duration: 4096 / 16000 = **256ms**
- Chunk size: 4096 × 2 bytes = **8,192 bytes**
- Base64 encoded: ~**10,923 characters**

### Output Chunks (24kHz)
- Sample rate: 24000 Hz
- Format: PCM16, little-endian
- Chunks vary in size (depends on Gemini's speech generation)
- Playback uses gapless scheduling

### Byte Order (Little-Endian)
We handle this correctly with DataView:

```typescript
const dataView = new DataView(bytes.buffer);
for (let i = 0; i < numSamples; i++) {
  pcm16[i] = dataView.getInt16(i * 2, true); // true = little-endian
}
```

## Benefits of This Configuration

### ✅ API Compliance
- Input matches Gemini's requirement (16kHz)
- Prevents errors or quality issues

### ✅ Optimal Quality
- Output matches Gemini's native format (24kHz)
- No unnecessary resampling
- Maximum audio clarity

### ✅ Efficient Bandwidth
- Input uses smaller data size (16kHz)
- Output provides higher quality (24kHz)
- Best of both worlds

### ✅ Natural Voice Quality
- 24kHz output captures full voice range
- Better for female voices (higher frequencies)
- Professional audio quality

## Console Verification

### Expected Logs

**Microphone (Input):**
```
[Audio Context] Created with sample rate: 16000
[Audio] 🎤 Audio chunk #1 (size: 10923 base64 chars)
```

**Playback (Output):**
```
[Audio Context] Created with sample rate: 24000
[Audio] ⬇ Received chunk: XXXX chars, mime: audio/pcm
[Audio] PCM16 samples: XXXX
```

## Testing

### Refresh Frontend
```bash
# Just refresh the page (Ctrl+R / Cmd+R)
```

### What to Verify

1. **Microphone captures at 16kHz** ✅
   - Check console: AudioContext with 16000 Hz for input

2. **Playback at 24kHz** ✅
   - Check console: AudioContext with 24000 Hz for output

3. **Female voice (Kore)** ✅
   - Listen to Gemini's response

4. **Clear audio** ✅
   - Higher quality than before
   - No distortion or artifacts

## Summary

| Component | Sample Rate | Format | Purpose |
|-----------|-------------|--------|---------|
| **Microphone Input** | 16kHz | PCM16 LE | Required by Gemini API |
| **Gemini Processing** | Internal | N/A | Speech recognition & synthesis |
| **Audio Output** | 24kHz | PCM16 LE | Gemini's native TTS output |
| **Playback** | 24kHz | Float32 | Web Audio API |

**Key Insight**: Gemini Live API accepts 16kHz input but outputs 24kHz for better quality!

✅ **Input**: 16kHz (API requirement)
✅ **Output**: 24kHz (matches Gemini's output)
✅ **Voice**: Kore (Female)
✅ **Format**: PCM16, little-endian (correct)
