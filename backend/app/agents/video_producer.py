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
from app.services.storage_client import storage_client

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
            "product_name": product_name,
            "product_category": product_category,
            "key_features": key_features,
        }

        # Validate image URL
        if not image_url:
            raise ValueError("image_url is required for video generation")

        try:
            # Generate video using Veo
            logger.info(f"Calling Veo API for {duration_seconds}s video...")
            video_data = await veo_client.generate_video(
                prompt=base_prompt,
                reference_image=image_url,
                duration_seconds=duration_seconds,
            )

            # Check if video data was generated
            if not video_data or len(video_data) == 0:
                raise RuntimeError("Veo API returned empty video data")

            logger.info(f"Veo generated {len(video_data)} bytes of video data")

            # Upload to Google Cloud Storage and get signed URL
            asset_id, video_url = await storage_client.upload_video(
                video_data=video_data,
                content_type="video/mp4",
            )

            video_asset = VideoAsset(
                asset_id=asset_id,
                url=video_url,  # Real GCS signed URL
                duration_seconds=duration_seconds,
                generation_params=generation_params,
                revision_number=0,
            )

            logger.info(f"Video uploaded to GCS: {asset_id}")

            return video_asset

        except Exception as e:
            logger.error(f"Video generation failed: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

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
        old_video = output.video

        # Track revision
        revision_note = f"Revision {old_video.revision_number + 1}: {critique.revision_instructions}"
        output.revision_history.append(revision_note)

        # Extract original generation parameters
        gen_params = old_video.generation_params

        # Re-generate video with revision instructions
        try:
            revised_video = await self._generate_video(
                image_url=gen_params.get("reference_image", ""),
                product_name=gen_params.get("product_name", "Product"),
                theme=gen_params.get("theme", "modern"),
                key_features=gen_params.get("key_features", []),
                product_category=gen_params.get("product_category", "product"),
                duration_seconds=old_video.duration_seconds,
                revision_instructions=critique.revision_instructions,
            )

            # Update revision number
            revised_video.revision_number = old_video.revision_number + 1

            # Update output with revised video
            output.video = revised_video
            output.critique_notes = critique.revision_instructions

            logger.info(f"Video revision {revised_video.revision_number} completed")

            return output.model_dump()

        except Exception as e:
            logger.error(f"Video revision failed: {e}")
            # Return original output with error note
            output.critique_notes = f"Revision failed: {str(e)}"
            return output.model_dump()
