"""Video Producer Agent - Social media video generation.

Uses Veo to generate video clips from hero images.
Includes internal critique and revision capability (max 2 revisions).
"""

import logging
import uuid
from typing import Any, Dict

from app.agents.base import AgentBase
from app.models.assets import CritiqueResult, VideoAsset, VideoProducerOutput
from app.services.google_ai_client import veo_client

logger = logging.getLogger(__name__)


class VideoProducerAgent(AgentBase):
    """
    Video Producer Agent generates social media video clips.

    Features:
    - Generates 15-second videos from hero images
    - Internal critique loop (checks against brief requirements)
    - Maximum 2 revisions per video
    - Tracks revision history
    """

    def __init__(self):
        """Initialize Video Producer Agent."""
        super().__init__(agent_id="video_producer")

    async def execute(
        self, task: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute video generation.

        Args:
            task: Contains image_url, product info, theme, key_features
            context: Shared project context

        Returns:
            VideoProducerOutput with video and revision history
        """
        logger.info(f"Video Producer executing for: {task.get('product_name')}")

        image_url = task.get("image_url", "")
        product_name = task.get("product_name", "Product")
        theme = task.get("theme", "modern")
        key_features = task.get("key_features", [])
        product_category = task.get("product_category", "product")
        duration = task.get("duration_seconds", 8)  # Veo 3.1 supports 4, 6, or 8 seconds

        # Generate initial video
        video = await self._generate_video(
            image_url=image_url,
            product_name=product_name,
            theme=theme,
            key_features=key_features,
            product_category=product_category,
            duration_seconds=duration,
        )

        output = VideoProducerOutput(
            video=video,
            critique_notes=None,
            revision_history=[],
        )

        logger.info(f"Video Producer completed: {video.asset_id}")

        return output.model_dump()

    async def _generate_video(
        self,
        image_url: str,
        product_name: str,
        theme: str,
        key_features: list,
        product_category: str,
        duration_seconds: int = 15,
        revision_instructions: str = "",
    ) -> VideoAsset:
        """
        Generate video using Veo.

        Args:
            image_url: Reference hero image URL
            product_name: Product name
            theme: Visual theme
            key_features: Features to highlight
            product_category: Product category
            duration_seconds: Video length
            revision_instructions: Optional revision guidance

        Returns:
            VideoAsset
        """
        # Build prompt (image is passed separately in API call)
        base_prompt = f"""
        Create a dynamic {duration_seconds}-second social media video for {product_name}.

        VIDEO REQUIREMENTS:
        - Theme: {theme}
        - Product Category: {product_category}
        - Duration: {duration_seconds} seconds
        - Key Features to Show: {', '.join(key_features[:3])}

        VISUAL TREATMENT:
        - Animate the provided reference image to life
        - Start with establishing shot, then zoom into key product feature
        - Dynamic camera movement (smooth pan/zoom)
        - {theme} aesthetic maintained throughout
        - Professional {product_category} video style

        PACING:
        - Seconds 0-3: Establishing shot with product
        - Seconds 3-6: Close-up of key feature (e.g., glowing sole, unique element)
        - Seconds 6-8: Pull back to hero shot with branding

        OUTPUT:
        - High-quality social media format
        - Smooth transitions
        - Engaging movement
        - Ready for Instagram/TikTok/YouTube Shorts
        """

        if revision_instructions:
            base_prompt += f"\n\nREVISION NOTES:\n{revision_instructions}"

        generation_params = {
            "prompt": base_prompt,
            "reference_image": image_url,
            "duration_seconds": duration_seconds,
            "theme": theme,
        }

        # Generate video using Veo
        video_data = await veo_client.generate_video(
            prompt=base_prompt,
            reference_image=image_url,
            duration_seconds=duration_seconds,
        )

        # In production, upload to GCS and get URL
        asset_id = f"vid_{uuid.uuid4().hex[:12]}"
        mock_url = f"gs://ai-agency-demo/videos/{asset_id}.mp4"

        video_asset = VideoAsset(
            asset_id=asset_id,
            url=mock_url,
            duration_seconds=duration_seconds,
            generation_params=generation_params,
            revision_number=0,
        )

        logger.debug(f"Generated video: {asset_id}")

        return video_asset

    async def critique(
        self, result: Dict[str, Any], brief: Dict[str, Any]
    ) -> CritiqueResult:
        """
        Internal critique - evaluate video against brief requirements.

        This implements the Producer's critique loop mentioned in design.md:
        "The 'Tokyo neon' theme is strong, but it doesn't clearly show the 'glowing sole'.
        I'm sending it back to the agent with instructions for a 2-second close-up."

        Args:
            result: Video Producer output
            brief: Project brief with requirements

        Returns:
            CritiqueResult with pass/revise status
        """
        output = VideoProducerOutput(**result)
        video = output.video

        issues = []
        revision_notes = []

        # Check duration
        expected_duration = brief.get("video_duration", 15)
        if video.duration_seconds != expected_duration:
            issues.append(f"Duration should be {expected_duration}s, got {video.duration_seconds}s")

        # Check theme consistency
        theme = brief.get("theme", "")
        if theme and theme not in str(video.generation_params):
            issues.append(f"Video should emphasize {theme} theme")
            revision_notes.append(f"Strengthen {theme} visual elements throughout video")

        # Check key features are shown
        key_features = brief.get("key_features", [])
        if key_features:
            # In production, use video analysis API
            # For now, check if features mentioned in generation params
            feature_check = any(
                feature.lower() in str(video.generation_params).lower()
                for feature in key_features[:2]
            )
            if not feature_check:
                main_feature = key_features[0] if key_features else "key feature"
                issues.append(f"Video doesn't clearly show '{main_feature}'")
                revision_notes.append(
                    f"Add 2-second close-up clearly showing the '{main_feature}'"
                )

        # Determine score and status
        if issues:
            score = max(0.4, 1.0 - (len(issues) * 0.2))
            return CritiqueResult(
                status="REVISE",
                score=score,
                issues=issues,
                revision_instructions="; ".join(revision_notes),
            )

        return CritiqueResult(status="PASS", score=1.0, issues=[])

    async def revise(
        self, result: Dict[str, Any], critique: CritiqueResult
    ) -> Dict[str, Any]:
        """
        Revise video based on critique feedback.

        Args:
            result: Original video output
            critique: Critique with revision instructions

        Returns:
            Revised video output with updated revision history
        """
        logger.info(f"Video Producer revising: {critique.revision_instructions}")

        output = VideoProducerOutput(**result)

        # Track revision
        revision_note = f"Revision {output.video.revision_number + 1}: {critique.revision_instructions}"
        output.revision_history.append(revision_note)

        # Re-generate video with revision instructions
        # In production, call _generate_video with revision_instructions
        # For now, increment revision number
        output.video.revision_number += 1
        output.critique_notes = critique.revision_instructions

        logger.info(f"Video revision {output.video.revision_number} completed")

        return output.model_dump()
