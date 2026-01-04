"""Schedule phase for Hearth engine.

Computes agent clusters and determines execution order for the tick.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.types import AgentName
from ..context import TickContext
from services.scheduler import Scheduler

if TYPE_CHECKING:
    from services.agent_service import AgentService


class SchedulePhase:
    """Compute clusters and determine execution order.

    Active agents (not sleeping, not journeying) act each tick.
    Journeying agents are in "movement trance" - they skip turns until
    interrupted or arrived. Clustering determines execution order:
    - Agents in different clusters can execute in parallel
    - Agents in the same cluster execute sequentially (round-robin)

    Also persists wake state for agents identified by WakePhase.
    """

    def __init__(self, scheduler: Scheduler, agent_service: "AgentService"):
        """Initialize SchedulePhase.

        Args:
            scheduler: Scheduler service for computing clusters
            agent_service: AgentService for persisting wake state
        """
        self._scheduler = scheduler
        self._agent_service = agent_service

    async def execute(self, ctx: TickContext) -> TickContext:
        """Execute schedule phase.

        Computes which agents will act this tick and groups them into
        clusters for execution ordering. Also persists wake state changes.

        Args:
            ctx: Current tick context

        Returns:
            Updated context with agents_to_act and clusters populated
        """
        updated_agents = dict(ctx.agents)

        # Active agents: not sleeping, not journeying (journey = movement trance)
        active_agents = {
            name: agent
            for name, agent in updated_agents.items()
            if not agent.is_sleeping and not agent.is_journeying
        }

        # Wake agents identified by WakePhase and add to active
        for name in ctx.agents_to_wake:
            if name in ctx.agents:
                # Persist wake state to database
                await self._agent_service.set_sleeping(name, False)
                # Keep in-memory snapshot consistent for this tick
                updated_agent = updated_agents[name].with_sleeping(False)
                updated_agents[name] = updated_agent
                active_agents[name] = updated_agent

        # Compute clusters based on proximity
        clusters = self._scheduler.compute_clusters(active_agents)

        # Handle forced turn (move agent to front of their cluster)
        forced = self._scheduler.get_forced_next()
        if forced:
            for cluster in clusters:
                if forced in cluster:
                    cluster.remove(forced)
                    cluster.insert(0, forced)
                    break

        # All active agents will act this tick
        agents_to_act = frozenset(active_agents.keys())

        return (
            ctx.with_agents(updated_agents)
            .with_agents_to_act(agents_to_act)
            .with_clusters(clusters)
        )
