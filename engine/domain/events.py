from datetime import datetime
from typing import Annotated, Literal, Union
from pydantic import BaseModel, ConfigDict, Discriminator
from .types import AgentName, ConversationId, LocationId

# --- Agent Events ---

class AgentMovedEvent(BaseModel):
    """Agent moved to a new location."""
    model_config = ConfigDict(frozen=True)
    type: Literal["agent_moved"] = "agent_moved"
    tick: int
    timestamp: datetime

    agent: AgentName
    from_location: LocationId
    to_location: LocationId

class AgentMoodChangedEvent(BaseModel):
    """Agent's mood changed."""
    model_config = ConfigDict(frozen=True)
    type: Literal["agent_mood_changed"] = "agent_mood_changed"
    tick: int
    timestamp: datetime

    agent: AgentName
    old_mood: str
    new_mood: str

class AgentEnergyChangedEvent(BaseModel):
    """Agent's energy changed."""
    model_config = ConfigDict(frozen=True)
    type: Literal["agent_energy_changed"] = "agent_energy_changed"
    tick: int
    timestamp: datetime

    agent: AgentName
    old_energy: int
    new_energy: int

class AgentActionEvent(BaseModel):
    """Agent performed an action."""
    model_config = ConfigDict(frozen=True)
    type: Literal["agent_action"] = "agent_action"
    tick: int
    timestamp: datetime

    agent: AgentName
    location: LocationId
    description: str

class AgentSleptEvent(BaseModel):
    """Agent went to sleep."""
    model_config = ConfigDict(frozen=True)
    type: Literal["agent_slept"] = "agent_slept"
    tick: int
    timestamp: datetime

    agent: AgentName
    location: LocationId

class AgentWokeEvent(BaseModel):
    """Agent woke up."""
    model_config = ConfigDict(frozen=True)
    type: Literal["agent_woke"] = "agent_woke"
    tick: int
    timestamp: datetime

    agent: AgentName
    location: LocationId
    reason: str  # "time_period_changed", "visitor_arrived", etc.

class AgentLastActiveTickUpdatedEvent(BaseModel):
    """Agent's last active tick was updated."""
    model_config = ConfigDict(frozen=True)
    type: Literal["agent_last_active_tick_updated"] = "agent_last_active_tick_updated"
    tick: int
    timestamp: datetime

    agent: AgentName
    old_last_active_tick: int
    new_last_active_tick: int


class AgentSessionIdUpdatedEvent(BaseModel):
    """Agent's SDK session ID was updated."""
    model_config = ConfigDict(frozen=True)
    type: Literal["agent_session_id_updated"] = "agent_session_id_updated"
    tick: int
    timestamp: datetime

    agent: AgentName
    old_session_id: str | None
    new_session_id: str


# --- Conversation Events ---

class ConversationInvitedEvent(BaseModel):
    """Agent invited another to a conversation."""
    model_config = ConfigDict(frozen=True)
    type: Literal["conversation_invited"] = "conversation_invited"
    tick: int
    timestamp: datetime

    conversation_id: ConversationId
    inviter: AgentName
    invitee: AgentName
    location: LocationId
    privacy: Literal["public", "private"]

class ConversationInviteAcceptedEvent(BaseModel):
    """Agent accepted an invitation."""
    model_config = ConfigDict(frozen=True)
    type: Literal["conversation_invite_accepted"] = "conversation_invite_accepted"
    tick: int
    timestamp: datetime

    conversation_id: ConversationId
    inviter: AgentName
    invitee: AgentName

class ConversationInviteDeclinedEvent(BaseModel):
    """Agent declined an invitation."""
    model_config = ConfigDict(frozen=True)
    type: Literal["conversation_invite_declined"] = "conversation_invite_declined"
    tick: int
    timestamp: datetime

    conversation_id: ConversationId
    inviter: AgentName
    invitee: AgentName

class ConversationInviteExpiredEvent(BaseModel):
    """Invitation expired without response."""
    model_config = ConfigDict(frozen=True)
    type: Literal["conversation_invite_expired"] = "conversation_invite_expired"
    tick: int
    timestamp: datetime

    conversation_id: ConversationId
    inviter: AgentName
    invitee: AgentName

class ConversationStartedEvent(BaseModel):
    """Conversation started (first invite accepted)."""
    model_config = ConfigDict(frozen=True)
    type: Literal["conversation_started"] = "conversation_started"
    tick: int
    timestamp: datetime

    conversation_id: ConversationId
    location: LocationId
    privacy: Literal["public", "private"]
    initial_participants: tuple[AgentName, ...]

class ConversationJoinedEvent(BaseModel):
    """Agent joined an existing conversation."""
    model_config = ConfigDict(frozen=True)
    type: Literal["conversation_joined"] = "conversation_joined"
    tick: int
    timestamp: datetime

    conversation_id: ConversationId
    agent: AgentName

class ConversationLeftEvent(BaseModel):
    """Agent left a conversation."""
    model_config = ConfigDict(frozen=True)
    type: Literal["conversation_left"] = "conversation_left"
    tick: int
    timestamp: datetime

    conversation_id: ConversationId
    agent: AgentName

class ConversationTurnEvent(BaseModel):
    """Agent spoke in a conversation."""
    model_config = ConfigDict(frozen=True)
    type: Literal["conversation_turn"] = "conversation_turn"
    tick: int
    timestamp: datetime

    conversation_id: ConversationId
    speaker: AgentName
    narrative: str

class ConversationNextSpeakerSetEvent(BaseModel):
    """Conversation next speaker set."""
    model_config = ConfigDict(frozen=True)
    type: Literal["conversation_next_speaker_set"] = "conversation_next_speaker_set"
    tick: int
    timestamp: datetime

    conversation_id: ConversationId
    next_speaker: AgentName

class ConversationEndedEvent(BaseModel):
    """Conversation ended."""
    model_config = ConfigDict(frozen=True)
    type: Literal["conversation_ended"] = "conversation_ended"
    tick: int
    timestamp: datetime

    conversation_id: ConversationId
    reason: str
    final_participants: tuple[AgentName, ...]
    summary: str  # Generated by Haiku at end

# --- World Events ---

class WorldEventOccurred(BaseModel):
    """Observer-triggered or system world event."""
    model_config = ConfigDict(frozen=True)
    type: Literal["world_event"] = "world_event"
    tick: int
    timestamp: datetime

    description: str
    location: LocationId | None = None
    agents_involved: tuple[AgentName, ...] = ()

class WeatherChangedEvent(BaseModel):
    """Weather changed."""
    model_config = ConfigDict(frozen=True)
    type: Literal["weather_changed"] = "weather_changed"
    tick: int
    timestamp: datetime

    old_weather: str
    new_weather: str

# --- The discriminated union ---

DomainEvent = Annotated[
    Union[
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
        WorldEventOccurred,
        WeatherChangedEvent,
    ],
    Discriminator("type"),
]
