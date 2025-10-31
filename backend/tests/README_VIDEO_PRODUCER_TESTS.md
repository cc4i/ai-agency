# Video Producer Agent Tests

This directory contains comprehensive tests for the Video Producer Agent, including both unit tests (mocked) and integration tests (real API).

## What Was Fixed

### 1. **Mock Data Leakage Eliminated** ✅
**Before**: Video bytes from Veo API were discarded, fake `gs://` URL returned
```python
video_data = await veo_client.generate_video(...)  # API called
mock_url = f"gs://ai-agency-demo/videos/{asset_id}.mp4"  # ❌ Fake URL!
```

**After**: Real GCS upload with signed URL
```python
video_data = await veo_client.generate_video(...)
asset_id, video_url = await storage_client.upload_video(video_data)  # ✅ Real upload
```

### 2. **Incomplete Revise Method Fixed** ✅
**Before**: Only incremented revision number, didn't re-generate video
```python
output.video.revision_number += 1  # ❌ No actual revision
```

**After**: Fully functional revision with new video generation
```python
revised_video = await self._generate_video(
    ...
    revision_instructions=critique.revision_instructions,
)
```

### 3. **Error Handling Added** ✅
- Validates image_url before API call
- Checks for empty video data
- Wraps API calls in try/except
- Logs errors with tracebacks
- Graceful failure in revision workflow

### 4. **Storage Client Created** ✅
New `app/services/storage_client.py` provides:
- GCS upload for videos, audio, images
- Signed URL generation (7-day expiry)
- Proper error handling and logging

## Test Structure

```
tests/
├── conftest.py                              # Shared fixtures
├── pytest.ini                               # Pytest configuration
├── test_agents/
│   └── test_video_producer.py              # Unit tests (mocked)
└── integration/
    └── test_video_producer_api.py          # Integration tests (real API)
```

## Running Tests

### Unit Tests (Fast, No API Calls)
```bash
cd backend

# Run all unit tests
pytest tests/test_agents/test_video_producer.py -v

# Run specific test class
pytest tests/test_agents/test_video_producer.py::TestVideoProducerExecution -v

# Run with coverage
pytest tests/test_agents/test_video_producer.py --cov=app.agents.video_producer
```

### Integration Tests (Slow, Real API)
```bash
# Set up credentials first
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/credentials.json"
export GOOGLE_CLOUD_PROJECT="your-project-id"

# Run all integration tests
pytest -m integration tests/integration/test_video_producer_api.py -v

# Run specific integration test
pytest tests/integration/test_video_producer_api.py::TestVideoProducerRealAPI::test_generate_video_with_veo_api -v

# Run without slow tests
pytest -m "integration and not slow" tests/integration/test_video_producer_api.py -v
```

### All Tests
```bash
# Run everything (unit + integration)
pytest tests/ -v

# Run only unit tests (skip integration)
pytest tests/ -m "not integration" -v
```

## Test Coverage

### Unit Tests (`test_video_producer.py`)

**TestVideoProducerExecution**:
- ✅ `test_execute_success` - Successful video generation with mocked Veo and GCS
- ✅ `test_execute_missing_image_url` - Validation error for missing image
- ✅ `test_execute_empty_video_data` - Error handling for empty Veo response
- ✅ `test_execute_veo_api_error` - Veo API failure handling
- ✅ `test_execute_gcs_upload_error` - GCS upload failure handling
- ✅ `test_generation_params_stored` - Verify all params saved for revisions

**TestVideoProducerCritique**:
- ✅ `test_critique_pass` - Critique passes for good output
- ✅ `test_critique_duration_mismatch` - Fails on wrong duration
- ✅ `test_critique_missing_theme` - Fails when theme not emphasized
- ✅ `test_critique_missing_key_feature` - Fails when feature not shown

**TestVideoProducerRevision**:
- ✅ `test_revise_generates_new_video` - Revision actually re-generates video
- ✅ `test_revise_handles_failure` - Graceful failure handling

**TestVideoProducerIntegration**:
- ✅ `test_execute_with_critique_loop` - Full execution with critique

### Integration Tests (`test_video_producer_api.py`)

**TestVideoProducerRealAPI**:
- ✅ `test_generate_video_with_veo_api` - Real Veo 3.1 API call
- ✅ `test_generate_video_different_durations` - Test 4s, 6s, 8s videos
- ✅ `test_critique_real_video` - Critique on real generated video
- ✅ `test_revision_workflow_real_api` - Complete revision workflow
- ✅ `test_invalid_image_url_handling` - Error handling for invalid URLs
- ✅ `test_malformed_data_uri` - Error handling for malformed data

**TestVideoProducerProductAgnostic**:
- ✅ `test_beverage_category_video` - Beverage product video
- ✅ `test_electronics_category_video` - Electronics product video

**TestVideoProducerPerformance**:
- ✅ `test_video_generation_timeout` - Completes within 5 minutes
- ✅ `test_concurrent_video_generation` - Multiple concurrent generations

## Test Fixtures

### Unit Test Fixtures
- `video_producer` - VideoProducerAgent instance
- `sample_task` - Task parameters for Aura Smart Sneaker
- `sample_context` - Project context
- `mock_video_data` - Minimal valid MP4 bytes
- `mock_gcs_url` - Mock signed URL

### Integration Test Fixtures
- `sample_image_data_uri` - 1x1 pixel PNG as data URI
- `test_task` - Real task for Aura Smart Sneaker
- `beverage_task` - Task for beverage category
- `electronics_task` - Task for electronics category

## Expected Test Results

### Unit Tests
- **Duration**: ~2-5 seconds total
- **Success Rate**: 100% (all should pass)
- **API Calls**: 0 (all mocked)

### Integration Tests
- **Duration**: ~5-15 minutes total (Veo is slow)
- **Success Rate**: 95%+ (may fail due to quota limits)
- **API Calls**: 15-20 real Veo/GCS calls
- **Cost**: ~$0.50-$2.00 (Veo pricing)

## Troubleshooting

### Common Issues

**1. Integration tests skipped**
```
SKIPPED [1] tests/integration/test_video_producer_api.py:19: GOOGLE_APPLICATION_CREDENTIALS not set
```
**Solution**: Set credentials environment variable
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/key.json"
```

**2. Veo API quota exceeded**
```
google.api_core.exceptions.ResourceExhausted: 429 Quota exceeded
```
**Solution**: Wait for quota reset or request quota increase

**3. GCS bucket not found**
```
google.cloud.exceptions.NotFound: 404 Bucket 'ai-agency-demo' not found
```
**Solution**: Create bucket or update `GCS_BUCKET_NAME` in `.env`
```bash
gsutil mb gs://ai-agency-demo
```

**4. Veo generation timeout**
```
asyncio.exceptions.TimeoutError
```
**Solution**: Increase timeout in test (Veo can take 2-3 minutes)

**5. Import errors**
```
ImportError: cannot import name 'storage_client'
```
**Solution**: Ensure `storage_client.py` exists and is importable

## Adding New Tests

### Unit Test Template
```python
@pytest.mark.asyncio
async def test_new_feature(video_producer, sample_task, sample_context):
    """Test description."""
    # Mock dependencies
    with patch("app.agents.video_producer.veo_client") as mock_veo:
        mock_veo.generate_video = AsyncMock(return_value=b"video_data")

        # Test your feature
        result = await video_producer.execute(sample_task, sample_context)

        # Assertions
        assert result["video"]["asset_id"]
```

### Integration Test Template
```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_new_real_api_feature(video_producer, test_task, test_context):
    """Test description."""
    # Real API call
    result = await video_producer.execute(test_task, test_context)

    # Verify real results
    assert result["video"]["url"].startswith("https://")
```

## CI/CD Recommendations

### GitHub Actions Example
```yaml
name: Tests

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run unit tests
        run: pytest -m "not integration" tests/

  integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up credentials
        env:
          GCP_CREDENTIALS: ${{ secrets.GCP_CREDENTIALS }}
        run: echo "$GCP_CREDENTIALS" > /tmp/credentials.json
      - name: Run integration tests
        env:
          GOOGLE_APPLICATION_CREDENTIALS: /tmp/credentials.json
        run: pytest -m integration tests/
```

## Performance Benchmarks

| Test | Duration | API Calls | Cost (est.) |
|------|----------|-----------|-------------|
| Unit tests (all) | ~3s | 0 | $0 |
| Single video generation | ~90s | 1 Veo + 1 GCS | $0.08 |
| Full revision workflow | ~180s | 2 Veo + 2 GCS | $0.16 |
| All integration tests | ~600s | 15-20 calls | $1.20 |

## Next Steps

1. **Add E2E Tests**: Test complete campaign workflow with video generation
2. **Add Performance Tests**: Load testing with concurrent video generation
3. **Add Regression Tests**: Ensure video quality doesn't degrade
4. **Add Snapshot Tests**: Compare generated prompts against baselines
5. **Monitor API Costs**: Track Veo API usage in production

## Resources

- [Veo 3.1 Documentation](https://cloud.google.com/vertex-ai/docs/generative-ai/video/generate-video)
- [Google Cloud Storage Python Client](https://cloud.google.com/storage/docs/reference/libraries#client-libraries-install-python)
- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest Async](https://pytest-asyncio.readthedocs.io/)
