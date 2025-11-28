"""Agent Management API Router.

Provides endpoints for managing local and remote A2A agents.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.models.a2a import AgentInfo, RemoteAgentConfig
from app.services.agent_registry import agent_registry
from app.services.circuit_breaker import circuit_breaker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["Agents"])


# ============ Request/Response Models ============


class RegisterAgentRequest(BaseModel):
    """Request to register a remote A2A agent."""

    agent_card_url: str
    api_key: str  # Actual API key (will be stored securely)
    override_local: Optional[str] = None  # Local agent ID to override
    fallback_to_local: bool = True
    timeout: Optional[dict] = None


class RegisterAgentResponse(BaseModel):
    """Response from agent registration."""

    success: bool
    agent: Optional[AgentInfo] = None
    error: Optional[str] = None


class AgentListResponse(BaseModel):
    """Response containing list of agents."""

    agents: List[AgentInfo]
    local_count: int
    remote_count: int


class CircuitBreakerStatus(BaseModel):
    """Circuit breaker status for an agent."""

    agent_id: str
    state: str
    failures: int
    failure_threshold: int
    last_failure_time: Optional[float] = None
    recovery_in_seconds: Optional[float] = None


class HealthCheckResponse(BaseModel):
    """Health check response for remote agents."""

    results: dict  # agent_id -> is_healthy


# ============ Endpoints ============


@router.get("", response_model=AgentListResponse)
async def list_agents(
    provider: Optional[str] = Query(None, description="Filter by provider (local/remote)"),
):
    """
    List all registered agents.

    Args:
        provider: Optional filter for 'local' or 'remote' agents

    Returns:
        List of all agents with metadata
    """
    all_agents = await agent_registry.get_all_agent_info()

    if provider:
        all_agents = [a for a in all_agents if a.provider == provider]

    local_count = len([a for a in all_agents if a.provider == "local"])
    remote_count = len([a for a in all_agents if a.provider == "remote"])

    return AgentListResponse(
        agents=all_agents,
        local_count=local_count,
        remote_count=remote_count,
    )


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    """
    Get agent details by ID.

    Args:
        agent_id: Agent identifier

    Returns:
        Agent info or 404 if not found
    """
    info = agent_registry.get_agent_info(agent_id)
    if not info:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    return info


@router.post("/register", response_model=RegisterAgentResponse)
async def register_remote_agent(request: RegisterAgentRequest):
    """
    Register a new remote A2A agent.

    The agent will be validated by fetching its Agent Card.
    If override_local is specified, the remote agent will replace
    the local agent for all requests.

    Args:
        request: Registration request with Agent Card URL and API key reference

    Returns:
        Registration result with agent info or error
    """
    logger.info(f"Registering remote agent from: {request.agent_card_url}")

    try:
        config = RemoteAgentConfig(
            agent_card_url=request.agent_card_url,
            api_key=request.api_key,
            fallback_to_local=request.fallback_to_local,
            timeout=request.timeout or {"connect": 10, "read": 300, "total": 600},
        )

        agent_info = await agent_registry.register_remote_agent(
            config, override_local=request.override_local
        )

        logger.info(f"Successfully registered remote agent: {agent_info.agent_id}")
        return RegisterAgentResponse(success=True, agent=agent_info)

    except ValueError as e:
        logger.warning(f"Registration failed (config error): {e}")
        return RegisterAgentResponse(success=False, error=str(e))

    except ConnectionError as e:
        logger.warning(f"Registration failed (connection error): {e}")
        return RegisterAgentResponse(success=False, error=str(e))

    except Exception as e:
        logger.error(f"Registration failed (unexpected error): {e}", exc_info=True)
        return RegisterAgentResponse(success=False, error=f"Unexpected error: {e}")


@router.delete("/{agent_id}")
async def unregister_agent(agent_id: str):
    """
    Unregister a remote agent.

    This will remove the agent and restore any overridden local agent.

    Args:
        agent_id: Agent identifier

    Returns:
        Success status
    """
    success = await agent_registry.unregister_remote_agent(agent_id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Remote agent not found: {agent_id}",
        )

    logger.info(f"Unregistered remote agent: {agent_id}")
    return {"success": True, "agent_id": agent_id}


@router.get("/{agent_id}/health")
async def check_agent_health(agent_id: str):
    """
    Check health of a specific agent.

    For remote agents, this fetches the Agent Card to verify connectivity.

    Args:
        agent_id: Agent identifier

    Returns:
        Health status
    """
    remote_agent = agent_registry.get_remote_agent(agent_id)
    if remote_agent:
        is_healthy = await remote_agent.health_check()
        return {
            "agent_id": agent_id,
            "provider": "remote",
            "healthy": is_healthy,
        }

    local_agent = agent_registry.get_local_agent(agent_id)
    if local_agent:
        return {
            "agent_id": agent_id,
            "provider": "local",
            "healthy": True,  # Local agents are always healthy
        }

    raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")


@router.post("/health-check-all", response_model=HealthCheckResponse)
async def check_all_remote_agents():
    """
    Check health of all remote agents.

    Returns:
        Dictionary of agent_id -> is_healthy
    """
    results = await agent_registry.health_check_remote_agents()
    return HealthCheckResponse(results=results)


@router.get("/{agent_id}/circuit-breaker", response_model=CircuitBreakerStatus)
async def get_circuit_breaker_status(agent_id: str):
    """
    Get circuit breaker status for a remote agent.

    Args:
        agent_id: Agent identifier

    Returns:
        Circuit breaker status
    """
    remote_agent = agent_registry.get_remote_agent(agent_id)
    if not remote_agent:
        raise HTTPException(
            status_code=404,
            detail=f"Remote agent not found: {agent_id}",
        )

    status = circuit_breaker.get_status(agent_id)
    return CircuitBreakerStatus(**status)


@router.post("/{agent_id}/circuit-breaker/reset")
async def reset_circuit_breaker(agent_id: str):
    """
    Manually reset circuit breaker for a remote agent.

    This allows retrying a previously failing agent.

    Args:
        agent_id: Agent identifier

    Returns:
        Success status
    """
    remote_agent = agent_registry.get_remote_agent(agent_id)
    if not remote_agent:
        raise HTTPException(
            status_code=404,
            detail=f"Remote agent not found: {agent_id}",
        )

    await circuit_breaker.reset(agent_id)
    logger.info(f"Reset circuit breaker for agent: {agent_id}")

    return {"success": True, "agent_id": agent_id}


@router.get("/{agent_id}/skills")
async def get_agent_skills(agent_id: str):
    """
    Get skills declared by a remote agent.

    For remote agents, this returns skills from the Agent Card.
    For local agents, returns an empty list (local agents don't declare skills).

    Args:
        agent_id: Agent identifier

    Returns:
        List of skills
    """
    remote_agent = agent_registry.get_remote_agent(agent_id)
    if remote_agent:
        skills = await remote_agent.get_skills()
        return {"agent_id": agent_id, "skills": skills}

    local_agent = agent_registry.get_local_agent(agent_id)
    if local_agent:
        return {"agent_id": agent_id, "skills": []}

    raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
