# Vertex AI Migration - Complete

**Date**: 2025-10-29
**Status**: ✅ Ready for testing

## What Changed

### 1. Updated Dependencies

Updated to latest Google AI packages:
- `google-cloud-aiplatform`: **1.42.0 → 1.122.0**
- `google-generativeai**: **0.3.2 → 0.8.5**

**File**: `backend/pyproject.toml`

### 2. Switched to Vertex AI Endpoint

**Old** (Google AI API):
```
wss://generativelanguage.googleapis.com/ws/v1/models/gemini-2.5-flash-native-audio-preview-09-2025
```

**New** (Vertex AI):
```
wss://us-central1-aiplatform.googleapis.com/ws/google.cloud.aiplatform.v1beta1.LlmBidiService/BidiGenerateContent
```

**File**: `backend/app/config.py:45-47`

### 3. Updated Authentication

**Old**: API Key authentication
```python
await websockets.connect(
    f"{url}?key={api_key}",
    additional_headers={"Content-Type": "application/json"}
)
```

**New**: OAuth 2.0 Bearer Token (Vertex AI)
```python
credentials, project = google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
auth_req = google.auth.transport.requests.Request()
credentials.refresh(auth_req)

await websockets.connect(
    url,
    additional_headers={
        "Authorization": f"Bearer {credentials.token}",
        "x-goog-user-project": project,
    }
)
```

**File**: `backend/app/services/gemini_live.py:234-254`

### 4. Updated Model Path Format

**Old**: Direct model name
```python
"model": "models/gemini-2.5-flash-native-audio-preview-09-2025"
```

**New**: Full Vertex AI resource path
```python
model_path = f"projects/{project}/locations/{location}/publishers/google/models/gemini-2.0-flash-exp"
```

**File**: `backend/app/services/gemini_live.py:262`

### 5. Using Latest Experimental Model

**Model**: `gemini-2.0-flash-exp`
- Latest experimental Gemini model
- Should have improved audio quality
- Supports native audio input/output

**Voice**: Still using "Kore" (changed from previous "Charon")

## Files Modified

1. ✅ `backend/pyproject.toml` - Updated dependencies
2. ✅ `backend/app/config.py` - Changed WebSocket URL
3. ✅ `backend/app/services/gemini_live.py` - Updated authentication and model path
4. ✅ `backend/.env.example` - Updated example configuration

## Prerequisites

Ensure your `.env` file has:

```bash
# Required for Vertex AI
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1

# Optional (WebSocket URL is now in config.py)
GEMINI_LIVE_WS_URL=wss://us-central1-aiplatform.googleapis.com/ws/google.cloud.aiplatform.v1beta1.LlmBidiService/BidiGenerateContent
```

## Testing Steps

### 1. Verify Backend Connection

The backend should start successfully:

```bash
cd backend
uv run uvicorn app.main:app --reload
```

**Expected logs**:
```
✓ Authenticated with project: your-project-id
✓ Connected to Gemini Live WebSocket (Vertex AI)
📤 Sent setup with model: projects/your-project/locations/us-central1/publishers/google/models/gemini-2.0-flash-exp
📤 Voice: Kore
```

### 2. Test Audio Quality

Open the frontend and have a conversation. Then:

**Frontend console**:
```javascript
// Download diagnostics logs
logger.downloadLogs('text')
```

**Backend logs**:
```bash
tail -n 100 backend/logs/backend.log
```

### 3. Compare Audio Quality

**Previous baseline** (from `AUDIO_NOISE_DIAGNOSIS.md`):
- ✅ GOOD chunks: 67%
- ⚠️ NEEDS INVESTIGATION: 33%
- Issues: High zero-crossing rate (>0.5), clipping (1-2%)

**New target**:
- ✅ GOOD chunks: >80% (improvement)
- ⚠️ NEEDS INVESTIGATION: <20%

**How to analyze**:
1. Download frontend logs: `logger.downloadLogs('text')`
2. Search for "✅ GOOD" and "⚠️ NEEDS INVESTIGATION"
3. Count occurrences
4. Calculate percentage

### 4. Check for Errors

**If connection fails**, check logs for:

**401 Unauthorized**:
- Check `GOOGLE_APPLICATION_CREDENTIALS` path is correct
- Verify service account has `Vertex AI User` role
- Run: `gcloud auth application-default print-access-token` to test auth

**403 Forbidden**:
- Enable Vertex AI API: `gcloud services enable aiplatform.googleapis.com`
- Check project has billing enabled

**404 Not Found**:
- Model name might be incorrect
- Try different model: `gemini-2.0-flash-preview`

**500 Internal Server Error**:
- Check Vertex AI quota limits
- Verify region is correct (`us-central1`)

## Expected Benefits

1. **Better Audio Quality**: Newer model should have improved TTS synthesis
2. **Latest Features**: Access to newest Gemini capabilities
3. **Enterprise Support**: Vertex AI provides better SLA and support
4. **Unified Platform**: Consistent with other Google Cloud services

## Rollback Plan

If Vertex AI has issues, revert to Google AI API:

```bash
# Revert config.py
gemini_live_ws_url: str = "wss://generativelanguage.googleapis.com/ws/v1/models/gemini-2.5-flash-native-audio-preview-09-2025"

# Revert gemini_live.py connection method
gemini_ws = await websockets.connect(
    f"{settings.gemini_live_ws_url}?key={settings.gemini_api_key}",
    additional_headers={"Content-Type": "application/json"}
)

# Revert model in setup message
"model": "models/gemini-2.5-flash-native-audio-preview-09-2025"
```

## Next Steps

1. ✅ Dependencies updated
2. ✅ Code migrated to Vertex AI
3. ✅ Backend running successfully
4. 🔄 **Test audio quality** (waiting for user)
5. ⏳ Compare results with previous baseline
6. ⏳ Adjust if needed (try different voice/model)

## Reference

- **Vertex AI Gemini API**: https://cloud.google.com/vertex-ai/docs/generative-ai/multimodal/gemini-api
- **Gemini Live API**: https://ai.google.dev/api/live
- **Authentication**: https://cloud.google.com/docs/authentication
- **Available Models**: https://cloud.google.com/vertex-ai/docs/generative-ai/learn/models
