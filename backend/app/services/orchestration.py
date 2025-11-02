"""Agent Orchestration Service - Coordinates multi-agent workflows.

Handles:
- Task delegation to agents
- Parallel agent execution
- Event-driven triggers
- Context sharing between agents
- Critique loop orchestration
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Callable

from app.celery_app import celery_app
from app.models.brief import ProjectBrief
from app.services.agent_registry import agent_registry
from app.services.redis_client import redis_client

logger = logging.getLogger(__name__)


# Agent execution dependencies
# Key: agent_id, Value: list of agent_ids that must complete first
AGENT_DEPENDENCIES = {
    "strategy": [],  # No dependencies, can start immediately
    "art_director": ["strategy"],  # Needs slogan from Strategy
    "video_producer": ["art_director"],  # Needs hero image from Art Director
    "audio_team": ["strategy"],  # Can start after Strategy (theme detected)
    "web_dev": ["art_director"],  # Needs hero image from Art Director
}


# Event-based triggers
# When event occurs, which agents should be notified
EVENT_TRIGGERS = {
    "slogan_selected": ["art_director"],
    "image_selected": ["video_producer", "web_dev"],
    "theme_detected": ["audio_team"],
    "brief_updated": ["all_agents"],
}


class AgentOrchestrator:
    """
    Orchestrates multi-agent workflows with event-driven coordination.

    Features:
    - Sequential and parallel agent execution
    - Dependency management
    - Event publishing and subscription
    - Critique loop coordination
    - Context sharing via Project Brief
    """

    async def execute_agent(
        self,
        agent_id: str,
        task: Dict[str, Any],
        project_id: str,
        with_critique: bool = False,
        announcement_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        Execute a single agent with optional critique loop.

        Args:
            agent_id: Agent to execute
            task: Task parameters
            project_id: Project identifier
            with_critique: Whether to run critique loop
            announcement_callback: Async function to send announcements to the frontend.

        Returns:
            Agent output
        """
        agent = agent_registry.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent not found: {agent_id}")

        logger.info(f"Executing agent: {agent_id} for project: {project_id}")

        # Update agent status and announce start
        # Note: We set status in Redis as "working" but ADK tools will broadcast "thinking" to frontend
        await redis_client.set_agent_status(agent_id, "working")
        if announcement_callback:
            await announcement_callback(f"🤖 Agent '{agent.agent_id}' is starting its task...", "info")

        try:
            # Get project brief for context
            brief = await redis_client.get_project_brief(project_id)
            if not brief:
                raise ValueError(f"Project brief not found: {project_id}")

            context = {"project_id": project_id, "brief": brief.model_dump()}

            # Execute with or without critique
            if with_critique:
                result = await agent.execute_with_critique(
                    task, context, brief.model_dump()
                )
            else:
                result = await agent.execute(task, context)

            # Store result
            task_id = task.get("task_id", f"{agent_id}_{project_id}")
            await redis_client.store_agent_result(agent_id, task_id, result)

            # Update status and announce completion
            await redis_client.set_agent_status(agent_id, "completed")
            if announcement_callback:
                await announcement_callback(f"✅ Agent '{agent.agent_id}' has completed its task.", "success")

            # Publish completion event
            await redis_client.publish_event(
                "agent_completed",
                {
                    "agent_id": agent_id,
                    "project_id": project_id,
                    "task_id": task_id,
                },
            )

            logger.info(f"Agent {agent_id} completed successfully")

            return result

        except Exception as e:
            logger.error(f"Agent {agent_id} failed: {e}")
            await redis_client.set_agent_status(agent_id, "failed")
            if announcement_callback:
                await announcement_callback(f"❌ Agent '{agent.agent_id}' failed: {e}", "error")
            raise

    async def execute_parallel_agents(
        self,
        agent_ids: List[str],
        tasks: Dict[str, Dict[str, Any]],
        project_id: str,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Execute multiple agents in parallel.

        Args:
            agent_ids: List of agents to execute
            tasks: Task parameters for each agent {agent_id: task}
            project_id: Project identifier

        Returns:
            Results from all agents {agent_id: result}
        """
        logger.info(f"Executing {len(agent_ids)} agents in parallel: {agent_ids}")

        # Create tasks for parallel execution
        agent_tasks = [
            self.execute_agent(agent_id, tasks.get(agent_id, {}), project_id)
            for agent_id in agent_ids
        ]

        # Execute in parallel
        results = await asyncio.gather(*agent_tasks, return_exceptions=True)

        # Map results to agent IDs
        result_dict = {}
        for agent_id, result in zip(agent_ids, results):
            if isinstance(result, Exception):
                logger.error(f"Agent {agent_id} failed: {result}")
                result_dict[agent_id] = {"error": str(result)}
            else:
                result_dict[agent_id] = result

        logger.info(f"Parallel execution completed: {len(result_dict)} results")

        return result_dict

    async def execute_campaign_workflow(
        self, project_id: str, user_selections: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute complete campaign workflow with dependency management.

        Workflow:
        1. Strategy Agent (sequential)
        2. User selects slogan
        3. Art Director Agent (sequential)
        4. User selects image
        5. [Video Producer || Audio Team || Web Dev] (parallel)

        Args:
            project_id: Project identifier
            user_selections: User choices (slogan, image)

        Returns:
            Complete campaign results
        """
        logger.info(f"Starting campaign workflow for project: {project_id}")

        # Get project brief
        brief = await redis_client.get_project_brief(project_id)
        if not brief:
            raise ValueError(f"Project not found: {project_id}")

        results = {}

        # Phase 1: Strategy Agent
        logger.info("Phase 1: Executing Strategy Agent")
        strategy_task = {
            "task_id": f"strategy_{project_id}",
            "sketch_url": brief.initial_sketch_url,
            "product_name": brief.product_name,
            "product_category": brief.product_category,
            "theme": brief.theme,
            "brand_tone": brief.brand_tone,
            "target_market": brief.target_market,
            "key_features": brief.key_features,
        }
        results["strategy"] = await self.execute_agent(
            "strategy", strategy_task, project_id
        )

        # Wait for user to select slogan
        # In production, this would be handled by WebSocket events
        # For now, use from user_selections or default to first slogan
        selected_slogan = (
            user_selections.get("selected_slogan")
            if user_selections
            else results["strategy"]["slogans"][0]
        )

        # Update brief with selected slogan
        await redis_client.update_project_brief(
            project_id, {"selected_slogan": selected_slogan}
        )

        # Publish slogan_selected event
        await redis_client.publish_event(
            "slogan_selected",
            {"project_id": project_id, "slogan": selected_slogan},
        )

        # Phase 2: Art Director Agent
        logger.info("Phase 2: Executing Art Director Agent")
        art_task = {
            "task_id": f"art_{project_id}",
            "slogan": selected_slogan,
            "product_name": brief.product_name,
            "product_category": brief.product_category,
            "theme": brief.theme,
            "brand_tone": brief.brand_tone,
            "key_features": brief.key_features,
        }
        results["art_director"] = await self.execute_agent(
            "art_director", art_task, project_id
        )

        # Wait for user to select image
        selected_image = (
            user_selections.get("selected_image")
            if user_selections
            else results["art_director"]["images"][0]
        )

        # Update brief with selected image
        await redis_client.update_project_brief(
            project_id, {"selected_image": selected_image}
        )

        # Publish image_selected event
        await redis_client.publish_event(
            "image_selected",
            {"project_id": project_id, "image": selected_image},
        )

        # Phase 3: Parallel execution (Video, Audio, Web Dev)
        logger.info("Phase 3: Executing Video, Audio, Web Dev in parallel")

        image_url = selected_image.get("url", "")

        parallel_tasks = {
            "video_producer": {
                "task_id": f"video_{project_id}",
                "image_url": image_url,
                "product_name": brief.product_name,
                "product_category": brief.product_category,
                "theme": brief.theme,
                "key_features": brief.key_features,
            },
            "audio_team": {
                "task_id": f"audio_{project_id}",
                "theme": brief.theme,
                "slogan": selected_slogan,
                "brand_tone": brief.brand_tone,
                "product_name": brief.product_name,
                "product_category": brief.product_category,
            },
            "web_dev": {
                "task_id": f"web_{project_id}",
                "image_url": image_url,
                "slogan": selected_slogan,
                "product_name": brief.product_name,
                "product_category": brief.product_category,
                "theme": brief.theme,
                "brand_tone": brief.brand_tone,
                "key_features": brief.key_features,
            },
        }

        parallel_results = await self.execute_parallel_agents(
            ["video_producer", "audio_team", "web_dev"], parallel_tasks, project_id
        )

        results.update(parallel_results)

        # Update project brief status
        await redis_client.update_project_brief(project_id, {"status": "completed"})

        logger.info(f"Campaign workflow completed for project: {project_id}")

        return results

    async def handle_event_trigger(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """
        Handle event-based agent triggers.

        Args:
            event_type: Type of event
            event_data: Event payload
        """
        triggered_agents = EVENT_TRIGGERS.get(event_type, [])

        if not triggered_agents:
            logger.debug(f"No agents triggered by event: {event_type}")
            return

        if "all_agents" in triggered_agents:
            triggered_agents = agent_registry.list_agents()

        logger.info(
            f"Event '{event_type}' triggered {len(triggered_agents)} agents: {triggered_agents}"
        )

        # In production, this would queue background tasks
        # For now, just log the trigger
        for agent_id in triggered_agents:
            logger.info(f"Agent '{agent_id}' notified of event '{event_type}'")


# Global orchestrator instance
orchestrator = AgentOrchestrator()
