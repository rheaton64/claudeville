"""
Level 1 Integration Tests: Event Store Recovery

Tests that the EventStore correctly persists events and recovers
state through event replay. This validates the event sourcing
foundation of engine.

Run with: uv run pytest tests/integration/test_event_store.py -v
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from engine.domain import (
    AgentName,
    LocationId,
    ConversationId,
    AgentMovedEvent,
    AgentMoodChangedEvent,
    AgentActionEvent,
    AgentSleptEvent,
    AgentWokeEvent,
    ConversationInvitedEvent,
    ConversationInviteAcceptedEvent,
    ConversationStartedEvent,
    ConversationTurnEvent,
    ConversationLeftEvent,
    ConversationEndedEvent,
    Weather,
    WeatherChangedEvent,
)
from engine.storage import EventStore, VillageSnapshot
from tests.integration.fixtures import create_test_village


# =============================================================================
# Basic Recovery Tests
# =============================================================================


class TestBasicRecovery:
    """Test basic event store initialization and recovery."""

    def test_initialize_creates_snapshot(self, temp_village: Path):
        """Initialize should create and persist initial snapshot."""
        store = EventStore(temp_village)
        snapshot = create_test_village()
        store.initialize(snapshot)

        # Should have current snapshot
        current = store.get_current_snapshot()
        assert current is not None
        assert current.tick == 0
        assert len(current.agents) == 3

        # Snapshot file should exist
        snapshot_files = list((temp_village / "snapshots").glob("*.json"))
        assert len(snapshot_files) == 1

    def test_recover_empty_store_returns_none(self, temp_village: Path):
        """Recovering from empty store should return None."""
        store = EventStore(temp_village)
        result = store.recover()
        assert result is None

    def test_recover_after_initialize(self, temp_village: Path):
        """Recovery should restore initial state."""
        # Initialize first store
        store1 = EventStore(temp_village)
        snapshot = create_test_village()
        store1.initialize(snapshot)

        # Create new store and recover
        store2 = EventStore(temp_village)
        recovered = store2.recover()

        assert recovered is not None
        assert recovered.tick == 0
        assert len(recovered.agents) == 3


# =============================================================================
# Event Replay Tests
# =============================================================================


class TestEventReplay:
    """Test event replay correctly updates state."""

    def test_movement_event_updates_location(self, initialized_event_store: EventStore):
        """AgentMovedEvent should update agent location."""
        store = initialized_event_store
        initial = store.get_current_snapshot()

        # Verify Alice starts at workshop
        assert initial.agents[AgentName("Alice")].location == LocationId("workshop")

        # Apply movement event
        event = AgentMovedEvent(
            tick=1,
            timestamp=datetime.now(),
            agent=AgentName("Alice"),
            from_location=LocationId("workshop"),
            to_location=LocationId("garden"),
        )
        store.append(event)

        # Verify location updated
        current = store.get_current_snapshot()
        assert current.agents[AgentName("Alice")].location == LocationId("garden")

    def test_mood_event_updates_mood(self, initialized_event_store: EventStore):
        """AgentMoodChangedEvent should update agent mood."""
        store = initialized_event_store
        initial = store.get_current_snapshot()

        # Verify Alice starts curious
        assert initial.agents[AgentName("Alice")].mood == "curious"

        # Apply mood event
        event = AgentMoodChangedEvent(
            tick=1,
            timestamp=datetime.now(),
            agent=AgentName("Alice"),
            old_mood="curious",
            new_mood="peaceful",
        )
        store.append(event)

        # Verify mood updated
        current = store.get_current_snapshot()
        assert current.agents[AgentName("Alice")].mood == "peaceful"

    def test_sleep_wake_cycle(self, initialized_event_store: EventStore):
        """Sleep and wake events should update is_sleeping."""
        store = initialized_event_store
        initial = store.get_current_snapshot()

        # Alice starts awake
        assert not initial.agents[AgentName("Alice")].is_sleeping

        # Alice goes to sleep
        sleep_event = AgentSleptEvent(
            tick=1,
            timestamp=datetime.now(),
            agent=AgentName("Alice"),
            location=LocationId("workshop"),
        )
        store.append(sleep_event)

        current = store.get_current_snapshot()
        assert current.agents[AgentName("Alice")].is_sleeping is True
        assert current.agents[AgentName("Alice")].sleep_started_tick == 1

        # Alice wakes up
        wake_event = AgentWokeEvent(
            tick=5,
            timestamp=datetime.now(),
            agent=AgentName("Alice"),
            location=LocationId("workshop"),
            reason="time_period_changed",
        )
        store.append(wake_event)

        current = store.get_current_snapshot()
        assert current.agents[AgentName("Alice")].is_sleeping is False

    def test_weather_event_updates_world(self, initialized_event_store: EventStore):
        """WeatherChangedEvent should update world weather."""
        store = initialized_event_store
        initial = store.get_current_snapshot()

        assert initial.world.weather == Weather.CLEAR

        event = WeatherChangedEvent(
            tick=1,
            timestamp=datetime.now(),
            old_weather="clear",
            new_weather="rainy",
        )
        store.append(event)

        current = store.get_current_snapshot()
        assert current.world.weather == Weather.RAINY


# =============================================================================
# Conversation Event Sequence Tests
# =============================================================================


class TestConversationEventSequence:
    """Test full conversation lifecycle through events."""

    def test_conversation_invite_creates_pending(
        self, initialized_event_store: EventStore
    ):
        """ConversationInvitedEvent should create pending invite."""
        store = initialized_event_store
        conv_id = ConversationId("conv-test-001")

        event = ConversationInvitedEvent(
            tick=1,
            timestamp=datetime.now(),
            conversation_id=conv_id,
            inviter=AgentName("Alice"),
            invitee=AgentName("Bob"),
            location=LocationId("workshop"),
            privacy="private",
        )
        store.append(event)

        current = store.get_current_snapshot()
        assert AgentName("Bob") in current.pending_invites
        invite = current.pending_invites[AgentName("Bob")]
        assert invite.inviter == AgentName("Alice")
        assert invite.conversation_id == conv_id

    def test_full_conversation_lifecycle(self, initialized_event_store: EventStore):
        """Full conversation lifecycle: invite → accept → start → turns → end."""
        store = initialized_event_store
        conv_id = ConversationId("conv-test-002")
        now = datetime.now()

        # 1. Alice invites Bob
        invite_event = ConversationInvitedEvent(
            tick=1,
            timestamp=now,
            conversation_id=conv_id,
            inviter=AgentName("Alice"),
            invitee=AgentName("Bob"),
            location=LocationId("workshop"),
            privacy="private",
        )
        store.append(invite_event)

        # Verify pending invite
        current = store.get_current_snapshot()
        assert AgentName("Bob") in current.pending_invites

        # 2. Bob accepts
        accept_event = ConversationInviteAcceptedEvent(
            tick=2,
            timestamp=now + timedelta(minutes=5),
            conversation_id=conv_id,
            inviter=AgentName("Alice"),
            invitee=AgentName("Bob"),
        )
        store.append(accept_event)

        # Pending invite should be removed
        current = store.get_current_snapshot()
        assert AgentName("Bob") not in current.pending_invites

        # 3. Conversation starts
        start_event = ConversationStartedEvent(
            tick=2,
            timestamp=now + timedelta(minutes=5),
            conversation_id=conv_id,
            location=LocationId("workshop"),
            privacy="private",
            initial_participants=(AgentName("Alice"), AgentName("Bob")),
        )
        store.append(start_event)

        # Verify conversation created
        current = store.get_current_snapshot()
        assert conv_id in current.conversations
        conv = current.conversations[conv_id]
        assert AgentName("Alice") in conv.participants
        assert AgentName("Bob") in conv.participants

        # 4. Alice speaks
        turn1_event = ConversationTurnEvent(
            tick=3,
            timestamp=now + timedelta(minutes=10),
            conversation_id=conv_id,
            speaker=AgentName("Alice"),
            narrative="Hello Bob! How are you today?",
        )
        store.append(turn1_event)

        current = store.get_current_snapshot()
        conv = current.conversations[conv_id]
        assert len(conv.history) == 1
        assert conv.history[0].speaker == AgentName("Alice")

        # 5. Bob speaks
        turn2_event = ConversationTurnEvent(
            tick=4,
            timestamp=now + timedelta(minutes=15),
            conversation_id=conv_id,
            speaker=AgentName("Bob"),
            narrative="I'm doing well, thanks for asking!",
        )
        store.append(turn2_event)

        current = store.get_current_snapshot()
        conv = current.conversations[conv_id]
        assert len(conv.history) == 2

        # 6. Alice leaves
        leave_event = ConversationLeftEvent(
            tick=5,
            timestamp=now + timedelta(minutes=20),
            conversation_id=conv_id,
            agent=AgentName("Alice"),
        )
        store.append(leave_event)

        current = store.get_current_snapshot()
        conv = current.conversations[conv_id]
        assert AgentName("Alice") not in conv.participants

        # 7. Conversation ends
        end_event = ConversationEndedEvent(
            tick=5,
            timestamp=now + timedelta(minutes=20),
            conversation_id=conv_id,
            reason="all_left",
            final_participants=(AgentName("Bob"),),
            summary="A friendly greeting between Alice and Bob.",
        )
        store.append(end_event)

        # Conversation should be removed
        current = store.get_current_snapshot()
        assert conv_id not in current.conversations


# =============================================================================
# Recovery After Events Tests
# =============================================================================


class TestRecoveryAfterEvents:
    """Test recovery correctly replays events."""

    def test_recovery_replays_all_events(self, temp_village: Path):
        """Recovery should replay events and restore correct state."""
        # Initialize and add events
        store1 = EventStore(temp_village)
        snapshot = create_test_village()
        store1.initialize(snapshot)

        now = datetime.now()

        # Add several events
        events = [
            AgentMovedEvent(
                tick=1,
                timestamp=now,
                agent=AgentName("Alice"),
                from_location=LocationId("workshop"),
                to_location=LocationId("garden"),
            ),
            AgentMoodChangedEvent(
                tick=1,
                timestamp=now,
                agent=AgentName("Alice"),
                old_mood="curious",
                new_mood="peaceful",
            ),
            AgentActionEvent(
                tick=2,
                timestamp=now + timedelta(minutes=5),
                agent=AgentName("Bob"),
                location=LocationId("library"),
                description="read a book",
            ),
        ]
        store1.append_all(events)

        # Create new store and recover
        store2 = EventStore(temp_village)
        recovered = store2.recover()

        # State should match
        assert recovered is not None
        assert recovered.agents[AgentName("Alice")].location == LocationId("garden")
        assert recovered.agents[AgentName("Alice")].mood == "peaceful"

    def test_recovery_with_conversation(self, temp_village: Path):
        """Recovery should restore active conversations."""
        # Initialize and create conversation
        store1 = EventStore(temp_village)
        snapshot = create_test_village()
        store1.initialize(snapshot)

        conv_id = ConversationId("conv-recovery-001")
        now = datetime.now()

        events = [
            ConversationStartedEvent(
                tick=1,
                timestamp=now,
                conversation_id=conv_id,
                location=LocationId("workshop"),
                privacy="public",
                initial_participants=(AgentName("Alice"), AgentName("Bob")),
            ),
            ConversationTurnEvent(
                tick=2,
                timestamp=now + timedelta(minutes=5),
                conversation_id=conv_id,
                speaker=AgentName("Alice"),
                narrative="Hello!",
            ),
        ]
        store1.append_all(events)

        # Recover in new store
        store2 = EventStore(temp_village)
        recovered = store2.recover()

        assert recovered is not None
        assert conv_id in recovered.conversations
        conv = recovered.conversations[conv_id]
        assert len(conv.history) == 1


# =============================================================================
# Snapshot and Archive Tests
# =============================================================================


class TestSnapshotAndArchive:
    """Test snapshot creation and event archiving."""

    def test_create_snapshot_saves_state(self, initialized_event_store: EventStore):
        """create_snapshot_and_archive should save current state."""
        store = initialized_event_store

        # Add some events
        for i in range(5):
            event = AgentActionEvent(
                tick=i + 1,
                timestamp=datetime.now(),
                agent=AgentName("Alice"),
                location=LocationId("workshop"),
                description=f"action {i}",
            )
            store.append(event)

        # Create snapshot
        store.create_snapshot_and_archive()

        # Snapshot should exist
        snapshot_files = list(
            (store.village_root / "snapshots").glob("*.json")
        )
        assert len(snapshot_files) >= 1

    def test_events_persisted_to_file(self, initialized_event_store: EventStore):
        """Events should be written to events.jsonl."""
        store = initialized_event_store

        # Add event
        event = AgentMovedEvent(
            tick=1,
            timestamp=datetime.now(),
            agent=AgentName("Alice"),
            from_location=LocationId("workshop"),
            to_location=LocationId("garden"),
        )
        store.append(event)

        # Read events file
        events_file = store.village_root / "events.jsonl"
        assert events_file.exists()

        with open(events_file) as f:
            lines = f.readlines()

        assert len(lines) == 1
        assert "agent_moved" in lines[0]

    def test_get_recent_events(self, initialized_event_store: EventStore):
        """get_recent_events should return recent events."""
        store = initialized_event_store

        # Add multiple events
        now = datetime.now()
        for i in range(10):
            event = AgentActionEvent(
                tick=i + 1,
                timestamp=now + timedelta(minutes=i),
                agent=AgentName("Alice"),
                location=LocationId("workshop"),
                description=f"action {i}",
            )
            store.append(event)

        # Get recent events
        recent = store.get_recent_events(limit=5)
        assert len(recent) == 5

        # Should be most recent
        assert recent[-1].tick == 10

    def test_get_recent_events_with_filter(self, initialized_event_store: EventStore):
        """get_recent_events should filter by event type."""
        store = initialized_event_store

        now = datetime.now()
        # Add mixed events
        store.append(AgentMovedEvent(
            tick=1,
            timestamp=now,
            agent=AgentName("Alice"),
            from_location=LocationId("workshop"),
            to_location=LocationId("garden"),
        ))
        store.append(AgentActionEvent(
            tick=2,
            timestamp=now + timedelta(minutes=1),
            agent=AgentName("Alice"),
            location=LocationId("garden"),
            description="pick flowers",
        ))
        store.append(AgentMoodChangedEvent(
            tick=3,
            timestamp=now + timedelta(minutes=2),
            agent=AgentName("Alice"),
            old_mood="curious",
            new_mood="peaceful",
        ))

        # Filter by type
        mood_events = store.get_recent_events(
            limit=10,
            event_types={"agent_mood_changed"},
        )
        assert len(mood_events) == 1
        assert mood_events[0].type == "agent_mood_changed"


# =============================================================================
# Batch Operations Tests
# =============================================================================


class TestBatchOperations:
    """Test batch event operations."""

    def test_append_all_atomic(self, initialized_event_store: EventStore):
        """append_all should apply all events atomically."""
        store = initialized_event_store
        now = datetime.now()

        events = [
            AgentMovedEvent(
                tick=1,
                timestamp=now,
                agent=AgentName("Alice"),
                from_location=LocationId("workshop"),
                to_location=LocationId("library"),
            ),
            AgentMovedEvent(
                tick=1,
                timestamp=now,
                agent=AgentName("Bob"),
                from_location=LocationId("library"),
                to_location=LocationId("garden"),
            ),
            AgentMoodChangedEvent(
                tick=1,
                timestamp=now,
                agent=AgentName("Carol"),
                old_mood="peaceful",
                new_mood="excited",
            ),
        ]

        store.append_all(events)

        current = store.get_current_snapshot()
        assert current.agents[AgentName("Alice")].location == LocationId("library")
        assert current.agents[AgentName("Bob")].location == LocationId("garden")
        assert current.agents[AgentName("Carol")].mood == "excited"

    def test_append_all_empty_list(self, initialized_event_store: EventStore):
        """append_all with empty list should be no-op."""
        store = initialized_event_store
        before = store.get_current_snapshot()

        store.append_all([])

        after = store.get_current_snapshot()
        # State should be unchanged
        assert before.tick == after.tick


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_get_snapshot_before_initialize_raises(self, temp_village: Path):
        """get_current_snapshot before initialize should raise."""
        store = EventStore(temp_village)

        with pytest.raises(RuntimeError, match="not initialized"):
            store.get_current_snapshot()

    def test_events_since_empty(self, initialized_event_store: EventStore):
        """get_events_since with no events should return empty list."""
        store = initialized_event_store
        events = store.get_events_since(0)
        assert events == []

    def test_tick_updates_on_events(self, initialized_event_store: EventStore):
        """World tick should update as events are applied."""
        store = initialized_event_store
        initial = store.get_current_snapshot()
        assert initial.tick == 0

        # Add event at tick 5
        event = AgentActionEvent(
            tick=5,
            timestamp=datetime.now(),
            agent=AgentName("Alice"),
            location=LocationId("workshop"),
            description="test",
        )
        store.append(event)

        current = store.get_current_snapshot()
        assert current.tick == 5
