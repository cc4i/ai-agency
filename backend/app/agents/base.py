"""Base agent abstraction for all specialist agents."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from app.models.assets import CritiqueResult


class AgentBase(ABC):
    """
    Abstract base class for all AI agents.

    Each specialist agent (Strategy, Art Director, Video Producer, Audio Team, Web Dev)
    inherits from this class and implements the execute, critique, and revise methods.
    """

    def __init__(self, agent_id: str):
        """
        Initialize agent with unique identifier.

        Args:
            agent_id: Unique identifier for this agent (e.g., "strategy", "art_director")
        """
        self.agent_id = agent_id
        self.max_revisions = 2

    @abstractmethod
    async def execute(
        self, task: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute the agent's primary task.

        Args:
            task: Task parameters specific to this agent
            context: Shared context (e.g., project brief, previous outputs)

        Returns:
            Agent output as dictionary (will be parsed to specific model)
        """
        pass

    @abstractmethod
    async def critique(
        self, result: Dict[str, Any], brief: Dict[str, Any]
    ) -> CritiqueResult:
        """
        Evaluate the result against project brief.

        Args:
            result: Agent output to evaluate
            brief: Project brief for comparison

        Returns:
            CritiqueResult with status and revision instructions
        """
        pass

    @abstractmethod
    async def revise(
        self, result: Dict[str, Any], critique: CritiqueResult
    ) -> Dict[str, Any]:
        """
        Revise the result based on critique feedback.

        Args:
            result: Original agent output
            critique: Critique with revision instructions

        Returns:
            Revised agent output
        """
        pass

    async def execute_with_critique(
        self, task: Dict[str, Any], context: Dict[str, Any], brief: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute task with automatic critique and revision loop.

        This is a helper method that combines execution, critique, and revision.
        Maximum 2 revisions per task.

        Args:
            task: Task parameters
            context: Shared context
            brief: Project brief for critique

        Returns:
            Final agent output after critique loop
        """
        result = await self.execute(task, context)
        revision_count = 0

        while revision_count < self.max_revisions:
            critique = await self.critique(result, brief)

            if critique.status == "PASS":
                # Quality acceptable, return result
                return result

            # Need revision
            revision_count += 1
            if revision_count >= self.max_revisions:
                # Max revisions reached, return current result
                # In production, this would escalate to user
                return result

            # Revise the result
            result = await self.revise(result, critique)

        return result


class MockAgent(AgentBase):
    """
    Mock agent for development and testing.

    Returns pre-defined outputs without calling real APIs.
    """

    def __init__(self, agent_id: str, mock_output: Optional[Dict[str, Any]] = None):
        """
        Initialize mock agent.

        Args:
            agent_id: Agent identifier
            mock_output: Pre-defined output to return (optional)
        """
        super().__init__(agent_id)
        self.mock_output = mock_output or {"status": "completed", "data": {}}

    async def execute(
        self, task: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Return mock output."""
        return self.mock_output

    async def critique(
        self, result: Dict[str, Any], brief: Dict[str, Any]
    ) -> CritiqueResult:
        """Always pass critique in mock mode."""
        return CritiqueResult(status="PASS", score=1.0, issues=[])

    async def revise(
        self, result: Dict[str, Any], critique: CritiqueResult
    ) -> Dict[str, Any]:
        """Return unchanged result."""
        return result
