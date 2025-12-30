"""Tests for engine.domain.events module."""

import pytest
from datetime import datetime
from pydantic import TypeAdapter, ValidationError

from engine.domain import (
    AgentName,
    LocationId,
    ConversationId,
)
from engine.domain.events import (
    DomainEvent,
    AgentMovedEvent,
    AgentMoodChangedEvent,
    AgentEnergyChangedEvent,
    AgentActionEvent,
    AgentSleptEvent,
    AgentWokeEvent,
    ConversationInvitedEvent,
    ConversationInviteAcceptedEvent,
    ConversationInviteDeclinedEvent,
    ConversationInviteExpiredEvent,
    ConversationStartedEvent,
    ConversationJoinedEvent,
    ConversationLeftEvent,
    ConversationTurnEvent,
    ConversationNextSpeakerSetEvent,
    ConversationMovedEvent,
    ConversationEndedEvent,
    WorldEventOccurred,
    WeatherChangedEvent,
)


# Type adapter for discriminated union
EventAdapter = TypeAdapter(DomainEvent)


@pytest.fixture
def base_tick() -> int:
    return 5


@pytest.fixture
def base_timestamp() -> datetime:
    return datetime(2024, 6, 15, 14, 0, 0)


class TestAgentMovedEvent:
    """Tests for AgentMovedEvent."""

    def test_creation(self, base_tick: int, base_timestamp: datetime):
        """Test creating an AgentMovedEvent."""
        event = AgentMovedEvent(
            tick=base_tick,
            timestamp=base_timestamp,
            agent=AgentName("Ember"),
            from_location=LocationId("workshop"),
            to_location=LocationId("garden"),
        )
        assert event.type == "agent_moved"
        assert event.tick == base_tick
        assert event.agent == "Ember"

    def test_immutability(self, base_tick: int, base_timestamp: datetime):
        """Test event is frozen."""
        event = AgentMovedEvent(
            tick=base_tick,
            timestamp=base_timestamp,
            agent=AgentName("Ember"),
            from_location=LocationId("a"),
            to_location=LocationId("b"),
        )
        with pytest.raises(ValidationError):
            event.tick = 999  # type: ignore


class TestAgentMoodChangedEvent:
    """Tests for AgentMoodChangedEvent."""

    def test_creation(self, base_tick: int, base_timestamp: datetime):
        """Test creating an AgentMoodChangedEvent."""
        event = AgentMoodChangedEvent(
            tick=base_tick,
            timestamp=base_timestamp,
            agent=AgentName("Sage"),
            old_mood="calm",
            new_mood="excited",
        )
        assert event.type == "agent_mood_changed"
        assert event.old_mood == "calm"
        assert event.new_mood == "excited"


class TestAgentEnergyChangedEvent:
    """Tests for AgentEnergyChangedEvent."""

    def test_creation(self, base_tick: int, base_timestamp: datetime):
        """Test creating an AgentEnergyChangedEvent."""
        event = AgentEnergyChangedEvent(
            tick=base_tick,
            timestamp=base_timestamp,
            agent=AgentName("River"),
            old_energy=80,
            new_energy=60,
        )
        assert event.type == "agent_energy_changed"
        assert event.old_energy == 80
        assert event.new_energy == 60


class TestAgentActionEvent:
    """Tests for AgentActionEvent."""

    def test_creation(self, base_tick: int, base_timestamp: datetime):
        """Test creating an AgentActionEvent."""
        event = AgentActionEvent(
            tick=base_tick,
            timestamp=base_timestamp,
            agent=AgentName("Ember"),
            location=LocationId("workshop"),
            description="Started painting a beautiful sunset.",
        )
        assert event.type == "agent_action"
        assert event.description == "Started painting a beautiful sunset."


class TestAgentSleptEvent:
    """Tests for AgentSleptEvent."""

    def test_creation(self, base_tick: int, base_timestamp: datetime):
        """Test creating an AgentSleptEvent."""
        event = AgentSleptEvent(
            tick=base_tick,
            timestamp=base_timestamp,
            agent=AgentName("Luna"),
            location=LocationId("garden"),
        )
        assert event.type == "agent_slept"


class TestAgentWokeEvent:
    """Tests for AgentWokeEvent."""

    def test_creation(self, base_tick: int, base_timestamp: datetime):
        """Test creating an AgentWokeEvent."""
        event = AgentWokeEvent(
            tick=base_tick,
            timestamp=base_timestamp,
            agent=AgentName("Luna"),
            location=LocationId("garden"),
            reason="time_period_changed",
        )
        assert event.type == "agent_woke"
        assert event.reason == "time_period_changed"


class TestConversationInvitedEvent:
    """Tests for ConversationInvitedEvent."""

    def test_creation(self, base_tick: int, base_timestamp: datetime):
        """Test creating a ConversationInvitedEvent."""
        event = ConversationInvitedEvent(
            tick=base_tick,
            timestamp=base_timestamp,
            conversation_id=ConversationId("conv-001"),
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            location=LocationId("workshop"),
            privacy="private",
        )
        assert event.type == "conversation_invited"
        assert event.privacy == "private"


class TestConversationInviteAcceptedEvent:
    """Tests for ConversationInviteAcceptedEvent."""

    def test_creation(self, base_tick: int, base_timestamp: datetime):
        """Test creating a ConversationInviteAcceptedEvent."""
        event = ConversationInviteAcceptedEvent(
            tick=base_tick,
            timestamp=base_timestamp,
            conversation_id=ConversationId("conv-001"),
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
        )
        assert event.type == "conversation_invite_accepted"


class TestConversationInviteDeclinedEvent:
    """Tests for ConversationInviteDeclinedEvent."""

    def test_creation(self, base_tick: int, base_timestamp: datetime):
        """Test creating a ConversationInviteDeclinedEvent."""
        event = ConversationInviteDeclinedEvent(
            tick=base_tick,
            timestamp=base_timestamp,
            conversation_id=ConversationId("conv-001"),
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
        )
        assert event.type == "conversation_invite_declined"


class TestConversationInviteExpiredEvent:
    """Tests for ConversationInviteExpiredEvent."""

    def test_creation(self, base_tick: int, base_timestamp: datetime):
        """Test creating a ConversationInviteExpiredEvent."""
        event = ConversationInviteExpiredEvent(
            tick=base_tick,
            timestamp=base_timestamp,
            conversation_id=ConversationId("conv-001"),
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
        )
        assert event.type == "conversation_invite_expired"


class TestConversationStartedEvent:
    """Tests for ConversationStartedEvent."""

    def test_creation(self, base_tick: int, base_timestamp: datetime):
        """Test creating a ConversationStartedEvent."""
        event = ConversationStartedEvent(
            tick=base_tick,
            timestamp=base_timestamp,
            conversation_id=ConversationId("conv-001"),
            location=LocationId("workshop"),
            privacy="private",
            initial_participants=(AgentName("Ember"), AgentName("Sage")),
        )
        assert event.type == "conversation_started"
        assert len(event.initial_participants) == 2


class TestConversationJoinedEvent:
    """Tests for ConversationJoinedEvent."""

    def test_creation(self, base_tick: int, base_timestamp: datetime):
        """Test creating a ConversationJoinedEvent."""
        event = ConversationJoinedEvent(
            tick=base_tick,
            timestamp=base_timestamp,
            conversation_id=ConversationId("conv-001"),
            agent=AgentName("River"),
        )
        assert event.type == "conversation_joined"


class TestConversationLeftEvent:
    """Tests for ConversationLeftEvent."""

    def test_creation(self, base_tick: int, base_timestamp: datetime):
        """Test creating a ConversationLeftEvent."""
        event = ConversationLeftEvent(
            tick=base_tick,
            timestamp=base_timestamp,
            conversation_id=ConversationId("conv-001"),
            agent=AgentName("River"),
        )
        assert event.type == "conversation_left"


class TestConversationTurnEvent:
    """Tests for ConversationTurnEvent."""

    def test_creation(self, base_tick: int, base_timestamp: datetime):
        """Test creating a ConversationTurnEvent."""
        event = ConversationTurnEvent(
            tick=base_tick,
            timestamp=base_timestamp,
            conversation_id=ConversationId("conv-001"),
            speaker=AgentName("Ember"),
            narrative="I was thinking about the garden.",
        )
        assert event.type == "conversation_turn"
        assert event.narrative == "I was thinking about the garden."


class TestConversationNextSpeakerSetEvent:
    """Tests for ConversationNextSpeakerSetEvent."""

    def test_creation(self, base_tick: int, base_timestamp: datetime):
        """Test creating a ConversationNextSpeakerSetEvent."""
        event = ConversationNextSpeakerSetEvent(
            tick=base_tick,
            timestamp=base_timestamp,
            conversation_id=ConversationId("conv-001"),
            next_speaker=AgentName("Sage"),
        )
        assert event.type == "conversation_next_speaker_set"


class TestConversationMovedEvent:
    """Tests for ConversationMovedEvent."""

    def test_creation(self, base_tick: int, base_timestamp: datetime):
        """Test creating a ConversationMovedEvent."""
        event = ConversationMovedEvent(
            tick=base_tick,
            timestamp=base_timestamp,
            conversation_id=ConversationId("conv-001"),
            initiated_by=AgentName("Ember"),
            from_location=LocationId("workshop"),
            to_location=LocationId("garden"),
            participants=(AgentName("Ember"), AgentName("Sage")),
        )
        assert event.type == "conversation_moved"
        assert event.initiated_by == "Ember"
        assert event.from_location == "workshop"
        assert event.to_location == "garden"
        assert len(event.participants) == 2

    def test_immutability(self, base_tick: int, base_timestamp: datetime):
        """Test event is frozen."""
        event = ConversationMovedEvent(
            tick=base_tick,
            timestamp=base_timestamp,
            conversation_id=ConversationId("conv-001"),
            initiated_by=AgentName("Ember"),
            from_location=LocationId("workshop"),
            to_location=LocationId("garden"),
            participants=(AgentName("Ember"), AgentName("Sage")),
        )
        with pytest.raises(ValidationError):
            event.to_location = LocationId("library")  # type: ignore

    def test_serialization_roundtrip(self, base_tick: int, base_timestamp: datetime):
        """Test serialization and deserialization."""
        event = ConversationMovedEvent(
            tick=base_tick,
            timestamp=base_timestamp,
            conversation_id=ConversationId("conv-001"),
            initiated_by=AgentName("Ember"),
            from_location=LocationId("workshop"),
            to_location=LocationId("garden"),
            participants=(AgentName("Ember"), AgentName("Sage")),
        )
        data = event.model_dump(mode="json")
        restored = ConversationMovedEvent.model_validate(data)
        assert restored.conversation_id == event.conversation_id
        assert restored.to_location == event.to_location


class TestConversationEndedEvent:
    """Tests for ConversationEndedEvent."""

    def test_creation(self, base_tick: int, base_timestamp: datetime):
        """Test creating a ConversationEndedEvent."""
        event = ConversationEndedEvent(
            tick=base_tick,
            timestamp=base_timestamp,
            conversation_id=ConversationId("conv-001"),
            reason="All participants left",
            final_participants=(AgentName("Ember"), AgentName("Sage")),
            summary="A pleasant conversation about art.",
        )
        assert event.type == "conversation_ended"
        assert event.summary == "A pleasant conversation about art."


class TestWorldEventOccurred:
    """Tests for WorldEventOccurred."""

    def test_creation_minimal(self, base_tick: int, base_timestamp: datetime):
        """Test creating a WorldEventOccurred with minimal fields."""
        event = WorldEventOccurred(
            tick=base_tick,
            timestamp=base_timestamp,
            description="A bird flew overhead.",
        )
        assert event.type == "world_event"
        assert event.location is None
        assert event.agents_involved == ()

    def test_creation_full(self, base_tick: int, base_timestamp: datetime):
        """Test creating a WorldEventOccurred with all fields."""
        event = WorldEventOccurred(
            tick=base_tick,
            timestamp=base_timestamp,
            description="A festival began in the garden.",
            location=LocationId("garden"),
            agents_involved=(AgentName("Ember"), AgentName("Sage")),
        )
        assert event.location == "garden"
        assert len(event.agents_involved) == 2


class TestWeatherChangedEvent:
    """Tests for WeatherChangedEvent."""

    def test_creation(self, base_tick: int, base_timestamp: datetime):
        """Test creating a WeatherChangedEvent."""
        event = WeatherChangedEvent(
            tick=base_tick,
            timestamp=base_timestamp,
            old_weather="clear",
            new_weather="rainy",
        )
        assert event.type == "weather_changed"
        assert event.old_weather == "clear"
        assert event.new_weather == "rainy"


class TestDomainEventDiscriminatedUnion:
    """Tests for the DomainEvent discriminated union type."""

    def test_parse_agent_moved_event(self, base_timestamp: datetime):
        """Test parsing AgentMovedEvent from dict."""
        data = {
            "type": "agent_moved",
            "tick": 5,
            "timestamp": base_timestamp.isoformat(),
            "agent": "Ember",
            "from_location": "workshop",
            "to_location": "garden",
        }
        event = EventAdapter.validate_python(data)
        assert isinstance(event, AgentMovedEvent)

    def test_parse_conversation_started_event(self, base_timestamp: datetime):
        """Test parsing ConversationStartedEvent from dict."""
        data = {
            "type": "conversation_started",
            "tick": 5,
            "timestamp": base_timestamp.isoformat(),
            "conversation_id": "conv-001",
            "location": "workshop",
            "privacy": "private",
            "initial_participants": ["Ember", "Sage"],
        }
        event = EventAdapter.validate_python(data)
        assert isinstance(event, ConversationStartedEvent)

    def test_parse_weather_changed_event(self, base_timestamp: datetime):
        """Test parsing WeatherChangedEvent from dict."""
        data = {
            "type": "weather_changed",
            "tick": 5,
            "timestamp": base_timestamp.isoformat(),
            "old_weather": "clear",
            "new_weather": "stormy",
        }
        event = EventAdapter.validate_python(data)
        assert isinstance(event, WeatherChangedEvent)

    def test_all_event_types_have_unique_discriminators(self):
        """Test all event types have unique type discriminators."""
        event_types = [
            AgentMovedEvent,
            AgentMoodChangedEvent,
            AgentEnergyChangedEvent,
            AgentActionEvent,
            AgentSleptEvent,
            AgentWokeEvent,
            ConversationInvitedEvent,
            ConversationInviteAcceptedEvent,
            ConversationInviteDeclinedEvent,
            ConversationInviteExpiredEvent,
            ConversationStartedEvent,
            ConversationJoinedEvent,
            ConversationLeftEvent,
            ConversationTurnEvent,
            ConversationNextSpeakerSetEvent,
            ConversationMovedEvent,
            ConversationEndedEvent,
            WorldEventOccurred,
            WeatherChangedEvent,
        ]

        discriminators = set()
        for cls in event_types:
            type_value = cls.model_fields["type"].default
            assert type_value not in discriminators, f"Duplicate type: {type_value}"
            discriminators.add(type_value)

        assert len(discriminators) == 19

    def test_serialization_roundtrip(self, base_tick: int, base_timestamp: datetime):
        """Test serialization and deserialization of various events."""
        events = [
            AgentMovedEvent(
                tick=base_tick,
                timestamp=base_timestamp,
                agent=AgentName("Ember"),
                from_location=LocationId("workshop"),
                to_location=LocationId("garden"),
            ),
            AgentSleptEvent(
                tick=base_tick,
                timestamp=base_timestamp,
                agent=AgentName("Luna"),
                location=LocationId("garden"),
            ),
            ConversationTurnEvent(
                tick=base_tick,
                timestamp=base_timestamp,
                conversation_id=ConversationId("conv-001"),
                speaker=AgentName("Ember"),
                narrative="Hello!",
            ),
        ]

        for event in events:
            data = event.model_dump(mode="json")
            restored = EventAdapter.validate_python(data)
            assert type(restored) == type(event)
            assert restored.tick == event.tick
