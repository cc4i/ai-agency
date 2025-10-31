"""Integration tests for Video Producer Agent with real Veo API.

These tests make real API calls to Google Cloud services.
Run with: pytest -m integration

Requirements:
- GOOGLE_APPLICATION_CREDENTIALS environment variable set
- Valid Google Cloud project with Vertex AI enabled
- Veo 3.1 API access enabled
"""

import os
import pytest
import base64

from app.agents.video_producer import VideoProducerAgent
from app.config import settings


# Skip all tests if credentials not configured
pytestmark = pytest.mark.skipif(
    not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
    reason="GOOGLE_APPLICATION_CREDENTIALS not set - skipping integration tests",
)


@pytest.fixture
def video_producer():
    """Create VideoProducerAgent instance."""
    return VideoProducerAgent()


@pytest.fixture
def sample_image_data_uri():
    """Create a 720p test image as data URI (Veo minimum requirement)."""
    from PIL import Image
    import io

    # Create a 1280x720 (720p) image with gradient
    # Veo requires minimum 720p resolution
    width, height = 1280, 720
    img = Image.new('RGB', (width, height))

    # Draw a simple gradient (purple to blue) to make it visually distinct
    pixels = img.load()
    for y in range(height):
        for x in range(width):
            # Gradient from purple (128, 0, 255) to blue (0, 0, 255)
            r = int(128 * (1 - x / width))
            g = 0
            b = 255
            pixels[x, y] = (r, g, b)

    # Add some visual elements (centered white rectangle with "TEST" text area)
    # This makes it look more like a product image
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    # White rectangle in center
    draw.rectangle([width//4, height//4, 3*width//4, 3*height//4], fill=(255, 255, 255))

    # Save to bytes as PNG
    img_bytes_io = io.BytesIO()
    img.save(img_bytes_io, format='PNG')
    img_bytes = img_bytes_io.getvalue()

    # Convert to base64 data URI
    b64_image = base64.b64encode(img_bytes).decode("utf-8")
    return f"data:image/png;base64,{b64_image}"


@pytest.fixture
def test_task(sample_image_data_uri):
    """Test task for Aura Smart Sneaker demo."""
    return {
        "image_url": sample_image_data_uri,
        "product_name": "Aura Smart Sneaker",
        "theme": "futuristic urban athlete",
        "key_features": ["glowing sole", "smart tracking", "adaptive cushioning"],
        "product_category": "footwear",
        "duration_seconds": 8,  # Veo 3.1 supports 4, 6, or 8 seconds
    }


@pytest.fixture
def test_context():
    """Test context."""
    return {
        "project_id": "integration_test_project",
        "brief": {
            "product_name": "Aura Smart Sneaker",
            "theme": "futuristic urban athlete",
            "brand_tone": "innovative",
        },
    }


@pytest.mark.integration
@pytest.mark.asyncio
class TestVideoProducerRealAPI:
    """Integration tests with real Veo API."""

    async def test_generate_video_with_veo_api(
        self, video_producer, test_task, test_context
    ):
        """
        Test video generation with real Veo 3.1 API.

        This test:
        1. Calls real Veo API to generate video
        2. Uploads video to real GCS bucket
        3. Returns signed URL

        Note: This test is SLOW (~60-120 seconds for Veo generation)
        """
        # Execute video generation
        result = await video_producer.execute(test_task, test_context)

        # Verify result structure
        assert "video" in result
        assert "critique_notes" in result
        assert "revision_history" in result

        # Verify video asset
        video = result["video"]
        assert video["asset_id"].startswith("vid_")
        assert video["url"].startswith("https://storage.googleapis.com")
        assert video["duration_seconds"] == 8
        assert video["revision_number"] == 0

        # Verify generation parameters
        gen_params = video["generation_params"]
        assert "Aura Smart Sneaker" in gen_params["prompt"]
        assert "futuristic urban athlete" in gen_params["prompt"]
        assert gen_params["product_name"] == "Aura Smart Sneaker"
        assert gen_params["theme"] == "futuristic urban athlete"
        assert "glowing sole" in gen_params["key_features"]

        # Print results for manual verification
        print(f"\n✅ Video generated successfully!")
        print(f"Asset ID: {video['asset_id']}")
        print(f"URL: {video['url'][:100]}...")
        print(f"Duration: {video['duration_seconds']}s")

    async def test_generate_video_different_durations(
        self, video_producer, test_task, test_context
    ):
        """Test video generation with different duration options (4, 6, 8 seconds)."""
        durations = [4, 6, 8]

        for duration in durations:
            task = test_task.copy()
            task["duration_seconds"] = duration

            result = await video_producer.execute(task, test_context)

            assert result["video"]["duration_seconds"] == duration
            print(f"✅ Generated {duration}s video: {result['video']['asset_id']}")

    async def test_critique_real_video(
        self, video_producer, test_task, test_context
    ):
        """Test critique evaluation on real generated video."""
        # Generate video
        result = await video_producer.execute(test_task, test_context)

        # Critique against brief
        brief = {
            "video_duration": 8,
            "theme": "futuristic urban athlete",
            "key_features": ["glowing sole", "smart tracking"],
        }

        critique = await video_producer.critique(result, brief)

        # Print critique results
        print(f"\n📊 Critique Results:")
        print(f"Status: {critique.status}")
        print(f"Score: {critique.score}")
        print(f"Issues: {critique.issues}")
        if critique.revision_instructions:
            print(f"Revision Instructions: {critique.revision_instructions}")

        # Basic validation
        assert critique.status in ["PASS", "REVISE"]
        assert 0.0 <= critique.score <= 1.0

    async def test_revision_workflow_real_api(
        self, video_producer, test_task, test_context
    ):
        """
        Test complete revision workflow with real API.

        This test:
        1. Generates initial video
        2. Creates a critique requiring revision
        3. Generates revised video with new instructions

        Note: This test is VERY SLOW (~2-4 minutes for 2 videos)
        """
        # Generate initial video
        result = await video_producer.execute(test_task, test_context)
        original_asset_id = result["video"]["asset_id"]

        print(f"\n🎬 Original video: {original_asset_id}")

        # Create a critique requiring revision
        from app.models.assets import CritiqueResult

        critique = CritiqueResult(
            status="REVISE",
            score=0.75,
            issues=["Need more emphasis on glowing sole feature"],
            revision_instructions="Add 2-second close-up clearly showing the glowing sole lighting effect",
        )

        # Execute revision
        revised_result = await video_producer.revise(result, critique)

        # Verify revision
        revised_video = revised_result["video"]
        assert revised_video["asset_id"] != original_asset_id  # New video generated
        assert revised_video["revision_number"] == 1
        assert revised_result["critique_notes"] == critique.revision_instructions
        assert len(revised_result["revision_history"]) == 1

        print(f"🔄 Revised video: {revised_video['asset_id']}")
        print(f"Revision history: {revised_result['revision_history']}")

        # Verify revision instructions were included in prompt
        gen_params = revised_video["generation_params"]
        assert "glowing sole" in gen_params["prompt"].lower()

    async def test_invalid_image_url_handling(
        self, video_producer, test_task, test_context
    ):
        """Test error handling for invalid image URL."""
        task = test_task.copy()
        task["image_url"] = ""  # Empty image URL

        with pytest.raises(ValueError, match="image_url is required"):
            await video_producer.execute(task, test_context)

    async def test_malformed_data_uri(
        self, video_producer, test_task, test_context
    ):
        """Test error handling for malformed data URI."""
        task = test_task.copy()
        task["image_url"] = "data:image/png;base64,INVALID_BASE64!!!"

        # Should fail during Veo API call (invalid base64)
        with pytest.raises(Exception):
            await video_producer.execute(task, test_context)


@pytest.mark.integration
@pytest.mark.asyncio
class TestVideoProducerProductAgnostic:
    """Test product-agnostic video generation with various categories."""

    @pytest.fixture
    def beverage_task(self, sample_image_data_uri):
        """Task for beverage product."""
        return {
            "image_url": sample_image_data_uri,
            "product_name": "Quantum Energy Drink",
            "theme": "neon cyberpunk",
            "key_features": ["zero sugar", "nano-particles", "instant energy"],
            "product_category": "beverage",
            "duration_seconds": 6,
        }

    @pytest.fixture
    def electronics_task(self, sample_image_data_uri):
        """Task for electronics product."""
        return {
            "image_url": sample_image_data_uri,
            "product_name": "NeuralLink Earbuds",
            "theme": "minimalist tech",
            "key_features": ["AI noise cancellation", "biometric sensors", "wireless charging"],
            "product_category": "electronics",
            "duration_seconds": 8,
        }

    async def test_beverage_category_video(
        self, video_producer, beverage_task, test_context
    ):
        """Test video generation for beverage category."""
        result = await video_producer.execute(beverage_task, test_context)

        video = result["video"]
        gen_params = video["generation_params"]

        # Verify product-specific content
        assert "Quantum Energy Drink" in gen_params["prompt"]
        assert "beverage" in gen_params["prompt"]
        assert "neon cyberpunk" in gen_params["prompt"]
        assert gen_params["product_category"] == "beverage"

        print(f"✅ Beverage video: {video['asset_id']}")

    async def test_electronics_category_video(
        self, video_producer, electronics_task, test_context
    ):
        """Test video generation for electronics category."""
        result = await video_producer.execute(electronics_task, test_context)

        video = result["video"]
        gen_params = video["generation_params"]

        # Verify product-specific content
        assert "NeuralLink Earbuds" in gen_params["prompt"]
        assert "electronics" in gen_params["prompt"]
        assert "minimalist tech" in gen_params["prompt"]

        print(f"✅ Electronics video: {video['asset_id']}")


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
class TestVideoProducerPerformance:
    """Performance and stress tests."""

    async def test_video_generation_timeout(
        self, video_producer, test_task, test_context
    ):
        """Test that video generation completes within reasonable time."""
        import asyncio
        import time

        start_time = time.time()

        # Should complete within 5 minutes (Veo can be slow)
        result = await asyncio.wait_for(
            video_producer.execute(test_task, test_context),
            timeout=300.0,  # 5 minutes
        )

        elapsed = time.time() - start_time
        print(f"⏱️  Video generation took {elapsed:.2f} seconds")

        assert "video" in result

    async def test_concurrent_video_generation(
        self, video_producer, test_task, test_context
    ):
        """Test generating multiple videos concurrently."""
        import asyncio

        # Create 3 tasks
        tasks = [
            video_producer.execute(test_task, test_context)
            for _ in range(3)
        ]

        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify all succeeded
        successful = [r for r in results if not isinstance(r, Exception)]
        print(f"✅ Generated {len(successful)}/3 videos concurrently")

        assert len(successful) >= 2  # At least 2 should succeed
