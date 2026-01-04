"""Conversation repository for Hearth.

Handles persistence of conversations, turns, participants, and invitations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from core.types import AgentName, ConversationId
from core.conversation import (
    INVITE_EXPIRY_TICKS,
    Conversation,
    ConversationTurn,
    Invitation,
)
from core.constants import HEARTH_TZ

from .base import BaseRepository


# Type alias for privacy values
Privacy = Literal["public", "private"]
_VALID_PRIVACY_VALUES = frozenset(["public", "private"])


def _validate_privacy(value: str) -> Privacy:
    """Validate and cast privacy value from database.

    Args:
        value: Privacy value from database

    Returns:
        Validated privacy literal

    Raises:
        ValueError: If value is not 'public' or 'private'
    """
    if value not in _VALID_PRIVACY_VALUES:
        raise ValueError(f"Invalid privacy value: {value!r}, expected 'public' or 'private'")
    return value  # type: ignore[return-value]


class ConversationRepository(BaseRepository):
    """Repository for conversations and invitations.

    Handles:
    - Conversation CRUD
    - Participant management
    - Turn history
    - Invitation management
    """

    # --- Conversation CRUD ---

    async def create_conversation(
        self,
        created_by: AgentName,
        privacy: str,
        tick: int,
    ) -> Conversation:
        """Create a new conversation.

        Args:
            created_by: Agent who started the conversation
            privacy: 'public' or 'private'
            tick: Current tick

        Returns:
            Created conversation
        """
        conv_id = ConversationId(f"conv_{uuid4().hex[:8]}")

        await self.db.execute(
            """
            INSERT INTO conversations (id, privacy, started_at_tick, created_by)
            VALUES (?, ?, ?, ?)
            """,
            (str(conv_id), privacy, tick, str(created_by)),
        )

        # Add creator as first participant
        await self._add_participant(conv_id, created_by, tick)

        await self.db.commit()

        return Conversation(
            id=conv_id,
            privacy=_validate_privacy(privacy),
            participants=frozenset([created_by]),
            history=(),
            started_at_tick=tick,
            created_by=created_by,
        )

    async def get_conversation(self, conv_id: ConversationId) -> Conversation | None:
        """Get a conversation by ID.

        Args:
            conv_id: Conversation ID

        Returns:
            Conversation if found, None otherwise
        """
        row = await self.db.fetch_one(
            "SELECT * FROM conversations WHERE id = ?",
            (str(conv_id),),
        )
        if row is None:
            return None

        # Load participants
        participants = await self._get_active_participants(conv_id)

        # Load history
        history = await self._get_turns(conv_id)

        return Conversation(
            id=conv_id,
            privacy=_validate_privacy(row["privacy"]),
            participants=participants,
            history=history,
            started_at_tick=row["started_at_tick"],
            created_by=AgentName(row["created_by"]),
            ended_at_tick=row["ended_at_tick"],
        )

    async def get_conversation_for_agent(
        self, agent: AgentName
    ) -> Conversation | None:
        """Get the active conversation an agent is in.

        Args:
            agent: Agent name

        Returns:
            Active conversation, or None if not in any
        """
        row = await self.db.fetch_one(
            """
            SELECT c.id FROM conversations c
            JOIN conversation_participants p ON c.id = p.conversation_id
            WHERE p.agent = ? AND p.left_at_tick IS NULL AND c.ended_at_tick IS NULL
            """,
            (str(agent),),
        )
        if row is None:
            return None
        return await self.get_conversation(ConversationId(row["id"]))

    async def get_all_active_conversations(self) -> list[Conversation]:
        """Get all active (not ended) conversations.

        Returns:
            List of active conversations
        """
        rows = await self.db.fetch_all(
            "SELECT id FROM conversations WHERE ended_at_tick IS NULL"
        )
        conversations = []
        for row in rows:
            conv = await self.get_conversation(ConversationId(row["id"]))
            if conv is not None:
                conversations.append(conv)
        return conversations

    async def end_conversation(self, conv_id: ConversationId, tick: int) -> None:
        """Mark a conversation as ended.

        Args:
            conv_id: Conversation ID
            tick: Tick when conversation ended
        """
        await self.db.execute(
            "UPDATE conversations SET ended_at_tick = ? WHERE id = ?",
            (tick, str(conv_id)),
        )
        await self.db.commit()

    # --- Participants ---

    async def _add_participant(
        self, conv_id: ConversationId, agent: AgentName, tick: int
    ) -> None:
        """Add a participant to a conversation (internal).

        Args:
            conv_id: Conversation ID
            agent: Agent to add
            tick: Tick when joined
        """
        await self.db.execute(
            """
            INSERT INTO conversation_participants (conversation_id, agent, joined_at_tick)
            VALUES (?, ?, ?)
            ON CONFLICT(conversation_id, agent) DO UPDATE SET
                left_at_tick = NULL,
                joined_at_tick = excluded.joined_at_tick
            """,
            (str(conv_id), str(agent), tick),
        )

    async def add_participant(
        self, conv_id: ConversationId, agent: AgentName, tick: int
    ) -> None:
        """Add a participant to a conversation.

        Args:
            conv_id: Conversation ID
            agent: Agent to add
            tick: Tick when joined
        """
        await self._add_participant(conv_id, agent, tick)
        await self.db.commit()

    async def remove_participant(
        self, conv_id: ConversationId, agent: AgentName, tick: int
    ) -> int:
        """Remove a participant from a conversation.

        Args:
            conv_id: Conversation ID
            agent: Agent to remove
            tick: Tick when left

        Returns:
            Number of remaining active participants
        """
        await self.db.execute(
            """
            UPDATE conversation_participants
            SET left_at_tick = ?
            WHERE conversation_id = ? AND agent = ? AND left_at_tick IS NULL
            """,
            (tick, str(conv_id), str(agent)),
        )
        await self.db.commit()

        # Return count of remaining participants
        row = await self.db.fetch_one(
            """
            SELECT COUNT(*) as cnt FROM conversation_participants
            WHERE conversation_id = ? AND left_at_tick IS NULL
            """,
            (str(conv_id),),
        )
        return row["cnt"] if row else 0

    async def _get_active_participants(
        self, conv_id: ConversationId
    ) -> frozenset[AgentName]:
        """Get active participants in a conversation.

        Args:
            conv_id: Conversation ID

        Returns:
            Frozenset of participant names
        """
        rows = await self.db.fetch_all(
            """
            SELECT agent FROM conversation_participants
            WHERE conversation_id = ? AND left_at_tick IS NULL
            """,
            (str(conv_id),),
        )
        return frozenset(AgentName(row["agent"]) for row in rows)

    async def get_last_turn_tick(
        self, conv_id: ConversationId, agent: AgentName
    ) -> int | None:
        """Get the tick of the agent's last turn in the conversation.

        Used for computing unseen history.

        Args:
            conv_id: Conversation ID
            agent: Agent name

        Returns:
            Tick of last turn, or None if no turns yet
        """
        row = await self.db.fetch_one(
            """
            SELECT last_turn_tick FROM conversation_participants
            WHERE conversation_id = ? AND agent = ?
            """,
            (str(conv_id), str(agent)),
        )
        return row["last_turn_tick"] if row else None

    async def update_last_turn_tick(
        self, conv_id: ConversationId, agent: AgentName, tick: int
    ) -> None:
        """Update the tick of the agent's last turn.

        Args:
            conv_id: Conversation ID
            agent: Agent name
            tick: Tick of the turn
        """
        await self.db.execute(
            """
            UPDATE conversation_participants
            SET last_turn_tick = ?
            WHERE conversation_id = ? AND agent = ?
            """,
            (tick, str(conv_id), str(agent)),
        )
        await self.db.commit()

    # --- Turns ---

    async def add_turn(
        self,
        conv_id: ConversationId,
        speaker: AgentName,
        message: str,
        tick: int,
    ) -> ConversationTurn:
        """Add a turn to a conversation.

        Args:
            conv_id: Conversation ID
            speaker: Who spoke
            message: What they said
            tick: Current tick

        Returns:
            Created turn
        """
        now = datetime.now(HEARTH_TZ)

        await self.db.execute(
            """
            INSERT INTO conversation_turns (conversation_id, speaker, message, tick, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (str(conv_id), str(speaker), message, tick, now.isoformat()),
        )

        # Update speaker's last turn tick
        await self.update_last_turn_tick(conv_id, speaker, tick)

        await self.db.commit()

        return ConversationTurn(
            speaker=speaker,
            message=message,
            tick=tick,
            timestamp=now,
        )

    async def _get_turns(self, conv_id: ConversationId) -> tuple[ConversationTurn, ...]:
        """Get all turns in a conversation.

        Args:
            conv_id: Conversation ID

        Returns:
            Tuple of turns in order
        """
        rows = await self.db.fetch_all(
            """
            SELECT speaker, message, tick, timestamp
            FROM conversation_turns
            WHERE conversation_id = ?
            ORDER BY id
            """,
            (str(conv_id),),
        )
        return tuple(
            ConversationTurn(
                speaker=AgentName(row["speaker"]),
                message=row["message"],
                tick=row["tick"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
            )
            for row in rows
        )

    async def get_turns_since(
        self, conv_id: ConversationId, since_tick: int | None
    ) -> tuple[ConversationTurn, ...]:
        """Get turns since a specific tick.

        Args:
            conv_id: Conversation ID
            since_tick: Tick to start from (exclusive), or None for all

        Returns:
            Tuple of turns after the specified tick
        """
        if since_tick is None:
            return await self._get_turns(conv_id)

        rows = await self.db.fetch_all(
            """
            SELECT speaker, message, tick, timestamp
            FROM conversation_turns
            WHERE conversation_id = ? AND tick > ?
            ORDER BY id
            """,
            (str(conv_id), since_tick),
        )
        return tuple(
            ConversationTurn(
                speaker=AgentName(row["speaker"]),
                message=row["message"],
                tick=row["tick"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
            )
            for row in rows
        )

    # --- Invitations ---

    async def create_invitation(
        self,
        inviter: AgentName,
        invitee: AgentName,
        privacy: str,
        tick: int,
    ) -> Invitation:
        """Create a new invitation.

        Args:
            inviter: Who is inviting
            invitee: Who is being invited
            privacy: 'public' or 'private'
            tick: Current tick

        Returns:
            Created invitation
        """
        invite_id = f"inv_{uuid4().hex[:8]}"
        conv_id = ConversationId(f"conv_{uuid4().hex[:8]}")
        expires_at_tick = tick + INVITE_EXPIRY_TICKS
        now = datetime.now(HEARTH_TZ)

        await self.db.execute(
            """
            INSERT INTO conversation_invitations
            (id, conversation_id, inviter, invitee, privacy, created_at_tick, expires_at_tick)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                invite_id,
                str(conv_id),
                str(inviter),
                str(invitee),
                privacy,
                tick,
                expires_at_tick,
            ),
        )
        await self.db.commit()

        return Invitation(
            id=invite_id,
            conversation_id=conv_id,
            inviter=inviter,
            invitee=invitee,
            privacy=_validate_privacy(privacy),
            created_at_tick=tick,
            expires_at_tick=expires_at_tick,
            invited_at=now,
        )

    async def get_pending_invitation(self, agent: AgentName) -> Invitation | None:
        """Get the pending invitation for an agent (as invitee).

        Args:
            agent: Agent name (invitee)

        Returns:
            Pending invitation, or None if none
        """
        row = await self.db.fetch_one(
            "SELECT * FROM conversation_invitations WHERE invitee = ?",
            (str(agent),),
        )
        if row is None:
            return None

        return Invitation(
            id=row["id"],
            conversation_id=ConversationId(row["conversation_id"]),
            inviter=AgentName(row["inviter"]),
            invitee=AgentName(row["invitee"]),
            privacy=_validate_privacy(row["privacy"]),
            created_at_tick=row["created_at_tick"],
            expires_at_tick=row["expires_at_tick"],
        )

    async def get_pending_outgoing_invite(
        self, agent: AgentName
    ) -> Invitation | None:
        """Get the pending invitation sent by an agent (as inviter).

        Args:
            agent: Agent name (inviter)

        Returns:
            Pending outgoing invitation, or None if none
        """
        row = await self.db.fetch_one(
            "SELECT * FROM conversation_invitations WHERE inviter = ?",
            (str(agent),),
        )
        if row is None:
            return None

        return Invitation(
            id=row["id"],
            conversation_id=ConversationId(row["conversation_id"]),
            inviter=AgentName(row["inviter"]),
            invitee=AgentName(row["invitee"]),
            privacy=_validate_privacy(row["privacy"]),
            created_at_tick=row["created_at_tick"],
            expires_at_tick=row["expires_at_tick"],
        )

    async def delete_invitation(self, invite_id: str) -> None:
        """Delete an invitation.

        Args:
            invite_id: Invitation ID to delete
        """
        await self.db.execute(
            "DELETE FROM conversation_invitations WHERE id = ?",
            (invite_id,),
        )
        await self.db.commit()

    async def delete_invitations_for_invitee(self, agent: AgentName) -> None:
        """Delete all pending invitations for an agent.

        Args:
            agent: Agent name (invitee)
        """
        await self.db.execute(
            "DELETE FROM conversation_invitations WHERE invitee = ?",
            (str(agent),),
        )
        await self.db.commit()

    async def get_expired_invitations(self, current_tick: int) -> list[Invitation]:
        """Get all expired invitations.

        Uses strict less-than so invitees get the full tick to respond.
        With INVITE_EXPIRY_TICKS=2, an invite created at tick 5 (expires_at_tick=7)
        will expire at start of tick 8, giving invitee ticks 6 and 7 to respond.

        Args:
            current_tick: Current tick

        Returns:
            List of expired invitations
        """
        rows = await self.db.fetch_all(
            "SELECT * FROM conversation_invitations WHERE expires_at_tick < ?",
            (current_tick,),
        )
        return [
            Invitation(
                id=row["id"],
                conversation_id=ConversationId(row["conversation_id"]),
                inviter=AgentName(row["inviter"]),
                invitee=AgentName(row["invitee"]),
                privacy=_validate_privacy(row["privacy"]),
                created_at_tick=row["created_at_tick"],
                expires_at_tick=row["expires_at_tick"],
            )
            for row in rows
        ]
