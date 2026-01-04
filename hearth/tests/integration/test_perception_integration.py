"""Integration tests for the perception builder.

These tests require ANTHROPIC_API_KEY to be set.
Run with: pytest tests/integration/test_perception_integration.py -m integration
Skip with: pytest -m "not slow" or -m "not integration"
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from adapters.perception import PerceptionBuilder, get_time_of_day
from core.types import Position, Direction, Rect, AgentName
from core.terrain import Terrain, Weather
from core.world import Cell
from core.agent import Agent, AgentModel, Inventory, InventoryStack
from core.objects import Sign, generate_object_id


# Test model for agent fixtures
TEST_MODEL = AgentModel(id="test-model", display_name="Test Model")


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def mock_world_service():
    """Create a mock WorldService."""
    service = MagicMock()
    service.get_world_state = AsyncMock(
        return_value=MagicMock(weather=Weather.CLEAR, width=100, height=100, current_tick=0)
    )
    service.get_world_dimensions = AsyncMock(return_value=(100, 100))
    service.get_cells_in_rect = AsyncMock(return_value=[])
    service.get_objects_in_rect = AsyncMock(return_value=[])
    return service


@pytest.fixture
def mock_agent_service():
    """Create a mock AgentService."""
    service = MagicMock()
    service.get_agent_or_raise = AsyncMock()
    service.get_nearby_agents = AsyncMock(return_value=[])
    return service


@pytest.fixture
def basic_agent():
    """Create a basic agent for testing."""
    return Agent(
        name=AgentName("TestAgent"),
        model=TEST_MODEL,
        position=Position(50, 50),
        known_agents=frozenset(),
    )


# -----------------------------------------------------------------------------
# Integration Tests
# -----------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.slow
class TestPerceptionNarrativeIntegration:
    """Integration tests that call the actual Haiku API for narrative generation.

    These tests verify that the perception builder generates meaningful
    atmospheric prose descriptions via Haiku.
    """

    @pytest.mark.asyncio
    async def test_generate_narrative_clear_morning(self, mock_world_service, mock_agent_service):
        """Test narrative generation for clear morning weather."""
        # Create builder without mocked client (will use real Haiku)
        builder = PerceptionBuilder(
            world_service=mock_world_service,
            agent_service=mock_agent_service,
            haiku_client=None,  # Will initialize real client
            vision_radius=3,
        )

        # Build feature set
        features = {
            "terrain": ["forest to the north", "water to the east"],
            "objects": ["a sign to the west"],
            "agents": [],
            "standing_on": None,
        }

        prose = await builder._generate_narrative(features, "morning", Weather.CLEAR)

        # Should produce meaningful prose
        assert len(prose) > 20
        # Should mention something about the surroundings or atmosphere
        # (exact content varies, but should have substance)
        assert prose.strip()  # Not just whitespace

    @pytest.mark.asyncio
    async def test_generate_narrative_rainy_night(self, mock_world_service, mock_agent_service):
        """Test narrative generation for rainy night weather."""
        builder = PerceptionBuilder(
            world_service=mock_world_service,
            agent_service=mock_agent_service,
            haiku_client=None,
            vision_radius=3,
        )

        features = {
            "terrain": ["stone to the southwest"],
            "objects": [],
            "agents": ["Sage to the north"],
            "standing_on": "Foundation Stone",
        }

        prose = await builder._generate_narrative(features, "night", Weather.RAINY)

        # Should produce meaningful prose
        assert len(prose) > 20
        # Should feel different from clear morning (night/rain atmosphere)
        assert prose.strip()

    @pytest.mark.asyncio
    async def test_generate_narrative_with_named_place(self, mock_world_service, mock_agent_service):
        """Test narrative includes named place naturally."""
        builder = PerceptionBuilder(
            world_service=mock_world_service,
            agent_service=mock_agent_service,
            haiku_client=None,
            vision_radius=3,
        )

        features = {
            "terrain": [],
            "objects": [],
            "agents": [],
            "standing_on": "The Old Oak",
        }

        prose = await builder._generate_narrative(features, "afternoon", Weather.CLOUDY)

        # Should produce meaningful prose
        assert len(prose) > 20
        # Should mention the named place in some way
        assert "oak" in prose.lower() or "stand" in prose.lower() or "place" in prose.lower()

    @pytest.mark.asyncio
    async def test_generate_narrative_foggy_evening(self, mock_world_service, mock_agent_service):
        """Test narrative with foggy weather adds atmosphere."""
        builder = PerceptionBuilder(
            world_service=mock_world_service,
            agent_service=mock_agent_service,
            haiku_client=None,
            vision_radius=3,
        )

        features = {
            "terrain": ["hill in multiple directions", "coast to the south"],
            "objects": [],
            "agents": [],
            "standing_on": None,
        }

        prose = await builder._generate_narrative(features, "evening", Weather.FOGGY)

        # Should produce meaningful prose
        assert len(prose) > 20
        # Fog should add some atmospheric element
        assert prose.strip()


@pytest.mark.integration
@pytest.mark.slow
class TestPerceptionBuildIntegration:
    """Integration tests for full perception building."""

    @pytest.mark.asyncio
    async def test_build_full_perception(self, mock_world_service, mock_agent_service, basic_agent):
        """Test building complete perception with real Haiku narrative."""
        # Configure mocks to return realistic data
        mock_agent_service.get_agent_or_raise.return_value = basic_agent

        # Set up cells with varied terrain
        cells = [
            Cell(position=Position(50, 50), terrain=Terrain.GRASS),
            Cell(position=Position(48, 50), terrain=Terrain.FOREST),
            Cell(position=Position(52, 50), terrain=Terrain.WATER),
            Cell(position=Position(50, 52), terrain=Terrain.STONE),
        ]
        mock_world_service.get_cells_in_rect.return_value = cells

        # Add a sign
        sign = Sign(
            id=generate_object_id(),
            position=Position(49, 50),
            text="Welcome",
        )
        mock_world_service.get_objects_in_rect.return_value = [sign]

        # Create another agent nearby
        other_agent = Agent(
            name=AgentName("Sage"),
            model=TEST_MODEL,
            position=Position(51, 50),
        )
        mock_agent_service.get_nearby_agents.return_value = [basic_agent, other_agent]

        # Build perception
        builder = PerceptionBuilder(
            world_service=mock_world_service,
            agent_service=mock_agent_service,
            haiku_client=None,  # Will initialize real client
            vision_radius=3,
        )

        perception = await builder.build(basic_agent.name, tick=6)  # Afternoon

        # Verify all components are present
        assert perception.grid_view  # Has grid content
        assert perception.narrative  # Has narrative
        assert perception.inventory_text == "You carry nothing."
        assert perception.journey_text is None
        assert "Sage" in perception.visible_agents_text or "unfamiliar" in perception.visible_agents_text.lower()
        assert perception.time_of_day == "afternoon"
        assert perception.weather == Weather.CLEAR
        assert perception.position == Position(50, 50)

        # Grid should contain expected symbols
        assert "@" in perception.grid_view  # Self
        assert "👤" in perception.grid_view  # Other agent

        # Narrative should have substance
        assert len(perception.narrative) > 20

    @pytest.mark.asyncio
    async def test_build_perception_with_inventory(self, mock_world_service, mock_agent_service):
        """Test perception includes inventory state."""
        agent_with_items = Agent(
            name=AgentName("TestAgent"),
            model=TEST_MODEL,
            position=Position(50, 50),
            inventory=Inventory(
                stacks=(
                    InventoryStack(item_type="wood", quantity=3),
                    InventoryStack(item_type="stone", quantity=2),
                ),
            ),
        )
        mock_agent_service.get_agent_or_raise.return_value = agent_with_items

        builder = PerceptionBuilder(
            world_service=mock_world_service,
            agent_service=mock_agent_service,
            haiku_client=None,
            vision_radius=3,
        )

        perception = await builder.build(agent_with_items.name, tick=0)

        # Inventory should be formatted
        assert "wood (3)" in perception.inventory_text
        assert "stone (2)" in perception.inventory_text
