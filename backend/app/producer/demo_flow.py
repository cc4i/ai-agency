"""Aura Smart Sneaker Demo Flow - Complete campaign walkthrough.

Implements the complete "Aura Smart Sneaker" demo flow from design.md:
1. Welcome & Handoff
2. Planning Phase
3. Strategy Agent Execution
4. Slogan Selection
5. Art Director Execution
6. Image Selection
7. Parallel Agent Execution (Video, Audio, Web)
8. Campaign Completion
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from app.models.brief import ProjectBrief
from app.producer.executive_producer import ExecutiveProducer
from app.services.brief_sync import brief_sync_manager
from app.services.conversation_manager import ConversationManager, ConversationState
from app.services.redis_client import redis_client

logger = logging.getLogger(__name__)


class AuraDemoFlow:
    """
    Orchestrates the complete Aura Smart Sneaker demo flow.

    This implements the user flow from design.md with all phases:
    - Phase 1: Handoff & Planning
    - Phase 2: Agency Hub (Strategy → Art → Final Production)
    - Phase 3: Launch Party (Completion)
    """

    def __init__(self, session_id: str, project_id: str):
        """
        Initialize demo flow.

        Args:
            session_id: Session identifier
            project_id: Project identifier
        """
        self.session_id = session_id
        self.project_id = project_id
        self.producer = ExecutiveProducer(session_id, project_id)
        self.conversation = ConversationManager(session_id, project_id)

    async def run_demo(
        self, user_selections: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Run complete demo flow.

        Args:
            user_selections: Optional pre-selected choices (for automated demo)

        Returns:
            Final campaign results
        """
        logger.info("=" * 60)
        logger.info("Starting Aura Smart Sneaker Demo Flow")
        logger.info("=" * 60)

        # Initialize
        await self.conversation.initialize()
        brief = await self.producer.initialize()

        results = {}

        try:
            # Phase 1: Welcome & Handoff
            await self._phase_welcome(brief)

            # Phase 2: Agency Hub - Strategy
            results["strategy"] = await self._phase_strategy(brief)

            # User selects slogan
            selected_slogan = self._get_user_selection(
                user_selections, "slogan", results["strategy"]["slogans"][2]
            )

            # Phase 2: Agency Hub - Art Director
            results["art"] = await self._phase_art_director(brief, selected_slogan)

            # User selects image
            selected_image = self._get_user_selection(
                user_selections, "image", results["art"]["images"][1]
            )

            # Phase 2: Agency Hub - Final Production (Parallel)
            parallel_results = await self._phase_final_production(
                brief, selected_slogan, selected_image
            )
            results.update(parallel_results)

            # Phase 3: Launch Party
            await self._phase_completion(brief)

            logger.info("=" * 60)
            logger.info("Aura Demo Flow Complete!")
            logger.info("=" * 60)

            return results

        except Exception as e:
            logger.error(f"Demo flow error: {e}")
            raise

    def _get_user_selection(
        self, user_selections: Optional[Dict[str, Any]], key: str, default: Any
    ) -> Any:
        """
        Get user selection or use default.

        Args:
            user_selections: User selections dict
            key: Selection key
            default: Default value

        Returns:
            Selected value
        """
        if user_selections and key in user_selections:
            return user_selections[key]
        return default

    async def _phase_welcome(self, brief: ProjectBrief) -> None:
        """
        Phase 1: Welcome & Handoff.

        Producer introduces itself and the project.
        """
        logger.info("PHASE: Welcome & Handoff")

        self.conversation.set_state(ConversationState.WELCOME)

        # Welcome message
        welcome_message = f"""
        Welcome. I'm your Executive Producer. Our first project is the '{brief.product_name}' launch.
        I've pulled up the initial sketch.
        """

        await self.conversation.add_message("assistant", welcome_message.strip())
        await brief_sync_manager.sync_producer_announcement(
            self.project_id, welcome_message.strip()
        )

        # Brief introduction message
        intro_message = f"""
        To start, I need to build out the core marketing strategy for this {brief.product_category} campaign.
        Shall I proceed?
        """

        await self.conversation.add_message("assistant", intro_message.strip())

        # Simulate user approval
        await asyncio.sleep(1)
        await self.conversation.add_message("user", "Yes, go ahead.")

        # Generate and present plan
        self.conversation.set_state(ConversationState.PLANNING)
        plan_description = await self.producer.create_campaign_plan()

        await self.conversation.add_message("assistant", plan_description)
        await brief_sync_manager.sync_producer_announcement(
            self.project_id, plan_description
        )

        # Simulate user approval
        await asyncio.sleep(1)
        self.conversation.set_state(ConversationState.PLAN_APPROVAL)
        await self.conversation.add_message("user", "Yes, task the Strategy Agent.")

        approval_response = await self.producer.handle_plan_approval(True)
        await self.conversation.add_message("assistant", approval_response)

    async def _phase_strategy(self, brief: ProjectBrief) -> Dict[str, Any]:
        """
        Execute Strategy Agent phase.

        Returns:
            Strategy agent output
        """
        logger.info("PHASE: Strategy Agent Execution")

        self.conversation.set_state(ConversationState.STRATEGY_REVIEW)

        # Announce task delegation
        announcement = f"Okay, I've tasked our Strategy Agent [Gemini Pro] with analyzing the {brief.product_name} sketch."
        await self.conversation.add_message("assistant", announcement)
        await brief_sync_manager.sync_agent_status(
            self.project_id, "strategy", "thinking"
        )

        # Execute Strategy Agent
        strategy_task = {
            "description": "analyzing sketch and generating personas/slogans",
            "task_id": f"strategy_{self.project_id}",
            "sketch_url": brief.initial_sketch_url,
            "product_name": brief.product_name,
            "product_category": brief.product_category,
            "theme": brief.theme,
            "brand_tone": brief.brand_tone,
            "target_market": brief.target_market,
            "key_features": brief.key_features,
        }

        from app.services.orchestration import orchestrator

        result = await orchestrator.execute_agent(
            "strategy", strategy_task, self.project_id
        )

        # Announce completion
        completion = "It's generated three key customer personas and five potential slogans. They are on your screen now."
        await self.conversation.add_message("assistant", completion)
        await brief_sync_manager.sync_asset_added(self.project_id, "strategy", result)

        self.conversation.set_state(ConversationState.SLOGAN_SELECTION)

        return result

    async def _phase_art_director(
        self, brief: ProjectBrief, selected_slogan: str
    ) -> Dict[str, Any]:
        """
        Execute Art Director phase.

        Args:
            brief: Project brief
            selected_slogan: User-selected slogan

        Returns:
            Art Director output
        """
        logger.info(f"PHASE: Art Director Execution (slogan: {selected_slogan})")

        # Update brief
        await brief_sync_manager.update_and_sync(
            self.project_id, {"selected_slogan": selected_slogan}
        )

        # User selection message
        await self.conversation.add_message("user", f"I like '{selected_slogan}'")

        # Producer response
        response = await self.producer.handle_user_selection("slogan", selected_slogan)
        await self.conversation.add_message("assistant", response)

        self.conversation.set_state(ConversationState.ART_REVIEW)

        await brief_sync_manager.sync_agent_status(
            self.project_id, "art_director", "thinking"
        )

        # Execute Art Director
        art_task = {
            "description": "generating hero images",
            "task_id": f"art_{self.project_id}",
            "slogan": selected_slogan,
            "product_name": brief.product_name,
            "product_category": brief.product_category,
            "theme": brief.theme,
            "brand_tone": brief.brand_tone,
            "key_features": brief.key_features,
            "reference_images": [img.model_dump() for img in brief.reference_images],
        }

        from app.services.orchestration import orchestrator

        result = await orchestrator.execute_agent(
            "art_director", art_task, self.project_id
        )

        # Announce completion
        completion = "Our Art Director has created four stunning hero images. Take a look and let me know which one resonates with you."
        await self.conversation.add_message("assistant", completion)
        await brief_sync_manager.sync_asset_added(self.project_id, "art_director", result)

        self.conversation.set_state(ConversationState.IMAGE_SELECTION)

        return result

    async def _phase_final_production(
        self, brief: ProjectBrief, selected_slogan: str, selected_image: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute final production phase (Video, Audio, Web in parallel).

        Args:
            brief: Project brief
            selected_slogan: Selected slogan
            selected_image: Selected image

        Returns:
            Results from all three agents
        """
        logger.info("PHASE: Final Production (Video + Audio + Web parallel)")

        # Update brief
        await brief_sync_manager.update_and_sync(
            self.project_id, {"selected_image": selected_image}
        )

        # User selection
        await self.conversation.add_message(
            "user", "The second image is perfect."
        )

        # Producer response (proactive collaboration announcement)
        response = await self.producer.handle_user_selection("image", selected_image)
        await self.conversation.add_message("assistant", response)

        self.conversation.set_state(ConversationState.FINAL_PRODUCTION)

        # Mark agents as working
        for agent_id in ["video_producer", "audio_team", "web_dev"]:
            await brief_sync_manager.sync_agent_status(
                self.project_id, agent_id, "thinking"
            )

        # Execute in parallel
        from app.services.orchestration import orchestrator

        image_url = selected_image.get("url", "")

        tasks = {
            "video_producer": {
                "description": "creating social media video",
                "task_id": f"video_{self.project_id}",
                "image_url": image_url,
                "product_name": brief.product_name,
                "product_category": brief.product_category,
                "theme": brief.theme,
                "key_features": brief.key_features,
            },
            "audio_team": {
                "description": "composing jingle and podcast ad",
                "task_id": f"audio_{self.project_id}",
                "theme": brief.theme,
                "slogan": selected_slogan,
                "brand_tone": brief.brand_tone,
                "product_name": brief.product_name,
                "product_category": brief.product_category,
            },
            "web_dev": {
                "description": "building landing page",
                "task_id": f"web_{self.project_id}",
                "image_url": image_url,
                "slogan": selected_slogan,
                "product_name": brief.product_name,
                "product_category": brief.product_category,
                "theme": brief.theme,
                "brand_tone": brief.brand_tone,
                "key_features": brief.key_features,
            },
        }

        results = await orchestrator.execute_parallel_agents(
            ["video_producer", "audio_team", "web_dev"], tasks, self.project_id
        )

        # Announce completions
        for agent_id, result in results.items():
            if "error" not in result:
                await brief_sync_manager.sync_asset_added(
                    self.project_id, agent_id, result
                )

        completion_msg = "All final assets have been completed. Video, audio, and web page are ready for review."
        await self.conversation.add_message("assistant", completion_msg)

        return results

    async def _phase_completion(self, brief: ProjectBrief) -> None:
        """
        Phase 3: Launch Party - Campaign completion.

        Args:
            brief: Project brief
        """
        logger.info("PHASE: Launch Party (Completion)")

        self.conversation.set_state(ConversationState.COMPLETION)

        # Final announcement
        completion = await self.producer.announce_campaign_completion()
        await self.conversation.add_message("assistant", completion)
        await brief_sync_manager.sync_producer_announcement(
            self.project_id, completion, "success"
        )
