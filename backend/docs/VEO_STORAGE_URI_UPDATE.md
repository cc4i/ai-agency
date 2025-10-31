# Veo API Update - storageUri Parameter

## Summary

Updated Veo API integration to use `storageUri` parameter as documented in the official Veo API reference. This aligns the implementation with Google's recommended approach and improves efficiency.

## What Changed

### 1. Request Structure Updated

**Before:**
```json
{
  "instances": [{...}],
  "parameters": {
    "sampleCount": 1,
    "durationSeconds": 8,
    "generateAudio": false
  }
}
```

**After:**
```json
{
  "instances": [{...}],
  "parameters": {
    "sampleCount": 1,
    "durationSeconds": 8,
    "generateAudio": false,
    "storageUri": "gs://ai-agency-demo/veo_videos/veo_abc123"
  }
}
```

### 2. Code Changes

**File**: `app/services/google_ai_client.py`

**Lines 487-501**: Added `storageUri` to request parameters
```python
# Generate unique video ID
import uuid
video_id = f"veo_{uuid.uuid4().hex[:12]}"
storage_uri = f"gs://{settings.gcs_bucket_name}/veo_videos/{video_id}"

parameters = {
    "sampleCount": 1,
    "durationSeconds": duration_seconds,
    "generateAudio": False,
    "storageUri": storage_uri,  # NEW: Save to GCS instead of returning base64
}

logger.info(f"Veo: Requesting video save to: {storage_uri}")
```

**Lines 657-674**: Updated response parsing to prioritize `gcsUri`
```python
# Video should be in GCS (since we provided storageUri)
# But fallback to base64 if GCS URI not present
if "gcsUri" in video_obj:
    gcs_uri = video_obj["gcsUri"]
    logger.info(f"Veo: Downloading video from GCS: {gcs_uri}")
    video_bytes = await self._download_from_gcs(gcs_uri)
    return video_bytes
elif "bytesBase64Encoded" in video_obj:
    # Fallback: base64 response (shouldn't happen with storageUri)
    logger.warning("Veo: Received base64 response despite storageUri request")
    video_b64 = video_obj["bytesBase64Encoded"]
    video_bytes = base64.b64decode(video_b64)
    return video_bytes
```

### 3. Response Structure

**Without storageUri (old way):**
```json
{
  "done": true,
  "response": {
    "videos": [{
      "video": {
        "bytesBase64Encoded": "{5-10MB base64 string}"
      }
    }]
  }
}
```

**With storageUri (new way):**
```json
{
  "done": true,
  "response": {
    "videos": [{
      "video": {
        "gcsUri": "gs://ai-agency-demo/veo_videos/veo_abc123/00000000.mp4"
      }
    }]
  }
}
```

## Benefits

### 1. **Efficiency**
- **Before**: API response contains 5-10MB base64-encoded video
- **After**: API response contains only GCS URI (~100 bytes)
- **Savings**: 99.99% reduction in response payload size

### 2. **Performance**
- Smaller response payloads = faster network transfer
- No need to encode/decode large base64 strings
- Direct GCS download is optimized

### 3. **Storage**
- Videos automatically saved to GCS bucket
- Persistent storage (not just in memory)
- Can be accessed later without re-generation

### 4. **Alignment with Documentation**
- Follows Google's recommended approach
- Uses official API parameters
- Future-proof implementation

## Storage Location

Videos are saved to:
```
gs://ai-agency-demo/veo_videos/veo_{unique_id}/
```

Each video gets a unique ID (12 hex chars):
- Example: `gs://ai-agency-demo/veo_videos/veo_a1b2c3d4e5f6/00000000.mp4`

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Client Request                                               │
│    POST :predictLongRunning                                     │
│    parameters.storageUri = "gs://ai-agency-demo/veo_videos/..." │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. Veo API Processing                                           │
│    - Generates video (60-180 seconds)                           │
│    - Saves directly to GCS bucket                               │
│    - Returns operation ID                                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. Poll Operation                                               │
│    POST :fetchPredictOperation                                  │
│    - Check every 5 seconds                                      │
│    - Wait for done: true                                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. Get GCS URI                                                  │
│    response.videos[0].video.gcsUri                              │
│    = "gs://ai-agency-demo/veo_videos/veo_abc123/00000000.mp4"  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. Download from GCS                                            │
│    storage_client.bucket().blob().download_as_bytes()           │
│    - Efficient direct download                                  │
│    - No base64 encoding/decoding                                │
└─────────────────────────────────────────────────────────────────┘
```

## Backward Compatibility

The implementation maintains backward compatibility:

1. **Primary Path**: Check for `gcsUri` (expected with `storageUri`)
2. **Fallback Path**: Check for `bytesBase64Encoded` (old format)
3. **Legacy Path**: Check for old `predictions` format

This ensures the code works even if:
- Veo API doesn't support `storageUri` in some regions
- API falls back to base64 response for any reason
- Future API changes occur

## Configuration

The GCS bucket is configured in `.env`:
```bash
GCS_BUCKET_NAME=ai-agency-demo
```

Or via environment variable:
```bash
export GCS_BUCKET_NAME="your-bucket-name"
```

## Testing

The integration tests now:
1. Send request with `storageUri`
2. Verify operation starts successfully
3. Poll until complete
4. Expect `gcsUri` in response
5. Download video from GCS
6. Verify video bytes

**Expected log output:**
```
INFO: Veo: Requesting video save to: gs://ai-agency-demo/veo_videos/veo_abc123
INFO: Veo: Starting long-running video generation operation...
INFO: Veo: Operation started: projects/.../operations/...
INFO: Veo: Polling operation (max wait: 300s, interval: 5s)
...
INFO: Veo: Operation complete after 25 polls (125.3s)
INFO: Veo: Video object keys: dict_keys(['gcsUri'])
INFO: Veo: Downloading video from GCS: gs://ai-agency-demo/veo_videos/veo_abc123/00000000.mp4
INFO: Veo: Downloaded 5483920 bytes from GCS
```

## Documentation Updates

Updated files:
- ✅ `docs/VEO_API_FLOW.md` - Added `storageUri` to request examples
- ✅ `docs/VEO_STORAGE_URI_UPDATE.md` - This document
- ✅ `app/services/google_ai_client.py` - Implementation with debug logging

## References

- [Veo Video Generation API](https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/veo-video-generation)
- [Veo Image-to-Video Parameters](https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/veo-video-generation#rest-itv)
- `app/services/google_ai_client.py:487-501` - Request construction
- `app/services/google_ai_client.py:657-674` - Response parsing
- `app/services/google_ai_client.py:705-739` - GCS download helper
