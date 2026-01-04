"""Tests for TickContext."""

import pytest

from hearth.core.types import AgentName, Position
from hearth.core.terrain import Weather
from hearth.core.agent import Agent, AgentModel
from hearth.engine.context import TickContext, TurnResult


@pytest.fixture
def sample_agents():
    """Create sample agents for testing."""
    model = AgentModel(id="test-model", display_name="Test Model")
    return {
        AgentName("Ember"): Agent(
            name=AgentName("Ember"),
            model=model,
            position=Position(10, 10),
        ),
        AgentName("Sage"): Agent(
            name=AgentName("Sage"),
            model=model,
            position=Position(20, 20),
        ),
    }


@pytest.fixture
def sample_context(sample_agents):
    """Create sample context for testing."""
    return TickContext(
        tick=1,
        time_of_day="morning",
        weather=Weather.CLEAR,
        agents=sample_agents,
    )


class TestTickContext:
    """Tests for TickContext immutable transforms."""

    def test_default_values(self, sample_agents):
        """Test context has correct default values."""
        ctx = TickContext(
            tick=1,
            time_of_day="morning",
            weather=Weather.CLEAR,
            agents=sample_agents,
        )
        assert ctx.agents_to_act == frozenset()
        assert ctx.agents_to_wake == frozenset()
        assert ctx.clusters == ()
        assert ctx.events == ()
        assert ctx.turn_results == {}

    def test_with_agents_to_act(self, sample_context):
        """Test with_agents_to_act returns new context."""
        agents = frozenset([AgentName("Ember")])
        new_ctx = sample_context.with_agents_to_act(agents)

        # Original unchanged
        assert sample_context.agents_to_act == frozenset()

        # New context has update
        assert new_ctx.agents_to_act == agents
        assert new_ctx.tick == sample_context.tick
        assert new_ctx.agents == sample_context.agents

    def test_with_agents_to_wake(self, sample_context):
        """Test with_agents_to_wake returns new context."""
        agents = frozenset([AgentName("Sage")])
        new_ctx = sample_context.with_agents_to_wake(agents)

        assert sample_context.agents_to_wake == frozenset()
        assert new_ctx.agents_to_wake == agents

    def test_with_clusters(self, sample_context):
        """Test with_clusters converts lists to tuples."""
        clusters = [[AgentName("Ember")], [AgentName("Sage")]]
        new_ctx = sample_context.with_clusters(clusters)

        assert sample_context.clusters == ()
        assert new_ctx.clusters == (
            (AgentName("Ember"),),
            (AgentName("Sage"),),
        )

    def test_with_events(self, sample_context):
        """Test with_events returns new context."""
        # Create a simple mock event (using a dict for simplicity)
        from hearth.core.events import TimeAdvancedEvent
        from datetime import datetime

        event = TimeAdvancedEvent(
            tick=1,
            timestamp=datetime.now(),
            new_tick=2,
        )
        new_ctx = sample_context.with_events((event,))

        assert sample_context.events == ()
        assert len(new_ctx.events) == 1

    def test_append_events(self, sample_context):
        """Test append_events adds to existing events."""
        from hearth.core.events import TimeAdvancedEvent
        from datetime import datetime

        event1 = TimeAdvancedEvent(tick=1, timestamp=datetime.now(), new_tick=2)
        ctx_with_one = sample_context.with_events((event1,))

        event2 = TimeAdvancedEvent(tick=2, timestamp=datetime.now(), new_tick=3)
        ctx_with_two = ctx_with_one.append_events([event2])

        assert len(ctx_with_one.events) == 1
        assert len(ctx_with_two.events) == 2

    def test_with_turn_results(self, sample_context):
        """Test with_turn_results returns new context."""
        # Create a mock turn result
        from unittest.mock import MagicMock

        mock_perception = MagicMock()
        result = TurnResult(
            agent_name=AgentName("Ember"),
            perception=mock_perception,
            actions_taken=[],
            events=[],
        )

        new_ctx = sample_context.with_turn_results({AgentName("Ember"): result})

        assert sample_context.turn_results == {}
        assert AgentName("Ember") in new_ctx.turn_results

    def test_immutability(self, sample_context):
        """Test that context is truly immutable."""
        with pytest.raises(Exception):  # FrozenInstanceError
            sample_context.tick = 999


class TestTurnResult:
    """Tests for TurnResult."""

    def test_default_values(self):
        """Test TurnResult has correct default values."""
        from unittest.mock import MagicMock

        mock_perception = MagicMock()
        result = TurnResult(
            agent_name=AgentName("Ember"),
            perception=mock_perception,
        )

        assert result.agent_name == AgentName("Ember")
        assert result.perception == mock_perception
        assert result.actions_taken == []
        assert result.events == []
