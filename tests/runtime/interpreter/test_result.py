"""Tests for engine.runtime.interpreter.result module."""

import pytest
from pydantic import ValidationError

from engine.runtime.interpreter import AgentTurnResult, MutableTurnResult


class TestAgentTurnResult:
    """Tests for AgentTurnResult."""

    def test_creation_minimal(self):
        """Test creating with just narrative."""
        result = AgentTurnResult(narrative="I walked to the garden.")

        assert result.narrative == "I walked to the garden."
        assert result.movement is None
        assert result.mood_expressed is None
        assert result.wants_to_sleep is False
        assert result.actions_described == ()

    def test_creation_full(self):
        """Test creating with all fields."""
        result = AgentTurnResult(
            narrative="I felt happy walking to the garden where I tended flowers.",
            movement="garden",
            movement_narrative_start="tended flowers",
            proposes_moving_together=None,
            mood_expressed="happy",
            wants_to_rest=False,
            wants_to_sleep=False,
            actions_described=("tended flowers", "watered plants"),
            suggested_next_speaker="Sage",
        )

        assert result.movement == "garden"
        assert result.mood_expressed == "happy"
        assert len(result.actions_described) == 2
        assert result.suggested_next_speaker == "Sage"

    def test_immutability(self):
        """Test result is frozen."""
        result = AgentTurnResult(narrative="Hello")

        with pytest.raises(ValidationError):
            result.narrative = "Changed"  # type: ignore

    def test_actions_described_tuple(self):
        """Test actions_described is a tuple."""
        result = AgentTurnResult(
            narrative="Did things",
            actions_described=("action1", "action2"),
        )

        assert isinstance(result.actions_described, tuple)


class TestAgentTurnResultGetArrivalNarrative:
    """Tests for get_arrival_narrative method."""

    def test_full_narrative_when_no_start_marker(self):
        """Test returns full narrative when no arrival marker."""
        result = AgentTurnResult(
            narrative="I walked through the village.",
            movement="garden",
        )

        assert result.get_arrival_narrative() == "I walked through the village."

    def test_partial_narrative_with_start_marker(self):
        """Test returns narrative from arrival marker."""
        result = AgentTurnResult(
            narrative="I decided to leave. I arrived at the garden and tended the flowers.",
            movement="garden",
            movement_narrative_start="I arrived at",
        )

        assert result.get_arrival_narrative() == "I arrived at the garden and tended the flowers."

    def test_full_narrative_when_marker_not_found(self):
        """Test returns full narrative when marker not in text."""
        result = AgentTurnResult(
            narrative="I walked to the garden.",
            movement="garden",
            movement_narrative_start="This text is not in narrative",
        )

        assert result.get_arrival_narrative() == "I walked to the garden."


class TestMutableTurnResult:
    """Tests for MutableTurnResult builder."""

    def test_creation(self):
        """Test creating mutable result."""
        result = MutableTurnResult(narrative="Test narrative")

        assert result.narrative == "Test narrative"
        assert result.movement is None
        assert result.actions_described == []

    def test_mutability(self):
        """Test fields can be modified."""
        result = MutableTurnResult(narrative="Test")

        result.movement = "garden"
        result.mood_expressed = "happy"
        result.wants_to_sleep = True
        result.actions_described.append("did something")

        assert result.movement == "garden"
        assert result.mood_expressed == "happy"
        assert result.wants_to_sleep is True
        assert len(result.actions_described) == 1

    def test_to_result_basic(self):
        """Test converting to frozen result."""
        mutable = MutableTurnResult(narrative="Test narrative")
        mutable.movement = "library"

        frozen = mutable.to_result()

        assert isinstance(frozen, AgentTurnResult)
        assert frozen.narrative == "Test narrative"
        assert frozen.movement == "library"

    def test_to_result_converts_actions_to_tuple(self):
        """Test actions list is converted to tuple."""
        mutable = MutableTurnResult(narrative="Test")
        mutable.actions_described.append("action1")
        mutable.actions_described.append("action2")

        frozen = mutable.to_result()

        assert isinstance(frozen.actions_described, tuple)
        assert frozen.actions_described == ("action1", "action2")

    def test_to_result_all_fields(self):
        """Test all fields are transferred correctly."""
        mutable = MutableTurnResult(narrative="Full test")
        mutable.movement = "garden"
        mutable.movement_narrative_start = "arrived at"
        mutable.proposes_moving_together = "library"
        mutable.mood_expressed = "curious"
        mutable.wants_to_rest = True
        mutable.wants_to_sleep = False
        mutable.actions_described = ["read", "wrote"]
        mutable.suggested_next_speaker = "Ember"

        frozen = mutable.to_result()

        assert frozen.movement == "garden"
        assert frozen.movement_narrative_start == "arrived at"
        assert frozen.proposes_moving_together == "library"
        assert frozen.mood_expressed == "curious"
        assert frozen.wants_to_rest is True
        assert frozen.wants_to_sleep is False
        assert frozen.actions_described == ("read", "wrote")
        assert frozen.suggested_next_speaker == "Ember"
