"""Wake phase for Hearth engine.

Wakes sleeping agents based on conditions (time of day changes, visitors, etc.).
"""

from __future__ import annotations

from core.types import AgentName
from ..context import TickContext


class WakePhase:
    """Wake sleeping agents based on conditions.

    Currently wakes agents when:
    - Time of day becomes "morning"

    Future extensions could include:
    - Another agent arrives nearby (visitor)
    - World event occurs
    - Alarm/schedule trigger
    """

    async def execute(self, ctx: TickContext) -> TickContext:
        """Execute wake phase.

        Identifies sleeping agents that should wake up and adds them
        to agents_to_wake in the context.

        Args:
            ctx: Current tick context

        Returns:
            Updated context with agents_to_wake populated
        """
        to_wake: set[AgentName] = set()

        for name, agent in ctx.agents.items():
            if not agent.is_sleeping:
                continue

            # Wake on morning
            if ctx.time_of_day == "morning":
                to_wake.add(name)

        return ctx.with_agents_to_wake(frozenset(to_wake))
