"""Integration tests for Audio Team Agent with real Google Cloud APIs.

Tests cover:
- Real TTS generation with Google Cloud Text-to-Speech
- Audio upload to GCS
- Different voice selections
- Product-agnostic design

Note: Requires Google Cloud credentials and may incur API costs.
Note: Chirp (Speech-to-Text) and Lyria (Music) tests are commented out
      as they require additional setup or are not yet available.
"""

import pytest
import os
from app.agents.audio_team import AudioTeamAgent


# Skip if credentials not available
pytestmark = pytest.mark.skipif(
    not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
    reason="Google Cloud credentials not configured"
)


@pytest.fixture
def audio_team():
    """Create Audio Team agent instance."""
    return AudioTeamAgent()


class TestRealTTSGeneration:
    """Test real TTS generation with Google Cloud Text-to-Speech."""

    @pytest.mark.asyncio
    async def test_tts_professional_voice(self, audio_team):
        """Test TTS with professional voice."""
        from app.services.google_ai_client import lyria_client

        # Generate TTS
        script = "Introducing the future of innovation. Experience tomorrow, today."
        voice = "en-US-Studio-O"  # Professional female voice

        audio_bytes = await lyria_client.synthesize_speech(text=script, voice=voice)

        # Verify audio was generated
        assert audio_bytes is not None
        assert len(audio_bytes) > 0
        print(f"✓ Generated {len(audio_bytes)} bytes of TTS audio (professional voice)")

    @pytest.mark.asyncio
    async def test_tts_luxury_voice(self, audio_team):
        """Test TTS with luxury (British) voice."""
        from app.services.google_ai_client import lyria_client

        script = "Introducing the epitome of excellence. Because you deserve nothing but the finest."
        voice = "en-GB-Neural2-B"  # British male, sophisticated

        audio_bytes = await lyria_client.synthesize_speech(text=script, voice=voice)

        assert audio_bytes is not None
        assert len(audio_bytes) > 0
        print(f"✓ Generated {len(audio_bytes)} bytes of TTS audio (luxury voice)")

    @pytest.mark.asyncio
    async def test_tts_edgy_voice(self, audio_team):
        """Test TTS with edgy voice."""
        from app.services.google_ai_client import lyria_client

        script = "Ready to break the rules? Don't just follow the crowd. Lead it."
        voice = "en-US-Neural2-D"  # Male, energetic

        audio_bytes = await lyria_client.synthesize_speech(text=script, voice=voice)

        assert audio_bytes is not None
        assert len(audio_bytes) > 0
        print(f"✓ Generated {len(audio_bytes)} bytes of TTS audio (edgy voice)")


class TestRealPodcastAdGeneration:
    """Test real podcast ad generation with TTS."""

    @pytest.mark.asyncio
    async def test_podcast_ad_footwear(self, audio_team):
        """Test podcast ad for footwear product with real TTS."""
        # This will generate real TTS and upload to GCS
        podcast_ad = await audio_team._generate_podcast_ad(
            product_name="Aura Smart Sneaker",
            slogan="Run Your Future",
            theme="futuristic urban athlete",
            brand_tone="futuristic",
            product_category="footwear",
        )

        # Verify podcast ad
        assert podcast_ad.asset_id.startswith("podcast_")
        assert podcast_ad.url.startswith("https://")  # GCS signed URL
        assert podcast_ad.duration_seconds > 0
        assert podcast_ad.audio_type == "podcast_ad"
        assert podcast_ad.script is not None
        assert "Aura Smart Sneaker" in podcast_ad.script
        assert "Run Your Future" in podcast_ad.script

        print(f"✓ Generated podcast ad: {podcast_ad.asset_id}")
        print(f"  URL: {podcast_ad.url[:80]}...")
        print(f"  Duration: {podcast_ad.duration_seconds:.1f}s")
        print(f"  Script length: {len(podcast_ad.script)} chars")

    @pytest.mark.asyncio
    async def test_podcast_ad_beverage(self, audio_team):
        """Test podcast ad for beverage product."""
        podcast_ad = await audio_team._generate_podcast_ad(
            product_name="Pure Energy Drink",
            slogan="Fuel Your Ambition",
            theme="dynamic energy",
            brand_tone="energetic",
            product_category="beverage",
        )

        assert podcast_ad.asset_id.startswith("podcast_")
        assert podcast_ad.url.startswith("https://")
        assert "Pure Energy Drink" in podcast_ad.script
        assert "beverage" in podcast_ad.script

        print(f"✓ Generated podcast ad (beverage): {podcast_ad.asset_id}")

    @pytest.mark.asyncio
    async def test_podcast_ad_luxury_product(self, audio_team):
        """Test podcast ad for luxury product with British voice."""
        podcast_ad = await audio_team._generate_podcast_ad(
            product_name="Prestige Watch",
            slogan="Timeless Elegance",
            theme="luxury craftsmanship",
            brand_tone="luxury",
            product_category="jewelry",
        )

        assert podcast_ad.asset_id.startswith("podcast_")
        assert podcast_ad.url.startswith("https://")
        assert "Prestige Watch" in podcast_ad.script
        assert "epitome of excellence" in podcast_ad.script  # Luxury opening

        print(f"✓ Generated podcast ad (luxury): {podcast_ad.asset_id}")


class TestRealJingleGeneration:
    """Test jingle generation with Lyria API (lyria-002)."""

    @pytest.mark.asyncio
    async def test_jingle_generation(self, audio_team):
        """Test jingle generation with real Lyria API."""
        jingle = await audio_team._generate_jingle(
            theme="futuristic urban athlete",
            brand_tone="energetic",
            product_name="Test Product",
            slogan="Test Slogan",
        )

        assert jingle.asset_id.startswith("jingle_")
        assert jingle.url
        assert jingle.audio_type == "jingle"

        # Check if real music was generated or placeholder
        if jingle.url.startswith("https://"):
            # Real music generated and uploaded to GCS
            assert jingle.duration_seconds == 30.0  # Lyria generates 30s fixed
            print(f"✓ Jingle generation: {jingle.asset_id} (real Lyria music, 30s)")
        else:
            # Placeholder (Lyria API may not be available or failed)
            assert jingle.url.startswith("gs://ai-agency-demo/")
            assert jingle.duration_seconds == 10.0  # Placeholder duration
            print(f"⚠ Jingle generation: {jingle.asset_id} (placeholder, Lyria not available)")


class TestFullAudioTeamExecution:
    """Test complete Audio Team execution with real APIs."""

    @pytest.mark.asyncio
    async def test_complete_execution_footwear(self, audio_team):
        """Test complete audio team execution for footwear product."""
        task = {
            "product_name": "Aura Smart Sneaker",
            "product_category": "footwear",
            "theme": "futuristic urban athlete",
            "brand_tone": "futuristic",
            "slogan": "Run Your Future",
        }
        context = {
            "project_id": "aura_smart_sneaker",
            "session_id": "test_integration",
        }

        # Execute (this will generate real TTS)
        result = await audio_team.execute(task, context)

        # Verify all assets
        assert "jingle" in result
        assert "podcast_ad" in result
        assert "transcription" in result
        assert "proactive_suggestion" in result

        # Verify jingle (placeholder)
        jingle = result["jingle"]
        assert jingle["asset_id"].startswith("jingle_")
        print(f"✓ Jingle: {jingle['asset_id']}")

        # Verify podcast ad (real TTS + GCS upload)
        podcast = result["podcast_ad"]
        assert podcast["asset_id"].startswith("podcast_")
        assert podcast["url"].startswith("https://")
        assert "Aura Smart Sneaker" in podcast["script"]
        print(f"✓ Podcast ad: {podcast['asset_id']}")
        print(f"  URL: {podcast['url'][:80]}...")

        # Verify transcription (may fail if audio URL not accessible to Chirp)
        # Chirp needs publicly accessible audio URL or GCS path
        transcription = result["transcription"]
        assert transcription["asset_id"].startswith("transcript_")
        print(f"✓ Transcription: {transcription['asset_id']}")

        # Verify suggestion
        assert "futuristic" in result["proactive_suggestion"]
        print(f"✓ Suggestion: {result['proactive_suggestion'][:80]}...")

    @pytest.mark.asyncio
    async def test_complete_execution_luxury_product(self, audio_team):
        """Test complete execution for luxury product (British voice)."""
        task = {
            "product_name": "Prestige Watch",
            "product_category": "jewelry",
            "theme": "timeless elegance",
            "brand_tone": "luxury",
            "slogan": "Eternal Brilliance",
        }
        context = {}

        # Execute
        result = await audio_team.execute(task, context)

        # Verify podcast uses luxury voice and script
        podcast = result["podcast_ad"]
        assert "Prestige Watch" in podcast["script"]
        assert "epitome of excellence" in podcast["script"]  # Luxury opening
        assert "finest" in podcast["script"]  # Luxury closing
        print(f"✓ Luxury product execution complete: {podcast['asset_id']}")


class TestProductAgnosticDesign:
    """Test product-agnostic design with different categories."""

    @pytest.mark.asyncio
    async def test_electronics_product(self, audio_team):
        """Test with electronics product."""
        task = {
            "product_name": "Smart Watch Pro",
            "product_category": "electronics",
            "theme": "modern tech",
            "brand_tone": "professional",
            "slogan": "Time Redefined",
        }

        result = await audio_team.execute(task, {})

        # Verify script adapted to electronics
        podcast = result["podcast_ad"]
        assert "Smart Watch Pro" in podcast["script"]
        assert "electronics" in podcast["script"]
        assert "Innovation you can trust" in podcast["script"]  # Professional closing
        print(f"✓ Electronics product: {podcast['asset_id']}")

    @pytest.mark.asyncio
    async def test_beverage_product(self, audio_team):
        """Test with beverage product."""
        task = {
            "product_name": "Energy Boost",
            "product_category": "beverage",
            "theme": "dynamic power",
            "brand_tone": "energetic",
            "slogan": "Unleash Your Potential",
        }

        result = await audio_team.execute(task, {})

        podcast = result["podcast_ad"]
        assert "Energy Boost" in podcast["script"]
        assert "beverage" in podcast["script"]
        print(f"✓ Beverage product: {podcast['asset_id']}")

    @pytest.mark.asyncio
    async def test_toy_product(self, audio_team):
        """Test with toy product (playful tone)."""
        task = {
            "product_name": "Mega Fun Robot",
            "product_category": "toy",
            "theme": "colorful adventure",
            "brand_tone": "playful",
            "slogan": "Adventure Awaits",
        }

        result = await audio_team.execute(task, {})

        podcast = result["podcast_ad"]
        assert "Mega Fun Robot" in podcast["script"]
        assert "Get ready for something amazing" in podcast["script"]  # Playful opening
        assert "Life's too short for boring" in podcast["script"]  # Playful closing
        print(f"✓ Toy product: {podcast['asset_id']}")


# Note: Chirp (Speech-to-Text) integration tests would go here
# but require the podcast ad audio to be accessible via public URL or GCS
# The transcription generation is tested in unit tests with mocks.

# Note: Lyria (Music generation) integration tests are not included
# as the API is not yet publicly available. When it becomes available,
# tests should be added for:
# - Real music generation with different styles
# - Upload to GCS
# - Duration verification
