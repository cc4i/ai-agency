"""Campaign Planner - Generates 5-phase execution plans.

The Producer presents a chain-of-thought plan before execution,
requiring user approval before tasking agents.
"""

import logging
from typing import Any, Dict, List

from app.models.assets import CampaignPlan, PlanPhase
from app.models.brief import ProjectBrief
from app.services.google_ai_client import gemini_pro_client

logger = logging.getLogger(__name__)


class CampaignPlanner:
    """
    Generates campaign execution plans with chain-of-thought reasoning.

    The Producer analyzes the project brief and creates a detailed 5-phase plan
    that explains which agents will be used and what they will accomplish.
    """

    async def generate_plan(self, brief: ProjectBrief) -> CampaignPlan:
        """
        Generate 5-phase campaign execution plan.

        Args:
            brief: Project brief with product information

        Returns:
            CampaignPlan with phases and description
        """
        logger.info(f"Generating campaign plan for: {brief.product_name}")

        # Create system prompt for planning
        system_prompt = """
        You are an Executive Producer managing a creative AI agency.
        You coordinate specialist agents to execute campaigns.

        Your agents:
        - Strategy Agent [Gemini Pro]: Analyzes sketches, creates personas and slogans
        - Art Director [Imagen]: Generates hero images
        - Video Producer [Veo]: Creates social media videos
        - Audio Team [Lyria]: Composes jingles and podcast ads
        - Web Dev Agent [Gemini Code Assist]: Builds landing pages

        Create a clear, professional 5-phase execution plan that explains:
        1. What each agent will do
        2. What deliverables they will produce
        3. How phases depend on each other
        """

        # Generate plan using Gemini Pro
        prompt = f"""
        Create a campaign execution plan for "{brief.product_name}".

        PRODUCT INFO:
        - Name: {brief.product_name}
        - Category: {brief.product_category}
        - Theme: {brief.theme}
        - Brand Tone: {brief.brand_tone}
        - Target Market: {brief.target_market}
        - Key Features: {', '.join(brief.key_features)}

        Generate a professional plan following this structure:

        "To launch the {brief.product_name}, I've broken the project into 5 phases:

        First, our Strategy Agent [Gemini Pro] will [specific task].
        Then, our Art Director [Imagen] will [specific task].
        After that, our Video Producer [Veo] will [specific task].
        Simultaneously, our Audio Team [Lyria] will [specific task].
        Finally, our Web Dev Agent [Gemini Code Assist] will [specific task].

        This plan is now in your Project Brief. Shall I task the Strategy Agent to begin?"

        Make it conversational and professional, explaining value at each phase.
        """

        plan_description = await gemini_pro_client.generate_content(
            prompt, system_prompt=system_prompt
        )

        # Create structured plan phases
        phases = [
            PlanPhase(
                phase_number=1,
                agent="Strategy Agent [Gemini Pro]",
                task_description=f"Analyze the {brief.product_name} sketch and generate 3 customer personas and 5 campaign slogans tailored to {brief.target_market}",
                dependencies=[],
            ),
            PlanPhase(
                phase_number=2,
                agent="Art Director [Imagen]",
                task_description=f"Create 4 photorealistic hero images showcasing the {brief.theme} theme and {brief.brand_tone} brand tone",
                dependencies=[1],  # Depends on Strategy completing
            ),
            PlanPhase(
                phase_number=3,
                agent="Video Producer [Veo]",
                task_description=f"Generate a 15-second social media video highlighting key features: {', '.join(brief.key_features[:2])}",
                dependencies=[2],  # Depends on Art Director completing
            ),
            PlanPhase(
                phase_number=4,
                agent="Audio Team [Lyria + Chirp]",
                task_description=f"Compose a {brief.brand_tone} jingle and create a podcast ad with professional TTS voiceover",
                dependencies=[1],  # Can start after Strategy
            ),
            PlanPhase(
                phase_number=5,
                agent="Web Dev Agent [Gemini Code Assist]",
                task_description=f"Build a responsive landing page with countdown timer, email signup, and {brief.theme} styling",
                dependencies=[2],  # Depends on Art Director for hero image
            ),
        ]

        plan = CampaignPlan(
            phases=phases,
            approval_status="pending",
            description=plan_description or self._get_default_plan_description(brief),
        )

        logger.info(f"Campaign plan generated with {len(phases)} phases")

        return plan

    def _get_default_plan_description(self, brief: ProjectBrief) -> str:
        """
        Generate default plan description if AI fails.

        Args:
            brief: Project brief

        Returns:
            Default plan description
        """
        return f"""
        To launch the {brief.product_name}, I've broken the project into 5 phases:

        First, our Strategy Agent [Gemini Pro] will analyze the initial sketch and generate 3 customer personas and 5 campaign slogans specifically tailored to {brief.target_market}.

        Then, our Art Director [Imagen] will create 4 photorealistic hero images that showcase the {brief.theme} theme with a {brief.brand_tone} feel.

        After that, our Video Producer [Veo] will generate a 15-second social media video that highlights the key features: {', '.join(brief.key_features[:2])}.

        Simultaneously, our Audio Team [Lyria] will compose an {brief.brand_tone} jingle and create a podcast ad with professional TTS voiceover.

        Finally, our Web Dev Agent [Gemini Code Assist] will build a responsive "Coming Soon" landing page with countdown timer, email signup, and {brief.theme} styling.

        This plan is now in your Project Brief. Shall I task the Strategy Agent to begin?
        """

    def format_plan_for_display(self, plan: CampaignPlan) -> str:
        """
        Format plan for user-friendly display.

        Args:
            plan: Campaign plan

        Returns:
            Formatted plan text
        """
        lines = [plan.description, "", "CAMPAIGN PHASES:", ""]

        for phase in plan.phases:
            lines.append(f"Phase {phase.phase_number}: {phase.agent}")
            lines.append(f"  → {phase.task_description}")
            if phase.dependencies:
                dep_str = ", ".join([f"Phase {d}" for d in phase.dependencies])
                lines.append(f"  ⚠ Depends on: {dep_str}")
            lines.append("")

        return "\n".join(lines)
