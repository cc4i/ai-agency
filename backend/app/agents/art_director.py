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
        reference_images = task.get("reference_images", [])

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
                reference_images=reference_images,
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
        reference_images: list = [],
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
        # Build reference style guidance if reference images provided
        reference_guidance = ""
        if reference_images:
            reference_count = len(reference_images)
            reference_descriptions = []
            for i, img in enumerate(reference_images[:3], 1):  # Max 3 references in prompt
                desc = img.get('description', f'Reference {i}')
                reference_descriptions.append(f"- Reference {i}: {desc}")

            reference_guidance = f"""
REFERENCE STYLE GUIDANCE:
The user has provided {reference_count} reference image(s) to guide the visual style.
Match the overall aesthetic, composition style, lighting quality, and color palette of these references.
{chr(10).join(reference_descriptions)}

Use these references as inspiration for:
- Visual composition and framing
- Lighting mood and quality
- Color grading and palette
- Overall artistic direction
"""

        # Build comprehensive prompt
        prompt = f"""
        Create a stunning photorealistic hero image for a {product_category} campaign.

        PRODUCT: {product_name}
        SLOGAN: "{slogan}"
        THEME: {theme}
        BRAND TONE: {brand_tone}
        KEY FEATURES TO HIGHLIGHT: {', '.join(key_features[:3])}
        {reference_guidance}
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
        image_data_list = await imagen_client.generate_images(
            prompt=prompt,
            number_of_images=1,
            aspect_ratio="16:9",
        )

        # Convert image bytes to base64 data URI for display
        import base64
        asset_id = f"img_{uuid.uuid4().hex[:12]}"

        if image_data_list and len(image_data_list) > 0:
            image_bytes = image_data_list[0]
            # Convert to base64 data URI
            base64_data = base64.b64encode(image_bytes).decode('utf-8')
            image_url = f"data:image/png;base64,{base64_data}"
            logger.info(f"Converted image to data URI (length: {len(image_url)})")
        else:
            # Fallback if no image generated
            logger.warning(f"No image generated for variation {variation}, using placeholder")
            image_url = "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iODAwIiBoZWlnaHQ9IjQ1MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iODAwIiBoZWlnaHQ9IjQ1MCIgZmlsbD0iIzMzMyIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmb250LXNpemU9IjI0IiBmaWxsPSIjYWFhIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBkb21pbmFudC1iYXNlbGluZT0ibWlkZGxlIj5JbWFnZSBOb3QgR2VuZXJhdGVkPC90ZXh0Pjwvc3ZnPg=="

        image_asset = ImageAsset(
            asset_id=asset_id,
            url=image_url,  # Now a real base64 data URI!
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
