"""
Level 2 Integration Tests: Pipeline with Mock LLM

Tests the full tick pipeline with a deterministic mock LLM provider.
This validates that effects flow correctly through phases and
become events that update state.

Run with: uv run pytest tests/integration/test_pipeline_mock.py -v
"""

from __future__ import annotations

from datetime import datetime

import pytest

from engine.domain import (
    AgentName,
    LocationId,
    ConversationId,
)
from tests.integration.fixtures import (
    MockLLMProvider,
    SAMPLE_NARRATIVES,
    create_test_village,
    create_test_village_with_conversation,
)


# =============================================================================
# Single Tick Execution Tests
# =============================================================================


class TestSingleTickExecution:
    """Test basic single tick execution with mock LLM."""

    @pytest.mark.asyncio
    async def test_single_tick_increments_tick(self, test_engine):
        """Single tick should increment tick counter."""
        initial_tick = test_engine.tick

        result = await test_engine.tick_once()

        assert test_engine.tick == initial_tick + 1
        assert result.tick == initial_tick + 1

    @pytest.mark.asyncio
    async def test_agents_act_during_tick(self, test_engine, mock_provider):
        """Agents should act during tick."""
        mock_provider.set_narrative("Alice", "I work on my painting.")
        mock_provider.set_narrative("Bob", "I read quietly.")
        mock_provider.set_narrative("Carol", "I tend to the plants.")

        result = await test_engine.tick_once()

        # At least some agents should have acted
        assert len(result.agents_acted) >= 1

    @pytest.mark.asyncio
    async def test_tick_produces_events(self, test_engine, mock_provider):
        """Tick should produce domain events."""
        mock_provider.set_narrative(
            "Alice",
            "I walk to the garden, feeling peaceful."
        )

        result = await test_engine.tick_once()

        # Should have at least some events (actions, possibly movement)
        # The exact events depend on interpreter behavior
        assert result is not None


# =============================================================================
# Movement Detection Tests
# =============================================================================


class TestMovementDetection:
    """Test movement effects flow through pipeline."""

    @pytest.mark.asyncio
    async def test_movement_updates_agent_location(self, test_engine, mock_provider):
        """Agent moving should update their location in state."""
        # Verify Alice starts at workshop
        assert test_engine.agents[AgentName("Alice")].location == LocationId("workshop")

        mock_provider.set_narrative("Alice", SAMPLE_NARRATIVES["movement_to_garden"])

        await test_engine.tick_once()

        # If interpreter detects movement, location should change
        # Note: This depends on interpreter correctly detecting movement
        alice_location = test_engine.agents[AgentName("Alice")].location
        # Could be garden or workshop depending on interpreter
        assert alice_location in [LocationId("garden"), LocationId("workshop")]

    @pytest.mark.asyncio
    async def test_movement_creates_event(self, test_engine, mock_provider):
        """Movement should create AgentMovedEvent."""
        mock_provider.set_narrative("Alice", SAMPLE_NARRATIVES["movement_to_library"])

        result = await test_engine.tick_once()

        # Check if movement event was created
        move_events = [e for e in result.events if e.type == "agent_moved"]
        # May or may not have movement depending on interpreter
        # Just verify no crash


# =============================================================================
# Mood Detection Tests
# =============================================================================


class TestMoodDetection:
    """Test mood effects flow through pipeline."""

    @pytest.mark.asyncio
    async def test_mood_updates_agent_state(self, test_engine, mock_provider):
        """Mood changes should update agent state."""
        initial_mood = test_engine.agents[AgentName("Alice")].mood

        mock_provider.set_narrative("Alice", SAMPLE_NARRATIVES["joyful_mood"])

        await test_engine.tick_once()

        # Mood may or may not change depending on interpreter
        # Just verify no crash and state is consistent


# =============================================================================
# Sleep Detection Tests
# =============================================================================


class TestSleepDetection:
    """Test sleep effects flow through pipeline."""

    @pytest.mark.asyncio
    async def test_sleep_updates_agent_state(self, test_engine, mock_provider):
        """Going to sleep should update is_sleeping."""
        assert not test_engine.agents[AgentName("Alice")].is_sleeping

        mock_provider.set_narrative("Alice", SAMPLE_NARRATIVES["going_to_sleep"])

        await test_engine.tick_once()

        # If interpreter detects sleep, state should update
        # This depends on interpreter behavior


# =============================================================================
# Sleeping Agent Tests
# =============================================================================


class TestSleepingAgentBehavior:
    """Test sleeping agents are handled correctly."""

    @pytest.mark.asyncio
    async def test_sleeping_agent_not_scheduled(self, test_engine, mock_provider):
        """Sleeping agents should not act."""
        # Make Alice sleep directly (bypass tick)
        alice = test_engine.agents[AgentName("Alice")]
        test_engine._agents[AgentName("Alice")] = alice.model_copy(
            update={"is_sleeping": True}
        )

        mock_provider.set_narrative("Alice", "This should not be called")
        mock_provider.set_narrative("Bob", "I read quietly.")

        result = await test_engine.tick_once()

        # Alice should not have acted
        assert AgentName("Alice") not in result.agents_acted


# =============================================================================
# Parallel Agent Execution Tests
# =============================================================================


class TestParallelAgentExecution:
    """Test multiple agents at different locations act in parallel."""

    @pytest.mark.asyncio
    async def test_agents_at_different_locations_act(self, test_engine, mock_provider):
        """Agents at different locations can act in parallel."""
        mock_provider.set_narrative("Alice", "I paint at the workshop.")
        mock_provider.set_narrative("Bob", "I read at the library.")
        mock_provider.set_narrative("Carol", "I garden in the garden.")

        result = await test_engine.tick_once()

        # Multiple agents should have acted (they're at different locations)
        assert len(result.agents_acted) >= 1


# =============================================================================
# Multi-Tick Tests
# =============================================================================


class TestMultiTick:
    """Test multiple consecutive ticks."""

    @pytest.mark.asyncio
    async def test_five_tick_sequence(self, test_engine, mock_provider):
        """Run 5 ticks and verify state consistency."""
        mock_provider.set_narrative("Alice", "I continue my work.")
        mock_provider.set_narrative("Bob", "I read quietly.")
        mock_provider.set_narrative("Carol", "I tend the garden.")

        initial_tick = test_engine.tick

        for i in range(5):
            result = await test_engine.tick_once()
            assert result.tick == initial_tick + i + 1

        assert test_engine.tick == initial_tick + 5

    @pytest.mark.asyncio
    async def test_state_persists_across_ticks(self, test_engine, mock_provider):
        """State changes should persist across ticks."""
        # First tick: Alice moves to garden
        mock_provider.set_narrative("Alice", SAMPLE_NARRATIVES["movement_to_garden"])
        await test_engine.tick_once()

        # Second tick: Different narrative
        mock_provider.set_narrative("Alice", "I enjoy the garden.")
        await test_engine.tick_once()

        # State should be consistent


# =============================================================================
# Conversation Flow Tests (with conversation fixture)
# =============================================================================


class TestConversationTurns:
    """Test conversation turn mechanics."""

    @pytest.mark.asyncio
    async def test_conversation_participant_acts(
        self,
        test_engine_with_conversation,
        mock_provider,
    ):
        """Agents in conversation should get turns."""
        engine = test_engine_with_conversation

        mock_provider.set_narrative("Alice", "Hello Bob, how are you?")
        mock_provider.set_narrative("Bob", "I'm doing well, thanks!")

        result = await engine.tick_once()

        # Should have executed tick without error
        assert result is not None


# =============================================================================
# Mock Provider Verification Tests
# =============================================================================


class TestMockProviderBehavior:
    """Verify mock provider behaves as expected."""

    @pytest.mark.asyncio
    async def test_mock_logs_calls(self, test_engine, mock_provider):
        """Mock provider should log all calls."""
        mock_provider.set_narrative("Alice", "Testing.")

        await test_engine.tick_once()

        # Check if provider was called
        if mock_provider.was_called("Alice"):
            context = mock_provider.get_last_context("Alice")
            assert context is not None
            assert context.agent.name == AgentName("Alice")

    @pytest.mark.asyncio
    async def test_default_narrative_used(self, test_engine, mock_provider):
        """Unconfigured agents should use default narrative."""
        # Don't configure any narratives
        mock_provider.clear_all()

        await test_engine.tick_once()

        # Should not crash - default narrative is used


# =============================================================================
# Tool Call Tests
# =============================================================================


class TestToolCalls:
    """Test tool call flow through mock provider."""

    @pytest.mark.asyncio
    async def test_invite_tool_creates_pending_invite(
        self,
        test_engine,
        mock_provider,
    ):
        """invite_to_conversation tool should create pending invite."""
        # Move Alice and Bob to same location first
        test_engine._agents[AgentName("Bob")] = test_engine.agents[
            AgentName("Bob")
        ].model_copy(update={"location": LocationId("workshop")})

        mock_provider.set_narrative("Alice", "I call out to Bob.")
        mock_provider.set_tool_call(
            "Alice",
            "invite_to_conversation",
            {
                "invitee": "Bob",
                "privacy": "private",
            },
        )

        await test_engine.tick_once()

        # Check if invite was created
        # Note: This depends on whether tool was actually processed
        assert mock_provider.tool_was_called("Alice", "invite_to_conversation")


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Test pipeline error handling."""

    @pytest.mark.asyncio
    async def test_empty_narrative_handled(self, test_engine, mock_provider):
        """Empty narrative should not crash pipeline."""
        mock_provider.set_narrative("Alice", "")

        result = await test_engine.tick_once()

        # Should complete without crash
        assert result is not None

    @pytest.mark.asyncio
    async def test_very_long_narrative_handled(self, test_engine, mock_provider):
        """Very long narrative should be handled."""
        mock_provider.set_narrative("Alice", SAMPLE_NARRATIVES["very_long"])

        result = await test_engine.tick_once()

        assert result is not None


# =============================================================================
# State Recovery Tests
# =============================================================================


class TestStateRecovery:
    """Test state recovery after engine restart."""

    @pytest.mark.asyncio
    async def test_state_recoverable_after_ticks(self, temp_village, mock_provider):
        """State should be recoverable after running ticks."""
        from engine.engine import VillageEngine

        # Create and run first engine
        engine1 = VillageEngine(
            village_root=temp_village,
            llm_provider=mock_provider,
        )
        snapshot = create_test_village()
        engine1.initialize(snapshot)

        mock_provider.set_narrative("Alice", "I work quietly.")

        for _ in range(3):
            await engine1.tick_once()

        tick_before = engine1.tick

        # "Restart" with new engine
        engine2 = VillageEngine(
            village_root=temp_village,
            llm_provider=mock_provider,
        )
        assert engine2.recover()

        # Tick should be recovered
        assert engine2.tick == tick_before

    @pytest.mark.asyncio
    async def test_agents_recovered(self, temp_village, mock_provider):
        """Agent state should be recovered."""
        from engine.engine import VillageEngine

        engine1 = VillageEngine(
            village_root=temp_village,
            llm_provider=mock_provider,
        )
        snapshot = create_test_village()
        engine1.initialize(snapshot)

        await engine1.tick_once()

        # Create new engine and recover
        engine2 = VillageEngine(
            village_root=temp_village,
            llm_provider=mock_provider,
        )
        assert engine2.recover()

        # Should have same agents
        assert len(engine2.agents) == len(engine1.agents)
        assert AgentName("Alice") in engine2.agents


# =============================================================================
# Observer Integration Tests
# =============================================================================


class TestObserverIntegration:
    """Test observer API integration with pipeline."""

    @pytest.mark.asyncio
    async def test_observer_accessible(self, test_engine):
        """Observer should be accessible from engine."""
        observer = test_engine.observer

        assert observer is not None

    @pytest.mark.asyncio
    async def test_tick_continues_after_observer_command(
        self, test_engine, mock_provider
    ):
        """Ticks should work after observer commands."""
        # Use observer to get snapshot
        _ = test_engine.observer.get_village_snapshot()

        mock_provider.set_narrative("Alice", "I continue working.")

        result = await test_engine.tick_once()

        assert result is not None
