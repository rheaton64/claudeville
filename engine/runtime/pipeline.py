"""
TickPipeline - orchestrates phase execution for a tick.

The pipeline executes a sequence of phases, each transforming the TickContext.
Phases can be async (for I/O like LLM calls) or sync (for pure transformations).

Design principles:
- Clear phase boundaries for debugging and testing
- Each phase receives context and returns new context
- Phases can be tested independently
- Pipeline handles phase ordering and error recovery
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from engine.runtime.context import TickContext, TickResult


logger = logging.getLogger(__name__)


@runtime_checkable
class Phase(Protocol):
    """
    Protocol for tick phases.

    Each phase receives a TickContext and returns a new TickContext
    with its transformations applied.
    """

    @property
    def name(self) -> str:
        """Human-readable phase name for logging."""
        ...

    async def execute(self, ctx: TickContext) -> TickContext:
        """
        Execute this phase.

        Args:
            ctx: The current tick context

        Returns:
            New TickContext with phase transformations applied
        """
        ...


class BasePhase(ABC):
    """
    Base class for phases with common functionality.

    Provides:
    - Automatic name from class name
    - Logging wrapper around execution
    - Error handling
    """

    @property
    def name(self) -> str:
        """Phase name derived from class name."""
        # WakeCheckPhase -> wake_check
        class_name = self.__class__.__name__
        if class_name.endswith("Phase"):
            class_name = class_name[:-5]
        # Convert CamelCase to snake_case
        import re
        return re.sub(r"(?<!^)(?=[A-Z])", "_", class_name).lower()

    @abstractmethod
    async def _execute(self, ctx: TickContext) -> TickContext:
        """Override this to implement phase logic."""
        ...

    async def execute(self, ctx: TickContext) -> TickContext:
        """Execute with logging and error handling."""
        logger.debug(f"Phase {self.name} starting | tick={ctx.tick}")
        try:
            result = await self._execute(ctx)
            logger.debug(
                f"Phase {self.name} complete | "
                f"effects={len(result.effects) - len(ctx.effects)} | "
                f"events={len(result.events) - len(ctx.events)}"
            )
            return result
        except Exception as e:
            logger.error(f"Phase {self.name} failed: {e}", exc_info=True)
            raise PhaseError(phase_name=self.name, original_error=e) from e


@dataclass
class PhaseError(Exception):
    """Error that occurred during phase execution."""

    phase_name: str
    original_error: Exception

    def __str__(self) -> str:
        return f"Phase '{self.phase_name}' failed: {self.original_error}"


@dataclass
class PipelineMetrics:
    """Metrics collected during pipeline execution."""

    total_duration_ms: float = 0.0
    phase_durations_ms: dict[str, float] = field(default_factory=dict)
    effects_produced: int = 0
    events_produced: int = 0
    agents_acted: int = 0


class TickPipeline:
    """
    Orchestrates execution of tick phases.

    The pipeline:
    1. Executes phases in order
    2. Collects metrics on phase durations
    3. Handles errors with context about which phase failed
    4. Returns a TickResult summarizing the tick

    Usage:
        pipeline = TickPipeline([
            WakeCheckPhase(...),
            SchedulePhase(...),
            AgentTurnPhase(...),
            InterpretPhase(...),
            ApplyEffectsPhase(...),
            ArchivePhase(...),
        ])

        result = await pipeline.execute(initial_context)
    """

    def __init__(self, phases: list[Phase]):
        """
        Initialize the pipeline with phases.

        Args:
            phases: Ordered list of phases to execute
        """
        self.phases = phases
        self._metrics: PipelineMetrics | None = None

    async def execute(self, ctx: TickContext) -> TickResult:
        """
        Execute all phases and return the result.

        Args:
            ctx: Initial tick context

        Returns:
            TickResult with all events and effects
        """
        import time

        self._metrics = PipelineMetrics()
        start_time = time.perf_counter()

        for phase in self.phases:
            phase_start = time.perf_counter()
            ctx = await phase.execute(ctx)
            phase_duration = (time.perf_counter() - phase_start) * 1000
            self._metrics.phase_durations_ms[phase.name] = phase_duration

        total_duration = (time.perf_counter() - start_time) * 1000
        self._metrics.total_duration_ms = total_duration
        self._metrics.effects_produced = len(ctx.effects)
        self._metrics.events_produced = len(ctx.events)
        self._metrics.agents_acted = len(ctx.agents_acted)

        logger.info(
            f"Pipeline complete | tick={ctx.tick} | "
            f"duration={total_duration:.1f}ms | "
            f"agents={len(ctx.agents_acted)} | "
            f"events={len(ctx.events)}"
        )

        return TickResult.from_context(ctx)

    def get_metrics(self) -> PipelineMetrics | None:
        """Get metrics from the last pipeline execution."""
        return self._metrics

    def get_phase(self, name: str) -> Phase | None:
        """Get a phase by name (for testing/debugging)."""
        for phase in self.phases:
            if phase.name == name:
                return phase
        return None
