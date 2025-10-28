"""Executive Producer - Main orchestrator and user interface.

The Producer is the primary interface between the user and the AI agency.
It manages:
- Campaign planning and user approval
- Task delegation to specialist agents
- Agent status monitoring
- Internal critique and revision loops
- Conversation with user via Gemini Live
- Project Brief updates
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from app.models.brief import ConversationMessage, ProjectBrief
from app.producer.critique import critique_system
from app.producer.planner import CampaignPlanner
from app.services.agent_registry import agent_registry
from app.services.google_ai_client import gemini_pro_client
from app.services.orchestration import orchestrator
from app.services.redis_client import redis_client

logger = logging.getLogger(__name__)


class ExecutiveProducer:
    """
    Executive Producer - Manages campaign execution and user communication.

    Personality traits (from design.md):
    - Professional and collaborative
    - Explains reasoning and agent roles
    - Announces actions before performing them
    - First-person voice ("I've tasked...", "I'm analyzing...")
    """

    def __init__(self, session_id: str, project_id: str):
        """
        Initialize Executive Producer.

        Args:
            session_id: User session identifier
            project_id: Project identifier
        """
        self.session_id = session_id
        self.project_id = project_id
        self.planner = CampaignPlanner()
        self.conversation_history: list[ConversationMessage] = []

    async def initialize(self) -> ProjectBrief:
        """
        Initialize Producer with project brief.

        Returns:
            Project brief
        """
        brief = await redis_client.get_project_brief(self.project_id)
        if not brief:
            raise ValueError(f"Project not found: {self.project_id}")

        logger.info(
            f"Executive Producer initialized for {brief.product_name} ({self.project_id})"
        )

        return brief

    # Planning Phase

    async def create_campaign_plan(self) -> str:
        """
        Generate campaign execution plan and present to user.

        Returns:
            Plan description to speak to user
        """
        logger.info("Creating campaign plan")

        brief = await self.initialize()

        # Generate plan
        plan = await self.planner.generate_plan(brief)

        # Update brief with plan
        await redis_client.update_project_brief(
            self.project_id, {"campaign_plan": plan.model_dump(), "plan_approved": False}
        )

        # Return plan description for the Producer to speak
        return plan.description

    async def handle_plan_approval(self, approved: bool) -> str:
        """
        Handle user's plan approval or rejection.

        Args:
            approved: Whether user approved the plan

        Returns:
            Response message
        """
        if approved:
            await redis_client.update_project_brief(
                self.project_id, {"plan_approved": True, "status": "executing"}
            )
            return "Great! I'm tasking the Strategy Agent to begin."
        else:
            return "I understand. Would you like me to revise the plan, or would you prefer to provide specific guidance?"

    # Task Delegation

    async def delegate_to_agent(
        self, agent_id: str, task: Dict[str, Any], announce: bool = True
    ) -> str:
        """
        Delegate task to a specialist agent.

        Args:
            agent_id: Agent to delegate to
            task: Task parameters
            announce: Whether to announce the delegation

        Returns:
            Announcement message to speak
        """
        agent = agent_registry.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent not found: {agent_id}")

        logger.info(f"Delegating to {agent_id}")

        # Get agent display name
        agent_names = {
            "strategy": "Strategy Agent [Gemini Pro]",
            "art_director": "Art Director [Imagen]",
            "video_producer": "Video Producer [Veo]",
            "audio_team": "Audio Team [Lyria]",
            "web_dev": "Web Dev Agent [Gemini Code Assist]",
        }
        agent_name = agent_names.get(agent_id, agent_id)

        announcement = f"Okay, I've tasked our {agent_name} with {task.get('description', 'the next phase')}."

        if announce:
            logger.info(f"Announcement: {announcement}")

        # Execute agent in background (async)
        # In production, this would be a Celery task
        asyncio.create_task(
            self._execute_and_monitor_agent(agent_id, task)
        )

        return announcement

    async def _execute_and_monitor_agent(
        self, agent_id: str, task: Dict[str, Any]
    ) -> None:
        """
        Execute agent and monitor progress.

        Args:
            agent_id: Agent identifier
            task: Task parameters
        """
        try:
            # Execute agent
            result = await orchestrator.execute_agent(
                agent_id, task, self.project_id, with_critique=False
            )

            # Run critique for specific agents
            if agent_id in ["video_producer", "strategy", "art_director"]:
                await self._critique_and_revise_if_needed(agent_id, result)

            # Announce completion
            await self._announce_completion(agent_id, result)

        except Exception as e:
            logger.error(f"Agent {agent_id} failed: {e}")
            # In production, notify user of failure

    async def _critique_and_revise_if_needed(
        self, agent_id: str, result: Dict[str, Any], max_revisions: int = 2
    ) -> Dict[str, Any]:
        """
        Run internal critique loop and request revisions if needed.

        Args:
            agent_id: Agent identifier
            result: Agent output
            max_revisions: Maximum revisions allowed

        Returns:
            Final result after critique/revision
        """
        brief = await redis_client.get_project_brief(self.project_id)
        if not brief:
            return result

        revision_count = 0
        current_result = result

        while revision_count < max_revisions:
            # Evaluate output
            if agent_id == "strategy":
                critique = await critique_system.evaluate_strategy_output(
                    current_result, brief
                )
            elif agent_id == "art_director":
                critique = await critique_system.evaluate_art_output(current_result, brief)
            elif agent_id == "video_producer":
                critique = await critique_system.evaluate_video_output(
                    current_result, brief
                )
            elif agent_id == "audio_team":
                critique = await critique_system.evaluate_audio_output(
                    current_result, brief
                )
            elif agent_id == "web_dev":
                critique = await critique_system.evaluate_web_output(current_result, brief)
            else:
                break  # No critique for this agent

            if critique.status == "PASS":
                logger.info(f"Critique passed for {agent_id}")
                break

            # Need revision
            revision_count += 1
            logger.info(
                f"Critique failed for {agent_id}, requesting revision {revision_count}"
            )

            # Announce revision to user (internal monologue)
            revision_announcement = f"Hmm, I'm analyzing it against our brief. {critique.issues[0] if critique.issues else 'Quality needs improvement'}. I'm sending it back to the agent with instructions for {critique.revision_instructions}."
            logger.info(f"Revision note: {revision_announcement}")

            # Request revision from agent
            agent = agent_registry.get_agent(agent_id)
            if agent:
                current_result = await agent.revise(current_result, critique)

        return current_result

    async def _announce_completion(
        self, agent_id: str, result: Dict[str, Any]
    ) -> str:
        """
        Announce agent completion to user.

        Args:
            agent_id: Agent identifier
            result: Agent output

        Returns:
            Announcement message
        """
        announcements = {
            "strategy": "Our Strategy Agent has generated three key customer personas and five potential slogans. They are on your screen now.",
            "art_director": "Our Art Director has created four stunning hero images. Take a look and let me know which one resonates with you.",
            "video_producer": "The Video Producer has completed the social media clip. The video is ready for your review.",
            "audio_team": "Our Audio Team has delivered the jingle, podcast ad, and transcription. All audio assets are ready.",
            "web_dev": "The Web Dev Agent has built the landing page. You can preview it on the right side of your screen.",
        }

        announcement = announcements.get(
            agent_id,
            f"The {agent_id} has completed their work. Results are ready for review.",
        )

        logger.info(f"Completion: {announcement}")

        # In production, send this via WebSocket to trigger TTS
        return announcement

    # User Input Handling

    async def handle_user_selection(
        self, selection_type: str, selection_value: Any
    ) -> str:
        """
        Handle user's selection (slogan, image, etc.).

        Args:
            selection_type: Type of selection (slogan, image)
            selection_value: Selected value

        Returns:
            Response message
        """
        logger.info(f"User selected {selection_type}: {selection_value}")

        brief = await redis_client.get_project_brief(self.project_id)
        if not brief:
            return "Error: Project brief not found."

        if selection_type == "slogan":
            # Update brief with selected slogan
            await redis_client.update_project_brief(
                self.project_id, {"selected_slogan": selection_value}
            )

            # Announce and delegate to Art Director
            response = f"Excellent choice. Now, I'm sending this slogan to our Art Director Agent [Imagen] to generate the hero image."

            # Delegate to Art Director
            art_task = {
                "description": "generating hero images",
                "slogan": selection_value,
                "product_name": brief.product_name,
                "product_category": brief.product_category,
                "theme": brief.theme,
                "brand_tone": brief.brand_tone,
                "key_features": brief.key_features,
            }
            await self.delegate_to_agent("art_director", art_task, announce=False)

            return response

        elif selection_type == "image":
            # Update brief with selected image
            await redis_client.update_project_brief(
                self.project_id, {"selected_image": selection_value}
            )

            # Announce proactive collaboration
            response = "Got it. I've added that to the project brief. Our Video Producer Agent and Web Dev Agent have already been notified and are using that image as their style reference."

            # Delegate to Video, Audio, Web Dev in parallel
            image_url = selection_value.get("url", "")

            video_task = {
                "description": "creating social media video",
                "image_url": image_url,
                "product_name": brief.product_name,
                "product_category": brief.product_category,
                "theme": brief.theme,
                "key_features": brief.key_features,
            }

            audio_task = {
                "description": "composing jingle and podcast ad",
                "theme": brief.theme,
                "slogan": brief.selected_slogan,
                "brand_tone": brief.brand_tone,
                "product_name": brief.product_name,
                "product_category": brief.product_category,
            }

            web_task = {
                "description": "building landing page",
                "image_url": image_url,
                "slogan": brief.selected_slogan,
                "product_name": brief.product_name,
                "product_category": brief.product_category,
                "theme": brief.theme,
                "brand_tone": brief.brand_tone,
                "key_features": brief.key_features,
            }

            # Execute in parallel
            asyncio.create_task(self._execute_and_monitor_agent("video_producer", video_task))
            asyncio.create_task(self._execute_and_monitor_agent("audio_team", audio_task))
            asyncio.create_task(self._execute_and_monitor_agent("web_dev", web_task))

            return response

        return "Thank you for your input."

    # Conversation Management

    async def add_to_conversation(
        self, role: str, text: str
    ) -> None:
        """
        Add message to conversation history.

        Args:
            role: Message role (user or assistant)
            text: Message text
        """
        from datetime import datetime

        message = ConversationMessage(
            role=role, text=text, timestamp=datetime.utcnow()
        )

        await redis_client.add_conversation_message(self.session_id, message)
        self.conversation_history.append(message)

    # Campaign Completion

    async def announce_campaign_completion(self) -> str:
        """
        Announce campaign completion to user.

        Returns:
            Completion message
        """
        brief = await redis_client.get_project_brief(self.project_id)
        if not brief:
            return "Campaign status unavailable."

        # Update status
        await redis_client.update_project_brief(self.project_id, {"status": "completed"})

        completion_message = f"""
        And with that, our campaign is complete. We've gone from a sketch to a full product launch in just a few minutes.

        All assets are available in your project brief:
        - Customer personas and marketing slogans
        - Hero images
        - Social media video
        - Jingle and podcast ad
        - Landing page code

        Everything is ready for {brief.product_name}. What would you like to do next?
        """

        return completion_message.strip()
