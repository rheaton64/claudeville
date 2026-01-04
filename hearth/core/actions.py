"""Action types for Hearth.

Actions are agent intents that the ActionEngine validates and executes.
Each action type is a frozen Pydantic model with a type discriminator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Discriminator

from .types import Position, Direction, AgentName, ObjectId, LandmarkName


class BaseAction(BaseModel):
    """Base class for all actions.

    All actions have a type discriminator field.
    """

    model_config = ConfigDict(frozen=True)


# --- Movement Actions ---


class WalkAction(BaseAction):
    """Move one cell in a direction."""

    type: Literal["walk"] = "walk"
    direction: Direction


class ApproachAction(BaseAction):
    """Move toward a visible object or agent.

    Target can be an ObjectId or AgentName.
    """

    type: Literal["approach"] = "approach"
    target: str  # ObjectId or AgentName as string


class JourneyAction(BaseAction):
    """Begin multi-cell travel to a distant location.

    Destination can be a Position or a named landmark.
    """

    type: Literal["journey"] = "journey"
    destination: Position | str  # Position or LandmarkName


# --- Perception Actions ---


class LookAction(BaseAction):
    """Survey surroundings.

    Returns information about visible cells, objects, and agents.
    """

    type: Literal["look"] = "look"


class ExamineAction(BaseAction):
    """Inspect something closely in a direction.

    Look north, south, east, west, or down (current cell).
    """

    type: Literal["examine"] = "examine"
    direction: str  # "north", "south", "east", "west", or "down"


class SenseOthersAction(BaseAction):
    """Feel direction toward known agents.

    Returns direction and rough distance to agents the actor has met.
    """

    type: Literal["sense_others"] = "sense_others"


# --- Interaction Actions ---


class TakeAction(BaseAction):
    """Pick up an object from nearby.

    Look north, south, east, west, or down (current cell).
    """

    type: Literal["take"] = "take"
    direction: str  # "north", "south", "east", "west", or "down"


class DropAction(BaseAction):
    """Put something down from inventory.

    Either item_id (for unique items) or item_type (for stackable resources).
    """

    type: Literal["drop"] = "drop"
    item_type: str | None = None  # For stackable resources
    item_id: ObjectId | None = None  # For unique items
    quantity: int = 1


class GiveAction(BaseAction):
    """Offer item to another agent.

    Either item_id (for unique items) or item_type (for stackable resources).
    """

    type: Literal["give"] = "give"
    recipient: AgentName
    item_type: str | None = None
    item_id: ObjectId | None = None
    quantity: int = 1


class GatherAction(BaseAction):
    """Collect resource from environment.

    Resource type can be specified or inferred from terrain.
    """

    type: Literal["gather"] = "gather"
    resource_type: str | None = None  # Optional - infer from terrain if not specified


# --- Material Actions (stubs for Phase 7) ---


class CombineAction(BaseAction):
    """Combine multiple items to craft something new.

    Items can be item IDs (for unique items) or type names (for stackable resources).
    Requires at least 2 items. Some recipes require 3 or more.
    """

    type: Literal["combine"] = "combine"
    items: tuple[str, ...]  # Item IDs or types (minimum 2)


class WorkAction(BaseAction):
    """Shape/modify material (stub - Phase 7 Crafting System).

    Techniques: hollow, flatten, carve, weave, coil, etc.
    """

    type: Literal["work"] = "work"
    material: str  # Item ID or type
    technique: str


class ApplyAction(BaseAction):
    """Use tool on something (stub - Phase 7 Crafting System)."""

    type: Literal["apply"] = "apply"
    tool: str  # Item ID or type
    target: str  # Item ID or type


# --- Building Actions ---


class BuildShelterAction(BaseAction):
    """Create a simple structure quickly.

    Places walls on all four sides of current cell with a door.
    Requires building materials (wood).
    """

    type: Literal["build_shelter"] = "build_shelter"


class PlaceWallAction(BaseAction):
    """Add wall to cell edge.

    Requires building materials.
    """

    type: Literal["place_wall"] = "place_wall"
    direction: Direction


class PlaceDoorAction(BaseAction):
    """Add door to existing wall.

    Direction must have a wall already.
    """

    type: Literal["place_door"] = "place_door"
    direction: Direction


class PlaceItemAction(BaseAction):
    """Put item in world as PlacedItem.

    Either item_id (for unique items) or item_type (for stackable resources).
    """

    type: Literal["place_item"] = "place_item"
    item_type: str | None = None
    item_id: ObjectId | None = None


class RemoveWallAction(BaseAction):
    """Remove wall from cell edge."""

    type: Literal["remove_wall"] = "remove_wall"
    direction: Direction


# --- Expression Actions ---


class WriteSignAction(BaseAction):
    """Create readable marker at current location."""

    type: Literal["write_sign"] = "write_sign"
    text: str


class ReadSignAction(BaseAction):
    """Read a sign nearby.

    Look north, south, east, west, or down (current cell).
    """

    type: Literal["read_sign"] = "read_sign"
    direction: str  # "north", "south", "east", "west", or "down"


class NamePlaceAction(BaseAction):
    """Name current location."""

    type: Literal["name_place"] = "name_place"
    name: str


# --- Social Actions (stubs for Phase 13) ---


class SpeakAction(BaseAction):
    """Say something aloud (stub - Phase 13 Conversation System)."""

    type: Literal["speak"] = "speak"
    message: str


class InviteAction(BaseAction):
    """Initiate conversation (stub - Phase 13 Conversation System)."""

    type: Literal["invite"] = "invite"
    agent: AgentName
    privacy: Literal["public", "private"] = "public"


class AcceptInviteAction(BaseAction):
    """Accept pending invitation (stub - Phase 13 Conversation System)."""

    type: Literal["accept_invite"] = "accept_invite"


class DeclineInviteAction(BaseAction):
    """Decline pending invitation (stub - Phase 13 Conversation System)."""

    type: Literal["decline_invite"] = "decline_invite"


class JoinConversationAction(BaseAction):
    """Join public conversation (stub - Phase 13 Conversation System).

    Specify someone in the conversation to join.
    """

    type: Literal["join_conversation"] = "join_conversation"
    participant: AgentName


class LeaveConversationAction(BaseAction):
    """Exit conversation (stub - Phase 13 Conversation System)."""

    type: Literal["leave_conversation"] = "leave_conversation"


# --- State Actions ---


class SleepAction(BaseAction):
    """Full rest - go to sleep.

    Sets agent to sleeping state until woken.
    """

    type: Literal["sleep"] = "sleep"


# --- Discriminated Union ---


Action = Annotated[
    Union[
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
    ],
    Discriminator("type"),
]


# --- Action Result ---


# Import here to avoid circular import with events
from .events import DomainEvent  # noqa: E402


@dataclass(frozen=True)
class ActionResult:
    """Result of executing an action.

    Attributes:
        success: Whether the action succeeded
        message: Human-readable message for narrator to elaborate
        events: Domain events produced (to be logged)
        data: Action-specific data for narrator context
    """

    success: bool
    message: str
    events: tuple[DomainEvent, ...] = ()
    data: dict[str, Any] | None = None

    @classmethod
    def ok(
        cls,
        message: str,
        events: list[DomainEvent] | None = None,
        data: dict[str, Any] | None = None,
    ) -> ActionResult:
        """Create a successful result."""
        return cls(
            success=True,
            message=message,
            events=tuple(events or []),
            data=data,
        )

    @classmethod
    def fail(
        cls, message: str, data: dict[str, Any] | None = None
    ) -> ActionResult:
        """Create a failure result."""
        return cls(success=False, message=message, data=data)

    @classmethod
    def not_implemented(cls, action_type: str) -> ActionResult:
        """Create a 'not implemented' result for stub actions."""
        return cls(
            success=False,
            message=f"The {action_type} action is not yet available in this world.",
        )
