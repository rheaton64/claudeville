"""Tests for engine.runtime.phases.apply_effects module."""

import pytest
from datetime import datetime

from engine.domain import (
    AgentName,
    LocationId,
    ConversationId,
    AgentSnapshot,
    Conversation,
    Invitation,
    MoveAgentEffect,
    UpdateMoodEffect,
    UpdateEnergyEffect,
    RecordActionEffect,
    AgentSleepEffect,
    AgentWakeEffect,
    InviteToConversationEffect,
    AcceptInviteEffect,
    DeclineInviteEffect,
    JoinConversationEffect,
    LeaveConversationEffect,
    MoveConversationEffect,
    AddConversationTurnEffect,
    SetNextSpeakerEffect,
    EndConversationEffect,
    ConversationEndingSeenEffect,
    AgentMovedEvent,
    AgentMoodChangedEvent,
    AgentEnergyChangedEvent,
    AgentActionEvent,
    AgentSleptEvent,
    AgentWokeEvent,
    ConversationInvitedEvent,
    ConversationInviteAcceptedEvent,
    ConversationInviteDeclinedEvent,
    ConversationInviteExpiredEvent,
    ConversationStartedEvent,
    ConversationJoinedEvent,
    ConversationLeftEvent,
    ConversationTurnEvent,
    ConversationMovedEvent,
    ConversationEndedEvent,
    ConversationEndingUnseenEvent,
    ConversationEndingSeenEvent,
    UnseenConversationEnding,
)
from engine.runtime.context import TickContext
from engine.runtime.phases import ApplyEffectsPhase


class TestApplyEffectsPhaseBasics:
    """Basic tests for ApplyEffectsPhase."""

    @pytest.mark.asyncio
    async def test_phase_name(self):
        """Test phase has correct name."""
        phase = ApplyEffectsPhase()

        assert phase.name == "apply_effects"

    @pytest.mark.asyncio
    async def test_empty_effects(
        self,
        tick_context: TickContext,
    ):
        """Test phase with no effects produces no events."""
        phase = ApplyEffectsPhase()

        result = await phase.execute(tick_context)

        assert len(result.events) == 0


class TestMoveAgentEffect:
    """Tests for MoveAgentEffect processing."""

    @pytest.mark.asyncio
    async def test_apply_move(
        self,
        tick_context: TickContext,
        
    ):
        """Test applying move effect."""
        effect = MoveAgentEffect(
            agent=AgentName("Ember"),
            from_location=LocationId("workshop"),
            to_location=LocationId("garden"),
        )
        ctx = tick_context.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # Check event produced
        move_events = [e for e in result.events if isinstance(e, AgentMovedEvent)]
        assert len(move_events) == 1
        assert move_events[0].agent == AgentName("Ember")
        assert move_events[0].to_location == LocationId("garden")

        # Check state updated
        assert result.agents[AgentName("Ember")].location == LocationId("garden")


class TestUpdateMoodEffect:
    """Tests for UpdateMoodEffect processing."""

    @pytest.mark.asyncio
    async def test_apply_mood(
        self,
        tick_context: TickContext,
        
    ):
        """Test applying mood update."""
        effect = UpdateMoodEffect(
            agent=AgentName("Ember"),
            mood="excited",
        )
        ctx = tick_context.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # Check event
        mood_events = [e for e in result.events if isinstance(e, AgentMoodChangedEvent)]
        assert len(mood_events) == 1
        assert mood_events[0].new_mood == "excited"

        # Check state
        assert result.agents[AgentName("Ember")].mood == "excited"


class TestUpdateEnergyEffect:
    """Tests for UpdateEnergyEffect processing."""

    @pytest.mark.asyncio
    async def test_apply_energy(
        self,
        tick_context: TickContext,
        
    ):
        """Test applying energy update."""
        effect = UpdateEnergyEffect(
            agent=AgentName("Ember"),
            energy=50,
        )
        ctx = tick_context.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # Check event
        energy_events = [e for e in result.events if isinstance(e, AgentEnergyChangedEvent)]
        assert len(energy_events) == 1
        assert energy_events[0].new_energy == 50

        # Check state
        assert result.agents[AgentName("Ember")].energy == 50

    @pytest.mark.asyncio
    async def test_energy_clamped_to_100(
        self,
        tick_context: TickContext,
        
    ):
        """Test energy is clamped to max 100."""
        effect = UpdateEnergyEffect(
            agent=AgentName("Ember"),
            energy=150,
        )
        ctx = tick_context.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        assert result.agents[AgentName("Ember")].energy == 100

    @pytest.mark.asyncio
    async def test_energy_clamped_to_0(
        self,
        tick_context: TickContext,
        
    ):
        """Test energy is clamped to min 0."""
        effect = UpdateEnergyEffect(
            agent=AgentName("Ember"),
            energy=-50,
        )
        ctx = tick_context.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        assert result.agents[AgentName("Ember")].energy == 0


class TestRecordActionEffect:
    """Tests for RecordActionEffect processing."""

    @pytest.mark.asyncio
    async def test_apply_action(
        self,
        tick_context: TickContext,
        
    ):
        """Test recording an action."""
        effect = RecordActionEffect(
            agent=AgentName("Ember"),
            description="painted a landscape",
        )
        ctx = tick_context.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # Check event
        action_events = [e for e in result.events if isinstance(e, AgentActionEvent)]
        assert len(action_events) == 1
        assert action_events[0].description == "painted a landscape"


class TestSleepEffects:
    """Tests for sleep-related effects."""

    @pytest.mark.asyncio
    async def test_apply_sleep(
        self,
        tick_context: TickContext,
        
    ):
        """Test applying sleep effect."""
        effect = AgentSleepEffect(agent=AgentName("Ember"))
        ctx = tick_context.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # Check event
        sleep_events = [e for e in result.events if isinstance(e, AgentSleptEvent)]
        assert len(sleep_events) == 1

        # Check state
        agent = result.agents[AgentName("Ember")]
        assert agent.is_sleeping is True
        assert agent.sleep_started_tick == tick_context.tick

    @pytest.mark.asyncio
    async def test_apply_wake(
        self,
        tick_context: TickContext,
        
        sleeping_agent: AgentSnapshot,
    ):
        """Test applying wake effect."""
        ctx = tick_context.model_copy(
            update={"agents": {**tick_context.agents, sleeping_agent.name: sleeping_agent}}
        )

        effect = AgentWakeEffect(agent=sleeping_agent.name, reason="visitor_arrived")
        ctx = ctx.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # Check event
        wake_events = [e for e in result.events if isinstance(e, AgentWokeEvent)]
        assert len(wake_events) == 1
        assert wake_events[0].reason == "visitor_arrived"

        # Check state
        agent = result.agents[sleeping_agent.name]
        assert agent.is_sleeping is False
        assert agent.sleep_started_tick is None


class TestConversationInviteEffects:
    """Tests for conversation invite effects."""

    @pytest.mark.asyncio
    async def test_apply_invite(
        self,
        tick_context: TickContext,
        
    ):
        """Test creating an invitation."""
        effect = InviteToConversationEffect(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            location=LocationId("workshop"),
            privacy="private",
        )
        ctx = tick_context.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # Check event
        invite_events = [e for e in result.events if isinstance(e, ConversationInvitedEvent)]
        assert len(invite_events) == 1
        assert invite_events[0].inviter == AgentName("Ember")
        assert invite_events[0].invitee == AgentName("Sage")

        # Check invite added to context
        assert AgentName("Sage") in result.pending_invites

    @pytest.mark.asyncio
    async def test_apply_accept_creates_conversation(
        self,
        tick_context: TickContext,
        
        sample_invitation: Invitation,
    ):
        """Test accepting an invitation creates a conversation."""
        ctx = tick_context.with_added_invite(sample_invitation)
        # Also add to service

        effect = AcceptInviteEffect(
            agent=sample_invitation.invitee,
            conversation_id=sample_invitation.conversation_id,
        )
        ctx = ctx.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # Check events (accept + start)
        accept_events = [e for e in result.events if isinstance(e, ConversationInviteAcceptedEvent)]
        start_events = [e for e in result.events if isinstance(e, ConversationStartedEvent)]
        assert len(accept_events) == 1
        assert len(start_events) == 1

        # Check conversation created
        assert sample_invitation.conversation_id in result.conversations

        # Check invite removed
        assert sample_invitation.invitee not in result.pending_invites

    @pytest.mark.asyncio
    async def test_apply_decline(
        self,
        tick_context: TickContext,
        
        sample_invitation: Invitation,
    ):
        """Test declining an invitation."""
        ctx = tick_context.with_added_invite(sample_invitation)

        effect = DeclineInviteEffect(
            agent=sample_invitation.invitee,
            conversation_id=sample_invitation.conversation_id,
        )
        ctx = ctx.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # Check event
        decline_events = [e for e in result.events if isinstance(e, ConversationInviteDeclinedEvent)]
        assert len(decline_events) == 1

        # Check invite removed
        assert sample_invitation.invitee not in result.pending_invites


class TestConversationParticipationEffects:
    """Tests for conversation participation effects."""

    @pytest.mark.asyncio
    async def test_apply_join(
        self,
        tick_context: TickContext,
        
        public_conversation: Conversation,
    ):
        """Test joining a conversation."""
        ctx = tick_context.model_copy(
            update={"conversations": {public_conversation.id: public_conversation}}
        )

        effect = JoinConversationEffect(
            agent=AgentName("Ember"),
            conversation_id=public_conversation.id,
        )
        ctx = ctx.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # Check event
        join_events = [e for e in result.events if isinstance(e, ConversationJoinedEvent)]
        assert len(join_events) == 1

        # Check participant added
        conv = result.conversations[public_conversation.id]
        assert AgentName("Ember") in conv.participants

    @pytest.mark.asyncio
    async def test_apply_leave_with_remaining_participants(
        self,
        tick_context: TickContext,
        
        base_datetime: datetime,
    ):
        """Test leaving a conversation when others remain."""
        # Create 3-person conversation
        conv = Conversation(
            id=ConversationId("conv-test"),
            location=LocationId("workshop"),
            privacy="public",
            participants=frozenset([
                AgentName("Ember"),
                AgentName("Sage"),
                AgentName("River"),
            ]),
            history=(),
            started_at_tick=1,
            created_by=AgentName("Ember"),
        )

        ctx = tick_context.model_copy(
            update={"conversations": {conv.id: conv}}
        )

        effect = LeaveConversationEffect(
            agent=AgentName("Ember"),
            conversation_id=conv.id,
        )
        ctx = ctx.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # Check left event
        left_events = [e for e in result.events if isinstance(e, ConversationLeftEvent)]
        assert len(left_events) == 1

        # Conversation should still exist
        assert conv.id in result.conversations
        assert AgentName("Ember") not in result.conversations[conv.id].participants

    @pytest.mark.asyncio
    async def test_apply_leave_ends_conversation(
        self,
        tick_context: TickContext,
        
        sample_conversation: Conversation,
    ):
        """Test leaving a 2-person conversation ends it."""
        ctx = tick_context.model_copy(
            update={"conversations": {sample_conversation.id: sample_conversation}}
        )

        effect = LeaveConversationEffect(
            agent=AgentName("Ember"),
            conversation_id=sample_conversation.id,
        )
        ctx = ctx.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # Check both left and ended events
        left_events = [e for e in result.events if isinstance(e, ConversationLeftEvent)]
        ended_events = [e for e in result.events if isinstance(e, ConversationEndedEvent)]
        assert len(left_events) == 1
        assert len(ended_events) == 1

        # Conversation should be removed
        assert sample_conversation.id not in result.conversations


class TestConversationTurnEffects:
    """Tests for conversation turn effects."""

    @pytest.mark.asyncio
    async def test_apply_add_turn(
        self,
        tick_context: TickContext,
        
        sample_conversation: Conversation,
    ):
        """Test adding a turn to a conversation."""
        ctx = tick_context.model_copy(
            update={"conversations": {sample_conversation.id: sample_conversation}}
        )

        effect = AddConversationTurnEffect(
            conversation_id=sample_conversation.id,
            speaker=AgentName("Sage"),
            narrative="Hello, Ember!",
        )
        ctx = ctx.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # Check event
        turn_events = [e for e in result.events if isinstance(e, ConversationTurnEvent)]
        assert len(turn_events) == 1
        assert turn_events[0].speaker == AgentName("Sage")
        assert turn_events[0].narrative == "Hello, Ember!"

        # Check history updated
        conv = result.conversations[sample_conversation.id]
        assert len(conv.history) == len(sample_conversation.history) + 1

    @pytest.mark.asyncio
    async def test_apply_set_next_speaker(
        self,
        tick_context: TickContext,
        
        sample_conversation: Conversation,
    ):
        """Test setting next speaker."""
        ctx = tick_context.model_copy(
            update={"conversations": {sample_conversation.id: sample_conversation}}
        )

        effect = SetNextSpeakerEffect(
            conversation_id=sample_conversation.id,
            speaker=AgentName("Ember"),
        )
        ctx = ctx.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # Check state
        conv = result.conversations[sample_conversation.id]
        assert conv.next_speaker == AgentName("Ember")


class TestInviteToExistingConversation:
    """Tests for inviting someone to join an existing conversation."""

    @pytest.mark.asyncio
    async def test_invite_uses_existing_conversation_id(
        self,
        tick_context: TickContext,
        sample_conversation: Conversation,
    ):
        """When inviter is in a conversation, invite uses that conversation's ID."""
        # Ember is in a conversation with Sage
        ctx = tick_context.with_updated_conversation(sample_conversation)

        # Ember invites River - should use existing conversation ID
        effect = InviteToConversationEffect(
            inviter=AgentName("Ember"),
            invitee=AgentName("River"),
            location=sample_conversation.location,
            privacy="public",
        )
        ctx = ctx.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # Check invite event uses existing conversation ID
        invite_events = [e for e in result.events if isinstance(e, ConversationInvitedEvent)]
        assert len(invite_events) == 1
        assert invite_events[0].conversation_id == sample_conversation.id

        # Check pending invite uses existing conversation ID
        assert AgentName("River") in result.pending_invites
        assert result.pending_invites[AgentName("River")].conversation_id == sample_conversation.id

    @pytest.mark.asyncio
    async def test_invite_creates_new_id_when_not_in_conversation(
        self,
        tick_context: TickContext,
    ):
        """When inviter is not in a conversation, creates a new conversation ID."""
        effect = InviteToConversationEffect(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            location=LocationId("workshop"),
            privacy="public",
        )
        ctx = tick_context.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # Check invite event created with new ID
        invite_events = [e for e in result.events if isinstance(e, ConversationInvitedEvent)]
        assert len(invite_events) == 1
        # New ID should be 8 characters
        assert len(invite_events[0].conversation_id) == 8

    @pytest.mark.asyncio
    async def test_accept_invite_to_existing_conversation_joins(
        self,
        tick_context: TickContext,
        sample_conversation: Conversation,
        base_datetime: datetime,
    ):
        """Accepting invite to existing conversation adds participant."""
        # Setup: Ember+Sage in conversation, River has pending invite
        ctx = tick_context.with_updated_conversation(sample_conversation)

        invite = Invitation(
            conversation_id=sample_conversation.id,
            inviter=AgentName("Ember"),
            invitee=AgentName("River"),
            location=sample_conversation.location,
            privacy="public",
            created_at_tick=0,
            expires_at_tick=3,
            invited_at=base_datetime,
        )
        ctx = ctx.with_added_invite(invite)

        # River accepts the invite
        effect = AcceptInviteEffect(
            agent=AgentName("River"),
            conversation_id=sample_conversation.id,
        )
        ctx = ctx.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # Check joined event (not started event)
        joined_events = [e for e in result.events if isinstance(e, ConversationJoinedEvent)]
        started_events = [e for e in result.events if isinstance(e, ConversationStartedEvent)]

        assert len(joined_events) == 1
        assert joined_events[0].agent == "River"
        assert len(started_events) == 0  # No new conversation started

        # Check River is now a participant
        conv = result.conversations[sample_conversation.id]
        assert AgentName("River") in conv.participants
        assert AgentName("Ember") in conv.participants
        assert AgentName("Sage") in conv.participants


class TestInviteExpiry:
    """Tests for automatic invite expiry."""

    @pytest.mark.asyncio
    async def test_expired_invite_removed(
        self,
        tick_context: TickContext,
        
        base_datetime: datetime,
    ):
        """Test expired invites are automatically removed."""
        # Create an invite that expires at tick 1 (current tick)
        expired_invite = Invitation(
            conversation_id=ConversationId("conv-expired"),
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            location=LocationId("workshop"),
            privacy="private",
            created_at_tick=0,
            expires_at_tick=1,  # Same as tick_context.tick
            invited_at=base_datetime,
        )

        ctx = tick_context.with_added_invite(expired_invite)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # Check expired event
        expired_events = [e for e in result.events if isinstance(e, ConversationInviteExpiredEvent)]
        assert len(expired_events) == 1

        # Check invite removed
        assert expired_invite.invitee not in result.pending_invites


class TestAcceptInviteFirstMessage:
    """Tests for AcceptInviteEffect with first_message."""

    @pytest.mark.asyncio
    async def test_accept_with_first_message_creates_turn(
        self,
        tick_context: TickContext,
        sample_invitation: Invitation,
    ):
        """AcceptInviteEffect with first_message creates ConversationTurnEvent."""
        ctx = tick_context.with_added_invite(sample_invitation)

        effect = AcceptInviteEffect(
            agent=sample_invitation.invitee,
            conversation_id=sample_invitation.conversation_id,
            first_message="Hello! I'm glad you invited me.",
        )
        ctx = ctx.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # Check turn event was created
        turn_events = [e for e in result.events if isinstance(e, ConversationTurnEvent)]
        assert len(turn_events) == 1
        assert turn_events[0].speaker == sample_invitation.invitee
        assert turn_events[0].narrative == "Hello! I'm glad you invited me."
        assert turn_events[0].is_departure is False

    @pytest.mark.asyncio
    async def test_accept_without_first_message_no_turn(
        self,
        tick_context: TickContext,
        sample_invitation: Invitation,
    ):
        """AcceptInviteEffect without first_message doesn't create turn."""
        ctx = tick_context.with_added_invite(sample_invitation)

        effect = AcceptInviteEffect(
            agent=sample_invitation.invitee,
            conversation_id=sample_invitation.conversation_id,
        )
        ctx = ctx.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # Check no turn event (only accept + start events)
        turn_events = [e for e in result.events if isinstance(e, ConversationTurnEvent)]
        assert len(turn_events) == 0


class TestJoinConversationFirstMessage:
    """Tests for JoinConversationEffect with first_message."""

    @pytest.mark.asyncio
    async def test_join_with_first_message_creates_turn(
        self,
        tick_context: TickContext,
        public_conversation: Conversation,
    ):
        """JoinConversationEffect with first_message creates ConversationTurnEvent."""
        ctx = tick_context.model_copy(
            update={"conversations": {public_conversation.id: public_conversation}}
        )

        effect = JoinConversationEffect(
            agent=AgentName("Ember"),
            conversation_id=public_conversation.id,
            first_message="Mind if I join you?",
        )
        ctx = ctx.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # Check turn event was created
        turn_events = [e for e in result.events if isinstance(e, ConversationTurnEvent)]
        assert len(turn_events) == 1
        assert turn_events[0].speaker == AgentName("Ember")
        assert turn_events[0].narrative == "Mind if I join you?"
        assert turn_events[0].is_departure is False

    @pytest.mark.asyncio
    async def test_join_without_first_message_no_turn(
        self,
        tick_context: TickContext,
        public_conversation: Conversation,
    ):
        """JoinConversationEffect without first_message doesn't create turn."""
        ctx = tick_context.model_copy(
            update={"conversations": {public_conversation.id: public_conversation}}
        )

        effect = JoinConversationEffect(
            agent=AgentName("Ember"),
            conversation_id=public_conversation.id,
        )
        ctx = ctx.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # Check no turn event
        turn_events = [e for e in result.events if isinstance(e, ConversationTurnEvent)]
        assert len(turn_events) == 0


class TestLeaveConversationLastMessage:
    """Tests for LeaveConversationEffect with last_message."""

    @pytest.mark.asyncio
    async def test_leave_with_last_message_creates_turn(
        self,
        tick_context: TickContext,
        base_datetime: datetime,
    ):
        """LeaveConversationEffect with last_message creates ConversationTurnEvent."""
        # Create 3-person conversation so it doesn't end
        conv = Conversation(
            id=ConversationId("conv-test"),
            location=LocationId("workshop"),
            privacy="public",
            participants=frozenset([
                AgentName("Ember"),
                AgentName("Sage"),
                AgentName("River"),
            ]),
            history=(),
            started_at_tick=1,
            created_by=AgentName("Ember"),
        )
        ctx = tick_context.model_copy(
            update={"conversations": {conv.id: conv}}
        )

        effect = LeaveConversationEffect(
            agent=AgentName("Ember"),
            conversation_id=conv.id,
            last_message="I need to go now. Goodbye!",
        )
        ctx = ctx.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # Check turn event was created with is_departure=True
        turn_events = [e for e in result.events if isinstance(e, ConversationTurnEvent)]
        assert len(turn_events) == 1
        assert turn_events[0].speaker == AgentName("Ember")
        assert turn_events[0].narrative == "I need to go now. Goodbye!"
        assert turn_events[0].is_departure is True

    @pytest.mark.asyncio
    async def test_leave_without_last_message_no_turn(
        self,
        tick_context: TickContext,
        base_datetime: datetime,
    ):
        """LeaveConversationEffect without last_message doesn't create turn."""
        conv = Conversation(
            id=ConversationId("conv-test"),
            location=LocationId("workshop"),
            privacy="public",
            participants=frozenset([
                AgentName("Ember"),
                AgentName("Sage"),
                AgentName("River"),
            ]),
            history=(),
            started_at_tick=1,
            created_by=AgentName("Ember"),
        )
        ctx = tick_context.model_copy(
            update={"conversations": {conv.id: conv}}
        )

        effect = LeaveConversationEffect(
            agent=AgentName("Ember"),
            conversation_id=conv.id,
        )
        ctx = ctx.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # Check no turn event
        turn_events = [e for e in result.events if isinstance(e, ConversationTurnEvent)]
        assert len(turn_events) == 0

    @pytest.mark.asyncio
    async def test_leave_turn_before_left_event(
        self,
        tick_context: TickContext,
        base_datetime: datetime,
    ):
        """ConversationTurnEvent comes before ConversationLeftEvent."""
        conv = Conversation(
            id=ConversationId("conv-test"),
            location=LocationId("workshop"),
            privacy="public",
            participants=frozenset([
                AgentName("Ember"),
                AgentName("Sage"),
                AgentName("River"),
            ]),
            history=(),
            started_at_tick=1,
            created_by=AgentName("Ember"),
        )
        ctx = tick_context.model_copy(
            update={"conversations": {conv.id: conv}}
        )

        effect = LeaveConversationEffect(
            agent=AgentName("Ember"),
            conversation_id=conv.id,
            last_message="Farewell!",
        )
        ctx = ctx.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # Find indices
        turn_idx = next(i for i, e in enumerate(result.events) if isinstance(e, ConversationTurnEvent))
        left_idx = next(i for i, e in enumerate(result.events) if isinstance(e, ConversationLeftEvent))

        # Turn should come before left
        assert turn_idx < left_idx


class TestConversationEndingUnseen:
    """Tests for ConversationEndingUnseenEvent generation."""

    @pytest.mark.asyncio
    async def test_leave_2person_with_message_creates_unseen_event(
        self,
        tick_context: TickContext,
        sample_conversation: Conversation,
    ):
        """Leaving 2-person conv with last_message creates ConversationEndingUnseenEvent."""
        ctx = tick_context.model_copy(
            update={"conversations": {sample_conversation.id: sample_conversation}}
        )

        effect = LeaveConversationEffect(
            agent=AgentName("Ember"),
            conversation_id=sample_conversation.id,
            last_message="I must go now. Take care!",
        )
        ctx = ctx.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # Check unseen event was created for remaining participant
        unseen_events = [e for e in result.events if isinstance(e, ConversationEndingUnseenEvent)]
        assert len(unseen_events) == 1
        assert unseen_events[0].agent == AgentName("Sage")  # The remaining participant
        assert unseen_events[0].other_participant == AgentName("Ember")  # Who left
        assert unseen_events[0].final_message == "I must go now. Take care!"

    @pytest.mark.asyncio
    async def test_leave_2person_without_message_no_unseen_event(
        self,
        tick_context: TickContext,
        sample_conversation: Conversation,
    ):
        """Leaving 2-person conv without last_message doesn't create unseen event."""
        ctx = tick_context.model_copy(
            update={"conversations": {sample_conversation.id: sample_conversation}}
        )

        effect = LeaveConversationEffect(
            agent=AgentName("Ember"),
            conversation_id=sample_conversation.id,
        )
        ctx = ctx.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # No unseen event
        unseen_events = [e for e in result.events if isinstance(e, ConversationEndingUnseenEvent)]
        assert len(unseen_events) == 0

    @pytest.mark.asyncio
    async def test_leave_3person_no_unseen_event(
        self,
        tick_context: TickContext,
        base_datetime: datetime,
    ):
        """Leaving 3-person conv doesn't create ConversationEndingUnseenEvent."""
        conv = Conversation(
            id=ConversationId("conv-test"),
            location=LocationId("workshop"),
            privacy="public",
            participants=frozenset([
                AgentName("Ember"),
                AgentName("Sage"),
                AgentName("River"),
            ]),
            history=(),
            started_at_tick=1,
            created_by=AgentName("Ember"),
        )
        ctx = tick_context.model_copy(
            update={"conversations": {conv.id: conv}}
        )

        effect = LeaveConversationEffect(
            agent=AgentName("Ember"),
            conversation_id=conv.id,
            last_message="Goodbye everyone!",
        )
        ctx = ctx.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # No unseen event - conversation continues
        unseen_events = [e for e in result.events if isinstance(e, ConversationEndingUnseenEvent)]
        assert len(unseen_events) == 0

        # Conversation should still exist
        assert conv.id in result.conversations


class TestConversationEndingSeenEffect:
    """Tests for ConversationEndingSeenEffect processing."""

    @pytest.mark.asyncio
    async def test_seen_effect_creates_seen_event(
        self,
        tick_context: TickContext,
    ):
        """ConversationEndingSeenEffect creates ConversationEndingSeenEvent."""
        # Add unseen ending to context
        ending = UnseenConversationEnding(
            conversation_id=ConversationId("conv-ended"),
            other_participant=AgentName("Sage"),
            final_message="Goodbye!",
            ended_at_tick=0,
        )
        ctx = tick_context.model_copy(
            update={"unseen_endings": {AgentName("Ember"): [ending]}}
        )

        effect = ConversationEndingSeenEffect(
            agent=AgentName("Ember"),
            conversation_id=ConversationId("conv-ended"),
        )
        ctx = ctx.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # Check seen event was created
        seen_events = [e for e in result.events if isinstance(e, ConversationEndingSeenEvent)]
        assert len(seen_events) == 1
        assert seen_events[0].agent == AgentName("Ember")
        assert seen_events[0].conversation_id == ConversationId("conv-ended")


class TestMoveConversationEffect:
    """Tests for MoveConversationEffect processing."""

    @pytest.mark.asyncio
    async def test_apply_move_conversation_moves_all_participants(
        self,
        tick_context: TickContext,
        sample_conversation: Conversation,
    ):
        """Test moving a conversation moves all participants."""
        # Update sample_agent to be at workshop (same as conversation)
        ctx = tick_context.model_copy(
            update={"conversations": {sample_conversation.id: sample_conversation}}
        )

        effect = MoveConversationEffect(
            agent=AgentName("Ember"),
            conversation_id=sample_conversation.id,
            to_location=LocationId("garden"),
        )
        ctx = ctx.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # Check move events for each participant
        move_events = [e for e in result.events if isinstance(e, AgentMovedEvent)]
        assert len(move_events) == 2  # Ember and Sage

        # Check all participants moved to garden
        moved_agents = {e.agent for e in move_events}
        assert AgentName("Ember") in moved_agents
        assert AgentName("Sage") in moved_agents

        for event in move_events:
            assert event.to_location == LocationId("garden")

        # Check agent state updated
        assert result.agents[AgentName("Ember")].location == LocationId("garden")
        assert result.agents[AgentName("Sage")].location == LocationId("garden")

    @pytest.mark.asyncio
    async def test_apply_move_conversation_creates_moved_event(
        self,
        tick_context: TickContext,
        sample_conversation: Conversation,
    ):
        """Test moving a conversation creates ConversationMovedEvent."""
        ctx = tick_context.model_copy(
            update={"conversations": {sample_conversation.id: sample_conversation}}
        )

        effect = MoveConversationEffect(
            agent=AgentName("Ember"),
            conversation_id=sample_conversation.id,
            to_location=LocationId("garden"),
        )
        ctx = ctx.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # Check conversation moved event
        moved_events = [e for e in result.events if isinstance(e, ConversationMovedEvent)]
        assert len(moved_events) == 1
        assert moved_events[0].conversation_id == sample_conversation.id
        assert moved_events[0].initiated_by == AgentName("Ember")
        assert moved_events[0].from_location == LocationId("workshop")
        assert moved_events[0].to_location == LocationId("garden")
        assert set(moved_events[0].participants) == {AgentName("Ember"), AgentName("Sage")}

    @pytest.mark.asyncio
    async def test_apply_move_conversation_updates_conversation_location(
        self,
        tick_context: TickContext,
        sample_conversation: Conversation,
    ):
        """Test moving a conversation updates the conversation's location."""
        ctx = tick_context.model_copy(
            update={"conversations": {sample_conversation.id: sample_conversation}}
        )

        effect = MoveConversationEffect(
            agent=AgentName("Ember"),
            conversation_id=sample_conversation.id,
            to_location=LocationId("garden"),
        )
        ctx = ctx.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # Check conversation location updated
        conv = result.conversations[sample_conversation.id]
        assert conv.location == LocationId("garden")

    @pytest.mark.asyncio
    async def test_apply_move_nonexistent_conversation(
        self,
        tick_context: TickContext,
    ):
        """Test moving a non-existent conversation does nothing."""
        effect = MoveConversationEffect(
            agent=AgentName("Ember"),
            conversation_id=ConversationId("nonexistent"),
            to_location=LocationId("garden"),
        )
        ctx = tick_context.with_effect(effect)

        phase = ApplyEffectsPhase()
        result = await phase.execute(ctx)

        # No events produced
        assert len(result.events) == 0
