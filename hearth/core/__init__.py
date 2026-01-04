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
from .world import Cell, Grid, WorldState

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

# Conversation
from .conversation import (
    INVITE_EXPIRY_TICKS,
    ConversationTurn,
    Invitation,
    Conversation,
    ConversationContext,
)

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
    InvitationSentEvent,
    InvitationAcceptedEvent,
    InvitationDeclinedEvent,
    InvitationExpiredEvent,
    ConversationStartedEvent,
    AgentJoinedConversationEvent,
    AgentLeftConversationEvent,
    ConversationTurnEvent,
    ConversationEndedEvent,
    # Union type
    DomainEvent,
)

# Constants
from .constants import (
    HEARTH_TZ,
    DEFAULT_VISION_RADIUS,
    NIGHT_VISION_MODIFIER,
)

# Actions
from .actions import (
    BaseAction,
    # Movement
    WalkAction,
    ApproachAction,
    JourneyAction,
    # Perception
    LookAction,
    ExamineAction,
    SenseOthersAction,
    # Interaction
    TakeAction,
    DropAction,
    GiveAction,
    GatherAction,
    # Material (stubs)
    CombineAction,
    WorkAction,
    ApplyAction,
    # Building
    BuildShelterAction,
    PlaceWallAction,
    PlaceDoorAction,
    PlaceItemAction,
    RemoveWallAction,
    # Expression
    WriteSignAction,
    ReadSignAction,
    NamePlaceAction,
    # Social (stubs)
    SpeakAction,
    InviteAction,
    AcceptInviteAction,
    DeclineInviteAction,
    JoinConversationAction,
    LeaveConversationAction,
    # State
    SleepAction,
    # Union type
    Action,
    # Result
    ActionResult,
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
    "WorldState",
    # Objects
    "WorldObject",
    "Sign",
    "PlacedItem",
    "Item",
    "AnyWorldObject",
    "generate_object_id",
    # Structures
    "Structure",
    # Conversation
    "INVITE_EXPIRY_TICKS",
    "ConversationTurn",
    "Invitation",
    "Conversation",
    "ConversationContext",
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
    "InvitationSentEvent",
    "InvitationAcceptedEvent",
    "InvitationDeclinedEvent",
    "InvitationExpiredEvent",
    "ConversationStartedEvent",
    "AgentJoinedConversationEvent",
    "AgentLeftConversationEvent",
    "ConversationTurnEvent",
    "ConversationEndedEvent",
    "DomainEvent",
    # Actions
    "BaseAction",
    "WalkAction",
    "ApproachAction",
    "JourneyAction",
    "LookAction",
    "ExamineAction",
    "SenseOthersAction",
    "TakeAction",
    "DropAction",
    "GiveAction",
    "GatherAction",
    "CombineAction",
    "WorkAction",
    "ApplyAction",
    "BuildShelterAction",
    "PlaceWallAction",
    "PlaceDoorAction",
    "PlaceItemAction",
    "RemoveWallAction",
    "WriteSignAction",
    "ReadSignAction",
    "NamePlaceAction",
    "SpeakAction",
    "InviteAction",
    "AcceptInviteAction",
    "DeclineInviteAction",
    "JoinConversationAction",
    "LeaveConversationAction",
    "SleepAction",
    "Action",
    "ActionResult",
    # Constants
    "HEARTH_TZ",
    "DEFAULT_VISION_RADIUS",
    "NIGHT_VISION_MODIFIER",
]
