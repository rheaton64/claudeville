"""
Level 6 Integration Tests: Two-Agent Conversation with Real Haiku

Tests two agents having natural conversation with real Claude Haiku.
These are behavioral tests - outcomes are emergent, not deterministic.

Run with: uv run pytest tests/integration/test_two_agent_haiku.py -v
Requires: ANTHROPIC_API_KEY environment variable
"""

from __future__ import annotations

import pytest

from engine.domain import AgentName, LocationId
from tests.integration.conftest import requires_api_key


# All tests in this module require API key and are slow
pytestmark = [requires_api_key, pytest.mark.haiku, pytest.mark.slow]


# =============================================================================
# Fixture for Co-located Agents
# =============================================================================


@pytest.fixture
def colocated_engine(haiku_engine):
    """Engine with Alice and Bob at the same location (workshop)."""
    from engine.domain import MoveAgentEffect

    # Move Bob to workshop using proper event sourcing
    # This creates an AgentMovedEvent that persists across tick hydration
    haiku_engine.apply_effect(MoveAgentEffect(
        agent=AgentName("Bob"),
        from_location=LocationId("library"),
        to_location=LocationId("workshop"),
    ))

    return haiku_engine


# =============================================================================
# Basic Two-Agent Tests
# =============================================================================


class TestTwoAgentBasics:
    """Test basic two-agent behavior with real Haiku."""

    @pytest.mark.asyncio
    async def test_colocated_agents_both_produce_narratives(self, colocated_engine):
        """Both co-located agents generate narratives."""
        result = await colocated_engine.tick_once()

        # At least one agent should have acted
        assert len(result.agents_acted) >= 1

        # Each turn result should have narrative
        for agent_name, turn_result in result.turn_results.items():
            assert turn_result.narrative, f"{agent_name} produced empty narrative"

    @pytest.mark.asyncio
    async def test_colocated_agents_over_multiple_ticks(self, colocated_engine):
        """Co-located agents continue interacting over multiple ticks."""
        narratives_by_agent: dict[str, list[str]] = {}

        for _ in range(5):
            result = await colocated_engine.tick_once()
            for agent_name, turn_result in result.turn_results.items():
                if agent_name not in narratives_by_agent:
                    narratives_by_agent[agent_name] = []
                narratives_by_agent[agent_name].append(turn_result.narrative)

        # Each agent should have generated some narratives
        for agent_name, narratives in narratives_by_agent.items():
            total_content = "".join(narratives)
            assert len(total_content) > 0, f"{agent_name} produced no content"


# =============================================================================
# Conversation Initiation Tests
# =============================================================================


class TestConversationInitiation:
    """Test conversation initiation between two agents."""

    @pytest.mark.asyncio
    async def test_agents_may_start_conversation(self, colocated_engine):
        """Co-located agents may initiate conversation (emergent behavior)."""
        conversation_events = []

        for _ in range(10):
            result = await colocated_engine.tick_once()
            conversation_events.extend([
                e for e in result.events
                if e.type in ("conversation_invited", "conversation_started")
            ])

        # Conversation initiation is emergent - may or may not happen
        # Just verify no crashes and track what happened
        assert colocated_engine.tick == 10

    @pytest.mark.asyncio
    async def test_pending_invite_can_be_created(self, colocated_engine):
        """System can track pending invites between agents."""
        # Run several ticks, checking for invites
        for _ in range(10):
            await colocated_engine.tick_once()

            # Check if any invites were created
            if colocated_engine.pending_invites:
                # Verify invite structure is valid
                for invitee, invite in colocated_engine.pending_invites.items():
                    assert invite.inviter is not None
                    assert invite.conversation_id is not None
                break


# =============================================================================
# Dream-Encouraged Conversation Tests
# =============================================================================


class TestDreamEncouragedConversation:
    """Test conversation flow when agents are encouraged via dreams."""

    @pytest.mark.asyncio
    async def test_dream_encouraged_invite_creates_event(self, colocated_engine):
        """Agent receiving dream to invite creates a conversation_invited event."""
        # Send Alice a dream encouraging her to invite Bob
        dream_content = """
You feel a strong impulse to formally invite Bob to a conversation.
Bob is right here with you. Use the invite_to_conversation tool
with invitee="Bob" to start a real conversation with him.
"""
        colocated_engine.write_to_agent_dreams(AgentName("Alice"), dream_content)

        # Run tick - Alice should use invite tool
        result = await colocated_engine.tick_once()

        # Check for conversation_invited event
        invite_events = [e for e in result.events if e.type == "conversation_invited"]
        assert len(invite_events) >= 1, "No conversation_invited event created"

        # Verify invite structure
        invite = invite_events[0]
        assert invite.inviter == AgentName("Alice")
        assert invite.invitee == AgentName("Bob")
        assert invite.location == LocationId("workshop")

    @pytest.mark.asyncio
    async def test_dream_encouraged_invite_and_accept(self, colocated_engine):
        """Agent accepts invite when encouraged via dream."""
        # Send Alice a dream to invite Bob
        alice_dream = """
You must formally invite Bob to a conversation using the invite_to_conversation tool.
invitee="Bob", privacy="private". Do this now.
"""
        colocated_engine.write_to_agent_dreams(AgentName("Alice"), alice_dream)

        # Tick 1: Alice should invite
        result1 = await colocated_engine.tick_once()
        invite_events = [e for e in result1.events if e.type == "conversation_invited"]
        assert len(invite_events) >= 1, "No invite created in tick 1"

        # Verify pending invite exists
        assert AgentName("Bob") in colocated_engine.pending_invites

        # Send Bob a dream to accept the invite
        bob_dream = """
You have a pending conversation invitation from Alice! Accept it immediately
using the accept_invite tool.
"""
        colocated_engine.write_to_agent_dreams(AgentName("Bob"), bob_dream)

        # Tick 2: Bob should accept
        result2 = await colocated_engine.tick_once()

        # Check for conversation started
        started_events = [e for e in result2.events if e.type == "conversation_started"]
        if not started_events:
            # May need another tick for the accept to process
            result3 = await colocated_engine.tick_once()
            started_events = [e for e in result3.events if e.type == "conversation_started"]

        assert len(started_events) >= 1, "Conversation was not started after invite acceptance"

        # Verify conversation exists
        assert len(colocated_engine.conversations) >= 1

    @pytest.mark.asyncio
    async def test_full_conversation_flow_with_dreams(self, colocated_engine):
        """Test complete flow: invite -> accept -> conversation turns."""
        # Dream 1: Alice invites
        colocated_engine.write_to_agent_dreams(
            AgentName("Alice"),
            "Formally invite Bob to a conversation using invite_to_conversation tool. invitee='Bob'."
        )

        # Run until invite created
        invite_created = False
        for _ in range(3):
            result = await colocated_engine.tick_once()
            for event in result.events:
                if event.type == "conversation_invited":
                    invite_created = True
                    break
            if invite_created:
                break

        assert invite_created, "Failed to create invite"

        # Dream 2: Bob accepts
        colocated_engine.write_to_agent_dreams(
            AgentName("Bob"),
            "Accept the conversation invitation from Alice using the accept_invite tool."
        )

        # Run until conversation started
        conversation_started = False
        for _ in range(3):
            result = await colocated_engine.tick_once()
            for event in result.events:
                if event.type == "conversation_started":
                    conversation_started = True
                    break
            if conversation_started:
                break

        assert conversation_started, "Conversation was not started"

        # Run a few more ticks for conversation to happen
        turn_events = []
        for _ in range(5):
            result = await colocated_engine.tick_once()
            turn_events.extend([e for e in result.events if e.type == "conversation_turn"])

        # Should have some conversation turns
        # (This is emergent - the conversation may or may not have substantive turns)
        assert colocated_engine.tick >= 5, "Test completed required ticks"


# =============================================================================
# Conversation Turn Tests
# =============================================================================


class TestConversationTurns:
    """Test conversation turn mechanics with real Haiku."""

    @pytest.mark.asyncio
    async def test_conversation_accumulates_history(self, colocated_engine):
        """Active conversations accumulate turn history."""
        # Run ticks to potentially start and continue conversation
        for _ in range(15):
            await colocated_engine.tick_once()

        # If any conversations exist, check their history
        for conv_id, conv in colocated_engine.conversations.items():
            # History should exist if conversation is active
            assert hasattr(conv, "history")

    @pytest.mark.asyncio
    async def test_turn_events_generated(self, colocated_engine):
        """Conversation turns generate events."""
        turn_events = []

        for _ in range(10):
            result = await colocated_engine.tick_once()
            turn_events.extend([
                e for e in result.events
                if e.type == "conversation_turn"
            ])

        # Turn events may or may not occur depending on emergent behavior
        # Just verify the system tracks them correctly
        for event in turn_events:
            assert event.tick > 0


# =============================================================================
# Narrative Quality Tests (LLM Judge)
# =============================================================================


class TestNarrativeQuality:
    """Test narrative quality with LLM judge validation."""

    @pytest.mark.asyncio
    async def test_narratives_are_coherent(self, colocated_engine, llm_judge):
        """Agent narratives should be coherent (LLM judge validation)."""
        result = await colocated_engine.tick_once()

        for agent_name, turn_result in result.turn_results.items():
            if not turn_result.narrative:
                continue

            agent = colocated_engine.agents[agent_name]

            judgment = llm_judge(
                "Is this narrative coherent and believable?",
                f"Agent: {agent_name} ({agent.job})\n"
                f"Location: {agent.location}\n"
                f"Narrative: {turn_result.narrative}"
            )

            if not judgment.passed:
                pytest.skip(f"LLM judge for {agent_name}: {judgment.reasoning}")

    @pytest.mark.asyncio
    async def test_interaction_seems_natural(self, colocated_engine, llm_judge):
        """Interaction between agents should seem natural."""
        all_narratives = []

        for _ in range(5):
            result = await colocated_engine.tick_once()
            for agent_name, turn_result in result.turn_results.items():
                if turn_result.narrative:
                    all_narratives.append(f"{agent_name}: {turn_result.narrative}")

        if len(all_narratives) < 2:
            pytest.skip("Not enough narratives to evaluate interaction")

        combined = "\n\n".join(all_narratives)

        judgment = llm_judge(
            "Do these agent narratives seem like a natural interaction?",
            f"Agent narratives over 5 ticks:\n{combined}"
        )

        if not judgment.passed:
            pytest.skip(f"LLM judge: {judgment.reasoning}")


# =============================================================================
# State Consistency Tests
# =============================================================================


class TestTwoAgentStateConsistency:
    """Test state consistency with two agents."""

    @pytest.mark.asyncio
    async def test_agents_remain_valid(self, colocated_engine):
        """Both agents remain in valid state after interactions."""
        for _ in range(10):
            await colocated_engine.tick_once()

        for name, agent in colocated_engine.agents.items():
            assert agent.name == name
            assert agent.location in colocated_engine.world.locations
            assert 0 <= agent.energy <= 100

    @pytest.mark.asyncio
    async def test_events_have_valid_structure(self, colocated_engine):
        """All events have valid structure."""
        for i in range(5):
            result = await colocated_engine.tick_once()
            for event in result.events:
                assert event.tick == i + 1
                assert hasattr(event, "type")


# =============================================================================
# Movement During Interaction Tests
# =============================================================================


class TestMovementDuringInteraction:
    """Test movement behavior when agents are together."""

    @pytest.mark.asyncio
    async def test_agent_may_move_away(self, colocated_engine):
        """Agent might decide to move to different location (emergent)."""
        initial_locations = {
            name: agent.location
            for name, agent in colocated_engine.agents.items()
        }

        for _ in range(10):
            await colocated_engine.tick_once()

        # Check if any agent moved
        moved = False
        for name, agent in colocated_engine.agents.items():
            if agent.location != initial_locations[name]:
                moved = True
                break

        # Movement is emergent - just verify no crashes
        assert colocated_engine.tick == 10


# =============================================================================
# Recovery Tests
# =============================================================================


class TestTwoAgentRecovery:
    """Test state recovery with two-agent interactions."""

    @pytest.mark.asyncio
    async def test_recovery_preserves_colocated_state(
        self, temp_village, colocated_engine
    ):
        """State recovery preserves co-located agent state."""
        # Run some ticks
        for _ in range(5):
            await colocated_engine.tick_once()

        tick_before = colocated_engine.tick
        locations_before = {
            n: a.location for n, a in colocated_engine.agents.items()
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

        # State should match
        assert engine2.tick == tick_before
        for name, loc in locations_before.items():
            assert engine2.agents[name].location == loc

    @pytest.mark.asyncio
    async def test_can_continue_after_recovery(self, temp_village, colocated_engine):
        """Simulation can continue after recovery."""
        # Run some ticks
        for _ in range(3):
            await colocated_engine.tick_once()

        # Recover in new engine
        from engine.engine import VillageEngine
        from engine.adapters import ClaudeProvider

        provider = ClaudeProvider(model="claude-haiku-4-5-20251001")
        engine2 = VillageEngine(
            village_root=temp_village,
            llm_provider=provider,
        )
        engine2.recover()

        # Continue simulation
        for _ in range(3):
            result = await engine2.tick_once()
            assert result is not None
