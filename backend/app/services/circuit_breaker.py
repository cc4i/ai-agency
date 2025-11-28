"""Circuit Breaker for Remote Agent Fault Tolerance.

Prevents repeated calls to failing remote agents and enables
automatic recovery after a timeout period.
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, requests allowed
    OPEN = "open"  # Failure threshold exceeded, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures.

    States:
    - CLOSED: Normal operation, all requests pass through
    - OPEN: Too many failures, requests are immediately rejected
    - HALF_OPEN: After recovery timeout, allow one test request

    Usage:
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)

        if await breaker.can_execute("agent_id"):
            try:
                result = await call_remote_agent()
                await breaker.record_success("agent_id")
            except Exception:
                await breaker.record_failure("agent_id")
                raise
        else:
            # Circuit is open, use fallback
            result = await call_local_agent()
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 1,
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            half_open_max_calls: Max concurrent calls in half-open state
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._failures: Dict[str, int] = {}
        self._last_failure_time: Dict[str, float] = {}
        self._state: Dict[str, CircuitState] = {}
        self._half_open_calls: Dict[str, int] = {}
        self._lock = asyncio.Lock()

    def _get_state(self, agent_id: str) -> CircuitState:
        """Get current state for an agent."""
        return self._state.get(agent_id, CircuitState.CLOSED)

    def _set_state(self, agent_id: str, state: CircuitState) -> None:
        """Set state for an agent."""
        old_state = self._state.get(agent_id, CircuitState.CLOSED)
        if old_state != state:
            logger.info(f"Circuit breaker {agent_id}: {old_state} -> {state}")
        self._state[agent_id] = state

    async def can_execute(self, agent_id: str) -> bool:
        """
        Check if a request can be executed.

        Args:
            agent_id: Agent identifier

        Returns:
            True if request should proceed, False if circuit is open
        """
        async with self._lock:
            state = self._get_state(agent_id)

            if state == CircuitState.CLOSED:
                return True

            elif state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                last_failure = self._last_failure_time.get(agent_id, 0)
                if time.time() - last_failure >= self.recovery_timeout:
                    # Transition to half-open
                    self._set_state(agent_id, CircuitState.HALF_OPEN)
                    self._half_open_calls[agent_id] = 0
                    return True
                return False

            elif state == CircuitState.HALF_OPEN:
                # Allow limited calls in half-open state
                current_calls = self._half_open_calls.get(agent_id, 0)
                if current_calls < self.half_open_max_calls:
                    self._half_open_calls[agent_id] = current_calls + 1
                    return True
                return False

            return False

    async def record_success(self, agent_id: str) -> None:
        """
        Record a successful call.

        Args:
            agent_id: Agent identifier
        """
        async with self._lock:
            state = self._get_state(agent_id)

            if state == CircuitState.HALF_OPEN:
                # Success in half-open state closes the circuit
                self._set_state(agent_id, CircuitState.CLOSED)
                self._failures[agent_id] = 0
                self._half_open_calls[agent_id] = 0
                logger.info(f"Circuit breaker {agent_id}: recovered, circuit closed")

            elif state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failures[agent_id] = 0

    async def record_failure(self, agent_id: str) -> None:
        """
        Record a failed call.

        Args:
            agent_id: Agent identifier
        """
        async with self._lock:
            state = self._get_state(agent_id)
            self._last_failure_time[agent_id] = time.time()

            if state == CircuitState.HALF_OPEN:
                # Failure in half-open state reopens the circuit
                self._set_state(agent_id, CircuitState.OPEN)
                self._half_open_calls[agent_id] = 0
                logger.warning(f"Circuit breaker {agent_id}: recovery failed, circuit reopened")

            elif state == CircuitState.CLOSED:
                # Increment failure count
                failures = self._failures.get(agent_id, 0) + 1
                self._failures[agent_id] = failures

                if failures >= self.failure_threshold:
                    self._set_state(agent_id, CircuitState.OPEN)
                    logger.warning(
                        f"Circuit breaker {agent_id}: threshold exceeded "
                        f"({failures}/{self.failure_threshold}), circuit opened"
                    )

    async def is_open(self, agent_id: str) -> bool:
        """
        Check if circuit is open (blocking calls).

        Args:
            agent_id: Agent identifier

        Returns:
            True if circuit is open
        """
        return not await self.can_execute(agent_id)

    async def reset(self, agent_id: str) -> None:
        """
        Manually reset circuit breaker for an agent.

        Args:
            agent_id: Agent identifier
        """
        async with self._lock:
            self._failures[agent_id] = 0
            self._last_failure_time.pop(agent_id, None)
            self._state[agent_id] = CircuitState.CLOSED
            self._half_open_calls[agent_id] = 0
            logger.info(f"Circuit breaker {agent_id}: manually reset")

    def get_status(self, agent_id: str) -> Dict[str, any]:
        """
        Get current status for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Status dictionary
        """
        state = self._get_state(agent_id)
        failures = self._failures.get(agent_id, 0)
        last_failure = self._last_failure_time.get(agent_id)

        status = {
            "agent_id": agent_id,
            "state": state.value,
            "failures": failures,
            "failure_threshold": self.failure_threshold,
        }

        if last_failure:
            status["last_failure_time"] = last_failure
            status["seconds_since_failure"] = time.time() - last_failure

            if state == CircuitState.OPEN:
                remaining = self.recovery_timeout - (time.time() - last_failure)
                status["recovery_in_seconds"] = max(0, remaining)

        return status

    def get_all_statuses(self) -> Dict[str, Dict[str, any]]:
        """
        Get status for all tracked agents.

        Returns:
            Dictionary of agent_id -> status
        """
        all_agents = set(self._state.keys()) | set(self._failures.keys())
        return {agent_id: self.get_status(agent_id) for agent_id in all_agents}


# Global circuit breaker instance
circuit_breaker = CircuitBreaker()
