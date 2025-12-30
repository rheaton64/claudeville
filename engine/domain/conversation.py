from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from .types import AgentName, ConversationId, LocationId

# How many ticks an invite remains valid before expiring
INVITE_EXPIRY_TICKS = 2


class ConversationTurn(BaseModel):
    """A single turn in a conversation."""
    model_config = ConfigDict(frozen=True)

    speaker: AgentName
    narrative: str
    tick: int
    timestamp: datetime
    is_departure: bool = False  # True if speaker left the conversation after this message
    narrative_with_tools: str | None = None  # Narrative with tool calls interleaved

class Invitation(BaseModel):
    """A pending invitation to a conversation."""
    model_config = ConfigDict(frozen=True)

    conversation_id: ConversationId
    inviter: AgentName
    invitee: AgentName
    location: LocationId
    privacy: Literal["public", "private"]
    created_at_tick: int
    expires_at_tick: int
    invited_at: datetime = Field(default_factory=datetime.now)

class Conversation(BaseModel):
    """An active conversation."""
    model_config = ConfigDict(frozen=True)

    id: ConversationId
    location: LocationId
    privacy: Literal["public", "private"]
    participants: frozenset[AgentName] = Field(default_factory=frozenset)
    pending_invitations: dict[AgentName, Invitation] = Field(default_factory=dict) # invitee -> invitation
    history: tuple[ConversationTurn, ...] = Field(default_factory=tuple)
    started_at_tick: int
    created_by: AgentName
    next_speaker: AgentName | None = None


class UnseenConversationEnding(BaseModel):
    """Notification that a conversation ended, not yet seen by this agent."""
    model_config = ConfigDict(frozen=True)

    conversation_id: ConversationId
    other_participant: AgentName  # Who left
    final_message: str | None
    ended_at_tick: int
