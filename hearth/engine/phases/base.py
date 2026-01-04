"""Base classes and protocols for tick phases.

This module defines the Phase protocol and TickPipeline for executing
phases in sequence during a tick.
"""

from __future__ import annotations

from typing import Protocol

from ..context import TickContext


class Phase(Protocol):
    """Protocol for tick phases.

    Each phase receives the current TickContext, processes it, and returns
    an updated context. Phases should be stateless - all state flows through
    the context.
    """

    async def execute(self, ctx: TickContext) -> TickContext:
        """Execute this phase.

        Args:
            ctx: Current tick context

        Returns:
            Updated tick context
        """
        ...


class TickPipeline:
    """Executes phases in sequence.

    The pipeline takes a list of phases and executes them one by one,
    passing the updated context from each phase to the next.
    """

    def __init__(self, phases: list[Phase]):
        """Initialize pipeline with phases.

        Args:
            phases: List of phases to execute in order
        """
        self._phases = phases

    async def execute(self, ctx: TickContext) -> TickContext:
        """Execute all phases in sequence.

        Args:
            ctx: Initial tick context

        Returns:
            Final tick context after all phases
        """
        for phase in self._phases:
            ctx = await phase.execute(ctx)
        return ctx

    @property
    def phases(self) -> list[Phase]:
        """Get the list of phases."""
        return self._phases
