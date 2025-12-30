"""Tests for engine.runtime.interpreter.registry module."""

import pytest

from engine.runtime.interpreter.registry import (
    OBSERVATION_REGISTRY,
    ObservationAction,
    InterpreterContext,
    register_observation,
    get_interpreter_tools,
    get_tool_names,
    match_destination,
    process_movement,
    process_propose_move_together,
    process_next_speaker,
)
from engine.runtime.interpreter import MutableTurnResult


class TestObservationRegistry:
    """Tests for the observation registry."""

    def test_registry_has_standard_observations(self):
        """Test standard observations are registered."""
        expected_names = [
            "report_movement",
            "report_mood",
            "report_resting",
            "report_action",
            "report_propose_move_together",
            "report_sleeping",
            "report_next_speaker",
        ]

        for name in expected_names:
            assert name in OBSERVATION_REGISTRY, f"Missing: {name}"

    def test_get_tool_names(self):
        """Test getting all tool names."""
        names = get_tool_names()

        assert "report_movement" in names
        assert "report_mood" in names
        assert len(names) >= 7

    def test_get_interpreter_tools(self):
        """Test generating tool definitions."""
        tools = get_interpreter_tools()

        assert len(tools) >= 7
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool


class TestObservationAction:
    """Tests for ObservationAction dataclass."""

    def test_basic_observation(self):
        """Test creating a basic observation."""
        action = ObservationAction(
            name="test_action",
            description="A test action",
            input_schema={"type": "object", "properties": {}},
            result_field="test_field",
        )

        assert action.name == "test_action"
        assert action.is_list_field is False
        assert action.is_bool_field is False
        assert action.processor is None

    def test_list_field_observation(self):
        """Test observation for list field."""
        action = ObservationAction(
            name="test_list",
            description="List action",
            input_schema={"type": "object", "properties": {}},
            result_field="actions_described",
            is_list_field=True,
        )

        assert action.is_list_field is True

    def test_bool_field_observation(self):
        """Test observation for bool field."""
        action = ObservationAction(
            name="test_bool",
            description="Bool action",
            input_schema={"type": "object", "properties": {}},
            result_field="wants_to_sleep",
            is_bool_field=True,
        )

        assert action.is_bool_field is True


class TestInterpreterContext:
    """Tests for InterpreterContext dataclass."""

    def test_creation(self):
        """Test creating interpreter context."""
        ctx = InterpreterContext(
            current_location="workshop",
            available_paths=["library", "garden"],
            present_agents=["Sage", "River"],
        )

        assert ctx.current_location == "workshop"
        assert "library" in ctx.available_paths
        assert "Sage" in ctx.present_agents


class TestMatchDestination:
    """Tests for destination matching."""

    def test_exact_match(self):
        """Test exact destination match."""
        result = match_destination("library", ["library", "garden", "workshop"])

        assert result == "library"

    def test_substring_match(self):
        """Test substring match."""
        result = match_destination("the library", ["library", "garden"])

        assert result == "library"

    def test_case_insensitive(self):
        """Test case insensitive matching."""
        result = match_destination("LIBRARY", ["library", "garden"])

        assert result == "library"

    def test_word_match(self):
        """Test word-based matching."""
        result = match_destination("village_square", ["square", "garden"])

        assert result == "square"

    def test_no_match_returns_none(self):
        """Test no match returns None."""
        result = match_destination("nowhere", ["library", "garden"])

        assert result is None

    def test_empty_destination_returns_none(self):
        """Test empty destination returns None."""
        result = match_destination("", ["library", "garden"])

        assert result is None

    def test_empty_paths_returns_none(self):
        """Test empty paths list returns None."""
        result = match_destination("library", [])

        assert result is None


class TestProcessMovement:
    """Tests for movement processor."""

    def test_basic_movement(self):
        """Test processing movement."""
        result = MutableTurnResult(narrative="I went to the library.")
        context = InterpreterContext(
            current_location="workshop",
            available_paths=["library", "garden"],
            present_agents=[],
        )

        process_movement(
            {"destination": "library", "arrival_starts_with": "I arrived"},
            result,
            context,
        )

        assert result.movement == "library"
        assert result.movement_narrative_start == "I arrived"

    def test_movement_with_fuzzy_destination(self):
        """Test movement with fuzzy destination matching."""
        result = MutableTurnResult(narrative="Test")
        context = InterpreterContext(
            current_location="workshop",
            available_paths=["library", "garden"],
            present_agents=[],
        )

        process_movement(
            {"destination": "the library building", "arrival_starts_with": ""},
            result,
            context,
        )

        assert result.movement == "library"

    def test_movement_no_match(self):
        """Test movement with unmatched destination."""
        result = MutableTurnResult(narrative="Test")
        context = InterpreterContext(
            current_location="workshop",
            available_paths=["library", "garden"],
            present_agents=[],
        )

        process_movement(
            {"destination": "nowhere", "arrival_starts_with": ""},
            result,
            context,
        )

        assert result.movement is None


class TestProcessProposeMoveTogetherProcessor:
    """Tests for move together proposal processor."""

    def test_propose_move_together(self):
        """Test processing move together proposal."""
        result = MutableTurnResult(narrative="Let's go to the garden!")
        context = InterpreterContext(
            current_location="workshop",
            available_paths=["library", "garden"],
            present_agents=["Sage"],
        )

        process_propose_move_together(
            {"destination": "garden"},
            result,
            context,
        )

        assert result.proposes_moving_together == "garden"


class TestProcessNextSpeaker:
    """Tests for next speaker processor."""

    def test_valid_next_speaker(self):
        """Test processing valid next speaker."""
        result = MutableTurnResult(narrative="What do you think, Sage?")
        context = InterpreterContext(
            current_location="workshop",
            available_paths=[],
            present_agents=["Sage", "River"],
        )

        process_next_speaker(
            {"next_speaker": "Sage"},
            result,
            context,
        )

        assert result.suggested_next_speaker == "Sage"

    def test_invalid_next_speaker(self):
        """Test processing invalid next speaker (not present)."""
        result = MutableTurnResult(narrative="What do you think?")
        context = InterpreterContext(
            current_location="workshop",
            available_paths=[],
            present_agents=["River"],  # Sage not present
        )

        process_next_speaker(
            {"next_speaker": "Sage"},
            result,
            context,
        )

        # Should not set because Sage isn't present
        assert result.suggested_next_speaker is None


class TestRegisterObservation:
    """Tests for register_observation function."""

    def test_register_new_observation(self):
        """Test registering a new observation."""
        # Save original state
        original_keys = set(OBSERVATION_REGISTRY.keys())

        try:
            register_observation(
                name="test_custom_observation",
                description="A custom test observation",
                input_schema={"type": "object", "properties": {}},
                result_field="movement",
            )

            assert "test_custom_observation" in OBSERVATION_REGISTRY
        finally:
            # Clean up
            if "test_custom_observation" in OBSERVATION_REGISTRY:
                del OBSERVATION_REGISTRY["test_custom_observation"]
