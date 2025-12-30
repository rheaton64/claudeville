"""Tests for engine.domain.effects module."""

import pytest
from pydantic import TypeAdapter, ValidationError

from engine.domain import (
    AgentName,
    LocationId,
    ConversationId,
)
from engine.domain.effects import (
    Effect,
    MoveAgentEffect,
    UpdateMoodEffect,
    UpdateEnergyEffect,
    RecordActionEffect,
    AgentSleepEffect,
    AgentWakeEffect,
    InviteToConversationEffect,
    AcceptInviteEffect,
    DeclineInviteEffect,
    ExpireInviteEffect,
    JoinConversationEffect,
    LeaveConversationEffect,
    MoveConversationEffect,
    AddConversationTurnEffect,
    SetNextSpeakerEffect,
    EndConversationEffect,
)


# Type adapter for discriminated union
EffectAdapter = TypeAdapter(Effect)


class TestMoveAgentEffect:
    """Tests for MoveAgentEffect."""

    def test_creation(self):
        """Test creating a MoveAgentEffect."""
        effect = MoveAgentEffect(
            agent=AgentName("Ember"),
            from_location=LocationId("workshop"),
            to_location=LocationId("garden"),
        )
        assert effect.type == "move_agent"
        assert effect.agent == "Ember"
        assert effect.from_location == "workshop"
        assert effect.to_location == "garden"

    def test_immutability(self):
        """Test effect is frozen."""
        effect = MoveAgentEffect(
            agent=AgentName("Ember"),
            from_location=LocationId("a"),
            to_location=LocationId("b"),
        )
        with pytest.raises(ValidationError):
            effect.agent = AgentName("Other")  # type: ignore

    def test_serialization_roundtrip(self):
        """Test serialization and deserialization."""
        effect = MoveAgentEffect(
            agent=AgentName("Ember"),
            from_location=LocationId("workshop"),
            to_location=LocationId("garden"),
        )
        data = effect.model_dump()
        restored = MoveAgentEffect.model_validate(data)
        assert restored == effect


class TestUpdateMoodEffect:
    """Tests for UpdateMoodEffect."""

    def test_creation(self):
        """Test creating an UpdateMoodEffect."""
        effect = UpdateMoodEffect(
            agent=AgentName("Sage"),
            mood="happy",
        )
        assert effect.type == "update_mood"
        assert effect.agent == "Sage"
        assert effect.mood == "happy"


class TestUpdateEnergyEffect:
    """Tests for UpdateEnergyEffect."""

    def test_creation(self):
        """Test creating an UpdateEnergyEffect."""
        effect = UpdateEnergyEffect(
            agent=AgentName("River"),
            energy=75,
        )
        assert effect.type == "update_energy"
        assert effect.agent == "River"
        assert effect.energy == 75


class TestRecordActionEffect:
    """Tests for RecordActionEffect."""

    def test_creation(self):
        """Test creating a RecordActionEffect."""
        effect = RecordActionEffect(
            agent=AgentName("Ember"),
            description="Started painting a landscape",
        )
        assert effect.type == "record_action"
        assert effect.description == "Started painting a landscape"


class TestAgentSleepEffect:
    """Tests for AgentSleepEffect."""

    def test_creation(self):
        """Test creating an AgentSleepEffect."""
        effect = AgentSleepEffect(agent=AgentName("Luna"))
        assert effect.type == "agent_sleep"
        assert effect.agent == "Luna"


class TestAgentWakeEffect:
    """Tests for AgentWakeEffect."""

    def test_creation_without_reason(self):
        """Test creating an AgentWakeEffect without reason."""
        effect = AgentWakeEffect(agent=AgentName("Luna"))
        assert effect.type == "agent_wake"
        assert effect.reason is None

    def test_creation_with_reason(self):
        """Test creating an AgentWakeEffect with reason."""
        effect = AgentWakeEffect(
            agent=AgentName("Luna"),
            reason="time_period_changed",
        )
        assert effect.reason == "time_period_changed"


class TestInviteToConversationEffect:
    """Tests for InviteToConversationEffect."""

    def test_creation(self):
        """Test creating an InviteToConversationEffect."""
        effect = InviteToConversationEffect(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            location=LocationId("workshop"),
            privacy="private",
        )
        assert effect.type == "invite_to_conversation"
        assert effect.inviter == "Ember"
        assert effect.invitee == "Sage"
        assert effect.topic is None

    def test_creation_with_topic(self):
        """Test creating with optional topic."""
        effect = InviteToConversationEffect(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            location=LocationId("workshop"),
            privacy="private",
            topic="Let's discuss art",
        )
        assert effect.topic == "Let's discuss art"


class TestAcceptInviteEffect:
    """Tests for AcceptInviteEffect."""

    def test_creation(self):
        """Test creating an AcceptInviteEffect."""
        effect = AcceptInviteEffect(
            agent=AgentName("Sage"),
            conversation_id=ConversationId("conv-001"),
        )
        assert effect.type == "accept_invite"
        assert effect.agent == "Sage"


class TestDeclineInviteEffect:
    """Tests for DeclineInviteEffect."""

    def test_creation(self):
        """Test creating a DeclineInviteEffect."""
        effect = DeclineInviteEffect(
            agent=AgentName("Sage"),
            conversation_id=ConversationId("conv-001"),
        )
        assert effect.type == "decline_invite"


class TestExpireInviteEffect:
    """Tests for ExpireInviteEffect."""

    def test_creation(self):
        """Test creating an ExpireInviteEffect."""
        effect = ExpireInviteEffect(
            conversation_id=ConversationId("conv-001"),
            invitee=AgentName("Sage"),
        )
        assert effect.type == "expire_invite"


class TestJoinConversationEffect:
    """Tests for JoinConversationEffect."""

    def test_creation(self):
        """Test creating a JoinConversationEffect."""
        effect = JoinConversationEffect(
            agent=AgentName("River"),
            conversation_id=ConversationId("conv-001"),
        )
        assert effect.type == "join_conversation"


class TestLeaveConversationEffect:
    """Tests for LeaveConversationEffect."""

    def test_creation(self):
        """Test creating a LeaveConversationEffect."""
        effect = LeaveConversationEffect(
            agent=AgentName("River"),
            conversation_id=ConversationId("conv-001"),
        )
        assert effect.type == "leave_conversation"


class TestMoveConversationEffect:
    """Tests for MoveConversationEffect."""

    def test_creation(self):
        """Test creating a MoveConversationEffect."""
        effect = MoveConversationEffect(
            agent=AgentName("Ember"),
            conversation_id=ConversationId("conv-001"),
            to_location=LocationId("garden"),
        )
        assert effect.type == "move_conversation"
        assert effect.agent == "Ember"
        assert effect.conversation_id == "conv-001"
        assert effect.to_location == "garden"

    def test_immutability(self):
        """Test effect is frozen."""
        effect = MoveConversationEffect(
            agent=AgentName("Ember"),
            conversation_id=ConversationId("conv-001"),
            to_location=LocationId("garden"),
        )
        with pytest.raises(ValidationError):
            effect.to_location = LocationId("library")  # type: ignore

    def test_serialization_roundtrip(self):
        """Test serialization and deserialization."""
        effect = MoveConversationEffect(
            agent=AgentName("Ember"),
            conversation_id=ConversationId("conv-001"),
            to_location=LocationId("garden"),
        )
        data = effect.model_dump()
        restored = MoveConversationEffect.model_validate(data)
        assert restored == effect


class TestAddConversationTurnEffect:
    """Tests for AddConversationTurnEffect."""

    def test_creation(self):
        """Test creating an AddConversationTurnEffect."""
        effect = AddConversationTurnEffect(
            conversation_id=ConversationId("conv-001"),
            speaker=AgentName("Ember"),
            narrative="I think we should explore the garden.",
        )
        assert effect.type == "add_conversation_turn"
        assert effect.narrative == "I think we should explore the garden."


class TestSetNextSpeakerEffect:
    """Tests for SetNextSpeakerEffect."""

    def test_creation(self):
        """Test creating a SetNextSpeakerEffect."""
        effect = SetNextSpeakerEffect(
            conversation_id=ConversationId("conv-001"),
            speaker=AgentName("Sage"),
        )
        assert effect.type == "set_next_speaker"
        assert effect.speaker == "Sage"


class TestEndConversationEffect:
    """Tests for EndConversationEffect."""

    def test_creation(self):
        """Test creating an EndConversationEffect."""
        effect = EndConversationEffect(
            conversation_id=ConversationId("conv-001"),
            reason="All participants left",
        )
        assert effect.type == "end_conversation"
        assert effect.reason == "All participants left"


class TestEffectDiscriminatedUnion:
    """Tests for the Effect discriminated union type."""

    def test_parse_move_agent_effect(self):
        """Test parsing MoveAgentEffect from JSON."""
        data = {
            "type": "move_agent",
            "agent": "Ember",
            "from_location": "workshop",
            "to_location": "garden",
        }
        effect = EffectAdapter.validate_python(data)
        assert isinstance(effect, MoveAgentEffect)

    def test_parse_update_mood_effect(self):
        """Test parsing UpdateMoodEffect from JSON."""
        data = {
            "type": "update_mood",
            "agent": "Sage",
            "mood": "contemplative",
        }
        effect = EffectAdapter.validate_python(data)
        assert isinstance(effect, UpdateMoodEffect)

    def test_parse_agent_sleep_effect(self):
        """Test parsing AgentSleepEffect from JSON."""
        data = {
            "type": "agent_sleep",
            "agent": "Luna",
        }
        effect = EffectAdapter.validate_python(data)
        assert isinstance(effect, AgentSleepEffect)

    def test_parse_invite_effect(self):
        """Test parsing InviteToConversationEffect from JSON."""
        data = {
            "type": "invite_to_conversation",
            "inviter": "Ember",
            "invitee": "Sage",
            "location": "workshop",
            "privacy": "private",
        }
        effect = EffectAdapter.validate_python(data)
        assert isinstance(effect, InviteToConversationEffect)

    def test_all_effect_types_have_unique_discriminators(self):
        """Test all effect types have unique type discriminators."""
        effect_types = [
            MoveAgentEffect,
            UpdateMoodEffect,
            UpdateEnergyEffect,
            RecordActionEffect,
            AgentSleepEffect,
            AgentWakeEffect,
            InviteToConversationEffect,
            AcceptInviteEffect,
            DeclineInviteEffect,
            ExpireInviteEffect,
            JoinConversationEffect,
            LeaveConversationEffect,
            MoveConversationEffect,
            AddConversationTurnEffect,
            SetNextSpeakerEffect,
            EndConversationEffect,
        ]

        discriminators = set()
        for cls in effect_types:
            # Get the default value of the 'type' field
            type_value = cls.model_fields["type"].default
            assert type_value not in discriminators, f"Duplicate type: {type_value}"
            discriminators.add(type_value)

        assert len(discriminators) == 16
