"""
WakeCheckPhase - checks sleeping agents for wake conditions.

Wake conditions:
1. Time period changed since they fell asleep
2. Another agent arrived at their location

This phase produces AgentWakeEffect for agents that should wake up.
"""

import logging

from engine.domain import (
    AgentName,
    AgentSnapshot,
    AgentWakeEffect,
    TimePeriod,
)
from engine.runtime.context import TickContext
from engine.runtime.pipeline import BasePhase


logger = logging.getLogger(__name__)


class WakeCheckPhase(BasePhase):
    """
    Check sleeping agents and wake them if conditions are met.

    Wake conditions:
    - Time period changed (morning → afternoon, etc.)
    - A visitor arrived at their location

    The phase tracks recent arrivals to detect visitor-based waking.
    """

    def __init__(self, recent_arrivals: set[AgentName] | None = None):
        """
        Initialize the phase.

        Args:
            recent_arrivals: Agents who moved this tick (for visitor wake)
        """
        self._recent_arrivals = recent_arrivals or set()

    def set_recent_arrivals(self, arrivals: set[AgentName]) -> None:
        """Update recent arrivals (called by engine before tick)."""
        self._recent_arrivals = arrivals

    async def _execute(self, ctx: TickContext) -> TickContext:
        """Check all sleeping agents for wake conditions."""
        effects = []

        for agent in ctx.agents.values():
            if not agent.is_sleeping:
                continue

            should_wake, reason = self._check_wake_conditions(agent, ctx)
            if should_wake:
                logger.debug(
                    f"Agent {agent.name} waking up | reason={reason} | "
                    f"location={agent.location}"
                )
                effects.append(AgentWakeEffect(agent=agent.name, reason=reason))

        if effects:
            logger.info(f"Waking {len(effects)} agents")

        return ctx.with_effects(effects)

    def _check_wake_conditions(
        self,
        agent: AgentSnapshot,
        ctx: TickContext,
    ) -> tuple[bool, str]:
        """
        Check if an agent should wake up.

        Returns:
            (should_wake, reason) tuple
        """
        # Condition 1: Time period changed
        if self._time_period_changed(agent, ctx):
            return True, "time_period_changed"

        # Condition 2: Visitor arrived at location
        visitor = self._check_visitor_arrival(agent, ctx)
        if visitor:
            return True, f"visitor_arrived:{visitor}"

        return False, ""

    def _time_period_changed(
        self,
        agent: AgentSnapshot,
        ctx: TickContext,
    ) -> bool:
        """Check if the time period changed since agent fell asleep."""
        if agent.sleep_started_time_period is None:
            return False

        current_period = ctx.time_snapshot.period
        sleep_period = agent.sleep_started_time_period
        if sleep_period == TimePeriod.NIGHT or sleep_period == TimePeriod.EVENING:
            return current_period == TimePeriod.MORNING

        return current_period != sleep_period

    def _check_visitor_arrival(
        self,
        agent: AgentSnapshot,
        ctx: TickContext,
    ) -> AgentName | None:
        """
        Check if a visitor arrived at the agent's location.

        Returns the visitor's name if one arrived, None otherwise.
        """
        for arrival in self._recent_arrivals:
            if arrival == agent.name:
                continue  # Can't be woken by yourself

            visitor = ctx.agents.get(arrival)
            if visitor and visitor.location == agent.location:
                return arrival

        return None
