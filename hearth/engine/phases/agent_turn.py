"""Agent turn phase for Hearth engine.

Executes agent turns using cluster-based ordering:
- Different clusters run in parallel (asyncio.gather)
- Agents within a cluster run sequentially (round-robin)
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from core.types import AgentName
from core.events import DomainEvent
from ..context import TickContext, TurnResult

if TYPE_CHECKING:
    from adapters.perception import PerceptionBuilder
    from adapters.claude_provider import HearthProvider


logger = logging.getLogger(__name__)


class AgentTurnPhase:
    """Execute agent turns using cluster-based ordering.

    Uses clustering for execution order:
    - Different clusters run in parallel (asyncio.gather)
    - Agents within a cluster run sequentially (round-robin)
    """

    def __init__(
        self,
        perception_builder: "PerceptionBuilder",
        provider: "HearthProvider | None" = None,
    ):
        """Initialize AgentTurnPhase.

        Args:
            perception_builder: PerceptionBuilder for generating agent context
            provider: HearthProvider for LLM calls (None for stub mode)
        """
        self._perception = perception_builder
        self._provider = provider

    async def execute(self, ctx: TickContext) -> TickContext:
        """Execute agent turns.

        Runs clusters in parallel, with agents within each cluster
        executing sequentially.

        Args:
            ctx: Current tick context

        Returns:
            Updated context with turn_results populated
        """
        if not ctx.clusters:
            # No agents to execute
            return ctx

        # Execute clusters in parallel, agents within cluster sequentially
        cluster_tasks = [
            self._execute_cluster(cluster, ctx) for cluster in ctx.clusters
        ]

        # Gather results from all clusters
        cluster_results = await asyncio.gather(*cluster_tasks)

        # Merge all turn results
        turn_results: dict[AgentName, TurnResult] = {}
        all_events: list[DomainEvent] = []

        for results in cluster_results:
            for result in results:
                turn_results[result.agent_name] = result
                all_events.extend(result.events)

        return ctx.with_turn_results(turn_results).append_events(all_events)

    async def _execute_cluster(
        self, cluster: tuple[AgentName, ...], ctx: TickContext
    ) -> list[TurnResult]:
        """Execute agents in a cluster sequentially.

        Args:
            cluster: Tuple of agent names in execution order
            ctx: Current tick context

        Returns:
            List of TurnResults for all agents in the cluster
        """
        results: list[TurnResult] = []

        for agent_name in cluster:
            result = await self._execute_agent_turn(agent_name, ctx)
            results.append(result)

        return results

    async def _execute_agent_turn(
        self, agent_name: AgentName, ctx: TickContext
    ) -> TurnResult:
        """Execute a single agent's turn.

        Args:
            agent_name: Name of the agent
            ctx: Current tick context

        Returns:
            TurnResult with perception, actions, events, and narrative
        """
        # Build perception
        perception = await self._perception.build(agent_name, ctx.tick)

        # If no provider, return stub result
        if self._provider is None:
            logger.debug(f"[{agent_name}] Stub mode - no provider")
            return TurnResult(
                agent_name=agent_name,
                perception=perception,
                actions_taken=[],
                events=[],
            )

        # Get agent from context
        agent = ctx.agents.get(agent_name)
        if agent is None:
            logger.error(f"[{agent_name}] Agent not found in context")
            return TurnResult(
                agent_name=agent_name,
                perception=perception,
                actions_taken=[],
                events=[],
            )

        # Skip sleeping agents
        if agent.is_sleeping:
            logger.debug(f"[{agent_name}] Sleeping - skipping turn")
            return TurnResult(
                agent_name=agent_name,
                perception=perception,
                actions_taken=[],
                events=[],
            )

        # Execute turn via provider
        try:
            provider_result = await self._provider.execute_turn(
                agent=agent,
                perception=perception,
                tick=ctx.tick,
            )

            return TurnResult(
                agent_name=agent_name,
                perception=perception,
                actions_taken=provider_result.actions_taken,
                events=provider_result.events,
                narrative=provider_result.narrative,
                session_id=provider_result.session_id,
                token_usage=provider_result.token_usage,
            )

        except Exception as e:
            logger.exception(f"[{agent_name}] Error executing turn: {e}")
            return TurnResult(
                agent_name=agent_name,
                perception=perception,
                actions_taken=[],
                events=[],
            )
