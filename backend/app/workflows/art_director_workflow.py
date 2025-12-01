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
        from app.services.google_ai_client import ImagenClient
        self.google_ai_client = ImagenClient()

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

        # Retry failed variations to ensure we get all 4
        failed_variations = []
        for i, result in enumerate(results, 1):
            if isinstance(result, Exception) or not isinstance(result, dict) or not result.get("success"):
                failed_variations.append(i)
                logger.warning(f"ArtDirectorWorkflow: Variation {i} failed on first attempt, will retry")

        # Retry failed variations (1 retry attempt each)
        if failed_variations:
            logger.info(f"ArtDirectorWorkflow: Retrying {len(failed_variations)} failed variations: {failed_variations}")
            retry_tasks = [
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
                for i in failed_variations
            ]
            retry_results = await asyncio.gather(*retry_tasks, return_exceptions=True)

            # Update results with retry outcomes
            for variation, retry_result in zip(failed_variations, retry_results):
                results[variation - 1] = retry_result
                if isinstance(retry_result, dict) and retry_result.get("success"):
                    logger.info(f"ArtDirectorWorkflow: Variation {variation} succeeded on retry")
                else:
                    logger.error(f"ArtDirectorWorkflow: Variation {variation} failed even after retry")

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

    # ========================================================================
    # IMAGE REFINEMENT METHODS (NEW)
    # ========================================================================

    async def _analyze_user_feedback(
        self,
        original_prompt: str,
        user_feedback: str,
        image_b64: str,
    ) -> Dict[str, Any]:
        """
        Analyze user feedback using Gemini 2.5 Flash with vision.

        Extracts what to KEEP vs. CHANGE from user's refinement request
        by analyzing both the image and the feedback.

        Args:
            original_prompt: The prompt used to generate the original image
            user_feedback: User's refinement request (e.g., "add modern elements")
            image_b64: Base64-encoded original image for visual analysis

        Returns:
            {
                "keep_aspects": List[str],
                "change_aspects": List[str],
                "refinement_strategy": str
            }
        """

        analysis_system_prompt = """
You are an expert Image Analysis AI helping refine product marketing images.

Your job: Analyze user feedback on an image to determine what to KEEP and what to CHANGE.

# ANALYSIS APPROACH

1. **Understand the Feedback**
   - What is the user explicitly praising? (e.g., "I like the lighting")
   - What is the user requesting to change? (e.g., "but add modern elements")
   - What is implied to stay the same? (composition, positioning, etc.)

2. **Visual Analysis** (from image)
   - Identify current composition, lighting, colors, styling
   - Note prominent features that user might want preserved
   - Detect elements that might need modification

3. **Extract Keep/Change Lists**
   - KEEP: Elements user likes OR elements not mentioned (assume preservation)
   - CHANGE: Explicit requests for additions, modifications, or removals

# OUTPUT FORMAT

Return valid JSON only (no markdown):
{
    "keep_aspects": [
        "Specific aspect 1 to preserve",
        "Specific aspect 2 to preserve",
        ...
    ],
    "change_aspects": [
        "Specific change 1 to implement",
        "Specific change 2 to implement",
        ...
    ],
    "refinement_strategy": "One-sentence strategy for refinement"
}

# EXAMPLES

**Example 1**:
Feedback: "Option 1 is great, but add modern UI elements"
Keep: ["Dramatic lighting", "Product centered", "Ocean-blue background", "16:9 composition"]
Change: ["Add modern UI overlays", "Include holographic elements", "Tech graphics"]
Strategy: "Maintain hero product shot composition and lighting, overlay modern tech UI elements"

**Example 2**:
Feedback: "Make it brighter and more vibrant"
Keep: ["Composition", "Product positioning", "Background style", "Overall aesthetic"]
Change: ["Increase brightness", "Boost color saturation", "Enhance vibrancy"]
Strategy: "Maintain all compositional elements, adjust exposure and color saturation"

**Example 3**:
Feedback: "I love the composition but dial back the holographic overlays"
Keep: ["Composition", "Framing", "Product positioning", "Base lighting"]
Change: ["Reduce holographic overlay intensity", "Make UI elements more subtle", "Soften tech graphics"]
Strategy: "Preserve composition completely, reduce visual prominence of overlay elements"

# IMPORTANT RULES

- KEEP aspects should be specific (not "everything else")
- CHANGE aspects should be actionable instructions
- If feedback is vague, infer reasonable keep/change from image context
- Refinement strategy should be implementable as an image generation prompt
- Always preserve product as focal point unless explicitly told otherwise
"""

        user_prompt = f"""
# ORIGINAL IMAGE GENERATION PROMPT
{original_prompt}

# USER'S REFINEMENT FEEDBACK
{user_feedback}

# TASK
Analyze the image and feedback. Return JSON with keep_aspects, change_aspects, and refinement_strategy.
"""

        try:
            import json
            import re
            from google.genai.types import Part

            response = await genai_client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    Part(text=user_prompt),
                    Part(inline_data={'mime_type': 'image/png', 'data': image_b64})
                ],
                config=types.GenerateContentConfig(
                    temperature=0.3,  # Lower for consistent analysis
                    system_instruction=analysis_system_prompt,
                    response_mime_type='application/json'
                )
            )

            # Parse JSON response
            text = response.text.strip()
            text = re.sub(r'^```json?\s*', '', text)
            text = re.sub(r'\s*```$', '', text)

            analysis = json.loads(text)

            logger.info(
                f"Feedback analysis: Keep {len(analysis['keep_aspects'])} aspects, "
                f"Change {len(analysis['change_aspects'])} aspects"
            )

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing feedback: {e}")
            # Fallback: simple text-based analysis
            return {
                "keep_aspects": ["composition", "product positioning", "overall style"],
                "change_aspects": [user_feedback],
                "refinement_strategy": f"Apply user's requested change: {user_feedback}"
            }

    async def _generate_refinement_prompt(
        self,
        original_prompt: str,
        keep_aspects: List[str],
        change_aspects: List[str],
        refinement_strategy: str,
        product_context: Dict[str, Any],
    ) -> str:
        """
        Generate refinement prompt incorporating keep/change aspects.

        Args:
            original_prompt: Original image generation prompt
            keep_aspects: Aspects to preserve from original
            change_aspects: Changes to implement
            refinement_strategy: Overall strategy for refinement
            product_context: Product details (name, category, theme, etc.)

        Returns:
            Refined prompt text
        """
        keep_text = "\n".join([f"- {aspect}" for aspect in keep_aspects])
        change_text = "\n".join([f"- {aspect}" for aspect in change_aspects])

        refinement_prompt = f"""Generate a refined version of this product image.

REFINEMENT STRATEGY:
{refinement_strategy}

PRESERVE THESE ASPECTS (CRITICAL):
{keep_text}

IMPLEMENT THESE CHANGES:
{change_text}

PRODUCT CONTEXT:
- Product: {product_context.get('product_name', 'Unknown')}
- Category: {product_context.get('product_category', 'product')}
- Theme: {product_context.get('theme', 'modern')}
- Brand Tone: {product_context.get('brand_tone', 'professional')}

ORIGINAL PROMPT FOR REFERENCE:
{original_prompt}

REQUIREMENTS:
- Product MUST remain the clear focal point
- Maintain professional marketing quality
- Implement changes while preserving specified aspects
- 16:9 aspect ratio
- High resolution, photorealistic style

Generate the refined image maintaining what works while implementing the requested changes.
"""
        return refinement_prompt

    async def refine_image(
        self,
        original_image: Dict[str, Any],
        user_feedback: str,
        product_context: Dict[str, Any],
        max_iterations: int = 2,
    ) -> Dict[str, Any]:
        """
        Refine a specific image based on user feedback.

        Args:
            original_image: Original ImageAsset dict
            user_feedback: Natural language feedback (e.g., "add modern elements")
            product_context: Product name, category, theme, brand_tone, key_features
            max_iterations: Max retry attempts if critique score < 0.7

        Returns:
            Refined ImageAsset dict with new version metadata

        Raises:
            ValueError: If max refinement iterations exceeded
        """
        from app.models.assets import ImageAsset

        # Check max iterations limit
        MAX_REFINEMENT_ITERATIONS = 5
        current_iteration = original_image.get("refinement_iteration", 0)

        if current_iteration >= MAX_REFINEMENT_ITERATIONS:
            raise ValueError(
                f"Maximum refinement iterations ({MAX_REFINEMENT_ITERATIONS}) reached. "
                "Consider selecting an existing version or generating a new image."
            )

        logger.info(f"Refining image {original_image.get('asset_id')} with feedback: '{user_feedback}'")

        # Extract base64 from original image URL
        original_url = original_image.get("url", "")
        if not original_url.startswith("data:image"):
            raise ValueError("Original image must be a data URI")

        _, original_b64 = original_url.split(',', 1)

        # Step 1: Analyze user feedback
        logger.info("Step 1: Analyzing user feedback with Gemini vision...")

        # Get original prompt from generation params (if available)
        original_prompt = original_image.get("generation_params", {}).get("prompt", "Product hero shot")

        analysis = await self._analyze_user_feedback(
            original_prompt=original_prompt,
            user_feedback=user_feedback,
            image_b64=original_b64
        )

        # Step 2: Generate refinement prompt
        logger.info("Step 2: Generating refinement prompt...")
        refinement_prompt = await self._generate_refinement_prompt(
            original_prompt=original_prompt,
            keep_aspects=analysis["keep_aspects"],
            change_aspects=analysis["change_aspects"],
            refinement_strategy=analysis["refinement_strategy"],
            product_context=product_context
        )

        # Step 3-5: Generate and critique refined image (with retry loop)
        logger.info("Step 3: Generating refined image...")

        refined_b64 = None
        final_critique = None

        for iteration in range(max_iterations):
            # Generate image with original as reference
            image_result = await generate_image_tool(
                prompt=refinement_prompt,
                reference_images_b64=[original_b64],  # Use original as reference
                variation=original_image.get("generation_params", {}).get("variation", 1)
            )

            if not image_result.get("success"):
                logger.warning(f"Image generation failed on iteration {iteration + 1}")
                continue

            refined_b64 = image_result.get("image_b64", "")

            # Critique with user feedback validation
            logger.info("Step 4: Validating refinement with critique...")
            critique = await critique_image_tool(
                image_b64=refined_b64,
                variation=original_image.get("generation_params", {}).get("variation", 1),
                theme=product_context.get("theme", "modern"),
                brand_tone=product_context.get("brand_tone", "professional"),
                product_category=product_context.get("product_category", "product"),
                user_feedback=user_feedback  # NEW: Pass feedback for validation
            )

            final_critique = critique
            score = critique.get("score", 0.0)

            if score >= 0.7:
                logger.info(f"Refinement approved with score {score:.2f}")
                break
            else:
                logger.warning(f"Refinement iteration {iteration + 1} scored {score:.2f}, retrying...")

        if not refined_b64:
            raise RuntimeError("Failed to generate refined image after all retry attempts")

        # Step 5: Create refined ImageAsset
        logger.info("Step 5: Creating refined ImageAsset...")

        new_iteration = current_iteration + 1
        refined_image = ImageAsset(
            asset_id=f"img_{uuid.uuid4().hex[:12]}",
            url=f"data:image/png;base64,{refined_b64}",
            description=f"{original_image.get('description', 'Image')} - v{new_iteration} ({user_feedback})",
            generation_params={
                "model": "gemini-2.5-flash-image",
                "variation": original_image.get("generation_params", {}).get("variation", 1),
                "theme": product_context.get("theme", ""),
                "approved": final_critique.get("approved", False) if final_critique else False,
                "score": final_critique.get("score", 0.0) if final_critique else 0.0,
                "issues": final_critique.get("issues", []) if final_critique else [],
                "iterations": max_iterations,
                "prompt": refinement_prompt,  # Store for future refinements
                "feedback_addressed": final_critique.get("feedback_addressed", False) if final_critique else False,
            },
            # Refinement tracking (within same generation)
            parent_asset_id=original_image.get("asset_id"),
            refinement_iteration=new_iteration,
            user_feedback_applied=user_feedback,
            # Generation tracking (NEW - preserve from original)
            generation_number=original_image.get("generation_number", 1),
            variation_number=original_image.get("variation_number", 1),
        )

        logger.info(
            f"Refinement complete: v{new_iteration} created "
            f"(score: {refined_image.generation_params['score']:.2f})"
        )

        return refined_image.model_dump()

    async def refine_all_images(
        self,
        all_images: List[Dict[str, Any]],
        global_feedback: str,
        product_context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Refine ALL images with the same feedback in parallel.

        Args:
            all_images: List of ImageAsset dicts (typically 4)
            global_feedback: Feedback to apply to all images
            product_context: Product details

        Returns:
            List of refined ImageAsset dicts
        """
        logger.info(f"Batch refining {len(all_images)} images with feedback: '{global_feedback}'")

        # Refine all images in parallel
        tasks = [
            self.refine_image(
                original_image=img,
                user_feedback=global_feedback,
                product_context=product_context
            )
            for img in all_images
        ]

        refined_images = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions, log errors
        successful_refinements = []
        for i, result in enumerate(refined_images):
            if isinstance(result, Exception):
                logger.error(f"Failed to refine image {i+1}: {result}")
                # Keep original if refinement failed
                successful_refinements.append(all_images[i])
            else:
                successful_refinements.append(result)

        logger.info(f"Batch refinement complete: {len(successful_refinements)}/{len(all_images)} successful")

        return successful_refinements

    async def generate_concepts(
        self,
        reference_image_data: str,
        instruction: str,
        product_context: Dict[str, Any],
        num_concepts: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Generate fast concept sketches based on a reference image.

        Used for the concept validation loop - generates low-fidelity variations
        to confirm style/direction before creating final hero images.

        Uses Gemini 2.5 Flash Image with the reference image to generate
        concepts that actually incorporate the user's visual input.

        Args:
            reference_image_data: Base64-encoded reference image (data URI format)
            instruction: User's instruction for the concepts
            product_context: Product details from brief
            num_concepts: Number of concept variations to generate (default 3)

        Returns:
            List of ImageAsset dicts with type="concept"
        """
        import base64
        import time
        from google.genai.types import Part
        from app.services.google_ai_client import genai_client

        logger.info(f"Generating {num_concepts} concept sketches based on reference image")

        # Extract base64 from data URI
        reference_b64 = ""
        if reference_image_data.startswith("data:image"):
            try:
                _, reference_b64 = reference_image_data.split(",", 1)
                logger.info(f"[Concepts] Extracted reference image: {len(reference_b64)} chars")
            except Exception as e:
                logger.warning(f"[Concepts] Failed to parse reference image data URI: {e}")
        else:
            # Assume it's already base64
            reference_b64 = reference_image_data

        # Build concept generation prompt
        product_name = product_context.get("product_name", "product")
        theme = product_context.get("theme", "")
        product_category = product_context.get("product_category", "")
        reference_category = product_context.get("reference_category", "sketch")
        reference_description = product_context.get("reference_description", "")

        # Determine extraction instructions based on reference category
        if reference_category == "sketch":
            extraction_context = """CRITICAL: The reference image shows a hand-drawn sketch on paper (possibly in a notebook, held by hands,
with background elements visible from a camera/video feed). IGNORE everything except the DRAWING ITSELF:
- IGNORE: hands, notebook edges, spiral binding, lined paper, background (curtains, room, furniture, etc.)
- IGNORE: any person visible, camera artifacts, lighting conditions
- EXTRACT: ONLY the SKETCH/DRAWING content - the actual design being shown on the paper
- INTERPRET: Transform the rough sketch into a polished, professional concept"""
        elif reference_category == "screen":
            extraction_context = """CRITICAL: The reference image shows a screen capture or digital image.
- EXTRACT: The main visual content displayed on the screen
- IGNORE: Screen bezels, reflections, or UI elements not part of the design"""
        elif reference_category == "product":
            extraction_context = """CRITICAL: The reference image shows a physical product.
- EXTRACT: The product design, form, colors, and features
- IGNORE: Background, hands holding it, or surrounding objects"""
        else:
            extraction_context = """Extract the main visual subject from the reference image.
- Focus on the central design element
- Ignore any incidental background or capture artifacts"""

        prompt = f"""Create a POLISHED CONCEPT IMAGE inspired by the visual reference.

{extraction_context}

FOCUS ON THE DESIGN CONTENT:
- The main subject/object being shown (e.g., vehicle, product, character)
- The composition and layout of the key elements
- Any labels, text, or annotations that are part of the design
- The design intent and style

REFERENCE CONTEXT: {reference_description if reference_description else 'User-provided visual reference'}

PRODUCT: {product_name} ({product_category})
INSTRUCTION: {instruction}
THEME: {theme}

OUTPUT: Generate a CLEAN, PROFESSIONAL concept image that brings the design to life.
Do NOT include: notebooks, paper edges, hands, pens, video call UI, room backgrounds, or any capture artifacts.
Create a standalone product visualization as if it were a professional marketing render or product concept art."""

        concepts = []

        try:
            # Generate concepts sequentially using Gemini 2.5 Flash Image
            # (API doesn't support batch generation with reference images)
            for i in range(num_concepts):
                variation_instruction = (
                    "Focus on the core composition and primary elements from the design." if i == 0 else
                    "Explore a slightly different angle or perspective of the design." if i == 1 else
                    "Add more creative interpretation while keeping the essence of the design."
                )
                variation_prompt = f"""{prompt}

VARIATION {i + 1} of {num_concepts}: {variation_instruction}

CRITICAL REMINDER: Output a CLEAN professional product image ONLY.
- NO notebook, NO paper, NO lined pages
- NO hands, NO fingers, NO person
- NO room background, NO curtains, NO furniture
- NO video call interface, NO camera artifacts
ONLY the product/design itself on a clean background."""

                try:
                    # Build contents with reference image + prompt
                    contents = []

                    # Add reference image
                    if reference_b64:
                        contents.append(Part(
                            inline_data={'mime_type': 'image/jpeg', 'data': reference_b64}
                        ))
                        logger.info(f"[Concepts] Added reference image to concept {i + 1}")

                    # Add text prompt
                    contents.append(Part(text=variation_prompt))

                    # Generate with Gemini 2.5 Flash Image (same model as hero images)
                    logger.info(f"[Concepts] Generating concept {i + 1}/{num_concepts}...")
                    response = await genai_client.aio.models.generate_content(
                        model="gemini-2.5-flash-image",
                        contents=contents,
                        config=types.GenerateContentConfig(
                            response_modalities=['Image'],
                            image_config=types.ImageConfig(
                                aspect_ratio="16:9",
                            )
                        )
                    )

                    # Extract image from response
                    for part in response.parts:
                        if hasattr(part, 'inline_data') and part.inline_data:
                            image_bytes = part.inline_data.data
                            img_b64 = base64.b64encode(image_bytes).decode('utf-8')

                            concept = {
                                "asset_id": f"concept_{int(time.time() * 1000)}_{i}",
                                "url": f"data:image/png;base64,{img_b64}",
                                "type": "concept",
                                "prompt": variation_prompt,
                                "generation_number": i + 1,
                                "timestamp": time.time(),
                                "metadata": {
                                    "is_concept": True,
                                    "reference_based": True,
                                    "has_reference_image": bool(reference_b64)
                                }
                            }
                            concepts.append(concept)
                            logger.info(f"[Concepts] ✓ Generated concept {i + 1}: {len(image_bytes)} bytes")
                            break

                except Exception as e:
                    logger.error(f"[Concepts] Error generating concept {i + 1}: {e}")
                    continue

            logger.info(f"[Concepts] Generated {len(concepts)}/{num_concepts} concept sketches")
            return concepts

        except Exception as e:
            logger.error(f"[Concepts] Error generating concepts: {e}", exc_info=True)
            return []

    async def rollback_to_version(
        self,
        target_version: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Restore a previous version as current (no regeneration).

        Args:
            target_version: The ImageAsset dict to restore

        Returns:
            The target version (unchanged)
        """
        logger.info(f"Rolling back to version {target_version.get('refinement_iteration', 0)}")
        return target_version

    async def refine_version_with_attributes(
        self,
        base_version: Dict[str, Any],
        attribute_sources: Dict[str, Dict[str, Any]],
        product_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create new version by combining base with attributes from other versions.

        Args:
            base_version: The version to use as foundation
            attribute_sources: Dict mapping attributes to source versions
                e.g., {"brightness": v4_dict, "saturation": v3_dict}
            product_context: Product details

        Returns:
            New refined ImageAsset combining requested attributes

        Example:
            User: "Take v2 but keep brightness from v4"
            → base_version = v2
            → attribute_sources = {"brightness": v4}
            → Generates v5 with v2's composition + v4's brightness
        """
        logger.info(
            f"Creating version mix from v{base_version.get('refinement_iteration', 0)} "
            f"with attributes from {len(attribute_sources)} other versions"
        )

        # Build synthetic feedback describing the attribute mixing
        feedback_parts = []
        for attr, source_version in attribute_sources.items():
            source_iter = source_version.get("refinement_iteration", 0)
            feedback_parts.append(f"apply {attr} from version {source_iter}")

        synthetic_feedback = "Combine: " + ", ".join(feedback_parts)

        # For simplicity, treat this as a refinement with synthetic feedback
        # In a more sophisticated implementation, you would extract actual parameters
        # from attribute_sources and apply them programmatically

        return await self.refine_image(
            original_image=base_version,
            user_feedback=synthetic_feedback,
            product_context=product_context
        )
