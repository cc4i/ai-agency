"""Art Director Agent - Hero image generation.

Uses Imagen to generate photorealistic product images.
Product-agnostic with category-specific visual guidelines.
"""

import logging
import uuid
from typing import Any, Dict

from app.agents.base import AgentBase
from app.models.assets import ArtDirectorOutput, CritiqueResult, ImageAsset
from app.services.google_ai_client import imagen_client

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

    Generates exactly 4 photorealistic images using Imagen.
    Adapts visual style based on product category and brand tone.
    """

    def __init__(self):
        """Initialize Art Director Agent."""
        super().__init__(agent_id="art_director")

    async def execute(
        self, task: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute hero image generation.

        Args:
            task: Contains slogan, theme, product info, category, brand_tone
            context: Shared project context

        Returns:
            ArtDirectorOutput with 4 images and style guide
        """
        logger.info(f"Art Director executing for: {task.get('product_name')}")

        slogan = task.get("slogan", "")
        theme = task.get("theme", "modern")
        product_name = task.get("product_name", "Product")
        product_category = task.get("product_category", "product")
        brand_tone = task.get("brand_tone", "professional")
        key_features = task.get("key_features", [])

        # Get category-specific guidelines
        visual_guidelines = CATEGORY_VISUAL_GUIDELINES.get(
            product_category,
            "Professional product photography with clean composition",
        )

        # Generate 4 image variations
        images = []
        for i in range(4):
            image = await self._generate_image(
                slogan=slogan,
                theme=theme,
                product_name=product_name,
                product_category=product_category,
                brand_tone=brand_tone,
                key_features=key_features,
                visual_guidelines=visual_guidelines,
                variation=i + 1,
            )
            images.append(image)

        # Create style guide
        style_guide = self._create_style_guide(
            theme, brand_tone, product_category, visual_guidelines
        )

        output = ArtDirectorOutput(images=images, style_guide=style_guide)

        logger.info(f"Art Director completed: {len(images)} images generated")

        return output.model_dump()

    async def _generate_image(
        self,
        slogan: str,
        theme: str,
        product_name: str,
        product_category: str,
        brand_tone: str,
        key_features: list,
        visual_guidelines: str,
        variation: int,
    ) -> ImageAsset:
        """
        Generate a single hero image.

        Args:
            slogan: Campaign slogan
            theme: Visual theme
            product_name: Product name
            product_category: Product category
            brand_tone: Brand tone (futuristic, luxury, etc.)
            key_features: Product features to highlight
            visual_guidelines: Category-specific guidelines
            variation: Image variation number (1-4)

        Returns:
            ImageAsset with generated image
        """
        # Build comprehensive prompt
        prompt = f"""
        Create a stunning photorealistic hero image for a {product_category} campaign.

        PRODUCT: {product_name}
        SLOGAN: "{slogan}"
        THEME: {theme}
        BRAND TONE: {brand_tone}
        KEY FEATURES TO HIGHLIGHT: {', '.join(key_features[:3])}

        VISUAL STYLE:
        {visual_guidelines}

        COMPOSITION GUIDELINES:
        - Product should be the focal point
        - {theme} aesthetic with {brand_tone} feel
        - Professional {product_category}-appropriate lighting
        - High-quality, magazine-worthy composition
        - Variation {variation}: {"Hero shot with dramatic lighting" if variation == 1 else "Lifestyle context" if variation == 2 else "Close-up detail shot" if variation == 3 else "Environmental/action shot"}

        TECHNICAL SPECS:
        - Photorealistic quality
        - 16:9 aspect ratio
        - Sharp focus on product
        - Professional color grading
        - {brand_tone} color palette
        """

        generation_params = {
            "prompt": prompt,
            "aspect_ratio": "16:9",
            "variation": variation,
            "theme": theme,
            "brand_tone": brand_tone,
        }

        # Generate image using Imagen
        image_data = await imagen_client.generate_images(
            prompt=prompt,
            number_of_images=1,
            aspect_ratio="16:9",
        )

        # In production, upload to GCS and get URL
        # For now, create mock asset
        asset_id = f"img_{uuid.uuid4().hex[:12]}"
        mock_url = f"gs://ai-agency-demo/images/{asset_id}.png"

        image_asset = ImageAsset(
            asset_id=asset_id,
            url=mock_url,
            generation_params=generation_params,
            description=f"{product_name} hero image - {theme} theme, variation {variation}",
        )

        logger.debug(f"Generated image {variation}: {asset_id}")

        return image_asset

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
