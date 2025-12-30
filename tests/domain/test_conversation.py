"""Tests for engine.domain.conversation module."""

import pytest
from datetime import datetime
from pydantic import ValidationError

from engine.domain import (
    AgentName,
    LocationId,
    ConversationId,
    ConversationTurn,
    Invitation,
    Conversation,
)


class TestConversationTurn:
    """Tests for ConversationTurn model."""

    def test_creation(self):
        """Test creating a ConversationTurn."""
        turn = ConversationTurn(
            speaker=AgentName("Ember"),
            narrative="Hello, how are you?",
            tick=5,
            timestamp=datetime(2024, 6, 15, 10, 0, 0),
        )
        assert turn.speaker == "Ember"
        assert turn.narrative == "Hello, how are you?"
        assert turn.tick == 5

    def test_immutability(self, sample_conversation_turn: ConversationTurn):
        """Test that ConversationTurn is frozen."""
        with pytest.raises(ValidationError):
            sample_conversation_turn.narrative = "Changed"  # type: ignore

    def test_serialization_roundtrip(self, sample_conversation_turn: ConversationTurn):
        """Test model_dump and model_validate roundtrip."""
        data = sample_conversation_turn.model_dump(mode="json")
        restored = ConversationTurn.model_validate(data)
        assert restored.speaker == sample_conversation_turn.speaker
        assert restored.narrative == sample_conversation_turn.narrative


class TestInvitation:
    """Tests for Invitation model."""

    def test_creation(self):
        """Test creating an Invitation."""
        invite = Invitation(
            conversation_id=ConversationId("conv-123"),
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            location=LocationId("workshop"),
            privacy="private",
            created_at_tick=1,
            expires_at_tick=2,
            invited_at=datetime(2024, 6, 15, 10, 0, 0),
        )
        assert invite.inviter == "Ember"
        assert invite.invitee == "Sage"
        assert invite.privacy == "private"
        assert invite.expires_at_tick == 2

    def test_default_invited_at(self):
        """Test invited_at has default value."""
        invite = Invitation(
            conversation_id=ConversationId("conv-123"),
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            location=LocationId("workshop"),
            privacy="public",
            created_at_tick=1,
            expires_at_tick=2,
        )
        # Should have a default datetime
        assert invite.invited_at is not None

    def test_immutability(self, sample_invitation: Invitation):
        """Test that Invitation is frozen."""
        with pytest.raises(ValidationError):
            sample_invitation.invitee = AgentName("River")  # type: ignore

    def test_serialization_roundtrip(self, sample_invitation: Invitation):
        """Test model_dump and model_validate roundtrip."""
        data = sample_invitation.model_dump(mode="json")
        restored = Invitation.model_validate(data)
        assert restored.inviter == sample_invitation.inviter
        assert restored.expires_at_tick == sample_invitation.expires_at_tick

    def test_privacy_values(self):
        """Test privacy can be public or private."""
        public = Invitation(
            conversation_id=ConversationId("conv-1"),
            inviter=AgentName("A"),
            invitee=AgentName("B"),
            location=LocationId("loc"),
            privacy="public",
            created_at_tick=1,
            expires_at_tick=2,
        )
        private = Invitation(
            conversation_id=ConversationId("conv-2"),
            inviter=AgentName("A"),
            invitee=AgentName("B"),
            location=LocationId("loc"),
            privacy="private",
            created_at_tick=1,
            expires_at_tick=2,
        )
        assert public.privacy == "public"
        assert private.privacy == "private"


class TestConversation:
    """Tests for Conversation model."""

    def test_creation_with_all_fields(self):
        """Test creating a Conversation with all fields."""
        turn = ConversationTurn(
            speaker=AgentName("Ember"),
            narrative="Hello!",
            tick=1,
            timestamp=datetime(2024, 6, 15, 10, 0, 0),
        )
        conv = Conversation(
            id=ConversationId("conv-001"),
            location=LocationId("workshop"),
            privacy="private",
            participants=frozenset({AgentName("Ember"), AgentName("Sage")}),
            history=(turn,),
            started_at_tick=1,
            created_by=AgentName("Ember"),
            next_speaker=AgentName("Sage"),
        )
        assert conv.id == "conv-001"
        assert len(conv.participants) == 2
        assert len(conv.history) == 1
        assert conv.next_speaker == "Sage"

    def test_default_values(self):
        """Test default values for optional fields."""
        conv = Conversation(
            id=ConversationId("conv-minimal"),
            location=LocationId("somewhere"),
            privacy="public",
            started_at_tick=1,
            created_by=AgentName("Creator"),
        )
        assert conv.participants == frozenset()
        assert conv.pending_invitations == {}
        assert conv.history == ()
        assert conv.next_speaker is None

    def test_immutability(self, sample_conversation: Conversation):
        """Test that Conversation is frozen."""
        with pytest.raises(ValidationError):
            sample_conversation.next_speaker = AgentName("River")  # type: ignore

    def test_serialization_roundtrip(self, sample_conversation: Conversation):
        """Test model_dump and model_validate roundtrip."""
        data = sample_conversation.model_dump(mode="json")
        restored = Conversation.model_validate(data)
        assert restored.id == sample_conversation.id
        assert restored.privacy == sample_conversation.privacy

    def test_participants_frozenset(self, sample_conversation: Conversation):
        """Test participants is a frozenset."""
        assert isinstance(sample_conversation.participants, frozenset)
        assert AgentName("Ember") in sample_conversation.participants

    def test_history_tuple(self, sample_conversation: Conversation):
        """Test history is a tuple."""
        assert isinstance(sample_conversation.history, tuple)

    def test_empty_conversation(self):
        """Test creating an empty conversation (before anyone joins)."""
        conv = Conversation(
            id=ConversationId("new-conv"),
            location=LocationId("garden"),
            privacy="public",
            started_at_tick=5,
            created_by=AgentName("Initiator"),
        )
        assert len(conv.participants) == 0
        assert len(conv.history) == 0


class TestConversationUpdates:
    """Tests for creating updated conversation snapshots."""

    def test_add_participant(self, sample_conversation: Conversation):
        """Test adding a participant creates new snapshot."""
        new_participants = sample_conversation.participants | {AgentName("River")}
        updated = Conversation(**{
            **sample_conversation.model_dump(),
            "participants": new_participants,
        })
        assert AgentName("River") in updated.participants
        assert len(updated.participants) == 3

    def test_add_turn_to_history(self, sample_conversation: Conversation):
        """Test adding a turn to history."""
        new_turn = ConversationTurn(
            speaker=AgentName("Sage"),
            narrative="Hello back!",
            tick=2,
            timestamp=datetime(2024, 6, 15, 10, 5, 0),
        )
        new_history = (*sample_conversation.history, new_turn)
        updated = Conversation(**{
            **sample_conversation.model_dump(),
            "history": new_history,
        })
        assert len(updated.history) == len(sample_conversation.history) + 1
        assert updated.history[-1].speaker == "Sage"

    def test_set_next_speaker(self, sample_conversation: Conversation):
        """Test setting next speaker."""
        updated = Conversation(**{
            **sample_conversation.model_dump(),
            "next_speaker": AgentName("River"),
        })
        assert updated.next_speaker == "River"

    def test_clear_next_speaker(self, sample_conversation: Conversation):
        """Test clearing next speaker."""
        updated = Conversation(**{
            **sample_conversation.model_dump(),
            "next_speaker": None,
        })
        assert updated.next_speaker is None

    def test_remove_participant(self, sample_conversation: Conversation):
        """Test removing a participant."""
        new_participants = sample_conversation.participants - {AgentName("Sage")}
        updated = Conversation(**{
            **sample_conversation.model_dump(),
            "participants": new_participants,
        })
        assert AgentName("Sage") not in updated.participants
        assert len(updated.participants) == 1
