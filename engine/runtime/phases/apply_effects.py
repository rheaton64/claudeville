"""
ApplyEffectsPhase - converts effects to domain events.

This phase processes all accumulated effects:
1. Converts each effect to one or more domain events
2. Updates context state (for subsequent effect processing within the tick)
3. Handles conversation lifecycle (create, end)
4. Handles invite expiry

NOTE: This phase does NOT directly mutate services. It only produces events.
The EventStore._apply_event method is the single source of truth for state
updates. After events are committed, VillageEngine._hydrate_from_snapshot()
syncs services from the updated snapshot.
"""

import logging
from uuid import uuid4

from engine.domain import (
    AgentName,
    AgentSnapshot,
    LocationId,
    ConversationId,
    Conversation,
    ConversationTurn,
    Invitation,
    INVITE_EXPIRY_TICKS,
    TimePeriod,
    Effect,
    DomainEvent,
    # Effects
    MoveAgentEffect,
    UpdateMoodEffect,
    UpdateEnergyEffect,
    RecordActionEffect,
    AgentSleepEffect,
    AgentWakeEffect,
    UpdateLastActiveTickEffect,
    UpdateSessionIdEffect,
    InviteToConversationEffect,
    AcceptInviteEffect,
    DeclineInviteEffect,
    ExpireInviteEffect,
    JoinConversationEffect,
    LeaveConversationEffect,
    AddConversationTurnEffect,
    SetNextSpeakerEffect,
    EndConversationEffect,
    # Events
    AgentMovedEvent,
    AgentMoodChangedEvent,
    AgentEnergyChangedEvent,
    AgentActionEvent,
    AgentSleptEvent,
    AgentWokeEvent,
    AgentLastActiveTickUpdatedEvent,
    AgentSessionIdUpdatedEvent,
    ConversationInvitedEvent,
    ConversationInviteAcceptedEvent,
    ConversationInviteDeclinedEvent,
    ConversationInviteExpiredEvent,
    ConversationStartedEvent,
    ConversationJoinedEvent,
    ConversationLeftEvent,
    ConversationTurnEvent,
    ConversationNextSpeakerSetEvent,
    ConversationEndedEvent,
)
from engine.runtime.context import TickContext
from engine.runtime.pipeline import BasePhase


logger = logging.getLogger(__name__)


class ApplyEffectsPhase(BasePhase):
    """
    Apply all accumulated effects to produce domain events.

    This phase:
    - Processes effects in order
    - Creates domain events for each effect
    - Updates context state (for subsequent effect processing)
    - Handles conversation lifecycle (create on accept, end on leave)

    State updates happen through events only. EventStore._apply_event is the
    single source of truth. Services are hydrated from snapshots after events
    are committed.
    """

    async def _execute(self, ctx: TickContext) -> TickContext:
        """Process all effects and produce events."""
        # Delegate to sync implementation
        return self.execute_sync(ctx)

    def execute_sync(self, ctx: TickContext) -> TickContext:
        """
        Synchronous version of execute - for use from non-async contexts.

        Since ApplyEffectsPhase doesn't do any I/O, all work is synchronous.
        This method can be called directly without needing an event loop.
        """
        events: list[DomainEvent] = []
        new_ctx = ctx

        for effect in ctx.effects:
            event_list, new_ctx = self._apply_effect(effect, new_ctx)
            events.extend(event_list)

        # Expire any pending invites that have passed their deadline
        expired_events, new_ctx = self._expire_invites(new_ctx)
        events.extend(expired_events)

        logger.debug(f"Applied {len(ctx.effects)} effects, produced {len(events)} events")
        return new_ctx.with_events(events)

    def _apply_effect(
        self,
        effect: Effect,
        ctx: TickContext,
    ) -> tuple[list[DomainEvent], TickContext]:
        """Apply a single effect and return events + updated context."""
        match effect:
            case MoveAgentEffect():
                return self._apply_move(effect, ctx)
            case UpdateMoodEffect():
                return self._apply_mood(effect, ctx)
            case UpdateEnergyEffect():
                return self._apply_energy(effect, ctx)
            case RecordActionEffect():
                return self._apply_action(effect, ctx)
            case AgentSleepEffect():
                return self._apply_sleep(effect, ctx)
            case AgentWakeEffect():
                return self._apply_wake(effect, ctx)
            case UpdateLastActiveTickEffect():
                return self._apply_last_active_tick(effect, ctx)
            case UpdateSessionIdEffect():
                return self._apply_session_id(effect, ctx)
            case InviteToConversationEffect():
                return self._apply_invite(effect, ctx)
            case AcceptInviteEffect():
                return self._apply_accept(effect, ctx)
            case DeclineInviteEffect():
                return self._apply_decline(effect, ctx)
            case ExpireInviteEffect():
                return self._apply_expire(effect, ctx)
            case JoinConversationEffect():
                return self._apply_join(effect, ctx)
            case LeaveConversationEffect():
                return self._apply_leave(effect, ctx)
            case AddConversationTurnEffect():
                return self._apply_conv_turn(effect, ctx)
            case SetNextSpeakerEffect():
                return self._apply_set_next_speaker(effect, ctx)
            case EndConversationEffect():
                return self._apply_end_conversation(effect, ctx)
            case _:
                logger.warning(f"Unknown effect type: {type(effect)}")
                return [], ctx

    # =========================================================================
    # Agent effects
    # =========================================================================

    def _apply_move(
        self,
        effect: MoveAgentEffect,
        ctx: TickContext,
    ) -> tuple[list[DomainEvent], TickContext]:
        """Apply agent movement."""
        agent = ctx.agents.get(effect.agent)
        if not agent:
            return [], ctx

        # Update agent location
        new_agent = AgentSnapshot(**{
            **agent.model_dump(),
            "location": effect.to_location,
        })

        event = AgentMovedEvent(
            tick=ctx.tick,
            timestamp=ctx.timestamp,
            agent=effect.agent,
            from_location=effect.from_location,
            to_location=effect.to_location,
        )

        return [event], ctx.with_updated_agent(new_agent)

    def _apply_mood(
        self,
        effect: UpdateMoodEffect,
        ctx: TickContext,
    ) -> tuple[list[DomainEvent], TickContext]:
        """Apply mood change."""
        agent = ctx.agents.get(effect.agent)
        if not agent:
            return [], ctx

        old_mood = agent.mood
        new_agent = AgentSnapshot(**{
            **agent.model_dump(),
            "mood": effect.mood,
        })

        event = AgentMoodChangedEvent(
            tick=ctx.tick,
            timestamp=ctx.timestamp,
            agent=effect.agent,
            old_mood=old_mood,
            new_mood=effect.mood,
        )

        return [event], ctx.with_updated_agent(new_agent)

    def _apply_energy(
        self,
        effect: UpdateEnergyEffect,
        ctx: TickContext,
    ) -> tuple[list[DomainEvent], TickContext]:
        """Apply energy change."""
        agent = ctx.agents.get(effect.agent)
        if not agent:
            return [], ctx

        old_energy = agent.energy
        new_energy_value = max(0, min(100, effect.energy))
        if new_energy_value == old_energy:
            return [], ctx

        new_agent = AgentSnapshot(**{
            **agent.model_dump(),
            "energy": new_energy_value,
        })

        event = AgentEnergyChangedEvent(
            tick=ctx.tick,
            timestamp=ctx.timestamp,
            agent=effect.agent,
            old_energy=old_energy,
            new_energy=new_energy_value,
        )

        return [event], ctx.with_updated_agent(new_agent)

    def _apply_action(
        self,
        effect: RecordActionEffect,
        ctx: TickContext,
    ) -> tuple[list[DomainEvent], TickContext]:
        """Record an action (produces event, no state change)."""
        agent = ctx.agents.get(effect.agent)
        if not agent:
            return [], ctx

        event = AgentActionEvent(
            tick=ctx.tick,
            timestamp=ctx.timestamp,
            agent=effect.agent,
            location=agent.location,
            description=effect.description,
        )

        return [event], ctx

    def _apply_sleep(
        self,
        effect: AgentSleepEffect,
        ctx: TickContext,
    ) -> tuple[list[DomainEvent], TickContext]:
        """Apply agent going to sleep."""
        agent = ctx.agents.get(effect.agent)
        if not agent:
            return [], ctx

        new_agent = AgentSnapshot(**{
            **agent.model_dump(),
            "is_sleeping": True,
            "sleep_started_tick": ctx.tick,
            "sleep_started_time_period": ctx.time_snapshot.period,
        })

        event = AgentSleptEvent(
            tick=ctx.tick,
            timestamp=ctx.timestamp,
            agent=effect.agent,
            location=agent.location,
        )

        return [event], ctx.with_updated_agent(new_agent)

    def _apply_wake(
        self,
        effect: AgentWakeEffect,
        ctx: TickContext,
    ) -> tuple[list[DomainEvent], TickContext]:
        """Apply agent waking up."""
        agent = ctx.agents.get(effect.agent)
        if not agent:
            return [], ctx

        new_agent = AgentSnapshot(**{
            **agent.model_dump(),
            "is_sleeping": False,
            "sleep_started_tick": None,
            "sleep_started_time_period": None,
        })

        event = AgentWokeEvent(
            tick=ctx.tick,
            timestamp=ctx.timestamp,
            agent=effect.agent,
            location=agent.location,
            reason=effect.reason or "phase_check",
        )

        return [event], ctx.with_updated_agent(new_agent)

    def _apply_last_active_tick(
        self,
        effect: UpdateLastActiveTickEffect,
        ctx: TickContext,
    ) -> tuple[list[DomainEvent], TickContext]:
        """Update the agent's last active tick."""
        agent = ctx.agents.get(effect.agent)
        if not agent:
            return [], ctx

        old_tick = agent.last_active_tick
        new_tick = ctx.tick
        if new_tick == old_tick:
            return [], ctx

        new_agent = AgentSnapshot(**{
            **agent.model_dump(),
            "last_active_tick": new_tick,
        })

        event = AgentLastActiveTickUpdatedEvent(
            tick=ctx.tick,
            timestamp=ctx.timestamp,
            agent=effect.agent,
            old_last_active_tick=old_tick,
            new_last_active_tick=new_tick,
        )

        return [event], ctx.with_updated_agent(new_agent)

    def _apply_session_id(
        self,
        effect: UpdateSessionIdEffect,
        ctx: TickContext,
    ) -> tuple[list[DomainEvent], TickContext]:
        """Update the agent's SDK session ID."""
        agent = ctx.agents.get(effect.agent)
        if not agent:
            return [], ctx

        old_session_id = agent.session_id
        new_session_id = effect.session_id

        # Don't emit event if unchanged
        if new_session_id == old_session_id:
            return [], ctx

        new_agent = AgentSnapshot(**{
            **agent.model_dump(),
            "session_id": new_session_id,
        })

        event = AgentSessionIdUpdatedEvent(
            tick=ctx.tick,
            timestamp=ctx.timestamp,
            agent=effect.agent,
            old_session_id=old_session_id,
            new_session_id=new_session_id,
        )

        return [event], ctx.with_updated_agent(new_agent)

    # =========================================================================
    # Conversation effects
    # =========================================================================

    def _apply_invite(
        self,
        effect: InviteToConversationEffect,
        ctx: TickContext,
    ) -> tuple[list[DomainEvent], TickContext]:
        """Create a conversation invitation."""
        # Generate conversation ID
        conv_id = ConversationId(str(uuid4())[:8])

        # Create invitation
        invitation = Invitation(
            conversation_id=conv_id,
            inviter=effect.inviter,
            invitee=effect.invitee,
            location=effect.location,
            privacy=effect.privacy,
            created_at_tick=ctx.tick,
            expires_at_tick=ctx.tick + INVITE_EXPIRY_TICKS,
            invited_at=ctx.timestamp,
        )

        event = ConversationInvitedEvent(
            tick=ctx.tick,
            timestamp=ctx.timestamp,
            conversation_id=conv_id,
            inviter=effect.inviter,
            invitee=effect.invitee,
            location=effect.location,
            privacy=effect.privacy,
        )

        return [event], ctx.with_added_invite(invitation)

    def _apply_accept(
        self,
        effect: AcceptInviteEffect,
        ctx: TickContext,
    ) -> tuple[list[DomainEvent], TickContext]:
        """Accept an invitation (creates conversation if first accept)."""
        invite = ctx.pending_invites.get(effect.agent)
        if not invite or invite.conversation_id != effect.conversation_id:
            return [], ctx

        events: list[DomainEvent] = []

        # Accept event
        events.append(ConversationInviteAcceptedEvent(
            tick=ctx.tick,
            timestamp=ctx.timestamp,
            conversation_id=effect.conversation_id,
            inviter=invite.inviter,
            invitee=effect.agent,
        ))

        # Create conversation (if it doesn't exist)
        if effect.conversation_id not in ctx.conversations:
            conv = Conversation(
                id=effect.conversation_id,
                location=invite.location,
                privacy=invite.privacy,
                participants=frozenset([invite.inviter, effect.agent]),
                pending_invitations={},
                history=(),
                started_at_tick=ctx.tick,
                created_by=invite.inviter,
            )

            events.append(ConversationStartedEvent(
                tick=ctx.tick,
                timestamp=ctx.timestamp,
                conversation_id=effect.conversation_id,
                location=invite.location,
                privacy=invite.privacy,
                initial_participants=(invite.inviter, effect.agent),
            ))

            new_ctx = ctx.with_updated_conversation(conv)
        else:
            new_ctx = ctx

        new_ctx = new_ctx.with_removed_invite(effect.agent)

        return events, new_ctx

    def _apply_decline(
        self,
        effect: DeclineInviteEffect,
        ctx: TickContext,
    ) -> tuple[list[DomainEvent], TickContext]:
        """Decline an invitation."""
        invite = ctx.pending_invites.get(effect.agent)
        if not invite or invite.conversation_id != effect.conversation_id:
            return [], ctx

        event = ConversationInviteDeclinedEvent(
            tick=ctx.tick,
            timestamp=ctx.timestamp,
            conversation_id=effect.conversation_id,
            inviter=invite.inviter,
            invitee=effect.agent,
        )

        return [event], ctx.with_removed_invite(effect.agent)

    def _apply_expire(
        self,
        effect: ExpireInviteEffect,
        ctx: TickContext,
    ) -> tuple[list[DomainEvent], TickContext]:
        """Handle invitation expiry."""
        invite = ctx.pending_invites.get(effect.invitee)
        if not invite or invite.conversation_id != effect.conversation_id:
            return [], ctx

        event = ConversationInviteExpiredEvent(
            tick=ctx.tick,
            timestamp=ctx.timestamp,
            conversation_id=effect.conversation_id,
            inviter=invite.inviter,
            invitee=effect.invitee,
        )

        return [event], ctx.with_removed_invite(effect.invitee)

    def _apply_join(
        self,
        effect: JoinConversationEffect,
        ctx: TickContext,
    ) -> tuple[list[DomainEvent], TickContext]:
        """Join a public conversation."""
        conv = ctx.conversations.get(effect.conversation_id)
        if not conv:
            return [], ctx

        # Add participant
        new_conv = Conversation(**{
            **conv.model_dump(),
            "participants": conv.participants | {effect.agent},
        })

        event = ConversationJoinedEvent(
            tick=ctx.tick,
            timestamp=ctx.timestamp,
            conversation_id=effect.conversation_id,
            agent=effect.agent,
        )

        return [event], ctx.with_updated_conversation(new_conv)

    def _apply_leave(
        self,
        effect: LeaveConversationEffect,
        ctx: TickContext,
    ) -> tuple[list[DomainEvent], TickContext]:
        """Leave a conversation (may end it if < 2 remain)."""
        conv = ctx.conversations.get(effect.conversation_id)
        if not conv or effect.agent not in conv.participants:
            return [], ctx

        events: list[DomainEvent] = []
        new_participants = conv.participants - {effect.agent}

        events.append(ConversationLeftEvent(
            tick=ctx.tick,
            timestamp=ctx.timestamp,
            conversation_id=effect.conversation_id,
            agent=effect.agent,
        ))

        if len(new_participants) < 2:
            # Conversation ends
            events.append(ConversationEndedEvent(
                tick=ctx.tick,
                timestamp=ctx.timestamp,
                conversation_id=effect.conversation_id,
                reason="not_enough_participants",
                final_participants=tuple(new_participants),
                summary="",  # Would generate summary here
            ))

            return events, ctx.with_removed_conversation(conv.id)
        else:
            # Update conversation
            new_conv = Conversation(**{
                **conv.model_dump(),
                "participants": new_participants,
            })

            return events, ctx.with_updated_conversation(new_conv)

    def _apply_conv_turn(
        self,
        effect: AddConversationTurnEffect,
        ctx: TickContext,
    ) -> tuple[list[DomainEvent], TickContext]:
        """Add a turn to a conversation."""
        conv = ctx.conversations.get(effect.conversation_id)
        if not conv:
            return [], ctx

        turn = ConversationTurn(
            speaker=effect.speaker,
            narrative=effect.narrative,
            tick=ctx.tick,
            timestamp=ctx.timestamp,
        )

        new_conv = Conversation(**{
            **conv.model_dump(),
            "history": (*conv.history, turn),
            "next_speaker": None,  # Clear after speaking
        })

        event = ConversationTurnEvent(
            tick=ctx.tick,
            timestamp=ctx.timestamp,
            conversation_id=effect.conversation_id,
            speaker=effect.speaker,
            narrative=effect.narrative,
        )

        return [event], ctx.with_updated_conversation(new_conv)

    def _apply_set_next_speaker(
        self,
        effect: SetNextSpeakerEffect,
        ctx: TickContext,
    ) -> tuple[list[DomainEvent], TickContext]:
        """Set the next speaker for a conversation."""
        conv = ctx.conversations.get(effect.conversation_id)
        if not conv or effect.speaker not in conv.participants:
            return [], ctx

        new_conv = Conversation(**{
            **conv.model_dump(),
            "next_speaker": effect.speaker,
        })

        event = ConversationNextSpeakerSetEvent(
            tick=ctx.tick,
            timestamp=ctx.timestamp,
            conversation_id=effect.conversation_id,
            next_speaker=effect.speaker,
        )

        return [event], ctx.with_updated_conversation(new_conv)

    def _apply_end_conversation(
        self,
        effect: EndConversationEffect,
        ctx: TickContext,
    ) -> tuple[list[DomainEvent], TickContext]:
        """Explicitly end a conversation."""
        conv = ctx.conversations.get(effect.conversation_id)
        if not conv:
            return [], ctx

        event = ConversationEndedEvent(
            tick=ctx.tick,
            timestamp=ctx.timestamp,
            conversation_id=effect.conversation_id,
            reason=effect.reason,
            final_participants=tuple(conv.participants),
            summary="",  # Would generate summary here
        )

        return [event], ctx.with_removed_conversation(conv.id)

    # =========================================================================
    # Invite expiry
    # =========================================================================

    def _expire_invites(
        self,
        ctx: TickContext,
    ) -> tuple[list[DomainEvent], TickContext]:
        """Expire any invites past their deadline."""
        events: list[DomainEvent] = []
        new_ctx = ctx

        for invitee, invite in list(ctx.pending_invites.items()):
            if invite.expires_at_tick <= ctx.tick:
                events.append(ConversationInviteExpiredEvent(
                    tick=ctx.tick,
                    timestamp=ctx.timestamp,
                    conversation_id=invite.conversation_id,
                    inviter=invite.inviter,
                    invitee=invite.invitee,
                ))

                new_ctx = new_ctx.with_removed_invite(invitee)

        if events:
            logger.debug(f"Expired {len(events)} invites")

        return events, new_ctx
