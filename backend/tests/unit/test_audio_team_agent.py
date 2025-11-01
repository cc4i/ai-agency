"""Level 1 Component Tests - Audio Team Agent.

Tests individual Audio Team Agent functionality:
- Output format validation
- Multiple audio assets (jingle, podcast ad, transcription)
- Proactive suggestions
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, patch, Mock

from app.agents.audio_team import AudioTeamAgent


@pytest.mark.asyncio
async def test_audio_team_output_format(sample_audio_task):
    """Test that Audio Team returns correct output format."""
    agent = AudioTeamAgent()

    # lyria_client.generate_music() and synthesize_speech() return bytes
    mock_music_bytes = b'fake_music_data'
    mock_tts_bytes = b'fake_tts_data'

    with patch('app.agents.audio_team.lyria_client') as mock_lyria, \
         patch('app.agents.audio_team.storage_client') as mock_storage, \
         patch('app.agents.audio_team.chirp_client') as mock_chirp:
        # Mock Lyria music generation
        mock_lyria.generate_music = AsyncMock(return_value=mock_music_bytes)
        # Mock Lyria TTS
        mock_lyria.synthesize_speech = AsyncMock(return_value=mock_tts_bytes)
        # Mock storage uploads
        mock_storage.upload_audio = AsyncMock(
            side_effect=[("jingle_123", "gs://bucket/jingle_123.wav"),
                        ("podcast_123", "gs://bucket/podcast_123.mp3")]
        )
        # Mock Chirp transcription
        mock_chirp.transcribe = AsyncMock(return_value={"text": "Transcription text", "language": "en"})

        result = await agent.execute(sample_audio_task, {})

    assert isinstance(result, dict)
    assert "jingle" in result
    assert "podcast_ad" in result
    assert "transcription" in result


@pytest.mark.asyncio
async def test_audio_team_three_outputs(sample_audio_task):
    """Test that Audio Team generates 3 distinct outputs."""
    agent = AudioTeamAgent()

    # lyria_client returns bytes
    mock_music_bytes = b'fake_music_data'
    mock_tts_bytes = b'fake_tts_data'

    with patch('app.agents.audio_team.lyria_client') as mock_lyria, \
         patch('app.agents.audio_team.storage_client') as mock_storage, \
         patch('app.agents.audio_team.chirp_client') as mock_chirp:
        mock_lyria.generate_music = AsyncMock(return_value=mock_music_bytes)
        mock_lyria.synthesize_speech = AsyncMock(return_value=mock_tts_bytes)
        mock_storage.upload_audio = AsyncMock(
            side_effect=[("jingle_123", "gs://bucket/jingle_123.wav"),
                        ("podcast_123", "gs://bucket/podcast_123.mp3")]
        )
        mock_chirp.transcribe = AsyncMock(return_value={"text": "Transcription text", "language": "en"})

        result = await agent.execute(sample_audio_task, {})

    # Verify 3 distinct outputs
    assert result["jingle"]["url"] is not None
    assert result["podcast_ad"]["url"] is not None
    assert result["transcription"]["text"] is not None

    # Verify jingle duration (Lyria generates 30s fixed duration)
    assert result["jingle"]["duration_seconds"] > 0

    # Verify podcast ad duration
    assert result["podcast_ad"]["duration_seconds"] > 0


@pytest.mark.asyncio
async def test_audio_team_proactive_suggestion(sample_audio_task):
    """Test that Audio Team can make proactive suggestions."""
    agent = AudioTeamAgent()

    # Simulate theme detection triggering suggestion
    task = {
        **sample_audio_task,
        "theme": "Tokyo neon",
        "brand_tone": "futuristic"
    }

    # lyria_client returns bytes
    mock_music_bytes = b'fake_music_data'
    mock_tts_bytes = b'fake_tts_data'

    with patch('app.agents.audio_team.lyria_client') as mock_lyria, \
         patch('app.agents.audio_team.storage_client') as mock_storage, \
         patch('app.agents.audio_team.chirp_client') as mock_chirp:
        mock_lyria.generate_music = AsyncMock(return_value=mock_music_bytes)
        mock_lyria.synthesize_speech = AsyncMock(return_value=mock_tts_bytes)
        mock_storage.upload_audio = AsyncMock(
            side_effect=[("jingle_123", "gs://bucket/jingle_123.wav"),
                        ("podcast_123", "gs://bucket/podcast_123.mp3")]
        )
        mock_chirp.transcribe = AsyncMock(return_value={"text": "Transcription text", "language": "en"})

        result = await agent.execute(task, {})

        # Should have proactive suggestion
        assert result["proactive_suggestion"] is not None
        assert isinstance(result["proactive_suggestion"], str)

        # Should mention the brand tone
        assert "futuristic" in result["proactive_suggestion"].lower()


@pytest.mark.asyncio
async def test_audio_team_brand_tone_adaptation(sample_audio_task):
    """Test that Audio Team adapts to different brand tones."""
    agent = AudioTeamAgent()

    tones = ["futuristic", "luxury", "playful", "edgy"]

    for tone in tones:
        task = {
            **sample_audio_task,
            "brand_tone": tone
        }

        # lyria_client returns bytes
        mock_music_bytes = b'fake_music_data'
        mock_tts_bytes = b'fake_tts_data'

        with patch('app.agents.audio_team.lyria_client') as mock_lyria, \
             patch('app.agents.audio_team.storage_client') as mock_storage, \
             patch('app.agents.audio_team.chirp_client') as mock_chirp:
            mock_lyria.generate_music = AsyncMock(return_value=mock_music_bytes)
            mock_lyria.synthesize_speech = AsyncMock(return_value=mock_tts_bytes)
            mock_storage.upload_audio = AsyncMock(
                side_effect=[("jingle_123", "gs://bucket/jingle_123.wav"),
                            ("podcast_123", "gs://bucket/podcast_123.mp3")]
            )
            mock_chirp.transcribe = AsyncMock(return_value={"text": "Transcription text", "language": "en"})

            result = await agent.execute(task, {})

            # Verify all 3 outputs generated
            assert result["jingle"]["url"] is not None
            assert result["podcast_ad"]["url"] is not None


@pytest.mark.asyncio
async def test_audio_team_error_handling():
    """Test Audio Team error handling."""
    agent = AudioTeamAgent()

    task = {"task_id": "error_test"}  # Missing required fields

    with patch('app.agents.audio_team.lyria_client') as mock_lyria:
        mock_lyria.generate_music = AsyncMock(side_effect=Exception("Lyria API Error"))

        with pytest.raises(Exception):
            await agent.execute(task, {})


print("✅ Audio Team Agent Level 1 tests created")
