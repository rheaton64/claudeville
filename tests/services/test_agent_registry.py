"""Tests for engine.services.agent_registry module."""

import pytest

from engine.domain import (
    AgentName,
    LocationId,
    AgentSnapshot,
    TimePeriod,
)
from engine.services.agent_registry import AgentRegistry


class TestAgentRegistryBasicCRUD:
    """Tests for basic CRUD operations."""

    def test_register_agent(
        self,
        agent_registry: AgentRegistry,
        sample_agent: AgentSnapshot,
    ):
        """Test registering an agent."""
        agent_registry.register(sample_agent)

        assert agent_registry.get(sample_agent.name) == sample_agent
        assert agent_registry.count() == 1

    def test_update_agent(
        self,
        agent_registry: AgentRegistry,
        sample_agent: AgentSnapshot,
    ):
        """Test updating an agent replaces the snapshot."""
        agent_registry.register(sample_agent)

        updated = AgentSnapshot(**{**sample_agent.model_dump(), "mood": "happy"})
        agent_registry.update(updated)

        assert agent_registry.get(sample_agent.name).mood == "happy"

    def test_get_nonexistent_agent(self, agent_registry: AgentRegistry):
        """Test getting a nonexistent agent returns None."""
        assert agent_registry.get(AgentName("Nobody")) is None

    def test_get_all(self, populated_agent_registry: AgentRegistry):
        """Test getting all agents."""
        all_agents = populated_agent_registry.get_all()

        assert len(all_agents) == 3  # sample_agent, second_agent, sleeping_agent

    def test_names(self, populated_agent_registry: AgentRegistry):
        """Test getting all agent names."""
        names = populated_agent_registry.names()

        assert AgentName("Ember") in names
        assert AgentName("Sage") in names
        assert AgentName("Luna") in names

    def test_count(self, populated_agent_registry: AgentRegistry):
        """Test counting agents."""
        assert populated_agent_registry.count() == 3


class TestAgentRegistryLocationQueries:
    """Tests for location-based queries."""

    def test_get_at_location(self, populated_agent_registry: AgentRegistry):
        """Test getting agents at a location."""
        # sample_agent is at workshop
        agents = populated_agent_registry.get_at_location(LocationId("workshop"))

        assert len(agents) == 1
        assert agents[0].name == AgentName("Ember")

    def test_get_at_location_empty(self, populated_agent_registry: AgentRegistry):
        """Test getting agents at empty location returns empty list."""
        agents = populated_agent_registry.get_at_location(LocationId("nowhere"))

        assert agents == []

    def test_get_others_at_location(
        self,
        agent_registry: AgentRegistry,
        sample_agent: AgentSnapshot,
        third_agent: AgentSnapshot,  # Also at workshop
    ):
        """Test getting other agents at location."""
        agent_registry.register(sample_agent)
        agent_registry.register(third_agent)

        others = agent_registry.get_others_at_location(
            LocationId("workshop"),
            exclude=AgentName("Ember"),
        )

        assert len(others) == 1
        assert others[0].name == AgentName("River")

    def test_count_at_location(
        self,
        agent_registry: AgentRegistry,
        sample_agent: AgentSnapshot,
        third_agent: AgentSnapshot,
    ):
        """Test counting agents at a location."""
        agent_registry.register(sample_agent)
        agent_registry.register(third_agent)

        count = agent_registry.count_at_location(LocationId("workshop"))

        assert count == 2

    def test_get_locations(self, populated_agent_registry: AgentRegistry):
        """Test getting location to agent names mapping."""
        locations = populated_agent_registry.get_locations()

        assert LocationId("workshop") in locations
        assert AgentName("Ember") in locations[LocationId("workshop")]


class TestAgentRegistrySleepQueries:
    """Tests for sleep state queries."""

    def test_get_awake(self, populated_agent_registry: AgentRegistry):
        """Test getting awake agents."""
        awake = populated_agent_registry.get_awake()

        # sample_agent and second_agent are awake, sleeping_agent is asleep
        assert len(awake) == 2
        names = [a.name for a in awake]
        assert AgentName("Ember") in names
        assert AgentName("Sage") in names
        assert AgentName("Luna") not in names

    def test_get_sleeping(self, populated_agent_registry: AgentRegistry):
        """Test getting sleeping agents."""
        sleeping = populated_agent_registry.get_sleeping()

        assert len(sleeping) == 1
        assert sleeping[0].name == AgentName("Luna")

    def test_all_sleeping_false(self, populated_agent_registry: AgentRegistry):
        """Test all_sleeping returns False when some awake."""
        assert populated_agent_registry.all_sleeping() is False

    def test_all_sleeping_true(
        self,
        agent_registry: AgentRegistry,
        sleeping_agent: AgentSnapshot,
    ):
        """Test all_sleeping returns True when all asleep."""
        agent_registry.register(sleeping_agent)

        assert agent_registry.all_sleeping() is True

    def test_all_sleeping_empty(self, agent_registry: AgentRegistry):
        """Test all_sleeping returns True for empty registry."""
        assert agent_registry.all_sleeping() is True

    def test_any_awake(self, populated_agent_registry: AgentRegistry):
        """Test any_awake returns True when some awake."""
        assert populated_agent_registry.any_awake() is True


class TestAgentRegistryStateUpdates:
    """Tests for state update helper methods."""

    def test_with_location(self, populated_agent_registry: AgentRegistry):
        """Test creating snapshot with new location."""
        new_snapshot = populated_agent_registry.with_location(
            AgentName("Ember"),
            LocationId("garden"),
        )

        assert new_snapshot is not None
        assert new_snapshot.location == LocationId("garden")
        # Original unchanged in registry
        assert populated_agent_registry.get(AgentName("Ember")).location == LocationId("workshop")

    def test_with_location_nonexistent(self, populated_agent_registry: AgentRegistry):
        """Test with_location for nonexistent agent returns None."""
        result = populated_agent_registry.with_location(
            AgentName("Nobody"),
            LocationId("garden"),
        )

        assert result is None

    def test_with_mood(self, populated_agent_registry: AgentRegistry):
        """Test creating snapshot with new mood."""
        new_snapshot = populated_agent_registry.with_mood(
            AgentName("Ember"),
            "excited",
        )

        assert new_snapshot is not None
        assert new_snapshot.mood == "excited"

    def test_with_energy(self, populated_agent_registry: AgentRegistry):
        """Test creating snapshot with new energy."""
        new_snapshot = populated_agent_registry.with_energy(
            AgentName("Ember"),
            90,
        )

        assert new_snapshot is not None
        assert new_snapshot.energy == 90

    def test_with_energy_clamps_max(self, populated_agent_registry: AgentRegistry):
        """Test energy is clamped to max 100."""
        new_snapshot = populated_agent_registry.with_energy(
            AgentName("Ember"),
            150,
        )

        assert new_snapshot is not None
        assert new_snapshot.energy == 100

    def test_with_energy_clamps_min(self, populated_agent_registry: AgentRegistry):
        """Test energy is clamped to min 0."""
        new_snapshot = populated_agent_registry.with_energy(
            AgentName("Ember"),
            -50,
        )

        assert new_snapshot is not None
        assert new_snapshot.energy == 0

    def test_with_sleep_state_sleeping(self, populated_agent_registry: AgentRegistry):
        """Test setting sleep state to sleeping."""
        new_snapshot = populated_agent_registry.with_sleep_state(
            AgentName("Ember"),
            is_sleeping=True,
            tick=10,
            period=TimePeriod.NIGHT,
        )

        assert new_snapshot is not None
        assert new_snapshot.is_sleeping is True
        assert new_snapshot.sleep_started_tick == 10
        assert new_snapshot.sleep_started_time_period == TimePeriod.NIGHT

    def test_with_sleep_state_waking(self, populated_agent_registry: AgentRegistry):
        """Test setting sleep state to awake clears sleep fields."""
        new_snapshot = populated_agent_registry.with_sleep_state(
            AgentName("Luna"),  # Currently sleeping
            is_sleeping=False,
        )

        assert new_snapshot is not None
        assert new_snapshot.is_sleeping is False
        assert new_snapshot.sleep_started_tick is None
        assert new_snapshot.sleep_started_time_period is None

    def test_with_session_id(self, populated_agent_registry: AgentRegistry):
        """Test updating session ID."""
        new_snapshot = populated_agent_registry.with_session_id(
            AgentName("Ember"),
            session_id="session-abc",
        )

        assert new_snapshot is not None
        assert new_snapshot.session_id == "session-abc"


class TestAgentRegistryLoadState:
    """Tests for load_state functionality."""

    def test_load_state(
        self,
        agent_registry: AgentRegistry,
        sample_agent: AgentSnapshot,
        second_agent: AgentSnapshot,
    ):
        """Test loading state from snapshot."""
        agents_dict = {
            sample_agent.name: sample_agent,
            second_agent.name: second_agent,
        }

        agent_registry.load_state(agents_dict)

        assert agent_registry.count() == 2
        assert agent_registry.get(sample_agent.name) == sample_agent
