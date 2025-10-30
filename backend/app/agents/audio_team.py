"""Audio Team Agent - Jingles, TTS, and transcription.

Uses Lyria for music generation and TTS, Chirp for transcription.
Includes proactive suggestion capability based on theme analysis.
"""

import logging
import uuid
from typing import Any, Dict, Optional

from app.agents.base import AgentBase
from app.models.assets import (
    AudioAsset,
    AudioTeamOutput,
    CritiqueResult,
    TranscriptionAsset,
)
from app.services.google_ai_client import chirp_client, lyria_client

logger = logging.getLogger(__name__)


# Brand tone to music style mapping
BRAND_TONE_MUSIC_STYLES = {
    "futuristic": "uplifting, electronic, synthesized beats with ambient textures",
    "luxury": "sophisticated, orchestral, elegant piano with subtle strings",
    "playful": "bouncy, cheerful, acoustic instruments with bright melodies",
    "edgy": "intense, rock-influenced, driving beats with bold instrumentation",
    "professional": "corporate, clean, modern production with confident tone",
    "natural": "organic, acoustic, warm instrumentation with earthy tones",
    "energetic": "high-tempo, dynamic, motivating beats with powerful rhythm",
}


class AudioTeamAgent(AgentBase):
    """
    Audio Team Agent generates audio assets for campaigns.

    Outputs:
    1. Jingle (Lyria music generation)
    2. Podcast ad with TTS voiceover (Lyria TTS)
    3. Transcription for international markets (Chirp)
    4. Optional proactive suggestion based on theme
    """

    def __init__(self):
        """Initialize Audio Team Agent."""
        super().__init__(agent_id="audio_team")

    async def execute(
        self, task: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute audio asset generation.

        Args:
            task: Contains theme, slogan, brand_tone, product info
            context: Shared project context

        Returns:
            AudioTeamOutput with jingle, podcast ad, and transcription
        """
        logger.info(f"Audio Team executing for: {task.get('product_name')}")

        theme = task.get("theme", "modern")
        slogan = task.get("slogan", "")
        brand_tone = task.get("brand_tone", "professional")
        product_name = task.get("product_name", "Product")
        product_category = task.get("product_category", "product")

        # Generate proactive suggestion
        suggestion = await self._generate_suggestion(theme, brand_tone, product_category)

        # Generate jingle
        jingle = await self._generate_jingle(
            theme=theme,
            brand_tone=brand_tone,
            product_name=product_name,
            slogan=slogan,
        )

        # Generate podcast ad script and TTS
        podcast_ad = await self._generate_podcast_ad(
            product_name=product_name,
            slogan=slogan,
            theme=theme,
            brand_tone=brand_tone,
            product_category=product_category,
        )

        # Generate transcription
        transcription = await self._generate_transcription(podcast_ad)

        output = AudioTeamOutput(
            jingle=jingle,
            podcast_ad=podcast_ad,
            transcription=transcription,
            proactive_suggestion=suggestion,
        )

        logger.info("Audio Team completed: jingle, podcast ad, and transcription")

        return output.model_dump()

    async def _generate_suggestion(
        self, theme: str, brand_tone: str, product_category: str
    ) -> Optional[str]:
        """
        Generate proactive suggestion based on theme analysis.

        This implements the proactive collaboration feature:
        "Our Audio Agent has a proactive suggestion: based on the 'Tokyo neon' theme
        and the 'Run on light' slogan, it recommends an 'uplifting, futuristic,
        electronic beat'."

        Args:
            theme: Campaign theme
            brand_tone: Brand tone
            product_category: Product category

        Returns:
            Suggestion text or None
        """
        music_style = BRAND_TONE_MUSIC_STYLES.get(
            brand_tone, "modern, professional production"
        )

        suggestion = f"""Based on the '{theme}' theme and '{brand_tone}' brand tone,
I recommend a '{music_style}' style for the jingle.
This will resonate with {product_category} enthusiasts and create emotional connection."""

        logger.debug(f"Audio suggestion: {suggestion[:100]}...")

        return suggestion

    async def _generate_jingle(
        self, theme: str, brand_tone: str, product_name: str, slogan: str
    ) -> AudioAsset:
        """
        Generate musical jingle using Lyria.

        Args:
            theme: Campaign theme
            brand_tone: Brand tone
            product_name: Product name
            slogan: Campaign slogan

        Returns:
            AudioAsset with jingle
        """
        music_style = BRAND_TONE_MUSIC_STYLES.get(
            brand_tone, "modern, professional production"
        )

        prompt = f"""
        Compose a 10-second jingle for {product_name}.

        MUSIC STYLE: {music_style}
        THEME: {theme}
        BRAND TONE: {brand_tone}
        SLOGAN: "{slogan}"

        REQUIREMENTS:
        - Duration: 10 seconds
        - Style: {music_style}
        - Mood: Matches {brand_tone} brand tone
        - Energy: Appropriate for {theme} theme
        - Format: Instrumental background music
        - Purpose: Social media ads, podcast intros

        COMPOSITION:
        - Opening: Attention-grabbing hook (1-2 seconds)
        - Middle: Develop theme with {brand_tone} feel (5-6 seconds)
        - Ending: Memorable closing flourish (2-3 seconds)
        """

        # Generate music using Lyria
        audio_data = await lyria_client.generate_music(
            prompt=prompt, duration_seconds=10
        )

        # In production, upload to GCS
        asset_id = f"jingle_{uuid.uuid4().hex[:12]}"
        mock_url = f"gs://ai-agency-demo/audio/{asset_id}.mp3"

        jingle = AudioAsset(
            asset_id=asset_id,
            url=mock_url,
            duration_seconds=10.0,
            audio_type="jingle",
        )

        logger.debug(f"Generated jingle: {asset_id}")

        return jingle

    async def _generate_podcast_ad(
        self,
        product_name: str,
        slogan: str,
        theme: str,
        brand_tone: str,
        product_category: str,
    ) -> AudioAsset:
        """
        Generate podcast ad with TTS voiceover.

        Args:
            product_name: Product name
            slogan: Campaign slogan
            theme: Campaign theme
            brand_tone: Brand tone
            product_category: Product category

        Returns:
            AudioAsset with podcast ad
        """
        # Create ad script
        script = self._create_ad_script(
            product_name, slogan, theme, brand_tone, product_category
        )

        # Select voice based on brand tone
        voice = self._select_voice(brand_tone)

        # Generate TTS using Lyria
        audio_data = await lyria_client.synthesize_speech(text=script, voice=voice)

        # In production, upload to GCS
        asset_id = f"podcast_{uuid.uuid4().hex[:12]}"
        mock_url = f"gs://ai-agency-demo/audio/{asset_id}.mp3"

        # Estimate duration (rough: ~150 words per minute)
        word_count = len(script.split())
        duration = (word_count / 150) * 60

        podcast_ad = AudioAsset(
            asset_id=asset_id,
            url=mock_url,
            duration_seconds=duration,
            audio_type="podcast_ad",
        )

        logger.debug(f"Generated podcast ad: {asset_id}, ~{duration:.1f}s")

        return podcast_ad

    def _create_ad_script(
        self,
        product_name: str,
        slogan: str,
        theme: str,
        brand_tone: str,
        product_category: str,
    ) -> str:
        """
        Create podcast ad script.

        Args:
            product_name: Product name
            slogan: Campaign slogan
            theme: Campaign theme
            brand_tone: Brand tone
            product_category: Product category

        Returns:
            Ad script text
        """
        # Adapt script to brand tone
        if brand_tone == "luxury":
            opening = "Introducing the epitome of excellence:"
            closing = "Because you deserve nothing but the finest."
        elif brand_tone == "edgy":
            opening = "Ready to break the rules?"
            closing = "Don't just follow the crowd. Lead it."
        elif brand_tone == "playful":
            opening = "Get ready for something amazing!"
            closing = "Life's too short for boring. Choose adventure."
        elif brand_tone == "futuristic":
            opening = "The future is here."
            closing = "Step into tomorrow, today."
        else:  # professional
            opening = "Elevate your experience with"
            closing = "Innovation you can trust."

        script = f"""
        {opening} {product_name}.

        {slogan}

        Designed for those who appreciate {theme} aesthetics and uncompromising quality.
        Experience the next generation of {product_category}.

        {product_name}. {closing}
        """

        return script.strip()

    def _select_voice(self, brand_tone: str) -> str:
        """
        Select TTS voice based on brand tone.

        Args:
            brand_tone: Brand tone

        Returns:
            Voice identifier (Google Cloud TTS voice name)
        """
        # Map brand tones to actual Google Cloud TTS voice names
        # See: https://cloud.google.com/text-to-speech/docs/voices
        voice_mapping = {
            "luxury": "en-GB-Neural2-B",        # British male, sophisticated
            "futuristic": "en-US-Neural2-F",    # Female, clear and modern
            "edgy": "en-US-Neural2-D",          # Male, energetic
            "playful": "en-US-Neural2-E",       # Female, warm and friendly
            "professional": "en-US-Studio-O",   # Female, professional quality
            "energetic": "en-US-Neural2-J",     # Male, dynamic
            "natural": "en-US-Neural2-F",       # Female, natural
        }

        return voice_mapping.get(brand_tone, "en-US-Studio-O")  # Default: professional female

    async def _generate_transcription(self, podcast_ad: AudioAsset) -> TranscriptionAsset:
        """
        Generate transcription using Chirp.

        Args:
            podcast_ad: Podcast audio asset

        Returns:
            TranscriptionAsset with SRT format
        """
        # Transcribe using Chirp
        transcription_data = await chirp_client.transcribe(
            audio_url=podcast_ad.url, format="srt", language="en"
        )

        asset_id = f"transcript_{uuid.uuid4().hex[:12]}"

        transcription = TranscriptionAsset(
            asset_id=asset_id,
            text=transcription_data.get("text", ""),
            language="en",
            format="srt",
        )

        logger.debug(f"Generated transcription: {asset_id}")

        return transcription

    async def critique(
        self, result: Dict[str, Any], brief: Dict[str, Any]
    ) -> CritiqueResult:
        """
        Evaluate audio output against brief.

        Args:
            result: Audio Team output
            brief: Project brief

        Returns:
            Critique result
        """
        output = AudioTeamOutput(**result)

        issues = []

        # Check all assets exist
        if not output.jingle.url:
            issues.append("Jingle missing URL")

        if not output.podcast_ad.url:
            issues.append("Podcast ad missing URL")

        if not output.transcription.text:
            issues.append("Transcription empty")

        # Check brand tone alignment
        brand_tone = brief.get("brand_tone", "")
        if brand_tone and output.proactive_suggestion:
            if brand_tone not in output.proactive_suggestion:
                issues.append(f"Suggestion should reference {brand_tone} tone")

        if issues:
            return CritiqueResult(
                status="REVISE",
                score=0.6,
                issues=issues,
                revision_instructions=f"Fix: {'; '.join(issues)}",
            )

        return CritiqueResult(status="PASS", score=1.0, issues=[])

    async def revise(
        self, result: Dict[str, Any], critique: CritiqueResult
    ) -> Dict[str, Any]:
        """
        Revise audio based on critique.

        Args:
            result: Original output
            critique: Critique feedback

        Returns:
            Revised output
        """
        logger.info(f"Audio Team revising: {critique.revision_instructions}")

        # In production, regenerate specific assets
        return result
