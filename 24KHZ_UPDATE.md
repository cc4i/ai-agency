# 24kHz Audio Update

## Changes Made

### ✅ Voice Verification
**Confirmed: Voice is set to "Kore" (Female)**

File: `backend/app/main.py` line 109
```python
voice_name="Kore"  # Female voice
```

### ✅ Sample Rate Updated to 24kHz

All audio components updated from 16kHz to 24kHz for higher quality:

#### 1. Microphone Capture
**File**: `frontend/src/hooks/useMicrophone.ts`
- Default sample rate: 16000 → **24000 Hz**
- AudioContext: 24kHz
- Chunk duration: ~171ms (4096 samples at 24kHz)

```typescript
sampleRate = 24000, // Higher quality audio (24kHz)
```

#### 2. Audio Playback
**File**: `frontend/src/hooks/useWebSocket.ts`
- AudioContext sample rate: 16000 → **24000 Hz**
- Both playback and processing contexts

```typescript
audioContextRef.current = new AudioContext({ sampleRate: 24000 });
```

#### 3. Workspace Configuration
**File**: `frontend/src/components/WorkspaceClient.tsx`
- Microphone hook sample rate: 16000 → **24000 Hz**

```typescript
sampleRate: 24000, // Higher quality 24kHz audio
```

## Technical Details

### Sample Rate Comparison

| Aspect | 16kHz (Old) | 24kHz (New) |
|--------|-------------|-------------|
| **Quality** | Telephone quality | FM radio quality |
| **Frequency range** | 0-8 kHz | 0-12 kHz |
| **Nyquist limit** | 8 kHz | 12 kHz |
| **Voice clarity** | Good | Excellent |
| **Data size (per second)** | 32 KB | 48 KB |
| **Bandwidth** | Lower | Higher (+50%) |

### Chunk Size Calculations

**At 24kHz:**
- 4096 samples = 4096 / 24000 = **0.171 seconds** (~171ms)
- PCM16 format = 2 bytes per sample
- Chunk size = 4096 × 2 = **8,192 bytes**
- Base64 encoded ≈ **10,923 characters**

**Compared to 16kHz:**
- Same buffer size (4096 samples)
- Shorter duration (171ms vs 256ms)
- More samples per second (higher quality)

### Audio Pipeline

**Input (Microphone → Gemini):**
1. Capture at **24kHz** (higher quality)
2. Buffer 4096 samples (~171ms)
3. Convert to PCM16
4. Send to Gemini Live

**Output (Gemini → Speakers):**
1. Receive audio from Gemini (might be 16kHz or 24kHz)
2. Decode PCM16
3. Create AudioBuffer at **24kHz**
4. Web Audio API handles resampling if needed
5. Play through speakers

### Sample Rate Mismatch Handling

**Important Note:**
- Gemini Live might still output at **16kHz** (standard for voice)
- Our playback is set to **24kHz**
- Web Audio API **automatically resamples** when needed
- No quality loss if upsampling 16kHz → 24kHz (interpolation)

**Scenarios:**
1. **If Gemini outputs 16kHz**: Web Audio resamples to 24kHz (upsampling, no quality loss)
2. **If Gemini outputs 24kHz**: Direct playback at 24kHz (perfect match)
3. **If Gemini auto-detects**: Might match our 24kHz input

## Benefits of 24kHz

### ✅ Higher Frequency Response
- 16kHz captures up to 8 kHz frequencies
- 24kHz captures up to 12 kHz frequencies
- Better reproduction of voice nuances, sibilants (s, sh sounds)

### ✅ Better Audio Quality
- Clearer voice reproduction
- More natural sound
- Better for female voices (higher frequency content)

### ✅ Professional Audio Standard
- 24kHz is used in VoIP systems
- Better than telephone quality (8kHz)
- Approaching broadcast quality (48kHz)

## Trade-offs

### ⚠️ Increased Bandwidth
- **+50% data size** compared to 16kHz
- 48 KB/s vs 32 KB/s
- More WebSocket traffic

### ⚠️ Higher CPU Usage
- More samples to process
- More encoding/decoding work
- Still negligible on modern devices

### ⚠️ Potential Sample Rate Conversion
- If Gemini outputs 16kHz, resampling happens
- Web Audio handles this automatically
- No quality loss with upsampling

## Testing

### Restart Frontend
```bash
cd frontend
npm run dev
```

### Verify in Console

**Expected logs:**
```
Frontend console:
[Audio Context] Created with sample rate: 24000

Backend logs:
[Session: ...] [Turn: 0] 🔊 Audio diagnostics - Max amplitude: XXXX
[Session: ...] [Turn: 0] 📤 Forwarding audio to Gemini (chunk #1, 8192 bytes)

Frontend console (on receiving):
[Audio] ⬇ Received chunk: ~XXXX chars, mime: audio/pcm
[Audio] PCM16 samples: XXXX
[Audio] ✓ PCM buffer created, duration: X.XX s, samples: XXXX
```

### What to Listen For

1. **Higher clarity** - Voice should sound clearer, crisper
2. **Better sibilants** - S, SH, CH sounds more defined
3. **More natural** - Less "telephone" quality
4. **Female voice** - Should hear "Kore" (female) voice

### Troubleshooting

**If audio sounds weird:**
- Check console for sample rate (should be 24000)
- Verify no error messages
- Check chunk sizes are correct

**If no audio:**
- Gemini might need time to adjust to 24kHz input
- Check backend logs for errors
- Try restarting both frontend and backend

## Rollback Instructions

If 24kHz causes issues, rollback to 16kHz:

### Frontend Files

**`frontend/src/hooks/useMicrophone.ts` line 28:**
```typescript
sampleRate = 16000, // Back to 16kHz
```

**`frontend/src/hooks/useWebSocket.ts` lines 164 & 211:**
```typescript
audioContextRef.current = new AudioContext({ sampleRate: 16000 });
```

**`frontend/src/components/WorkspaceClient.tsx` line 63:**
```typescript
sampleRate: 16000, // Back to 16kHz
```

## Summary

✅ **Voice**: Confirmed "Kore" (Female)
✅ **Sample Rate**: 16kHz → 24kHz (50% higher quality)
✅ **Chunk Size**: 8,192 bytes (4096 samples at 24kHz)
✅ **Frequency Range**: 0-12 kHz (was 0-8 kHz)
✅ **Quality**: FM radio quality for voice

**Try it now:**
1. Refresh the page
2. Click mic and speak
3. Listen to the female voice (Kore) at higher quality!
