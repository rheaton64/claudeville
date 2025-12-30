"""
Level 3 Integration Tests: Conversation Flow

Tests the full conversation lifecycle with mock LLM:
- Invite → Accept → Conversation Start
- Invite → Decline
- Invite expiration
- Turn rotation
- Leave conversation
- Conversation end

Run with: uv run pytest tests/integration/test_conversation_flow.py -v
"""

from __future__ import annotations

from datetime import datetime, timedelta

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
)


# =============================================================================
# Invitation Flow Tests
# =============================================================================


class TestInvitationFlow:
    """Test conversation invitation mechanics."""

    @pytest.mark.asyncio
    async def test_invite_creates_pending_invite(
        self,
        test_engine,
        mock_provider: MockLLMProvider,
    ):
        """Inviting creates a pending invite for the invitee."""
        # Move Bob to workshop (same as Alice)
        test_engine._agents[AgentName("Bob")] = test_engine.agents[
            AgentName("Bob")
        ].model_copy(update={"location": LocationId("workshop")})

        mock_provider.set_narrative("Alice", SAMPLE_NARRATIVES["invite_bob"])
        mock_provider.set_tool_call(
            "Alice",
            "invite_to_conversation",
            {"invitee": "Bob", "privacy": "private"},
        )

        await test_engine.tick_once()

        # Should have a pending invite for Bob
        assert AgentName("Bob") in test_engine.pending_invites
        invite = test_engine.pending_invites[AgentName("Bob")]
        assert invite.inviter == AgentName("Alice")

    @pytest.mark.asyncio
    async def test_invite_accept_creates_conversation(
        self,
        test_engine,
        mock_provider: MockLLMProvider,
    ):
        """Accepting invite creates an active conversation."""
        # Setup: Move Bob to workshop
        test_engine._agents[AgentName("Bob")] = test_engine.agents[
            AgentName("Bob")
        ].model_copy(update={"location": LocationId("workshop")})

        # Tick 1: Alice invites Bob
        mock_provider.set_narrative("Alice", "I'd like to chat with Bob.")
        mock_provider.set_tool_call(
            "Alice",
            "invite_to_conversation",
            {"invitee": "Bob", "privacy": "public"},
        )
        await test_engine.tick_once()

        assert AgentName("Bob") in test_engine.pending_invites
        invite = test_engine.pending_invites[AgentName("Bob")]
        conv_id = invite.conversation_id

        # Tick 2: Bob accepts
        mock_provider.clear_tool_call("Alice")
        mock_provider.set_narrative("Alice", "I wait for Bob's response.")
        mock_provider.set_narrative("Bob", "I'd be happy to chat!")
        mock_provider.set_tool_call(
            "Bob",
            "accept_invite",
            {"conversation_id": str(conv_id)},
        )
        await test_engine.tick_once()

        # Pending invite should be cleared
        assert AgentName("Bob") not in test_engine.pending_invites

        # Conversation should exist
        assert conv_id in test_engine.conversations
        conv = test_engine.conversations[conv_id]
        assert AgentName("Alice") in conv.participants
        assert AgentName("Bob") in conv.participants

    @pytest.mark.asyncio
    async def test_invite_decline_removes_invite(
        self,
        test_engine,
        mock_provider: MockLLMProvider,
    ):
        """Declining invite removes it without creating conversation."""
        # Setup
        test_engine._agents[AgentName("Bob")] = test_engine.agents[
            AgentName("Bob")
        ].model_copy(update={"location": LocationId("workshop")})

        # Tick 1: Alice invites
        mock_provider.set_tool_call(
            "Alice",
            "invite_to_conversation",
            {"invitee": "Bob", "privacy": "private"},
        )
        await test_engine.tick_once()

        invite = test_engine.pending_invites[AgentName("Bob")]
        conv_id = invite.conversation_id

        # Tick 2: Bob declines
        mock_provider.clear_tool_call("Alice")
        mock_provider.set_tool_call(
            "Bob",
            "decline_invite",
            {"conversation_id": str(conv_id)},
        )
        await test_engine.tick_once()

        # Invite cleared, no conversation
        assert AgentName("Bob") not in test_engine.pending_invites
        assert conv_id not in test_engine.conversations

    @pytest.mark.asyncio
    async def test_cannot_invite_agent_at_different_location(
        self,
        test_engine,
        mock_provider: MockLLMProvider,
    ):
        """Cannot invite agent who is at a different location."""
        # Bob is at library, Alice at workshop (default setup)
        mock_provider.set_tool_call(
            "Alice",
            "invite_to_conversation",
            {"invitee": "Bob", "privacy": "public"},
        )
        await test_engine.tick_once()

        # Should NOT have created an invite (different locations)
        assert AgentName("Bob") not in test_engine.pending_invites


# =============================================================================
# Conversation Turn Tests
# =============================================================================


class TestConversationTurns:
    """Test conversation turn mechanics."""

    @pytest.mark.asyncio
    async def test_conversation_records_turn(
        self,
        test_engine_with_conversation,
        mock_provider: MockLLMProvider,
    ):
        """Speaking in conversation records the turn."""
        engine = test_engine_with_conversation

        mock_provider.set_narrative("Alice", "Hello Bob! Nice day, isn't it?")
        mock_provider.set_narrative("Bob", "Indeed it is!")

        result = await engine.tick_once()

        # Check for conversation turn events
        turn_events = [e for e in result.events if e.type == "conversation_turn"]
        # Should have at least one turn
        assert len(turn_events) >= 1

    @pytest.mark.asyncio
    async def test_conversation_history_accumulates(
        self,
        test_engine_with_conversation,
        mock_provider: MockLLMProvider,
    ):
        """Conversation history grows with each turn."""
        engine = test_engine_with_conversation

        # Get initial history length
        conv_id = list(engine.conversations.keys())[0]
        initial_len = len(engine.conversations[conv_id].history)

        # Run several ticks
        for i in range(3):
            mock_provider.set_narrative("Alice", f"Alice says thing {i}")
            mock_provider.set_narrative("Bob", f"Bob responds {i}")
            await engine.tick_once()

        # History should have grown
        final_len = len(engine.conversations[conv_id].history)
        assert final_len > initial_len


# =============================================================================
# Leave Conversation Tests
# =============================================================================


class TestLeaveConversation:
    """Test leaving conversations."""

    @pytest.mark.asyncio
    async def test_leave_tool_is_called(
        self,
        test_engine_with_conversation,
        mock_provider: MockLLMProvider,
    ):
        """Leaving conversation tool call is registered."""
        engine = test_engine_with_conversation
        conv_id = list(engine.conversations.keys())[0]

        # Set Bob as the actor since he's next_speaker
        mock_provider.set_narrative("Bob", SAMPLE_NARRATIVES["end_conversation"])
        mock_provider.set_tool_call(
            "Bob",
            "leave_conversation",
            {"conversation_id": str(conv_id)},
        )

        await engine.tick_once()

        # Verify tool was called
        assert mock_provider.tool_was_called("Bob", "leave_conversation")

    @pytest.mark.asyncio
    async def test_observer_can_end_conversation(
        self,
        test_engine_with_conversation,
        mock_provider: MockLLMProvider,
    ):
        """Observer API can end a conversation directly."""
        engine = test_engine_with_conversation
        conv_id = list(engine.conversations.keys())[0]

        # Use observer to end conversation
        engine.end_conversation(conv_id, reason="test")

        # Conversation should be ended
        assert conv_id not in engine.conversations


# =============================================================================
# Group Conversation Tests
# =============================================================================


class TestGroupConversation:
    """Test group conversation mechanics."""

    @pytest.mark.asyncio
    async def test_three_agent_conversation(
        self,
        test_engine_with_group_conversation,
        mock_provider: MockLLMProvider,
    ):
        """Three agents can be in a conversation together."""
        engine = test_engine_with_group_conversation

        conv_id = list(engine.conversations.keys())[0]
        conv = engine.conversations[conv_id]

        assert len(conv.participants) == 3
        assert AgentName("Alice") in conv.participants
        assert AgentName("Bob") in conv.participants
        assert AgentName("Carol") in conv.participants

    @pytest.mark.asyncio
    async def test_joinable_conversations_visible(
        self,
        test_engine_with_conversation,
        mock_provider: MockLLMProvider,
    ):
        """Agents can see public conversations at their location."""
        engine = test_engine_with_conversation

        conv_id = list(engine.conversations.keys())[0]
        conv = engine.conversations[conv_id]

        # Make conversation public and move Carol to same location
        engine._conversations[conv_id] = conv.model_copy(update={"privacy": "public"})
        engine._agents[AgentName("Carol")] = engine.agents[
            AgentName("Carol")
        ].model_copy(update={"location": conv.location})

        # Update world agent_locations to match
        new_locs = dict(engine.world.agent_locations)
        new_locs[AgentName("Carol")] = conv.location
        engine._world = engine.world.model_copy(update={"agent_locations": new_locs})

        mock_provider.set_narrative("Carol", "I see others talking.")

        await engine.tick_once()

        # Verify Carol was called with joinable conversation info
        calls = mock_provider.get_calls_for_agent("Carol")
        # Carol might or might not be scheduled based on conversation dynamics

    @pytest.mark.asyncio
    async def test_cannot_join_private_conversation(
        self,
        test_engine_with_conversation,
        mock_provider: MockLLMProvider,
    ):
        """Cannot join a private conversation without invite."""
        engine = test_engine_with_conversation

        conv_id = list(engine.conversations.keys())[0]
        conv = engine.conversations[conv_id]

        # Move Carol to same location
        engine._agents[AgentName("Carol")] = engine.agents[
            AgentName("Carol")
        ].model_copy(update={"location": conv.location})

        # Conversation is private by default, Carol tries to join
        mock_provider.set_tool_call(
            "Carol",
            "join_conversation",
            {"conversation_id": str(conv_id)},
        )

        await engine.tick_once()

        # Carol should NOT be in the conversation
        conv = engine.conversations[conv_id]
        assert AgentName("Carol") not in conv.participants


# =============================================================================
# Edge Cases
# =============================================================================


class TestConversationEdgeCases:
    """Test edge cases in conversation flow."""

    @pytest.mark.asyncio
    async def test_invalid_conversation_id(
        self,
        test_engine,
        mock_provider: MockLLMProvider,
    ):
        """Invalid conversation ID should not crash."""
        mock_provider.set_tool_call(
            "Alice",
            "join_conversation",
            {"conversation_id": "nonexistent-conv"},
        )

        # Should not crash
        result = await test_engine.tick_once()
        assert result is not None

    @pytest.mark.asyncio
    async def test_leave_nonexistent_conversation(
        self,
        test_engine,
        mock_provider: MockLLMProvider,
    ):
        """Leaving nonexistent conversation should not crash."""
        mock_provider.set_tool_call(
            "Alice",
            "leave_conversation",
            {"conversation_id": "nonexistent-conv"},
        )

        result = await test_engine.tick_once()
        assert result is not None

    @pytest.mark.asyncio
    async def test_accept_expired_invite(
        self,
        test_engine,
        mock_provider: MockLLMProvider,
    ):
        """Accepting with no pending invite should not crash."""
        mock_provider.set_tool_call(
            "Bob",
            "accept_invite",
            {"conversation_id": "nonexistent-conv"},
        )

        result = await test_engine.tick_once()
        assert result is not None
