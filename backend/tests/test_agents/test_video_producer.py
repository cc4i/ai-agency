"""Unit tests for Video Producer Agent.

Tests video generation, critique loop, and revision workflow with mocked APIs.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.video_producer import VideoProducerAgent
from app.models.assets import CritiqueResult, VideoAsset, VideoProducerOutput


@pytest.fixture
def video_producer():
    """Create VideoProducerAgent instance."""
    return VideoProducerAgent()


@pytest.fixture
def sample_task():
    """Sample task parameters for video generation."""
    return {
        "image_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        "product_name": "Aura Smart Sneaker",
        "theme": "futuristic urban athlete",
        "key_features": ["glowing sole", "smart tracking", "adaptive cushioning"],
        "product_category": "footwear",
        "duration_seconds": 8,
    }


@pytest.fixture
def sample_context():
    """Sample context for agent execution."""
    return {
        "project_id": "test_project_123",
        "brief": {
            "product_name": "Aura Smart Sneaker",
            "theme": "futuristic urban athlete",
            "brand_tone": "innovative",
        },
    }


@pytest.fixture
def mock_video_data():
    """Mock video bytes data."""
    # Tiny valid MP4 header (minimal valid video)
    return b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2mp41"


@pytest.fixture
def mock_gcs_url():
    """Mock GCS signed URL."""
    return "https://storage.googleapis.com/ai-agency-demo/videos/vid_abc123.mp4?X-Goog-Signature=..."


class TestVideoProducerExecution:
    """Test video generation execution."""

    @pytest.mark.asyncio
    async def test_execute_success(
        self, video_producer, sample_task, sample_context, mock_video_data, mock_gcs_url
    ):
        """Test successful video generation."""
        # Mock Veo client
        with patch("app.agents.video_producer.veo_client") as mock_veo:
            mock_veo.generate_video = AsyncMock(return_value=mock_video_data)

            # Mock storage client
            with patch("app.agents.video_producer.storage_client") as mock_storage:
                mock_storage.upload_video = AsyncMock(
                    return_value=("vid_abc123", mock_gcs_url)
                )

                # Execute agent
                result = await video_producer.execute(sample_task, sample_context)

                # Verify result structure
                assert "video" in result
                assert "critique_notes" in result
                assert "revision_history" in result

                # Verify video asset
                video = result["video"]
                assert video["asset_id"] == "vid_abc123"
                assert video["url"] == mock_gcs_url
                assert video["duration_seconds"] == 8
                assert video["revision_number"] == 0

                # Verify Veo was called correctly
                mock_veo.generate_video.assert_called_once()
                call_kwargs = mock_veo.generate_video.call_args.kwargs
                assert "prompt" in call_kwargs
                assert "Aura Smart Sneaker" in call_kwargs["prompt"]
                assert "futuristic urban athlete" in call_kwargs["prompt"]
                assert call_kwargs["reference_image"] == sample_task["image_url"]
                assert call_kwargs["duration_seconds"] == 8

                # Verify GCS upload was called
                mock_storage.upload_video.assert_called_once()
                upload_call = mock_storage.upload_video.call_args
                assert upload_call.kwargs["video_data"] == mock_video_data

    @pytest.mark.asyncio
    async def test_execute_missing_image_url(
        self, video_producer, sample_task, sample_context
    ):
        """Test execution fails when image_url is missing."""
        # Remove image_url
        task_no_image = sample_task.copy()
        task_no_image["image_url"] = ""

        # Mock Veo client
        with patch("app.agents.video_producer.veo_client") as mock_veo:
            mock_veo.generate_video = AsyncMock()

            # Should raise ValueError
            with pytest.raises(ValueError, match="image_url is required"):
                await video_producer.execute(task_no_image, sample_context)

            # Veo should not be called
            mock_veo.generate_video.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_empty_video_data(
        self, video_producer, sample_task, sample_context
    ):
        """Test execution fails when Veo returns empty data."""
        # Mock Veo to return empty bytes
        with patch("app.agents.video_producer.veo_client") as mock_veo:
            mock_veo.generate_video = AsyncMock(return_value=b"")

            # Should raise RuntimeError
            with pytest.raises(RuntimeError, match="Veo API returned empty video data"):
                await video_producer.execute(sample_task, sample_context)

    @pytest.mark.asyncio
    async def test_execute_veo_api_error(
        self, video_producer, sample_task, sample_context
    ):
        """Test execution handles Veo API errors."""
        # Mock Veo to raise exception
        with patch("app.agents.video_producer.veo_client") as mock_veo:
            mock_veo.generate_video = AsyncMock(
                side_effect=Exception("Veo API quota exceeded")
            )

            # Should propagate exception
            with pytest.raises(Exception, match="Veo API quota exceeded"):
                await video_producer.execute(sample_task, sample_context)

    @pytest.mark.asyncio
    async def test_execute_gcs_upload_error(
        self, video_producer, sample_task, sample_context, mock_video_data
    ):
        """Test execution handles GCS upload errors."""
        # Mock Veo success
        with patch("app.agents.video_producer.veo_client") as mock_veo:
            mock_veo.generate_video = AsyncMock(return_value=mock_video_data)

            # Mock storage to fail
            with patch("app.agents.video_producer.storage_client") as mock_storage:
                mock_storage.upload_video = AsyncMock(
                    side_effect=Exception("GCS bucket not found")
                )

                # Should propagate exception
                with pytest.raises(Exception, match="GCS bucket not found"):
                    await video_producer.execute(sample_task, sample_context)

    @pytest.mark.asyncio
    async def test_generation_params_stored(
        self, video_producer, sample_task, sample_context, mock_video_data, mock_gcs_url
    ):
        """Test that generation parameters are properly stored for revisions."""
        with patch("app.agents.video_producer.veo_client") as mock_veo:
            mock_veo.generate_video = AsyncMock(return_value=mock_video_data)

            with patch("app.agents.video_producer.storage_client") as mock_storage:
                mock_storage.upload_video = AsyncMock(
                    return_value=("vid_abc123", mock_gcs_url)
                )

                result = await video_producer.execute(sample_task, sample_context)

                # Check generation params
                gen_params = result["video"]["generation_params"]
                assert gen_params["product_name"] == "Aura Smart Sneaker"
                assert gen_params["theme"] == "futuristic urban athlete"
                assert gen_params["product_category"] == "footwear"
                assert gen_params["key_features"] == sample_task["key_features"]
                assert gen_params["reference_image"] == sample_task["image_url"]


class TestVideoProducerCritique:
    """Test critique evaluation logic."""

    @pytest.mark.asyncio
    async def test_critique_pass(self, video_producer):
        """Test critique passes for good output."""
        result = {
            "video": {
                "asset_id": "vid_123",
                "url": "https://example.com/video.mp4",
                "duration_seconds": 15,
                "generation_params": {
                    "theme": "futuristic",
                    "key_features": ["glowing sole", "smart tracking"],
                },
                "revision_number": 0,
            },
            "critique_notes": None,
            "revision_history": [],
        }

        brief = {
            "video_duration": 15,
            "theme": "futuristic",
            "key_features": ["glowing sole"],
        }

        critique = await video_producer.critique(result, brief)

        assert critique.status == "PASS"
        assert critique.score == 1.0
        assert len(critique.issues) == 0

    @pytest.mark.asyncio
    async def test_critique_duration_mismatch(self, video_producer):
        """Test critique fails on duration mismatch."""
        result = {
            "video": {
                "asset_id": "vid_123",
                "url": "https://example.com/video.mp4",
                "duration_seconds": 8,  # Wrong duration
                "generation_params": {"theme": "futuristic", "key_features": []},
                "revision_number": 0,
            },
            "critique_notes": None,
            "revision_history": [],
        }

        brief = {
            "video_duration": 15,  # Expected 15 seconds
            "theme": "futuristic",
            "key_features": [],
        }

        critique = await video_producer.critique(result, brief)

        assert critique.status == "REVISE"
        assert critique.score < 1.0
        assert any("Duration" in issue for issue in critique.issues)

    @pytest.mark.asyncio
    async def test_critique_missing_theme(self, video_producer):
        """Test critique fails when theme not emphasized."""
        result = {
            "video": {
                "asset_id": "vid_123",
                "url": "https://example.com/video.mp4",
                "duration_seconds": 15,
                "generation_params": {
                    "theme": "wrong_theme",  # Theme mismatch
                    "key_features": [],
                },
                "revision_number": 0,
            },
            "critique_notes": None,
            "revision_history": [],
        }

        brief = {
            "video_duration": 15,
            "theme": "futuristic",
            "key_features": [],
        }

        critique = await video_producer.critique(result, brief)

        assert critique.status == "REVISE"
        assert any("theme" in issue.lower() for issue in critique.issues)
        assert "Strengthen futuristic visual elements" in critique.revision_instructions

    @pytest.mark.asyncio
    async def test_critique_missing_key_feature(self, video_producer):
        """Test critique fails when key feature not shown."""
        result = {
            "video": {
                "asset_id": "vid_123",
                "url": "https://example.com/video.mp4",
                "duration_seconds": 15,
                "generation_params": {
                    "theme": "futuristic",
                    "key_features": [],  # No features in params
                },
                "revision_number": 0,
            },
            "critique_notes": None,
            "revision_history": [],
        }

        brief = {
            "video_duration": 15,
            "theme": "futuristic",
            "key_features": ["glowing sole", "smart tracking"],
        }

        critique = await video_producer.critique(result, brief)

        assert critique.status == "REVISE"
        assert any("glowing sole" in issue for issue in critique.issues)
        assert "2-second close-up" in critique.revision_instructions


class TestVideoProducerRevision:
    """Test revision workflow."""

    @pytest.mark.asyncio
    async def test_revise_generates_new_video(
        self, video_producer, mock_video_data, mock_gcs_url
    ):
        """Test that revise actually re-generates the video."""
        original_result = {
            "video": {
                "asset_id": "vid_original",
                "url": "https://example.com/original.mp4",
                "duration_seconds": 8,
                "generation_params": {
                    "reference_image": "data:image/png;base64,ABC",
                    "product_name": "Test Product",
                    "theme": "modern",
                    "key_features": ["feature1"],
                    "product_category": "product",
                },
                "revision_number": 0,
            },
            "critique_notes": None,
            "revision_history": [],
        }

        critique = CritiqueResult(
            status="REVISE",
            score=0.7,
            issues=["Missing key feature"],
            revision_instructions="Add 2-second close-up of feature1",
        )

        # Mock Veo and storage
        with patch("app.agents.video_producer.veo_client") as mock_veo:
            mock_veo.generate_video = AsyncMock(return_value=mock_video_data)

            with patch("app.agents.video_producer.storage_client") as mock_storage:
                mock_storage.upload_video = AsyncMock(
                    return_value=("vid_revised", mock_gcs_url)
                )

                # Execute revision
                revised = await video_producer.revise(original_result, critique)

                # Verify Veo was called with revision instructions
                mock_veo.generate_video.assert_called_once()
                call_kwargs = mock_veo.generate_video.call_args.kwargs
                assert "Add 2-second close-up" in call_kwargs["prompt"]

                # Verify new video
                assert revised["video"]["asset_id"] == "vid_revised"
                assert revised["video"]["revision_number"] == 1
                assert revised["critique_notes"] == critique.revision_instructions

                # Verify revision history
                assert len(revised["revision_history"]) == 1
                assert "Revision 1" in revised["revision_history"][0]
                assert "Add 2-second close-up" in revised["revision_history"][0]

    @pytest.mark.asyncio
    async def test_revise_handles_failure(self, video_producer):
        """Test that revise handles re-generation failures gracefully."""
        original_result = {
            "video": {
                "asset_id": "vid_original",
                "url": "https://example.com/original.mp4",
                "duration_seconds": 8,
                "generation_params": {
                    "reference_image": "data:image/png;base64,ABC",
                    "product_name": "Test Product",
                    "theme": "modern",
                    "key_features": [],
                    "product_category": "product",
                },
                "revision_number": 0,
            },
            "critique_notes": None,
            "revision_history": [],
        }

        critique = CritiqueResult(
            status="REVISE",
            score=0.6,
            issues=["Issue"],
            revision_instructions="Fix issue",
        )

        # Mock Veo to fail
        with patch("app.agents.video_producer.veo_client") as mock_veo:
            mock_veo.generate_video = AsyncMock(side_effect=Exception("API error"))

            # Execute revision
            revised = await video_producer.revise(original_result, critique)

            # Should return original video with error note
            assert revised["video"]["asset_id"] == "vid_original"
            assert "Revision failed" in revised["critique_notes"]
            assert "API error" in revised["critique_notes"]


class TestVideoProducerIntegration:
    """Integration tests with multiple components."""

    @pytest.mark.asyncio
    async def test_execute_with_critique_loop(
        self, video_producer, sample_task, sample_context, mock_video_data, mock_gcs_url
    ):
        """Test complete execution with critique loop."""
        brief = {
            "video_duration": 8,
            "theme": "futuristic urban athlete",
            "key_features": ["glowing sole", "smart tracking"],
        }

        with patch("app.agents.video_producer.veo_client") as mock_veo:
            mock_veo.generate_video = AsyncMock(return_value=mock_video_data)

            with patch("app.agents.video_producer.storage_client") as mock_storage:
                # First upload - original
                # Second upload - revision
                mock_storage.upload_video = AsyncMock(
                    side_effect=[
                        ("vid_v1", "https://example.com/v1.mp4"),
                        ("vid_v2", "https://example.com/v2.mp4"),
                    ]
                )

                # Execute with critique
                result = await video_producer.execute_with_critique(
                    sample_task, sample_context, brief
                )

                # First video should pass critique (has features in task)
                assert result["video"]["revision_number"] == 0
                assert result["critique_notes"] is None or result["critique_notes"] == ""
