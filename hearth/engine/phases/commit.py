"""Commit phase for Hearth engine.

Persists all events from the tick to storage.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..context import TickContext

if TYPE_CHECKING:
    from storage import Storage
    from services import AgentService


class CommitPhase:
    """Commit events to storage.

    This phase runs last in the tick pipeline. It:
    1. Writes all accumulated events to the event log (audit trail)
    2. Updates the world state tick counter
    3. Saves session IDs for conversation continuity

    Note: State changes from actions should have already been persisted
    by the ActionEngine. This phase just logs events for audit purposes.
    """

    def __init__(self, storage: "Storage", agent_service: "AgentService"):
        """Initialize CommitPhase.

        Args:
            storage: Connected Storage instance
            agent_service: AgentService for session persistence
        """
        self._storage = storage
        self._agent_service = agent_service

    async def execute(self, ctx: TickContext) -> TickContext:
        """Execute commit phase.

        Persists events, updates tick counter, and saves session IDs.

        Args:
            ctx: Current tick context with accumulated events

        Returns:
            Unchanged context (this is the final phase)
        """
        # Write all events to audit log
        if ctx.events:
            await self._storage.log_events(ctx.events)

        # Save session IDs for conversation continuity
        for agent_name, result in ctx.turn_results.items():
            if result.session_id:
                await self._agent_service.update_session(
                    agent_name, result.session_id, ctx.tick
                )

        # Update world state tick
        await self._storage.world.set_tick(ctx.tick)

        return ctx
