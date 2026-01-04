"""Tests for WakePhase."""

import pytest

from hearth.core.types import AgentName, Position
from hearth.core.terrain import Weather
from hearth.core.agent import Agent, AgentModel
from hearth.engine.context import TickContext
from hearth.engine.phases.wake import WakePhase


@pytest.fixture
def model():
    """Create a test model."""
    return AgentModel(id="test-model", display_name="Test Model")


def make_agent(name: str, sleeping: bool, model: AgentModel) -> Agent:
    """Helper to create agent."""
    return Agent(
        name=AgentName(name),
        model=model,
        position=Position(0, 0),
        is_sleeping=sleeping,
    )


class TestWakePhase:
    """Tests for WakePhase."""

    @pytest.mark.asyncio
    async def test_wake_on_morning(self, model):
        """Test sleeping agents wake on morning."""
        agents = {
            AgentName("Ember"): make_agent("Ember", sleeping=True, model=model),
            AgentName("Sage"): make_agent("Sage", sleeping=True, model=model),
        }
        ctx = TickContext(
            tick=1,
            time_of_day="morning",
            weather=Weather.CLEAR,
            agents=agents,
        )

        phase = WakePhase()
        result = await phase.execute(ctx)

        assert AgentName("Ember") in result.agents_to_wake
        assert AgentName("Sage") in result.agents_to_wake

    @pytest.mark.asyncio
    async def test_no_wake_at_night(self, model):
        """Test sleeping agents don't wake at night."""
        agents = {
            AgentName("Ember"): make_agent("Ember", sleeping=True, model=model),
        }
        ctx = TickContext(
            tick=1,
            time_of_day="night",
            weather=Weather.CLEAR,
            agents=agents,
        )

        phase = WakePhase()
        result = await phase.execute(ctx)

        assert result.agents_to_wake == frozenset()

    @pytest.mark.asyncio
    async def test_awake_agents_not_added(self, model):
        """Test already awake agents not added to wake list."""
        agents = {
            AgentName("Ember"): make_agent("Ember", sleeping=False, model=model),
        }
        ctx = TickContext(
            tick=1,
            time_of_day="morning",
            weather=Weather.CLEAR,
            agents=agents,
        )

        phase = WakePhase()
        result = await phase.execute(ctx)

        # Not in wake list because already awake
        assert AgentName("Ember") not in result.agents_to_wake

    @pytest.mark.asyncio
    async def test_mixed_agents(self, model):
        """Test mixed sleeping/awake agents."""
        agents = {
            AgentName("Ember"): make_agent("Ember", sleeping=True, model=model),
            AgentName("Sage"): make_agent("Sage", sleeping=False, model=model),
        }
        ctx = TickContext(
            tick=1,
            time_of_day="morning",
            weather=Weather.CLEAR,
            agents=agents,
        )

        phase = WakePhase()
        result = await phase.execute(ctx)

        assert AgentName("Ember") in result.agents_to_wake
        assert AgentName("Sage") not in result.agents_to_wake
