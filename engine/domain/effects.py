from typing import Annotated, Literal, Union
from pydantic import BaseModel, ConfigDict, Discriminator
from .types import AgentName, ConversationId, LocationId

# Each effect is standalone with a type discriminator
class MoveAgentEffect(BaseModel):
    """Agent moved to a new location."""
    model_config = ConfigDict(frozen=True)
    type: Literal["move_agent"] = "move_agent"

    agent: AgentName
    from_location: LocationId
    to_location: LocationId

class UpdateMoodEffect(BaseModel):
    """Agent's mood changed."""
    model_config = ConfigDict(frozen=True)
    type: Literal["update_mood"] = "update_mood"

    agent: AgentName
    mood: str

class UpdateEnergyEffect(BaseModel):
    """Agent's energy changed."""
    model_config = ConfigDict(frozen=True)
    type: Literal["update_energy"] = "update_energy"

    agent: AgentName
    energy: int

class RecordActionEffect(BaseModel):
    """Agent performed an action."""
    model_config = ConfigDict(frozen=True)
    type: Literal["record_action"] = "record_action"

    agent: AgentName
    description: str

class AgentSleepEffect(BaseModel):
    """Agent is going to sleep."""
    model_config = ConfigDict(frozen=True)
    type: Literal["agent_sleep"] = "agent_sleep"

    agent: AgentName

class AgentWakeEffect(BaseModel):
    """Agent is waking up."""
    model_config = ConfigDict(frozen=True)
    type: Literal["agent_wake"] = "agent_wake"

    agent: AgentName
    reason: str | None = None

class UpdateLastActiveTickEffect(BaseModel):
    """Update the agent's last active tick to the current tick."""
    model_config = ConfigDict(frozen=True)
    type: Literal["update_last_active_tick"] = "update_last_active_tick"

    agent: AgentName
    location: LocationId  # Where the agent was when they acted


class UpdateSessionIdEffect(BaseModel):
    """Update the agent's SDK session ID for conversation resumption."""
    model_config = ConfigDict(frozen=True)
    type: Literal["update_session_id"] = "update_session_id"

    agent: AgentName
    session_id: str


# --- Conversation Effects ---

class InviteToConversationEffect(BaseModel):
    """Agent invites another to a conversation."""
    model_config = ConfigDict(frozen=True)
    type: Literal["invite_to_conversation"] = "invite_to_conversation"

    inviter: AgentName
    invitee: AgentName
    location: LocationId
    privacy: Literal["public", "private"]
    topic: str | None = None

class AcceptInviteEffect(BaseModel):
    """Agent accepts a conversation invitation."""
    model_config = ConfigDict(frozen=True)
    type: Literal["accept_invite"] = "accept_invite"

    agent: AgentName
    conversation_id: ConversationId
    first_message: str | None = None  # Text after the accept tool call

class DeclineInviteEffect(BaseModel):
    """Agent declines a conversation invitation."""
    model_config = ConfigDict(frozen=True)
    type: Literal["decline_invite"] = "decline_invite"

    agent: AgentName
    conversation_id: ConversationId

class ExpireInviteEffect(BaseModel):
    """Invitation expired (no response)."""
    model_config = ConfigDict(frozen=True)
    type: Literal["expire_invite"] = "expire_invite"

    conversation_id: ConversationId
    invitee: AgentName

class JoinConversationEffect(BaseModel):
    """Agent joins a public conversation."""
    model_config = ConfigDict(frozen=True)
    type: Literal["join_conversation"] = "join_conversation"

    agent: AgentName
    conversation_id: ConversationId
    first_message: str | None = None  # Text after the join tool call

class LeaveConversationEffect(BaseModel):
    """Agent leaves a conversation."""
    model_config = ConfigDict(frozen=True)
    type: Literal["leave_conversation"] = "leave_conversation"

    agent: AgentName
    conversation_id: ConversationId
    last_message: str | None = None  # Text before the leave tool call


class MoveConversationEffect(BaseModel):
    """Move entire conversation to a new location."""
    model_config = ConfigDict(frozen=True)
    type: Literal["move_conversation"] = "move_conversation"

    agent: AgentName  # Who initiated the move
    conversation_id: ConversationId
    to_location: LocationId


class AddConversationTurnEffect(BaseModel):
    """Agent spoke in a conversation."""
    model_config = ConfigDict(frozen=True)
    type: Literal["add_conversation_turn"] = "add_conversation_turn"

    conversation_id: ConversationId
    speaker: AgentName
    narrative: str
    narrative_with_tools: str | None = None  # Narrative with tool calls interleaved


class SetNextSpeakerEffect(BaseModel):
    """Set the next speaker for a conversation."""
    model_config = ConfigDict(frozen=True)
    type: Literal["set_next_speaker"] = "set_next_speaker"

    conversation_id: ConversationId
    speaker: AgentName

class EndConversationEffect(BaseModel):
    """Conversation ended (< 2 participants or explicit end)."""
    model_config = ConfigDict(frozen=True)
    type: Literal["end_conversation"] = "end_conversation"

    conversation_id: ConversationId
    reason: str


class ConversationEndingSeenEffect(BaseModel):
    """Agent has seen/acknowledged a conversation ending."""
    model_config = ConfigDict(frozen=True)
    type: Literal["conversation_ending_seen"] = "conversation_ending_seen"

    agent: AgentName
    conversation_id: ConversationId


# --- Compaction Effects ---

class ShouldCompactEffect(BaseModel):
    """Request compaction for an agent's context.

    Emitted by AgentTurnPhase when tokens >= 100K (pre-sleep threshold).
    ApplyEffectsPhase decides whether to actually compact based on:
    - critical=True (>= 150K): always compact
    - critical=False (100K-150K): only compact if agent is going to sleep
    """
    model_config = ConfigDict(frozen=True)
    type: Literal["should_compact"] = "should_compact"

    agent: AgentName
    pre_tokens: int  # Token count before compaction
    critical: bool  # True = 150K threshold (critical), False = 100K pre-sleep (opportunistic)


# --- Token Usage Effects ---


class RecordAgentTokenUsageEffect(BaseModel):
    """Record token usage from an agent turn.

    Emitted by AgentTurnPhase after each LLM call. Updates both
    session tokens (for compaction) and all-time totals.
    """

    model_config = ConfigDict(frozen=True)
    type: Literal["record_agent_token_usage"] = "record_agent_token_usage"

    agent: AgentName
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    model_id: str


class RecordInterpreterTokenUsageEffect(BaseModel):
    """Record token usage from interpreter call (system overhead).

    Emitted by InterpretPhase. Tracked separately from agent tokens
    since these are infrastructure costs.
    """

    model_config = ConfigDict(frozen=True)
    type: Literal["record_interpreter_token_usage"] = "record_interpreter_token_usage"

    input_tokens: int
    output_tokens: int


class ResetSessionTokensEffect(BaseModel):
    """Reset session tokens after compaction.

    Emitted by CompactionService after successful compaction. Sets
    session tokens to the post-compaction value while preserving
    all-time totals.
    """

    model_config = ConfigDict(frozen=True)
    type: Literal["reset_session_tokens"] = "reset_session_tokens"

    agent: AgentName
    new_session_tokens: int  # Post-compaction token count from SDK


Effect = Annotated[
    Union[
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
    ],
    Discriminator("type"),
]
