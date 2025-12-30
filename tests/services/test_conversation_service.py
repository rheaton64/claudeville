"""Tests for engine.services.conversation_service module."""

import pytest
from datetime import datetime

from engine.domain import (
    AgentName,
    LocationId,
    ConversationId,
    Conversation,
    Invitation,
    INVITE_EXPIRY_TICKS,
)
from engine.services.conversation_service import ConversationService


class TestConversationServiceBasics:
    """Tests for basic ConversationService functionality."""

    def test_empty_service(self, conversation_service: ConversationService):
        """Test empty service behavior."""
        assert conversation_service.get_all_conversations() == {}
        assert conversation_service.get_all_pending_invites() == {}

    def test_invite_expiry_constant(self):
        """Test invite expiry constant."""
        assert INVITE_EXPIRY_TICKS == 2


class TestInviteCreation:
    """Tests for invitation creation."""

    def test_create_invite(
        self,
        conversation_service: ConversationService,
        base_datetime: datetime,
    ):
        """Test creating an invitation."""
        conv_id, invite = conversation_service.create_invite(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            location=LocationId("workshop"),
            privacy="private",
            current_tick=5,
            invited_at=base_datetime,
        )

        assert conv_id is not None
        assert invite.inviter == AgentName("Ember")
        assert invite.invitee == AgentName("Sage")
        assert invite.created_at_tick == 5
        assert invite.expires_at_tick == 5 + INVITE_EXPIRY_TICKS

    def test_pending_invite_stored(
        self,
        conversation_service: ConversationService,
        base_datetime: datetime,
    ):
        """Test invite is stored in pending invites."""
        conversation_service.create_invite(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            location=LocationId("workshop"),
            privacy="private",
            current_tick=5,
        )

        invite = conversation_service.get_pending_invite(AgentName("Sage"))
        assert invite is not None
        assert invite.inviter == AgentName("Ember")


class TestInviteAcceptance:
    """Tests for accepting invitations."""

    def test_accept_invite_creates_conversation(
        self,
        conversation_service: ConversationService,
        base_datetime: datetime,
    ):
        """Test accepting an invite creates a conversation."""
        conv_id, _ = conversation_service.create_invite(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            location=LocationId("workshop"),
            privacy="private",
            current_tick=5,
        )

        conv = conversation_service.accept_invite(
            agent=AgentName("Sage"),
            current_tick=6,
            timestamp=base_datetime,
        )

        assert conv is not None
        assert conv.id == conv_id
        assert AgentName("Ember") in conv.participants
        assert AgentName("Sage") in conv.participants
        assert len(conv.participants) == 2

    def test_accept_invite_removes_pending(
        self,
        conversation_service: ConversationService,
        base_datetime: datetime,
    ):
        """Test accepting an invite removes it from pending."""
        conversation_service.create_invite(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            location=LocationId("workshop"),
            privacy="private",
            current_tick=5,
        )

        conversation_service.accept_invite(
            agent=AgentName("Sage"),
            current_tick=6,
            timestamp=base_datetime,
        )

        assert conversation_service.get_pending_invite(AgentName("Sage")) is None

    def test_accept_nonexistent_invite_returns_none(
        self,
        conversation_service: ConversationService,
        base_datetime: datetime,
    ):
        """Test accepting a nonexistent invite returns None."""
        result = conversation_service.accept_invite(
            agent=AgentName("Sage"),
            current_tick=6,
            timestamp=base_datetime,
        )

        assert result is None


class TestInviteDecline:
    """Tests for declining invitations."""

    def test_decline_invite(
        self,
        conversation_service: ConversationService,
    ):
        """Test declining an invite returns and removes it."""
        conversation_service.create_invite(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            location=LocationId("workshop"),
            privacy="private",
            current_tick=5,
        )

        declined = conversation_service.decline_invite(AgentName("Sage"))

        assert declined is not None
        assert declined.invitee == AgentName("Sage")
        assert conversation_service.get_pending_invite(AgentName("Sage")) is None

    def test_decline_nonexistent_returns_none(
        self,
        conversation_service: ConversationService,
    ):
        """Test declining nonexistent invite returns None."""
        result = conversation_service.decline_invite(AgentName("Sage"))

        assert result is None


class TestInviteExpiry:
    """Tests for invitation expiry."""

    def test_expire_invite(
        self,
        conversation_service: ConversationService,
    ):
        """Test expiring an invite."""
        conversation_service.create_invite(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            location=LocationId("workshop"),
            privacy="private",
            current_tick=5,
        )

        expired = conversation_service.expire_invite(AgentName("Sage"))

        assert expired is not None
        assert conversation_service.get_pending_invite(AgentName("Sage")) is None

    def test_expire_invites_at_tick(
        self,
        conversation_service: ConversationService,
    ):
        """Test batch expiring invites at a tick."""
        # Create invite that expires at tick (5 + INVITE_EXPIRY_TICKS)
        conversation_service.create_invite(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            location=LocationId("workshop"),
            privacy="private",
            current_tick=5,
        )

        # At expiry tick, it should expire (uses <=)
        expired = conversation_service.expire_invites_at_tick(current_tick=5 + INVITE_EXPIRY_TICKS)

        assert len(expired) == 1
        assert expired[0].invitee == AgentName("Sage")

    def test_expire_invites_before_expiry_tick(
        self,
        conversation_service: ConversationService,
    ):
        """Test invites don't expire before their expiry tick."""
        conversation_service.create_invite(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            location=LocationId("workshop"),
            privacy="private",
            current_tick=5,
        )

        # At tick 5, invite expires at (5 + INVITE_EXPIRY_TICKS), should NOT expire yet
        expired = conversation_service.expire_invites_at_tick(current_tick=5)

        assert len(expired) == 0


class TestJoinConversation:
    """Tests for joining conversations."""

    def test_join_public_conversation(
        self,
        conversation_service: ConversationService,
        base_datetime: datetime,
    ):
        """Test joining a public conversation."""
        # Create a public conversation
        conv_id, _ = conversation_service.create_invite(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            location=LocationId("workshop"),
            privacy="public",
            current_tick=5,
        )
        conversation_service.accept_invite(
            AgentName("Sage"),
            current_tick=6,
            timestamp=base_datetime,
        )

        # River joins
        conv = conversation_service.join_conversation(
            AgentName("River"),
            conv_id,
        )

        assert conv is not None
        assert AgentName("River") in conv.participants
        assert len(conv.participants) == 3

    def test_join_private_conversation_fails(
        self,
        conversation_service: ConversationService,
        base_datetime: datetime,
    ):
        """Test joining a private conversation fails."""
        conv_id, _ = conversation_service.create_invite(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            location=LocationId("workshop"),
            privacy="private",
            current_tick=5,
        )
        conversation_service.accept_invite(
            AgentName("Sage"),
            current_tick=6,
            timestamp=base_datetime,
        )

        result = conversation_service.join_conversation(
            AgentName("River"),
            conv_id,
        )

        assert result is None

    def test_join_nonexistent_conversation_fails(
        self,
        conversation_service: ConversationService,
    ):
        """Test joining nonexistent conversation fails."""
        result = conversation_service.join_conversation(
            AgentName("River"),
            ConversationId("nonexistent"),
        )

        assert result is None

    def test_join_already_in_conversation(
        self,
        conversation_service: ConversationService,
        base_datetime: datetime,
    ):
        """Test joining when already in conversation returns conversation."""
        conv_id, _ = conversation_service.create_invite(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            location=LocationId("workshop"),
            privacy="public",
            current_tick=5,
        )
        conversation_service.accept_invite(
            AgentName("Sage"),
            current_tick=6,
            timestamp=base_datetime,
        )

        # Sage tries to join again
        conv = conversation_service.join_conversation(
            AgentName("Sage"),
            conv_id,
        )

        assert conv is not None
        assert len(conv.participants) == 2  # Still 2, not duplicated


class TestLeaveConversation:
    """Tests for leaving conversations."""

    def test_leave_conversation_three_participants(
        self,
        conversation_service: ConversationService,
        base_datetime: datetime,
    ):
        """Test leaving a conversation with 3+ participants."""
        # Create conversation with 3 participants
        conv_id, _ = conversation_service.create_invite(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            location=LocationId("workshop"),
            privacy="public",
            current_tick=5,
        )
        conversation_service.accept_invite(
            AgentName("Sage"),
            current_tick=6,
            timestamp=base_datetime,
        )
        conversation_service.join_conversation(AgentName("River"), conv_id)

        # River leaves (still has Ember and Sage)
        conv, ended = conversation_service.leave_conversation(
            AgentName("River"),
            conv_id,
        )

        assert ended is False
        assert conv is not None
        assert AgentName("River") not in conv.participants
        assert len(conv.participants) == 2

    def test_leave_ends_conversation_below_two(
        self,
        conversation_service: ConversationService,
        base_datetime: datetime,
    ):
        """Test leaving ends conversation when < 2 participants remain."""
        # Create conversation with exactly 2 participants
        conv_id, _ = conversation_service.create_invite(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            location=LocationId("workshop"),
            privacy="private",
            current_tick=5,
        )
        conversation_service.accept_invite(
            AgentName("Sage"),
            current_tick=6,
            timestamp=base_datetime,
        )

        # First leave (still 1 remaining)
        _, ended = conversation_service.leave_conversation(
            AgentName("Sage"),
            conv_id,
        )

        assert ended is True
        assert conversation_service.get_conversation(conv_id) is None

    def test_leave_nonexistent_conversation(
        self,
        conversation_service: ConversationService,
    ):
        """Test leaving nonexistent conversation returns None, False."""
        conv, ended = conversation_service.leave_conversation(
            AgentName("Sage"),
            ConversationId("nonexistent"),
        )

        assert conv is None
        assert ended is False


class TestConversationTurns:
    """Tests for conversation turn management."""

    def test_add_turn(
        self,
        populated_conversation_service: ConversationService,
        sample_conversation: Conversation,
        base_datetime: datetime,
    ):
        """Test adding a turn to conversation."""
        conv = populated_conversation_service.add_turn(
            conv_id=sample_conversation.id,
            speaker=AgentName("Sage"),
            narrative="I was just thinking about you!",
            tick=2,
            timestamp=base_datetime,
        )

        assert conv is not None
        assert len(conv.history) == 2  # Original had 1 turn
        assert conv.history[-1].speaker == AgentName("Sage")
        assert conv.history[-1].narrative == "I was just thinking about you!"

    def test_add_turn_clears_next_speaker(
        self,
        populated_conversation_service: ConversationService,
        sample_conversation: Conversation,
        base_datetime: datetime,
    ):
        """Test adding turn clears next_speaker if that agent spoke."""
        # sample_conversation has next_speaker=Sage
        conv = populated_conversation_service.add_turn(
            conv_id=sample_conversation.id,
            speaker=AgentName("Sage"),  # This is the next_speaker
            narrative="Hello!",
            tick=2,
            timestamp=base_datetime,
        )

        assert conv.next_speaker is None

    def test_add_turn_keeps_different_next_speaker(
        self,
        populated_conversation_service: ConversationService,
        sample_conversation: Conversation,
        base_datetime: datetime,
    ):
        """Test adding turn keeps next_speaker if different agent spoke."""
        # sample_conversation has next_speaker=Sage
        conv = populated_conversation_service.add_turn(
            conv_id=sample_conversation.id,
            speaker=AgentName("Ember"),  # Not the next_speaker
            narrative="Actually, I'll go first.",
            tick=2,
            timestamp=base_datetime,
        )

        assert conv.next_speaker == AgentName("Sage")

    def test_add_turn_nonparticipant_fails(
        self,
        populated_conversation_service: ConversationService,
        sample_conversation: Conversation,
        base_datetime: datetime,
    ):
        """Test non-participant cannot add turn."""
        result = populated_conversation_service.add_turn(
            conv_id=sample_conversation.id,
            speaker=AgentName("River"),  # Not in conversation
            narrative="Can I join?",
            tick=2,
            timestamp=base_datetime,
        )

        assert result is None


class TestNextSpeaker:
    """Tests for next speaker management."""

    def test_set_next_speaker(
        self,
        populated_conversation_service: ConversationService,
        sample_conversation: Conversation,
    ):
        """Test setting next speaker."""
        result = populated_conversation_service.set_next_speaker(
            sample_conversation.id,
            AgentName("Ember"),
        )

        assert result is True
        conv = populated_conversation_service.get_conversation(sample_conversation.id)
        assert conv.next_speaker == AgentName("Ember")

    def test_set_next_speaker_nonparticipant_fails(
        self,
        populated_conversation_service: ConversationService,
        sample_conversation: Conversation,
    ):
        """Test setting next speaker to non-participant fails."""
        result = populated_conversation_service.set_next_speaker(
            sample_conversation.id,
            AgentName("River"),  # Not in conversation
        )

        assert result is False

    def test_get_next_speaker_returns_set_speaker(
        self,
        populated_conversation_service: ConversationService,
        sample_conversation: Conversation,
    ):
        """Test get_next_speaker returns explicitly set speaker."""
        # sample_conversation has next_speaker=Sage
        speaker = populated_conversation_service.get_next_speaker(
            sample_conversation.id,
        )

        assert speaker == AgentName("Sage")

    def test_get_next_speaker_random_when_not_set(
        self,
        conversation_service: ConversationService,
        base_datetime: datetime,
    ):
        """Test get_next_speaker picks randomly when not set."""
        conv_id, _ = conversation_service.create_invite(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            location=LocationId("workshop"),
            privacy="private",
            current_tick=5,
        )
        conversation_service.accept_invite(
            AgentName("Sage"),
            current_tick=6,
            timestamp=base_datetime,
        )

        speaker = conversation_service.get_next_speaker(conv_id)

        # Should return one of the participants
        assert speaker in [AgentName("Ember"), AgentName("Sage")]


class TestEndConversation:
    """Tests for ending conversations."""

    def test_end_conversation(
        self,
        populated_conversation_service: ConversationService,
        sample_conversation: Conversation,
    ):
        """Test explicitly ending a conversation."""
        ended = populated_conversation_service.end_conversation(sample_conversation.id)

        assert ended is not None
        assert ended.id == sample_conversation.id
        assert populated_conversation_service.get_conversation(sample_conversation.id) is None

    def test_end_nonexistent_conversation(
        self,
        conversation_service: ConversationService,
    ):
        """Test ending nonexistent conversation returns None."""
        result = conversation_service.end_conversation(ConversationId("nonexistent"))

        assert result is None


class TestConversationQueries:
    """Tests for conversation queries."""

    def test_get_conversations_for_agent(
        self,
        populated_conversation_service: ConversationService,
    ):
        """Test getting conversations for an agent."""
        convs = populated_conversation_service.get_conversations_for_agent(
            AgentName("Ember")
        )

        assert len(convs) == 1

    def test_get_conversations_at_location(
        self,
        conversation_service: ConversationService,
        base_datetime: datetime,
    ):
        """Test getting conversations at a location."""
        # Create a public conversation at workshop
        conv_id, _ = conversation_service.create_invite(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            location=LocationId("workshop"),
            privacy="public",
            current_tick=5,
        )
        conversation_service.accept_invite(
            AgentName("Sage"),
            current_tick=6,
            timestamp=base_datetime,
        )

        convs = conversation_service.get_conversations_at_location(
            LocationId("workshop"),
            public_only=True,
        )

        assert len(convs) == 1

    def test_is_in_conversation(
        self,
        populated_conversation_service: ConversationService,
    ):
        """Test checking if agent is in any conversation."""
        assert populated_conversation_service.is_in_conversation(AgentName("Ember"))
        assert not populated_conversation_service.is_in_conversation(AgentName("River"))

    def test_is_in_specific_conversation(
        self,
        populated_conversation_service: ConversationService,
        sample_conversation: Conversation,
    ):
        """Test checking if agent is in specific conversation."""
        assert populated_conversation_service.is_in_specific_conversation(
            AgentName("Ember"),
            sample_conversation.id,
        )
        assert not populated_conversation_service.is_in_specific_conversation(
            AgentName("River"),
            sample_conversation.id,
        )


class TestConversationContext:
    """Tests for get_conversation_context."""

    def test_get_context_basic(
        self,
        populated_conversation_service: ConversationService,
        sample_conversation: Conversation,
    ):
        """Test getting conversation context."""
        context = populated_conversation_service.get_conversation_context(
            sample_conversation.id,
            AgentName("Sage"),
        )

        assert context is not None
        assert context["conversation"] == sample_conversation
        assert context["participant_count"] == 2
        assert context["is_group"] is False
        assert AgentName("Ember") in context["other_participants"]

    def test_get_context_is_opener(
        self,
        conversation_service: ConversationService,
        base_datetime: datetime,
    ):
        """Test is_opener flag for new conversation."""
        conv_id, _ = conversation_service.create_invite(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            location=LocationId("workshop"),
            privacy="private",
            current_tick=5,
        )
        conversation_service.accept_invite(
            AgentName("Sage"),
            current_tick=6,
            timestamp=base_datetime,
        )

        context = conversation_service.get_conversation_context(
            conv_id,
            AgentName("Ember"),
        )

        assert context["is_opener"] is True

    def test_get_context_nonparticipant_returns_none(
        self,
        populated_conversation_service: ConversationService,
        sample_conversation: Conversation,
    ):
        """Test non-participant gets None context."""
        context = populated_conversation_service.get_conversation_context(
            sample_conversation.id,
            AgentName("River"),  # Not in conversation
        )

        assert context is None


class TestLoadState:
    """Tests for load_state functionality."""

    def test_load_state(
        self,
        conversation_service: ConversationService,
        sample_conversation: Conversation,
        sample_invitation: Invitation,
    ):
        """Test loading state from snapshot."""
        conversations = {sample_conversation.id: sample_conversation}
        pending_invites = {sample_invitation.invitee: sample_invitation}

        conversation_service.load_state(conversations, pending_invites)

        assert conversation_service.get_conversation(sample_conversation.id) is not None
        assert conversation_service.get_pending_invite(sample_invitation.invitee) is not None
        assert conversation_service.is_in_conversation(AgentName("Ember"))
