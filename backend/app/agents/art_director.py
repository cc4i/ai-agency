"""Art Director Agent - Hero image generation.

Uses Gemini 2.5 Flash Image with ADK multi-agent workflow.
Product-agnostic with category-specific visual guidelines.
Parallel generation with built-in quality validation and retry logic.
"""

import logging
import uuid
from typing import Any, Dict

from app.agents.base import AgentBase
from app.models.assets import ArtDirectorOutput, CritiqueResult, ImageAsset

logger = logging.getLogger(__name__)


# Category-specific visual guidelines
CATEGORY_VISUAL_GUIDELINES = {
    "footwear": "Show product in action or lifestyle context, emphasize texture and materials, dynamic angles",
    "beverage": "Focus on condensation, pour shots, refreshment appeal, vibrant colors, appetizing presentation",
    "electronics": "Clean product shots, emphasize sleek design, modern tech environment, minimalist composition",
    "fashion": "Lifestyle imagery, model interaction, emphasis on fabric and fit, aspirational settings",
    "beauty": "Close-up product shots, elegant presentation, skin/texture focus, soft lighting",
    "food": "Appetizing food styling, fresh ingredients, warm inviting lighting, natural settings",
    "automotive": "Dynamic angles, motion blur or still power shots, environment context, dramatic lighting",
}


class ArtDirectorAgent(AgentBase):
    """
    Art Director Agent generates hero images for campaigns.

    Uses ADK multi-agent workflow with:
    - ParallelAgent: Runs 4 image variations simultaneously (4x faster)
    - LoopAgent: Each variation has built-in quality validation and retry (max 3 attempts)
    - Gemini 2.5 Flash Image: Supports reference images for style matching

    Adapts visual style based on product category and brand tone.
    """

    def __init__(self):
        """Initialize Art Director Agent."""
        super().__init__(agent_id="art_director")

    async def execute(
        self, task: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute hero image generation using ADK multi-agent workflow.

        Uses ParallelAgent + LoopAgent for:
        - 4x faster generation (parallel execution)
        - Automatic quality validation
        - Built-in retry logic (max 3 attempts per image)
        - Reference image support for style matching

        Args:
            task: Contains slogan, theme, product info, category, brand_tone, reference_images
            context: Shared project context

        Returns:
            ArtDirectorOutput with 4 images and style guide
        """
        logger.info(f"Art Director executing for: {task.get('product_name')} (ADK workflow)")

        slogan = task.get("slogan", "")
        theme = task.get("theme", "modern")
        product_name = task.get("product_name", "Product")
        product_category = task.get("product_category", "product")
        brand_tone = task.get("brand_tone", "professional")
        key_features = task.get("key_features", [])
        reference_images = task.get("reference_images", [])

        # Get category-specific guidelines
        visual_guidelines = CATEGORY_VISUAL_GUIDELINES.get(
            product_category,
            "Professional product photography with clean composition",
        )

        # Execute ADK workflow (parallel generation with quality validation)
        from app.workflows.art_director_workflow import ArtDirectorWorkflow

        workflow = ArtDirectorWorkflow()

        logger.info(f"Art Director: Starting ADK workflow with {len(reference_images)} reference images")

        # Execute workflow - returns list of ImageAsset dicts
        image_dicts = await workflow.execute(
            slogan=slogan,
            product_name=product_name,
            product_category=product_category,
            theme=theme,
            brand_tone=brand_tone,
            key_features=key_features,
            reference_images=reference_images,
        )

        # Convert dicts back to ImageAsset objects
        images = [ImageAsset(**img_dict) for img_dict in image_dicts]

        # Create style guide
        style_guide = self._create_style_guide(
            theme, brand_tone, product_category, visual_guidelines
        )

        output = ArtDirectorOutput(images=images, style_guide=style_guide)

        logger.info(f"Art Director completed: {len(images)} images generated via ADK workflow")

        return output.model_dump()

    def _create_style_guide(
        self,
        theme: str,
        brand_tone: str,
        product_category: str,
        visual_guidelines: str,
    ) -> str:
        """
        Create style guide documentation.

        Args:
            theme: Visual theme
            brand_tone: Brand tone
            product_category: Product category
            visual_guidelines: Category guidelines

        Returns:
            Style guide text
        """
        return f"""
        VISUAL STYLE GUIDE

        Theme: {theme}
        Brand Tone: {brand_tone}
        Category: {product_category}

        Visual Guidelines:
        {visual_guidelines}

        Color Palette:
        - Primary: {theme}-inspired colors
        - Secondary: Complementary {brand_tone} tones
        - Accents: High-contrast highlights

        Photography Style:
        - Photorealistic quality
        - {brand_tone} aesthetic
        - Professional {product_category} photography standards
        - Consistent {theme} theme across all assets

        Composition:
        - Product-focused framing
        - Clean, uncluttered backgrounds
        - Strategic use of negative space
        - Emphasis on key product features
        """

    async def critique(
        self, result: Dict[str, Any], brief: Dict[str, Any]
    ) -> CritiqueResult:
        """
        Evaluate art output against project brief.

        Args:
            result: Art Director output
            brief: Project brief

        Returns:
            Critique result
        """
        output = ArtDirectorOutput(**result)

        issues = []

        # Check image count
        if len(output.images) != 4:
            issues.append(f"Expected 4 images, got {len(output.images)}")

        # Check if all images have valid URLs
        for i, img in enumerate(output.images):
            if not img.url:
                issues.append(f"Image {i+1} missing URL")

        # Check theme consistency
        theme = brief.get("theme", "")
        if theme and theme not in output.style_guide:
            issues.append(f"Style guide should reference {theme} theme")

        if issues:
            return CritiqueResult(
                status="REVISE",
                score=0.6,
                issues=issues,
                revision_instructions=f"Fix the following: {'; '.join(issues)}",
            )

        return CritiqueResult(status="PASS", score=1.0, issues=[])

    async def revise(
        self, result: Dict[str, Any], critique: CritiqueResult
    ) -> Dict[str, Any]:
        """
        Revise art based on critique.

        Args:
            result: Original output
            critique: Critique feedback

        Returns:
            Revised output
        """
        logger.info(f"Art Director revising based on: {critique.revision_instructions}")

        # In production, regenerate specific images
        # For now, return original result
        return result

    async def generate_concept_sketches(
        self,
        reference_image_data: str,
        reference_id: str,
        instruction: str,
        project_id: str
    ) -> Dict[str, Any]:
        """
        Generate concept sketches based on a visual reference.

        This is used in the concept validation loop - generates quick concept
        variations for user approval before creating final hero images.

        The reference image data is passed directly (not looked up from brief),
        as captured references are stored temporarily on the connection.

        Args:
            reference_image_data: Base64 image data of the captured reference
            reference_id: ID of the reference (for tracking)
            instruction: User's instruction for the concepts
            project_id: Project identifier

        Returns:
            Dict with success status and list of concept images
        """
        logger.info(f"[Art Director] Generating concept sketches from reference: {reference_id}")

        try:
            from app.services.redis_client import redis_client
            from app.workflows.art_director_workflow import ArtDirectorWorkflow

            # Get project brief for product context
            brief = await redis_client.get_project_brief(project_id)
            product_context = {
                "product_name": brief.product_name if brief else "product",
                "theme": brief.theme if brief else "",
                "product_category": brief.product_category if brief else ""
            }

            # Instantiate workflow
            workflow = ArtDirectorWorkflow()

            # Generate concepts using workflow
            concepts = await workflow.generate_concepts(
                reference_image_data=reference_image_data,
                instruction=instruction,
                product_context=product_context,
                num_concepts=3
            )

            if not concepts:
                return {
                    "success": False,
                    "error": "Failed to generate concept sketches"
                }

            # Track iteration number
            iteration = getattr(self, '_concept_iteration', 0) + 1
            self._concept_iteration = iteration

            # Prepare concepts for preview (don't save to brief yet - user needs to select)
            import time
            concept_previews = []
            for i, concept in enumerate(concepts):
                concept_id = concept.get("asset_id", f"concept_{int(time.time() * 1000)}_{i}")
                concept_previews.append({
                    "id": concept_id,
                    "url": concept.get("url", ""),
                    "description": concept.get("prompt", "Concept sketch"),
                    "generation_number": i + 1,
                    "instruction": instruction,
                })
                logger.info(f"[Art Director] Prepared concept preview: {concept_id}")

            logger.info(f"[Art Director] Generated {len(concepts)} concept previews (iteration {iteration})")

            return {
                "success": True,
                "concepts": concept_previews,
                "iteration": iteration,
                "message": f"Generated {len(concepts)} concept sketches. They are now visible in the Smart Mirror. Ask the user which one they prefer, or if they want to iterate with different instructions."
            }

        except Exception as e:
            logger.error(f"[Art Director] Error generating concepts: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
