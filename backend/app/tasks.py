"""Celery tasks for running AI agents in the background."""

import asyncio
import logging
import json
from typing import Any, Dict

from app.celery_app import celery
from app.services.agent_registry import agent_registry
from app.services.redis_client import redis_client

logger = logging.getLogger(__name__)

@celery.task(name="app.tasks.run_agent_task")
def run_agent_task(
    agent_id: str,
    task: Dict[str, Any],
    project_id: str,
    with_critique: bool = False,
    call_id: str = "",
    session_id: str = "",
) -> None:
    """
    Celery task to execute a single agent asynchronously.

    Args:
        agent_id: The ID of the agent to execute.
        task: The task parameters for the agent.
        project_id: The ID of the project context.
        with_critique: Whether to run a critique loop on the agent's output.
        call_id: The ID of the tool call from Gemini.
        session_id: The ID of the Gemini Live session.

    Returns:
        None. The result is published to Redis.
    """
    logger.info(f"[Celery Task] Worker picked up task for agent: {agent_id}")

    if not call_id or not session_id:
        logger.error(f"[Celery Task] Missing call_id or session_id for agent {agent_id}. Cannot report result.")
        return

    # Since agent execution is async, we need to run it in an event loop.
    asyncio.run(
        _run_agent_async(
            agent_id, task, project_id, with_critique, call_id, session_id
        )
    )

async def _run_agent_async(
    agent_id: str,
    task: Dict[str, Any],
    project_id: str,
    with_critique: bool,
    call_id: str,
    session_id: str,
) -> None:
    """
    The async portion of the agent execution logic.
    """
    agent = agent_registry.get_agent(agent_id)
    if not agent:
        logger.error(f"[Celery Task] Agent '{agent_id}' not found in registry.")
        # Publish failure to Redis
        await redis_client.publish_event(
            f"agent_results:{session_id}",
            json.dumps({
                "agent_id": agent_id,
                "call_id": call_id,
                "status": "failed",
                "result": {"error": f"Agent {agent_id} not found."},
            }),
        )
        return

    logger.info(f"[Celery Task] Executing agent: {agent_id} for project: {project_id}")

    # Publish "working" status to Redis
    await redis_client.publish_event(
        f"agent_results:{session_id}",
        json.dumps({
            "agent_id": agent_id,
            "call_id": call_id,
            "status": "working",
            "message": f"Agent {agent.name} is starting its task...",
        }),
    )

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

        # Publish completion event to Redis
        await redis_client.publish_event(
            f"agent_results:{session_id}",
            json.dumps({
                "agent_id": agent_id,
                "call_id": call_id,
                "status": "completed",
                "result": result,
            }),
        )

        logger.info(f"[Celery Task] Agent {agent_id} completed successfully.")

    except Exception as e:
        logger.error(f"[Celery Task] Agent {agent_id} failed: {e}")
        # Publish failure event to Redis
        await redis_client.publish_event(
            f"agent_results:{session_id}",
            json.dumps({
                "agent_id": agent_id,
                "call_id": call_id,
                "status": "failed",
                "result": {"error": str(e)},
            }),
        )
        raise
