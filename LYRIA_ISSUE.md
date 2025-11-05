# Lyria Music Generation Issue

**Status:** ✅ **FIXED**
**Date:** 2025-11-05

---

## Solution

**Root Cause:** The Lyria API response uses `bytesBase64Encoded` as the field name, not `audioContent`.

**Fix Applied:**
1. Rewrote Lyria implementation to use direct HTTP POST calls (as per official documentation)
2. Changed endpoint to use `:predict` suffix (not `:predictLongRunning`)
3. Updated response parsing to look for `bytesBase64Encoded` field instead of `audioContent`

**Result:** ✅ Lyria now successfully generates 32.8-second WAV files (48kHz, ~6MB)

---

## Problem (Original Issue)

Lyria music generation (`lyria-002` model) was returning empty predictions due to:
1. Using PredictionServiceClient instead of direct HTTP calls
2. Looking for wrong response field name (`audioContent` vs `bytesBase64Encoded`)

### Original Test Results

```
Lyria Music Generation: ❌ FAIL
- API call succeeds (no auth errors)
- Prediction response received
- But `audioContent` field is missing
- Returns: <proto.marshal.collections.maps.MapComposite object>

Text-to-Speech: ✅ PASS
- Working correctly
- Generates speech audio successfully
```

---

## Root Cause (Identified & Fixed)

The Lyria API response structure is:
```json
{
  "predictions": [
    {
      "bytesBase64Encoded": "<base64-encoded-wav-data>",
      "mimeType": "audio/wav"
    }
  ]
}
```

**Not:**
```json
{
  "predictions": [
    {
      "audioContent": "<base64-data>"  // ❌ This field doesn't exist
    }
  ]
}
```

---

## Verified Working (2025-11-05)

Test results after fix:

```bash
$ python backend/scripts/test_lyria.py

================================================================================
Lyria Music Generation Test
================================================================================

2. Testing music generation...
   Generating 10-second test jingle...

   ✅ SUCCESS: Generated 6291544 bytes of audio
   Audio format: WAV, 48kHz, ~30 seconds (Lyria fixed duration)

   Saved test jingle to: /tmp/test_jingle.wav

3. Testing Text-to-Speech...
   ✅ SUCCESS: Generated 18816 bytes of speech

================================================================================
Test Summary
================================================================================
Lyria Music Generation: ✅ PASS
Text-to-Speech:         ✅ PASS
```

**Verification:**
- Audio file size: 6.0MB (6,291,544 bytes)
- Format: WAV, 48kHz sample rate
- Duration: 32.8 seconds (Lyria's fixed output duration)
- Playback: ✅ Verified working with `afplay /tmp/test_jingle.wav`

---

## Previous Behavior (Before Fix)

When audio agent tried to generate jingle:
1. Calls `lyria_client.generate_music()`
2. Gets empty response (`b""`)
3. Falls back to placeholder URL: `gs://ai-agency-demo/audio/jingle_{id}.wav`
4. **This file doesn't exist**, so frontend shows broken audio player

---

## Workaround Options (No Longer Needed)

### Option 1: Use Placeholder Audio (Quick Fix)

Create actual placeholder audio files:

```bash
# Create a simple 10-second silent WAV
cd backend
python scripts/create_placeholder_audio.py
```

This will:
- Generate `placeholder_jingle.wav` (10s instrumental loop)
- Upload to GCS at `gs://ai-agency-demo/audio/placeholder_jingle.wav`
- Return this URL when Lyria fails

**Pros:** Immediate fix, something plays in frontend
**Cons:** Not real generated music

### Option 2: Use Alternative Music API

Replace Lyria with:
- **Mubert API** (AI music generation)
- **AIVA API** (AI composer)
- **Soundful API** (royalty-free AI music)

**Pros:** Actually generates music
**Cons:** Requires external API integration, costs

### Option 3: Skip Music Generation

Don't generate jingles, only generate:
- TTS podcast ads (working ✅)
- Transcriptions (working ✅)

**Pros:** Uses only working features
**Cons:** Missing music asset

---

## Investigation Needed

### Check if Lyria is Available

```bash
# List available models in Vertex AI
gcloud ai models list \
  --region=us-central1 \
  --project=multi-gke-ops \
  --filter="displayName:lyria*"

# Or check publishers
gcloud ai endpoints list \
  --region=us-central1 \
  --project=multi-gke-ops
```

### Check Model Response Format

The prediction response is a `MapComposite` object, but we don't know what keys it contains. Need to:
1. Enable full debug logging
2. Print all available keys in the response
3. Check if there's a different field name (e.g., `audio`, `audioData`, `music`, etc.)

### Try Different Model Names

Lyria might be under a different name:
- `lyria` (without version)
- `lyria-v1`
- `music-generation`
- `ai-music-generator`

---

## Recommended Action

**Short-term (Now):**
Use **Option 1** - Create placeholder audio so frontend doesn't break

**Long-term (This week):**
- Contact Google Cloud support to verify Lyria availability
- Check Google AI Studio for music generation capabilities
- Consider alternative music generation services

---

## Files Affected

- `backend/app/services/google_ai_client.py:771-875` - Lyria music generation
- `backend/app/agents/audio_team.py:137-212` - Jingle generation
- `backend/scripts/test_lyria.py` - Diagnostic test

---

## Next Steps

1. **Create placeholder audio** (5 min)
   ```bash
   cd backend
   python scripts/create_placeholder_audio.py
   ```

2. **Update audio agent to use placeholder** (2 min)
   - Return placeholder URL when Lyria fails
   - Log warning about Lyria unavailability

3. **Research Lyria availability** (1 hour)
   - Check Google AI documentation
   - Test in Google AI Studio
   - Contact Cloud support if needed

4. **Consider alternatives** (if Lyria unavailable)
   - Evaluate Mubert/AIVA/Soundful APIs
   - Or skip music generation for MVP
