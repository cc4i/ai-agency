"""
Tool functions for Art Director workflow.

Tools:
- generate_image_tool: Generates images using Gemini 2.5 Flash Image
- critique_image_tool: Validates image quality using Gemini Pro Vision
"""

import base64
import json
import logging
import re
from typing import Any, Dict, List, Optional

from google.genai import types

logger = logging.getLogger(__name__)


# ============================================================================
# TOOL: Generate Image with Gemini 2.5 Flash Image
# ============================================================================

async def generate_image_tool(
    prompt: str,
    reference_images_b64: Optional[List[str]] = None,
    variation: int = 1,
) -> Dict[str, Any]:
    """
    Generate single image using Gemini 2.5 Flash Image.

    Args:
        prompt: Hyper-specific descriptive prompt
        reference_images_b64: List of base64-encoded reference images (max 3), or None to auto-retrieve
        variation: Image variation number (1-4)

    Returns:
        {"success": bool, "image_b64": str, "size_bytes": int, "variation": int}
    """
    try:
        logger.info(f"[ImageGenTool] Generating variation {variation}")

        # Auto-retrieve reference images from workflow context if not provided
        if reference_images_b64 is None:
            from app.workflows.art_director_workflow import _current_reference_images_b64
            reference_images_b64 = _current_reference_images_b64
            logger.info(f"[ImageGenTool] Auto-retrieved {len(reference_images_b64)} reference images from workflow context")

        # Build contents array for Gemini Image API
        from google.genai.types import Part
        from app.services.google_ai_client import genai_client

        contents = []

        # Add reference images (up to 3)
        if reference_images_b64:
            logger.info(f"[ImageGenTool] Using {len(reference_images_b64[:3])} reference images")
            for i, ref_b64 in enumerate(reference_images_b64[:3], 1):
                contents.append(Part(
                    inline_data={'mime_type': 'image/png', 'data': ref_b64}
                ))
                logger.debug(f"[ImageGenTool] Added reference image {i}")

        # Add text prompt
        contents.append(Part(text=prompt))

        # Generate image
        logger.info(f"[ImageGenTool] Calling Gemini 2.5 Flash Image API with 16:9 aspect ratio...")
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
                # part.inline_data.data is bytes, not base64 string
                image_bytes = part.inline_data.data

                # Convert bytes to base64 string
                image_b64 = base64.b64encode(image_bytes).decode('utf-8')

                logger.info(f"[ImageGenTool] ✓ Generated {len(image_bytes)} bytes for variation {variation}")

                return {
                    "success": True,
                    "image_b64": image_b64,
                    "size_bytes": len(image_bytes),
                    "variation": variation,
                }

        raise RuntimeError("No image in response")

    except Exception as e:
        logger.error(f"[ImageGenTool] Error generating variation {variation}: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "variation": variation,
        }


# ============================================================================
# TOOL: Critique Image Quality
# ============================================================================

async def critique_image_tool(
    image_b64: str,
    variation: int,
    theme: str,
    brand_tone: str,
    product_category: str,
    user_feedback: Optional[str] = None,  # NEW: For refinement validation
) -> Dict[str, Any]:
    """
    Validate generated image against quality rules using Gemini Pro Vision.

    For refinements (when user_feedback is provided), validates that feedback was addressed.

    Args:
        image_b64: Base64-encoded generated image
        variation: Image variation number
        theme: Brand theme
        brand_tone: Brand tone
        product_category: Product category
        user_feedback: User's refinement feedback to validate (optional)

    Returns:
        {
            "approved": bool,
            "score": float,
            "issues": List[str],
            "strengths": List[str],
            "recommendation": "APPROVE"|"REVISE"|"REJECT",
            "feedback_addressed": bool (only if user_feedback provided)
        }
    """
    try:
        if user_feedback:
            logger.info(f"[CritiqueTool] Analyzing refinement for variation {variation} (feedback: '{user_feedback}')")
        else:
            logger.info(f"[CritiqueTool] Analyzing variation {variation}")

        # Build critique prompt (different for refinements vs. originals)
        if user_feedback:
            # REFINEMENT critique - validate feedback addressed
            critique_prompt = f"""Analyze this REFINED AI-generated product image.

🎯 CRITICAL: The user requested this refinement:
"{user_feedback}"

Your primary job: Verify this feedback was successfully addressed.

EVALUATION CRITERIA:

1. USER FEEDBACK ADDRESSED (50% weight - CRITICAL):
   - Was the requested change implemented?
   - Is it noticeable and effective?
   - Did it achieve the user's intent?
   - Examples:
     * "add modern elements" → Should see modern UI, tech graphics, contemporary styling
     * "make brighter" → Should have increased exposure/luminosity
     * "dial back overlays" → Should see reduced intensity of overlay elements

2. TECHNICAL QUALITY (25%):
   - Sharpness and clarity maintained
   - No artifacts or distortions
   - Acceptable resolution

3. CONSISTENCY (15%):
   - Product still focal point
   - Brand alignment: Theme={theme}, Tone={brand_tone}
   - Category conventions: {product_category}

4. OVERALL IMPROVEMENT (10%):
   - Is this refinement an improvement over the original?
   - Does it maintain what was good while implementing changes?

SCORING (0.0-1.0):
- 0.9-1.0: Feedback perfectly addressed, excellent refinement
- 0.7-0.89: Feedback mostly addressed, good refinement
- 0.5-0.69: Feedback partially addressed, needs more work
- 0.0-0.49: Feedback not addressed, failed refinement

IMPORTANT: Set approved=true ONLY if:
- Score >= 0.7 AND
- User feedback was substantially addressed

Return ONLY valid JSON:
{{
    "approved": true or false,
    "score": 0.0 to 1.0,
    "issues": ["issue 1", "issue 2"],
    "strengths": ["strength 1", "strength 2"],
    "recommendation": "APPROVE" or "REVISE" or "REJECT",
    "feedback_addressed": true or false
}}
"""
        else:
            # ORIGINAL critique - standard quality validation
            critique_prompt = f"""Analyze this AI-generated product image and validate quality.

EVALUATION CRITERIA:

1. TECHNICAL QUALITY (40%):
   - Sharpness and clarity
   - Proper composition and framing
   - No visible artifacts, distortions, or corruptions
   - Acceptable resolution for marketing use

2. BRAND ALIGNMENT (30%):
   - Theme: {theme}
   - Brand Tone: {brand_tone}
   - Does the aesthetic match these requirements?

3. PRODUCT FOCUS (20%):
   - Is the product clearly visible and the focal point?
   - Category: {product_category}
   - Does it follow {product_category} marketing conventions?

4. SAFETY & COMPLIANCE (10%):
   - No watermarks or unwanted text overlays
   - No inappropriate content
   - Professional and brand-safe

SCORING:
- 0.9-1.0: Excellent, ready for publication
- 0.7-0.89: Good, minor improvements possible
- 0.5-0.69: Acceptable but needs revision
- 0.0-0.49: Poor, requires significant changes

Return ONLY valid JSON (no markdown, no explanations):
{{
    "approved": true or false,
    "score": 0.0 to 1.0,
    "issues": ["specific issue 1", "specific issue 2"],
    "strengths": ["strength 1", "strength 2"],
    "recommendation": "APPROVE" or "REVISE" or "REJECT"
}}

IMPORTANT: Set approved=true ONLY if score >= 0.7
"""

        # Use Gemini Pro Vision to analyze
        from app.services.google_ai_client import genai_client
        from google.genai.types import Part

        response = await genai_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                Part(text=critique_prompt),
                Part(inline_data={'mime_type': 'image/png', 'data': image_b64})
            ],
            config=types.GenerateContentConfig(
                temperature=0.3,
            )
        )

        # Parse JSON response
        text = response.text.strip()

        # Remove markdown code fences if present
        text = re.sub(r'^```json?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)

        critique_data = json.loads(text)

        # Ensure approved is consistent with score
        score = critique_data.get("score", 0.0)
        approved = critique_data.get("approved", False)

        # Enforce rule: approved=true only if score >= 0.7
        if score < 0.7:
            critique_data["approved"] = False
            if approved:
                logger.warning(f"[CritiqueTool] Overriding approved=true because score={score} < 0.7")

        logger.info(
            f"[CritiqueTool] Variation {variation}: {critique_data.get('recommendation', 'UNKNOWN')} "
            f"(score: {score:.2f}, approved: {critique_data['approved']})"
        )

        return critique_data

    except Exception as e:
        logger.error(f"[CritiqueTool] Error analyzing variation {variation}: {e}", exc_info=True)
        return {
            "approved": False,
            "score": 0.0,
            "issues": [f"Critique failed: {str(e)}"],
            "strengths": [],
            "recommendation": "REJECT"
        }
