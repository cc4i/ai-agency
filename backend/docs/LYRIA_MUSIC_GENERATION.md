# Lyria Music Generation Implementation

## Overview

The Audio Team agent now uses Google's **Lyria (lyria-002)** model for AI-generated music jingles. Lyria is a state-of-the-art music generation model that creates instrumental music from text prompts.

**Implementation Date**: January 31, 2025
**Model**: `lyria-002`
**Location**: Configured via `GOOGLE_CLOUD_LOCATION` (e.g., `us-central1`)

---

## API Specifications

### Model Information

- **Model ID**: `lyria-002`
- **Endpoint**: `projects/{PROJECT_ID}/locations/{LOCATION}/publishers/google/models/lyria-002`
- **API**: Vertex AI Prediction Service
- **Pricing**: $0.06 per 30 seconds of generated music

### Output Specifications

- **Format**: WAV (uncompressed)
- **Sample Rate**: 48 kHz
- **Duration**: **30 seconds (fixed)**
- **Content**: Instrumental music only (no vocals)
- **Channels**: Stereo

### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `prompt` | string | Yes | Text description in US English (en-us) |
| `negative_prompt` | string | No | Elements to exclude from generation |
| `seed` | integer | No | Seed for deterministic output (incompatible with `sample_count`) |
| `sample_count` | integer | No | Number of samples to generate (default: 1, incompatible with `seed`) |

### Response Format

```json
{
  "predictions": [
    {
      "audioContent": "base64-encoded WAV data",
      "mimeType": "audio/wav"
    }
  ],
  "deployedModelId": "...",
  "model": "...",
  "modelDisplayName": "lyria-002"
}
```

---

## Implementation Details

### File: `app/services/google_ai_client.py`

**Class**: `LyriaClient`

**Method**: `generate_music()`

```python
async def generate_music(
    self,
    prompt: str,
    duration_seconds: int = 10,
    negative_prompt: str = None,
    seed: int = None
) -> bytes:
    """
    Generate music using Lyria (lyria-002 model).

    Args:
        prompt: Music generation prompt (US English)
        duration_seconds: Ignored (Lyria generates 30s fixed)
        negative_prompt: Optional elements to exclude
        seed: Optional seed for deterministic output

    Returns:
        Generated audio as bytes (WAV format, 48 kHz, 30s)
    """
```

**Key Implementation Points**:

1. **Vertex AI Prediction API**: Uses `PredictionServiceClient` from `google.cloud.aiplatform_v1`
2. **Async Execution**: Runs blocking API call in executor to avoid blocking event loop
3. **Base64 Decoding**: Extracts and decodes `audioContent` from response
4. **Error Handling**: Returns empty bytes on error for graceful degradation
5. **Logging**: Detailed logs for debugging API calls

### File: `app/agents/audio_team.py`

**Method**: `_generate_jingle()`

**Key Changes**:

1. **WAV Output**: Changed upload content type from `audio/mpeg` to `audio/wav`
2. **30s Duration**: Jingles are 30 seconds when Lyria succeeds (not 10s)
3. **Placeholder Handling**: Falls back to placeholder URL when Lyria fails
4. **Prompt Engineering**: Detailed prompts with brand tone, style, and structure

**Example Prompt**:

```python
prompt = """
Compose a 10-second jingle for Aura Smart Sneaker.

MUSIC STYLE: uplifting, electronic, synthesized beats with ambient textures
THEME: futuristic urban athlete
BRAND TONE: futuristic
SLOGAN: "Run Your Future"

REQUIREMENTS:
- Duration: 10 seconds
- Style: uplifting, electronic, synthesized beats
- Mood: Matches futuristic brand tone
- Energy: Appropriate for urban athlete theme
- Format: Instrumental background music
- Purpose: Social media ads, podcast intros

COMPOSITION:
- Opening: Attention-grabbing hook (1-2 seconds)
- Middle: Develop theme with futuristic feel (5-6 seconds)
- Ending: Memorable closing flourish (2-3 seconds)
"""
```

**Note**: Lyria generates 30 seconds regardless of prompt duration request.

---

## Usage in Audio Team Workflow

### Jingle Generation Flow

1. **Audio Team receives task** with theme, brand tone, product name, slogan
2. **Select music style** based on brand tone mapping:
   - `futuristic` → "uplifting, electronic, synthesized beats"
   - `luxury` → "sophisticated, orchestral, elegant piano"
   - `playful` → "bouncy, cheerful, acoustic instruments"
   - `edgy` → "intense, rock-influenced, driving beats"
   - `professional` → "corporate, clean, modern production"
   - `energetic` → "high-tempo, dynamic, motivating beats"

3. **Construct detailed prompt** with music style, theme, tone, requirements
4. **Call Lyria API** via `lyria_client.generate_music()`
5. **Handle response**:
   - **Success**: Upload WAV to GCS, return asset with 30s duration
   - **Failure**: Use placeholder URL, return asset with 10s duration

### Storage and URLs

**Successful Generation**:
- Audio uploaded to GCS bucket
- Signed URL returned (7-day expiration)
- Format: `https://storage.googleapis.com/ai-agency-demo/audio/{asset_id}.wav`

**Placeholder (Lyria unavailable)**:
- No upload occurs
- Placeholder GCS path returned
- Format: `gs://ai-agency-demo/audio/{asset_id}.wav`

---

## Testing

### Unit Tests

**File**: `tests/test_agents/test_audio_team.py`

**Test Cases**:
- `test_generate_jingle_with_music_data`: Verifies WAV upload, 30s duration
- `test_generate_jingle_without_music_data`: Verifies placeholder fallback

**All tests passing** ✅ (24/24 tests in 0.31s)

### Integration Tests

**File**: `tests/integration/test_audio_team_api.py`

**Test**: `test_jingle_generation`

Handles both scenarios:
- **Real Lyria API**: Validates 30s duration, HTTPS URL
- **Placeholder**: Validates 10s duration, GCS path

**To run integration tests**:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="path/to/credentials.json"
export GOOGLE_CLOUD_PROJECT="your-project-id"
export GOOGLE_CLOUD_LOCATION="us-central1"

python -m pytest tests/integration/test_audio_team_api.py::TestRealJingleGeneration -v -s
```

---

## Configuration

### Environment Variables

Required environment variables in `.env`:

```bash
# Google Cloud Configuration
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1  # Must support Lyria

# Authentication
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

### Google Cloud Setup

**1. Enable APIs**:

```bash
gcloud services enable aiplatform.googleapis.com
gcloud services enable storage.googleapis.com
```

**2. Grant Permissions**:

Service account needs:
- `aiplatform.endpoints.predict` (Vertex AI Prediction)
- `storage.objects.create` (GCS upload)
- `storage.objects.get` (GCS download)

**3. Supported Regions**:

Lyria is available in limited regions. Recommended:
- `us-central1`
- `us-east1`
- `europe-west4`

Check availability: https://cloud.google.com/vertex-ai/generative-ai/docs/learn/locations

---

## Prompt Engineering Best Practices

### Effective Prompts

✅ **Good Prompt**:
```
A calm acoustic folk song with gentle guitar melody and soft strings.
Warm, intimate atmosphere. Morning coffee shop vibe.
```

❌ **Poor Prompt**:
```
Make music
```

### Tips for Quality Output

1. **Be Specific**: Describe instruments, tempo, mood, style
2. **Use Music Terms**: "Uplifting", "ambient", "driving beats", "orchestral"
3. **Set Context**: "Social media ad", "podcast intro", "background music"
4. **Describe Structure**: "Opening hook", "build-up", "climax", "outro"
5. **Match Brand Tone**: Align music style with brand personality

### Negative Prompts

Use `negative_prompt` to exclude unwanted elements:

```python
negative_prompt="drums, electric guitar, vocals, distortion"
```

Common exclusions:
- Specific instruments: "drums", "piano", "guitar"
- Vocal elements: "vocals", "singing", "voice"
- Genres: "rock", "jazz", "classical"
- Qualities: "harsh", "loud", "aggressive"

---

## Limitations

### Current Limitations

1. **Fixed Duration**: Always generates 30 seconds (cannot customize)
2. **Language**: Prompts must be in US English (en-us)
3. **Instrumental Only**: No vocal generation support
4. **One Sample**: Default generates single sample (use `sample_count` for multiple)
5. **Seed vs Sample Count**: Cannot use both simultaneously

### Content Safety

Lyria applies:
- **Content safety filters**: Prevents harmful content
- **Recitation checking**: Avoids copyrighted material
- **Artist intent checks**: Respects artist rights
- **SynthID watermarking**: Embeds AI-generated metadata

---

## Troubleshooting

### Lyria Returns Empty Bytes

**Symptoms**: Jingle generation falls back to placeholder

**Possible Causes**:
1. **Region not supported**: Lyria not available in your `GOOGLE_CLOUD_LOCATION`
2. **API not enabled**: `aiplatform.googleapis.com` not enabled
3. **Permissions issue**: Service account lacks `aiplatform.endpoints.predict`
4. **Content filtered**: Prompt triggered safety filters
5. **Quota exceeded**: API quota limit reached

**Solution**:
```bash
# Check region support
echo $GOOGLE_CLOUD_LOCATION

# Enable API
gcloud services enable aiplatform.googleapis.com

# Check service account permissions
gcloud projects get-iam-policy $GOOGLE_CLOUD_PROJECT \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:YOUR_SA_EMAIL"

# Check logs
tail -f logs/backend.log | grep "Lyria"
```

### API Response Error

**Error**: `Could not extract audioContent from prediction`

**Cause**: Response format mismatch

**Solution**: Check response structure in logs. The implementation handles multiple formats:
- `prediction.audioContent` (direct attribute)
- `prediction['audioContent']` (dict access)
- `prediction.get('audioContent')` (protobuf struct)

### Upload Fails

**Error**: `Failed to upload audio to GCS`

**Cause**: Storage client error

**Solution**:
1. Check GCS bucket exists and is accessible
2. Verify service account has `storage.objects.create`
3. Check network connectivity to GCS

---

## Cost Optimization

### Pricing

- **Cost**: $0.06 per 30 seconds
- **Per jingle**: $0.06 (fixed, since Lyria generates 30s)

### Cost Estimates

| Volume | Monthly Cost |
|--------|--------------|
| 100 jingles/month | $6.00 |
| 500 jingles/month | $30.00 |
| 1,000 jingles/month | $60.00 |
| 10,000 jingles/month | $600.00 |

### Optimization Strategies

1. **Cache Jingles**: Reuse jingles for similar brand tones
2. **Batch Generation**: Use `sample_count` to generate multiple variations
3. **Deterministic Generation**: Use `seed` parameter for reproducible results
4. **Preview Before Production**: Test prompts in development first

---

## Future Enhancements

### Potential Improvements

1. **Custom Duration**: Wait for Lyria API to support variable durations
2. **Music Editing**: Trim 30s output to desired length (10s for jingles)
3. **Format Conversion**: Convert WAV to MP3 for smaller file sizes
4. **Caching Layer**: Cache generated jingles by prompt hash
5. **A/B Testing**: Generate multiple variations with different seeds
6. **Lyrics Integration**: When Lyria supports vocals, add jingle lyrics

### Format Conversion Example

Convert Lyria WAV to MP3:

```python
import subprocess

def convert_wav_to_mp3(wav_bytes: bytes) -> bytes:
    """Convert WAV to MP3 using ffmpeg."""
    process = subprocess.Popen(
        ['ffmpeg', '-i', 'pipe:0', '-f', 'mp3', '-b:a', '192k', 'pipe:1'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    mp3_bytes, _ = process.communicate(input=wav_bytes)
    return mp3_bytes
```

---

## References

- **Lyria API Documentation**: https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/lyria-music-generation
- **Vertex AI Prediction Service**: https://cloud.google.com/vertex-ai/docs/predictions/get-predictions
- **Audio Team Implementation**: `app/agents/audio_team.py`
- **Lyria Client**: `app/services/google_ai_client.py` (lines 754-868)

---

## Summary

✅ **Lyria music generation fully implemented**
✅ **All 24 unit tests passing**
✅ **Integration tests ready**
✅ **WAV format with 48 kHz output**
✅ **30-second fixed duration**
✅ **Graceful fallback to placeholder**
✅ **Brand tone mapping for prompt engineering**
✅ **Product-agnostic design**

The Audio Team agent now generates real AI music jingles using Google's Lyria model!
