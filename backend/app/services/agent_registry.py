"""Agent Registry - Central registry for all specialist agents.

Provides singleton access to all agents, supporting both local and remote A2A agents.
Handles agent lookup, registration, and fallback logic.
"""

import logging
from typing import Any, Callable, Dict, List, Optional

from app.agents.art_director import ArtDirectorAgent
from app.agents.audio_team import AudioTeamAgent
from app.agents.base import AgentBase
from app.agents.remote_a2a_adapter import RemoteA2AAgentAdapter
from app.agents.strategy import StrategyAgent
from app.agents.video_producer import VideoProducerAgent
from app.agents.web_dev import WebDevAgent
from app.models.a2a import AgentInfo, RemoteAgentConfig
from app.services.circuit_breaker import circuit_breaker

logger = logging.getLogger(__name__)


class AgentRegistry:
    """
    Central registry for all AI agents (local and remote).

    Provides:
    - Singleton access to agent instances
    - Agent lookup by ID with remote/local resolution
    - Remote agent registration via A2A protocol
    - Automatic fallback to local agents when remote agents fail
    - Circuit breaker integration for fault tolerance
    """

    def __init__(self):
        """Initialize agent registry with all specialist agents."""
        self._local_agents: Dict[str, AgentBase] = {}
        self._remote_agents: Dict[str, RemoteA2AAgentAdapter] = {}
        self._remote_configs: Dict[str, RemoteAgentConfig] = {}
        self._overrides: Dict[str, str] = {}  # local_id -> remote_id
        self._on_progress: Optional[Callable[[str, int, str], None]] = None
        self._initialize_local_agents()

    def _initialize_local_agents(self) -> None:
        """Create and register all local specialist agents."""
        agents = [
            StrategyAgent(),
            ArtDirectorAgent(),
            VideoProducerAgent(),
            AudioTeamAgent(),
            WebDevAgent(),
        ]

        for agent in agents:
            self._local_agents[agent.agent_id] = agent
            logger.info(f"Registered local agent: {agent.agent_id}")

        logger.info(f"Agent registry initialized with {len(self._local_agents)} local agents")

    def set_progress_callback(
        self, callback: Callable[[str, int, str], None]
    ) -> None:
        """
        Set callback for progress updates from remote agents.

        Args:
            callback: Function(task_id, progress, message)
        """
        self._on_progress = callback

    async def register_remote_agent(
        self,
        config: RemoteAgentConfig,
        override_local: Optional[str] = None,
    ) -> AgentInfo:
        """
        Register a remote A2A agent.

        Args:
            config: Remote agent configuration
            override_local: ID of local agent to override (optional)

        Returns:
            AgentInfo for the registered agent

        Raises:
            ValueError: If configuration is invalid
            ConnectionError: If unable to fetch Agent Card
        """
        # Validate API key is provided
        if not config.api_key:
            raise ValueError("API key is required for remote agent registration")

        # Create adapter
        adapter = RemoteA2AAgentAdapter(
            agent_id=f"remote_{hash(config.agent_card_url) % 10000:04d}",
            agent_card_url=config.agent_card_url,
            api_key=config.api_key,
            timeout=config.timeout,
            on_progress=self._on_progress,
        )

        # Fetch Agent Card to validate and get metadata
        try:
            card = await adapter.get_agent_card()
        except Exception as e:
            raise ConnectionError(f"Failed to fetch Agent Card: {e}") from e

        # Use ID from Agent Card
        agent_id = card.id
        adapter.agent_id = agent_id

        # Store adapter and config
        self._remote_agents[agent_id] = adapter
        self._remote_configs[agent_id] = config

        # Handle override
        if override_local and override_local in self._local_agents:
            self._overrides[override_local] = agent_id
            logger.info(f"Remote agent {agent_id} overrides local {override_local}")

        logger.info(f"Registered remote agent: {agent_id} ({card.name})")

        return AgentInfo(
            agent_id=agent_id,
            name=card.name,
            description=card.description,
            provider="remote",
            status="ready",
            skills=[s.model_dump() for s in card.skills],
            is_active=True,
            overrides=override_local,
        )

    async def unregister_remote_agent(self, agent_id: str) -> bool:
        """
        Unregister a remote agent.

        Args:
            agent_id: Agent identifier

        Returns:
            True if agent was unregistered
        """
        if agent_id not in self._remote_agents:
            return False

        # Remove override
        for local_id, remote_id in list(self._overrides.items()):
            if remote_id == agent_id:
                del self._overrides[local_id]

        # Close adapter
        adapter = self._remote_agents.pop(agent_id)
        await adapter.close()
        self._remote_configs.pop(agent_id, None)

        # Reset circuit breaker
        await circuit_breaker.reset(agent_id)

        logger.info(f"Unregistered remote agent: {agent_id}")
        return True

    def get_agent(self, agent_id: str) -> Optional[AgentBase]:
        """
        Get agent by ID, preferring remote over local if configured.

        Args:
            agent_id: Agent identifier

        Returns:
            Agent instance or None if not found
        """
        # Check if local agent is overridden by remote
        if agent_id in self._overrides:
            remote_id = self._overrides[agent_id]
            if remote_id in self._remote_agents:
                return self._remote_agents[remote_id]

        # Check remote agents
        if agent_id in self._remote_agents:
            return self._remote_agents[agent_id]

        # Check local agents
        if agent_id in self._local_agents:
            return self._local_agents[agent_id]

        logger.warning(f"Agent not found: {agent_id}")
        return None

    async def get_agent_with_fallback(self, agent_id: str) -> AgentBase:
        """
        Get agent with automatic fallback to local if remote fails.

        Args:
            agent_id: Agent identifier

        Returns:
            Agent instance (remote or fallback local)

        Raises:
            ValueError: If no agent found
        """
        # Check if local agent is overridden by remote
        remote_id = self._overrides.get(agent_id, agent_id)

        # Check if remote agent exists and circuit is not open
        if remote_id in self._remote_agents:
            config = self._remote_configs.get(remote_id)

            # Check circuit breaker
            if await circuit_breaker.can_execute(remote_id):
                return self._remote_agents[remote_id]
            else:
                # Circuit is open, check fallback
                if config and config.fallback_to_local and agent_id in self._local_agents:
                    logger.info(
                        f"Circuit open for {remote_id}, falling back to local {agent_id}"
                    )
                    return self._local_agents[agent_id]
                else:
                    raise ValueError(
                        f"Remote agent {remote_id} unavailable and no fallback configured"
                    )

        # Check local agents
        if agent_id in self._local_agents:
            return self._local_agents[agent_id]

        raise ValueError(f"Agent not found: {agent_id}")

    def get_local_agent(self, agent_id: str) -> Optional[AgentBase]:
        """
        Get local agent by ID (bypasses remote override).

        Args:
            agent_id: Agent identifier

        Returns:
            Local agent instance or None
        """
        return self._local_agents.get(agent_id)

    def get_remote_agent(self, agent_id: str) -> Optional[RemoteA2AAgentAdapter]:
        """
        Get remote agent by ID.

        Args:
            agent_id: Agent identifier

        Returns:
            Remote agent adapter or None
        """
        return self._remote_agents.get(agent_id)

    def list_agents(self) -> List[str]:
        """
        Get list of all registered agent IDs (both local and remote).

        Returns:
            List of agent IDs
        """
        all_ids = set(self._local_agents.keys()) | set(self._remote_agents.keys())
        return list(all_ids)

    def list_local_agents(self) -> List[str]:
        """Get list of local agent IDs."""
        return list(self._local_agents.keys())

    def list_remote_agents(self) -> List[str]:
        """Get list of remote agent IDs."""
        return list(self._remote_agents.keys())

    def get_agent_info(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get agent metadata.

        Args:
            agent_id: Agent identifier

        Returns:
            Agent info dict or None
        """
        # Check remote agents first
        if agent_id in self._remote_agents:
            adapter = self._remote_agents[agent_id]
            status = circuit_breaker.get_status(agent_id)

            return {
                "agent_id": agent_id,
                "class_name": "RemoteA2AAgentAdapter",
                "provider": "remote",
                "agent_card_url": adapter.agent_card_url,
                "max_revisions": str(adapter.max_revisions),
                "circuit_state": status.get("state", "unknown"),
                "failures": status.get("failures", 0),
            }

        # Check local agents
        agent = self._local_agents.get(agent_id)
        if not agent:
            return None

        # Check if overridden
        overridden_by = None
        for local_id, remote_id in self._overrides.items():
            if local_id == agent_id:
                overridden_by = remote_id
                break

        return {
            "agent_id": agent.agent_id,
            "class_name": agent.__class__.__name__,
            "provider": "local",
            "max_revisions": str(agent.max_revisions),
            "overridden_by": overridden_by,
        }

    async def get_all_agent_info(self) -> List[AgentInfo]:
        """
        Get info for all agents.

        Returns:
            List of AgentInfo
        """
        result = []

        # Local agents
        for agent_id, agent in self._local_agents.items():
            overridden_by = self._overrides.get(agent_id)
            result.append(
                AgentInfo(
                    agent_id=agent_id,
                    name=agent.__class__.__name__.replace("Agent", ""),
                    description=f"Local {agent.__class__.__name__}",
                    provider="local",
                    status="ready",
                    skills=[],
                    is_active=overridden_by is None,
                    overridden_by=overridden_by,
                )
            )

        # Remote agents
        for agent_id, adapter in self._remote_agents.items():
            status = circuit_breaker.get_status(agent_id)
            circuit_state = status.get("state", "closed")

            agent_status = "ready"
            if circuit_state == "open":
                agent_status = "error"
            elif circuit_state == "half_open":
                agent_status = "working"

            # Find which local agent this overrides
            overrides = None
            for local_id, remote_id in self._overrides.items():
                if remote_id == agent_id:
                    overrides = local_id
                    break

            try:
                card = await adapter.get_agent_card()
                result.append(
                    AgentInfo(
                        agent_id=agent_id,
                        name=card.name,
                        description=card.description,
                        provider="remote",
                        status=agent_status,
                        skills=[s.model_dump() for s in card.skills],
                        is_active=True,
                        overrides=overrides,
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to get agent card for {agent_id}: {e}")
                result.append(
                    AgentInfo(
                        agent_id=agent_id,
                        name="Unknown",
                        description="Failed to fetch agent card",
                        provider="remote",
                        status="offline",
                        skills=[],
                        is_active=False,
                        overrides=overrides,
                    )
                )

        return result

    async def health_check_remote_agents(self) -> Dict[str, bool]:
        """
        Check health of all remote agents.

        Returns:
            Dictionary of agent_id -> is_healthy
        """
        results = {}
        for agent_id, adapter in self._remote_agents.items():
            results[agent_id] = await adapter.health_check()
        return results

    async def close_all(self) -> None:
        """Close all remote agent connections."""
        for adapter in self._remote_agents.values():
            await adapter.close()
        self._remote_agents.clear()
        self._remote_configs.clear()
        self._overrides.clear()


# Global agent registry instance
agent_registry = AgentRegistry()
