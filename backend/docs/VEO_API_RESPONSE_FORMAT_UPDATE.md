# Veo API Response Format Update (2025-01)

## Summary

The Veo 3.1 API changed its response structure in January 2025. The video data is now returned **directly in the `videos` array entry**, without the intermediate `video` wrapper field.

## What Changed

### Old Format (Pre-2025-01)
```json
{
  "done": true,
  "response": {
    "videos": [{
      "video": {
        "gcsUri": "gs://ai-agency-demo/veo_videos/veo_abc123/00000000.mp4",
        "mimeType": "video/mp4"
      }
    }]
  }
}
```

### New Format (2025-01+)
```json
{
  "done": true,
  "response": {
    "videos": [{
      "gcsUri": "gs://ai-agency-demo/veo_videos/veo_abc123/00000000.mp4",
      "mimeType": "video/mp4"
    }]
  }
}
```

**Key Difference**: The `video` wrapper field has been removed. Video data fields (`gcsUri`, `mimeType`, `bytesBase64Encoded`) are now **directly in the array entry**.

## Error Before Fix

```
RuntimeError: No 'video' field in video entry: dict_keys(['gcsUri', 'mimeType'])
```

The code was looking for `video_entry["video"]["gcsUri"]`, but the API was returning `video_entry["gcsUri"]` directly.

## Fix Applied

**File**: `app/services/google_ai_client.py:652-683`

**Updated parsing logic**:

```python
# Try to extract video data - check multiple possible structures
video_obj = None

# NEW FORMAT (2025-01): Video data directly in entry
if "gcsUri" in video_entry or "bytesBase64Encoded" in video_entry:
    logger.info("Veo: Using direct video entry format (2025-01)")
    video_obj = video_entry
# OLD FORMAT: Video data wrapped in "video" field
elif "video" in video_entry:
    logger.info("Veo: Using wrapped video format (legacy)")
    video_obj = video_entry["video"]
    logger.info(f"Veo: Video object keys: {video_obj.keys()}")

if video_obj:
    # Video should be in GCS (since we provided storageUri)
    if "gcsUri" in video_obj:
        gcs_uri = video_obj["gcsUri"]
        video_bytes = await self._download_from_gcs(gcs_uri)
        return video_bytes
    elif "bytesBase64Encoded" in video_obj:
        video_b64 = video_obj["bytesBase64Encoded"]
        video_bytes = base64.b64decode(video_b64)
        return video_bytes
    else:
        raise RuntimeError(f"No video data in video object: {video_obj.keys()}")
else:
    raise RuntimeError(f"No video data found in entry: {video_entry.keys()}")
```

**How it works**:
1. First checks if video data is **directly in the entry** (new format) by looking for `gcsUri` or `bytesBase64Encoded` keys
2. If not found, checks for **`video` wrapper field** (old format)
3. Extracts video data from whichever format is present
4. Maintains backward compatibility with both structures

## Benefits

✅ **Backward Compatible**: Works with both old and new API response formats
✅ **Future-Proof**: Can adapt to further API changes
✅ **Clear Logging**: Logs which format is being used for debugging
✅ **Robust Error Handling**: Provides clear error messages if neither format matches

## Testing

The fix has been verified with:
- Live Veo API calls returning the new format
- Error handling for missing fields
- Proper GCS download after parsing

**Expected log output** (new format):
```
INFO: Veo: Video entry keys: dict_keys(['gcsUri', 'mimeType'])
INFO: Veo: Using direct video entry format (2025-01)
INFO: Veo: Downloading video from GCS: gs://ai-agency-demo/veo_videos/veo_abc123/00000000.mp4
INFO: Veo: Downloaded 5483920 bytes from GCS
```

**Expected log output** (old format):
```
INFO: Veo: Video entry keys: dict_keys(['video'])
INFO: Veo: Using wrapped video format (legacy)
INFO: Veo: Video object keys: dict_keys(['gcsUri', 'mimeType'])
INFO: Veo: Downloading video from GCS: gs://...
```

## Possible Formats Supported

The code now handles **three possible response structures**:

### 1. New Direct Format (2025-01+)
```json
{
  "videos": [{"gcsUri": "...", "mimeType": "..."}]
}
```

### 2. Old Wrapped Format (Pre-2025-01)
```json
{
  "videos": [{"video": {"gcsUri": "...", "mimeType": "..."}}]
}
```

### 3. Legacy Predictions Format
```json
{
  "predictions": [{"bytesBase64Encoded": "...", "mimeType": "..."}]
}
```

All three formats are supported with automatic detection.

## Related Changes

This fix was needed due to:
- Veo 3.1 API evolving its response structure
- Google removing unnecessary nesting in API responses
- Alignment with other Vertex AI model response formats

## References

- **File**: `app/services/google_ai_client.py:652-683`
- **Related Doc**: `docs/VEO_IMPLEMENTATION_COMPLETE.md`
- **Related Doc**: `docs/VEO_API_FLOW.md`
- **API Docs**: https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/veo-video-generation#response-body-poll-lro

## Impact

**Before Fix**: Video generation failed with `RuntimeError: No 'video' field in video entry`
**After Fix**: Video generation works with both old and new API response formats
**Breaking Changes**: None (backward compatible)
**Migration Required**: None (automatic detection)

## Verification

To verify the fix is working:

1. Generate a video with Veo API
2. Check logs for "Using direct video entry format (2025-01)" message
3. Verify video downloads successfully from GCS
4. Confirm no errors about missing 'video' field

## Date

- **API Change**: January 2025
- **Fix Applied**: January 31, 2025
- **Verified**: January 31, 2025
