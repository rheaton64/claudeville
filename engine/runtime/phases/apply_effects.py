"""
ApplyEffectsPhase - converts effects to domain events.

This phase processes all accumulated effects:
1. Converts each effect to one or more domain events
2. Updates context state (for subsequent effect processing within the tick)
3. Handles conversation lifecycle (create, end)
4. Handles invite expiry
5. Handles compaction (ShouldCompactEffect -> CompactionService -> DidCompactEvent)

NOTE: Most of this phase does NOT directly mutate services. It only produces events.
The EventStore._apply_event method is the single source of truth for state
updates. After events are committed, VillageEngine._hydrate_from_snapshot()
syncs services from the updated snapshot.

EXCEPTION: ShouldCompactEffect requires calling CompactionService to send /compact
to the SDK. This is handled specially in the async _execute method.
"""

import logging
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from engine.services.compaction import CompactionService

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
    TokenUsage,
    InterpreterUsage,
    WorldSnapshot,
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
    MoveConversationEffect,
    AddConversationTurnEffect,
    SetNextSpeakerEffect,
    EndConversationEffect,
    ConversationEndingSeenEffect,
    ShouldCompactEffect,
    RecordAgentTokenUsageEffect,
    RecordInterpreterTokenUsageEffect,
    ResetSessionTokensEffect,
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
    ConversationMovedEvent,
    ConversationEndedEvent,
    ConversationEndingUnseenEvent,
    ConversationEndingSeenEvent,
    DidCompactEvent,
    AgentTokenUsageRecordedEvent,
    InterpreterTokenUsageRecordedEvent,
    SessionTokensResetEvent,
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
    - Handles compaction (ShouldCompactEffect -> CompactionService -> DidCompactEvent)

    State updates happen through events only. EventStore._apply_event is the
    single source of truth. Services are hydrated from snapshots after events
    are committed.
    """

    def __init__(self) -> None:
        super().__init__()
        self._compaction_service: "CompactionService | None" = None

    def set_compaction_service(self, service: "CompactionService | None") -> None:
        """Set the compaction service for handling ShouldCompactEffect."""
        self._compaction_service = service

    async def _execute(self, ctx: TickContext) -> TickContext:
        """Process all effects and produce events."""
        # First, run all sync effects
        new_ctx = self.execute_sync(ctx)

        # Then handle any ShouldCompactEffect effects asynchronously
        # These were skipped in execute_sync and need async I/O
        compaction_events: list[DomainEvent] = []

        for effect in ctx.effects:
            if isinstance(effect, ShouldCompactEffect):
                events = await self._handle_compaction(effect, new_ctx)
                compaction_events.extend(events)

        if compaction_events:
            new_ctx = new_ctx.with_events(compaction_events)

        return new_ctx

    async def _handle_compaction(
        self,
        effect: ShouldCompactEffect,
        ctx: TickContext,
    ) -> list[DomainEvent]:
        """
        Handle ShouldCompactEffect - decide whether to compact and execute.

        Decision logic:
        - critical=True (>= 150K tokens): Always compact
        - critical=False (100K-150K tokens): Only compact if agent is going to sleep

        Returns:
            List of events (DidCompactEvent and SessionTokensResetEvent) or empty list
        """
        if not self._compaction_service:
            logger.warning(
                f"ShouldCompactEffect for {effect.agent} but no compaction service"
            )
            return []

        should_compact = False

        if effect.critical:
            # Critical threshold (>= 150K) - always compact
            should_compact = True
            logger.info(
                f"COMPACTION_DECISION | {effect.agent} | CRITICAL | "
                f"tokens={effect.pre_tokens} | compacting=True"
            )
        else:
            # Below critical but above pre-sleep threshold (100K-150K)
            # Only compact if agent is going to sleep
            is_going_to_sleep = any(
                isinstance(e, AgentSleepEffect) and e.agent == effect.agent
                for e in ctx.effects
            )
            should_compact = is_going_to_sleep
            logger.info(
                f"COMPACTION_DECISION | {effect.agent} | PRE_SLEEP | "
                f"tokens={effect.pre_tokens} | sleeping={is_going_to_sleep} | "
                f"compacting={should_compact}"
            )

        if not should_compact:
            return []

        # Execute compaction
        post_tokens = await self._compaction_service.execute_compact(
            effect.agent, effect.critical
        )

        # Get agent's old session tokens for the reset event
        agent = ctx.agents.get(effect.agent)
        old_session_tokens = 0
        if agent:
            old_session_tokens = agent.token_usage.session_tokens

        # Create events
        events: list[DomainEvent] = []

        events.append(DidCompactEvent(
            tick=ctx.tick,
            timestamp=ctx.timestamp,
            agent=effect.agent,
            pre_tokens=effect.pre_tokens,
            post_tokens=post_tokens,
            critical=effect.critical,
        ))

        events.append(SessionTokensResetEvent(
            tick=ctx.tick,
            timestamp=ctx.timestamp,
            agent=effect.agent,
            old_session_tokens=old_session_tokens,
            new_session_tokens=post_tokens,
        ))

        return events

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
            case MoveConversationEffect():
                return self._apply_move_conversation(effect, ctx)
            case AddConversationTurnEffect():
                return self._apply_conv_turn(effect, ctx)
            case SetNextSpeakerEffect():
                return self._apply_set_next_speaker(effect, ctx)
            case EndConversationEffect():
                return self._apply_end_conversation(effect, ctx)
            case ConversationEndingSeenEffect():
                return self._apply_conversation_ending_seen(effect, ctx)
            case ShouldCompactEffect():
                # Handled asynchronously in _execute, skip here
                return [], ctx
            case RecordAgentTokenUsageEffect():
                return self._apply_agent_token_usage(effect, ctx)
            case RecordInterpreterTokenUsageEffect():
                return self._apply_interpreter_token_usage(effect, ctx)
            case ResetSessionTokensEffect():
                return self._apply_reset_session_tokens(effect, ctx)
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
            location=effect.location,
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
        # Check if inviter is already in a conversation at this location
        # If so, invite to that existing conversation instead of creating a new one
        existing_conv = None
        for conv in ctx.conversations.values():
            if (effect.inviter in conv.participants and
                conv.location == effect.location):
                existing_conv = conv
                break

        if existing_conv:
            conv_id = existing_conv.id
        else:
            # Generate new conversation ID
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

            # Add first message as conversation turn if provided
            if effect.first_message:
                events.append(ConversationTurnEvent(
                    tick=ctx.tick,
                    timestamp=ctx.timestamp,
                    conversation_id=effect.conversation_id,
                    speaker=effect.agent,
                    narrative=effect.first_message,
                ))

            new_ctx = ctx.with_updated_conversation(conv)
        else:
            # Conversation already exists - join it
            existing_conv = ctx.conversations[effect.conversation_id]
            updated_conv = Conversation(
                **{
                    **existing_conv.model_dump(),
                    "participants": existing_conv.participants | {effect.agent},
                }
            )

            events.append(ConversationJoinedEvent(
                tick=ctx.tick,
                timestamp=ctx.timestamp,
                conversation_id=effect.conversation_id,
                agent=effect.agent,
            ))

            # Add first message as conversation turn if provided
            if effect.first_message:
                events.append(ConversationTurnEvent(
                    tick=ctx.tick,
                    timestamp=ctx.timestamp,
                    conversation_id=effect.conversation_id,
                    speaker=effect.agent,
                    narrative=effect.first_message,
                ))

            new_ctx = ctx.with_updated_conversation(updated_conv)

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

        events: list[DomainEvent] = []

        events.append(ConversationJoinedEvent(
            tick=ctx.tick,
            timestamp=ctx.timestamp,
            conversation_id=effect.conversation_id,
            agent=effect.agent,
        ))

        # Add first message as conversation turn if provided
        if effect.first_message:
            events.append(ConversationTurnEvent(
                tick=ctx.tick,
                timestamp=ctx.timestamp,
                conversation_id=effect.conversation_id,
                speaker=effect.agent,
                narrative=effect.first_message,
            ))

        return events, ctx.with_updated_conversation(new_conv)

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

        # Add last message as conversation turn BEFORE leaving if provided
        if effect.last_message:
            events.append(ConversationTurnEvent(
                tick=ctx.tick,
                timestamp=ctx.timestamp,
                conversation_id=effect.conversation_id,
                speaker=effect.agent,
                narrative=effect.last_message,
                is_departure=True,
            ))

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

            # Create unseen ending notifications for remaining participants
            # (if there was a final message from the leaving agent)
            if effect.last_message:
                for remaining in new_participants:
                    events.append(ConversationEndingUnseenEvent(
                        tick=ctx.tick,
                        timestamp=ctx.timestamp,
                        agent=remaining,
                        conversation_id=effect.conversation_id,
                        other_participant=effect.agent,
                        final_message=effect.last_message,
                    ))

            return events, ctx.with_removed_conversation(conv.id)
        else:
            # Update conversation
            new_conv = Conversation(**{
                **conv.model_dump(),
                "participants": new_participants,
            })

            return events, ctx.with_updated_conversation(new_conv)

    def _apply_move_conversation(
        self,
        effect: MoveConversationEffect,
        ctx: TickContext,
    ) -> tuple[list[DomainEvent], TickContext]:
        """Apply conversation move - moves all participants to new location."""
        conv = ctx.conversations.get(effect.conversation_id)
        if not conv:
            return [], ctx

        from_location = conv.location
        to_location = effect.to_location

        events: list[DomainEvent] = []
        new_ctx = ctx

        # Move each participant
        for participant in conv.participants:
            agent = new_ctx.agents.get(participant)
            if not agent:
                continue

            # Create move event for this participant
            move_event = AgentMovedEvent(
                tick=ctx.tick,
                timestamp=ctx.timestamp,
                agent=participant,
                from_location=agent.location,
                to_location=to_location,
            )
            events.append(move_event)

            # Update agent in context
            new_agent = AgentSnapshot(**{
                **agent.model_dump(),
                "location": to_location,
            })
            new_ctx = new_ctx.with_updated_agent(new_agent)

        # Create conversation moved event
        conv_moved_event = ConversationMovedEvent(
            tick=ctx.tick,
            timestamp=ctx.timestamp,
            conversation_id=effect.conversation_id,
            initiated_by=effect.agent,
            from_location=from_location,
            to_location=to_location,
            participants=tuple(conv.participants),
        )
        events.append(conv_moved_event)

        # Update conversation location in context
        new_conv = Conversation(**{
            **conv.model_dump(),
            "location": to_location,
        })
        new_ctx = new_ctx.with_updated_conversation(new_conv)

        return events, new_ctx

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
            narrative_with_tools=effect.narrative_with_tools,
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
            narrative_with_tools=effect.narrative_with_tools,
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

    def _apply_conversation_ending_seen(
        self,
        effect: ConversationEndingSeenEffect,
        ctx: TickContext,
    ) -> tuple[list[DomainEvent], TickContext]:
        """Mark a conversation ending as seen by an agent."""
        event = ConversationEndingSeenEvent(
            tick=ctx.tick,
            timestamp=ctx.timestamp,
            agent=effect.agent,
            conversation_id=effect.conversation_id,
        )

        return [event], ctx

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

    # =========================================================================
    # Token usage effects
    # =========================================================================

    def _apply_agent_token_usage(
        self,
        effect: RecordAgentTokenUsageEffect,
        ctx: TickContext,
    ) -> tuple[list[DomainEvent], TickContext]:
        """Record token usage from an agent turn."""
        agent = ctx.agents.get(effect.agent)
        if not agent:
            return [], ctx

        old_usage = agent.token_usage

        # Context window size from SDK (cache_read is cumulative, input is per-turn)
        context_window_size = effect.cache_read_input_tokens + effect.input_tokens

        # Update context window and cumulative totals
        new_usage = TokenUsage(
            session_tokens=context_window_size,
            total_input_tokens=old_usage.total_input_tokens + effect.input_tokens,
            total_output_tokens=old_usage.total_output_tokens + effect.output_tokens,
            cache_creation_input_tokens=(
                old_usage.cache_creation_input_tokens +
                effect.cache_creation_input_tokens
            ),
            cache_read_input_tokens=(
                old_usage.cache_read_input_tokens +
                effect.cache_read_input_tokens
            ),
            turn_count=old_usage.turn_count + 1,
        )

        new_agent = AgentSnapshot(**{
            **agent.model_dump(),
            "token_usage": new_usage,
        })

        event = AgentTokenUsageRecordedEvent(
            tick=ctx.tick,
            timestamp=ctx.timestamp,
            agent=effect.agent,
            input_tokens=effect.input_tokens,
            output_tokens=effect.output_tokens,
            cache_creation_input_tokens=effect.cache_creation_input_tokens,
            cache_read_input_tokens=effect.cache_read_input_tokens,
            model_id=effect.model_id,
            cumulative_session_tokens=new_usage.session_tokens,
            cumulative_total_tokens=(
                new_usage.total_input_tokens + new_usage.total_output_tokens
            ),
        )

        return [event], ctx.with_updated_agent(new_agent)

    def _apply_interpreter_token_usage(
        self,
        effect: RecordInterpreterTokenUsageEffect,
        ctx: TickContext,
    ) -> tuple[list[DomainEvent], TickContext]:
        """Record token usage from interpreter call (system overhead)."""
        old_usage = ctx.world.interpreter_usage

        new_usage = InterpreterUsage(
            total_input_tokens=old_usage.total_input_tokens + effect.input_tokens,
            total_output_tokens=old_usage.total_output_tokens + effect.output_tokens,
            call_count=old_usage.call_count + 1,
        )

        new_world = WorldSnapshot(**{
            **ctx.world.model_dump(),
            "interpreter_usage": new_usage,
        })

        event = InterpreterTokenUsageRecordedEvent(
            tick=ctx.tick,
            timestamp=ctx.timestamp,
            input_tokens=effect.input_tokens,
            output_tokens=effect.output_tokens,
            cumulative_total_tokens=(
                new_usage.total_input_tokens + new_usage.total_output_tokens
            ),
        )

        return [event], ctx.with_updated_world(new_world)

    def _apply_reset_session_tokens(
        self,
        effect: ResetSessionTokensEffect,
        ctx: TickContext,
    ) -> tuple[list[DomainEvent], TickContext]:
        """Reset session tokens after compaction."""
        agent = ctx.agents.get(effect.agent)
        if not agent:
            return [], ctx

        old_usage = agent.token_usage

        # Reset session tokens to post-compaction context size
        # All-time totals remain unchanged
        new_usage = TokenUsage(
            session_tokens=effect.new_session_tokens,
            total_input_tokens=old_usage.total_input_tokens,
            total_output_tokens=old_usage.total_output_tokens,
            cache_creation_input_tokens=old_usage.cache_creation_input_tokens,
            cache_read_input_tokens=old_usage.cache_read_input_tokens,
            turn_count=old_usage.turn_count,
        )

        new_agent = AgentSnapshot(**{
            **agent.model_dump(),
            "token_usage": new_usage,
        })

        event = SessionTokensResetEvent(
            tick=ctx.tick,
            timestamp=ctx.timestamp,
            agent=effect.agent,
            old_session_tokens=old_usage.session_tokens,
            new_session_tokens=effect.new_session_tokens,
        )

        return [event], ctx.with_updated_agent(new_agent)
