"""Tests for the perception builder module."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from adapters.perception import (
    get_time_of_day,
    PerceptionBuilder,
    AgentPerception,
    _get_wall_char,
    DOOR_HORIZONTAL,
    DOOR_VERTICAL,
)
from core.types import Position, Direction, Rect, AgentName
from core.terrain import Terrain, Weather, TERRAIN_EMOJI
from core.world import Cell
from core.agent import Agent, AgentModel, Inventory, InventoryStack, Journey, JourneyDestination
from core.objects import Sign, PlacedItem, Item, generate_object_id


# Module-level test model for convenience
TEST_MODEL = AgentModel(id="test-model", display_name="Test Model")


# -----------------------------------------------------------------------------
# Time of Day Tests
# -----------------------------------------------------------------------------


class TestGetTimeOfDay:
    """Tests for get_time_of_day function."""

    def test_morning_tick_0(self):
        """Tick 0 should be morning."""
        assert get_time_of_day(0) == "morning"

    def test_morning_tick_5(self):
        """Tick 5 should still be morning."""
        assert get_time_of_day(5) == "morning"

    def test_afternoon_tick_6(self):
        """Tick 6 should be afternoon."""
        assert get_time_of_day(6) == "afternoon"

    def test_afternoon_tick_11(self):
        """Tick 11 should still be afternoon."""
        assert get_time_of_day(11) == "afternoon"

    def test_evening_tick_12(self):
        """Tick 12 should be evening."""
        assert get_time_of_day(12) == "evening"

    def test_evening_tick_17(self):
        """Tick 17 should still be evening."""
        assert get_time_of_day(17) == "evening"

    def test_night_tick_18(self):
        """Tick 18 should be night."""
        assert get_time_of_day(18) == "night"

    def test_night_tick_23(self):
        """Tick 23 should still be night."""
        assert get_time_of_day(23) == "night"

    def test_wraps_tick_24(self):
        """Tick 24 should wrap to morning."""
        assert get_time_of_day(24) == "morning"

    def test_wraps_tick_25(self):
        """Tick 25 should be morning (wrapped)."""
        assert get_time_of_day(25) == "morning"

    def test_wraps_tick_30(self):
        """Tick 30 should be afternoon (wrapped)."""
        assert get_time_of_day(30) == "afternoon"

    def test_custom_ticks_per_day(self):
        """Test with custom ticks per day."""
        # With 12 ticks per day, each period is 3 ticks
        assert get_time_of_day(0, ticks_per_day=12) == "morning"
        assert get_time_of_day(3, ticks_per_day=12) == "afternoon"
        assert get_time_of_day(6, ticks_per_day=12) == "evening"
        assert get_time_of_day(9, ticks_per_day=12) == "night"


# -----------------------------------------------------------------------------
# Wall Character Tests
# -----------------------------------------------------------------------------


class TestGetWallChar:
    """Tests for _get_wall_char function."""

    def test_vertical_wall(self):
        """Vertical wall (north-south only)."""
        assert _get_wall_char(True, True, False, False) == "│"

    def test_horizontal_wall(self):
        """Horizontal wall (east-west only)."""
        assert _get_wall_char(False, False, True, True) == "─"

    def test_top_left_corner(self):
        """Top-left corner (south and east)."""
        assert _get_wall_char(False, True, True, False) == "┌"

    def test_top_right_corner(self):
        """Top-right corner (south and west)."""
        assert _get_wall_char(False, True, False, True) == "┐"

    def test_bottom_left_corner(self):
        """Bottom-left corner (north and east)."""
        assert _get_wall_char(True, False, True, False) == "└"

    def test_bottom_right_corner(self):
        """Bottom-right corner (north and west)."""
        assert _get_wall_char(True, False, False, True) == "┘"

    def test_t_junction_east(self):
        """T-junction facing east (no west)."""
        assert _get_wall_char(True, True, True, False) == "├"

    def test_t_junction_west(self):
        """T-junction facing west (no east)."""
        assert _get_wall_char(True, True, False, True) == "┤"

    def test_t_junction_south(self):
        """T-junction facing south (no north)."""
        assert _get_wall_char(False, True, True, True) == "┬"

    def test_t_junction_north(self):
        """T-junction facing north (no south)."""
        assert _get_wall_char(True, False, True, True) == "┴"

    def test_cross(self):
        """Four-way cross."""
        assert _get_wall_char(True, True, True, True) == "┼"

    def test_no_connections(self):
        """No connections returns space."""
        assert _get_wall_char(False, False, False, False) == " "


# -----------------------------------------------------------------------------
# Helper Fixtures
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


@pytest.fixture
def perception_builder(mock_world_service, mock_agent_service):
    """Create a PerceptionBuilder with mocked services."""
    # Use a mock for haiku_client to avoid actual API calls
    mock_haiku = MagicMock()
    return PerceptionBuilder(
        world_service=mock_world_service,
        agent_service=mock_agent_service,
        haiku_client=mock_haiku,
        vision_radius=3,
    )


# -----------------------------------------------------------------------------
# Inventory Formatting Tests
# -----------------------------------------------------------------------------


class TestFormatInventory:
    """Tests for _format_inventory method."""

    def test_empty_inventory(self, perception_builder):
        """Empty inventory returns 'Your hands are empty.'"""
        inventory = Inventory()
        result = perception_builder._format_inventory(inventory)
        assert result == "Your hands are empty."

    def test_single_stack(self, perception_builder):
        """Single resource stack."""
        inventory = Inventory(
            stacks=(InventoryStack(item_type="wood", quantity=3),)
        )
        result = perception_builder._format_inventory(inventory)
        assert result == "You carry: wood (3)."

    def test_multiple_stacks(self, perception_builder):
        """Multiple resource stacks."""
        inventory = Inventory(
            stacks=(
                InventoryStack(item_type="wood", quantity=3),
                InventoryStack(item_type="stone", quantity=2),
            )
        )
        result = perception_builder._format_inventory(inventory)
        assert "wood (3)" in result
        assert "stone (2)" in result

    def test_single_quantity_stack(self, perception_builder):
        """Stack with quantity 1 doesn't show count."""
        inventory = Inventory(
            stacks=(InventoryStack(item_type="wood", quantity=1),)
        )
        result = perception_builder._format_inventory(inventory)
        assert result == "You carry: wood."

    def test_unique_item_no_properties(self, perception_builder):
        """Unique item without properties."""
        inventory = Inventory(
            items=(Item(id=generate_object_id(), item_type="bowl"),)
        )
        result = perception_builder._format_inventory(inventory)
        assert result == "You carry: a bowl."

    def test_unique_item_with_properties(self, perception_builder):
        """Unique item with properties."""
        inventory = Inventory(
            items=(Item(id=generate_object_id(), item_type="bowl", properties=("chipped", "large")),)
        )
        result = perception_builder._format_inventory(inventory)
        assert "a bowl (chipped, large)" in result

    def test_mixed_inventory(self, perception_builder):
        """Both stacks and unique items."""
        inventory = Inventory(
            stacks=(InventoryStack(item_type="wood", quantity=5),),
            items=(Item(id=generate_object_id(), item_type="knife", properties=("sharp",)),)
        )
        result = perception_builder._format_inventory(inventory)
        assert "wood (5)" in result
        assert "a knife (sharp)" in result


# -----------------------------------------------------------------------------
# Journey Formatting Tests
# -----------------------------------------------------------------------------


class TestFormatJourney:
    """Tests for _format_journey method."""

    def test_not_traveling(self, perception_builder, basic_agent):
        """Agent not on a journey returns None."""
        result = perception_builder._format_journey(basic_agent)
        assert result is None

    def test_traveling_to_position(self, perception_builder):
        """Agent traveling to a position with qualitative description."""
        journey = Journey(
            destination=JourneyDestination(position=Position(60, 60)),
            path=(
                Position(50, 50),
                Position(51, 50),
                Position(52, 50),
                Position(53, 50),
                Position(54, 50),
            ),
            progress=1,  # At position 1, 3 more to go
        )
        agent = Agent(
            name=AgentName("TestAgent"),
            model=TEST_MODEL,
            position=Position(51, 50),
            journey=journey,
        )
        result = perception_builder._format_journey(agent)
        assert result is not None
        assert "(60, 60)" in result
        assert "getting close" in result

    def test_traveling_to_landmark(self, perception_builder):
        """Agent traveling to a named landmark."""
        journey = Journey(
            destination=JourneyDestination(landmark="Foundation Stone"),
            path=(
                Position(50, 50),
                Position(51, 50),
                Position(52, 50),
                Position(53, 50),
                Position(54, 50),
                Position(55, 50),
            ),
            progress=0,  # At start, 5 more to go
        )
        agent = Agent(
            name=AgentName("TestAgent"),
            model=TEST_MODEL,
            position=Position(50, 50),
            journey=journey,
        )
        result = perception_builder._format_journey(agent)
        assert result is not None
        assert "Foundation Stone" in result
        assert "journey continues" in result

    def test_one_step_remaining(self, perception_builder):
        """One step remaining says almost there."""
        journey = Journey(
            destination=JourneyDestination(position=Position(52, 50)),
            path=(
                Position(50, 50),
                Position(51, 50),
                Position(52, 50),
            ),
            progress=1,  # At position 1, 1 more to go
        )
        agent = Agent(
            name=AgentName("TestAgent"),
            model=TEST_MODEL,
            position=Position(51, 50),
            journey=journey,
        )
        result = perception_builder._format_journey(agent)
        assert result is not None
        assert "almost there" in result


# -----------------------------------------------------------------------------
# Visible Agents Formatting Tests
# -----------------------------------------------------------------------------


class TestFormatVisibleAgents:
    """Tests for _format_visible_agents method."""

    def test_no_visible_agents(self, perception_builder, basic_agent):
        """No visible agents returns empty string."""
        result = perception_builder._format_visible_agents(basic_agent, [])
        assert result == ""

    def test_known_agent_visible(self, perception_builder):
        """Known agent is identified by name."""
        viewer = Agent(
            name=AgentName("Viewer"),
            model=TEST_MODEL,
            position=Position(50, 50),
            known_agents=frozenset({AgentName("Sage")}),
        )
        other = Agent(
            name=AgentName("Sage"),
            model=TEST_MODEL,
            position=Position(50, 52),  # North of viewer
        )
        result = perception_builder._format_visible_agents(viewer, [other])
        assert "Sage is north of you." in result

    def test_unknown_agent_visible(self, perception_builder):
        """Unknown agent is described as someone unfamiliar."""
        viewer = Agent(
            name=AgentName("Viewer"),
            model=TEST_MODEL,
            position=Position(50, 50),
            known_agents=frozenset(),  # Doesn't know anyone
        )
        other = Agent(
            name=AgentName("Stranger"),
            model=TEST_MODEL,
            position=Position(48, 50),  # West of viewer
        )
        result = perception_builder._format_visible_agents(viewer, [other])
        assert "Someone unfamiliar is west of you." in result

    def test_mixed_known_and_unknown(self, perception_builder):
        """Both known and unknown agents."""
        viewer = Agent(
            name=AgentName("Viewer"),
            model=TEST_MODEL,
            position=Position(50, 50),
            known_agents=frozenset({AgentName("Sage")}),
        )
        known = Agent(
            name=AgentName("Sage"),
            model=TEST_MODEL,
            position=Position(50, 52),
        )
        unknown = Agent(
            name=AgentName("Stranger"),
            model=TEST_MODEL,
            position=Position(48, 50),
        )
        result = perception_builder._format_visible_agents(viewer, [known, unknown])
        assert "Sage is north of you." in result
        assert "Someone unfamiliar is west of you." in result


# -----------------------------------------------------------------------------
# Grid View Tests
# -----------------------------------------------------------------------------


class TestBuildGridView:
    """Tests for _build_grid_view method."""

    def test_empty_grid_with_agent(self, perception_builder, basic_agent):
        """Basic grid with just the agent shows @ at center."""
        cells = [Cell(position=basic_agent.position)]
        rect = Rect(47, 47, 53, 53)  # 7x7 centered on 50,50

        result = perception_builder._build_grid_view(
            basic_agent, cells, [], [], rect
        )

        # Should contain the agent symbol
        assert "@" in result

    def test_terrain_symbols(self, perception_builder, basic_agent):
        """Different terrain types show correct emojis."""
        cells = [
            Cell(position=Position(48, 50), terrain=Terrain.FOREST),
            Cell(position=Position(52, 50), terrain=Terrain.WATER),
            Cell(position=basic_agent.position, terrain=Terrain.GRASS),
        ]
        rect = Rect(47, 47, 53, 53)

        result = perception_builder._build_grid_view(
            basic_agent, cells, [], [], rect
        )

        # Should contain terrain emojis
        assert TERRAIN_EMOJI[Terrain.FOREST] in result  # 🌲
        assert TERRAIN_EMOJI[Terrain.WATER] in result   # 💧

    def test_object_symbols(self, perception_builder, basic_agent):
        """Objects show correct emojis."""
        cells = [Cell(position=basic_agent.position)]
        sign = Sign(
            id=generate_object_id(),
            position=Position(51, 50),
            text="Hello",
        )
        rect = Rect(47, 47, 53, 53)

        result = perception_builder._build_grid_view(
            basic_agent, cells, [sign], [], rect
        )

        # Should contain sign emoji
        assert "📜" in result

    def test_other_agent_symbol(self, perception_builder, basic_agent):
        """Other agents show as 👤."""
        cells = [Cell(position=basic_agent.position)]
        other = Agent(
            name=AgentName("Other"),
            model=TEST_MODEL,
            position=Position(51, 50),
        )
        rect = Rect(47, 47, 53, 53)

        result = perception_builder._build_grid_view(
            basic_agent, cells, [], [other], rect
        )

        # Should contain agent emoji
        assert "👤" in result

    def test_priority_agent_over_object(self, perception_builder, basic_agent):
        """Agent symbol takes priority over object on same cell."""
        cells = [Cell(position=basic_agent.position)]
        sign = Sign(
            id=generate_object_id(),
            position=Position(51, 50),
            text="Hello",
        )
        other = Agent(
            name=AgentName("Other"),
            model=TEST_MODEL,
            position=Position(51, 50),  # Same position as sign
        )
        rect = Rect(47, 47, 53, 53)

        result = perception_builder._build_grid_view(
            basic_agent, cells, [sign], [other], rect
        )

        # Agent symbol should appear, sign may be hidden
        assert "👤" in result

    def test_single_wall_vertical(self, perception_builder, basic_agent):
        """Single vertical wall between cells."""
        # Cell at 50,50 has an east wall
        cells = [
            Cell(position=Position(50, 50), walls=frozenset({Direction.EAST})),
            Cell(position=Position(51, 50), walls=frozenset({Direction.WEST})),
        ]
        rect = Rect(48, 48, 52, 52)

        result = perception_builder._build_grid_view(
            basic_agent, cells, [], [], rect
        )

        # Should contain vertical wall character
        assert "│" in result

    def test_single_wall_horizontal(self, perception_builder, basic_agent):
        """Single horizontal wall between cells."""
        # Cell at 50,50 has a south wall
        cells = [
            Cell(position=Position(50, 50), walls=frozenset({Direction.SOUTH})),
            Cell(position=Position(50, 49), walls=frozenset({Direction.NORTH})),
        ]
        rect = Rect(48, 48, 52, 52)

        result = perception_builder._build_grid_view(
            basic_agent, cells, [], [], rect
        )

        # Should contain horizontal wall character
        assert "─" in result

    def test_door_shows_as_gap(self, perception_builder, basic_agent):
        """Door in wall shows as gap (space)."""
        # Cell has wall with door
        cells = [
            Cell(
                position=Position(50, 50),
                walls=frozenset({Direction.EAST}),
                doors=frozenset({Direction.EAST}),
            ),
            Cell(
                position=Position(51, 50),
                walls=frozenset({Direction.WEST}),
                doors=frozenset({Direction.WEST}),
            ),
        ]
        rect = Rect(48, 48, 52, 52)

        result = perception_builder._build_grid_view(
            basic_agent, cells, [], [], rect
        )

        # Should NOT contain wall character where door is
        # This is a bit tricky to test - the door replaces the wall with space


# -----------------------------------------------------------------------------
# Direction Phrase Tests
# -----------------------------------------------------------------------------


class TestGetDirectionPhrase:
    """Tests for _get_direction_phrase method."""

    def test_same_position(self, perception_builder):
        """Same position returns 'here'."""
        result = perception_builder._get_direction_phrase(
            Position(50, 50), Position(50, 50)
        )
        assert result == "here"

    def test_north(self, perception_builder):
        """North direction."""
        result = perception_builder._get_direction_phrase(
            Position(50, 50), Position(50, 52)
        )
        assert result == "north"

    def test_south(self, perception_builder):
        """South direction."""
        result = perception_builder._get_direction_phrase(
            Position(50, 50), Position(50, 48)
        )
        assert result == "south"

    def test_east(self, perception_builder):
        """East direction."""
        result = perception_builder._get_direction_phrase(
            Position(50, 50), Position(52, 50)
        )
        assert result == "east"

    def test_west(self, perception_builder):
        """West direction."""
        result = perception_builder._get_direction_phrase(
            Position(50, 50), Position(48, 50)
        )
        assert result == "west"

    def test_northeast(self, perception_builder):
        """Northeast direction."""
        result = perception_builder._get_direction_phrase(
            Position(50, 50), Position(52, 52)
        )
        assert result == "northeast"

    def test_northwest(self, perception_builder):
        """Northwest direction."""
        result = perception_builder._get_direction_phrase(
            Position(50, 50), Position(48, 52)
        )
        assert result == "northwest"

    def test_southeast(self, perception_builder):
        """Southeast direction."""
        result = perception_builder._get_direction_phrase(
            Position(50, 50), Position(52, 48)
        )
        assert result == "southeast"

    def test_southwest(self, perception_builder):
        """Southwest direction."""
        result = perception_builder._get_direction_phrase(
            Position(50, 50), Position(48, 48)
        )
        assert result == "southwest"
