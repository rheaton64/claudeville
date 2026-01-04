"""Conversation service for Hearth.

Business logic layer for consent-based conversations.

Key design decisions:
- Position-agnostic: Conversations continue regardless of agent movement
- Vision to start: Must see invitee to invite them
- One at a time: Agents can only be in ONE conversation at a time
- Unseen turns: Shows only turns since agent's last turn
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.types import AgentName, ConversationId
from core.conversation import (
    Conversation,
    ConversationContext,
    ConversationTurn,
    Invitation,
)

if TYPE_CHECKING:
    from storage import Storage

logger = logging.getLogger(__name__)


class ConversationService:
    """Service for managing conversations and invitations.

    Provides the business logic layer between ActionEngine and
    ConversationRepository.
    """

    def __init__(self, storage: "Storage"):
        """Initialize service with storage.

        Args:
            storage: Storage facade with conversation repository
        """
        self._storage = storage

    @property
    def _repo(self):
        """Get conversation repository."""
        return self._storage.conversations

    # --- Queries ---

    async def get_conversation(
        self, conv_id: ConversationId
    ) -> Conversation | None:
        """Get a conversation by ID.

        Args:
            conv_id: Conversation ID

        Returns:
            Conversation if found, None otherwise
        """
        return await self._repo.get_conversation(conv_id)

    async def get_conversation_for_agent(
        self, agent: AgentName
    ) -> Conversation | None:
        """Get the active conversation an agent is in.

        Args:
            agent: Agent name

        Returns:
            Active conversation, or None if not in any
        """
        return await self._repo.get_conversation_for_agent(agent)

    async def get_pending_invitation(
        self, agent: AgentName
    ) -> Invitation | None:
        """Get the pending invitation for an agent (as invitee).

        Args:
            agent: Agent name (invitee)

        Returns:
            Pending invitation, or None if none
        """
        return await self._repo.get_pending_invitation(agent)

    async def get_pending_outgoing_invite(
        self, agent: AgentName
    ) -> Invitation | None:
        """Get the pending invitation sent by an agent (as inviter).

        Used to check if agent has a pending outgoing invitation,
        particularly for blocking multiple private invitations.

        Args:
            agent: Agent name (inviter)

        Returns:
            Pending outgoing invitation, or None if none
        """
        return await self._repo.get_pending_outgoing_invite(agent)

    async def get_conversation_context(
        self, agent: AgentName
    ) -> ConversationContext | None:
        """Get conversation context for an agent, including only unseen turns.

        Args:
            agent: Agent name

        Returns:
            ConversationContext with unseen turns, or None if not in conversation
        """
        conv = await self._repo.get_conversation_for_agent(agent)
        if conv is None:
            return None

        # Get the tick of the agent's last turn
        last_turn_tick = await self._repo.get_last_turn_tick(conv.id, agent)

        # Get turns since that tick
        unseen_turns = await self._repo.get_turns_since(conv.id, last_turn_tick)

        # Get other participants
        other_participants = conv.participants - {agent}

        return ConversationContext(
            conversation=conv,
            unseen_turns=unseen_turns,
            other_participants=other_participants,
        )

    async def get_all_active_conversations(self) -> list[Conversation]:
        """Get all active conversations.

        Returns:
            List of active conversations
        """
        return await self._repo.get_all_active_conversations()

    async def is_agent_in_conversation(self, agent: AgentName) -> bool:
        """Check if an agent is currently in a conversation.

        Args:
            agent: Agent name

        Returns:
            True if in a conversation
        """
        conv = await self._repo.get_conversation_for_agent(agent)
        return conv is not None

    async def has_pending_invitation(self, agent: AgentName) -> bool:
        """Check if an agent has a pending invitation.

        Args:
            agent: Agent name

        Returns:
            True if has pending invitation
        """
        invite = await self._repo.get_pending_invitation(agent)
        return invite is not None

    # --- Commands ---

    async def create_invite(
        self,
        inviter: AgentName,
        invitee: AgentName,
        privacy: str,
        tick: int,
    ) -> Invitation:
        """Create an invitation to conversation.

        Note: Caller should validate visibility and availability before calling.

        Args:
            inviter: Who is inviting
            invitee: Who is being invited
            privacy: 'public' or 'private'
            tick: Current tick

        Returns:
            Created invitation
        """
        invitation = await self._repo.create_invitation(
            inviter=inviter,
            invitee=invitee,
            privacy=privacy,
            tick=tick,
        )

        logger.info(
            f"Created invitation from {inviter} to {invitee} "
            f"(privacy={privacy}, expires_at_tick={invitation.expires_at_tick})"
        )

        return invitation

    async def accept_invite(
        self, agent: AgentName, tick: int
    ) -> tuple[Conversation, Invitation] | None:
        """Accept a pending invitation and create/join conversation.

        Args:
            agent: Agent accepting (the invitee)
            tick: Current tick

        Returns:
            Tuple of (conversation, invitation) if accepted, None if no invitation
            or if inviter is already in a conversation (race condition)
        """
        invitation = await self._repo.get_pending_invitation(agent)
        if invitation is None:
            return None

        # Check if inviter is already in a conversation (race condition:
        # inviter sent multiple public invites and another was accepted first)
        existing_conv = await self._repo.get_conversation_for_agent(invitation.inviter)
        if existing_conv is not None:
            if existing_conv.privacy == "public":
                # Join the existing public conversation instead
                await self._repo.add_participant(existing_conv.id, agent, tick)
                await self._repo.delete_invitation(invitation.id)
                conv = await self._repo.get_conversation(existing_conv.id)
                logger.info(
                    f"{agent} accepted invitation from {invitation.inviter}, "
                    f"joined existing public conversation {conv.id}"
                )
                return conv, invitation
            else:
                # Private conversation - invitation is stale
                await self._repo.delete_invitation(invitation.id)
                logger.info(
                    f"Invitation from {invitation.inviter} to {agent} is stale "
                    "(inviter in private conversation)"
                )
                return None

        # Create the conversation with inviter as creator
        conv = await self._repo.create_conversation(
            created_by=invitation.inviter,
            privacy=invitation.privacy,
            tick=tick,
        )

        # Add the invitee as participant
        await self._repo.add_participant(conv.id, agent, tick)

        # Delete the invitation
        await self._repo.delete_invitation(invitation.id)

        # Reload conversation to get updated participants
        conv = await self._repo.get_conversation(conv.id)

        logger.info(
            f"{agent} accepted invitation from {invitation.inviter}, "
            f"conversation {conv.id} started"
        )

        return conv, invitation

    async def decline_invite(
        self, agent: AgentName
    ) -> Invitation | None:
        """Decline a pending invitation.

        Args:
            agent: Agent declining (the invitee)

        Returns:
            Declined invitation, or None if no invitation
        """
        invitation = await self._repo.get_pending_invitation(agent)
        if invitation is None:
            return None

        await self._repo.delete_invitation(invitation.id)

        logger.info(
            f"{agent} declined invitation from {invitation.inviter}"
        )

        return invitation

    async def join_conversation(
        self, agent: AgentName, conv_id: ConversationId, tick: int
    ) -> Conversation | None:
        """Join an existing public conversation.

        Note: Caller should validate conversation is public and agent
        can see a participant.

        Args:
            agent: Agent joining
            conv_id: Conversation to join
            tick: Current tick

        Returns:
            Updated conversation, or None if not found
        """
        conv = await self._repo.get_conversation(conv_id)
        if conv is None or not conv.is_active:
            return None

        await self._repo.add_participant(conv_id, agent, tick)

        # Reload to get updated participants
        conv = await self._repo.get_conversation(conv_id)

        logger.info(f"{agent} joined conversation {conv_id}")

        return conv

    async def leave_conversation(
        self, agent: AgentName, tick: int
    ) -> tuple[Conversation | None, bool]:
        """Leave the current conversation.

        Args:
            agent: Agent leaving
            tick: Current tick

        Returns:
            Tuple of (conversation, was_ended) where was_ended is True
            if the agent was the last participant
        """
        conv = await self._repo.get_conversation_for_agent(agent)
        if conv is None:
            return None, False

        # Remove participant
        remaining = await self._repo.remove_participant(conv.id, agent, tick)

        was_ended = False
        if remaining == 0:
            # Last person left, end the conversation
            await self._repo.end_conversation(conv.id, tick)
            was_ended = True

        # Reload conversation
        conv = await self._repo.get_conversation(conv.id)

        logger.info(
            f"{agent} left conversation {conv.id} "
            f"(remaining={remaining}, ended={was_ended})"
        )

        return conv, was_ended

    async def add_turn(
        self,
        agent: AgentName,
        message: str,
        tick: int,
    ) -> tuple[Conversation, ConversationTurn] | None:
        """Add a turn to the agent's current conversation.

        Args:
            agent: Agent speaking
            message: What they said
            tick: Current tick

        Returns:
            Tuple of (conversation, turn), or None if not in conversation
        """
        conv = await self._repo.get_conversation_for_agent(agent)
        if conv is None or not conv.is_active:
            return None

        turn = await self._repo.add_turn(
            conv_id=conv.id,
            speaker=agent,
            message=message,
            tick=tick,
        )

        # Reload conversation with new turn
        conv = await self._repo.get_conversation(conv.id)

        logger.debug(f"{agent} spoke in conversation {conv.id}")

        return conv, turn

    async def end_conversation(
        self, conv_id: ConversationId, tick: int
    ) -> Conversation | None:
        """End a conversation.

        Args:
            conv_id: Conversation to end
            tick: Current tick

        Returns:
            Ended conversation, or None if not found
        """
        await self._repo.end_conversation(conv_id, tick)
        conv = await self._repo.get_conversation(conv_id)

        if conv is not None:
            logger.info(f"Conversation {conv_id} ended at tick {tick}")

        return conv

    async def expire_invitations(self, current_tick: int) -> list[Invitation]:
        """Expire all invitations past their expiry tick.

        Args:
            current_tick: Current tick

        Returns:
            List of expired invitations
        """
        expired = await self._repo.get_expired_invitations(current_tick)

        for invite in expired:
            await self._repo.delete_invitation(invite.id)
            logger.info(
                f"Invitation from {invite.inviter} to {invite.invitee} expired"
            )

        return expired
