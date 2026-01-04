"""Tests for ConversationService."""

import pytest

from core.types import AgentName, Position
from core.agent import Agent, AgentModel
from services import ConversationService
from storage import Storage


# --- Helpers ---


async def create_test_agent(storage: Storage, name: str, position: Position = Position(0, 0)):
    """Create a test agent."""
    agent = Agent(
        name=AgentName(name),
        model=AgentModel(id="test-model", display_name="Test"),
        position=position,
    )
    await storage.agents.save_agent(agent)
    return agent


class TestInvitationFlow:
    """Test the invite → accept/decline flow."""

    async def test_create_and_accept_invitation(
        self, storage: Storage, conversation_service: ConversationService
    ):
        """Should create invitation, then accept to start conversation."""
        await create_test_agent(storage, "Ember")
        await create_test_agent(storage, "Sage")

        # Ember invites Sage
        invite = await conversation_service.create_invite(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            privacy="public",
            tick=1,
        )
        assert invite.inviter == AgentName("Ember")
        assert invite.invitee == AgentName("Sage")

        # Check Sage has pending invitation
        assert await conversation_service.has_pending_invitation(AgentName("Sage"))

        # Sage accepts
        result = await conversation_service.accept_invite(AgentName("Sage"), tick=2)
        assert result is not None
        conv, returned_invite = result

        # Conversation should have both participants
        assert AgentName("Ember") in conv.participants
        assert AgentName("Sage") in conv.participants
        assert conv.privacy == "public"

        # Sage should no longer have pending invitation
        assert not await conversation_service.has_pending_invitation(AgentName("Sage"))

        # Both agents should be in conversation
        assert await conversation_service.is_agent_in_conversation(AgentName("Ember"))
        assert await conversation_service.is_agent_in_conversation(AgentName("Sage"))

    async def test_decline_invitation(
        self, storage: Storage, conversation_service: ConversationService
    ):
        """Should decline invitation without creating conversation."""
        await create_test_agent(storage, "Ember")
        await create_test_agent(storage, "Sage")

        # Ember invites Sage
        await conversation_service.create_invite(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            privacy="public",
            tick=1,
        )

        # Sage declines
        declined = await conversation_service.decline_invite(AgentName("Sage"))
        assert declined is not None
        assert declined.inviter == AgentName("Ember")

        # No conversation should exist
        assert not await conversation_service.is_agent_in_conversation(AgentName("Sage"))
        assert not await conversation_service.is_agent_in_conversation(AgentName("Ember"))
        assert not await conversation_service.has_pending_invitation(AgentName("Sage"))

    async def test_accept_nonexistent_invitation(
        self, storage: Storage, conversation_service: ConversationService
    ):
        """Should return None when accepting without invitation."""
        await create_test_agent(storage, "Sage")

        result = await conversation_service.accept_invite(AgentName("Sage"), tick=1)
        assert result is None


class TestConversationParticipation:
    """Test joining and leaving conversations."""

    async def test_leave_conversation(
        self, storage: Storage, conversation_service: ConversationService
    ):
        """Should leave conversation while other participant stays."""
        await create_test_agent(storage, "Ember")
        await create_test_agent(storage, "Sage")

        # Start conversation
        await conversation_service.create_invite(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            privacy="public",
            tick=1,
        )
        result = await conversation_service.accept_invite(AgentName("Sage"), tick=2)
        conv, _ = result

        # Sage leaves
        left_conv, was_ended = await conversation_service.leave_conversation(
            AgentName("Sage"), tick=3
        )
        assert not was_ended
        assert AgentName("Sage") not in left_conv.participants
        assert AgentName("Ember") in left_conv.participants

        # Sage should no longer be in conversation
        assert not await conversation_service.is_agent_in_conversation(AgentName("Sage"))
        # Ember should still be in conversation
        assert await conversation_service.is_agent_in_conversation(AgentName("Ember"))

    async def test_last_person_leaving_ends_conversation(
        self, storage: Storage, conversation_service: ConversationService
    ):
        """Should end conversation when last person leaves."""
        await create_test_agent(storage, "Ember")
        await create_test_agent(storage, "Sage")

        # Start conversation
        await conversation_service.create_invite(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            privacy="public",
            tick=1,
        )
        await conversation_service.accept_invite(AgentName("Sage"), tick=2)

        # Both leave
        await conversation_service.leave_conversation(AgentName("Sage"), tick=3)
        left_conv, was_ended = await conversation_service.leave_conversation(
            AgentName("Ember"), tick=4
        )

        assert was_ended
        assert left_conv.ended_at_tick == 4

    async def test_join_public_conversation(
        self, storage: Storage, conversation_service: ConversationService
    ):
        """Should join an existing public conversation."""
        await create_test_agent(storage, "Ember")
        await create_test_agent(storage, "Sage")
        await create_test_agent(storage, "River")

        # Start conversation between Ember and Sage
        await conversation_service.create_invite(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            privacy="public",
            tick=1,
        )
        result = await conversation_service.accept_invite(AgentName("Sage"), tick=2)
        conv, _ = result

        # River joins
        joined_conv = await conversation_service.join_conversation(
            AgentName("River"), conv.id, tick=3
        )

        assert AgentName("River") in joined_conv.participants
        assert await conversation_service.is_agent_in_conversation(AgentName("River"))


class TestConversationTurns:
    """Test speaking in conversations."""

    async def test_add_turn(
        self, storage: Storage, conversation_service: ConversationService
    ):
        """Should add turn to conversation."""
        await create_test_agent(storage, "Ember")
        await create_test_agent(storage, "Sage")

        # Start conversation
        await conversation_service.create_invite(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            privacy="public",
            tick=1,
        )
        await conversation_service.accept_invite(AgentName("Sage"), tick=2)

        # Ember speaks
        result = await conversation_service.add_turn(
            agent=AgentName("Ember"),
            message="Hello, Sage!",
            tick=3,
        )
        assert result is not None
        conv, turn = result

        assert turn.speaker == AgentName("Ember")
        assert turn.message == "Hello, Sage!"
        assert len(conv.history) == 1

    async def test_add_turn_not_in_conversation(
        self, storage: Storage, conversation_service: ConversationService
    ):
        """Should return None when speaking outside conversation."""
        await create_test_agent(storage, "Ember")

        result = await conversation_service.add_turn(
            agent=AgentName("Ember"),
            message="Hello?",
            tick=1,
        )
        assert result is None


class TestConversationContext:
    """Test getting conversation context with unseen turns."""

    async def test_get_conversation_context(
        self, storage: Storage, conversation_service: ConversationService
    ):
        """Should get context with only unseen turns."""
        await create_test_agent(storage, "Ember")
        await create_test_agent(storage, "Sage")

        # Start conversation
        await conversation_service.create_invite(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            privacy="public",
            tick=1,
        )
        await conversation_service.accept_invite(AgentName("Sage"), tick=2)

        # Ember speaks (Sage hasn't spoken yet, so this is unseen)
        await conversation_service.add_turn(AgentName("Ember"), "Hello!", tick=3)
        await conversation_service.add_turn(AgentName("Ember"), "Anyone there?", tick=4)

        # Get context for Sage - should see both turns (hasn't spoken yet)
        ctx = await conversation_service.get_conversation_context(AgentName("Sage"))
        assert ctx is not None
        assert len(ctx.unseen_turns) == 2
        assert ctx.unseen_turns[0].message == "Hello!"
        assert AgentName("Ember") in ctx.other_participants

    async def test_unseen_turns_updates_after_speaking(
        self, storage: Storage, conversation_service: ConversationService
    ):
        """Should only show turns after agent's last turn."""
        await create_test_agent(storage, "Ember")
        await create_test_agent(storage, "Sage")

        # Start conversation
        await conversation_service.create_invite(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            privacy="public",
            tick=1,
        )
        await conversation_service.accept_invite(AgentName("Sage"), tick=2)

        # Conversation history
        await conversation_service.add_turn(AgentName("Ember"), "Hello!", tick=3)
        await conversation_service.add_turn(AgentName("Sage"), "Hi there!", tick=4)
        await conversation_service.add_turn(AgentName("Ember"), "How are you?", tick=5)

        # Sage should only see the last message (after tick 4)
        ctx = await conversation_service.get_conversation_context(AgentName("Sage"))
        assert len(ctx.unseen_turns) == 1
        assert ctx.unseen_turns[0].message == "How are you?"


class TestInvitationExpiry:
    """Test invitation expiration."""

    async def test_expire_invitations(
        self, storage: Storage, conversation_service: ConversationService
    ):
        """Should expire old invitations."""
        await create_test_agent(storage, "Ember")
        await create_test_agent(storage, "Sage")
        await create_test_agent(storage, "River")

        # Create two invitations at different times
        await conversation_service.create_invite(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            privacy="public",
            tick=1,
        )
        await conversation_service.create_invite(
            inviter=AgentName("River"),
            invitee=AgentName("Ember"),
            privacy="private",
            tick=5,
        )

        # Expire at tick 4 - only first should expire (INVITE_EXPIRY_TICKS = 2)
        expired = await conversation_service.expire_invitations(current_tick=4)
        assert len(expired) == 1
        assert expired[0].invitee == AgentName("Sage")

        # First invitation should be gone
        assert not await conversation_service.has_pending_invitation(AgentName("Sage"))
        # Second should still exist
        assert await conversation_service.has_pending_invitation(AgentName("Ember"))
