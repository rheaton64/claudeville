"""Tests for ObserverAPI."""

import pytest

from core.types import Position, Rect, ObjectId, AgentName
from core.terrain import Terrain
from core.world import Cell
from core.agent import Agent, AgentModel
from core.objects import Sign

from observe import ObserverAPI


class TestWorldQueries:
    """Test world state queries."""

    async def test_get_world_state(self, observer_api: ObserverAPI):
        """Should return world state."""
        state = await observer_api.get_world_state()
        assert state.current_tick == 0
        # Just verify dimensions are positive (default is 500x500 in production)
        assert state.width > 0
        assert state.height > 0

    async def test_get_world_dimensions(self, observer_api: ObserverAPI):
        """Should return world dimensions."""
        width, height = await observer_api.get_world_dimensions()
        assert width > 0
        assert height > 0


class TestCellQueries:
    """Test cell queries."""

    async def test_get_cell_returns_default(self, observer_api: ObserverAPI):
        """Should return default grass cell for unstored position."""
        cell = await observer_api.get_cell(Position(50, 50))
        assert cell.terrain == Terrain.GRASS

    async def test_get_terrain(self, observer_api: ObserverAPI):
        """Should return terrain at position."""
        terrain = await observer_api.get_terrain(Position(50, 50))
        assert terrain == Terrain.GRASS

    async def test_get_cells_in_rect(self, observer_api: ObserverAPI):
        """Should return cells in rectangle."""
        rect = Rect(0, 0, 2, 2)
        cells = await observer_api.get_cells_in_rect(rect)
        assert len(cells) == 9  # 3x3


class TestObjectQueries:
    """Test object queries."""

    async def test_get_objects_at_empty(self, observer_api: ObserverAPI):
        """Should return empty list when no objects."""
        objects = await observer_api.get_objects_at(Position(50, 50))
        assert objects == []

    async def test_get_objects_at_with_sign(
        self, observer_api: ObserverAPI, world_service
    ):
        """Should return objects at position."""
        sign = Sign(
            id=ObjectId("test-sign"),
            position=Position(10, 10),
            text="Hello",
            created_tick=0,
        )
        await world_service.place_object(sign)

        objects = await observer_api.get_objects_at(Position(10, 10))
        assert len(objects) == 1
        assert objects[0].id == ObjectId("test-sign")


class TestAgentQueries:
    """Test agent queries."""

    async def test_get_all_agents_empty(self, observer_api: ObserverAPI):
        """Should return empty list when no agents."""
        agents = await observer_api.get_all_agents()
        assert agents == []

    async def test_get_all_agents_with_agent(
        self, observer_api: ObserverAPI, agent_service
    ):
        """Should return all agents."""
        agent = Agent(
            name=AgentName("TestAgent"),
            model=AgentModel(id="test-model", display_name="Test"),
            personality="testing",
            position=Position(50, 50),
        )
        await agent_service.save_agent(agent)

        agents = await observer_api.get_all_agents()
        assert len(agents) == 1
        assert agents[0].name == AgentName("TestAgent")

    async def test_get_agent_by_name(
        self, observer_api: ObserverAPI, agent_service
    ):
        """Should get agent by name."""
        agent = Agent(
            name=AgentName("Ember"),
            model=AgentModel(id="test-model", display_name="Test"),
            personality="crafting",
            position=Position(25, 25),
        )
        await agent_service.save_agent(agent)

        result = await observer_api.get_agent(AgentName("Ember"))
        assert result is not None
        assert result.name == AgentName("Ember")
        assert result.position == Position(25, 25)

    async def test_get_agent_not_found(self, observer_api: ObserverAPI):
        """Should return None for unknown agent."""
        result = await observer_api.get_agent(AgentName("Unknown"))
        assert result is None

    async def test_get_agent_at_position(
        self, observer_api: ObserverAPI, agent_service
    ):
        """Should get agent at position."""
        agent = Agent(
            name=AgentName("Sage"),
            model=AgentModel(id="test-model", display_name="Test"),
            personality="knowledge",
            position=Position(30, 30),
        )
        await agent_service.save_agent(agent)

        result = await observer_api.get_agent_at(Position(30, 30))
        assert result is not None
        assert result.name == AgentName("Sage")

    async def test_get_agent_at_empty_position(self, observer_api: ObserverAPI):
        """Should return None for position with no agent."""
        result = await observer_api.get_agent_at(Position(99, 99))
        assert result is None


class TestViewportData:
    """Test viewport convenience method."""

    async def test_get_viewport_data(
        self, observer_api: ObserverAPI, world_service, agent_service
    ):
        """Should return all data for a viewport."""
        # Add a sign
        sign = Sign(
            id=ObjectId("viewport-sign"),
            position=Position(5, 5),
            text="Test",
            created_tick=0,
        )
        await world_service.place_object(sign)

        # Add an agent
        agent = Agent(
            name=AgentName("River"),
            model=AgentModel(id="test-model", display_name="Test"),
            personality="nature",
            position=Position(6, 6),
        )
        await agent_service.save_agent(agent)

        # Get viewport data
        rect = Rect(0, 0, 10, 10)
        cells, objects, agents = await observer_api.get_viewport_data(rect)

        assert len(cells) == 121  # 11x11
        assert len(objects) == 1
        assert objects[0].id == ObjectId("viewport-sign")
        assert len(agents) == 1
        assert agents[0].name == AgentName("River")
