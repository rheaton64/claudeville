"""Tests for engine.observer.snapshots module."""

import pytest
from datetime import datetime

from engine.domain import (
    AgentName,
    AgentSnapshot,
    AgentLLMModel,
    Conversation,
    ConversationId,
    ConversationTurn,
    Invitation,
    LocationId,
    TimeSnapshot,
    TimePeriod,
)
from engine.observer.snapshots import (
    AgentDisplaySnapshot,
    ConversationDisplaySnapshot,
    InviteDisplaySnapshot,
    ScheduleDisplaySnapshot,
    ScheduledEventDisplay,
    TimeDisplaySnapshot,
    VillageDisplaySnapshot,
)
from engine.services.scheduler import ScheduledEvent


class TestAgentDisplaySnapshot:
    """Tests for AgentDisplaySnapshot."""

    def test_from_domain(self, sample_agent: AgentSnapshot):
        """Test creating from domain AgentSnapshot."""
        display = AgentDisplaySnapshot.from_domain(
            agent=sample_agent,
            in_conversation=True,
            has_pending_invite=False,
        )

        assert display.name == sample_agent.name
        assert display.model_display == sample_agent.model.display_name
        assert display.location == sample_agent.location
        assert display.mood == sample_agent.mood
        assert display.energy == sample_agent.energy
        assert display.is_sleeping == sample_agent.is_sleeping
        assert display.in_conversation is True
        assert display.has_pending_invite is False

    def test_defaults_false(self, sample_agent: AgentSnapshot):
        """Test conversation flags default to False."""
        display = AgentDisplaySnapshot.from_domain(agent=sample_agent)

        assert display.in_conversation is False
        assert display.has_pending_invite is False

    def test_frozen(self, sample_agent: AgentSnapshot):
        """Test display snapshot is frozen."""
        display = AgentDisplaySnapshot.from_domain(agent=sample_agent)

        with pytest.raises(Exception):  # FrozenInstanceError
            display.mood = "other"


class TestConversationDisplaySnapshot:
    """Tests for ConversationDisplaySnapshot."""

    def test_from_domain(self, sample_conversation: Conversation):
        """Test creating from domain Conversation."""
        display = ConversationDisplaySnapshot.from_domain(sample_conversation)

        assert display.id == sample_conversation.id
        assert display.location == sample_conversation.location
        assert display.participants == tuple(sorted(sample_conversation.participants))
        assert display.privacy == sample_conversation.privacy

    def test_turn_count(self, sample_conversation: Conversation):
        """Test turn count is calculated."""
        display = ConversationDisplaySnapshot.from_domain(sample_conversation)

        assert display.turn_count == len(sample_conversation.history)

    def test_last_speaker_from_history(self):
        """Test last speaker is extracted from history."""
        conv = Conversation(
            id=ConversationId("conv1"),
            location=LocationId("workshop"),
            participants=frozenset({AgentName("Ember"), AgentName("Sage")}),
            privacy="public",
            started_at_tick=1,
            created_by=AgentName("Ember"),
            history=(
                ConversationTurn(
                    speaker=AgentName("Ember"),
                    narrative="Hello.",
                    tick=1,
                    timestamp=datetime.now(),
                ),
                ConversationTurn(
                    speaker=AgentName("Sage"),
                    narrative="Hi there.",
                    tick=2,
                    timestamp=datetime.now(),
                ),
            ),
        )

        display = ConversationDisplaySnapshot.from_domain(conv)

        assert display.last_speaker == "Sage"

    def test_last_speaker_none_when_empty(self):
        """Test last speaker is None when no history."""
        conv = Conversation(
            id=ConversationId("conv1"),
            location=LocationId("workshop"),
            participants=frozenset({AgentName("Ember"), AgentName("Sage")}),
            privacy="public",
            started_at_tick=1,
            created_by=AgentName("Ember"),
            history=(),
        )

        display = ConversationDisplaySnapshot.from_domain(conv)

        assert display.last_speaker is None


class TestInviteDisplaySnapshot:
    """Tests for InviteDisplaySnapshot."""

    def test_from_domain(self, sample_invitation: Invitation):
        """Test creating from domain Invitation."""
        display = InviteDisplaySnapshot.from_domain(sample_invitation)

        assert display.conversation_id == sample_invitation.conversation_id
        assert display.inviter == sample_invitation.inviter
        assert display.invitee == sample_invitation.invitee
        assert display.location == sample_invitation.location
        assert display.privacy == sample_invitation.privacy
        assert display.invited_at == sample_invitation.invited_at


class TestScheduledEventDisplay:
    """Tests for ScheduledEventDisplay."""

    def test_from_domain(self):
        """Test creating from domain ScheduledEvent."""
        event = ScheduledEvent(
            due_time=datetime(2024, 6, 15, 12, 0),
            event_type="agent_turn",
            target_id="Ember",
            location_id=LocationId("workshop"),
            priority=10,
        )

        display = ScheduledEventDisplay.from_domain(event)

        assert display.due_time == event.due_time
        assert display.event_type == "agent_turn"
        assert display.target_id == "Ember"
        assert display.location == LocationId("workshop")


class TestTimeDisplaySnapshot:
    """Tests for TimeDisplaySnapshot."""

    def test_from_domain(self):
        """Test creating from domain TimeSnapshot."""
        ts = TimeSnapshot(
            world_time=datetime(2024, 6, 15, 14, 30),
            tick=42,
            start_date=datetime(2024, 6, 12, 0, 0, 0),  # 3 days ago
        )

        display = TimeDisplaySnapshot.from_domain(tick=42, time_snapshot=ts)

        assert display.tick == 42
        assert display.timestamp == ts.timestamp
        assert display.day_number == 4  # computed from start_date
        assert display.time_of_day == "afternoon"
        assert display.clock_time == "14:30"

    def test_clock_time_format(self):
        """Test clock time formatting with padding."""
        ts = TimeSnapshot(
            world_time=datetime(2024, 6, 15, 8, 5),
            tick=1,
            start_date=datetime(2024, 6, 15, 0, 0, 0),
        )

        display = TimeDisplaySnapshot.from_domain(tick=1, time_snapshot=ts)

        assert display.clock_time == "08:05"  # Zero-padded


class TestScheduleDisplaySnapshot:
    """Tests for ScheduleDisplaySnapshot."""

    def test_creation(self):
        """Test creating a schedule display snapshot."""
        event_display = ScheduledEventDisplay(
            due_time=datetime(2024, 6, 15, 12, 0),
            event_type="agent_turn",
            target_id="Ember",
            location="workshop",
        )

        schedule = ScheduleDisplaySnapshot(
            pending_events=(event_display,),
            forced_next="Sage",
            skip_counts={"River": 2},
            turn_counts={"Ember": 5, "Sage": 3},
        )

        assert len(schedule.pending_events) == 1
        assert schedule.forced_next == "Sage"
        assert schedule.skip_counts["River"] == 2
        assert schedule.turn_counts["Ember"] == 5


class TestVillageDisplaySnapshot:
    """Tests for VillageDisplaySnapshot."""

    def test_creation(self, sample_agent: AgentSnapshot):
        """Test creating a complete village display snapshot."""
        time_display = TimeDisplaySnapshot(
            tick=10,
            timestamp=datetime(2024, 6, 15, 12, 0),
            day_number=1,
            time_of_day="morning",
            clock_time="12:00",
        )

        agent_display = AgentDisplaySnapshot.from_domain(sample_agent)

        schedule_display = ScheduleDisplaySnapshot(
            pending_events=(),
            forced_next=None,
            skip_counts={},
            turn_counts={},
        )

        village = VillageDisplaySnapshot(
            tick=10,
            time=time_display,
            weather="clear",
            agents={"Ember": agent_display},
            conversations=[],
            pending_invites=[],
            schedule=schedule_display,
        )

        assert village.tick == 10
        assert village.time.tick == 10
        assert village.weather == "clear"
        assert "Ember" in village.agents
        assert len(village.conversations) == 0
        assert len(village.pending_invites) == 0
