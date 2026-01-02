"""Core domain models for Hearth.

This module contains pure domain models with no I/O. All models are immutable
(frozen Pydantic models) and use transformation methods for updates.

Usage:
    from hearth.core import Position, Direction, Agent, Grid, DomainEvent
"""

# Types
from .types import (
    AgentName,
    ObjectId,
    LandmarkName,
    ConversationId,
    Position,
    Direction,
    Rect,
)

# Terrain and weather
from .terrain import (
    Terrain,
    Weather,
    TerrainProperties,
    TERRAIN_DEFAULTS,
    is_passable,
    get_symbol,
    get_gather_resource,
)

# World
from .world import Cell, Grid

# Objects
from .objects import (
    WorldObject,
    Sign,
    PlacedItem,
    Item,
    AnyWorldObject,
    generate_object_id,
)

# Structures
from .structures import Structure

# Agent
from .agent import (
    JourneyDestination,
    Journey,
    InventoryStack,
    Inventory,
    AgentModel,
    Agent,
)

# Events
from .events import (
    BaseEvent,
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
    # Union type
    DomainEvent,
)

__all__ = [
    # Types
    "AgentName",
    "ObjectId",
    "LandmarkName",
    "ConversationId",
    "Position",
    "Direction",
    "Rect",
    # Terrain
    "Terrain",
    "Weather",
    "TerrainProperties",
    "TERRAIN_DEFAULTS",
    "is_passable",
    "get_symbol",
    "get_gather_resource",
    # World
    "Cell",
    "Grid",
    # Objects
    "WorldObject",
    "Sign",
    "PlacedItem",
    "Item",
    "AnyWorldObject",
    "generate_object_id",
    # Structures
    "Structure",
    # Agent
    "JourneyDestination",
    "Journey",
    "InventoryStack",
    "Inventory",
    "AgentModel",
    "Agent",
    # Events
    "BaseEvent",
    "AgentMovedEvent",
    "JourneyStartedEvent",
    "JourneyInterruptedEvent",
    "JourneyCompletedEvent",
    "ObjectCreatedEvent",
    "ObjectRemovedEvent",
    "SignWrittenEvent",
    "WallPlacedEvent",
    "WallRemovedEvent",
    "DoorPlacedEvent",
    "StructureDetectedEvent",
    "PlaceNamedEvent",
    "ItemGatheredEvent",
    "ItemDroppedEvent",
    "ItemGivenEvent",
    "ItemCraftedEvent",
    "ItemTakenEvent",
    "AgentSleptEvent",
    "AgentWokeEvent",
    "AgentsMetEvent",
    "AgentSessionUpdatedEvent",
    "WorldEventOccurredEvent",
    "WeatherChangedEvent",
    "TimeAdvancedEvent",
    "ConversationStartedEvent",
    "ConversationEndedEvent",
    "DomainEvent",
]
