"""
Art Director Direct Async Workflow (No ADK agents to avoid token accumulation).

Architecture:
- Direct asyncio.gather() for parallel execution (4x speedup)
- Simple retry loops with Gemini API calls (no agent wrappers)
- Direct tool calls for image generation and critique
- No conversation history accumulation

Flow per variation:
1. Generate prompt with Gemini 2.5 Flash
2. Generate image with generate_image_tool()
3. Critique with critique_image_tool()
4. Retry if score < 0.7 (max 3 iterations)
"""

import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional

from app.services.google_ai_client import genai_client
from google.genai import types

from app.workflows.art_director_agents import (
    generate_image_tool,
    critique_image_tool,
)

logger = logging.getLogger(__name__)

# Module-level storage for reference images
_current_reference_images_b64: List[str] = []


class ArtDirectorWorkflow:
    """
    Orchestrates 4 parallel image generation loops using direct async.

    Uses asyncio.gather() for parallel execution with simple retry loops.
    No ADK agent wrappers - calls tools and Gemini API directly.
    """

    def __init__(self):
        """Initialize workflow."""
        pass  # No agent setup needed

    async def _generate_prompt(
        self,
        variation: int,
        product_name: str,
        slogan: str,
        theme: str,
        brand_tone: str,
        product_category: str,
        key_features: List[str],
        visual_guidelines: str,
        has_references: bool,
        previous_critique: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate image prompt using Gemini 2.5 Flash.

        Args:
            variation: Image variation number (1-4)
            product_name: Product name
            slogan: Campaign slogan
            theme: Visual theme
            brand_tone: Brand tone
            product_category: Product category
            key_features: Product features
            visual_guidelines: Category-specific guidelines
            has_references: Whether reference images exist
            previous_critique: Previous critique for retry (optional)

        Returns:
            Generated prompt text
        """
        # Variation-specific focus
        variation_focus = [
            "Hero shot with dramatic lighting and bold composition. Product as the star with powerful visual impact.",
            "Lifestyle context showing product in real-world use. Include human interaction or environmental setting.",
            "Close-up detail shot highlighting key features and textures. Show craftsmanship and quality.",
            "Environmental/action shot demonstrating product benefits. Dynamic composition showing product in motion."
        ][variation - 1]

        # Build prompt engineering request
        prompt_request = f"""You are an expert Image Generation Prompt Engineer for Gemini 2.5 Flash Image.

TASK: Create a hyper-specific, descriptive prompt for variation {variation}.

VARIATION {variation} FOCUS:
{variation_focus}

PRODUCT CONTEXT:
- Product: {product_name}
- Slogan: "{slogan}"
- Theme: {theme}
- Brand Tone: {brand_tone}
- Category: {product_category}
- Key Features: {', '.join(key_features[:3])}
- Visual Guidelines: {visual_guidelines}

PROMPT ENGINEERING RULES:
1. Write detailed scene descriptions, NOT keyword lists
2. Include specific details about:
   - Lighting: direction, quality, mood
   - Composition: camera angle, framing
   - Color palette: specific tones
   - Textures and materials
   - Environmental context
3. Match the brand theme and tone throughout
{"4. Match the composition style, lighting quality, and color palette of the reference images" if has_references else ""}
5. Emphasize: {variation_focus}
6. Keep prompt focused and concrete
7. Specify 16:9 aspect ratio
{"8. ADDRESS THESE ISSUES FROM PREVIOUS ATTEMPT: " + ", ".join(previous_critique.get("issues", [])) if previous_critique else ""}

OUTPUT: Write ONLY the prompt text, no explanations or metadata."""

        try:
            response = await genai_client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=[types.Part(text=prompt_request)],
                config=types.GenerateContentConfig(temperature=0.7)
            )

            prompt = response.text.strip()
            logger.info(f"[PromptEng Var{variation}] Generated prompt: {prompt[:100]}...")
            return prompt

        except Exception as e:
            logger.error(f"[PromptEng Var{variation}] Error: {e}")
            # Fallback basic prompt
            return f"{product_name} product photography, {theme} theme, professional quality, 16:9 aspect ratio"

    async def _generate_one_image(
        self,
        variation: int,
        product_name: str,
        slogan: str,
        theme: str,
        brand_tone: str,
        product_category: str,
        key_features: List[str],
        visual_guidelines: str,
        has_references: bool,
    ) -> Dict[str, Any]:
        """
        Generate one image variation with retry logic.

        Args:
            variation: Image variation number (1-4)
            product_name: Product name
            slogan: Campaign slogan
            theme: Visual theme
            brand_tone: Brand tone
            product_category: Product category
            key_features: Product features
            visual_guidelines: Category-specific guidelines
            has_references: Whether reference images exist

        Returns:
            Image result dict with image_b64, critique, etc.
        """
        logger.info(f"[Var{variation}] Starting image generation with max 3 iterations")

        max_iterations = 3
        previous_critique = None

        for iteration in range(1, max_iterations + 1):
            logger.info(f"[Var{variation}] Iteration {iteration}/{max_iterations}")

            # Step 1: Generate prompt
            prompt = await self._generate_prompt(
                variation=variation,
                product_name=product_name,
                slogan=slogan,
                theme=theme,
                brand_tone=brand_tone,
                product_category=product_category,
                key_features=key_features,
                visual_guidelines=visual_guidelines,
                has_references=has_references,
                previous_critique=previous_critique,
            )

            # Step 2: Generate image
            image_result = await generate_image_tool(
                prompt=prompt,
                reference_images_b64=None,  # Tool auto-retrieves from module variable
                variation=variation
            )

            if not image_result.get("success"):
                logger.error(f"[Var{variation}] Image generation failed: {image_result.get('error')}")
                continue  # Retry

            image_b64 = image_result["image_b64"]

            # Step 3: Critique image
            critique = await critique_image_tool(
                image_b64=image_b64,
                variation=variation,
                theme=theme,
                brand_tone=brand_tone,
                product_category=product_category,
            )

            score = critique.get("score", 0.0)
            approved = critique.get("approved", False)

            logger.info(
                f"[Var{variation}] Critique: {critique.get('recommendation', 'UNKNOWN')} "
                f"(score: {score:.2f}, approved: {approved})"
            )

            # Step 4: Check if approved
            if approved and score >= 0.7:
                logger.info(f"[Var{variation}] ✓ Image approved! Returning result.")
                return {
                    "success": True,
                    "image_b64": image_b64,
                    "critique": critique,
                    "variation": variation,
                    "iterations": iteration,
                }

            # Not approved - prepare for retry
            previous_critique = critique
            logger.info(f"[Var{variation}] Not approved (score: {score:.2f}), will retry...")

        # Max iterations reached
        logger.warning(f"[Var{variation}] Max iterations reached, returning last result")
        return {
            "success": image_result.get("success", False),
            "image_b64": image_result.get("image_b64", ""),
            "critique": previous_critique or {},
            "variation": variation,
            "iterations": max_iterations,
        }

    async def execute(
        self,
        slogan: str,
        product_name: str,
        product_category: str,
        theme: str,
        brand_tone: str,
        key_features: List[str],
        reference_images: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Execute parallel image generation workflow.

        Args:
            slogan: Campaign slogan
            product_name: Product name
            product_category: Product category (footwear, beverage, etc.)
            theme: Brand theme
            brand_tone: Brand tone (futuristic, luxury, etc.)
            key_features: Product features to highlight
            reference_images: User-uploaded reference images (ImageAsset dicts)

        Returns:
            List of 4 ImageAsset dictionaries with generated images
        """
        logger.info(f"ArtDirectorWorkflow: Starting parallel generation for {product_name}")

        # Convert reference images to base64 list
        reference_images_b64 = []

        for ref_img in reference_images[:3]:  # Max 3 references per Gemini Image API
            url = ref_img.get('url', '')
            if url.startswith('data:image'):
                # Extract base64 from data URI
                try:
                    _, b64_data = url.split(',', 1)
                    reference_images_b64.append(b64_data)
                    logger.info(f"ArtDirectorWorkflow: Added reference image ({len(b64_data)} chars)")
                except Exception as e:
                    logger.warning(f"ArtDirectorWorkflow: Failed to parse reference image: {e}")

        # Get category-specific visual guidelines
        from app.agents.art_director import CATEGORY_VISUAL_GUIDELINES
        visual_guidelines = CATEGORY_VISUAL_GUIDELINES.get(
            product_category,
            "Professional product photography with clean composition"
        )

        # Store reference images in module-level variable
        global _current_reference_images_b64
        _current_reference_images_b64 = reference_images_b64

        has_references = len(reference_images_b64) > 0

        logger.info("ArtDirectorWorkflow: Starting parallel execution of 4 image generation loops...")

        # Execute 4 image generations in parallel
        tasks = [
            self._generate_one_image(
                variation=i,
                product_name=product_name,
                slogan=slogan,
                theme=theme,
                brand_tone=brand_tone,
                product_category=product_category,
                key_features=key_features,
                visual_guidelines=visual_guidelines,
                has_references=has_references,
            )
            for i in range(1, 5)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("ArtDirectorWorkflow: Parallel execution completed")

        # Convert results to ImageAsset format
        # Variation descriptions for display
        variation_descriptions = [
            "Hero shot with dramatic lighting and bold composition",
            "Lifestyle context showing product in real-world use",
            "Close-up detail shot highlighting key features and textures",
            "Environmental/action shot demonstrating product benefits"
        ]

        images = []
        for i, result in enumerate(results, 1):
            if isinstance(result, Exception):
                logger.error(f"ArtDirectorWorkflow: Variation {i} failed with exception: {result}")
                continue

            if not isinstance(result, dict) or not result.get("success"):
                logger.warning(f"ArtDirectorWorkflow: Variation {i} failed - {result.get('error', 'Unknown error') if isinstance(result, dict) else 'Invalid result'}")
                continue

            # Convert to ImageAsset format
            from app.models.assets import ImageAsset

            b64_data = result.get("image_b64", "")
            critique = result.get("critique", {})

            if not b64_data:
                logger.warning(f"ArtDirectorWorkflow: Variation {i} has no image data")
                continue

            image_url = f"data:image/png;base64,{b64_data}"

            # Use descriptive variation focus as description with product name and variation number
            base_description = variation_descriptions[i-1] if i <= len(variation_descriptions) else "Image variation"
            description = f"{product_name} - {base_description} - Variation {i}"

            asset = ImageAsset(
                asset_id=f"img_{uuid.uuid4().hex[:12]}",
                url=image_url,
                description=description,
                generation_params={
                    "model": "gemini-2.5-flash-image",
                    "variation": i,
                    "theme": theme,
                    "approved": critique.get("approved", False) if isinstance(critique, dict) else False,
                    "score": critique.get("score", 0.0) if isinstance(critique, dict) else 0.0,
                    "issues": critique.get("issues", []) if isinstance(critique, dict) else [],
                    "iterations": result.get("iterations", 0),
                }
            )
            images.append(asset)
            logger.info(
                f"ArtDirectorWorkflow: Collected variation {i} "
                f"(score: {asset.generation_params.get('score', 0.0):.2f}, "
                f"iterations: {asset.generation_params.get('iterations', 0)})"
            )

        logger.info(f"ArtDirectorWorkflow complete: {len(images)}/4 images generated successfully")

        # Return as dicts for compatibility
        return [img.model_dump() for img in images]
