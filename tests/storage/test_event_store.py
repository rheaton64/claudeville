"""Tests for engine.storage.event_store module."""

import pytest
from datetime import datetime
from pathlib import Path

from engine.domain import (
    AgentName,
    LocationId,
    ConversationId,
    AgentSnapshot,
    WorldSnapshot,
    Weather,
    AgentMovedEvent,
    AgentMoodChangedEvent,
    AgentSleptEvent,
    AgentWokeEvent,
    ConversationStartedEvent,
    ConversationInvitedEvent,
    ConversationInviteAcceptedEvent,
    ConversationJoinedEvent,
    ConversationLeftEvent,
    ConversationTurnEvent,
    ConversationEndedEvent,
    ConversationEndingUnseenEvent,
    ConversationEndingSeenEvent,
    WeatherChangedEvent,
    UnseenConversationEnding,
)
from engine.storage import EventStore, VillageSnapshot


class TestEventStoreInitialization:
    """Tests for EventStore initialization."""

    def test_creates_village_root(self, temp_village_dir: Path):
        """Test EventStore creates village root if needed."""
        new_dir = temp_village_dir / "new_village"
        store = EventStore(new_dir)

        assert new_dir.exists()

    def test_initialize_saves_snapshot(self, temp_village_dir: Path, world_snapshot: WorldSnapshot, sample_agent: AgentSnapshot):
        """Test initialize saves the initial snapshot."""
        store = EventStore(temp_village_dir)
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
        )

        store.initialize(snapshot)

        # Snapshot should be saved
        assert (temp_village_dir / "snapshots").exists()
        snapshots = list((temp_village_dir / "snapshots").glob("state_*.json"))
        assert len(snapshots) == 1

    def test_get_current_snapshot_before_init_raises(self, temp_village_dir: Path):
        """Test accessing snapshot before initialization raises error."""
        store = EventStore(temp_village_dir)

        with pytest.raises(RuntimeError, match="not initialized"):
            store.get_current_snapshot()


class TestEventStoreAppend:
    """Tests for appending events."""

    def test_append_single_event(self, temp_village_dir: Path, world_snapshot: WorldSnapshot, sample_agent: AgentSnapshot):
        """Test appending a single event."""
        store = EventStore(temp_village_dir)
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
        )
        store.initialize(snapshot)

        event = AgentMovedEvent(
            tick=2,
            timestamp=datetime.now(),
            agent=sample_agent.name,
            from_location=sample_agent.location,
            to_location=LocationId("garden"),
        )
        store.append(event)

        # Event should be in log file
        assert store.event_log.exists()
        with open(store.event_log) as f:
            lines = f.readlines()
        assert len(lines) == 1

    def test_append_updates_state(self, temp_village_dir: Path, world_snapshot: WorldSnapshot, sample_agent: AgentSnapshot):
        """Test appending event updates in-memory state."""
        store = EventStore(temp_village_dir)
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
        )
        store.initialize(snapshot)

        event = AgentMovedEvent(
            tick=2,
            timestamp=datetime.now(),
            agent=sample_agent.name,
            from_location=sample_agent.location,
            to_location=LocationId("garden"),
        )
        store.append(event)

        current = store.get_current_snapshot()
        assert current.agents[sample_agent.name].location == LocationId("garden")

    def test_append_all_multiple_events(self, temp_village_dir: Path, world_snapshot: WorldSnapshot, sample_agent: AgentSnapshot):
        """Test appending multiple events atomically."""
        store = EventStore(temp_village_dir)
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
        )
        store.initialize(snapshot)

        now = datetime.now()
        events = [
            AgentMovedEvent(
                tick=2,
                timestamp=now,
                agent=sample_agent.name,
                from_location=sample_agent.location,
                to_location=LocationId("garden"),
            ),
            AgentMoodChangedEvent(
                tick=2,
                timestamp=now,
                agent=sample_agent.name,
                old_mood="curious",
                new_mood="happy",
            ),
        ]
        store.append_all(events)

        current = store.get_current_snapshot()
        assert current.agents[sample_agent.name].location == LocationId("garden")
        assert current.agents[sample_agent.name].mood == "happy"

    def test_append_empty_list_no_op(self, temp_village_dir: Path, world_snapshot: WorldSnapshot, sample_agent: AgentSnapshot):
        """Test appending empty list does nothing."""
        store = EventStore(temp_village_dir)
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
        )
        store.initialize(snapshot)

        store.append_all([])

        # No event log created
        assert not store.event_log.exists()


class TestEventStoreRecovery:
    """Tests for state recovery."""

    def test_recover_from_snapshot(self, temp_village_dir: Path, world_snapshot: WorldSnapshot, sample_agent: AgentSnapshot):
        """Test recovering from saved snapshot."""
        # Initialize and save
        store1 = EventStore(temp_village_dir)
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
        )
        store1.initialize(snapshot)

        # Recover in new store instance
        store2 = EventStore(temp_village_dir)
        recovered = store2.recover()

        assert recovered is not None
        assert recovered.tick == 1
        assert sample_agent.name in recovered.agents

    def test_recover_replays_events(self, temp_village_dir: Path, world_snapshot: WorldSnapshot, sample_agent: AgentSnapshot):
        """Test recovery replays events since snapshot."""
        store1 = EventStore(temp_village_dir)
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
        )
        store1.initialize(snapshot)

        # Append event
        event = AgentMovedEvent(
            tick=2,
            timestamp=datetime.now(),
            agent=sample_agent.name,
            from_location=sample_agent.location,
            to_location=LocationId("garden"),
        )
        store1.append(event)

        # Recover in new store
        store2 = EventStore(temp_village_dir)
        recovered = store2.recover()

        # Event should be replayed
        assert recovered.agents[sample_agent.name].location == LocationId("garden")

    def test_recover_no_snapshot_returns_none(self, temp_village_dir: Path):
        """Test recovery with no snapshot returns None."""
        store = EventStore(temp_village_dir)
        result = store.recover()

        assert result is None


class TestEventStoreApplyEvent:
    """Tests for event application to state."""

    def test_apply_agent_moved_event(self, temp_village_dir: Path, world_snapshot: WorldSnapshot, sample_agent: AgentSnapshot):
        """Test AgentMovedEvent updates location."""
        store = EventStore(temp_village_dir)
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
        )
        store.initialize(snapshot)

        event = AgentMovedEvent(
            tick=2,
            timestamp=datetime.now(),
            agent=sample_agent.name,
            from_location=LocationId("workshop"),
            to_location=LocationId("garden"),
        )
        store.append(event)

        current = store.get_current_snapshot()
        assert current.agents[sample_agent.name].location == LocationId("garden")
        assert current.world.agent_locations[sample_agent.name] == LocationId("garden")

    def test_apply_mood_changed_event(self, temp_village_dir: Path, world_snapshot: WorldSnapshot, sample_agent: AgentSnapshot):
        """Test AgentMoodChangedEvent updates mood."""
        store = EventStore(temp_village_dir)
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
        )
        store.initialize(snapshot)

        event = AgentMoodChangedEvent(
            tick=2,
            timestamp=datetime.now(),
            agent=sample_agent.name,
            old_mood="curious",
            new_mood="happy",
        )
        store.append(event)

        current = store.get_current_snapshot()
        assert current.agents[sample_agent.name].mood == "happy"

    def test_apply_slept_event(self, temp_village_dir: Path, world_snapshot: WorldSnapshot, sample_agent: AgentSnapshot):
        """Test AgentSleptEvent updates sleep state."""
        store = EventStore(temp_village_dir)
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
        )
        store.initialize(snapshot)

        event = AgentSleptEvent(
            tick=2,
            timestamp=datetime(2024, 6, 15, 22, 0, 0),  # Night time
            agent=sample_agent.name,
            location=sample_agent.location,
        )
        store.append(event)

        current = store.get_current_snapshot()
        assert current.agents[sample_agent.name].is_sleeping is True
        assert current.agents[sample_agent.name].sleep_started_tick == 2

    def test_apply_woke_event(self, temp_village_dir: Path, world_snapshot: WorldSnapshot, sleeping_agent: AgentSnapshot):
        """Test AgentWokeEvent clears sleep state."""
        store = EventStore(temp_village_dir)
        # Use world with sleeping agent
        world = WorldSnapshot(
            tick=1,
            world_time=datetime(2024, 6, 15, 10, 0, 0),
            start_date=datetime(2024, 6, 15, 0, 0, 0),
            weather=Weather.CLEAR,
            locations=world_snapshot.locations,
            agent_locations={sleeping_agent.name: sleeping_agent.location},
        )
        snapshot = VillageSnapshot(
            world=world,
            agents={sleeping_agent.name: sleeping_agent},
            conversations={},
            pending_invites={},
        )
        store.initialize(snapshot)

        event = AgentWokeEvent(
            tick=2,
            timestamp=datetime.now(),
            agent=sleeping_agent.name,
            location=sleeping_agent.location,
            reason="time_period_change",
        )
        store.append(event)

        current = store.get_current_snapshot()
        assert current.agents[sleeping_agent.name].is_sleeping is False
        assert current.agents[sleeping_agent.name].sleep_started_tick is None

    def test_apply_conversation_started_event(self, temp_village_dir: Path, world_snapshot: WorldSnapshot, sample_agent: AgentSnapshot):
        """Test ConversationStartedEvent creates conversation."""
        store = EventStore(temp_village_dir)
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
        )
        store.initialize(snapshot)

        conv_id = ConversationId("conv-new")
        event = ConversationStartedEvent(
            tick=2,
            timestamp=datetime.now(),
            conversation_id=conv_id,
            location=LocationId("workshop"),
            privacy="private",
            initial_participants=(AgentName("Ember"), AgentName("Sage")),
        )
        store.append(event)

        current = store.get_current_snapshot()
        assert conv_id in current.conversations
        assert AgentName("Ember") in current.conversations[conv_id].participants

    def test_apply_conversation_ended_event(self, temp_village_dir: Path, world_snapshot: WorldSnapshot, sample_agent: AgentSnapshot, sample_conversation):
        """Test ConversationEndedEvent removes conversation."""
        store = EventStore(temp_village_dir)
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={sample_conversation.id: sample_conversation},
            pending_invites={},
        )
        store.initialize(snapshot)

        event = ConversationEndedEvent(
            tick=2,
            timestamp=datetime.now(),
            conversation_id=sample_conversation.id,
            reason="ended",
            final_participants=tuple(sample_conversation.participants),
            summary="",
        )
        store.append(event)

        current = store.get_current_snapshot()
        assert sample_conversation.id not in current.conversations

    def test_apply_weather_changed_event(self, temp_village_dir: Path, world_snapshot: WorldSnapshot, sample_agent: AgentSnapshot):
        """Test WeatherChangedEvent updates weather."""
        store = EventStore(temp_village_dir)
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
        )
        store.initialize(snapshot)

        event = WeatherChangedEvent(
            tick=2,
            timestamp=datetime.now(),
            old_weather="clear",
            new_weather="rainy",
        )
        store.append(event)

        current = store.get_current_snapshot()
        assert current.world.weather == Weather.RAINY


class TestEventStoreQueries:
    """Tests for event queries."""

    def test_get_events_since(self, temp_village_dir: Path, world_snapshot: WorldSnapshot, sample_agent: AgentSnapshot):
        """Test getting events since a tick."""
        store = EventStore(temp_village_dir)
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
        )
        store.initialize(snapshot)

        # Add events at different ticks
        for tick in [2, 3, 4]:
            event = AgentMoodChangedEvent(
                tick=tick,
                timestamp=datetime.now(),
                agent=sample_agent.name,
                old_mood="curious",
                new_mood=f"mood_{tick}",
            )
            store.append(event)

        events = store.get_events_since(2)
        assert len(events) == 3  # tick 2, 3, and 4 (>= tick)

    def test_get_recent_events_limit(self, temp_village_dir: Path, world_snapshot: WorldSnapshot, sample_agent: AgentSnapshot):
        """Test get_recent_events respects limit."""
        store = EventStore(temp_village_dir)
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
        )
        store.initialize(snapshot)

        # Add multiple events
        for tick in range(2, 12):
            event = AgentMoodChangedEvent(
                tick=tick,
                timestamp=datetime.now(),
                agent=sample_agent.name,
                old_mood="curious",
                new_mood=f"mood_{tick}",
            )
            store.append(event)

        events = store.get_recent_events(limit=5)
        assert len(events) == 5

    def test_get_recent_events_type_filter(self, temp_village_dir: Path, world_snapshot: WorldSnapshot, sample_agent: AgentSnapshot):
        """Test get_recent_events filters by type."""
        store = EventStore(temp_village_dir)
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
        )
        store.initialize(snapshot)

        # Add mixed events
        store.append(AgentMoodChangedEvent(
            tick=2,
            timestamp=datetime.now(),
            agent=sample_agent.name,
            old_mood="curious",
            new_mood="happy",
        ))
        store.append(AgentMovedEvent(
            tick=3,
            timestamp=datetime.now(),
            agent=sample_agent.name,
            from_location=LocationId("workshop"),
            to_location=LocationId("garden"),
        ))

        events = store.get_recent_events(event_types={"agent_moved"})
        assert len(events) == 1
        assert events[0].type == "agent_moved"

    def test_get_recent_events_since_tick(self, temp_village_dir: Path, world_snapshot: WorldSnapshot, sample_agent: AgentSnapshot):
        """Test get_recent_events filters by since_tick (>= since_tick)."""
        store = EventStore(temp_village_dir)
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
        )
        store.initialize(snapshot)

        # Add events at ticks 1, 2, 3, 4, 5
        for tick in [1, 2, 3, 4, 5]:
            event = AgentMoodChangedEvent(
                tick=tick,
                timestamp=datetime.now(),
                agent=sample_agent.name,
                old_mood="curious",
                new_mood=f"mood_{tick}",
            )
            store.append(event)

        # since_tick=3 should return events at ticks 3, 4, 5 (>= 3)
        events = store.get_recent_events(since_tick=3)
        assert len(events) == 3
        assert [e.tick for e in events] == [3, 4, 5]

        # since_tick=0 should return all events (>= 0)
        events = store.get_recent_events(since_tick=0)
        assert len(events) == 5

        # since_tick=5 should return just tick 5
        events = store.get_recent_events(since_tick=5)
        assert len(events) == 1
        assert events[0].tick == 5

        # since_tick=6 should return nothing
        events = store.get_recent_events(since_tick=6)
        assert len(events) == 0


class TestEventStoreSnapshotAndArchive:
    """Tests for snapshot creation and archiving."""

    def test_create_snapshot_and_archive(self, temp_village_dir: Path, world_snapshot: WorldSnapshot, sample_agent: AgentSnapshot):
        """Test creating snapshot and archiving."""
        store = EventStore(temp_village_dir)
        # Create world at tick 100 to trigger archiving
        world = WorldSnapshot(
            tick=100,
            world_time=datetime.now(),
            start_date=datetime(2024, 6, 15, 0, 0, 0),
            weather=Weather.CLEAR,
            locations=world_snapshot.locations,
            agent_locations={sample_agent.name: sample_agent.location},
        )
        snapshot = VillageSnapshot(
            world=world,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
        )
        store.initialize(snapshot)

        store.create_snapshot_and_archive()

        # Snapshot should exist
        snapshots = list((temp_village_dir / "snapshots").glob("state_*.json"))
        assert len(snapshots) >= 1

    def test_set_scheduler_state(self, temp_village_dir: Path, world_snapshot: WorldSnapshot, sample_agent: AgentSnapshot):
        """Test setting scheduler state on snapshot."""
        from engine.services.scheduler import SchedulerState

        store = EventStore(temp_village_dir)
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
        )
        store.initialize(snapshot)

        scheduler_state = SchedulerState(
            queue=(),
            forced_next=AgentName("Ember"),
            skip_counts={},
            turn_counts={AgentName("Ember"): 5},
            last_location_speaker={},
        )
        store.set_scheduler_state(scheduler_state)

        current = store.get_current_snapshot()
        assert current.scheduler_state is not None
        assert current.scheduler_state.forced_next == AgentName("Ember")
        assert current.scheduler_state.turn_counts[AgentName("Ember")] == 5


class TestConversationTurnIsDeparture:
    """Tests for ConversationTurnEvent.is_departure handling."""

    def test_apply_turn_with_is_departure(
        self,
        temp_village_dir: Path,
        world_snapshot: WorldSnapshot,
        sample_agent: AgentSnapshot,
        sample_conversation,
    ):
        """Test ConversationTurnEvent with is_departure=True creates turn with flag."""
        store = EventStore(temp_village_dir)
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={sample_conversation.id: sample_conversation},
            pending_invites={},
        )
        store.initialize(snapshot)

        event = ConversationTurnEvent(
            tick=2,
            timestamp=datetime.now(),
            conversation_id=sample_conversation.id,
            speaker=AgentName("Ember"),
            narrative="Goodbye everyone!",
            is_departure=True,
        )
        store.append(event)

        current = store.get_current_snapshot()
        conv = current.conversations[sample_conversation.id]
        # Find the new turn (last one)
        last_turn = conv.history[-1]
        assert last_turn.speaker == AgentName("Ember")
        assert last_turn.narrative == "Goodbye everyone!"
        assert last_turn.is_departure is True

    def test_apply_turn_without_is_departure_defaults_false(
        self,
        temp_village_dir: Path,
        world_snapshot: WorldSnapshot,
        sample_agent: AgentSnapshot,
        sample_conversation,
    ):
        """Test ConversationTurnEvent without is_departure defaults to False."""
        store = EventStore(temp_village_dir)
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={sample_conversation.id: sample_conversation},
            pending_invites={},
        )
        store.initialize(snapshot)

        event = ConversationTurnEvent(
            tick=2,
            timestamp=datetime.now(),
            conversation_id=sample_conversation.id,
            speaker=AgentName("Ember"),
            narrative="Hello!",
        )
        store.append(event)

        current = store.get_current_snapshot()
        conv = current.conversations[sample_conversation.id]
        last_turn = conv.history[-1]
        assert last_turn.is_departure is False


class TestConversationEndingUnseenEvents:
    """Tests for ConversationEndingUnseen/Seen event handling."""

    def test_apply_unseen_event_adds_to_unseen_endings(
        self,
        temp_village_dir: Path,
        world_snapshot: WorldSnapshot,
        sample_agent: AgentSnapshot,
    ):
        """Test ConversationEndingUnseenEvent adds to unseen_endings."""
        store = EventStore(temp_village_dir)
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
        )
        store.initialize(snapshot)

        event = ConversationEndingUnseenEvent(
            tick=2,
            timestamp=datetime.now(),
            agent=AgentName("Ember"),
            conversation_id=ConversationId("conv-ended"),
            other_participant=AgentName("Sage"),
            final_message="Goodbye!",
        )
        store.append(event)

        current = store.get_current_snapshot()
        assert current.unseen_endings is not None
        assert AgentName("Ember") in current.unseen_endings
        endings = current.unseen_endings[AgentName("Ember")]
        assert len(endings) == 1
        assert endings[0].conversation_id == ConversationId("conv-ended")
        assert endings[0].other_participant == AgentName("Sage")
        assert endings[0].final_message == "Goodbye!"

    def test_apply_seen_event_removes_from_unseen_endings(
        self,
        temp_village_dir: Path,
        world_snapshot: WorldSnapshot,
        sample_agent: AgentSnapshot,
    ):
        """Test ConversationEndingSeenEvent removes from unseen_endings."""
        # Create snapshot with existing unseen ending
        ending = UnseenConversationEnding(
            conversation_id=ConversationId("conv-ended"),
            other_participant=AgentName("Sage"),
            final_message="Goodbye!",
            ended_at_tick=1,
        )
        store = EventStore(temp_village_dir)
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
            unseen_endings={AgentName("Ember"): [ending]},
        )
        store.initialize(snapshot)

        # Verify it exists
        current = store.get_current_snapshot()
        assert len(current.unseen_endings[AgentName("Ember")]) == 1

        # Apply seen event
        event = ConversationEndingSeenEvent(
            tick=2,
            timestamp=datetime.now(),
            agent=AgentName("Ember"),
            conversation_id=ConversationId("conv-ended"),
        )
        store.append(event)

        current = store.get_current_snapshot()
        # Should be removed - unseen_endings may be None when empty
        ember_endings = (current.unseen_endings or {}).get(AgentName("Ember"), [])
        assert len(ember_endings) == 0

    def test_apply_multiple_unseen_events_for_same_agent(
        self,
        temp_village_dir: Path,
        world_snapshot: WorldSnapshot,
        sample_agent: AgentSnapshot,
    ):
        """Test multiple ConversationEndingUnseenEvent for same agent accumulate."""
        store = EventStore(temp_village_dir)
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
        )
        store.initialize(snapshot)

        # Add two unseen events
        event1 = ConversationEndingUnseenEvent(
            tick=2,
            timestamp=datetime.now(),
            agent=AgentName("Ember"),
            conversation_id=ConversationId("conv-1"),
            other_participant=AgentName("Sage"),
            final_message="Bye from Sage!",
        )
        event2 = ConversationEndingUnseenEvent(
            tick=3,
            timestamp=datetime.now(),
            agent=AgentName("Ember"),
            conversation_id=ConversationId("conv-2"),
            other_participant=AgentName("River"),
            final_message="Bye from River!",
        )
        store.append(event1)
        store.append(event2)

        current = store.get_current_snapshot()
        endings = current.unseen_endings[AgentName("Ember")]
        assert len(endings) == 2
        conv_ids = {e.conversation_id for e in endings}
        assert ConversationId("conv-1") in conv_ids
        assert ConversationId("conv-2") in conv_ids
