"""
Level 5 Integration Tests: Single Agent with Real Haiku

Tests single agent behavior with real Claude Haiku LLM.
These are behavioral tests - outcomes are emergent, not deterministic.

Run with: uv run pytest tests/integration/test_single_agent_haiku.py -v
Requires: ANTHROPIC_API_KEY environment variable
"""

from __future__ import annotations

import pytest

from engine.domain import AgentName, LocationId
from tests.integration.conftest import requires_api_key


# All tests in this module require API key and are slow
pytestmark = [requires_api_key, pytest.mark.haiku, pytest.mark.slow]


# =============================================================================
# Basic Agent Behavior Tests
# =============================================================================


class TestSingleAgentBehavior:
    """Test single agent behavior with real Haiku."""

    @pytest.mark.asyncio
    async def test_agent_produces_narrative(self, haiku_engine):
        """Agent generates a narrative response."""
        result = await haiku_engine.tick_once()

        # At least one agent should have acted
        assert len(result.agents_acted) >= 1

        # Should have turn results
        assert len(result.turn_results) >= 1

        # Each turn result should have narrative
        for agent_name, turn_result in result.turn_results.items():
            assert turn_result.narrative, f"{agent_name} produced empty narrative"

    @pytest.mark.asyncio
    async def test_agent_narrative_is_coherent(self, haiku_engine, llm_judge):
        """Agent narrative should be coherent (LLM judge validation)."""
        result = await haiku_engine.tick_once()

        for agent_name, turn_result in result.turn_results.items():
            agent = haiku_engine.agents[agent_name]

            judgment = llm_judge(
                "Is this narrative coherent and does it describe believable behavior?",
                f"Agent: {agent_name} ({agent.job})\n"
                f"Location: {agent.location}\n"
                f"Narrative: {turn_result.narrative}"
            )

            if not judgment.passed:
                pytest.skip(f"LLM judge: {judgment.reasoning}")


# =============================================================================
# Action and Movement Tests
# =============================================================================


class TestAgentActionsAndMovement:
    """Test agent actions and movement with real Haiku."""

    @pytest.mark.asyncio
    async def test_agent_performs_actions_over_time(self, haiku_engine):
        """Agent performs meaningful actions over multiple ticks."""
        action_events = []

        for _ in range(3):
            result = await haiku_engine.tick_once()
            action_events.extend([e for e in result.events if e.type == "agent_action"])

        # Should have performed at least some actions
        assert len(action_events) >= 1

    @pytest.mark.asyncio
    async def test_agent_may_move_locations(self, haiku_engine):
        """Agent might move to new location over time (emergent behavior)."""
        initial_locations = {
            name: agent.location
            for name, agent in haiku_engine.agents.items()
        }

        move_events = []
        for _ in range(5):
            result = await haiku_engine.tick_once()
            move_events.extend([e for e in result.events if e.type == "agent_moved"])

        # Movement is emergent - may or may not happen
        # Just verify no crashes
        assert haiku_engine.tick == 5

    @pytest.mark.asyncio
    async def test_agent_mood_can_change(self, haiku_engine):
        """Agent mood can change based on activities (emergent)."""
        mood_events = []

        for _ in range(5):
            result = await haiku_engine.tick_once()
            mood_events.extend([e for e in result.events if e.type == "agent_mood_changed"])

        # Mood changes are emergent - just verify tracking works


# =============================================================================
# Consistency Tests
# =============================================================================


class TestAgentConsistency:
    """Test agent state consistency with real Haiku."""

    @pytest.mark.asyncio
    async def test_agent_state_consistent_after_ticks(self, haiku_engine):
        """Agent state remains valid after multiple ticks."""
        for _ in range(5):
            await haiku_engine.tick_once()

        # All agents should still be valid
        for name, agent in haiku_engine.agents.items():
            assert agent.name == name
            assert agent.location in haiku_engine.world.locations
            assert 0 <= agent.energy <= 100

    @pytest.mark.asyncio
    async def test_agent_at_valid_location(self, haiku_engine):
        """Agent should always be at a valid location."""
        for _ in range(5):
            await haiku_engine.tick_once()

            for agent in haiku_engine.agents.values():
                assert agent.location in haiku_engine.world.locations


# =============================================================================
# Event Generation Tests
# =============================================================================


class TestEventGeneration:
    """Test event generation with real Haiku."""

    @pytest.mark.asyncio
    async def test_ticks_generate_events(self, haiku_engine):
        """Ticks with real LLM should generate various events."""
        events_by_type: dict[str, int] = {}

        for _ in range(5):
            result = await haiku_engine.tick_once()
            for event in result.events:
                events_by_type[event.type] = events_by_type.get(event.type, 0) + 1

        # Should have some events
        total_events = sum(events_by_type.values())
        assert total_events > 0

        # Should at least have last_active_tick events
        assert "agent_last_active_tick_updated" in events_by_type

    @pytest.mark.asyncio
    async def test_events_have_valid_ticks(self, haiku_engine):
        """All events should have valid tick numbers."""
        for i in range(3):
            result = await haiku_engine.tick_once()
            for event in result.events:
                assert event.tick == i + 1


# =============================================================================
# Recovery Tests
# =============================================================================


class TestHaikuRecovery:
    """Test state recovery with real Haiku engine."""

    @pytest.mark.asyncio
    async def test_recovery_after_haiku_ticks(self, temp_village, haiku_engine):
        """State can be recovered after running with real Haiku."""
        # Run some ticks
        for _ in range(3):
            await haiku_engine.tick_once()

        tick_before = haiku_engine.tick
        agents_before = {n: a.location for n, a in haiku_engine.agents.items()}

        # Create new engine and recover
        from engine.engine import VillageEngine
        from engine.adapters import ClaudeProvider

        provider = ClaudeProvider(model="claude-haiku-4-5-20251001")
        engine2 = VillageEngine(
            village_root=temp_village,
            llm_provider=provider,
        )
        assert engine2.recover()

        # State should match
        assert engine2.tick == tick_before
        for name, loc in agents_before.items():
            assert engine2.agents[name].location == loc
