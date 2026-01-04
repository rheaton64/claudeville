"""HearthEngine - Main orchestrator for Hearth simulation.

Wires together all services and executes the tick pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable

from core.types import AgentName
from core.terrain import Weather
from .context import TickContext
from .phases import (
    TickPipeline,
    InvitationExpiryPhase,
    WakePhase,
    SchedulePhase,
    MovementPhase,
    AgentTurnPhase,
    CommitPhase,
)
from services import (
    WorldService,
    AgentService,
    ActionEngine,
    CraftingService,
    Narrator,
    ConversationService,
)
from services.scheduler import Scheduler
from adapters import PerceptionBuilder, get_time_of_day
from adapters.tracer import HearthTracer
from adapters.claude_provider import HearthProvider
from observe.api import ObserverAPI

if TYPE_CHECKING:
    from storage import Storage


class HearthEngine:
    """Main orchestrator for Hearth simulation.

    Wires together:
    - Existing services (WorldService, AgentService, ActionEngine, etc.)
    - New engine components (Scheduler, PerceptionBuilder, HearthProvider)
    - Tick pipeline (phases in sequence)
    - Observer API for TUI queries

    The engine maintains minimal state - most state lives in storage.
    """

    DEFAULT_VISION_RADIUS = 3  # Default: 7x7 grid (radius 3 = 3 cells in each direction)

    def __init__(
        self,
        storage: "Storage",
        vision_radius: int | None = None,
        agents_root: Path | None = None,
        enable_llm: bool = True,
    ):
        """Initialize HearthEngine.

        Args:
            storage: Connected Storage instance
            vision_radius: Vision radius for agents (default: 3)
            agents_root: Root directory for agent home directories
            enable_llm: Whether to enable LLM calls (False for testing)
        """
        self._storage = storage
        self._enable_llm = enable_llm
        self._agents_root = agents_root or Path("agents")

        # Vision radius is the single source of truth
        self._vision_radius = vision_radius or self.DEFAULT_VISION_RADIUS

        # Services (most already exist!)
        self._world_service = WorldService(storage)
        self._agent_service = AgentService(storage)
        self._crafting = CraftingService()
        self._conversation = ConversationService(storage)
        self._action_engine = ActionEngine(
            storage,
            self._world_service,
            self._agent_service,
            self._crafting,
            self._conversation,
            vision_radius=self._vision_radius,
        )
        self._narrator = Narrator()

        # PerceptionBuilder and Scheduler share vision_radius
        self._perception = PerceptionBuilder(
            self._world_service,
            self._agent_service,
            conversation_service=self._conversation,
            vision_radius=self._vision_radius,
        )
        self._scheduler = Scheduler(vision_radius=self._vision_radius)

        # Tracer for turn logging
        self._tracer = HearthTracer(storage.data_dir / "traces")

        # Provider for LLM calls (None if disabled)
        self._provider: HearthProvider | None = None
        if enable_llm:
            self._provider = HearthProvider(
                world_service=self._world_service,
                agent_service=self._agent_service,
                action_engine=self._action_engine,
                narrator=self._narrator,
                tracer=self._tracer,
                agents_root=self._agents_root,
            )

        # Pipeline
        self._pipeline = self._build_pipeline()

        # Observer interface
        self.observer = ObserverAPI(storage, self._world_service, self._agent_service)

        # State
        self._tick = 0

        # Callbacks
        self._tick_callbacks: list[Callable[[TickContext], None]] = []

    def _build_pipeline(self) -> TickPipeline:
        """Build the tick pipeline with all phases.

        Returns:
            Configured TickPipeline
        """
        return TickPipeline(
            [
                InvitationExpiryPhase(self._conversation),
                WakePhase(),
                MovementPhase(self._agent_service, self._scheduler.vision_radius),
                SchedulePhase(self._scheduler, self._agent_service),
                AgentTurnPhase(self._perception, self._provider),
                CommitPhase(self._storage, self._agent_service),
            ]
        )

    async def initialize(self) -> None:
        """Initialize engine from storage.

        Loads the current tick from world state. Should be called after
        storage is connected.
        """
        world_state = await self._world_service.get_world_state()
        self._tick = world_state.current_tick

    async def tick_once(self) -> TickContext:
        """Execute one tick.

        Increments tick counter, builds context, and runs all phases
        in the pipeline.

        Returns:
            Final TickContext after all phases complete
        """
        self._tick += 1

        # Build initial context
        ctx = await self._build_context()

        # Execute pipeline
        ctx = await self._pipeline.execute(ctx)

        # Notify callbacks
        for callback in self._tick_callbacks:
            callback(ctx)

        return ctx

    async def _build_context(self) -> TickContext:
        """Build initial TickContext for a tick.

        Returns:
            TickContext with current world state and empty accumulator fields
        """
        world_state = await self._world_service.get_world_state()
        agents = {a.name: a for a in await self._agent_service.get_all_agents()}
        time_of_day = get_time_of_day(self._tick)

        return TickContext(
            tick=self._tick,
            time_of_day=time_of_day,
            weather=world_state.weather,
            agents=agents,
            agents_to_act=frozenset(),
            agents_to_wake=frozenset(),
            clusters=(),  # Populated by SchedulePhase
            events=(),
            turn_results={},
        )

    def on_tick(self, callback: Callable[[TickContext], None]) -> None:
        """Register a tick completion callback.

        Callbacks are called after each tick completes with the final
        TickContext. Useful for TUI updates.

        Args:
            callback: Function to call after each tick
        """
        self._tick_callbacks.append(callback)

    def remove_callback(self, callback: Callable[[TickContext], None]) -> None:
        """Remove a tick callback.

        Args:
            callback: Callback to remove
        """
        if callback in self._tick_callbacks:
            self._tick_callbacks.remove(callback)

    # -------------------------------------------------------------------------
    # Observer Commands
    # -------------------------------------------------------------------------

    def force_turn(self, agent: AgentName) -> None:
        """Force an agent to act first in their cluster next tick.

        Args:
            agent: Agent name to prioritize
        """
        self._scheduler.force_next(agent)

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def tick(self) -> int:
        """Get current tick."""
        return self._tick

    @property
    def vision_radius(self) -> int:
        """Get vision radius."""
        return self._vision_radius

    @property
    def world_service(self) -> WorldService:
        """Get world service."""
        return self._world_service

    @property
    def agent_service(self) -> AgentService:
        """Get agent service."""
        return self._agent_service

    @property
    def action_engine(self) -> ActionEngine:
        """Get action engine."""
        return self._action_engine

    @property
    def narrator(self) -> Narrator:
        """Get narrator service."""
        return self._narrator

    @property
    def conversation_service(self) -> ConversationService:
        """Get conversation service."""
        return self._conversation

    @property
    def perception_builder(self) -> PerceptionBuilder:
        """Get perception builder."""
        return self._perception

    @property
    def tracer(self) -> HearthTracer:
        """Get tracer."""
        return self._tracer

    @property
    def provider(self) -> HearthProvider | None:
        """Get LLM provider (None if disabled)."""
        return self._provider

    async def shutdown(self) -> None:
        """Clean shutdown of engine resources."""
        if self._provider:
            await self._provider.disconnect_all()
