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
    location: LocationId  # Where the agent was when they acted
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
    is_departure: bool = False  # True if speaker left the conversation after this message
    narrative_with_tools: str | None = None  # Narrative with tool calls interleaved


class ConversationNextSpeakerSetEvent(BaseModel):
    """Conversation next speaker set."""
    model_config = ConfigDict(frozen=True)
    type: Literal["conversation_next_speaker_set"] = "conversation_next_speaker_set"
    tick: int
    timestamp: datetime

    conversation_id: ConversationId
    next_speaker: AgentName


class ConversationMovedEvent(BaseModel):
    """Conversation moved to a new location."""
    model_config = ConfigDict(frozen=True)
    type: Literal["conversation_moved"] = "conversation_moved"
    tick: int
    timestamp: datetime

    conversation_id: ConversationId
    initiated_by: AgentName
    from_location: LocationId
    to_location: LocationId
    participants: tuple[AgentName, ...]  # Who was moved


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


class ConversationEndingUnseenEvent(BaseModel):
    """Event recording that an agent has an unseen conversation ending."""
    model_config = ConfigDict(frozen=True)
    type: Literal["conversation_ending_unseen"] = "conversation_ending_unseen"
    tick: int
    timestamp: datetime

    agent: AgentName  # Who needs to see this
    conversation_id: ConversationId
    other_participant: AgentName  # Who left
    final_message: str | None


class ConversationEndingSeenEvent(BaseModel):
    """Event recording that an agent has seen/acknowledged a conversation ending."""
    model_config = ConfigDict(frozen=True)
    type: Literal["conversation_ending_seen"] = "conversation_ending_seen"
    tick: int
    timestamp: datetime

    agent: AgentName
    conversation_id: ConversationId


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


class NightSkippedEvent(BaseModel):
    """Night was skipped because all agents were sleeping."""
    model_config = ConfigDict(frozen=True)
    type: Literal["night_skipped"] = "night_skipped"
    tick: int
    timestamp: datetime

    from_time: datetime
    to_time: datetime  # Morning time we skipped to


# --- Compaction Events ---

class DidCompactEvent(BaseModel):
    """Agent's context was compacted.

    Emitted by ApplyEffectsPhase after successfully compacting an agent's
    SDK session context via the /compact command.
    """
    model_config = ConfigDict(frozen=True)
    type: Literal["did_compact"] = "did_compact"
    tick: int
    timestamp: datetime

    agent: AgentName
    pre_tokens: int  # Token count before compaction
    post_tokens: int  # Token count after compaction
    critical: bool  # True = was critical (>= 150K), False = was opportunistic pre-sleep


# --- Token Usage Events ---


class AgentTokenUsageRecordedEvent(BaseModel):
    """Historical record of agent token usage from a single turn.

    Emitted by ApplyEffectsPhase after recording token usage from an agent turn.
    """

    model_config = ConfigDict(frozen=True)
    type: Literal["agent_token_usage_recorded"] = "agent_token_usage_recorded"
    tick: int
    timestamp: datetime

    agent: AgentName

    # Per-turn usage
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    model_id: str

    # Cumulative at time of event (for querying)
    cumulative_session_tokens: int
    cumulative_total_tokens: int


class InterpreterTokenUsageRecordedEvent(BaseModel):
    """Historical record of interpreter token usage.

    Emitted by ApplyEffectsPhase after recording interpreter (Haiku) usage.
    """

    model_config = ConfigDict(frozen=True)
    type: Literal["interpreter_token_usage_recorded"] = "interpreter_token_usage_recorded"
    tick: int
    timestamp: datetime

    input_tokens: int
    output_tokens: int
    cumulative_total_tokens: int


class SessionTokensResetEvent(BaseModel):
    """Record of session token reset after compaction.

    Emitted by ApplyEffectsPhase after session tokens are reset following compaction.
    """

    model_config = ConfigDict(frozen=True)
    type: Literal["session_tokens_reset"] = "session_tokens_reset"
    tick: int
    timestamp: datetime

    agent: AgentName
    old_session_tokens: int
    new_session_tokens: int


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
        ConversationMovedEvent,
        ConversationEndedEvent,
        ConversationEndingUnseenEvent,
        ConversationEndingSeenEvent,
        WorldEventOccurred,
        WeatherChangedEvent,
        NightSkippedEvent,
        DidCompactEvent,
        AgentTokenUsageRecordedEvent,
        InterpreterTokenUsageRecordedEvent,
        SessionTokensResetEvent,
    ],
    Discriminator("type"),
]
