"""Unit tests for Audio Team Agent.

Tests cover:
- Audio asset generation (jingle, podcast ad)
- TTS with different voices
- Transcription
- Critique system
- Brand tone mapping
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.agents.audio_team import AudioTeamAgent
from app.models.assets import AudioAsset, TranscriptionAsset, AudioTeamOutput


@pytest.fixture
def audio_team():
    """Create Audio Team agent instance."""
    return AudioTeamAgent()


@pytest.fixture
def test_task():
    """Standard test task for Aura Smart Sneaker."""
    return {
        "product_name": "Aura Smart Sneaker",
        "product_category": "footwear",
        "theme": "futuristic urban athlete",
        "brand_tone": "futuristic",
        "slogan": "Run Your Future",
    }


@pytest.fixture
def test_context():
    """Test context."""
    return {
        "project_id": "aura_smart_sneaker",
        "session_id": "test_session",
    }


class TestAudioTeamExecution:
    """Test main execution flow."""

    @pytest.mark.asyncio
    async def test_execute_returns_complete_output(self, audio_team, test_task, test_context):
        """Test that execute returns all required assets."""
        # Mock the API clients
        with patch("app.agents.audio_team.lyria_client") as mock_lyria, \
             patch("app.agents.audio_team.chirp_client") as mock_chirp, \
             patch("app.agents.audio_team.storage_client") as mock_storage:

            # Mock Lyria music generation (returns empty since API not available)
            mock_lyria.generate_music = AsyncMock(return_value=b"")

            # Mock Lyria TTS
            mock_tts_audio = b"fake_tts_audio_data_here" * 100  # Simulate realistic size
            mock_lyria.synthesize_speech = AsyncMock(return_value=mock_tts_audio)

            # Mock storage upload
            mock_storage.upload_audio = AsyncMock(
                return_value=("podcast_abc123", "https://storage.googleapis.com/bucket/audio/podcast_abc123.mp3")
            )

            # Mock Chirp transcription
            mock_chirp.transcribe = AsyncMock(return_value={
                "text": "Introducing Aura Smart Sneaker. Run Your Future. Life's too short for boring."
            })

            # Execute
            result = await audio_team.execute(test_task, test_context)

            # Verify output structure
            assert "jingle" in result
            assert "podcast_ad" in result
            assert "transcription" in result
            assert "proactive_suggestion" in result

            # Verify jingle
            jingle = result["jingle"]
            assert jingle["asset_id"].startswith("jingle_")
            assert jingle["audio_type"] == "jingle"
            assert jingle["duration_seconds"] == 10.0

            # Verify podcast ad
            podcast = result["podcast_ad"]
            assert podcast["asset_id"].startswith("podcast_")
            assert podcast["audio_type"] == "podcast_ad"
            assert podcast["duration_seconds"] > 0
            assert podcast["script"] is not None
            assert "Aura Smart Sneaker" in podcast["script"]

            # Verify transcription
            transcription = result["transcription"]
            assert transcription["asset_id"].startswith("transcript_")
            assert transcription["text"]
            assert transcription["language"] == "en"
            assert transcription["format"] == "srt"

            # Verify suggestion
            assert "futuristic" in result["proactive_suggestion"]

    @pytest.mark.asyncio
    async def test_execute_with_minimal_task(self, audio_team):
        """Test execution with minimal task data (uses defaults)."""
        minimal_task = {}  # Empty task
        context = {}

        with patch("app.agents.audio_team.lyria_client") as mock_lyria, \
             patch("app.agents.audio_team.chirp_client") as mock_chirp, \
             patch("app.agents.audio_team.storage_client") as mock_storage:

            # Mock APIs
            mock_lyria.generate_music = AsyncMock(return_value=b"")
            mock_lyria.synthesize_speech = AsyncMock(return_value=b"audio_data" * 10)
            mock_storage.upload_audio = AsyncMock(return_value=("audio_123", "https://example.com/audio.mp3"))
            mock_chirp.transcribe = AsyncMock(return_value={"text": "Test transcription"})

            # Execute with defaults
            result = await audio_team.execute(minimal_task, context)

            # Should still generate all assets with default values
            assert result["jingle"]["asset_id"]
            assert result["podcast_ad"]["asset_id"]
            assert result["transcription"]["asset_id"]


class TestJingleGeneration:
    """Test jingle generation."""

    @pytest.mark.asyncio
    async def test_generate_jingle_with_music_data(self, audio_team):
        """Test jingle generation when Lyria returns audio data."""
        with patch("app.agents.audio_team.lyria_client") as mock_lyria, \
             patch("app.agents.audio_team.storage_client") as mock_storage:

            # Mock Lyria returning actual music data (WAV format)
            fake_music = b"music_bytes_here" * 1000  # 15KB
            mock_lyria.generate_music = AsyncMock(return_value=fake_music)
            mock_storage.upload_audio = AsyncMock(
                return_value=("jingle_123", "https://storage.googleapis.com/bucket/audio/jingle_123.wav")
            )

            # Generate
            jingle = await audio_team._generate_jingle(
                theme="futuristic",
                brand_tone="energetic",
                product_name="Test Product",
                slogan="Test Slogan",
            )

            # Verify upload was called
            mock_storage.upload_audio.assert_called_once()
            call_args = mock_storage.upload_audio.call_args
            assert call_args[1]["audio_data"] == fake_music
            assert call_args[1]["content_type"] == "audio/wav"  # Lyria outputs WAV

            # Verify jingle (Lyria generates 30s fixed duration)
            assert jingle.url == "https://storage.googleapis.com/bucket/audio/jingle_123.wav"
            assert jingle.duration_seconds == 30.0  # Lyria fixed duration
            assert jingle.audio_type == "jingle"

    @pytest.mark.asyncio
    async def test_generate_jingle_without_music_data(self, audio_team):
        """Test jingle generation when Lyria returns empty (API not available)."""
        with patch("app.agents.audio_team.lyria_client") as mock_lyria, \
             patch("app.agents.audio_team.storage_client") as mock_storage:

            # Mock Lyria returning empty (API not available)
            mock_lyria.generate_music = AsyncMock(return_value=b"")

            # Generate
            jingle = await audio_team._generate_jingle(
                theme="luxury",
                brand_tone="luxury",
                product_name="Luxury Watch",
                slogan="Timeless Elegance",
            )

            # Verify upload was NOT called
            mock_storage.upload_audio.assert_not_called()

            # Verify placeholder URL used (WAV format)
            assert jingle.url.startswith("gs://ai-agency-demo/audio/jingle_")
            assert jingle.url.endswith(".wav")
            assert jingle.duration_seconds == 10.0  # Placeholder duration


class TestPodcastAdGeneration:
    """Test podcast ad generation with TTS."""

    @pytest.mark.asyncio
    async def test_generate_podcast_ad_success(self, audio_team):
        """Test successful podcast ad generation."""
        with patch("app.agents.audio_team.lyria_client") as mock_lyria, \
             patch("app.agents.audio_team.storage_client") as mock_storage:

            # Mock TTS
            fake_tts_audio = b"tts_audio_bytes" * 500  # 7.5KB
            mock_lyria.synthesize_speech = AsyncMock(return_value=fake_tts_audio)
            mock_storage.upload_audio = AsyncMock(
                return_value=("podcast_456", "https://storage.googleapis.com/bucket/audio/podcast_456.mp3")
            )

            # Generate
            podcast_ad = await audio_team._generate_podcast_ad(
                product_name="Test Product",
                slogan="Test Slogan",
                theme="playful",
                brand_tone="playful",
                product_category="toy",
            )

            # Verify TTS was called
            mock_lyria.synthesize_speech.assert_called_once()
            tts_call = mock_lyria.synthesize_speech.call_args
            script = tts_call[1]["text"]
            voice = tts_call[1]["voice"]

            # Verify script content
            assert "Test Product" in script
            assert "Test Slogan" in script

            # Verify voice selection (playful = friendly female voice)
            assert voice == "en-US-Neural2-E"

            # Verify upload
            mock_storage.upload_audio.assert_called_once()

            # Verify podcast ad
            assert podcast_ad.url == "https://storage.googleapis.com/bucket/audio/podcast_456.mp3"
            assert podcast_ad.audio_type == "podcast_ad"
            assert podcast_ad.duration_seconds > 0  # Duration calculated from script word count
            assert podcast_ad.script is not None
            assert "Test Product" in podcast_ad.script

    @pytest.mark.asyncio
    async def test_generate_podcast_ad_tts_failure(self, audio_team):
        """Test podcast ad generation when TTS fails."""
        with patch("app.agents.audio_team.lyria_client") as mock_lyria:

            # Mock TTS returning empty
            mock_lyria.synthesize_speech = AsyncMock(return_value=b"")

            # Should raise error
            with pytest.raises(RuntimeError, match="Failed to generate TTS audio"):
                await audio_team._generate_podcast_ad(
                    product_name="Test",
                    slogan="Test",
                    theme="test",
                    brand_tone="professional",
                    product_category="test",
                )


class TestAdScriptCreation:
    """Test ad script creation logic."""

    def test_create_ad_script_luxury_tone(self, audio_team):
        """Test luxury brand tone script."""
        script = audio_team._create_ad_script(
            product_name="Diamond Watch",
            slogan="Eternal Brilliance",
            theme="luxury",
            brand_tone="luxury",
            product_category="jewelry",
        )

        assert "Introducing the epitome of excellence" in script
        assert "Diamond Watch" in script
        assert "Eternal Brilliance" in script
        assert "Because you deserve nothing but the finest" in script

    def test_create_ad_script_edgy_tone(self, audio_team):
        """Test edgy brand tone script."""
        script = audio_team._create_ad_script(
            product_name="Rebel Motorcycle",
            slogan="Break Free",
            theme="edgy urban",
            brand_tone="edgy",
            product_category="vehicle",
        )

        assert "Ready to break the rules?" in script
        assert "Rebel Motorcycle" in script
        assert "Don't just follow the crowd. Lead it." in script

    def test_create_ad_script_playful_tone(self, audio_team):
        """Test playful brand tone script."""
        script = audio_team._create_ad_script(
            product_name="Fun Toy",
            slogan="Play On",
            theme="colorful",
            brand_tone="playful",
            product_category="toy",
        )

        assert "Get ready for something amazing!" in script
        assert "Life's too short for boring" in script

    def test_create_ad_script_futuristic_tone(self, audio_team):
        """Test futuristic brand tone script."""
        script = audio_team._create_ad_script(
            product_name="Smart Device",
            slogan="Tomorrow Today",
            theme="tech",
            brand_tone="futuristic",
            product_category="electronics",
        )

        assert "The future is here" in script
        assert "Step into tomorrow, today" in script


class TestVoiceSelection:
    """Test TTS voice selection based on brand tone."""

    def test_select_voice_luxury(self, audio_team):
        """Test luxury voice selection."""
        voice = audio_team._select_voice("luxury")
        assert voice == "en-GB-Neural2-B"  # British male, sophisticated

    def test_select_voice_futuristic(self, audio_team):
        """Test futuristic voice selection."""
        voice = audio_team._select_voice("futuristic")
        assert voice == "en-US-Neural2-F"  # Female, clear and modern

    def test_select_voice_edgy(self, audio_team):
        """Test edgy voice selection."""
        voice = audio_team._select_voice("edgy")
        assert voice == "en-US-Neural2-D"  # Male, energetic

    def test_select_voice_playful(self, audio_team):
        """Test playful voice selection."""
        voice = audio_team._select_voice("playful")
        assert voice == "en-US-Neural2-E"  # Female, warm and friendly

    def test_select_voice_professional(self, audio_team):
        """Test professional voice selection."""
        voice = audio_team._select_voice("professional")
        assert voice == "en-US-Studio-O"  # Female, professional quality

    def test_select_voice_default(self, audio_team):
        """Test default voice selection for unknown tone."""
        voice = audio_team._select_voice("unknown_tone")
        assert voice == "en-US-Studio-O"  # Default: professional female


class TestTranscriptionGeneration:
    """Test transcription generation."""

    @pytest.mark.asyncio
    async def test_generate_transcription_success(self, audio_team):
        """Test successful transcription generation."""
        with patch("app.agents.audio_team.chirp_client") as mock_chirp:

            # Mock Chirp
            mock_chirp.transcribe = AsyncMock(return_value={
                "text": "This is the transcribed text from the podcast ad."
            })

            # Create fake podcast ad
            podcast_ad = AudioAsset(
                asset_id="podcast_test",
                url="https://example.com/audio.mp3",
                duration_seconds=15.0,
                audio_type="podcast_ad",
            )

            # Generate transcription
            transcription = await audio_team._generate_transcription(podcast_ad)

            # Verify Chirp was called correctly
            mock_chirp.transcribe.assert_called_once_with(
                audio_url=podcast_ad.url,
                format="srt",
                language="en",
            )

            # Verify transcription
            assert transcription.asset_id.startswith("transcript_")
            assert transcription.text == "This is the transcribed text from the podcast ad."
            assert transcription.language == "en"
            assert transcription.format == "srt"


class TestProactiveSuggestion:
    """Test proactive suggestion generation."""

    @pytest.mark.asyncio
    async def test_generate_suggestion_futuristic(self, audio_team):
        """Test suggestion for futuristic brand."""
        suggestion = await audio_team._generate_suggestion(
            theme="Tokyo neon",
            brand_tone="futuristic",
            product_category="footwear",
        )

        assert "Tokyo neon" in suggestion
        assert "futuristic" in suggestion
        assert "uplifting, electronic, synthesized beats" in suggestion
        assert "footwear" in suggestion

    @pytest.mark.asyncio
    async def test_generate_suggestion_luxury(self, audio_team):
        """Test suggestion for luxury brand."""
        suggestion = await audio_team._generate_suggestion(
            theme="elegant",
            brand_tone="luxury",
            product_category="jewelry",
        )

        assert "elegant" in suggestion
        assert "luxury" in suggestion
        assert "sophisticated, orchestral, elegant piano" in suggestion

    @pytest.mark.asyncio
    async def test_generate_suggestion_unknown_tone(self, audio_team):
        """Test suggestion for unknown brand tone (uses default)."""
        suggestion = await audio_team._generate_suggestion(
            theme="test theme",
            brand_tone="unknown",
            product_category="product",
        )

        assert "modern, professional production" in suggestion


class TestCritiqueSystem:
    """Test critique system."""

    @pytest.mark.asyncio
    async def test_critique_pass_complete_output(self, audio_team):
        """Test critique passes with complete output."""
        # Create complete output
        result = {
            "jingle": {
                "asset_id": "jingle_123",
                "url": "https://example.com/jingle.mp3",
                "duration_seconds": 10.0,
                "audio_type": "jingle",
            },
            "podcast_ad": {
                "asset_id": "podcast_456",
                "url": "https://example.com/podcast.mp3",
                "duration_seconds": 15.0,
                "audio_type": "podcast_ad",
                "script": "Test script",
            },
            "transcription": {
                "asset_id": "transcript_789",
                "text": "Transcribed text here",
                "language": "en",
                "format": "srt",
            },
            "proactive_suggestion": "Based on the 'futuristic' theme...",
        }

        brief = {
            "brand_tone": "futuristic",
        }

        # Critique
        critique = await audio_team.critique(result, brief)

        # Should pass
        assert critique.status == "PASS"
        assert critique.score == 1.0
        assert len(critique.issues) == 0

    @pytest.mark.asyncio
    async def test_critique_fail_missing_urls(self, audio_team):
        """Test critique fails with missing URLs."""
        result = {
            "jingle": {
                "asset_id": "jingle_123",
                "url": "",  # Missing URL
                "duration_seconds": 10.0,
                "audio_type": "jingle",
            },
            "podcast_ad": {
                "asset_id": "podcast_456",
                "url": "",  # Missing URL
                "duration_seconds": 15.0,
                "audio_type": "podcast_ad",
            },
            "transcription": {
                "asset_id": "transcript_789",
                "text": "",  # Empty transcription
                "language": "en",
                "format": "srt",
            },
            "proactive_suggestion": "Test suggestion",
        }

        brief = {}

        # Critique
        critique = await audio_team.critique(result, brief)

        # Should fail
        assert critique.status == "REVISE"
        assert critique.score < 1.0
        assert "Jingle missing URL" in critique.issues
        assert "Podcast ad missing URL" in critique.issues
        assert "Transcription empty" in critique.issues


class TestProductAgnosticDesign:
    """Test that agent works with different product categories."""

    @pytest.mark.asyncio
    async def test_beverage_product(self, audio_team):
        """Test with beverage product."""
        task = {
            "product_name": "Energy Drink",
            "product_category": "beverage",
            "theme": "dynamic energy",
            "brand_tone": "energetic",
            "slogan": "Fuel Your Day",
        }

        with patch("app.agents.audio_team.lyria_client") as mock_lyria, \
             patch("app.agents.audio_team.chirp_client") as mock_chirp, \
             patch("app.agents.audio_team.storage_client") as mock_storage:

            mock_lyria.generate_music = AsyncMock(return_value=b"")
            mock_lyria.synthesize_speech = AsyncMock(return_value=b"audio" * 100)
            mock_storage.upload_audio = AsyncMock(return_value=("id", "url"))
            mock_chirp.transcribe = AsyncMock(return_value={"text": "test"})

            result = await audio_team.execute(task, {})

            # Verify script adapted to beverage
            assert "beverage" in result["podcast_ad"]["script"]
            assert "Energy Drink" in result["podcast_ad"]["script"]

    @pytest.mark.asyncio
    async def test_electronics_product(self, audio_team):
        """Test with electronics product."""
        task = {
            "product_name": "Smart Watch",
            "product_category": "electronics",
            "theme": "modern tech",
            "brand_tone": "professional",
            "slogan": "Time Redefined",
        }

        with patch("app.agents.audio_team.lyria_client") as mock_lyria, \
             patch("app.agents.audio_team.chirp_client") as mock_chirp, \
             patch("app.agents.audio_team.storage_client") as mock_storage:

            mock_lyria.generate_music = AsyncMock(return_value=b"")
            mock_lyria.synthesize_speech = AsyncMock(return_value=b"audio" * 100)
            mock_storage.upload_audio = AsyncMock(return_value=("id", "url"))
            mock_chirp.transcribe = AsyncMock(return_value={"text": "test"})

            result = await audio_team.execute(task, {})

            # Verify script adapted to electronics
            assert "electronics" in result["podcast_ad"]["script"]
            assert "Smart Watch" in result["podcast_ad"]["script"]
            # Professional tone uses different opening
            assert "Innovation you can trust" in result["podcast_ad"]["script"]
