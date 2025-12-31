"""
VillageEngine - the main facade for ClaudeVille engine.

This is the primary entry point. It:
- Initializes and wires all components
- Provides tick_once() for running simulation
- Handles crash recovery from snapshots
- Exposes ObserverAPI for human interactions
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from langsmith import trace as langsmith_trace, traceable

from engine.domain import (
    AgentName,
    AgentSnapshot,
    Conversation,
    ConversationId,
    DomainEvent,
    Effect,
    Invitation,
    LocationId,
    AgentMovedEvent,
    NightSkippedEvent,
    TimePeriod,
    TimeSnapshot,
    WorldSnapshot,
    ConversationEndedEvent,
    WorldEventOccurred,
    UnseenConversationEnding,
)
from engine.storage import EventStore, VillageSnapshot
from engine.services import (
    Scheduler,
    ConversationService,
    AgentRegistry,
    CompactionService,
    ScheduledEvent,
    build_initial_snapshot,
    ensure_village_structure,
)
from engine.runtime import (
    TickContext,
    TickResult,
    TickPipeline,
    WakeCheckPhase,
    SchedulePhase,
    AgentTurnPhase,
    InterpretPhase,
    ApplyEffectsPhase,
    LLMProvider,
    get_conversation_tools,
)
from engine.adapters import VillageTracer
from engine.observer import ObserverAPI

if TYPE_CHECKING:
    from engine.adapters import ClaudeProvider

logger = logging.getLogger(__name__)


class VillageEngine:
    """
    The main simulation engine for ClaudeVille.

    This facade coordinates:
    - EventStore for persistence and state recovery
    - Scheduler for managing when agents act
    - ConversationService for managing conversations
    - TickPipeline for executing tick phases
    - ObserverAPI for human interactions
    """

    def __init__(
        self,
        village_root: Path | str | None = None,
        llm_provider: LLMProvider | None = None,
    ):
        """
        Initialize the engine.

        Args:
            village_root: Path to village data directory
            llm_provider: LLM provider for agent turns (required for running ticks)
        """
        self.village_root = Path(village_root) if village_root else Path("village")
        self.village_root.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initializing VillageEngine at {self.village_root}")

        # Ensure base village structure exists
        ensure_village_structure(self.village_root)

        # Core components
        self.event_store = EventStore(self.village_root)
        self.scheduler = Scheduler()
        self.conversation_service = ConversationService()
        self.agent_registry = AgentRegistry()
        self._llm_provider = llm_provider
        self.wake_phase = WakeCheckPhase()

        # Create tracer for real-time streaming
        self._tracer = VillageTracer(self.village_root / "traces")

        # Inject tracer into LLM provider if it supports it
        if hasattr(llm_provider, "_tracer"):
            llm_provider._tracer = self._tracer

        # Create compaction service if we have an LLM provider
        self._compaction_service: CompactionService | None = None
        if llm_provider is not None:
            self._compaction_service = CompactionService(llm_provider, self._tracer)

        # Build pipeline (phases that don't need LLM can still run)
        self._pipeline = self._build_pipeline()

        # Observer API (lazy initialization)
        self._observer: ObserverAPI | None = None

        # State tracking
        self._running = False
        self._paused = False
        self._pause_requested = False

        # Callbacks
        self._tick_callbacks: list[Callable[[TickResult], None]] = []
        self._event_callbacks: list[Callable[[DomainEvent], None]] = []

        # Current state (hydrated from EventStore)
        self._tick: int = 0
        self._time_snapshot: TimeSnapshot | None = None
        self._world: WorldSnapshot | None = None
        self._agents: dict[AgentName, AgentSnapshot] = {}
        self._conversations: dict[ConversationId, Conversation] = {}
        self._pending_invites: dict[AgentName, Invitation] = {}
        self._unseen_endings: dict[AgentName, list[UnseenConversationEnding]] = {}
        self._recent_arrivals: set[AgentName] = set()

    def _build_pipeline(self) -> TickPipeline:
        """Build the tick execution pipeline."""
        agent_turn_phase = AgentTurnPhase(self._llm_provider)
        agent_turn_phase.set_village_root(self.village_root)
        agent_turn_phase.set_event_store(self.event_store)
        agent_turn_phase.set_compaction_service(self._compaction_service)

        # Create interpret phase with tracer for interpret_complete events
        interpret_phase = InterpretPhase()
        interpret_phase.set_tracer(self._tracer)

        # Create apply effects phase with compaction service
        apply_effects_phase = ApplyEffectsPhase()
        apply_effects_phase.set_compaction_service(self._compaction_service)

        phases = [
            self.wake_phase,
            SchedulePhase(self.scheduler),
            agent_turn_phase,
            interpret_phase,
            apply_effects_phase,
        ]
        return TickPipeline(phases)

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def tick(self) -> int:
        """Current tick number."""
        return self._tick

    @property
    def time_snapshot(self) -> TimeSnapshot:
        """Current time snapshot."""
        if self._time_snapshot is None:
            raise RuntimeError("Engine not initialized - call recover() or initialize()")
        return self._time_snapshot

    @property
    def world(self) -> WorldSnapshot:
        """Current world state."""
        if self._world is None:
            raise RuntimeError("Engine not initialized - call recover() or initialize()")
        return self._world

    @property
    def agents(self) -> dict[AgentName, AgentSnapshot]:
        """Current agent states."""
        return self._agents

    @property
    def conversations(self) -> dict[ConversationId, Conversation]:
        """Current active conversations."""
        return self._conversations

    @property
    def pending_invites(self) -> dict[AgentName, Invitation]:
        """Current pending invitations."""
        return self._pending_invites

    @property
    def is_running(self) -> bool:
        """Whether the engine is running."""
        return self._running

    @property
    def is_paused(self) -> bool:
        """Whether the engine is paused."""
        return self._paused

    @property
    def is_pause_requested(self) -> bool:
        """Whether pause has been requested but not yet applied."""
        return self._pause_requested and not self._paused

    @property
    def observer(self) -> ObserverAPI:
        """Get the Observer API for human interactions."""
        if self._observer is None:
            self._observer = ObserverAPI(self)
        return self._observer

    @property
    def compaction_service(self) -> CompactionService | None:
        """Get the compaction service for manual compaction triggers."""
        return self._compaction_service

    # =========================================================================
    # Initialization and Recovery
    # =========================================================================

    def initialize(self, initial_snapshot: VillageSnapshot) -> None:
        """
        Initialize with a fresh village state.

        Args:
            initial_snapshot: Initial state for the village
        """
        logger.info("Initializing fresh village state")
        self.event_store.initialize(initial_snapshot)
        self._hydrate_from_snapshot(initial_snapshot)

        # Emit the founding event at tick 0 (before simulation starts)
        agent_names = tuple(self._agents.keys())
        founding_event = WorldEventOccurred(
            tick=0,
            timestamp=self._time_snapshot.timestamp,
            description="ClaudeVille has been founded! Three residents begin their new lives.",
            agents_involved=agent_names,
        )
        self.commit_event(founding_event)
        logger.info(f"Village founded with agents: {list(agent_names)}")

    def initialize_default(self) -> None:
        """
        Initialize a new village with default locations and agents.
        """
        snapshot = build_initial_snapshot(self.village_root)
        self.initialize(snapshot)

    def recover(self) -> bool:
        """
        Recover state from persisted snapshots and events.

        Returns:
            True if recovery succeeded, False if no state to recover
        """
        logger.info("Attempting to recover from persisted state")
        snapshot = self.event_store.recover()
        if snapshot is None:
            logger.warning("No persisted state found")
            return False

        self._hydrate_from_snapshot(snapshot)
        logger.info(f"Recovered at tick {self._tick}")
        return True

    def _hydrate_from_snapshot(
        self,
        snapshot: VillageSnapshot,
        *,
        include_scheduler: bool = True,
    ) -> None:
        """
        Hydrate in-memory state from a snapshot.

        Args:
            snapshot: The snapshot to hydrate from
            include_scheduler: Whether to load scheduler state (only True during recovery)
        """
        self._world = snapshot.world
        self._tick = snapshot.world.tick
        self._time_snapshot = TimeSnapshot(
            world_time=snapshot.world.world_time,
            tick=snapshot.world.tick,
            start_date=snapshot.world.start_date,
        )
        self._agents = dict(snapshot.agents)
        self._conversations = dict(snapshot.conversations)
        self._pending_invites = dict(snapshot.pending_invites)
        self._unseen_endings = dict(snapshot.unseen_endings) if snapshot.unseen_endings else {}

        # Hydrate services
        self.agent_registry.load_state(self._agents)
        self.conversation_service.load_state(
            self._conversations,
            self._pending_invites,
        )

        # Hydrate scheduler only during recovery, not after every tick
        # (to preserve force/skip modifiers set by observer between snapshots)
        if include_scheduler and snapshot.scheduler_state is not None:
            self.scheduler.load_state(snapshot.scheduler_state)

        # Restore token counts to provider from persisted agent snapshots
        # This ensures compaction threshold decisions are correct after restart
        if self._llm_provider is not None and hasattr(self._llm_provider, "restore_token_counts"):
            self._llm_provider.restore_token_counts(self._agents)

        logger.debug(
            f"Hydrated state | tick={self._tick} | "
            f"agents={len(self._agents)} | "
            f"conversations={len(self._conversations)}"
        )

    # =========================================================================
    # Tick Execution
    # =========================================================================

    async def tick_once(self) -> TickResult:
        """
        Execute a single tick of the simulation.

        This is the main entry point for advancing simulation time.
        Returns the result of the tick with all events that occurred.
        """
        if self._world is None:
            raise RuntimeError("Engine not initialized - call recover() or initialize()")

        if self._llm_provider is None:
            raise RuntimeError("No LLM provider configured - cannot run tick")

        # Ensure there is a schedule seeded for this tick
        self._ensure_schedule()

        # Provide recent arrivals to wake phase
        self.wake_phase.set_recent_arrivals(self._recent_arrivals)

        # Determine what time to advance to
        due_time = self._compute_next_tick_time()

        # Check for night skip: if all agents are sleeping, skip to morning
        night_skip_event = None
        if self._should_skip_night():
            morning_time = self._compute_next_morning()
            if morning_time > due_time:
                night_skip_event = NightSkippedEvent(
                    tick=self._tick + 1,
                    timestamp=morning_time,
                    from_time=self._time_snapshot.world_time if self._time_snapshot else due_time,
                    to_time=morning_time,
                )
                due_time = morning_time
                logger.info(f"Night skip: all agents sleeping, advancing to morning ({morning_time})")

        self._tick += 1

        # Update time snapshot
        self._time_snapshot = TimeSnapshot(
            world_time=due_time,
            tick=self._tick,
            start_date=self._world.start_date,
        )

        # Pop scheduled events for this tick
        scheduled_events = self.scheduler.pop_events_up_to(due_time)

        # Build initial context
        ctx = TickContext(
            tick=self._tick,
            timestamp=due_time,
            time_snapshot=self._time_snapshot,
            world=self._world,
            agents=dict(self._agents),
            conversations=dict(self._conversations),
            pending_invites=dict(self._pending_invites),
            unseen_endings=dict(self._unseen_endings),
            scheduled_events=scheduled_events,
        )

        logger.debug(
            f"Starting tick {self._tick} | "
            f"scheduled_events={len(scheduled_events)} | "
            f"agents={len(self._agents)}"
        )

        # Execute pipeline (with LangSmith tracing if enabled)
        langsmith_enabled = os.environ.get("LANGSMITH_TRACING", "").lower() == "true"

        if langsmith_enabled:
            async with langsmith_trace(
                name=f"tick:{self._tick}",
                run_type="chain",
                inputs={
                    "tick": self._tick,
                    "timestamp": due_time.isoformat(),
                    "scheduled_events": len(scheduled_events),
                    "agents": list(str(a) for a in self._agents.keys()),
                    "active_conversations": len(self._conversations),
                },
                metadata={
                    "time_period": self._time_snapshot.period.value if self._time_snapshot else None,
                    "weather": self._world.weather.value if self._world else None,
                },
                tags=["tick", f"tick-{self._tick}"],
            ) as run:
                result = await self._pipeline.execute(ctx)
                run.end(outputs={
                    "events_count": len(result.events),
                    "agents_acted": [str(a) for a in result.agents_acted],
                    "event_types": list(set(e.type for e in result.events)),
                })
        else:
            result = await self._pipeline.execute(ctx)

        # Commit events to storage
        # Note: last_location_speaker is updated via AgentLastActiveTickUpdatedEvent
        # Prepend night skip event if we skipped the night
        all_events = list(result.events)
        if night_skip_event:
            all_events.insert(0, night_skip_event)

        if all_events:
            self.event_store.append_all(all_events)

        # Update in-memory state from event store
        # Note: Don't reload scheduler state - preserve force/skip modifiers
        current_snapshot = self.event_store.get_current_snapshot()
        self._hydrate_from_snapshot(current_snapshot, include_scheduler=False)

        # Create snapshot and archive old events periodically
        # This happens AFTER events are committed, so snapshot captures current tick's state
        if self._tick > 0 and self._tick % self.event_store.SNAPSHOT_INTERVAL == 0:
            try:
                # Save scheduler state to snapshot before persisting
                self.event_store.set_scheduler_state(self.scheduler.to_state())
                self.event_store.create_snapshot_and_archive()
                logger.info(f"Created snapshot at tick {self._tick}")
            except Exception as e:
                # Snapshot failure shouldn't stop the simulation
                logger.error(f"Failed to create snapshot: {e}", exc_info=True)

        # Update recent arrivals
        self._recent_arrivals = {
            event.agent for event in result.events if isinstance(event, AgentMovedEvent)
        }

        # Record turns for agents that acted (clears forced_next if applicable)
        for agent in result.agents_acted:
            self.scheduler.record_turn(agent)

        # Fire callbacks
        for callback in self._tick_callbacks:
            try:
                callback(result)
            except Exception as e:
                logger.error(f"Tick callback error: {e}")

        for event in result.events:
            for callback in self._event_callbacks:
                try:
                    callback(event)
                except Exception as e:
                    logger.error(f"Event callback error: {e}")

        # Re-seed the schedule for display purposes
        # This ensures the scheduler reflects who will act on the NEXT tick
        self._ensure_schedule()

        logger.info(
            f"Tick {self._tick} complete | "
            f"events={len(result.events)} | "
            f"agents_acted={len(result.agents_acted)}"
        )

        return result

    def _compute_next_tick_time(self) -> datetime:
        """Compute the timestamp for the next tick."""
        # Check scheduler for earliest due event
        earliest = self.scheduler.get_earliest_due_time()
        if earliest:
            return earliest

        # No scheduled events - use default time increment
        if self._time_snapshot:
            return self._time_snapshot.timestamp + timedelta(minutes=Scheduler.SOLO_PACE_MINUTES)
        return datetime.now()

    def _should_skip_night(self) -> bool:
        """Check if we should skip to morning (all agents sleeping, not morning)."""
        if not self._agents or not self._time_snapshot:
            return False

        # All agents must be sleeping
        all_sleeping = all(agent.is_sleeping for agent in self._agents.values())
        if not all_sleeping:
            return False

        # Must not already be morning
        if self._time_snapshot.period == TimePeriod.MORNING:
            return False

        return True

    def _compute_next_morning(self) -> datetime:
        """Compute the datetime for the next 6 AM (start of morning)."""
        if not self._time_snapshot:
            return datetime.now()

        current = self._time_snapshot.world_time
        # If before 6 AM today, morning is today at 6 AM
        # Otherwise, morning is tomorrow at 6 AM
        morning_today = current.replace(hour=6, minute=0, second=0, microsecond=0)

        if current.hour < 6:
            return morning_today
        else:
            return morning_today + timedelta(days=1)

    def _ensure_schedule(self) -> None:
        """Seed the scheduler with pending events when needed."""
        if self._world is None or self._time_snapshot is None:
            return

        now = self._time_snapshot.world_time

        # Schedule invite responses (highest priority)
        for invitee, invite in self._pending_invites.items():
            if not self.scheduler.has_pending_invite_response(invitee):
                due_time = now + timedelta(minutes=Scheduler.INVITE_RESPONSE_MINUTES)
                self.scheduler.schedule_invite_response(
                    invitee,
                    invite.location,
                    due_time,
                )

        # Schedule conversation turns
        for conv_id, conv in self._conversations.items():
            if not self.scheduler.has_pending_conversation_turn(conv_id):
                due_time = now + timedelta(minutes=Scheduler.CONVERSATION_PACE_MINUTES)
                self.scheduler.schedule_conversation_turn(
                    conv_id,
                    conv.location,
                    due_time,
                )

        # Schedule solo turns for awake agents not in conversations
        participants: set[AgentName] = set()
        for conv in self._conversations.values():
            participants.update(conv.participants)

        for agent in self._agents.values():
            if agent.is_sleeping:
                continue
            if agent.name in participants:
                continue
            if agent.name in self._pending_invites:
                continue
            if not self.scheduler.has_pending_agent_turn(agent.name):
                due_time = now + timedelta(minutes=Scheduler.SOLO_PACE_MINUTES)
                self.scheduler.schedule_agent_turn(
                    agent.name,
                    agent.location,
                    due_time,
                )

    # =========================================================================
    # Run Loop
    # =========================================================================

    @traceable
    async def run(self, max_ticks: int | None = None) -> None:
        """
        Run the simulation loop.

        Args:
            max_ticks: Maximum ticks to run (None = run forever)
        """
        self._running = True
        self._paused = False
        ticks_run = 0

        logger.info(f"Starting simulation loop (max_ticks={max_ticks})")

        try:
            while self._running:
                if self._paused:
                    await asyncio.sleep(0.1)
                    continue

                await self.tick_once()
                ticks_run += 1

                # Apply pause after tick completes (graceful pause)
                if self._pause_requested:
                    self._paused = True
                    self._pause_requested = False

                if max_ticks and ticks_run >= max_ticks:
                    logger.info(f"Reached max_ticks ({max_ticks})")
                    break

        finally:
            self._running = False
            self._pause_requested = False
            logger.info(f"Simulation loop ended after {ticks_run} ticks")

    def pause(self) -> None:
        """Request graceful pause (will pause after current tick completes)."""
        self._pause_requested = True
        logger.info("Simulation pause requested")

    def resume(self) -> None:
        """Resume the simulation loop."""
        self._paused = False
        self._pause_requested = False
        logger.info("Simulation resumed")

    def stop(self) -> None:
        """Stop the simulation loop."""
        self._running = False
        self._pause_requested = False
        logger.info("Simulation stopping")

    # =========================================================================
    # Callbacks
    # =========================================================================

    def on_tick(self, callback: Callable[[TickResult], None]) -> None:
        """Register a callback for tick completion."""
        self._tick_callbacks.append(callback)

    def on_event(self, callback: Callable[[DomainEvent], None]) -> None:
        """Register a callback for domain events."""
        self._event_callbacks.append(callback)

    def on_agent_stream(self, callback: Callable[[str, dict], None]) -> None:
        """
        Register a callback for real-time agent trace events.

        Callbacks receive (event_type, event_dict) for each trace event.
        Thread-safe: runs on worker thread, use call_from_thread in TUI.

        Event types:
        - turn_start: Beginning of agent turn
        - text: Streaming text output
        - tool_use: Tool invocation
        - tool_result: Tool response
        - turn_end: End of turn (before interpretation)
        - interpret_complete: Interpreted observations (after InterpretPhase)

        Args:
            callback: Function(event_type: str, data: dict) -> None
        """
        self._tracer.register_callback(callback)

    # =========================================================================
    # State Mutation (for ObserverAPI)
    # =========================================================================

    def commit_event(self, event: DomainEvent) -> None:
        """
        Commit a single event (for observer commands).

        This bypasses the pipeline for direct observer actions.
        """
        self.event_store.append(event)
        current_snapshot = self.event_store.get_current_snapshot()
        self._hydrate_from_snapshot(current_snapshot)

        for callback in self._event_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Event callback error: {e}")

    def apply_effect(self, effect: Effect) -> None:
        """
        Apply a single effect (for observer commands).

        Converts the effect to events and commits them.
        """
        from engine.runtime.phases.apply_effects import ApplyEffectsPhase

        # Create a minimal context for the effect processor
        ctx = TickContext(
            tick=self._tick,
            timestamp=self._time_snapshot.timestamp if self._time_snapshot else datetime.now(),
            time_snapshot=self._time_snapshot
            or TimeSnapshot(
                world_time=datetime.now(),
                tick=0,
                start_date=self._world.start_date if self._world else datetime.now(),
            ),
            world=self._world,
            agents=dict(self._agents),
            conversations=dict(self._conversations),
            pending_invites=dict(self._pending_invites),
            unseen_endings=dict(self._unseen_endings),
        )

        # Use apply effects phase to convert effect to events (sync - no event loop needed)
        phase = ApplyEffectsPhase()
        ctx = ctx.with_effect(effect)
        ctx = phase.execute_sync(ctx)

        # Commit resulting events
        for event in ctx.events:
            self.commit_event(event)

    def end_conversation(
        self, conv_id: ConversationId, reason: str = "ended"
    ) -> DomainEvent | None:
        """
        End a conversation (for observer commands).

        Returns the ConversationEndedEvent or None if conversation not found.
        """
        from engine.domain import EndConversationEffect

        # Check if conversation exists
        conv = self._conversations.get(conv_id)
        if conv is None:
            return None

        # Use effect/event pattern - apply_effect handles conversion and commit
        effect = EndConversationEffect(conversation_id=conv_id, reason=reason)
        self.apply_effect(effect)

        # Return the event that was created (it's now in the event store)
        # We construct it here for the return value
        return ConversationEndedEvent(
            tick=self._tick,
            timestamp=self._time_snapshot.timestamp if self._time_snapshot else datetime.now(),
            conversation_id=conv_id,
            reason=reason,
            final_participants=tuple(conv.participants),
            summary="",
        )

    def write_to_agent_journal(self, agent_name: AgentName, content: str) -> None:
        """
        Write content to an agent's journal.

        This is a filesystem operation, not an event.
        """
        agent_dir = self.village_root / "agents" / agent_name / "journal"
        agent_dir.mkdir(parents=True, exist_ok=True)

        # Append to daily journal (use world time for consistency with simulation)
        world_time = self._time_snapshot.world_time if self._time_snapshot else datetime.now()
        date_str = world_time.strftime("%Y-%m-%d")
        journal_file = agent_dir / f"{date_str}.md"

        with open(journal_file, "a") as f:
            f.write(f"\n\n{content}")

        logger.debug(f"Wrote to journal for {agent_name}")

    def write_to_agent_dreams(self, agent_name: AgentName, content: str) -> None:
        """
        Write a dream entry to an agent's dreams directory.

        This is a filesystem operation, not an event.
        """
        from engine.services import append_dream

        # Use tick + 1 so dreams written now will be visible on the NEXT turn
        # (since get_unseen_dreams filters for tick > last_active_tick)
        append_dream(
            agent_name=agent_name,
            content=content,
            tick=self._tick + 1,
            village_root=self.village_root,
        )
        logger.debug(f"Wrote dream for {agent_name} (visible at tick {self._tick + 1})")

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def shutdown(self) -> None:
        """Shutdown the engine gracefully."""
        logger.info("Shutting down engine")
        self.stop()

        # Disconnect LLM provider if it supports it
        if hasattr(self._llm_provider, "disconnect_all"):
            await self._llm_provider.disconnect_all()

        logger.info("Engine shutdown complete")
