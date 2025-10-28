"""Agent Registry - Central registry for all specialist agents.

Provides singleton access to all agents and agent management utilities.
"""

import logging
from typing import Dict, Optional

from app.agents.art_director import ArtDirectorAgent
from app.agents.audio_team import AudioTeamAgent
from app.agents.base import AgentBase
from app.agents.strategy import StrategyAgent
from app.agents.video_producer import VideoProducerAgent
from app.agents.web_dev import WebDevAgent

logger = logging.getLogger(__name__)


class AgentRegistry:
    """
    Central registry for all AI agents.

    Provides:
    - Singleton access to agent instances
    - Agent lookup by ID
    - Agent metadata and capabilities
    """

    def __init__(self):
        """Initialize agent registry with all specialist agents."""
        self._agents: Dict[str, AgentBase] = {}
        self._initialize_agents()

    def _initialize_agents(self) -> None:
        """Create and register all specialist agents."""
        # Register all agents
        agents = [
            StrategyAgent(),
            ArtDirectorAgent(),
            VideoProducerAgent(),
            AudioTeamAgent(),
            WebDevAgent(),
        ]

        for agent in agents:
            self._agents[agent.agent_id] = agent
            logger.info(f"Registered agent: {agent.agent_id}")

        logger.info(f"Agent registry initialized with {len(self._agents)} agents")

    def get_agent(self, agent_id: str) -> Optional[AgentBase]:
        """
        Get agent by ID.

        Args:
            agent_id: Agent identifier

        Returns:
            Agent instance or None if not found
        """
        agent = self._agents.get(agent_id)
        if not agent:
            logger.warning(f"Agent not found: {agent_id}")
        return agent

    def list_agents(self) -> list[str]:
        """
        Get list of all registered agent IDs.

        Returns:
            List of agent IDs
        """
        return list(self._agents.keys())

    def get_agent_info(self, agent_id: str) -> Optional[Dict[str, str]]:
        """
        Get agent metadata.

        Args:
            agent_id: Agent identifier

        Returns:
            Agent info dict or None
        """
        agent = self.get_agent(agent_id)
        if not agent:
            return None

        return {
            "agent_id": agent.agent_id,
            "class_name": agent.__class__.__name__,
            "max_revisions": str(agent.max_revisions),
        }


# Global agent registry instance
agent_registry = AgentRegistry()
