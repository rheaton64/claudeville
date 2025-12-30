"""
Conversation service - manages invitation-based conversation lifecycle.

Key principles:
- Conversations don't exist until first invite is accepted
- Location is informational, not definitional (multiple convos per location OK)
- Agents can be in multiple conversations simultaneously
- Unanswered invites expire (soft semantics, not "declined")
"""

from datetime import datetime
from typing import Literal
from uuid import uuid4

from engine.domain import (
    AgentName,
    LocationId,
    ConversationId,
    Conversation,
    Invitation,
    ConversationTurn,
    INVITE_EXPIRY_TICKS,
)


class ConversationService:
    """
    Manages conversation lifecycle with explicit invitations.

    This replaces the old "location = conversation" model with explicit
    invite/accept/join/leave semantics that respect agent autonomy.
    """

    def __init__(self):
        self._conversations: dict[ConversationId, Conversation] = {}
        self._pending_invites: dict[AgentName, Invitation] = {}  # invitee -> invite
        self._agent_conversations: dict[AgentName, set[ConversationId]] = {}

    def load_state(
        self,
        conversations: dict[ConversationId, Conversation],
        pending_invites: dict[AgentName, Invitation] | None = None,
    ) -> None:
        """
        Load state from snapshot.

        Called during recovery to restore conversation state.
        """
        self._conversations = dict(conversations)
        self._pending_invites = dict(pending_invites) if pending_invites else {}

        # Rebuild agent -> conversation index for fast lookups
        self._agent_conversations = {}
        for conv_id, conv in self._conversations.items():
            for agent in conv.participants:
                if agent not in self._agent_conversations:
                    self._agent_conversations[agent] = set()
                self._agent_conversations[agent].add(conv_id)

    # =========================================================================
    # Queries (read-only, safe to call anytime)
    # =========================================================================

    def get_conversation(self, conv_id: ConversationId) -> Conversation | None:
        """Get a conversation by ID."""
        return self._conversations.get(conv_id)

    def get_conversations_for_agent(self, agent: AgentName) -> list[Conversation]:
        """
        Get all conversations an agent is participating in.

        Note: An agent can be in multiple conversations simultaneously.
        """
        conv_ids = self._agent_conversations.get(agent, set())
        return [self._conversations[cid] for cid in conv_ids if cid in self._conversations]

    def get_conversations_at_location(
        self,
        location: LocationId,
        public_only: bool = True
    ) -> list[Conversation]:
        """
        Get conversations at a location.

        Used to show agents what conversations they could join.
        By default only returns public conversations.
        """
        return [
            conv for conv in self._conversations.values()
            if conv.location == location and (not public_only or conv.privacy == "public")
        ]

    def get_pending_invite(self, agent: AgentName) -> Invitation | None:
        """Get pending invitation for an agent, if any."""
        return self._pending_invites.get(agent)

    def get_all_pending_invites(self) -> dict[AgentName, Invitation]:
        """Get all pending invitations."""
        return dict(self._pending_invites)

    def get_all_conversations(self) -> dict[ConversationId, Conversation]:
        """Get all active conversations."""
        return dict(self._conversations)

    def is_in_conversation(self, agent: AgentName) -> bool:
        """Check if an agent is in any conversation."""
        return bool(self._agent_conversations.get(agent))

    def is_in_specific_conversation(self, agent: AgentName, conv_id: ConversationId) -> bool:
        """Check if an agent is in a specific conversation."""
        conv_ids = self._agent_conversations.get(agent, set())
        return conv_id in conv_ids

    def get_conversation_context(
        self,
        conv_id: ConversationId,
        agent: AgentName,
        last_seen_tick: int = 0,
    ) -> dict | None:
        """
        Get conversation context for an agent's turn.

        Returns a dict with:
        - conversation: the Conversation object
        - unseen_history: turns since agent's last turn
        - is_opener: whether agent is opening the conversation
        - participant_count: number of participants
        - is_group: whether this is a group conversation (3+)

        Returns None if conversation doesn't exist or agent isn't in it.
        """
        conv = self._conversations.get(conv_id)
        if conv is None or agent not in conv.participants:
            return None

        # Find unseen history (turns since agent last spoke or since last_seen_tick)
        agent_last_turn_idx = -1
        for i, turn in enumerate(conv.history):
            if turn.speaker == agent:
                agent_last_turn_idx = i

        if agent_last_turn_idx >= 0:
            unseen_history = list(conv.history[agent_last_turn_idx + 1:])
        else:
            # Agent hasn't spoken yet - show all history after last_seen_tick
            unseen_history = [t for t in conv.history if t.tick > last_seen_tick]

        return {
            "conversation": conv,
            "unseen_history": unseen_history,
            "is_opener": len(conv.history) == 0,
            "participant_count": len(conv.participants),
            "is_group": len(conv.participants) > 2,
            "other_participants": [p for p in conv.participants if p != agent],
        }

    # =========================================================================
    # Commands (mutate state, should be followed by event emission)
    # =========================================================================

    def create_invite(
        self,
        inviter: AgentName,
        invitee: AgentName,
        location: LocationId,
        privacy: Literal["public", "private"],
        current_tick: int,
        invited_at: datetime | None = None,
    ) -> tuple[ConversationId, Invitation]:
        """
        Create a conversation invitation.

        The conversation doesn't exist yet - it's created when invite is accepted.
        This respects agent autonomy: agents must consent to conversations.

        Returns (conversation_id, invitation).
        """
        conv_id = ConversationId(str(uuid4())[:8])

        invitation = Invitation(
            conversation_id=conv_id,
            inviter=inviter,
            invitee=invitee,
            location=location,
            privacy=privacy,
            created_at_tick=current_tick,
            expires_at_tick=current_tick + INVITE_EXPIRY_TICKS,
            invited_at=invited_at or datetime.now(),
        )

        self._pending_invites[invitee] = invitation
        return conv_id, invitation

    def accept_invite(
        self,
        agent: AgentName,
        current_tick: int,
        timestamp: datetime,
    ) -> Conversation | None:
        """
        Accept a pending invitation.

        Creates the conversation if this is the first acceptance.
        Returns the conversation, or None if no pending invite.
        """
        invite = self._pending_invites.pop(agent, None)
        if invite is None:
            return None

        conv_id = invite.conversation_id

        if conv_id in self._conversations:
            # Conversation already exists - just add participant
            # (This could happen if we support multiple invites to same conv)
            conv = self._conversations[conv_id]
            conv = Conversation(
                **{**conv.model_dump(), "participants": conv.participants | {agent}}
            )
        else:
            # Create new conversation with both inviter and invitee
            conv = Conversation(
                id=conv_id,
                location=invite.location,
                privacy=invite.privacy,
                participants=frozenset([invite.inviter, agent]),
                pending_invitations={},
                history=(),
                started_at_tick=current_tick,
                created_by=invite.inviter,
            )

        self._conversations[conv_id] = conv

        # Update agent -> conversation index for all participants
        for participant in conv.participants:
            if participant not in self._agent_conversations:
                self._agent_conversations[participant] = set()
            self._agent_conversations[participant].add(conv_id)

        return conv

    def decline_invite(self, agent: AgentName) -> Invitation | None:
        """
        Decline a pending invitation.

        Returns the invitation that was declined, or None if no pending invite.
        """
        return self._pending_invites.pop(agent, None)

    def expire_invite(self, agent: AgentName) -> Invitation | None:
        """
        Expire a pending invitation (no response given).

        This is softer than "decline" - the invite just wasn't addressed.
        Returns the invitation that expired, or None if no pending invite.
        """
        return self._pending_invites.pop(agent, None)

    def expire_invites_at_tick(self, current_tick: int) -> list[Invitation]:
        """
        Expire all invites that have passed their expiry tick.

        Called during tick processing to clean up unanswered invites.
        Returns list of expired invitations.
        """
        expired = []
        to_remove = []

        for invitee, invite in self._pending_invites.items():
            if invite.expires_at_tick <= current_tick:
                expired.append(invite)
                to_remove.append(invitee)

        for invitee in to_remove:
            del self._pending_invites[invitee]

        return expired

    def join_conversation(
        self,
        agent: AgentName,
        conv_id: ConversationId,
    ) -> Conversation | None:
        """
        Join a public conversation.

        Only works for public conversations.
        Returns updated conversation or None if not found/private.
        """
        conv = self._conversations.get(conv_id)
        if conv is None:
            return None
        if conv.privacy != "public":
            return None
        if agent in conv.participants:
            return conv  # Already in conversation

        conv = Conversation(
            **{**conv.model_dump(), "participants": conv.participants | {agent}}
        )
        self._conversations[conv_id] = conv

        if agent not in self._agent_conversations:
            self._agent_conversations[agent] = set()
        self._agent_conversations[agent].add(conv_id)

        return conv

    def leave_conversation(
        self,
        agent: AgentName,
        conv_id: ConversationId,
    ) -> tuple[Conversation | None, bool]:
        """
        Leave a conversation.

        Returns (updated_conversation, ended).
        If < 2 participants remain, conversation ends and returns (None, True).
        """
        conv = self._conversations.get(conv_id)
        if conv is None or agent not in conv.participants:
            return None, False

        new_participants = conv.participants - {agent}

        # Remove from agent's conversation set
        if agent in self._agent_conversations:
            self._agent_conversations[agent].discard(conv_id)

        if len(new_participants) < 2:
            # Conversation ends - not enough participants
            del self._conversations[conv_id]
            # Clean up remaining participant's index too
            for p in new_participants:
                if p in self._agent_conversations:
                    self._agent_conversations[p].discard(conv_id)
            return None, True

        # Update conversation with new participants
        conv = Conversation(
            **{**conv.model_dump(), "participants": new_participants}
        )
        self._conversations[conv_id] = conv
        return conv, False

    def add_turn(
        self,
        conv_id: ConversationId,
        speaker: AgentName,
        narrative: str,
        tick: int,
        timestamp: datetime,
    ) -> Conversation | None:
        """
        Add a turn to a conversation.

        Speaker must be a participant.
        Returns updated conversation or None if conversation not found.
        """
        conv = self._conversations.get(conv_id)
        if conv is None or speaker not in conv.participants:
            return None

        turn = ConversationTurn(
            speaker=speaker,
            narrative=narrative,
            tick=tick,
            timestamp=timestamp,
        )

        # Clear next_speaker after they speak
        new_next_speaker = None if conv.next_speaker == speaker else conv.next_speaker

        conv = Conversation(
            **{
                **conv.model_dump(),
                "history": (*conv.history, turn),
                "next_speaker": new_next_speaker,
            }
        )
        self._conversations[conv_id] = conv
        return conv

    def set_next_speaker(self, conv_id: ConversationId, speaker: AgentName) -> bool:
        """
        Set the next speaker for a conversation.

        Used by interpreter when agent suggests who should speak next.
        Returns True if successful, False if conversation not found or speaker not in it.
        """
        conv = self._conversations.get(conv_id)
        if conv is None or speaker not in conv.participants:
            return False

        self._conversations[conv_id] = Conversation(
            **{**conv.model_dump(), "next_speaker": speaker}
        )
        return True

    def get_next_speaker(
        self,
        conv_id: ConversationId,
        last_speaker: AgentName | None = None,
    ) -> AgentName | None:
        """
        Get the next speaker for a conversation.

        Priority:
        1. Explicitly set next_speaker
        2. Random participant (excluding last speaker)

        Returns None if conversation not found or empty.
        """
        conv = self._conversations.get(conv_id)
        if conv is None or not conv.participants:
            return None

        # If next_speaker is set, use it
        if conv.next_speaker and conv.next_speaker in conv.participants:
            return conv.next_speaker

        # Otherwise pick randomly, excluding last speaker
        import random
        candidates = [p for p in conv.participants if p != last_speaker]
        if not candidates:
            candidates = list(conv.participants)

        return random.choice(candidates) if candidates else None

    def end_conversation(
        self,
        conv_id: ConversationId,
    ) -> Conversation | None:
        """
        End a conversation explicitly.

        Returns the ended conversation for summary generation, or None if not found.
        """
        conv = self._conversations.pop(conv_id, None)
        if conv:
            # Clean up all participants' indexes
            for agent in conv.participants:
                if agent in self._agent_conversations:
                    self._agent_conversations[agent].discard(conv_id)
        return conv

    # =========================================================================
    # Index management helpers (for ApplyEffectsPhase to keep index in sync)
    # =========================================================================

    def add_participant_to_index(self, agent: AgentName, conv_id: ConversationId) -> None:
        """Add agent to the conversation index (call after modifying _conversations)."""
        if agent not in self._agent_conversations:
            self._agent_conversations[agent] = set()
        self._agent_conversations[agent].add(conv_id)

    def remove_participant_from_index(self, agent: AgentName, conv_id: ConversationId) -> None:
        """Remove agent from the conversation index."""
        if agent in self._agent_conversations:
            self._agent_conversations[agent].discard(conv_id)

    def remove_conversation_from_all_indexes(
        self,
        conv_id: ConversationId,
        participants: frozenset[AgentName],
    ) -> None:
        """Remove conversation from all participants' indexes."""
        for agent in participants:
            if agent in self._agent_conversations:
                self._agent_conversations[agent].discard(conv_id)
