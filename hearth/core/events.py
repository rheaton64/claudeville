"""Event types for Hearth.

Events are the append-only audit log of everything that happens in the world.
Written to JSONL for debugging and analysis. NOT replayed - SQLite is authoritative.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Discriminator

from .types import Position, AgentName, ObjectId, Direction, ConversationId
from .terrain import Weather


class BaseEvent(BaseModel):
    """Base class for all events.

    All events have a tick number and timestamp.
    """

    model_config = ConfigDict(frozen=True)

    tick: int
    timestamp: datetime


# --- Movement Events ---


class AgentMovedEvent(BaseEvent):
    """Agent moved to an adjacent cell."""

    type: Literal["agent_moved"] = "agent_moved"
    agent: AgentName
    from_position: Position
    to_position: Position


class JourneyStartedEvent(BaseEvent):
    """Agent began a journey to a distant location."""

    type: Literal["journey_started"] = "journey_started"
    agent: AgentName
    destination: Position
    path_length: int


class JourneyInterruptedEvent(BaseEvent):
    """Agent's journey was interrupted."""

    type: Literal["journey_interrupted"] = "journey_interrupted"
    agent: AgentName
    reason: str  # "encountered_agent", "world_event", "discovery"
    at_position: Position


class JourneyCompletedEvent(BaseEvent):
    """Agent completed their journey."""

    type: Literal["journey_completed"] = "journey_completed"
    agent: AgentName
    destination: Position


# --- Object Events ---


class ObjectCreatedEvent(BaseEvent):
    """A new object was created in the world."""

    type: Literal["object_created"] = "object_created"
    object_id: ObjectId
    object_type: str  # "sign", "placed_item", etc.
    position: Position
    creator: AgentName | None


class ObjectRemovedEvent(BaseEvent):
    """An object was removed from the world."""

    type: Literal["object_removed"] = "object_removed"
    object_id: ObjectId


class SignWrittenEvent(BaseEvent):
    """A sign was written or updated."""

    type: Literal["sign_written"] = "sign_written"
    object_id: ObjectId
    position: Position
    text: str
    author: AgentName


# --- Building Events ---


class WallPlacedEvent(BaseEvent):
    """A wall was placed on a cell edge."""

    type: Literal["wall_placed"] = "wall_placed"
    position: Position
    direction: Direction
    builder: AgentName


class WallRemovedEvent(BaseEvent):
    """A wall was removed from a cell edge."""

    type: Literal["wall_removed"] = "wall_removed"
    position: Position
    direction: Direction


class DoorPlacedEvent(BaseEvent):
    """A door was placed in a wall."""

    type: Literal["door_placed"] = "door_placed"
    position: Position
    direction: Direction
    builder: AgentName


class StructureDetectedEvent(BaseEvent):
    """A new enclosed structure was detected."""

    type: Literal["structure_detected"] = "structure_detected"
    structure_id: ObjectId
    interior_cells: tuple[Position, ...]
    creator: AgentName | None


class PlaceNamedEvent(BaseEvent):
    """A location was given a name."""

    type: Literal["place_named"] = "place_named"
    position: Position
    name: str
    named_by: AgentName


# --- Inventory Events ---


class ItemGatheredEvent(BaseEvent):
    """An agent gathered a resource from the world."""

    type: Literal["item_gathered"] = "item_gathered"
    agent: AgentName
    item_type: str
    quantity: int
    from_position: Position


class ItemDroppedEvent(BaseEvent):
    """An agent dropped an item in the world."""

    type: Literal["item_dropped"] = "item_dropped"
    agent: AgentName
    item_type: str
    quantity: int
    at_position: Position


class ItemGivenEvent(BaseEvent):
    """An agent gave an item to another agent."""

    type: Literal["item_given"] = "item_given"
    giver: AgentName
    receiver: AgentName
    item_type: str
    quantity: int


class ItemCraftedEvent(BaseEvent):
    """An agent crafted a new item."""

    type: Literal["item_crafted"] = "item_crafted"
    agent: AgentName
    inputs: tuple[str, ...]
    output: str
    technique: str | None = None  # Only set for work actions


class ItemTakenEvent(BaseEvent):
    """An agent took an item from the world."""

    type: Literal["item_taken"] = "item_taken"
    agent: AgentName
    object_id: ObjectId
    item_type: str
    from_position: Position


# --- Agent State Events ---


class AgentSleptEvent(BaseEvent):
    """An agent went to sleep."""

    type: Literal["agent_slept"] = "agent_slept"
    agent: AgentName
    at_position: Position


class AgentWokeEvent(BaseEvent):
    """An agent woke up."""

    type: Literal["agent_woke"] = "agent_woke"
    agent: AgentName
    at_position: Position
    reason: str  # "time_changed", "visitor", "world_event", etc.


class AgentsMetEvent(BaseEvent):
    """Two agents met for the first time."""

    type: Literal["agents_met"] = "agents_met"
    agent1: AgentName
    agent2: AgentName
    at_position: Position


class AgentSessionUpdatedEvent(BaseEvent):
    """An agent's LLM session ID was updated."""

    type: Literal["agent_session_updated"] = "agent_session_updated"
    agent: AgentName
    old_session_id: str | None
    new_session_id: str


# --- World Events ---


class WorldEventOccurredEvent(BaseEvent):
    """A world event occurred (observer-triggered or system)."""

    type: Literal["world_event"] = "world_event"
    description: str
    at_position: Position | None = None


class WeatherChangedEvent(BaseEvent):
    """The weather changed."""

    type: Literal["weather_changed"] = "weather_changed"
    old_weather: Weather
    new_weather: Weather


class TimeAdvancedEvent(BaseEvent):
    """Time advanced (start of a new tick)."""

    type: Literal["time_advanced"] = "time_advanced"
    new_tick: int


# --- Conversation Events ---


class InvitationSentEvent(BaseEvent):
    """An agent sent an invitation to conversation."""

    type: Literal["invitation_sent"] = "invitation_sent"
    inviter: AgentName
    invitee: AgentName
    conversation_id: ConversationId
    privacy: str


class InvitationAcceptedEvent(BaseEvent):
    """An agent accepted a conversation invitation."""

    type: Literal["invitation_accepted"] = "invitation_accepted"
    agent: AgentName
    inviter: AgentName
    conversation_id: ConversationId


class InvitationDeclinedEvent(BaseEvent):
    """An agent declined a conversation invitation."""

    type: Literal["invitation_declined"] = "invitation_declined"
    agent: AgentName
    inviter: AgentName


class InvitationExpiredEvent(BaseEvent):
    """A conversation invitation expired without response."""

    type: Literal["invitation_expired"] = "invitation_expired"
    inviter: AgentName
    invitee: AgentName


class ConversationStartedEvent(BaseEvent):
    """A conversation started between agents."""

    type: Literal["conversation_started"] = "conversation_started"
    conversation_id: ConversationId
    participants: tuple[AgentName, ...]
    is_private: bool = False


class AgentJoinedConversationEvent(BaseEvent):
    """An agent joined an existing conversation."""

    type: Literal["agent_joined_conversation"] = "agent_joined_conversation"
    agent: AgentName
    conversation_id: ConversationId


class AgentLeftConversationEvent(BaseEvent):
    """An agent left a conversation."""

    type: Literal["agent_left_conversation"] = "agent_left_conversation"
    agent: AgentName
    conversation_id: ConversationId


class ConversationTurnEvent(BaseEvent):
    """An agent spoke in a conversation."""

    type: Literal["conversation_turn"] = "conversation_turn"
    conversation_id: ConversationId
    speaker: AgentName
    message: str


class ConversationEndedEvent(BaseEvent):
    """A conversation ended."""

    type: Literal["conversation_ended"] = "conversation_ended"
    conversation_id: ConversationId
    reason: str


# --- Discriminated Union ---


DomainEvent = Annotated[
    Union[
        # Movement
        AgentMovedEvent,
        JourneyStartedEvent,
        JourneyInterruptedEvent,
        JourneyCompletedEvent,
        # Objects
        ObjectCreatedEvent,
        ObjectRemovedEvent,
        SignWrittenEvent,
        # Building
        WallPlacedEvent,
        WallRemovedEvent,
        DoorPlacedEvent,
        StructureDetectedEvent,
        PlaceNamedEvent,
        # Inventory
        ItemGatheredEvent,
        ItemDroppedEvent,
        ItemGivenEvent,
        ItemCraftedEvent,
        ItemTakenEvent,
        # Agent state
        AgentSleptEvent,
        AgentWokeEvent,
        AgentsMetEvent,
        AgentSessionUpdatedEvent,
        # World
        WorldEventOccurredEvent,
        WeatherChangedEvent,
        TimeAdvancedEvent,
        # Conversations
        InvitationSentEvent,
        InvitationAcceptedEvent,
        InvitationDeclinedEvent,
        InvitationExpiredEvent,
        ConversationStartedEvent,
        AgentJoinedConversationEvent,
        AgentLeftConversationEvent,
        ConversationTurnEvent,
        ConversationEndedEvent,
    ],
    Discriminator("type"),
]
