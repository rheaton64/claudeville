"""Tests for event types and serialization."""

from datetime import datetime

import pytest
from pydantic import TypeAdapter

from hearth.core import (
    DomainEvent,
    AgentMovedEvent,
    JourneyStartedEvent,
    WallPlacedEvent,
    ItemGatheredEvent,
    AgentSleptEvent,
    WeatherChangedEvent,
    Position,
    Direction,
    AgentName,
    Weather,
)


class TestEventCreation:
    """Tests for creating events."""

    def test_create_agent_moved_event(self):
        """Create an agent moved event."""
        event = AgentMovedEvent(
            tick=1,
            timestamp=datetime(2025, 1, 1, 12, 0),
            agent=AgentName("Ember"),
            from_position=Position(5, 5),
            to_position=Position(5, 6),
        )

        assert event.type == "agent_moved"
        assert event.tick == 1
        assert event.agent == "Ember"
        assert event.from_position == Position(5, 5)
        assert event.to_position == Position(5, 6)

    def test_create_journey_started_event(self):
        """Create a journey started event."""
        event = JourneyStartedEvent(
            tick=1,
            timestamp=datetime(2025, 1, 1, 12, 0),
            agent=AgentName("Sage"),
            destination=Position(50, 50),
            path_length=20,
        )

        assert event.type == "journey_started"
        assert event.path_length == 20

    def test_create_wall_placed_event(self):
        """Create a wall placed event."""
        event = WallPlacedEvent(
            tick=5,
            timestamp=datetime(2025, 1, 1, 12, 0),
            position=Position(10, 10),
            direction=Direction.NORTH,
            builder=AgentName("Ember"),
        )

        assert event.type == "wall_placed"
        assert event.direction == Direction.NORTH

    def test_create_item_gathered_event(self):
        """Create an item gathered event."""
        event = ItemGatheredEvent(
            tick=3,
            timestamp=datetime(2025, 1, 1, 12, 0),
            agent=AgentName("River"),
            item_type="wood",
            quantity=3,
            from_position=Position(20, 20),
        )

        assert event.type == "item_gathered"
        assert event.item_type == "wood"
        assert event.quantity == 3

    def test_create_weather_changed_event(self):
        """Create a weather changed event."""
        event = WeatherChangedEvent(
            tick=10,
            timestamp=datetime(2025, 1, 1, 12, 0),
            old_weather=Weather.CLEAR,
            new_weather=Weather.RAINY,
        )

        assert event.type == "weather_changed"
        assert event.old_weather == Weather.CLEAR
        assert event.new_weather == Weather.RAINY


class TestEventSerialization:
    """Tests for event serialization and deserialization."""

    @pytest.fixture
    def event_adapter(self):
        """TypeAdapter for DomainEvent union."""
        return TypeAdapter(DomainEvent)

    def test_serialize_event_to_json(self, event_adapter):
        """Event can be serialized to JSON."""
        event = AgentMovedEvent(
            tick=1,
            timestamp=datetime(2025, 1, 1, 12, 0),
            agent=AgentName("Ember"),
            from_position=Position(5, 5),
            to_position=Position(5, 6),
        )

        json_str = event.model_dump_json()
        assert '"type":"agent_moved"' in json_str
        assert '"agent":"Ember"' in json_str

    def test_deserialize_event_from_json(self, event_adapter):
        """Event can be deserialized from JSON."""
        json_str = '{"type":"agent_moved","tick":1,"timestamp":"2025-01-01T12:00:00","agent":"Ember","from_position":[5,5],"to_position":[5,6]}'

        event = event_adapter.validate_json(json_str)

        assert isinstance(event, AgentMovedEvent)
        assert event.agent == "Ember"
        assert event.from_position == Position(5, 5)

    def test_roundtrip_serialization(self, event_adapter):
        """Event survives serialize/deserialize roundtrip."""
        original = WallPlacedEvent(
            tick=5,
            timestamp=datetime(2025, 1, 1, 12, 0),
            position=Position(10, 10),
            direction=Direction.NORTH,
            builder=AgentName("Ember"),
        )

        json_str = original.model_dump_json()
        restored = event_adapter.validate_json(json_str)

        assert restored.type == original.type
        assert restored.tick == original.tick
        assert restored.position == original.position
        assert restored.direction == original.direction
        assert restored.builder == original.builder

    def test_deserialize_discriminates_by_type(self, event_adapter):
        """Discriminator correctly identifies event type."""
        moved_json = '{"type":"agent_moved","tick":1,"timestamp":"2025-01-01T12:00:00","agent":"A","from_position":[0,0],"to_position":[0,1]}'
        slept_json = '{"type":"agent_slept","tick":1,"timestamp":"2025-01-01T12:00:00","agent":"A","at_position":[0,0]}'

        moved = event_adapter.validate_json(moved_json)
        slept = event_adapter.validate_json(slept_json)

        assert isinstance(moved, AgentMovedEvent)
        assert isinstance(slept, AgentSleptEvent)

    def test_event_to_dict(self):
        """Event can be converted to dict."""
        event = ItemGatheredEvent(
            tick=3,
            timestamp=datetime(2025, 1, 1, 12, 0),
            agent=AgentName("River"),
            item_type="wood",
            quantity=3,
            from_position=Position(20, 20),
        )

        d = event.model_dump()
        assert d["type"] == "item_gathered"
        assert d["agent"] == "River"
        assert d["item_type"] == "wood"


class TestEventImmutability:
    """Tests for event immutability."""

    def test_event_is_frozen(self):
        """Events are immutable."""
        event = AgentMovedEvent(
            tick=1,
            timestamp=datetime(2025, 1, 1, 12, 0),
            agent=AgentName("Ember"),
            from_position=Position(5, 5),
            to_position=Position(5, 6),
        )

        with pytest.raises(Exception):
            event.tick = 2

    def test_event_type_is_fixed(self):
        """Event type cannot be changed."""
        event = AgentSleptEvent(
            tick=1,
            timestamp=datetime(2025, 1, 1, 12, 0),
            agent=AgentName("Sage"),
            at_position=Position(10, 10),
        )

        # Type is a literal, always "agent_slept"
        assert event.type == "agent_slept"
