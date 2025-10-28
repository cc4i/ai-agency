"""Critique System - Producer evaluates agent outputs.

The Producer autonomously evaluates agent outputs against the project brief
before presenting them to the user. If quality issues are found, the Producer
requests revisions without user intervention.
"""

import logging
from typing import Any, Dict

from app.models.assets import CritiqueResult
from app.models.brief import ProjectBrief
from app.services.google_ai_client import gemini_pro_client

logger = logging.getLogger(__name__)


class CritiqueSystem:
    """
    Producer's internal critique system for quality control.

    Implements autonomous evaluation of agent outputs:
    1. Analyze output against project brief
    2. Check for theme consistency
    3. Verify key features are included
    4. Assess overall quality
    5. Provide specific revision instructions if needed

    Example from design.md:
    "The 'Tokyo neon' theme is strong, but it doesn't clearly show the 'glowing sole'.
    I'm sending it back to the agent with instructions for a 2-second close-up."
    """

    async def evaluate_strategy_output(
        self, output: Dict[str, Any], brief: ProjectBrief
    ) -> CritiqueResult:
        """
        Evaluate Strategy Agent output.

        Args:
            output: Strategy agent output
            brief: Project brief

        Returns:
            Critique result with pass/revise status
        """
        logger.info("Critiquing Strategy Agent output")

        issues = []

        # Check persona count
        personas = output.get("personas", [])
        if len(personas) != 3:
            issues.append(f"Expected 3 personas, received {len(personas)}")

        # Check slogan count
        slogans = output.get("slogans", [])
        if len(slogans) != 5:
            issues.append(f"Expected 5 slogans, received {len(slogans)}")

        # Check category relevance
        category = brief.product_category
        if not any(category.lower() in str(persona).lower() for persona in personas):
            issues.append(
                f"Personas should be tailored to {category} category consumers"
            )

        if issues:
            return CritiqueResult(
                status="REVISE",
                score=0.6,
                issues=issues,
                revision_instructions=f"Please address: {'; '.join(issues)}",
            )

        return CritiqueResult(
            status="PASS", score=1.0, issues=[], revision_instructions=None
        )

    async def evaluate_art_output(
        self, output: Dict[str, Any], brief: ProjectBrief
    ) -> CritiqueResult:
        """
        Evaluate Art Director output.

        Args:
            output: Art Director output
            brief: Project brief

        Returns:
            Critique result
        """
        logger.info("Critiquing Art Director output")

        issues = []

        # Check image count
        images = output.get("images", [])
        if len(images) != 4:
            issues.append(f"Expected 4 images, received {len(images)}")

        # Verify all images have URLs
        for i, img in enumerate(images):
            if not img.get("url"):
                issues.append(f"Image {i+1} missing URL")

        # Check theme consistency
        theme = brief.theme
        style_guide = output.get("style_guide", "")
        if theme.lower() not in style_guide.lower():
            issues.append(
                f"Style guide should emphasize the '{theme}' theme more prominently"
            )

        if issues:
            return CritiqueResult(
                status="REVISE",
                score=0.7,
                issues=issues,
                revision_instructions=f"Please fix: {'; '.join(issues)}",
            )

        return CritiqueResult(status="PASS", score=1.0, issues=[])

    async def evaluate_video_output(
        self, output: Dict[str, Any], brief: ProjectBrief
    ) -> CritiqueResult:
        """
        Evaluate Video Producer output with detailed analysis.

        This implements the key critique example from design.md:
        "The 'Tokyo neon' theme is strong, but it doesn't clearly show the 'glowing sole'."

        Args:
            output: Video Producer output
            brief: Project brief

        Returns:
            Critique result with specific revision instructions
        """
        logger.info("Critiquing Video Producer output")

        prompt = f"""
        You are an Executive Producer reviewing a video for a {brief.product_category} campaign.

        PROJECT BRIEF:
        - Product: {brief.product_name}
        - Theme: {brief.theme}
        - Brand Tone: {brief.brand_tone}
        - Key Features: {', '.join(brief.key_features)}

        VIDEO OUTPUT:
        - Duration: {output.get('video', {}).get('duration_seconds', 0)} seconds
        - Generation Parameters: {output.get('video', {}).get('generation_params', {})}

        EVALUATION CRITERIA:
        1. Does the video match the "{brief.theme}" theme?
        2. Does it clearly show key features: {', '.join(brief.key_features[:2])}?
        3. Is the {brief.brand_tone} brand tone evident?
        4. Is the duration appropriate (15 seconds)?
        5. Is the quality suitable for social media?

        RESPOND IN THIS FORMAT:
        STATUS: [PASS or REVISE]
        SCORE: [0.0 to 1.0]
        ISSUES: [List any issues found, or "None"]
        REVISION: [If REVISE, provide specific instructions]

        Example REVISE response:
        "The 'Tokyo neon' theme is strong, but it doesn't clearly show the 'glowing sole'.
        I'm sending it back to the agent with instructions for a 2-second close-up of this key feature."
        """

        critique_response = await gemini_pro_client.generate_content(prompt)

        # Parse response (simplified - in production, use structured output)
        if "PASS" in critique_response:
            return CritiqueResult(status="PASS", score=1.0, issues=[])
        else:
            # Extract key feature that needs emphasis
            key_feature = brief.key_features[0] if brief.key_features else "key feature"

            return CritiqueResult(
                status="REVISE",
                score=0.7,
                issues=[
                    f"The '{brief.theme}' theme is present, but doesn't clearly show '{key_feature}'"
                ],
                revision_instructions=f"Add a 2-second close-up clearly showing the '{key_feature}' feature",
            )

    async def evaluate_audio_output(
        self, output: Dict[str, Any], brief: ProjectBrief
    ) -> CritiqueResult:
        """
        Evaluate Audio Team output.

        Args:
            output: Audio Team output
            brief: Project brief

        Returns:
            Critique result
        """
        logger.info("Critiquing Audio Team output")

        issues = []

        # Check jingle exists
        if not output.get("jingle", {}).get("url"):
            issues.append("Jingle URL missing")

        # Check podcast ad exists
        if not output.get("podcast_ad", {}).get("url"):
            issues.append("Podcast ad URL missing")

        # Check transcription exists
        if not output.get("transcription", {}).get("text"):
            issues.append("Transcription text missing")

        # Verify brand tone in suggestion
        suggestion = output.get("proactive_suggestion", "")
        if suggestion and brief.brand_tone.lower() not in suggestion.lower():
            issues.append(
                f"Proactive suggestion should reference {brief.brand_tone} tone"
            )

        if issues:
            return CritiqueResult(
                status="REVISE",
                score=0.6,
                issues=issues,
                revision_instructions=f"Fix: {'; '.join(issues)}",
            )

        return CritiqueResult(status="PASS", score=1.0, issues=[])

    async def evaluate_web_output(
        self, output: Dict[str, Any], brief: ProjectBrief
    ) -> CritiqueResult:
        """
        Evaluate Web Dev output.

        Args:
            output: Web Dev output
            brief: Project brief

        Returns:
            Critique result
        """
        logger.info("Critiquing Web Dev output")

        issues = []

        code = output.get("code", {})

        # Check all code sections exist
        if not code.get("html"):
            issues.append("HTML code missing")
        if not code.get("css"):
            issues.append("CSS code missing")
        if not code.get("javascript"):
            issues.append("JavaScript code missing")

        # Check product name in HTML
        html = code.get("html", "")
        if brief.product_name not in html:
            issues.append(
                f"Landing page should prominently feature '{brief.product_name}'"
            )

        # Check slogan if selected
        if brief.selected_slogan and brief.selected_slogan not in html:
            issues.append(f"Landing page should display slogan '{brief.selected_slogan}'")

        if issues:
            return CritiqueResult(
                status="REVISE",
                score=0.5,
                issues=issues,
                revision_instructions=f"Fix: {'; '.join(issues)}",
            )

        return CritiqueResult(status="PASS", score=1.0, issues=[])

    async def evaluate_with_ai(
        self, agent_type: str, output: Dict[str, Any], brief: ProjectBrief
    ) -> CritiqueResult:
        """
        Generic AI-powered critique using Gemini Pro.

        Args:
            agent_type: Type of agent (strategy, art_director, etc.)
            output: Agent output
            brief: Project brief

        Returns:
            Critique result
        """
        prompt = f"""
        You are an Executive Producer evaluating {agent_type} output for a campaign.

        PROJECT BRIEF:
        {brief.model_dump_json(indent=2)}

        AGENT OUTPUT:
        {str(output)[:1000]}  # Truncate to avoid token limits

        Evaluate the output quality and alignment with the brief.
        Provide a PASS or REVISE status with specific feedback.
        """

        response = await gemini_pro_client.generate_content(prompt)

        # Simple parsing (in production, use structured output)
        if "PASS" in response.upper():
            return CritiqueResult(status="PASS", score=0.8, issues=[])
        else:
            return CritiqueResult(
                status="REVISE",
                score=0.6,
                issues=["Quality improvements needed"],
                revision_instructions="Please improve output quality and brief alignment",
            )


# Global critique system instance
critique_system = CritiqueSystem()
