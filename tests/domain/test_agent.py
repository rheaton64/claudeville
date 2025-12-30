"""Tests for engine.domain.agent module."""

import pytest
from pydantic import ValidationError

from engine.domain import (
    AgentName,
    LocationId,
    AgentSnapshot,
    AgentLLMModel,
    TimePeriod,
)


class TestAgentLLMModel:
    """Tests for AgentLLMModel."""

    def test_creation(self):
        """Test creating an AgentLLMModel."""
        model = AgentLLMModel(
            id="claude-3-5-sonnet-20241022",
            display_name="Claude 3.5 Sonnet",
            provider="anthropic",
        )
        assert model.id == "claude-3-5-sonnet-20241022"
        assert model.display_name == "Claude 3.5 Sonnet"
        assert model.provider == "anthropic"

    def test_immutability(self, sample_llm_model: AgentLLMModel):
        """Test that AgentLLMModel is frozen."""
        with pytest.raises(ValidationError):
            sample_llm_model.id = "new-model"  # type: ignore

    def test_serialization_roundtrip(self, sample_llm_model: AgentLLMModel):
        """Test model_dump and model_validate roundtrip."""
        data = sample_llm_model.model_dump()
        restored = AgentLLMModel.model_validate(data)
        assert restored == sample_llm_model


class TestAgentSnapshot:
    """Tests for AgentSnapshot."""

    def test_creation_with_all_fields(self, sample_llm_model: AgentLLMModel):
        """Test creating an AgentSnapshot with all fields."""
        agent = AgentSnapshot(
            name=AgentName("TestAgent"),
            model=sample_llm_model,
            personality="Test personality",
            job="Tester",
            interests=("testing", "debugging"),
            note_to_self="Remember to test",
            location=LocationId("test-location"),
            mood="neutral",
            energy=75,
            goals=("test all the code",),
            relationships={AgentName("Other"): "friend"},
            is_sleeping=False,
            sleep_started_tick=None,
            sleep_started_time_period=None,
            session_id="session-123",
        )
        assert agent.name == "TestAgent"
        assert agent.personality == "Test personality"
        assert agent.energy == 75
        assert agent.session_id == "session-123"

    def test_default_values(self, sample_llm_model: AgentLLMModel):
        """Test default values for optional fields."""
        agent = AgentSnapshot(
            name=AgentName("Minimal"),
            model=sample_llm_model,
            personality="Simple",
            job="Worker",
            interests=(),
            note_to_self="",
            location=LocationId("somewhere"),
            mood="calm",
            energy=50,
            goals=(),
            relationships={},
        )
        assert agent.is_sleeping is False
        assert agent.sleep_started_tick is None
        assert agent.sleep_started_time_period is None
        assert agent.session_id is None

    def test_immutability(self, sample_agent: AgentSnapshot):
        """Test that AgentSnapshot is frozen."""
        with pytest.raises(ValidationError):
            sample_agent.mood = "happy"  # type: ignore

    def test_serialization_roundtrip(self, sample_agent: AgentSnapshot):
        """Test model_dump and model_validate roundtrip."""
        data = sample_agent.model_dump()
        restored = AgentSnapshot.model_validate(data)
        assert restored == sample_agent

    def test_sleeping_agent_fields(self, sleeping_agent: AgentSnapshot):
        """Test that sleeping agent has correct sleep fields."""
        assert sleeping_agent.is_sleeping is True
        assert sleeping_agent.sleep_started_tick == 10
        assert sleeping_agent.sleep_started_time_period == TimePeriod.EVENING

    def test_relationships_dict(self, sample_agent: AgentSnapshot):
        """Test relationships dictionary."""
        assert AgentName("Sage") in sample_agent.relationships
        assert sample_agent.relationships[AgentName("Sage")] == "close friend"

    def test_interests_tuple(self, sample_agent: AgentSnapshot):
        """Test interests as tuple."""
        assert isinstance(sample_agent.interests, tuple)
        assert "painting" in sample_agent.interests

    def test_goals_tuple(self, sample_agent: AgentSnapshot):
        """Test goals as tuple."""
        assert isinstance(sample_agent.goals, tuple)
        assert len(sample_agent.goals) >= 1


class TestAgentSnapshotUpdates:
    """Tests for creating updated agent snapshots."""

    def test_update_location_creates_new_snapshot(self, sample_agent: AgentSnapshot):
        """Test updating location creates a new snapshot."""
        new_location = LocationId("garden")
        updated = AgentSnapshot(**{
            **sample_agent.model_dump(),
            "location": new_location,
        })
        assert updated.location == new_location
        assert sample_agent.location != new_location  # Original unchanged

    def test_update_mood_creates_new_snapshot(self, sample_agent: AgentSnapshot):
        """Test updating mood creates a new snapshot."""
        updated = AgentSnapshot(**{
            **sample_agent.model_dump(),
            "mood": "excited",
        })
        assert updated.mood == "excited"
        assert sample_agent.mood != "excited"

    def test_update_energy_creates_new_snapshot(self, sample_agent: AgentSnapshot):
        """Test updating energy creates a new snapshot."""
        updated = AgentSnapshot(**{
            **sample_agent.model_dump(),
            "energy": 100,
        })
        assert updated.energy == 100

    def test_update_sleep_state_creates_new_snapshot(self, sample_agent: AgentSnapshot):
        """Test updating sleep state creates a new snapshot."""
        updated = AgentSnapshot(**{
            **sample_agent.model_dump(),
            "is_sleeping": True,
            "sleep_started_tick": 15,
            "sleep_started_time_period": TimePeriod.NIGHT,
        })
        assert updated.is_sleeping is True
        assert updated.sleep_started_tick == 15
        assert updated.sleep_started_time_period == TimePeriod.NIGHT
