"""Celery application configuration for async agent tasks.

Celery is used for:
- Background agent execution
- Parallel task processing
- Long-running video/image generation
- Task scheduling and retries
"""

import logging

from celery import Celery

from app.config import settings

logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    "ai_agency",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Task execution settings
    task_acks_late=True,  # Acknowledge task after execution
    worker_prefetch_multiplier=1,  # Only fetch one task at a time
    task_time_limit=600,  # 10 minutes max per task
    task_soft_time_limit=540,  # 9 minutes soft limit (warning)
    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    # Task routing
    task_routes={
        "app.tasks.agents.*": {"queue": "agents"},
        "app.tasks.producers.*": {"queue": "producers"},
    },
)


@celery_app.task(name="app.tasks.agents.execute_agent")
def execute_agent_task(agent_id: str, task: dict, project_id: str, with_critique: bool = False):
    """
    Celery task to execute an agent.

    Args:
        agent_id: Agent identifier
        task: Task parameters
        project_id: Project identifier
        with_critique: Whether to run critique loop

    Returns:
        Agent output
    """
    import asyncio

    from app.services.orchestration import orchestrator

    logger.info(f"[Celery Task] Executing agent: {agent_id}")

    # Run async orchestrator in event loop
    result = asyncio.run(
        orchestrator.execute_agent(agent_id, task, project_id, with_critique)
    )

    logger.info(f"[Celery Task] Agent {agent_id} completed")

    return result


@celery_app.task(name="app.tasks.agents.execute_parallel_agents")
def execute_parallel_agents_task(agent_ids: list, tasks: dict, project_id: str):
    """
    Celery task to execute multiple agents in parallel.

    Args:
        agent_ids: List of agent identifiers
        tasks: Task parameters for each agent
        project_id: Project identifier

    Returns:
        Results from all agents
    """
    import asyncio

    from app.services.orchestration import orchestrator

    logger.info(f"[Celery Task] Executing parallel agents: {agent_ids}")

    result = asyncio.run(
        orchestrator.execute_parallel_agents(agent_ids, tasks, project_id)
    )

    logger.info(f"[Celery Task] Parallel execution completed")

    return result


@celery_app.task(name="app.tasks.campaign.execute_workflow")
def execute_campaign_workflow_task(project_id: str, user_selections: dict = None):
    """
    Celery task to execute complete campaign workflow.

    Args:
        project_id: Project identifier
        user_selections: User choices (slogan, image)

    Returns:
        Complete campaign results
    """
    import asyncio

    from app.services.orchestration import orchestrator

    logger.info(f"[Celery Task] Starting campaign workflow: {project_id}")

    result = asyncio.run(
        orchestrator.execute_campaign_workflow(project_id, user_selections)
    )

    logger.info(f"[Celery Task] Campaign workflow completed: {project_id}")

    return result


# Task error handler
@celery_app.task(bind=True, max_retries=3)
def retry_agent_task(self, agent_id: str, task: dict, project_id: str):
    """
    Retry wrapper for agent execution with exponential backoff.

    Args:
        agent_id: Agent identifier
        task: Task parameters
        project_id: Project identifier
    """
    try:
        return execute_agent_task(agent_id, task, project_id)
    except Exception as exc:
        logger.error(f"Agent task failed, retrying: {exc}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
