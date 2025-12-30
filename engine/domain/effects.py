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

class LeaveConversationEffect(BaseModel):
    """Agent leaves a conversation."""
    model_config = ConfigDict(frozen=True)
    type: Literal["leave_conversation"] = "leave_conversation"

    agent: AgentName
    conversation_id: ConversationId

class AddConversationTurnEffect(BaseModel):
    """Agent spoke in a conversation."""
    model_config = ConfigDict(frozen=True)
    type: Literal["add_conversation_turn"] = "add_conversation_turn"

    conversation_id: ConversationId
    speaker: AgentName
    narrative: str

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
        AddConversationTurnEffect,
        SetNextSpeakerEffect,
        EndConversationEffect,
    ],
    Discriminator("type"),
]
