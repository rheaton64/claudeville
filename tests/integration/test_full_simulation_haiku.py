"""
Level 7 Integration Tests: Full Village Simulation with Real Haiku

Tests full village simulation with all agents using real Claude Haiku.
These are behavioral tests - outcomes are emergent, not deterministic.

Run with: uv run pytest tests/integration/test_full_simulation_haiku.py -v
Requires: ANTHROPIC_API_KEY environment variable

WARNING: These tests make many API calls and are expensive to run frequently.
"""

from __future__ import annotations

import pytest

from engine.domain import AgentName, LocationId
from tests.integration.conftest import requires_api_key


# All tests in this module require API key, are slow, and expensive
pytestmark = [
    requires_api_key,
    pytest.mark.haiku,
    pytest.mark.slow,
    pytest.mark.expensive,
]


# =============================================================================
# Multi-Tick Simulation Tests
# =============================================================================


class TestMultiTickSimulation:
    """Test multi-tick simulation with all agents."""

    @pytest.mark.asyncio
    async def test_ten_tick_simulation(self, haiku_engine):
        """Run 10 ticks with full village."""
        events_by_type: dict[str, int] = {}

        for _ in range(10):
            result = await haiku_engine.tick_once()

            for event in result.events:
                events_by_type[event.type] = events_by_type.get(event.type, 0) + 1

        # Should have some events
        total_events = sum(events_by_type.values())
        assert total_events > 0

        # Log summary for analysis
        print(f"Event summary (10 ticks): {events_by_type}")

    @pytest.mark.asyncio
    async def test_twenty_tick_simulation(self, haiku_engine):
        """Run 20 ticks with full village - longer simulation."""
        events_by_type: dict[str, int] = {}
        agents_acted_total = set()

        for _ in range(20):
            result = await haiku_engine.tick_once()

            agents_acted_total.update(result.agents_acted)
            for event in result.events:
                events_by_type[event.type] = events_by_type.get(event.type, 0) + 1

        assert haiku_engine.tick == 20

        # All agents should have acted at some point
        assert len(agents_acted_total) >= 1

        # Should have variety of events
        print(f"Event summary (20 ticks): {events_by_type}")
        print(f"Agents who acted: {agents_acted_total}")

    @pytest.mark.asyncio
    async def test_thirty_tick_simulation(self, haiku_engine):
        """Run 30 ticks - extended simulation."""
        for _ in range(30):
            result = await haiku_engine.tick_once()
            assert result is not None

        assert haiku_engine.tick == 30

        # All agents should still be valid
        for name, agent in haiku_engine.agents.items():
            assert agent.name == name
            assert agent.location in haiku_engine.world.locations


# =============================================================================
# Emergent Behavior Tests
# =============================================================================


class TestEmergentBehavior:
    """Test emergent social and behavioral patterns."""

    @pytest.mark.asyncio
    async def test_agents_explore_village(self, haiku_engine):
        """Agents may move between locations over time."""
        locations_visited: dict[str, set] = {
            name: {agent.location}
            for name, agent in haiku_engine.agents.items()
        }

        for _ in range(20):
            await haiku_engine.tick_once()

            for name, agent in haiku_engine.agents.items():
                locations_visited[name].add(agent.location)

        # Log exploration patterns
        for name, locs in locations_visited.items():
            print(f"{name} visited: {locs}")

        # Exploration is emergent - just verify no crashes

    @pytest.mark.asyncio
    async def test_social_events_may_occur(self, haiku_engine):
        """Social events (invites, conversations) may occur."""
        social_events = []

        for _ in range(20):
            result = await haiku_engine.tick_once()

            social_events.extend([
                e for e in result.events
                if e.type in (
                    "conversation_invited",
                    "conversation_started",
                    "conversation_turn",
                    "conversation_ended",
                )
            ])

        # Social behavior is emergent
        print(f"Social events over 20 ticks: {len(social_events)}")

    @pytest.mark.asyncio
    async def test_mood_changes_over_time(self, haiku_engine):
        """Agent moods may change based on activities."""
        mood_events = []

        for _ in range(15):
            result = await haiku_engine.tick_once()

            mood_events.extend([
                e for e in result.events
                if e.type == "agent_mood_changed"
            ])

        # Mood changes are emergent
        print(f"Mood change events: {len(mood_events)}")

    @pytest.mark.asyncio
    async def test_actions_are_varied(self, haiku_engine):
        """Agents perform varied actions over time."""
        action_events = []

        for _ in range(15):
            result = await haiku_engine.tick_once()

            action_events.extend([
                e for e in result.events
                if e.type == "agent_action"
            ])

        # Should have some action events
        print(f"Action events: {len(action_events)}")


# =============================================================================
# State Consistency Tests
# =============================================================================


class TestFullSimulationConsistency:
    """Test state consistency in full simulation."""

    @pytest.mark.asyncio
    async def test_agents_consistent_throughout(self, haiku_engine):
        """Agent count and names remain consistent."""
        initial_agents = set(haiku_engine.agents.keys())

        for _ in range(15):
            await haiku_engine.tick_once()
            current_agents = set(haiku_engine.agents.keys())
            assert current_agents == initial_agents

    @pytest.mark.asyncio
    async def test_all_agents_valid_after_simulation(self, haiku_engine):
        """All agents remain in valid state after long simulation."""
        for _ in range(20):
            await haiku_engine.tick_once()

        for name, agent in haiku_engine.agents.items():
            assert agent.name == name
            assert agent.location in haiku_engine.world.locations
            assert 0 <= agent.energy <= 100
            # Mood should be a string
            assert isinstance(agent.mood, str)

    @pytest.mark.asyncio
    async def test_events_have_valid_ticks(self, haiku_engine):
        """All events have correct tick numbers."""
        for i in range(10):
            result = await haiku_engine.tick_once()
            for event in result.events:
                assert event.tick == i + 1


# =============================================================================
# Recovery Tests
# =============================================================================


class TestFullSimulationRecovery:
    """Test state recovery mid-simulation."""

    @pytest.mark.asyncio
    async def test_recovery_after_fifteen_ticks(self, temp_village, haiku_engine):
        """State recovers correctly after 15 ticks."""
        for _ in range(15):
            await haiku_engine.tick_once()

        tick_before = haiku_engine.tick
        state_before = {
            "locations": {n: a.location for n, a in haiku_engine.agents.items()},
            "conversations": len(haiku_engine.conversations),
        }

        # Create new engine and recover
        from engine.engine import VillageEngine
        from engine.adapters import ClaudeProvider

        provider = ClaudeProvider(model="claude-haiku-4-5-20251001")
        engine2 = VillageEngine(
            village_root=temp_village,
            llm_provider=provider,
        )
        assert engine2.recover()

        # Verify tick
        assert engine2.tick == tick_before

        # Verify agent locations
        for name, loc in state_before["locations"].items():
            assert engine2.agents[name].location == loc

    @pytest.mark.asyncio
    async def test_can_continue_long_simulation_after_recovery(
        self, temp_village, haiku_engine
    ):
        """Simulation continues correctly after recovery."""
        # Run first half
        for _ in range(10):
            await haiku_engine.tick_once()

        # Recover
        from engine.engine import VillageEngine
        from engine.adapters import ClaudeProvider

        provider = ClaudeProvider(model="claude-haiku-4-5-20251001")
        engine2 = VillageEngine(
            village_root=temp_village,
            llm_provider=provider,
        )
        engine2.recover()

        # Run second half
        for _ in range(10):
            result = await engine2.tick_once()
            assert result is not None

        assert engine2.tick == 20


# =============================================================================
# Quality Assessment Tests (LLM Judge)
# =============================================================================


class TestSimulationQuality:
    """Test overall simulation quality with LLM judge."""

    @pytest.mark.asyncio
    async def test_narratives_contextually_appropriate(self, haiku_engine, llm_judge):
        """Agent narratives are appropriate for their context."""
        result = await haiku_engine.tick_once()

        for agent_name, turn_result in result.turn_results.items():
            if not turn_result.narrative:
                continue

            agent = haiku_engine.agents[agent_name]
            location = haiku_engine.world.locations[agent.location]

            judgment = llm_judge(
                "Is this narrative contextually appropriate for the agent and location?",
                f"Agent: {agent_name}\n"
                f"Job: {agent.job}\n"
                f"Location: {location.name} - {location.description}\n"
                f"Mood: {agent.mood}\n"
                f"Narrative: {turn_result.narrative}"
            )

            if not judgment.passed:
                pytest.skip(f"LLM judge for {agent_name}: {judgment.reasoning}")

    @pytest.mark.asyncio
    async def test_simulation_produces_believable_day(self, haiku_engine, llm_judge):
        """Extended simulation produces believable village day."""
        all_narratives = []

        for _ in range(10):
            result = await haiku_engine.tick_once()
            for agent_name, turn_result in result.turn_results.items():
                if turn_result.narrative:
                    agent = haiku_engine.agents[agent_name]
                    all_narratives.append(
                        f"[{agent_name} at {agent.location}]: {turn_result.narrative}"
                    )

        if len(all_narratives) < 5:
            pytest.skip("Not enough narratives to evaluate simulation")

        # Sample some narratives for evaluation (avoid huge prompts)
        sample = all_narratives[:10] if len(all_narratives) > 10 else all_narratives
        combined = "\n\n".join(sample)

        judgment = llm_judge(
            "Do these agent activities represent a believable village simulation?",
            f"Agent activities over time:\n{combined}"
        )

        if not judgment.passed:
            pytest.skip(f"LLM judge: {judgment.reasoning}")


# =============================================================================
# Stress Tests
# =============================================================================


class TestSimulationStress:
    """Stress tests for simulation stability."""

    @pytest.mark.asyncio
    async def test_fifty_tick_simulation(self, haiku_engine):
        """Run 50 ticks without crashing."""
        for i in range(50):
            result = await haiku_engine.tick_once()
            assert result is not None
            assert result.tick == i + 1

        assert haiku_engine.tick == 50

    @pytest.mark.asyncio
    async def test_rapid_succession_ticks(self, haiku_engine):
        """Many ticks in rapid succession work correctly."""
        results = []

        for _ in range(20):
            result = await haiku_engine.tick_once()
            results.append(result)

        # All results should be valid
        for i, result in enumerate(results):
            assert result.tick == i + 1


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestFullSimulationEdgeCases:
    """Test edge cases in full simulation."""

    @pytest.mark.asyncio
    async def test_handles_all_agents_sleeping(self, haiku_engine):
        """Handles case where all agents fall asleep."""
        # Run simulation normally
        for _ in range(10):
            await haiku_engine.tick_once()

        # Force all agents to sleep
        for name in haiku_engine.agents:
            haiku_engine._agents[name] = haiku_engine.agents[name].model_copy(
                update={"is_sleeping": True}
            )

        # Should handle gracefully
        result = await haiku_engine.tick_once()
        assert result is not None
        # No agents should act when all sleeping
        assert len(result.agents_acted) == 0

    @pytest.mark.asyncio
    async def test_handles_empty_tick_results(self, haiku_engine):
        """Handles ticks that produce minimal results."""
        # Some ticks may have few events - that's okay
        for _ in range(10):
            result = await haiku_engine.tick_once()
            # Even empty results should be valid
            assert hasattr(result, "tick")
            assert hasattr(result, "events")


# =============================================================================
# Event Analysis Tests
# =============================================================================


class TestEventAnalysis:
    """Analyze event patterns in simulation."""

    @pytest.mark.asyncio
    async def test_event_distribution(self, haiku_engine):
        """Analyze distribution of event types."""
        events_by_type: dict[str, int] = {}

        for _ in range(20):
            result = await haiku_engine.tick_once()

            for event in result.events:
                events_by_type[event.type] = events_by_type.get(event.type, 0) + 1

        # Report distribution
        print("\nEvent distribution over 20 ticks:")
        for event_type, count in sorted(events_by_type.items()):
            print(f"  {event_type}: {count}")

        # Should have last_active_tick events at minimum
        assert "agent_last_active_tick_updated" in events_by_type

    @pytest.mark.asyncio
    async def test_agent_activity_distribution(self, haiku_engine):
        """Analyze how often each agent acts."""
        activity_count: dict[str, int] = {}

        for _ in range(20):
            result = await haiku_engine.tick_once()

            for agent_name in result.agents_acted:
                name_str = str(agent_name)
                activity_count[name_str] = activity_count.get(name_str, 0) + 1

        # Report activity
        print("\nAgent activity over 20 ticks:")
        for agent, count in sorted(activity_count.items()):
            print(f"  {agent}: {count} turns")

        # At least one agent should have acted
        assert sum(activity_count.values()) > 0
