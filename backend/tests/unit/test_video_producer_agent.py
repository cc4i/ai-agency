"""Level 1 Component Tests - Video Producer Agent.

Tests individual Video Producer Agent functionality:
- Output format validation
- Video generation (8 seconds for Veo 3.1)
- Critique and revision loop
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, patch, Mock

from app.agents.video_producer import VideoProducerAgent


@pytest.mark.asyncio
async def test_video_producer_output_format(sample_video_task):
    """Test that Video Producer returns correct output format."""
    agent = VideoProducerAgent()

    # veo_client.generate_video() returns bytes
    mock_video_bytes = b'fake_video_data'

    with patch('app.agents.video_producer.veo_client') as mock_veo, \
         patch('app.agents.video_producer.storage_client') as mock_storage:
        mock_veo.generate_video = AsyncMock(return_value=mock_video_bytes)
        mock_storage.upload_video = AsyncMock(return_value=("video_123", "gs://bucket/video_123.mp4"))

        result = await agent.execute(sample_video_task, {})

    assert isinstance(result, dict)
    assert "video" in result
    assert result["video"]["url"] is not None
    assert result["video"]["duration_seconds"] > 0


@pytest.mark.asyncio
async def test_video_producer_15_second_duration(sample_video_task):
    """Test that video duration is set correctly."""
    agent = VideoProducerAgent()

    # veo_client.generate_video() returns bytes
    mock_video_bytes = b'fake_video_data'

    # Task specifies 8 seconds (Veo 3.1 supports 4, 6, or 8)
    task = {**sample_video_task, "duration_seconds": 8}

    with patch('app.agents.video_producer.veo_client') as mock_veo, \
         patch('app.agents.video_producer.storage_client') as mock_storage:
        mock_veo.generate_video = AsyncMock(return_value=mock_video_bytes)
        mock_storage.upload_video = AsyncMock(return_value=("video_123", "gs://bucket/video_123.mp4"))

        result = await agent.execute(task, {})

    assert result["video"]["duration_seconds"] == 8


@pytest.mark.asyncio
async def test_video_producer_critique_triggers_revision(sample_video_task):
    """Test that critique can trigger revision."""
    from app.models.assets import CritiqueResult

    agent = VideoProducerAgent()

    # veo_client.generate_video() returns bytes
    mock_video_bytes_v1 = b'fake_video_data_v1'
    mock_video_bytes_v2 = b'fake_video_data_v2'

    # First generation
    with patch('app.agents.video_producer.veo_client') as mock_veo, \
         patch('app.agents.video_producer.storage_client') as mock_storage:
        mock_veo.generate_video = AsyncMock(return_value=mock_video_bytes_v1)
        mock_storage.upload_video = AsyncMock(return_value=("video_v1", "gs://bucket/video_v1.mp4"))

        result_v1 = await agent.execute(sample_video_task, {})

    # Critique says missing glowing sole
    critique = CritiqueResult(
        status="REVISE",
        score=0.6,
        issues=["Missing glowing sole close-up"],
        revision_instructions="Add 2-second close-up of glowing sole"
    )

    # Revision
    with patch('app.agents.video_producer.veo_client') as mock_veo, \
         patch('app.agents.video_producer.storage_client') as mock_storage:
        mock_veo.generate_video = AsyncMock(return_value=mock_video_bytes_v2)
        mock_storage.upload_video = AsyncMock(return_value=("video_v2", "gs://bucket/video_v2.mp4"))

        result_v2 = await agent.revise(result_v1, critique)

    # Verify revision number incremented
    assert result_v2["video"]["revision_number"] == 1
    assert result_v2["video"]["url"] != result_v1["video"]["url"]


@pytest.mark.asyncio
async def test_video_producer_max_revisions():
    """Test that max 2 revisions are allowed."""
    from app.models.assets import CritiqueResult

    agent = VideoProducerAgent()

    task = {
        "task_id": "video_max_rev",
        "description": "Test max revisions",
        "product_name": "Test Product",
        "image_url": "data:image/png;base64,abc123",
        "theme": "modern",
        "key_features": ["feature1"],
        "product_category": "product",
        "duration_seconds": 8
    }

    # Generate initial video
    with patch('app.agents.video_producer.veo_client') as mock_veo, \
         patch('app.agents.video_producer.storage_client') as mock_storage:
        mock_veo.generate_video = AsyncMock(return_value=b'video_v1')
        mock_storage.upload_video = AsyncMock(return_value=("v1", "gs://bucket/v1.mp4"))
        result = await agent.execute(task, {})

    # Revision 1
    critique_1 = CritiqueResult(status="REVISE", score=0.5, issues=["Issue 1"], revision_instructions="Fix 1")
    with patch('app.agents.video_producer.veo_client') as mock_veo, \
         patch('app.agents.video_producer.storage_client') as mock_storage:
        mock_veo.generate_video = AsyncMock(return_value=b'video_v2')
        mock_storage.upload_video = AsyncMock(return_value=("v2", "gs://bucket/v2.mp4"))
        result = await agent.revise(result, critique_1)

    assert result["video"]["revision_number"] == 1

    # Revision 2
    critique_2 = CritiqueResult(status="REVISE", score=0.6, issues=["Issue 2"], revision_instructions="Fix 2")
    with patch('app.agents.video_producer.veo_client') as mock_veo, \
         patch('app.agents.video_producer.storage_client') as mock_storage:
        mock_veo.generate_video = AsyncMock(return_value=b'video_v3')
        mock_storage.upload_video = AsyncMock(return_value=("v3", "gs://bucket/v3.mp4"))
        result = await agent.revise(result, critique_2)

    assert result["video"]["revision_number"] == 2


@pytest.mark.asyncio
async def test_video_producer_error_handling():
    """Test Video Producer error handling."""
    agent = VideoProducerAgent()

    task = {"task_id": "error_test"}  # Missing required fields

    with patch('app.agents.video_producer.veo_client') as mock_client:
        mock_client.generate_video = AsyncMock(side_effect=Exception("Veo API Error"))

        with pytest.raises(Exception):
            await agent.execute(task, {})


print("✅ Video Producer Agent Level 1 tests created")
