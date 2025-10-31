# Veo 3.1 API Flow - Long-Running Operations

This document explains the complete flow for video generation with Veo 3.1 API.

## Overview

Veo 3.1 uses a **long-running operation pattern** instead of immediate response. Video generation takes 60-180 seconds, so the API:
1. Returns an operation ID immediately
2. Requires polling the operation status
3. Returns video bytes or GCS URI when complete

## Step-by-Step Flow

### Step 1: Start Video Generation

**Endpoint:**
```
POST https://{location}-aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/publishers/google/models/veo-3.1-generate-preview:predictLongRunning
```

**Request:**
```json
{
  "instances": [{
    "prompt": "Create a dynamic 8-second social media video...",
    "image": {
      "bytesBase64Encoded": "iVBORw0KG...",
      "mimeType": "image/png"
    }
  }],
  "parameters": {
    "sampleCount": 1,
    "durationSeconds": 8,
    "generateAudio": false,
    "storageUri": "gs://ai-agency-demo/veo_videos/veo_abc123"
  }
}
```

**Note**: Including `storageUri` is more efficient - videos are saved to GCS instead of returning 5-10MB base64 strings in the response.

**Response (immediate):**
```json
{
  "name": "projects/multi-gke-ops/locations/us-central1/publishers/google/models/veo-3.1-generate-preview/operations/1234567890"
}
```

### Step 2: Poll Operation Status

**Endpoint:**
```
POST https://{location}-aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/publishers/google/models/veo-3.1-generate-preview:fetchPredictOperation
```

**Request:**
```json
{
  "operationName": "projects/multi-gke-ops/locations/us-central1/publishers/google/models/veo-3.1-generate-preview/operations/1234567890"
}
```

**Response (while running):**
```json
{
  "done": false
}
```

**Response (when complete):**
```json
{
  "done": true,
  "response": {
    "videos": [{
      "video": {
        "bytesBase64Encoded": "{5-10MB base64 video data}"
      }
    }]
  }
}
```

OR (if using GCS storage):
```json
{
  "done": true,
  "response": {
    "videos": [{
      "video": {
        "gcsUri": "gs://bucket-name/path/to/video.mp4"
      }
    }]
  }
}
```

**Note**: The response uses a `videos` list, not `predictions`. Each entry has a `video` object containing either `bytesBase64Encoded` or `gcsUri`.

### Step 3: Extract Video

**Option A: Base64 Response**
```python
video_obj = result["response"]["videos"][0]["video"]
video_b64 = video_obj["bytesBase64Encoded"]
video_bytes = base64.b64decode(video_b64)
```

**Option B: GCS URI**
```python
video_obj = result["response"]["videos"][0]["video"]
gcs_uri = video_obj["gcsUri"]
# Download from GCS
from google.cloud import storage
storage_client = storage.Client()
bucket_name, blob_name = parse_gcs_uri(gcs_uri)
video_bytes = storage_client.bucket(bucket_name).blob(blob_name).download_as_bytes()
```

## Implementation Details

### VeoClient.generate_video()

Located in `app/services/google_ai_client.py:426-547`

**Flow:**
1. Build request with prompt and optional reference image
2. Call `:predictLongRunning` endpoint → get operation name
3. Poll `:fetchPredictOperation` every 5 seconds (max 5 minutes)
4. Extract video from response (base64 or GCS)
5. Return video bytes

### Polling Configuration

```python
max_wait_seconds = 300  # 5 minutes timeout
poll_interval_seconds = 5  # Poll every 5 seconds
```

**Typical generation time:**
- 4-second video: ~60-90 seconds
- 6-second video: ~90-120 seconds
- 8-second video: ~120-180 seconds

### Error Handling

**Common errors:**
- `429 Too Many Requests` - Quota exceeded (retry with exponential backoff)
- `400 Bad Request` - Invalid parameters (check prompt, image format, duration)
- `RuntimeError: Operation timed out` - Generation took longer than max_wait_seconds
- `RuntimeError: Veo operation failed` - API error during generation

## Testing

### Unit Tests (Mocked)
```bash
pytest tests/test_agents/test_video_producer.py -v
```

### Integration Tests (Real API)
```bash
export GOOGLE_APPLICATION_CREDENTIALS="path/to/credentials.json"
pytest -m integration tests/integration/test_video_producer_api.py -v
```

**Warning:** Integration tests make real API calls and may hit quota limits (429 errors).

## Quota Limits

Veo 3.1 has strict quota limits:
- **Free tier**: Limited requests per day
- **Paid tier**: Higher limits but still rate-limited

If you hit 429 errors:
1. Wait for quota reset (usually 24 hours)
2. Request quota increase in GCP Console
3. Implement exponential backoff in production

## References

- [Veo Video Generation API Documentation](https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/veo-video-generation)
- [Long-Running Operations Pattern](https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/veo-video-generation#rest-itv)
- `app/services/google_ai_client.py` - VeoClient implementation
- `app/agents/video_producer.py` - Video Producer Agent
- `tests/integration/test_video_producer_api.py` - Real API tests
