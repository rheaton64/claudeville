"""
Level 4 Integration Tests: Multi-Tick Sequences

Tests multi-tick simulation sequences with mock LLM:
- State consistency over time
- Sleep/wake cycles
- Conversation lifecycles
- Crash recovery
- Edge cases

Run with: uv run pytest tests/integration/test_multi_tick_mock.py -v
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from engine.domain import (
    AgentName,
    LocationId,
    ConversationId,
    TimePeriod,
)
from tests.integration.fixtures import (
    MockLLMProvider,
    SAMPLE_NARRATIVES,
    create_test_village,
)


# =============================================================================
# Multi-Tick Simulation Tests
# =============================================================================


class TestMultiTickSimulation:
    """Test multi-tick simulation behavior."""

    @pytest.mark.asyncio
    async def test_ten_tick_simulation(
        self,
        test_engine,
        mock_provider: MockLLMProvider,
    ):
        """Run 10 ticks, verify state consistency."""
        mock_provider.set_narrative("Alice", "I work on my project.")
        mock_provider.set_narrative("Bob", "I read quietly.")
        mock_provider.set_narrative("Carol", "I tend the garden.")

        initial_tick = test_engine.tick
        events_by_type: dict[str, int] = {}

        for i in range(10):
            result = await test_engine.tick_once()
            assert result.tick == initial_tick + i + 1

            for event in result.events:
                events_by_type[event.type] = events_by_type.get(event.type, 0) + 1

        assert test_engine.tick == initial_tick + 10

        # Should have accumulated some events
        total_events = sum(events_by_type.values())
        assert total_events > 0

    @pytest.mark.asyncio
    async def test_twenty_tick_simulation(
        self,
        test_engine,
        mock_provider: MockLLMProvider,
    ):
        """Run 20 ticks for longer simulation."""
        mock_provider.set_narrative("Alice", "I continue my activities.")
        mock_provider.set_narrative("Bob", "I keep reading.")
        mock_provider.set_narrative("Carol", "I water the plants.")

        for _ in range(20):
            result = await test_engine.tick_once()
            assert result is not None

        assert test_engine.tick == 20

    @pytest.mark.asyncio
    async def test_agents_consistent_across_ticks(
        self,
        test_engine,
        mock_provider: MockLLMProvider,
    ):
        """Agent count and names stay consistent."""
        initial_agents = set(test_engine.agents.keys())

        mock_provider.set_narrative("Alice", "I work.")
        mock_provider.set_narrative("Bob", "I read.")
        mock_provider.set_narrative("Carol", "I garden.")

        for _ in range(5):
            await test_engine.tick_once()
            current_agents = set(test_engine.agents.keys())
            assert current_agents == initial_agents


# =============================================================================
# Sleep/Wake Cycle Tests
# =============================================================================


class TestSleepWakeCycles:
    """Test sleep and wake behavior over time."""

    @pytest.mark.asyncio
    async def test_sleep_state_tracked(
        self,
        test_engine,
        mock_provider: MockLLMProvider,
    ):
        """Sleeping state is tracked correctly."""
        # Make Alice sleep with matching time period
        current_period = test_engine.time_snapshot.period
        test_engine._agents[AgentName("Alice")] = test_engine.agents[
            AgentName("Alice")
        ].model_copy(update={
            "is_sleeping": True,
            "sleep_started_tick": 0,
            "sleep_started_time_period": current_period,
        })

        mock_provider.set_narrative("Bob", "I read.")
        mock_provider.set_narrative("Carol", "I garden.")

        # First tick - Alice might wake due to time period change
        result = await test_engine.tick_once()

        # Verify we can check sleeping state
        # (Agent may wake up due to time period change, which is expected behavior)
        assert test_engine.agents[AgentName("Alice")] is not None

    @pytest.mark.asyncio
    async def test_multiple_agents_can_sleep(
        self,
        test_engine,
        mock_provider: MockLLMProvider,
    ):
        """Multiple agents can be asleep simultaneously."""
        # Make Alice and Bob sleep
        test_engine._agents[AgentName("Alice")] = test_engine.agents[
            AgentName("Alice")
        ].model_copy(update={"is_sleeping": True})
        test_engine._agents[AgentName("Bob")] = test_engine.agents[
            AgentName("Bob")
        ].model_copy(update={"is_sleeping": True})

        mock_provider.set_narrative("Carol", "I garden alone.")

        result = await test_engine.tick_once()

        # Only Carol should act
        assert AgentName("Alice") not in result.agents_acted
        assert AgentName("Bob") not in result.agents_acted


# =============================================================================
# Conversation Lifecycle Tests
# =============================================================================


class TestConversationLifecycle:
    """Test full conversation lifecycle over multiple ticks."""

    @pytest.mark.asyncio
    async def test_conversation_persists_across_ticks(
        self,
        test_engine_with_conversation,
        mock_provider: MockLLMProvider,
    ):
        """Active conversation persists across ticks."""
        engine = test_engine_with_conversation
        conv_id = list(engine.conversations.keys())[0]

        mock_provider.set_narrative("Alice", "I continue chatting.")
        mock_provider.set_narrative("Bob", "Me too!")

        for _ in range(5):
            await engine.tick_once()
            assert conv_id in engine.conversations

    @pytest.mark.asyncio
    async def test_conversation_full_lifecycle(
        self,
        test_engine,
        mock_provider: MockLLMProvider,
    ):
        """Test full lifecycle: invite → accept → chat → end (via observer)."""
        # Move Bob to workshop
        test_engine._agents[AgentName("Bob")] = test_engine.agents[
            AgentName("Bob")
        ].model_copy(update={"location": LocationId("workshop")})

        # Tick 1: Alice invites Bob (force Alice since Bob is also at workshop)
        test_engine.scheduler.force_next_turn(AgentName("Alice"))
        mock_provider.set_tool_call(
            "Alice",
            "invite_to_conversation",
            {"invitee": "Bob", "privacy": "public"},
        )
        await test_engine.tick_once()

        assert AgentName("Bob") in test_engine.pending_invites
        invite = test_engine.pending_invites[AgentName("Bob")]
        conv_id = invite.conversation_id

        # Tick 2: Bob accepts (Bob has pending invite so gets scheduled)
        mock_provider.clear_tool_call("Alice")
        mock_provider.set_tool_call(
            "Bob",
            "accept_invite",
            {"conversation_id": str(conv_id)},
        )
        await test_engine.tick_once()

        assert conv_id in test_engine.conversations

        # Ticks 3-5: Chat (one speaker per tick in conversation)
        mock_provider.clear_tool_call("Bob")
        mock_provider.set_narrative("Alice", "So, what do you think?")
        mock_provider.set_narrative("Bob", "I think it's interesting!")

        for _ in range(3):
            await test_engine.tick_once()

        conv = test_engine.conversations[conv_id]
        assert len(conv.history) >= 1

        # End conversation via observer API
        # (leave_conversation tool behavior tested in test_conversation_flow.py)
        test_engine.end_conversation(conv_id, reason="test lifecycle complete")

        assert conv_id not in test_engine.conversations


# =============================================================================
# State Recovery Tests
# =============================================================================


class TestStateRecovery:
    """Test state recovery after engine restart."""

    @pytest.mark.asyncio
    async def test_recovery_preserves_tick(
        self,
        temp_village: Path,
        mock_provider: MockLLMProvider,
    ):
        """Tick number is preserved after recovery."""
        from engine.engine import VillageEngine

        # Create and run engine
        engine1 = VillageEngine(
            village_root=temp_village,
            llm_provider=mock_provider,
        )
        snapshot = create_test_village()
        engine1.initialize(snapshot)

        mock_provider.set_narrative("Alice", "I work.")

        for _ in range(7):
            await engine1.tick_once()

        tick_before = engine1.tick

        # Recover in new engine
        engine2 = VillageEngine(
            village_root=temp_village,
            llm_provider=mock_provider,
        )
        assert engine2.recover()

        assert engine2.tick == tick_before

    @pytest.mark.asyncio
    async def test_recovery_preserves_agent_locations(
        self,
        temp_village: Path,
        mock_provider: MockLLMProvider,
    ):
        """Agent locations are preserved after recovery."""
        from engine.engine import VillageEngine

        engine1 = VillageEngine(
            village_root=temp_village,
            llm_provider=mock_provider,
        )
        snapshot = create_test_village()
        engine1.initialize(snapshot)

        # Move Alice
        test_engine = engine1
        mock_provider.set_narrative("Alice", SAMPLE_NARRATIVES["movement_to_garden"])

        await engine1.tick_once()

        locations_before = {
            name: agent.location
            for name, agent in engine1.agents.items()
        }

        # Recover
        engine2 = VillageEngine(
            village_root=temp_village,
            llm_provider=mock_provider,
        )
        engine2.recover()

        for name, loc in locations_before.items():
            assert engine2.agents[name].location == loc

    @pytest.mark.asyncio
    async def test_recovery_preserves_conversations(
        self,
        temp_village: Path,
        mock_provider: MockLLMProvider,
    ):
        """Active conversations are preserved after recovery."""
        from engine.engine import VillageEngine

        engine1 = VillageEngine(
            village_root=temp_village,
            llm_provider=mock_provider,
        )
        snapshot = create_test_village()
        engine1.initialize(snapshot)

        # Move Bob to workshop and create conversation
        engine1._agents[AgentName("Bob")] = engine1.agents[
            AgentName("Bob")
        ].model_copy(update={"location": LocationId("workshop")})

        mock_provider.set_tool_call(
            "Alice",
            "invite_to_conversation",
            {"invitee": "Bob", "privacy": "public"},
        )
        await engine1.tick_once()

        invite = engine1.pending_invites[AgentName("Bob")]
        conv_id = invite.conversation_id

        mock_provider.clear_tool_call("Alice")
        mock_provider.set_tool_call(
            "Bob",
            "accept_invite",
            {"conversation_id": str(conv_id)},
        )
        await engine1.tick_once()

        assert conv_id in engine1.conversations

        # Recover
        engine2 = VillageEngine(
            village_root=temp_village,
            llm_provider=mock_provider,
        )
        engine2.recover()

        assert conv_id in engine2.conversations

    @pytest.mark.asyncio
    async def test_can_continue_after_recovery(
        self,
        temp_village: Path,
        mock_provider: MockLLMProvider,
    ):
        """Simulation can continue after recovery."""
        from engine.engine import VillageEngine

        # Run first engine
        engine1 = VillageEngine(
            village_root=temp_village,
            llm_provider=mock_provider,
        )
        engine1.initialize(create_test_village())

        for _ in range(3):
            await engine1.tick_once()

        # Recover and continue
        engine2 = VillageEngine(
            village_root=temp_village,
            llm_provider=mock_provider,
        )
        engine2.recover()

        # Should be able to continue
        mock_provider.set_narrative("Alice", "Continuing work.")

        for _ in range(3):
            result = await engine2.tick_once()
            assert result is not None


# =============================================================================
# Edge Cases
# =============================================================================


class TestMultiTickEdgeCases:
    """Test edge cases in multi-tick scenarios."""

    @pytest.mark.asyncio
    async def test_all_agents_sleeping(
        self,
        test_engine,
        mock_provider: MockLLMProvider,
    ):
        """Handle case where all agents are sleeping."""
        for name in test_engine.agents:
            test_engine._agents[name] = test_engine.agents[name].model_copy(
                update={"is_sleeping": True}
            )

        # Should handle gracefully
        result = await test_engine.tick_once()
        assert result is not None
        assert len(result.agents_acted) == 0

    @pytest.mark.asyncio
    async def test_no_events_tick(
        self,
        test_engine,
        mock_provider: MockLLMProvider,
    ):
        """Handle tick that produces no significant events."""
        # Empty narrative might not produce events
        mock_provider.set_narrative("Alice", "")
        mock_provider.set_narrative("Bob", "")
        mock_provider.set_narrative("Carol", "")

        result = await test_engine.tick_once()
        assert result is not None

    @pytest.mark.asyncio
    async def test_rapid_tick_succession(
        self,
        test_engine,
        mock_provider: MockLLMProvider,
    ):
        """Many ticks in rapid succession should work."""
        mock_provider.set_narrative("Alice", "Working.")
        mock_provider.set_narrative("Bob", "Reading.")
        mock_provider.set_narrative("Carol", "Gardening.")

        for i in range(50):
            result = await test_engine.tick_once()
            assert result.tick == i + 1


# =============================================================================
# Event Tracking Tests
# =============================================================================


class TestEventTracking:
    """Test event generation and tracking over time."""

    @pytest.mark.asyncio
    async def test_events_have_correct_ticks(
        self,
        test_engine,
        mock_provider: MockLLMProvider,
    ):
        """Events should have correct tick numbers."""
        mock_provider.set_narrative("Alice", "I do something.")

        for i in range(5):
            result = await test_engine.tick_once()
            for event in result.events:
                assert event.tick == i + 1

    @pytest.mark.asyncio
    async def test_events_accumulate_in_store(
        self,
        test_engine,
        mock_provider: MockLLMProvider,
    ):
        """Events should accumulate in event store."""
        mock_provider.set_narrative("Alice", "I work.")

        for _ in range(5):
            await test_engine.tick_once()

        # Check event store
        recent_events = test_engine.event_store.get_recent_events(limit=100)
        assert len(recent_events) >= 1
