"""Tests for engine.domain.world module."""

import pytest
from datetime import datetime
from pydantic import ValidationError

from engine.domain import (
    LocationId,
    AgentName,
    Location,
    WorldSnapshot,
    Weather,
)


class TestWeather:
    """Tests for Weather enum."""

    def test_all_values_exist(self):
        """Test all expected weather types exist."""
        assert Weather.CLEAR.value == "clear"
        assert Weather.CLOUDY.value == "cloudy"
        assert Weather.RAINY.value == "rainy"
        assert Weather.STORMY.value == "stormy"
        assert Weather.FOGGY.value == "foggy"
        assert Weather.SNOWY.value == "snowy"

    def test_enum_count(self):
        """Test we have exactly 6 weather types."""
        assert len(Weather) == 6


class TestLocation:
    """Tests for Location model."""

    def test_creation_with_all_fields(self):
        """Test creating a Location with all fields."""
        loc = Location(
            id=LocationId("test-loc"),
            name="Test Location",
            description="A test location for testing.",
            features=("bench", "tree", "lamp"),
            connections=(LocationId("other-loc"), LocationId("another-loc")),
        )
        assert loc.id == "test-loc"
        assert loc.name == "Test Location"
        assert len(loc.features) == 3
        assert len(loc.connections) == 2

    def test_default_values(self):
        """Test default values for optional fields."""
        loc = Location(
            id=LocationId("minimal"),
            name="Minimal",
            description="Just the basics.",
        )
        assert loc.features == ()
        assert loc.connections == ()

    def test_immutability(self, workshop_location: Location):
        """Test that Location is frozen."""
        with pytest.raises(ValidationError):
            workshop_location.name = "New Name"  # type: ignore

    def test_serialization_roundtrip(self, workshop_location: Location):
        """Test model_dump and model_validate roundtrip."""
        data = workshop_location.model_dump()
        restored = Location.model_validate(data)
        assert restored == workshop_location

    def test_features_tuple(self, workshop_location: Location):
        """Test features is a tuple."""
        assert isinstance(workshop_location.features, tuple)

    def test_connections_tuple(self, workshop_location: Location):
        """Test connections is a tuple."""
        assert isinstance(workshop_location.connections, tuple)


class TestWorldSnapshot:
    """Tests for WorldSnapshot model."""

    def test_creation_with_all_fields(
        self,
        all_locations: dict[LocationId, Location],
    ):
        """Test creating a WorldSnapshot with all fields."""
        ws = WorldSnapshot(
            tick=10,
            world_time=datetime(2024, 6, 15, 14, 0, 0),
            start_date=datetime(2024, 6, 15, 0, 0, 0),
            weather=Weather.RAINY,
            locations=all_locations,
            agent_locations={
                AgentName("Ember"): LocationId("workshop"),
                AgentName("Sage"): LocationId("library"),
            },
        )
        assert ws.tick == 10
        assert ws.weather == Weather.RAINY
        assert len(ws.locations) == 3
        assert len(ws.agent_locations) == 2

    def test_immutability(self, world_snapshot: WorldSnapshot):
        """Test that WorldSnapshot is frozen."""
        with pytest.raises(ValidationError):
            world_snapshot.tick = 999  # type: ignore

    def test_serialization_roundtrip(self, world_snapshot: WorldSnapshot):
        """Test model_dump and model_validate roundtrip."""
        data = world_snapshot.model_dump(mode="json")
        restored = WorldSnapshot.model_validate(data)
        assert restored.tick == world_snapshot.tick
        assert restored.weather == world_snapshot.weather

    def test_agent_locations_dict(self, world_snapshot: WorldSnapshot):
        """Test agent_locations dictionary."""
        assert AgentName("Ember") in world_snapshot.agent_locations
        # Value is the agent's location
        assert world_snapshot.agent_locations[AgentName("Ember")] == LocationId("workshop")

    def test_locations_dict(self, world_snapshot: WorldSnapshot):
        """Test locations dictionary."""
        assert LocationId("workshop") in world_snapshot.locations
        assert LocationId("library") in world_snapshot.locations


class TestWorldSnapshotUpdates:
    """Tests for creating updated world snapshots."""

    def test_update_weather_creates_new_snapshot(self, world_snapshot: WorldSnapshot):
        """Test updating weather creates a new snapshot."""
        updated = WorldSnapshot(**{
            **world_snapshot.model_dump(),
            "weather": Weather.STORMY,
        })
        assert updated.weather == Weather.STORMY
        assert world_snapshot.weather != Weather.STORMY

    def test_update_tick_creates_new_snapshot(self, world_snapshot: WorldSnapshot):
        """Test updating tick creates a new snapshot."""
        updated = WorldSnapshot(**{
            **world_snapshot.model_dump(),
            "tick": world_snapshot.tick + 1,
        })
        assert updated.tick == world_snapshot.tick + 1

    def test_update_agent_location(self, world_snapshot: WorldSnapshot):
        """Test updating an agent's location in world snapshot."""
        new_locations = {
            **world_snapshot.agent_locations,
            AgentName("Ember"): LocationId("garden"),
        }
        updated = WorldSnapshot(**{
            **world_snapshot.model_dump(),
            "agent_locations": new_locations,
        })
        assert updated.agent_locations[AgentName("Ember")] == LocationId("garden")


class TestLocationConnections:
    """Tests for location connection relationships."""

    def test_workshop_connects_to_library(
        self,
        workshop_location: Location,
        library_location: Location,
    ):
        """Test workshop connects to library."""
        assert library_location.id in workshop_location.connections

    def test_library_connects_to_workshop(
        self,
        workshop_location: Location,
        library_location: Location,
    ):
        """Test library connects to workshop (bidirectional)."""
        assert workshop_location.id in library_location.connections

    def test_all_locations_have_connections(self, all_locations: dict[LocationId, Location]):
        """Test all locations have at least one connection."""
        for loc in all_locations.values():
            assert len(loc.connections) > 0
