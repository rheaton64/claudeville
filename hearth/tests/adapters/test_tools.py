"""Unit tests for Hearth action tools."""

import pytest

from adapters.tools import (
    HEARTH_TOOL_REGISTRY,
    HEARTH_TOOL_NAMES,
    HearthTool,
    _direction_from_str,
    _build_journey_action,
)
from core.types import Direction, Position, AgentName
from core.actions import (
    WalkAction,
    GatherAction,
    JourneyAction,
    ExamineAction,
    CombineAction,
    WriteSignAction,
    SleepAction,
)


class TestToolRegistry:
    """Tests for the tool registry."""

    def test_registry_has_expected_count(self):
        """Registry should have all 27 tools."""
        assert len(HEARTH_TOOL_REGISTRY) == 27

    def test_tool_names_have_mcp_prefix(self):
        """Tool names for Claude should have MCP prefix."""
        for name in HEARTH_TOOL_NAMES:
            assert name.startswith("mcp__hearth__"), f"{name} missing MCP prefix"

    def test_all_tools_have_required_fields(self):
        """Each tool should have name, description, input_schema, action_builder."""
        for name, tool in HEARTH_TOOL_REGISTRY.items():
            assert isinstance(tool, HearthTool)
            assert tool.name == name
            assert tool.description
            assert isinstance(tool.input_schema, dict)
            assert callable(tool.action_builder)

    def test_movement_tools_exist(self):
        """Movement tools should be in registry."""
        assert "walk" in HEARTH_TOOL_REGISTRY
        assert "approach" in HEARTH_TOOL_REGISTRY
        assert "journey" in HEARTH_TOOL_REGISTRY

    def test_perception_tools_exist(self):
        """Perception tools should be in registry."""
        assert "examine" in HEARTH_TOOL_REGISTRY
        assert "sense_others" in HEARTH_TOOL_REGISTRY

    def test_interaction_tools_exist(self):
        """Interaction tools should be in registry."""
        assert "take" in HEARTH_TOOL_REGISTRY
        assert "drop" in HEARTH_TOOL_REGISTRY
        assert "give" in HEARTH_TOOL_REGISTRY
        assert "gather" in HEARTH_TOOL_REGISTRY

    def test_material_tools_exist(self):
        """Material/crafting tools should be in registry."""
        assert "combine" in HEARTH_TOOL_REGISTRY
        assert "work" in HEARTH_TOOL_REGISTRY
        assert "apply" in HEARTH_TOOL_REGISTRY

    def test_building_tools_exist(self):
        """Building tools should be in registry."""
        assert "build_shelter" in HEARTH_TOOL_REGISTRY
        assert "place_wall" in HEARTH_TOOL_REGISTRY
        assert "place_door" in HEARTH_TOOL_REGISTRY
        assert "place_item" in HEARTH_TOOL_REGISTRY
        assert "remove_wall" in HEARTH_TOOL_REGISTRY

    def test_expression_tools_exist(self):
        """Expression tools should be in registry."""
        assert "write_sign" in HEARTH_TOOL_REGISTRY
        assert "read_sign" in HEARTH_TOOL_REGISTRY
        assert "name_place" in HEARTH_TOOL_REGISTRY

    def test_social_tools_exist(self):
        """Social tools (stubs) should be in registry."""
        assert "speak" in HEARTH_TOOL_REGISTRY
        assert "invite" in HEARTH_TOOL_REGISTRY
        assert "accept_invite" in HEARTH_TOOL_REGISTRY
        assert "decline_invite" in HEARTH_TOOL_REGISTRY
        assert "join_conversation" in HEARTH_TOOL_REGISTRY
        assert "leave_conversation" in HEARTH_TOOL_REGISTRY

    def test_state_tools_exist(self):
        """State tools should be in registry."""
        assert "sleep" in HEARTH_TOOL_REGISTRY


class TestDirectionConversion:
    """Tests for direction string conversion."""

    def test_cardinal_directions(self):
        """Cardinal directions should convert correctly."""
        assert _direction_from_str("north") == Direction.NORTH
        assert _direction_from_str("south") == Direction.SOUTH
        assert _direction_from_str("east") == Direction.EAST
        assert _direction_from_str("west") == Direction.WEST

    def test_case_insensitive(self):
        """Direction conversion should be case insensitive."""
        assert _direction_from_str("NORTH") == Direction.NORTH
        assert _direction_from_str("North") == Direction.NORTH
        assert _direction_from_str("nOrTh") == Direction.NORTH

    def test_unknown_defaults_to_north(self):
        """Unknown direction should default to NORTH."""
        assert _direction_from_str("northeast") == Direction.NORTH
        assert _direction_from_str("invalid") == Direction.NORTH


class TestJourneyActionBuilder:
    """Tests for journey action destination parsing."""

    def test_coordinates_parsing(self):
        """Coordinate strings should parse to Position."""
        action = _build_journey_action("100,150")
        assert isinstance(action, JourneyAction)
        assert action.destination == Position(100, 150)

    def test_coordinates_with_spaces(self):
        """Coordinates with spaces should parse correctly."""
        action = _build_journey_action("100, 150")
        assert action.destination == Position(100, 150)

    def test_landmark_name(self):
        """Non-coordinate strings should be landmark names."""
        action = _build_journey_action("The Clearing")
        assert isinstance(action, JourneyAction)
        assert action.destination == "The Clearing"

    def test_invalid_coordinates_treated_as_landmark(self):
        """Invalid coordinate format should be treated as landmark."""
        action = _build_journey_action("abc,xyz")
        assert action.destination == "abc,xyz"


class TestActionBuilders:
    """Tests for individual action builders."""

    def test_walk_action_builder(self):
        """Walk action builder should create correct action."""
        tool = HEARTH_TOOL_REGISTRY["walk"]
        action = tool.action_builder({"direction": "north"})
        assert isinstance(action, WalkAction)
        assert action.direction == Direction.NORTH

    def test_gather_action_builder(self):
        """Gather action builder should handle optional resource_type."""
        tool = HEARTH_TOOL_REGISTRY["gather"]

        # Without resource type
        action = tool.action_builder({})
        assert isinstance(action, GatherAction)
        assert action.resource_type is None

        # With resource type
        action = tool.action_builder({"resource_type": "wood"})
        assert action.resource_type == "wood"

    def test_examine_action_builder(self):
        """Examine action builder should accept direction."""
        tool = HEARTH_TOOL_REGISTRY["examine"]
        action = tool.action_builder({"direction": "north"})
        assert isinstance(action, ExamineAction)
        assert action.direction == "north"

    def test_combine_action_builder(self):
        """Combine action builder should handle item list."""
        tool = HEARTH_TOOL_REGISTRY["combine"]
        action = tool.action_builder({"items": ["wood", "fiber"]})
        assert isinstance(action, CombineAction)
        assert action.items == ("wood", "fiber")

    def test_write_sign_action_builder(self):
        """Write sign action builder should accept text."""
        tool = HEARTH_TOOL_REGISTRY["write_sign"]
        action = tool.action_builder({"text": "Hello, world!"})
        assert isinstance(action, WriteSignAction)
        assert action.text == "Hello, world!"

    def test_sleep_action_builder(self):
        """Sleep action builder should work with no args."""
        tool = HEARTH_TOOL_REGISTRY["sleep"]
        action = tool.action_builder({})
        assert isinstance(action, SleepAction)


class TestToolSchemas:
    """Tests for tool input schemas."""

    def test_walk_schema(self):
        """Walk tool should require direction enum."""
        schema = HEARTH_TOOL_REGISTRY["walk"].input_schema
        assert "direction" in schema["properties"]
        assert schema["properties"]["direction"]["enum"] == ["north", "south", "east", "west"]
        assert "direction" in schema.get("required", [])

    def test_examine_schema(self):
        """Examine tool should require direction."""
        schema = HEARTH_TOOL_REGISTRY["examine"].input_schema
        assert "direction" in schema["properties"]
        assert schema["properties"]["direction"]["enum"] == ["north", "south", "east", "west", "down"]
        assert "direction" in schema.get("required", [])

    def test_combine_schema_requires_items_array(self):
        """Combine tool should require items array with minItems."""
        schema = HEARTH_TOOL_REGISTRY["combine"].input_schema
        assert "items" in schema["properties"]
        assert schema["properties"]["items"]["type"] == "array"
        assert schema["properties"]["items"].get("minItems", 0) >= 2
