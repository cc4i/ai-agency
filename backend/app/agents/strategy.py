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

        prompt = f"""
        You are a marketing strategist creating a campaign for a {product_category} product.

        PRODUCT INFORMATION:
        - Name: {product_name}
        - Category: {product_category}
        - Theme: {theme}
        - Brand Tone: {brand_tone}
        - Target Market: {target_market}
        - Key Features: {', '.join(key_features)}

        VISUAL ANALYSIS:
        {visual_analysis}

        PERSONA GUIDELINES FOR {product_category.upper()}:
        {persona_guidelines}

        YOUR TASK:
        Generate EXACTLY 3 customer personas and EXACTLY 5 slogans.

        FORMAT YOUR RESPONSE AS JSON:
        {{
            "personas": [
                {{
                    "name": "Persona name (e.g., 'Tech-Savvy Runner')",
                    "age_range": "Age range (e.g., '25-35')",
                    "description": "Brief persona description",
                    "pain_points": ["pain point 1", "pain point 2", "pain point 3"],
                    "motivations": ["motivation 1", "motivation 2", "motivation 3"],
                    "product_usage_context": "How and when they would use this {product_category}"
                }},
                // ... exactly 3 personas total
            ],
            "slogans": [
                "Slogan 1 - catchy, {brand_tone} tone, 3-5 words",
                "Slogan 2 - catchy, {brand_tone} tone, 3-5 words",
                "Slogan 3 - catchy, {brand_tone} tone, 3-5 words",
                "Slogan 4 - catchy, {brand_tone} tone, 3-5 words",
                "Slogan 5 - catchy, {brand_tone} tone, 3-5 words"
            ],
            "market_analysis": "Brief market analysis for {product_category} category (2-3 paragraphs)",
            "visual_theme_extracted": "Visual theme summary from the sketch",
            "category_insights": "Key insights about the {product_category} market and trends"
        }}

        IMPORTANT:
        - Personas must be specific to {product_category} buyers
        - Slogans must match the {brand_tone} brand tone
        - Include category-specific behaviors and needs
        - Make personas diverse and realistic
        """

        response = await gemini_pro_client.generate_content(prompt)

        # Parse JSON response (in real implementation)
        # For now, create mock structured output
        output = StrategyAgentOutput(
            personas=[
                CustomerPersona(
                    name=f"Persona 1 for {product_name}",
                    age_range="25-35",
                    description=f"Early adopter interested in {product_category}",
                    pain_points=[
                        "Needs innovative solutions",
                        "Values quality and design",
                        "Seeks authentic brands",
                    ],
                    motivations=[
                        "Stay ahead of trends",
                        "Express personal style",
                        "Improve daily life",
                    ],
                    product_usage_context=f"Would use {product_name} in {theme} settings",
                ),
                CustomerPersona(
                    name=f"Persona 2 for {product_name}",
                    age_range="35-50",
                    description=f"Professional seeking premium {product_category}",
                    pain_points=[
                        "Limited time for research",
                        "Wants reliable performance",
                        "Values brand reputation",
                    ],
                    motivations=[
                        "Quality investment",
                        "Status and recognition",
                        "Functional excellence",
                    ],
                    product_usage_context=f"Integrates {product_name} into professional lifestyle",
                ),
                CustomerPersona(
                    name=f"Persona 3 for {product_name}",
                    age_range="18-28",
                    description=f"Trend-conscious {product_category} enthusiast",
                    pain_points=[
                        "Budget constraints",
                        "Wants social validation",
                        "Seeks unique experiences",
                    ],
                    motivations=[
                        "Social media presence",
                        "Personal expression",
                        "Community belonging",
                    ],
                    product_usage_context=f"Uses {product_name} for social and recreational activities",
                ),
            ],
            slogans=[
                f"{product_name}: {theme} Redefined",
                f"Experience the Future of {product_category.title()}",
                f"Where {theme.title()} Meets Innovation",
                f"Elevate Your {product_category.title()} Game",
                f"The {brand_tone.title()} Choice for Modern Living",
            ],
            market_analysis=f"The {product_category} market is experiencing significant growth driven by consumer demand for innovation and quality. {product_name} is positioned in the {theme} segment, appealing to {target_market}. Key differentiators include {', '.join(key_features[:2])}.",
            visual_theme_extracted=visual_analysis[:200],
            category_insights=f"The {product_category} category shows strong trends toward {theme} aesthetics and {brand_tone} brand positioning. Consumer preferences favor products that deliver on {', '.join(key_features[:2])}.",
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
