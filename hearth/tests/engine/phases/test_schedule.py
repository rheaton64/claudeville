"""Tests for SchedulePhase."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from hearth.core.types import AgentName, Position
from hearth.core.terrain import Weather
from hearth.core.agent import Agent, AgentModel
from hearth.engine.context import TickContext
from hearth.engine.phases.schedule import SchedulePhase
from hearth.services.scheduler import Scheduler


@pytest.fixture
def model():
    """Create a test model."""
    return AgentModel(id="test-model", display_name="Test Model")


@pytest.fixture
def scheduler():
    """Create a scheduler."""
    return Scheduler(vision_radius=3)


@pytest.fixture
def mock_agent_service():
    """Create a mock agent service."""
    service = MagicMock()
    service.set_sleeping = AsyncMock()
    return service


def make_agent(name: str, x: int, y: int, model: AgentModel, sleeping: bool = False) -> Agent:
    """Helper to create agent."""
    return Agent(
        name=AgentName(name),
        model=model,
        position=Position(x, y),
        is_sleeping=sleeping,
    )


class TestSchedulePhase:
    """Tests for SchedulePhase."""

    @pytest.mark.asyncio
    async def test_all_awake_agents_act(self, model, scheduler, mock_agent_service):
        """Test all awake agents are scheduled to act."""
        agents = {
            AgentName("Ember"): make_agent("Ember", 0, 0, model),
            AgentName("Sage"): make_agent("Sage", 100, 100, model),
        }
        ctx = TickContext(
            tick=1,
            time_of_day="morning",
            weather=Weather.CLEAR,
            agents=agents,
        )

        phase = SchedulePhase(scheduler, mock_agent_service)
        result = await phase.execute(ctx)

        assert AgentName("Ember") in result.agents_to_act
        assert AgentName("Sage") in result.agents_to_act

    @pytest.mark.asyncio
    async def test_sleeping_agents_excluded(self, model, scheduler, mock_agent_service):
        """Test sleeping agents not scheduled."""
        agents = {
            AgentName("Ember"): make_agent("Ember", 0, 0, model, sleeping=False),
            AgentName("Sage"): make_agent("Sage", 100, 100, model, sleeping=True),
        }
        ctx = TickContext(
            tick=1,
            time_of_day="morning",
            weather=Weather.CLEAR,
            agents=agents,
        )

        phase = SchedulePhase(scheduler, mock_agent_service)
        result = await phase.execute(ctx)

        assert AgentName("Ember") in result.agents_to_act
        assert AgentName("Sage") not in result.agents_to_act

    @pytest.mark.asyncio
    async def test_woken_agents_included(self, model, scheduler, mock_agent_service):
        """Test agents in agents_to_wake are included even if sleeping."""
        agents = {
            AgentName("Ember"): make_agent("Ember", 0, 0, model, sleeping=True),
        }
        ctx = TickContext(
            tick=1,
            time_of_day="morning",
            weather=Weather.CLEAR,
            agents=agents,
            agents_to_wake=frozenset([AgentName("Ember")]),
        )

        phase = SchedulePhase(scheduler, mock_agent_service)
        result = await phase.execute(ctx)

        assert AgentName("Ember") in result.agents_to_act
        # Verify set_sleeping was called
        mock_agent_service.set_sleeping.assert_called_once_with(AgentName("Ember"), False)

    @pytest.mark.asyncio
    async def test_clusters_computed(self, model, scheduler, mock_agent_service):
        """Test clusters are computed and added to context."""
        # Two distant agents = 2 clusters
        agents = {
            AgentName("Ember"): make_agent("Ember", 0, 0, model),
            AgentName("Sage"): make_agent("Sage", 100, 100, model),
        }
        ctx = TickContext(
            tick=1,
            time_of_day="morning",
            weather=Weather.CLEAR,
            agents=agents,
        )

        phase = SchedulePhase(scheduler, mock_agent_service)
        result = await phase.execute(ctx)

        assert len(result.clusters) == 2

    @pytest.mark.asyncio
    async def test_nearby_agents_same_cluster(self, model, scheduler, mock_agent_service):
        """Test nearby agents are in same cluster."""
        agents = {
            AgentName("Ember"): make_agent("Ember", 0, 0, model),
            AgentName("Sage"): make_agent("Sage", 2, 1, model),  # nearby
        }
        ctx = TickContext(
            tick=1,
            time_of_day="morning",
            weather=Weather.CLEAR,
            agents=agents,
        )

        phase = SchedulePhase(scheduler, mock_agent_service)
        result = await phase.execute(ctx)

        assert len(result.clusters) == 1
        assert len(result.clusters[0]) == 2

    @pytest.mark.asyncio
    async def test_forced_turn_first(self, model, scheduler, mock_agent_service):
        """Test forced agent is first in their cluster."""
        agents = {
            AgentName("Ember"): make_agent("Ember", 0, 0, model),
            AgentName("Sage"): make_agent("Sage", 2, 1, model),  # same cluster
        }
        ctx = TickContext(
            tick=1,
            time_of_day="morning",
            weather=Weather.CLEAR,
            agents=agents,
        )

        # Force Sage to go first
        scheduler.force_next(AgentName("Sage"))

        phase = SchedulePhase(scheduler, mock_agent_service)
        result = await phase.execute(ctx)

        # Sage should be first in the cluster
        assert result.clusters[0][0] == AgentName("Sage")
