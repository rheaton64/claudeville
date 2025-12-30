"""Tests for engine.services.bootstrap module."""

import pytest
from datetime import datetime
from pathlib import Path

from engine.services.bootstrap import (
    AgentSeed,
    DEFAULT_LOCATIONS,
    DEFAULT_AGENTS,
    ensure_village_structure,
    build_world_snapshot,
    build_agent_snapshots,
    build_initial_snapshot,
)
from engine.domain import AgentName, LocationId, Weather


class TestAgentSeed:
    """Tests for AgentSeed dataclass."""

    def test_creation(self):
        """Test creating an AgentSeed."""
        seed = AgentSeed(
            name="TestAgent",
            model_id="claude-test",
            model_display="Claude Test",
            model_provider="anthropic",
            personality="A test personality.",
            job="Testing things",
            interests=("testing", "coding"),
            note_to_self="Keep testing.",
            location="workshop",
        )

        assert seed.name == "TestAgent"
        assert seed.model_id == "claude-test"
        assert seed.location == "workshop"
        assert seed.mood == "calm"  # default
        assert seed.energy == 80  # default

    def test_frozen(self):
        """Test AgentSeed is frozen."""
        seed = AgentSeed(
            name="Test",
            model_id="test",
            model_display="Test",
            model_provider="test",
            personality="Test",
            job="Test",
            interests=(),
            note_to_self="Test",
            location="workshop",
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            seed.name = "Other"


class TestDefaultConstants:
    """Tests for default locations and agents."""

    def test_default_locations_has_required(self):
        """Test default locations include expected places."""
        assert "town_square" in DEFAULT_LOCATIONS
        assert "workshop" in DEFAULT_LOCATIONS
        assert "library" in DEFAULT_LOCATIONS
        assert "residential" in DEFAULT_LOCATIONS

    def test_default_locations_have_connections(self):
        """Test locations have connections defined."""
        for loc_id, data in DEFAULT_LOCATIONS.items():
            assert "connections" in data
            assert isinstance(data["connections"], tuple)

    def test_default_agents_exist(self):
        """Test default agents are defined."""
        assert len(DEFAULT_AGENTS) >= 3

    def test_default_agents_have_valid_locations(self):
        """Test default agents start at valid locations."""
        for agent in DEFAULT_AGENTS:
            assert agent.location in DEFAULT_LOCATIONS


class TestEnsureVillageStructure:
    """Tests for ensure_village_structure function."""

    def test_creates_agents_dir(self, tmp_path: Path):
        """Test agents directory is created."""
        ensure_village_structure(tmp_path)

        assert (tmp_path / "agents").exists()
        assert (tmp_path / "agents").is_dir()

    def test_creates_shared_dirs(self, tmp_path: Path):
        """Test shared directories are created."""
        ensure_village_structure(tmp_path)

        assert (tmp_path / "shared").exists()

    def test_idempotent(self, tmp_path: Path):
        """Test calling twice doesn't error."""
        ensure_village_structure(tmp_path)
        ensure_village_structure(tmp_path)  # Should not raise

        assert (tmp_path / "agents").exists()


class TestBuildWorldSnapshot:
    """Tests for build_world_snapshot function."""

    def test_creates_snapshot(self):
        """Test building a world snapshot."""
        snapshot = build_world_snapshot()

        assert snapshot.tick == 0
        assert snapshot.weather == Weather.CLEAR
        assert len(snapshot.locations) > 0

    def test_uses_provided_time(self):
        """Test provided start time is used."""
        start = datetime(2024, 6, 15, 12, 0, 0)
        snapshot = build_world_snapshot(start_time=start)

        assert snapshot.world_time == start
        assert snapshot.start_date == start

    def test_uses_custom_locations(self):
        """Test custom locations override defaults."""
        custom_locs = {
            "test_loc": {
                "name": "Test Location",
                "description": "A test place.",
                "features": ("test",),
                "connections": (),
            }
        }

        snapshot = build_world_snapshot(locations=custom_locs)

        assert LocationId("test_loc") in snapshot.locations
        assert len(snapshot.locations) == 1

    def test_default_locations_loaded(self):
        """Test default locations are used when not provided."""
        snapshot = build_world_snapshot()

        assert LocationId("town_square") in snapshot.locations
        assert LocationId("workshop") in snapshot.locations


class TestBuildAgentSnapshots:
    """Tests for build_agent_snapshots function."""

    def test_builds_default_agents(self):
        """Test building default agent snapshots."""
        snapshots = build_agent_snapshots()

        assert len(snapshots) == len(DEFAULT_AGENTS)
        for seed in DEFAULT_AGENTS:
            assert AgentName(seed.name) in snapshots

    def test_uses_custom_agents(self):
        """Test custom agents override defaults."""
        custom_seeds = (
            AgentSeed(
                name="CustomAgent",
                model_id="custom-model",
                model_display="Custom Model",
                model_provider="test",
                personality="Custom personality.",
                job="Custom job",
                interests=("custom",),
                note_to_self="Be custom.",
                location="workshop",
                mood="happy",
                energy=100,
            ),
        )

        snapshots = build_agent_snapshots(agents=custom_seeds)

        assert len(snapshots) == 1
        assert AgentName("CustomAgent") in snapshots
        agent = snapshots[AgentName("CustomAgent")]
        assert agent.mood == "happy"
        assert agent.energy == 100

    def test_agent_has_required_fields(self):
        """Test agents have all required fields populated."""
        snapshots = build_agent_snapshots()

        for name, agent in snapshots.items():
            assert agent.name == name
            assert agent.model is not None
            assert agent.personality
            assert agent.job
            assert agent.location
            assert not agent.is_sleeping


class TestBuildInitialSnapshot:
    """Tests for build_initial_snapshot function."""

    def test_creates_complete_snapshot(self, tmp_path: Path):
        """Test building a complete initial snapshot."""
        snapshot = build_initial_snapshot(tmp_path)

        assert snapshot.world is not None
        assert len(snapshot.agents) > 0
        assert snapshot.conversations == {}
        assert snapshot.pending_invites == {}

    def test_creates_directory_structure(self, tmp_path: Path):
        """Test village directories are created."""
        build_initial_snapshot(tmp_path)

        assert (tmp_path / "agents").exists()

    def test_creates_agent_directories(self, tmp_path: Path):
        """Test agent directories are created."""
        snapshot = build_initial_snapshot(tmp_path)

        for name in snapshot.agents.keys():
            agent_dir = tmp_path / "agents" / str(name).lower()
            assert agent_dir.exists()

    def test_world_has_agent_locations(self, tmp_path: Path):
        """Test world snapshot has agent locations."""
        snapshot = build_initial_snapshot(tmp_path)

        for name, agent in snapshot.agents.items():
            assert name in snapshot.world.agent_locations
            assert snapshot.world.agent_locations[name] == agent.location

    def test_uses_custom_start_time(self, tmp_path: Path):
        """Test custom start time is used."""
        start = datetime(2024, 1, 1, 8, 0, 0)
        snapshot = build_initial_snapshot(tmp_path, start_time=start)

        assert snapshot.world.world_time == start

    def test_uses_custom_agents(self, tmp_path: Path):
        """Test custom agents can be provided."""
        custom_seeds = (
            AgentSeed(
                name="Solo",
                model_id="solo-model",
                model_display="Solo Model",
                model_provider="test",
                personality="Alone.",
                job="Being alone",
                interests=("solitude",),
                note_to_self="Stay solo.",
                location="library",
            ),
        )

        snapshot = build_initial_snapshot(tmp_path, agents=custom_seeds)

        assert len(snapshot.agents) == 1
        assert AgentName("Solo") in snapshot.agents
