"""Strategy Agent - Customer personas, slogans, and market analysis.

Uses Gemini Pro Vision to analyze product sketches and Gemini Pro for strategy generation.
Product-agnostic implementation that adapts to any product category.
"""

import logging
from typing import Any, Dict, List

from app.agents.base import AgentBase
from app.models.assets import (
    CritiqueResult,
    CustomerPersona,
    StrategyAgentOutput,
)
from app.services.google_ai_client import gemini_pro_client, gemini_vision_client

logger = logging.getLogger(__name__)


# Category-specific persona generation guidelines
CATEGORY_PERSONA_GUIDELINES = {
    "footwear": "Focus on runners, athletes, fashion-conscious consumers, comfort seekers",
    "beverage": "Consider athletes, gamers, professionals needing energy, health-conscious consumers",
    "electronics": "Target tech enthusiasts, early adopters, smart home users, productivity seekers",
    "fashion": "Include style-conscious consumers, professionals, trend followers, quality seekers",
    "beauty": "Consider skincare enthusiasts, makeup artists, age-conscious consumers, natural product seekers",
    "food": "Target foodies, health-conscious eaters, busy professionals, family meal planners",
    "automotive": "Include performance enthusiasts, eco-conscious drivers, family safety seekers, luxury buyers",
}


class StrategyAgent(AgentBase):
    """
    Strategy Agent generates customer personas, slogans, and market analysis.

    Process:
    1. Analyze product sketch using Gemini Pro Vision
    2. Extract visual theme and key features
    3. Generate 3 customer personas tailored to product category
    4. Create 5 catchy slogans matching brand tone
    5. Provide market analysis for the product category
    """

    def __init__(self):
        """Initialize Strategy Agent."""
        super().__init__(agent_id="strategy")

    async def execute(
        self, task: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute strategy generation.

        Args:
            task: Contains sketch_url, product info, category, theme, brand_tone
            context: Shared project context

        Returns:
            StrategyAgentOutput with personas, slogans, and analysis
        """
        logger.info(f"Strategy Agent executing for product: {task.get('product_name')}")

        # Step 1: Analyze sketch with Vision
        sketch_url = task.get("sketch_url")
        if sketch_url:
            visual_analysis = await self._analyze_sketch(sketch_url, task)
        else:
            visual_analysis = "No sketch provided - proceeding with text description only"

        # Step 2: Generate strategy
        output = await self._generate_strategy(task, visual_analysis)

        logger.info(
            f"Strategy Agent completed: {len(output.personas)} personas, {len(output.slogans)} slogans"
        )

        return output.model_dump()

    async def _analyze_sketch(self, sketch_url: str, task: Dict[str, Any]) -> str:
        """
        Analyze product sketch using Gemini Pro Vision.

        Args:
            sketch_url: URL to product sketch image
            task: Task parameters

        Returns:
            Visual analysis description
        """
        prompt = f"""
        Analyze this {task.get('product_category', 'product')} sketch image.

        Product: {task.get('product_name')}
        Theme: {task.get('theme')}
        Key Features: {', '.join(task.get('key_features', []))}

        Extract and describe:
        1. Visual theme and aesthetic (colors, style, mood)
        2. Key product features visible in the image
        3. Target audience implications from the visual design
        4. Usage context and environment shown

        Provide a concise analysis focusing on visual elements that inform marketing strategy.
        """

        analysis = await gemini_vision_client.analyze_image(sketch_url, prompt)
        logger.debug(f"Visual analysis: {analysis[:100]}...")
        return analysis

    async def _generate_strategy(
        self, task: Dict[str, Any], visual_analysis: str
    ) -> StrategyAgentOutput:
        """
        Generate personas, slogans, and market analysis.

        Args:
            task: Task parameters
            visual_analysis: Output from vision analysis

        Returns:
            Complete strategy output
        """
        product_name = task.get("product_name", "Product")
        product_category = task.get("product_category", "product")
        theme = task.get("theme", "modern")
        brand_tone = task.get("brand_tone", "professional")
        target_market = task.get("target_market", "general consumers")
        key_features = task.get("key_features", [])

        # Get category-specific guidelines
        persona_guidelines = CATEGORY_PERSONA_GUIDELINES.get(
            product_category, "Focus on key demographics for this product category"
        )

        prompt = f"""Generate a comprehensive marketing strategy for the following product:

PRODUCT INFORMATION:
- Name: {product_name}
- Category: {product_category}
- Theme: {theme}
- Brand Tone: {brand_tone}
- Target Market: {target_market}
- Key Features: {', '.join(key_features)}

VISUAL ANALYSIS:
{visual_analysis}

PERSONA GUIDELINES:
{persona_guidelines}

REQUIREMENTS:
1. Create EXACTLY 3 diverse customer personas specific to {product_category} buyers
2. Generate EXACTLY 5 catchy slogans matching the {brand_tone} tone (3-5 words each)
3. Each persona must have:
   - Unique name (e.g., "Tech-Savvy Urban Commuter")
   - Age range
   - Detailed description
   - 3 specific pain points
   - 3 key motivations
   - Product usage context

Return a JSON object with this exact structure:
{{
  "personas": [
    {{
      "name": "string",
      "age_range": "string",
      "description": "string",
      "pain_points": ["string", "string", "string"],
      "motivations": ["string", "string", "string"],
      "product_usage_context": "string"
    }}
  ],
  "slogans": ["string", "string", "string", "string", "string"],
  "market_analysis": "string (2-3 paragraphs)",
  "visual_theme_extracted": "string",
  "category_insights": "string"
}}"""

        # Generate strategy using Gemini with JSON mode
        import json
        import re

        # Call Gemini with JSON mode enabled for guaranteed valid JSON
        response = await gemini_pro_client.generate_content(prompt, json_mode=True)
        logger.info(f"Gemini JSON response received: {len(response) if response else 0} chars")

        # Debug: Log first 500 chars to see what's returned
        logger.debug(f"Response preview: {response[:500]}")

        # Parse JSON response with auto-repair for common issues
        response_text = response.strip()

        # Remove markdown code fences if present
        if response_text.startswith('```'):
            response_text = re.sub(r'^```json?\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)
            logger.warning("JSON mode returned markdown fences - stripping them")

        # Try to parse, with auto-repair on failure
        try:
            parsed = json.loads(response_text)
            logger.info(f"Successfully parsed JSON response")
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e} - attempting auto-repair")
            logger.debug(f"Problematic JSON around char {e.pos}: ...{response_text[max(0, e.pos-50):e.pos+50]}...")

            # Common issue: Truncated JSON - try to close it
            repaired = response_text

            # Remove trailing commas before closing braces/brackets
            repaired = re.sub(r',(\s*[}\]])', r'\1', repaired)

            # If truncated, try to close open structures
            if not repaired.rstrip().endswith('}'):
                logger.warning("JSON appears truncated - attempting to close structures")
                # Count open/close braces and brackets
                open_braces = repaired.count('{') - repaired.count('}')
                open_brackets = repaired.count('[') - repaired.count(']')

                # Close them
                for _ in range(open_brackets):
                    repaired += '\n  ]'
                for _ in range(open_braces):
                    repaired += '\n}'

            # Try parsing again
            try:
                parsed = json.loads(repaired)
                logger.info(f"Successfully parsed JSON after auto-repair")
            except json.JSONDecodeError as e2:
                logger.error(f"Auto-repair failed: {e2}")
                logger.error(f"Full response (first 1000 chars): {response[:1000]}")
                logger.error(f"Full response (last 500 chars): ...{response[-500:]}")
                raise

        # Extract personas
        personas = []
        for p_data in parsed.get("personas", []):
            personas.append(CustomerPersona(
                name=p_data.get("name", ""),
                age_range=p_data.get("age_range", ""),
                description=p_data.get("description", ""),
                pain_points=p_data.get("pain_points", []),
                motivations=p_data.get("motivations", []),
                product_usage_context=p_data.get("product_usage_context", ""),
            ))

        # Extract slogans
        slogans = parsed.get("slogans", [])

        # Extract other fields
        market_analysis = parsed.get("market_analysis", "")
        visual_theme_extracted = parsed.get("visual_theme_extracted", visual_analysis[:200])
        category_insights = parsed.get("category_insights", "")

        logger.info(f"Parsed {len(personas)} personas and {len(slogans)} slogans from Gemini")

        output = StrategyAgentOutput(
            personas=personas,
            slogans=slogans,
            market_analysis=market_analysis,
            visual_theme_extracted=visual_theme_extracted,
            category_insights=category_insights,
        )

        return output

    async def critique(
        self, result: Dict[str, Any], brief: Dict[str, Any]
    ) -> CritiqueResult:
        """
        Evaluate strategy output against project brief.

        Args:
            result: Strategy agent output
            brief: Project brief

        Returns:
            Critique result
        """
        output = StrategyAgentOutput(**result)

        issues = []

        # Check persona count
        if len(output.personas) != 3:
            issues.append(f"Expected 3 personas, got {len(output.personas)}")

        # Check slogan count
        if len(output.slogans) != 5:
            issues.append(f"Expected 5 slogans, got {len(output.slogans)}")

        # Check if personas are category-appropriate
        product_category = brief.get("product_category", "")
        if product_category not in str(output.personas):
            issues.append(f"Personas should reference {product_category} category")

        # Check brand tone in slogans
        brand_tone = brief.get("brand_tone", "")
        # Simple check - in production, use sentiment analysis
        if not output.slogans:
            issues.append("No slogans generated")

        if issues:
            return CritiqueResult(
                status="REVISE",
                score=0.5,
                issues=issues,
                revision_instructions=f"Fix the following: {'; '.join(issues)}",
            )

        return CritiqueResult(status="PASS", score=1.0, issues=[])

    async def revise(
        self, result: Dict[str, Any], critique: CritiqueResult
    ) -> Dict[str, Any]:
        """
        Revise strategy based on critique.

        Args:
            result: Original output
            critique: Critique feedback

        Returns:
            Revised output
        """
        logger.info(f"Strategy Agent revising based on: {critique.revision_instructions}")

        # In a real implementation, re-run generation with critique feedback
        # For now, return original result
        return result
