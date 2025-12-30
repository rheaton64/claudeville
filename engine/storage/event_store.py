from pathlib import Path
from typing import Sequence, TYPE_CHECKING
from pydantic import TypeAdapter

if TYPE_CHECKING:
    from engine.services.scheduler import SchedulerState

from engine.domain import (
    DomainEvent,
    AgentSnapshot,
    TimeSnapshot,
    WorldSnapshot,
    Conversation,
    Invitation,
    INVITE_EXPIRY_TICKS,
    # Event types for replay
    AgentMovedEvent,
    AgentMoodChangedEvent,
    AgentEnergyChangedEvent,
    AgentSleptEvent,
    AgentWokeEvent,
    AgentLastActiveTickUpdatedEvent,
    ConversationInvitedEvent,
    ConversationInviteAcceptedEvent,
    ConversationInviteDeclinedEvent,
    ConversationInviteExpiredEvent,
    ConversationStartedEvent,
    ConversationJoinedEvent,
    ConversationLeftEvent,
    ConversationTurnEvent,
    ConversationNextSpeakerSetEvent,
    ConversationEndedEvent,
    WeatherChangedEvent,
)
from .snapshot_store import SnapshotStore, VillageSnapshot
from .archive import EventArchive

EventAdapter = TypeAdapter(DomainEvent)

class EventStore:
    """
    Append-only event store with snapshot cache and cold storage.

    This is the primary persistance mechanism. All state changes flow through here as DomainEvents.
    """
    
    SNAPSHOT_INTERVAL = 100

    def __init__(self, village_root: Path):
        self.village_root = village_root
        self.village_root.mkdir(parents=True, exist_ok=True)

        self.event_log = village_root / "events.jsonl"
        self.snapshot_store = SnapshotStore(village_root)
        self.archive = EventArchive(village_root)
        
        # In-memory current state
        self._current_snapshot: VillageSnapshot | None = None
        self._events_since_snapshot: list[DomainEvent] = []

    def initialize(self, initial_snapshot: VillageSnapshot) -> None:
        """Initialize with a starting snapshot (for new villages)."""
        self._current_snapshot = initial_snapshot
        self._events_since_snapshot = []
        self.snapshot_store.save(initial_snapshot)

    def recover(self) -> VillageSnapshot | None:
        """Recover state from latest snapshot and replay events."""
        snapshot = self.snapshot_store.load_latest()
        if snapshot is None:
            return None

        # Replay events since snapshot
        events = self._load_events_since(snapshot.tick)
        self._current_snapshot = snapshot
        self._events_since_snapshot = []

        for event in events:
            self._apply_event(event)
            self._events_since_snapshot.append(event)

        return self.get_current_snapshot()

    def append(self, event: DomainEvent) -> None:
        """Append a single event."""
        self.append_all([event])

    def append_all(self, events: Sequence[DomainEvent]) -> None:
        """
        Atomically append multiple events.
        This is the main write path - all state changes flow through here.
        """
        if not events:
            return

        # Write to log file
        with open(self.event_log, "a") as f:
            for event in events:
                line = event.model_dump_json() + "\n"
                f.write(line)

        # Update in-memory state
        for event in events:
            self._apply_event(event)
            self._events_since_snapshot.append(event)

    def get_current_snapshot(self) -> VillageSnapshot:
        """Get the current village state."""
        if self._current_snapshot is None:
            raise RuntimeError("EventStore not initialized - call initialize() or recover()")
        return self._current_snapshot

    def get_events_since(self, tick: int) -> list[DomainEvent]:
        """Get all events since a given tick (from memory + disk if needed)."""
        # For now, just return from memory cache
        return [e for e in self._events_since_snapshot if e.tick > tick]

    def get_recent_events(
        self,
        limit: int = 20,
        event_types: set[str] | None = None,
        since_tick: int = 0,
    ) -> list[DomainEvent]:
        """
        Get recent events from the active log.

        Args:
            limit: Maximum number of events to return (most recent)
            event_types: Optional set of event.type values to include
            since_tick: Only include events with tick > since_tick
        """
        if limit <= 0 or not self.event_log.exists():
            return []

        with open(self.event_log) as f:
            lines = f.readlines()

        events: list[DomainEvent] = []
        for line in reversed(lines):
            if not line.strip():
                continue
            event = EventAdapter.validate_json(line)
            if event.tick <= since_tick:
                break
            if event_types and event.type not in event_types:
                continue
            events.append(event)
            if len(events) >= limit:
                break

        return list(reversed(events))

    def _load_events_since(self, tick: int) -> list[DomainEvent]:
        """Load events from disk since a given tick."""
        events = []
        if self.event_log.exists():
            with open(self.event_log) as f:
                for line in f:
                    if line.strip():
                        event = EventAdapter.validate_json(line)
                        if event.tick > tick:
                            events.append(event)
        return events
    def _apply_event(self, event: DomainEvent) -> None:
        """Apply an event to update the current snapshot."""
        if self._current_snapshot is None:
            raise RuntimeError("Cannot apply event - no current snapshot")

        # This is where events update the in-memory state
        # We need to create new immutable snapshots

        snapshot = self._current_snapshot
        world = snapshot.world
        agents = dict(snapshot.agents)
        conversations = dict(snapshot.conversations)
        pending_invites = dict(snapshot.pending_invites)

        # Update tick on world
        if event.tick > world.tick:
            world = WorldSnapshot(
                tick=event.tick,
                world_time=event.timestamp,
                start_date=world.start_date,
                weather=world.weather,
                locations=world.locations,
                agent_locations=world.agent_locations,
            )

        time_snapshot = TimeSnapshot(
            world_time=event.timestamp,
            tick=event.tick,
            start_date=world.start_date,
        )

        # Handle specific event types
        match event:
            case AgentMovedEvent():
                if event.agent in agents:
                    agent = agents[event.agent]
                    agents[event.agent] = AgentSnapshot(
                        **{**agent.model_dump(), "location": event.to_location}
                    )
                # Update world agent_locations
                new_locations = dict(world.agent_locations)
                new_locations[event.agent] = event.to_location
                world = WorldSnapshot(**{**world.model_dump(), "agent_locations": new_locations})

            case AgentMoodChangedEvent():
                if event.agent in agents:
                    agent = agents[event.agent]
                    agents[event.agent] = AgentSnapshot(
                        **{**agent.model_dump(), "mood": event.new_mood}
                    )

            case AgentEnergyChangedEvent():
                if event.agent in agents:
                    agent = agents[event.agent]
                    agents[event.agent] = AgentSnapshot(
                        **{**agent.model_dump(), "energy": event.new_energy}
                    )

            case AgentSleptEvent():
                if event.agent in agents:
                    agent = agents[event.agent]
                    agents[event.agent] = AgentSnapshot(
                        **{**agent.model_dump(), "is_sleeping": True, "sleep_started_tick": event.tick, "sleep_started_time_period": time_snapshot.period}
                    )

            case AgentWokeEvent():
                if event.agent in agents:
                    agent = agents[event.agent]
                    agents[event.agent] = AgentSnapshot(
                        **{**agent.model_dump(), "is_sleeping": False, "sleep_started_tick": None, "sleep_started_time_period": None}
                    )

            case AgentLastActiveTickUpdatedEvent():
                if event.agent in agents:
                    agent = agents[event.agent]
                    agents[event.agent] = AgentSnapshot(
                        **{**agent.model_dump(), "last_active_tick": event.new_last_active_tick}
                    )

            case ConversationStartedEvent():
                conversations[event.conversation_id] = Conversation(
                    id=event.conversation_id,
                    location=event.location,
                    privacy=event.privacy,
                    participants=frozenset(event.initial_participants),
                    started_at_tick=event.tick,
                    created_by=event.initial_participants[0] if event.initial_participants else "",
                )

            case ConversationInvitedEvent():
                invitation = Invitation(
                    conversation_id=event.conversation_id,
                    inviter=event.inviter,
                    invitee=event.invitee,
                    location=event.location,
                    privacy=event.privacy,
                    created_at_tick=event.tick,
                    expires_at_tick=event.tick + INVITE_EXPIRY_TICKS,
                    invited_at=event.timestamp,
                )
                pending_invites[event.invitee] = invitation

            case ConversationInviteAcceptedEvent():
                pending_invites.pop(event.invitee, None)

            case ConversationInviteDeclinedEvent():
                pending_invites.pop(event.invitee, None)

            case ConversationInviteExpiredEvent():
                pending_invites.pop(event.invitee, None)

            case ConversationJoinedEvent():
                if event.conversation_id in conversations:
                    conv = conversations[event.conversation_id]
                    conversations[event.conversation_id] = Conversation(
                        **{**conv.model_dump(), "participants": conv.participants | {event.agent}}
                    )

            case ConversationLeftEvent():
                if event.conversation_id in conversations:
                    conv = conversations[event.conversation_id]
                    conversations[event.conversation_id] = Conversation(
                        **{**conv.model_dump(), "participants": conv.participants - {event.agent}}
                    )

            case ConversationTurnEvent():
                if event.conversation_id in conversations:
                    conv = conversations[event.conversation_id]
                    from engine.domain import ConversationTurn
                    new_turn = ConversationTurn(
                        speaker=event.speaker,
                        narrative=event.narrative,
                        tick=event.tick,
                        timestamp=event.timestamp,
                    )
                    conversations[event.conversation_id] = Conversation(
                        **{
                            **conv.model_dump(),
                            "history": (*conv.history, new_turn),
                            "next_speaker": None,
                        }
                    )

            case ConversationNextSpeakerSetEvent():
                if event.conversation_id in conversations:
                    conv = conversations[event.conversation_id]
                    conversations[event.conversation_id] = Conversation(
                        **{**conv.model_dump(), "next_speaker": event.next_speaker}
                    )

            case ConversationEndedEvent():
                if event.conversation_id in conversations:
                    del conversations[event.conversation_id]

            case WeatherChangedEvent():
                from engine.domain import Weather
                world = WorldSnapshot(
                    **{**world.model_dump(), "weather": Weather(event.new_weather)}
                )

        # Preserve scheduler_state from previous snapshot (it's not affected by domain events)
        scheduler_state = snapshot.scheduler_state
        self._current_snapshot = VillageSnapshot(world, agents, conversations, pending_invites, scheduler_state)

    def set_scheduler_state(self, scheduler_state: "SchedulerState") -> None:
        """Update the scheduler state in the current snapshot.

        Called by the engine before saving periodic snapshots.
        Scheduler state is managed by the engine, not by domain events.
        """
        if self._current_snapshot is None:
            return

        # Create new snapshot with updated scheduler state
        s = self._current_snapshot
        self._current_snapshot = VillageSnapshot(
            world=s.world,
            agents=s.agents,
            conversations=s.conversations,
            pending_invites=s.pending_invites,
            scheduler_state=scheduler_state,
        )

    def create_snapshot_and_archive(self) -> None:
        """Create a snapshot and archive old events."""
        if self._current_snapshot is None:
            return

        # Save snapshot
        self.snapshot_store.save(self._current_snapshot)

        # Archive events older than SNAPSHOT_INTERVAL ticks ago
        archive_before = self._current_snapshot.tick - self.SNAPSHOT_INTERVAL
        if archive_before > 0:
            self.archive.archive_events_before(archive_before)

        # Clear in-memory event buffer (we have a snapshot now)
        self._events_since_snapshot = []

    
