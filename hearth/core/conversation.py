"""Conversation domain models for Hearth.

Defines the core types for consent-based conversations:
- ConversationTurn: A single message in a conversation
- Invitation: A pending invitation to start a conversation
- Conversation: An active conversation between agents

Key design decisions:
- Position-agnostic: Conversations continue regardless of agent movement
- One at a time: Agents can only be in ONE conversation at a time
- Unseen tracking: Shows only turns since agent's last turn (SDK has session persistence)
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .types import AgentName, ConversationId

# How many ticks an invite remains valid before expiring
INVITE_EXPIRY_TICKS = 2


class ConversationTurn(BaseModel):
    """A single turn in a conversation.

    Immutable record of who said what and when.
    """

    model_config = ConfigDict(frozen=True)

    speaker: AgentName
    message: str
    tick: int
    timestamp: datetime


class Invitation(BaseModel):
    """A pending invitation to a conversation.

    Created when an agent invites another to talk.
    Expires after INVITE_EXPIRY_TICKS if not accepted/declined.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    conversation_id: ConversationId
    inviter: AgentName
    invitee: AgentName
    privacy: Literal["public", "private"]
    created_at_tick: int
    expires_at_tick: int
    invited_at: datetime = Field(default_factory=datetime.now)


class Conversation(BaseModel):
    """An active conversation between agents.

    Position-agnostic: once started, continues at any distance.
    Tracks participants and full history.
    """

    model_config = ConfigDict(frozen=True)

    id: ConversationId
    privacy: Literal["public", "private"]
    participants: frozenset[AgentName] = Field(default_factory=frozenset)
    history: tuple[ConversationTurn, ...] = Field(default_factory=tuple)
    started_at_tick: int
    created_by: AgentName
    ended_at_tick: int | None = None

    @property
    def is_active(self) -> bool:
        """Check if conversation is still active."""
        return self.ended_at_tick is None

    def with_participant(self, agent: AgentName) -> Conversation:
        """Return a new Conversation with the agent added as participant."""
        return self.model_copy(
            update={"participants": self.participants | {agent}}
        )

    def without_participant(self, agent: AgentName) -> Conversation:
        """Return a new Conversation with the agent removed."""
        return self.model_copy(
            update={"participants": self.participants - {agent}}
        )

    def with_turn(self, turn: ConversationTurn) -> Conversation:
        """Return a new Conversation with the turn appended."""
        return self.model_copy(
            update={"history": self.history + (turn,)}
        )

    def with_ended(self, tick: int) -> Conversation:
        """Return a new Conversation marked as ended."""
        return self.model_copy(update={"ended_at_tick": tick})


class ConversationContext(BaseModel):
    """Context for an agent's view of a conversation.

    Used by PerceptionBuilder to show only unseen turns.
    """

    model_config = ConfigDict(frozen=True)

    conversation: Conversation
    unseen_turns: tuple[ConversationTurn, ...]
    other_participants: frozenset[AgentName]
