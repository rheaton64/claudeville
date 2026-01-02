"""Event types for Hearth.

Events are the append-only history of everything that happens in the world.
They're written to JSONL and can be replayed to reconstruct state.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Discriminator

from .types import Position, AgentName, ObjectId, Direction
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
    technique: str


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


# --- Conversation Events (for future use) ---


class ConversationStartedEvent(BaseEvent):
    """A conversation started between agents."""

    type: Literal["conversation_started"] = "conversation_started"
    conversation_id: str
    participants: tuple[AgentName, ...]
    at_position: Position
    is_private: bool = False


class ConversationEndedEvent(BaseEvent):
    """A conversation ended."""

    type: Literal["conversation_ended"] = "conversation_ended"
    conversation_id: str
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
        ConversationStartedEvent,
        ConversationEndedEvent,
    ],
    Discriminator("type"),
]
