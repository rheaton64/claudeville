"""Action engine for Hearth.

Validates and executes agent actions, producing ActionResults and DomainEvents.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import TYPE_CHECKING, Any

from core.types import Position, Direction, AgentName, ObjectId, Rect
from core.constants import HEARTH_TZ
from core.terrain import Terrain
from core.agent import Agent
from core.objects import Sign, PlacedItem, Item, generate_object_id
from core.events import (
    AgentMovedEvent,
    JourneyStartedEvent,
    ItemGatheredEvent,
    ItemDroppedEvent,
    ItemGivenEvent,
    ItemTakenEvent,
    ItemCraftedEvent,
    SignWrittenEvent,
    WallPlacedEvent,
    WallRemovedEvent,
    DoorPlacedEvent,
    PlaceNamedEvent,
    AgentSleptEvent,
    ObjectCreatedEvent,
    # Conversation events
    InvitationSentEvent,
    InvitationAcceptedEvent,
    InvitationDeclinedEvent,
    ConversationStartedEvent,
    AgentJoinedConversationEvent,
    AgentLeftConversationEvent,
    ConversationTurnEvent,
    ConversationEndedEvent,
)
from core.actions import (
    Action,
    ActionResult,
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
)

if TYPE_CHECKING:
    from storage import Storage
    from .world_service import WorldService
    from .agent_service import AgentService
    from .crafting import CraftingService
    from .conversation import ConversationService


# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

# Resources that can be gathered from terrain and stack in inventory.
# Any item_type NOT in this set is treated as a unique item.
RESOURCE_TYPES: frozenset[str] = frozenset({"wood", "stone", "clay", "grass"})

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def serialize_for_narrator(data: dict[str, Any] | None) -> dict[str, Any] | None:
    """Serialize data for JSON compatibility in narrator.

    Converts Position objects to dicts so json.dumps() won't fail.

    Args:
        data: Action result data (may contain Position objects)

    Returns:
        Serialized data safe for JSON encoding
    """
    if data is None:
        return None

    result: dict[str, Any] = {}
    for k, v in data.items():
        if isinstance(v, Position):
            result[k] = {"x": v.x, "y": v.y}
        elif isinstance(v, dict):
            result[k] = serialize_for_narrator(v)
        elif isinstance(v, list):
            result[k] = [
                {"x": item.x, "y": item.y} if isinstance(item, Position) else item
                for item in v
            ]
        else:
            result[k] = v
    return result


# -----------------------------------------------------------------------------
# Exceptions
# -----------------------------------------------------------------------------


class ActionEngineError(Exception):
    """Base exception for ActionEngine errors."""

    pass


# -----------------------------------------------------------------------------
# ActionEngine
# -----------------------------------------------------------------------------


class ActionEngine:
    """Validates and executes agent actions.

    The ActionEngine is the core of the action system. It:
    1. Receives an action from an agent
    2. Validates prerequisites (position, inventory, etc.)
    3. Executes the action (updating state via services)
    4. Returns an ActionResult with events for logging

    All methods are async and use WorldService/AgentService for state changes.
    """

    def __init__(
        self,
        storage: "Storage",
        world_service: "WorldService",
        agent_service: "AgentService",
        crafting_service: "CraftingService | None" = None,
        conversation_service: "ConversationService | None" = None,
        vision_radius: int | None = None,
    ):
        """Initialize ActionEngine.

        Args:
            storage: Connected Storage instance
            world_service: WorldService for world state operations
            agent_service: AgentService for agent state operations
            crafting_service: CraftingService for crafting operations (optional)
            conversation_service: ConversationService for social actions (optional)
            vision_radius: Vision radius for visibility checks (default: DEFAULT_VISION_RADIUS)
        """
        from core.constants import DEFAULT_VISION_RADIUS

        self._storage = storage
        self._world = world_service
        self._agents = agent_service
        self._crafting = crafting_service
        self._conversation = conversation_service
        self._vision_radius = vision_radius or DEFAULT_VISION_RADIUS
        self._time_of_day: str = "morning"

    def set_time_of_day(self, time_of_day: str) -> None:
        """Set the current time of day for vision calculations.

        Should be called before executing actions each tick.

        Args:
            time_of_day: "morning", "afternoon", "evening", or "night"
        """
        self._time_of_day = time_of_day

    def _get_effective_vision_radius(self) -> int:
        """Get vision radius accounting for time of day.

        At night, vision is reduced by NIGHT_VISION_MODIFIER (0.6).

        Returns:
            Effective vision radius (minimum 1)
        """
        from core.constants import NIGHT_VISION_MODIFIER

        if self._time_of_day == "night":
            return max(1, int(self._vision_radius * NIGHT_VISION_MODIFIER))
        return self._vision_radius

    async def execute(
        self,
        agent: Agent,
        action: Action,
        tick: int,
    ) -> ActionResult:
        """Execute an action for an agent.

        Dispatches to the appropriate handler based on action type.

        Args:
            agent: The agent performing the action
            action: The action to execute
            tick: Current simulation tick

        Returns:
            ActionResult with success status, message, and events
        """
        # Always work with current state from DB to handle:
        # - Multiple actions within a single turn (e.g., gather then drop)
        # - Sequential agents within a cluster seeing each other's changes
        agent = await self._agents.get_agent_or_raise(agent.name)

        # Dispatch based on action type
        handlers = {
            "walk": self._execute_walk,
            "approach": self._execute_approach,
            "journey": self._execute_journey,
            "look": self._execute_look,
            "examine": self._execute_examine,
            "sense_others": self._execute_sense_others,
            "take": self._execute_take,
            "drop": self._execute_drop,
            "give": self._execute_give,
            "gather": self._execute_gather,
            "combine": self._execute_combine,
            "work": self._execute_work,
            "apply": self._execute_apply,
            "build_shelter": self._execute_build_shelter,
            "place_wall": self._execute_place_wall,
            "place_door": self._execute_place_door,
            "place_item": self._execute_place_item,
            "remove_wall": self._execute_remove_wall,
            "write_sign": self._execute_write_sign,
            "read_sign": self._execute_read_sign,
            "name_place": self._execute_name_place,
            "speak": self._execute_speak,
            "invite": self._execute_invite,
            "accept_invite": self._execute_accept_invite,
            "decline_invite": self._execute_decline_invite,
            "join_conversation": self._execute_join_conversation,
            "leave_conversation": self._execute_leave_conversation,
            "sleep": self._execute_sleep,
        }

        handler = handlers.get(action.type)
        if handler is None:
            return ActionResult.fail(f"Unknown action type: {action.type}")

        return await handler(agent, action, tick)

    # -------------------------------------------------------------------------
    # Direction Helper
    # -------------------------------------------------------------------------

    def _resolve_direction_to_position(
        self, agent_pos: Position, direction: str
    ) -> Position:
        """Convert direction string to target position.

        Args:
            agent_pos: Agent's current position
            direction: "north", "south", "east", "west", or "down"

        Returns:
            Target position (agent's position for "down", adjacent cell otherwise)

        Raises:
            ValueError: If direction is invalid
        """
        if direction.lower() == "down":
            return agent_pos

        dir_map = {
            "north": Direction.NORTH,
            "south": Direction.SOUTH,
            "east": Direction.EAST,
            "west": Direction.WEST,
        }
        d = dir_map.get(direction.lower())
        if d is None:
            raise ValueError(f"Invalid direction: {direction}")
        return agent_pos + d

    # -------------------------------------------------------------------------
    # Movement Actions
    # -------------------------------------------------------------------------

    async def _execute_walk(
        self, agent: Agent, action: WalkAction, tick: int
    ) -> ActionResult:
        """Move agent one cell in a direction."""
        direction = action.direction
        from_pos = agent.position

        # Check if movement is possible
        if not await self._world.can_move(from_pos, direction):
            return ActionResult.fail(
                f"Cannot move {direction.value} - path is blocked."
            )

        to_pos = from_pos + direction

        # Update agent position
        await self._agents.update_position(agent.name, to_pos)

        event = AgentMovedEvent(
            tick=tick,
            timestamp=datetime.now(HEARTH_TZ),
            agent=agent.name,
            from_position=from_pos,
            to_position=to_pos,
        )

        return ActionResult.ok(
            f"Moved {direction.value}.",
            events=[event],
            data={"direction": direction.value, "new_position": to_pos},
        )

    async def _execute_approach(
        self, agent: Agent, action: ApproachAction, tick: int
    ) -> ActionResult:
        """Move toward a visible object or agent."""
        target = action.target

        # Find target position and verify visibility
        target_pos: Position | None = None

        # Try as AgentName first
        target_agent = await self._agents.get_agent(AgentName(target))
        if target_agent:
            # Verify agent is within vision range
            nearby = await self._agents.get_nearby_agents(
                agent.position, self._get_effective_vision_radius()
            )
            if not any(a.name == target_agent.name for a in nearby):
                return ActionResult.fail(f"You don't see {target} nearby.")
            target_pos = target_agent.position
        else:
            # Try as ObjectId
            obj = await self._storage.objects.get_object(ObjectId(target))
            if obj:
                # Verify object is within vision range
                if agent.position.distance_to(obj.position) > self._get_effective_vision_radius():
                    return ActionResult.fail("You don't see that object.")
                target_pos = obj.position

        if target_pos is None:
            return ActionResult.fail(f"Cannot find {target} to approach.")

        # Already at target?
        if agent.position == target_pos:
            return ActionResult.fail("Already at that location.")

        # Find direction to move
        direction = agent.position.direction_to(target_pos)
        if direction is None:
            return ActionResult.fail("Already at that location.")

        # Check if can move in that direction
        if not await self._world.can_move(agent.position, direction):
            return ActionResult.fail(f"Cannot move toward {target} - path blocked.")

        from_pos = agent.position
        to_pos = agent.position + direction
        await self._agents.update_position(agent.name, to_pos)

        event = AgentMovedEvent(
            tick=tick,
            timestamp=datetime.now(HEARTH_TZ),
            agent=agent.name,
            from_position=from_pos,
            to_position=to_pos,
        )

        return ActionResult.ok(
            f"Moved toward {target}.",
            events=[event],
            data={"target": target, "new_position": to_pos},
        )

    async def _execute_journey(
        self, agent: Agent, action: JourneyAction, tick: int
    ) -> ActionResult:
        """Begin multi-cell journey to destination."""
        destination = action.destination

        # Resolve destination to Position if it's a landmark name
        if isinstance(destination, str):
            dest_pos = await self._world.get_place_position(destination)
            if dest_pos is None:
                return ActionResult.fail(f"Unknown destination: {destination}")
        else:
            dest_pos = destination

        try:
            await self._agents.start_journey(agent.name, dest_pos, self._world)
        except Exception as e:
            return ActionResult.fail(f"Cannot journey there: {e}")

        # Get updated agent to find path length
        updated = await self._agents.get_agent_or_raise(agent.name)
        path_length = len(updated.journey.path) if updated.journey else 0

        event = JourneyStartedEvent(
            tick=tick,
            timestamp=datetime.now(HEARTH_TZ),
            agent=agent.name,
            destination=dest_pos,
            path_length=path_length,
        )

        return ActionResult.ok(
            f"Began journey (approximately {path_length} steps).",
            events=[event],
            data={"destination": dest_pos, "path_length": path_length},
        )

    # -------------------------------------------------------------------------
    # Perception Actions
    # -------------------------------------------------------------------------

    async def _execute_look(
        self, agent: Agent, action: LookAction, tick: int
    ) -> ActionResult:
        """Survey surroundings."""
        # Get visible area (default radius of 10), clamped to world bounds
        radius = 10
        width, height = await self._world.get_world_dimensions()
        rect = Rect.around(agent.position, radius).clamp(width, height)

        cells = await self._world.get_cells_in_rect(rect)
        objects = await self._world.get_objects_in_rect(rect)
        nearby_agents = await self._agents.get_nearby_agents(agent.position, radius)
        # Exclude self
        nearby_agents = [a for a in nearby_agents if a.name != agent.name]

        return ActionResult.ok(
            "You survey your surroundings.",
            data={
                "cells": len(cells),
                "objects": [
                    {
                        "id": str(o.id),
                        "type": getattr(o, "object_type", "unknown"),
                        "position": o.position,
                    }
                    for o in objects
                ],
                "agents": [
                    {"name": str(a.name), "position": a.position}
                    for a in nearby_agents
                ],
                "center": agent.position,
                "radius": radius,
            },
        )

    async def _execute_examine(
        self, agent: Agent, action: ExamineAction, tick: int
    ) -> ActionResult:
        """Inspect something closely in a direction."""
        try:
            target_pos = self._resolve_direction_to_position(
                agent.position, action.direction
            )
        except ValueError:
            return ActionResult.fail(
                "Look north, south, east, west, or down at your feet."
            )

        # Get the cell at target position
        cell = await self._world.get_cell(target_pos)

        # Check for objects at that position
        objects = await self._world.get_objects_at(target_pos)

        # Check for agents at that position
        agents_there = await self._agents.get_agents_at(target_pos)
        other_agents = [a for a in agents_there if a.name != agent.name]

        # Build response data
        data: dict = {
            "direction": action.direction,
            "position": {"x": target_pos.x, "y": target_pos.y},
            "terrain": cell.terrain.value,
        }

        if cell.walls:
            data["walls"] = [d.value for d in cell.walls]
        if cell.doors:
            data["doors"] = [d.value for d in cell.doors]
        if cell.place_name:
            data["place_name"] = cell.place_name

        if objects:
            data["objects"] = [
                {
                    "type": getattr(obj, "object_type", "unknown"),
                    "text": getattr(obj, "text", None),
                    "properties": list(getattr(obj, "properties", [])),
                }
                for obj in objects
            ]

        if other_agents:
            data["agents"] = [
                {
                    "name": str(a.name),
                    "is_sleeping": a.is_sleeping,
                    "is_journeying": a.is_journeying,
                }
                for a in other_agents
            ]

        direction_phrase = (
            "beneath you" if action.direction.lower() == "down"
            else f"to the {action.direction}"
        )
        return ActionResult.ok(
            f"You examine what lies {direction_phrase}.",
            data=data,
        )

    async def _execute_sense_others(
        self, agent: Agent, action: SenseOthersAction, tick: int
    ) -> ActionResult:
        """Feel direction toward known agents."""
        sensed = await self._agents.sense_others(agent.name)

        return ActionResult.ok(
            "You reach out with your senses.",
            data={
                "sensed": [
                    {
                        "name": str(s.name),
                        "direction": s.direction.value if s.direction else None,
                        "distance": s.distance_category,
                    }
                    for s in sensed
                ],
            },
        )

    # -------------------------------------------------------------------------
    # Interaction Actions
    # -------------------------------------------------------------------------

    async def _execute_take(
        self, agent: Agent, action: TakeAction, tick: int
    ) -> ActionResult:
        """Pick up an object from nearby in a direction."""
        try:
            target_pos = self._resolve_direction_to_position(
                agent.position, action.direction
            )
        except ValueError:
            return ActionResult.fail(
                "Look north, south, east, west, or down at your feet."
            )

        # Find takeable objects at that position
        objects = await self._world.get_objects_at(target_pos)
        placed_items = [obj for obj in objects if isinstance(obj, PlacedItem)]

        if not placed_items:
            direction_phrase = (
                "at your feet" if action.direction.lower() == "down"
                else f"to the {action.direction}"
            )
            return ActionResult.fail(f"Nothing to pick up {direction_phrase}.")

        # Take the first placed item found
        obj = placed_items[0]

        # Remove from world
        await self._world.remove_object(obj.id)

        # Add to inventory - stackable resources vs unique items
        if obj.item_type in RESOURCE_TYPES:
            # Stackable resource (wood, stone, clay, grass) - add to resource stacks
            await self._agents.add_resource(agent.name, obj.item_type, obj.quantity)
        else:
            # Unique item (crafted, placed, etc.) - add as unique item
            item = Item(
                id=obj.id,
                item_type=obj.item_type,
                properties=obj.properties,
                quantity=1,
            )
            await self._agents.add_item(agent.name, item)

        event = ItemTakenEvent(
            tick=tick,
            timestamp=datetime.now(HEARTH_TZ),
            agent=agent.name,
            object_id=obj.id,
            item_type=obj.item_type,
            from_position=obj.position,
        )

        quantity_str = f"{obj.quantity} " if obj.quantity > 1 else ""
        return ActionResult.ok(
            f"Picked up {quantity_str}{obj.item_type}.",
            events=[event],
            data={"item_type": obj.item_type, "quantity": obj.quantity},
        )

    async def _execute_drop(
        self, agent: Agent, action: DropAction, tick: int
    ) -> ActionResult:
        """Put something down from inventory."""
        item_type = action.item_type
        item_id = action.item_id
        quantity = action.quantity

        if item_id:
            # Dropping a unique item
            item = agent.inventory.get_item(item_id)
            if item is None:
                return ActionResult.fail("You don't have that item.")

            await self._agents.remove_item(agent.name, item_id)

            placed = item.to_placed_item(
                position=agent.position,
                created_by=agent.name,
                created_tick=tick,
            )
            await self._world.place_object(placed)

            event = ItemDroppedEvent(
                tick=tick,
                timestamp=datetime.now(HEARTH_TZ),
                agent=agent.name,
                item_type=item.item_type,
                quantity=1,
                at_position=agent.position,
            )

            return ActionResult.ok(
                f"Dropped {item.item_type}.",
                events=[event],
            )

        elif item_type:
            # Dropping stackable resource
            if not agent.inventory.has_resource(item_type, quantity):
                return ActionResult.fail(f"You don't have enough {item_type}.")

            await self._agents.remove_resource(agent.name, item_type, quantity)

            # Create placed item for dropped resources with quantity
            placed = PlacedItem(
                id=generate_object_id(),
                position=agent.position,
                created_by=agent.name,
                created_tick=tick,
                item_type=item_type,
                quantity=quantity,
            )
            await self._world.place_object(placed)

            event = ItemDroppedEvent(
                tick=tick,
                timestamp=datetime.now(HEARTH_TZ),
                agent=agent.name,
                item_type=item_type,
                quantity=quantity,
                at_position=agent.position,
            )

            return ActionResult.ok(
                f"Dropped {quantity} {item_type}.",
                events=[event],
            )

        return ActionResult.fail("Specify what to drop.")

    async def _execute_give(
        self, agent: Agent, action: GiveAction, tick: int
    ) -> ActionResult:
        """Offer item to another agent."""
        recipient = await self._agents.get_agent(action.recipient)

        if recipient is None:
            return ActionResult.fail(f"{action.recipient} is not here.")

        if agent.position.distance_to(recipient.position) > 1:
            return ActionResult.fail("Too far away to give.")

        if action.item_id:
            # Give unique item
            item = agent.inventory.get_item(action.item_id)
            if item is None:
                return ActionResult.fail("You don't have that item.")

            await self._agents.remove_item(agent.name, action.item_id)
            await self._agents.add_item(action.recipient, item)

            event = ItemGivenEvent(
                tick=tick,
                timestamp=datetime.now(HEARTH_TZ),
                giver=agent.name,
                receiver=action.recipient,
                item_type=item.item_type,
                quantity=1,
            )

            return ActionResult.ok(
                f"Gave {item.item_type} to {action.recipient}.",
                events=[event],
            )

        elif action.item_type:
            # Give stackable resource
            if not agent.inventory.has_resource(action.item_type, action.quantity):
                return ActionResult.fail(f"You don't have enough {action.item_type}.")

            await self._agents.remove_resource(
                agent.name, action.item_type, action.quantity
            )
            await self._agents.add_resource(
                action.recipient, action.item_type, action.quantity
            )

            event = ItemGivenEvent(
                tick=tick,
                timestamp=datetime.now(HEARTH_TZ),
                giver=agent.name,
                receiver=action.recipient,
                item_type=action.item_type,
                quantity=action.quantity,
            )

            return ActionResult.ok(
                f"Gave {action.quantity} {action.item_type} to {action.recipient}.",
                events=[event],
            )

        return ActionResult.fail("Specify what to give.")

    async def _execute_gather(
        self, agent: Agent, action: GatherAction, tick: int
    ) -> ActionResult:
        """Collect resource from environment."""
        cell = await self._world.get_cell(agent.position)
        terrain_resource = self._world.get_gather_resource(cell.terrain)

        resource = action.resource_type or terrain_resource

        if resource is None:
            return ActionResult.fail("Nothing to gather here.")

        if action.resource_type and action.resource_type != terrain_resource:
            return ActionResult.fail(f"Cannot gather {action.resource_type} here.")

        # Add to inventory
        await self._agents.add_resource(agent.name, resource, 1)

        event = ItemGatheredEvent(
            tick=tick,
            timestamp=datetime.now(HEARTH_TZ),
            agent=agent.name,
            item_type=resource,
            quantity=1,
            from_position=agent.position,
        )

        return ActionResult.ok(
            f"Gathered {resource}.",
            events=[event],
            data={"resource": resource},
        )

    # -------------------------------------------------------------------------
    # Material Actions (Crafting)
    # -------------------------------------------------------------------------

    async def _execute_combine(
        self, agent: Agent, action: CombineAction, tick: int
    ) -> ActionResult:
        """Combine multiple items to craft something new."""
        if self._crafting is None:
            return ActionResult.fail("Crafting is not available.")

        # Validate minimum items
        if len(action.items) < 2:
            return ActionResult.fail("Need at least 2 items to combine.")

        # Resolve all inputs to item types
        item_types: list[str] = []
        for item_ref in action.items:
            item_type = self._resolve_item_type(agent, item_ref)
            if item_type is None:
                return ActionResult.fail(f"You don't have {item_ref}.")
            item_types.append(item_type)

        # Count required quantities for each type
        type_counts = Counter(item_types)

        # Verify agent has enough of each type
        for item_type, required_count in type_counts.items():
            if agent.inventory.has_resource(item_type):
                if not agent.inventory.has_resource(item_type, required_count):
                    return ActionResult.fail(
                        f"You need at least {required_count} {item_type}."
                    )
            else:
                # Check unique items
                matching_items = [
                    i for i in agent.inventory.items if i.item_type == item_type
                ]
                if len(matching_items) < required_count:
                    return ActionResult.fail(
                        f"You need at least {required_count} {item_type}."
                    )

        # Try to craft
        result = self._crafting.try_craft("combine", item_types)

        if not result.success:
            hint_text = ""
            if result.hints:
                hint_text = " " + result.hints[0]
            return ActionResult.fail(
                f"These materials don't combine in any useful way.{hint_text}",
                data={"hints": list(result.hints)},
            )

        # Consume inputs - pair each item_ref with its resolved type
        for item_ref, item_type in zip(action.items, item_types):
            await self._consume_item(agent.name, item_ref, item_type)

        # Add output to inventory
        output = result.output_item
        if output.is_stackable:
            await self._agents.add_resource(
                agent.name, output.item_type, output.quantity
            )
        else:
            await self._agents.add_item(agent.name, output)

        event = ItemCraftedEvent(
            tick=tick,
            timestamp=datetime.now(HEARTH_TZ),
            agent=agent.name,
            inputs=tuple(item_types),
            output=output.item_type,
            technique=None,  # combine doesn't use technique
        )

        return ActionResult.ok(
            f"Created {output.item_type}. {result.message}",
            events=[event],
            data={
                "output": output.item_type,
                "quantity": output.quantity,
                "properties": list(output.properties),
                "discoveries": list(result.discoveries),
            },
        )

    async def _execute_work(
        self, agent: Agent, action: WorkAction, tick: int
    ) -> ActionResult:
        """Work material with a technique to shape it."""
        if self._crafting is None:
            return ActionResult.fail("Crafting is not available.")

        # Resolve material to item type
        material_type = self._resolve_item_type(agent, action.material)

        if material_type is None:
            return ActionResult.fail(f"You don't have {action.material}.")

        # Check inventory
        if not self._has_item_for_crafting(agent, action.material, material_type):
            return ActionResult.fail(f"You don't have {action.material}.")

        # Try to craft with technique
        result = self._crafting.try_craft("work", [material_type], action.technique)

        if not result.success:
            hint_text = ""
            if result.hints:
                hint_text = " " + result.hints[0]
            return ActionResult.fail(
                f"The {action.technique} technique doesn't work on {material_type}.{hint_text}",
                data={"hints": list(result.hints)},
            )

        # Consume input
        await self._consume_item(agent.name, action.material, material_type)

        # Add output to inventory
        output = result.output_item
        if output.is_stackable:
            await self._agents.add_resource(
                agent.name, output.item_type, output.quantity
            )
        else:
            await self._agents.add_item(agent.name, output)

        event = ItemCraftedEvent(
            tick=tick,
            timestamp=datetime.now(HEARTH_TZ),
            agent=agent.name,
            inputs=(material_type,),
            output=output.item_type,
            technique=action.technique,
        )

        return ActionResult.ok(
            f"Created {output.item_type}. {result.message}",
            events=[event],
            data={
                "output": output.item_type,
                "quantity": output.quantity,
                "properties": list(output.properties),
                "discoveries": list(result.discoveries),
            },
        )

    async def _execute_apply(
        self, agent: Agent, action: ApplyAction, tick: int
    ) -> ActionResult:
        """Apply a tool to a target to transform it."""
        if self._crafting is None:
            return ActionResult.fail("Crafting is not available.")

        # Resolve tool and target to item types
        tool_type = self._resolve_item_type(agent, action.tool)
        target_type = self._resolve_item_type(agent, action.target)

        if tool_type is None:
            return ActionResult.fail(f"You don't have {action.tool}.")
        if target_type is None:
            return ActionResult.fail(f"You don't have {action.target}.")

        # Check inventory
        if not self._has_item_for_crafting(agent, action.tool, tool_type):
            return ActionResult.fail(f"You don't have {action.tool}.")
        if not self._has_item_for_crafting(agent, action.target, target_type):
            return ActionResult.fail(f"You don't have {action.target}.")

        # Check tool has appropriate property (for unique items)
        # Accept items with 'tool' or 'heat' property (heat sources can apply heat)
        tool_item = self._get_unique_item(agent, action.tool)
        if tool_item:
            has_tool = "tool" in tool_item.properties
            has_heat = "heat" in tool_item.properties
            if not (has_tool or has_heat):
                return ActionResult.fail(f"The {tool_type} cannot be used this way.")

        # Try to apply
        result = self._crafting.try_apply(tool_type, target_type)

        if not result.success:
            hint_text = ""
            if result.hints:
                hint_text = " " + result.hints[0]
            return ActionResult.fail(
                f"The {tool_type} doesn't do anything useful to the {target_type}.{hint_text}",
                data={"hints": list(result.hints)},
            )

        # Only consume target, keep tool
        await self._consume_item(agent.name, action.target, target_type)

        # Add output to inventory
        output = result.output_item
        if output.is_stackable:
            await self._agents.add_resource(
                agent.name, output.item_type, output.quantity
            )
        else:
            await self._agents.add_item(agent.name, output)

        event = ItemCraftedEvent(
            tick=tick,
            timestamp=datetime.now(HEARTH_TZ),
            agent=agent.name,
            inputs=(tool_type, target_type),
            output=output.item_type,
            technique=None,  # apply doesn't use technique
        )

        return ActionResult.ok(
            f"Created {output.item_type}. {result.message}",
            events=[event],
            data={
                "output": output.item_type,
                "quantity": output.quantity,
                "properties": list(output.properties),
                "discoveries": list(result.discoveries),
            },
        )

    # -------------------------------------------------------------------------
    # Crafting Helper Methods
    # -------------------------------------------------------------------------

    def _resolve_item_type(self, agent: Agent, item_ref: str) -> str | None:
        """Resolve an item reference to its type.

        Item ref can be:
        - An item type (for stackable resources)
        - An ObjectId (for unique items)

        Returns the item_type or None if not found.
        """
        # Check if it's a stackable resource type
        if agent.inventory.has_resource(item_ref, 1):
            return item_ref

        # Check if it's a unique item ID
        item = agent.inventory.get_item(ObjectId(item_ref))
        if item:
            return item.item_type

        # Check if it's a unique item by type name
        for inv_item in agent.inventory.items:
            if inv_item.item_type == item_ref:
                return item_ref

        return None

    def _has_item_for_crafting(
        self, agent: Agent, item_ref: str, item_type: str
    ) -> bool:
        """Check if agent has the referenced item for crafting."""
        # Check stackable
        if agent.inventory.has_resource(item_type, 1):
            return True

        # Check unique items by ID
        if agent.inventory.get_item(ObjectId(item_ref)):
            return True

        # Check unique items by type
        for item in agent.inventory.items:
            if item.item_type == item_type:
                return True

        return False

    def _get_unique_item(self, agent: Agent, item_ref: str) -> Item | None:
        """Get a unique item by reference (ID or type)."""
        # Try by ID
        item = agent.inventory.get_item(ObjectId(item_ref))
        if item:
            return item

        # Try by type
        for inv_item in agent.inventory.items:
            if inv_item.item_type == item_ref:
                return inv_item

        return None

    async def _consume_item(
        self, agent_name: AgentName, item_ref: str, item_type: str
    ) -> None:
        """Consume an item from inventory for crafting."""
        # Get fresh agent state
        agent = await self._agents.get_agent_or_raise(agent_name)

        # Try to consume from stacks first
        if agent.inventory.has_resource(item_type, 1):
            await self._agents.remove_resource(agent_name, item_type, 1)
            return

        # Try to consume unique item by ID
        item = agent.inventory.get_item(ObjectId(item_ref))
        if item:
            await self._agents.remove_item(agent_name, item.id)
            return

        # Try to consume unique item by type
        for inv_item in agent.inventory.items:
            if inv_item.item_type == item_type:
                await self._agents.remove_item(agent_name, inv_item.id)
                return

    # -------------------------------------------------------------------------
    # Building Actions
    # -------------------------------------------------------------------------

    async def _execute_build_shelter(
        self, agent: Agent, action: BuildShelterAction, tick: int
    ) -> ActionResult:
        """Create a simple shelter structure."""
        # Quick shelter: walls on all four sides with a door facing south
        pos = agent.position

        # Check if we have materials
        if not agent.inventory.has_resource("wood", 4):
            return ActionResult.fail(
                "Need at least 4 wood to build a simple shelter."
            )

        # Remove materials
        await self._agents.remove_resource(agent.name, "wood", 4)

        # Place walls on all four sides of current cell
        events = []
        for direction in Direction:
            await self._world.place_wall(pos, direction)
            events.append(
                WallPlacedEvent(
                    tick=tick,
                    timestamp=datetime.now(HEARTH_TZ),
                    position=pos,
                    direction=direction,
                    builder=agent.name,
                )
            )

        # Add door on south side
        await self._world.place_door(pos, Direction.SOUTH)
        events.append(
            DoorPlacedEvent(
                tick=tick,
                timestamp=datetime.now(HEARTH_TZ),
                position=pos,
                direction=Direction.SOUTH,
                builder=agent.name,
            )
        )

        return ActionResult.ok(
            "Built a simple shelter around yourself.",
            events=events,
        )

    async def _execute_place_wall(
        self, agent: Agent, action: PlaceWallAction, tick: int
    ) -> ActionResult:
        """Add wall to cell edge."""
        pos = agent.position
        direction = action.direction

        # Check for materials
        if not agent.inventory.has_resource("wood", 1):
            return ActionResult.fail("Need wood to build a wall.")

        await self._agents.remove_resource(agent.name, "wood", 1)
        await self._world.place_wall(pos, direction)

        event = WallPlacedEvent(
            tick=tick,
            timestamp=datetime.now(HEARTH_TZ),
            position=pos,
            direction=direction,
            builder=agent.name,
        )

        return ActionResult.ok(
            f"Built a wall to the {direction.value}.",
            events=[event],
        )

    async def _execute_place_door(
        self, agent: Agent, action: PlaceDoorAction, tick: int
    ) -> ActionResult:
        """Add door to wall."""
        pos = agent.position
        direction = action.direction

        cell = await self._world.get_cell(pos)
        if direction not in cell.walls:
            return ActionResult.fail(
                f"No wall to the {direction.value} to put a door in."
            )

        if direction in cell.doors:
            return ActionResult.fail(f"Already a door to the {direction.value}.")

        await self._world.place_door(pos, direction)

        event = DoorPlacedEvent(
            tick=tick,
            timestamp=datetime.now(HEARTH_TZ),
            position=pos,
            direction=direction,
            builder=agent.name,
        )

        return ActionResult.ok(
            f"Added a door to the {direction.value} wall.",
            events=[event],
        )

    async def _execute_place_item(
        self, agent: Agent, action: PlaceItemAction, tick: int
    ) -> ActionResult:
        """Put item in world as PlacedItem."""
        item_id = action.item_id
        item_type = action.item_type

        if item_id:
            item = agent.inventory.get_item(item_id)
            if item is None:
                return ActionResult.fail("You don't have that item.")

            await self._agents.remove_item(agent.name, item_id)
            placed = item.to_placed_item(
                position=agent.position,
                created_by=agent.name,
                created_tick=tick,
            )
            await self._world.place_object(placed)

            event = ObjectCreatedEvent(
                tick=tick,
                timestamp=datetime.now(HEARTH_TZ),
                object_id=placed.id,
                object_type="placed_item",
                position=agent.position,
                creator=agent.name,
            )

            return ActionResult.ok(
                f"Placed {item.item_type}.",
                events=[event],
            )

        elif item_type:
            if not agent.inventory.has_resource(item_type, 1):
                return ActionResult.fail(f"You don't have any {item_type}.")

            await self._agents.remove_resource(agent.name, item_type, 1)
            placed = PlacedItem(
                id=generate_object_id(),
                position=agent.position,
                created_by=agent.name,
                created_tick=tick,
                item_type=item_type,
            )
            await self._world.place_object(placed)

            event = ObjectCreatedEvent(
                tick=tick,
                timestamp=datetime.now(HEARTH_TZ),
                object_id=placed.id,
                object_type="placed_item",
                position=agent.position,
                creator=agent.name,
            )

            return ActionResult.ok(
                f"Placed {item_type}.",
                events=[event],
            )

        return ActionResult.fail("Specify what to place.")

    async def _execute_remove_wall(
        self, agent: Agent, action: RemoveWallAction, tick: int
    ) -> ActionResult:
        """Remove wall from cell edge."""
        pos = agent.position
        direction = action.direction

        cell = await self._world.get_cell(pos)
        if direction not in cell.walls:
            return ActionResult.fail(f"No wall to the {direction.value} to remove.")

        await self._world.remove_wall(pos, direction)

        event = WallRemovedEvent(
            tick=tick,
            timestamp=datetime.now(HEARTH_TZ),
            position=pos,
            direction=direction,
        )

        return ActionResult.ok(
            f"Removed the wall to the {direction.value}.",
            events=[event],
        )

    # -------------------------------------------------------------------------
    # Expression Actions
    # -------------------------------------------------------------------------

    async def _execute_write_sign(
        self, agent: Agent, action: WriteSignAction, tick: int
    ) -> ActionResult:
        """Create readable marker."""
        sign = Sign(
            id=generate_object_id(),
            position=agent.position,
            created_by=agent.name,
            created_tick=tick,
            text=action.text,
        )
        await self._world.place_object(sign)

        event = SignWrittenEvent(
            tick=tick,
            timestamp=datetime.now(HEARTH_TZ),
            object_id=sign.id,
            position=agent.position,
            text=action.text,
            author=agent.name,
        )

        return ActionResult.ok(
            "Wrote a sign.",
            events=[event],
        )

    async def _execute_read_sign(
        self, agent: Agent, action: ReadSignAction, tick: int
    ) -> ActionResult:
        """Read a sign in a direction."""
        try:
            target_pos = self._resolve_direction_to_position(
                agent.position, action.direction
            )
        except ValueError:
            return ActionResult.fail(
                "Look north, south, east, west, or down at your feet."
            )

        # Find signs at that position
        objects = await self._world.get_objects_at(target_pos)
        signs = [obj for obj in objects if isinstance(obj, Sign)]

        if not signs:
            direction_phrase = (
                "at your feet" if action.direction.lower() == "down"
                else f"to the {action.direction}"
            )
            return ActionResult.fail(f"There's no sign {direction_phrase}.")

        # Read the first sign found
        sign = signs[0]

        return ActionResult.ok(
            f'The sign reads: "{sign.text}"',
            data={"text": sign.text, "author": str(sign.created_by)},
        )

    async def _execute_name_place(
        self, agent: Agent, action: NamePlaceAction, tick: int
    ) -> ActionResult:
        """Name current location."""
        await self._world.name_place(action.name, agent.position)

        event = PlaceNamedEvent(
            tick=tick,
            timestamp=datetime.now(HEARTH_TZ),
            position=agent.position,
            name=action.name,
            named_by=agent.name,
        )

        return ActionResult.ok(
            f'Named this place "{action.name}".',
            events=[event],
        )

    # -------------------------------------------------------------------------
    # Social Actions
    # -------------------------------------------------------------------------

    async def _execute_speak(
        self, agent: Agent, action: SpeakAction, tick: int
    ) -> ActionResult:
        """Speak in the agent's current conversation.

        Adds a turn to the conversation history.
        """
        if self._conversation is None:
            return ActionResult.fail("Conversation system not initialized.")

        # Check if in a conversation
        result = await self._conversation.add_turn(
            agent=agent.name,
            message=action.message,
            tick=tick,
        )

        if result is None:
            return ActionResult.fail("You are not in a conversation.")

        conv, turn = result

        # Get other participant names for the message
        others = conv.participants - {agent.name}
        others_str = ", ".join(str(n) for n in others) if others else "no one"

        event = ConversationTurnEvent(
            tick=tick,
            timestamp=datetime.now(HEARTH_TZ),
            conversation_id=conv.id,
            speaker=agent.name,
            message=action.message,
        )

        return ActionResult.ok(
            f"You say: {action.message}",
            events=[event],
            data={
                "message": action.message,
                "others": list(others),
            },
        )

    async def _execute_invite(
        self, agent: Agent, action: InviteAction, tick: int
    ) -> ActionResult:
        """Invite another agent to a conversation.

        Requires the invitee to be visible (within vision radius).
        """
        if self._conversation is None:
            return ActionResult.fail("Conversation system not initialized.")

        invitee_name = AgentName(action.agent)

        # Check if already in a conversation
        if await self._conversation.is_agent_in_conversation(agent.name):
            return ActionResult.fail(
                "You are already in a conversation. Leave it first."
            )

        # Block second private invite (private implies exclusivity)
        if action.privacy == "private":
            existing_invite = await self._conversation.get_pending_outgoing_invite(
                agent.name
            )
            if existing_invite is not None and existing_invite.privacy == "private":
                return ActionResult.fail(
                    "You already have a pending private invitation. "
                    "Wait for a response or it will expire."
                )

        # Check invitee exists
        invitee = await self._agents.get_agent(invitee_name)
        if invitee is None:
            return ActionResult.fail(f"No one named {action.agent} is here.")

        # Check invitee is visible (within vision radius, reduced at night)
        distance = agent.position.distance_to(invitee.position)
        if distance > self._get_effective_vision_radius():
            return ActionResult.fail(
                f"{action.agent} is too far away to invite."
            )

        # Check invitee doesn't already have a pending invite
        if await self._conversation.has_pending_invitation(invitee_name):
            return ActionResult.fail(
                f"{action.agent} already has a pending invitation."
            )

        # Check invitee isn't already in a conversation
        if await self._conversation.is_agent_in_conversation(invitee_name):
            return ActionResult.fail(
                f"{action.agent} is already in a conversation."
            )

        # Create the invitation
        invitation = await self._conversation.create_invite(
            inviter=agent.name,
            invitee=invitee_name,
            privacy=action.privacy,
            tick=tick,
        )

        event = InvitationSentEvent(
            tick=tick,
            timestamp=datetime.now(HEARTH_TZ),
            inviter=agent.name,
            invitee=invitee_name,
            conversation_id=invitation.conversation_id,
            privacy=action.privacy,
        )

        privacy_str = "private" if action.privacy == "private" else "public"
        return ActionResult.ok(
            f"You invited {action.agent} to a {privacy_str} conversation.",
            events=[event],
            data={
                "invitee": str(invitee_name),
                "privacy": action.privacy,
            },
        )

    async def _execute_accept_invite(
        self, agent: Agent, action: AcceptInviteAction, tick: int
    ) -> ActionResult:
        """Accept a pending invitation and join the conversation."""
        if self._conversation is None:
            return ActionResult.fail("Conversation system not initialized.")

        # Check if already in a conversation
        if await self._conversation.is_agent_in_conversation(agent.name):
            return ActionResult.fail(
                "You are already in a conversation. Leave it first."
            )

        # Try to accept
        result = await self._conversation.accept_invite(agent.name, tick)

        if result is None:
            return ActionResult.fail("You have no pending invitation.")

        conv, invitation = result

        events = [
            InvitationAcceptedEvent(
                tick=tick,
                timestamp=datetime.now(HEARTH_TZ),
                agent=agent.name,
                inviter=invitation.inviter,
                conversation_id=conv.id,
            ),
            ConversationStartedEvent(
                tick=tick,
                timestamp=datetime.now(HEARTH_TZ),
                conversation_id=conv.id,
                participants=tuple(conv.participants),
                is_private=conv.privacy == "private",
            ),
        ]

        return ActionResult.ok(
            f"You joined a conversation with {invitation.inviter}.",
            events=events,
            data={
                "inviter": str(invitation.inviter),
                "conversation_id": str(conv.id),
                "privacy": conv.privacy,
            },
        )

    async def _execute_decline_invite(
        self, agent: Agent, action: DeclineInviteAction, tick: int
    ) -> ActionResult:
        """Decline a pending invitation."""
        if self._conversation is None:
            return ActionResult.fail("Conversation system not initialized.")

        invitation = await self._conversation.decline_invite(agent.name)

        if invitation is None:
            return ActionResult.fail("You have no pending invitation.")

        event = InvitationDeclinedEvent(
            tick=tick,
            timestamp=datetime.now(HEARTH_TZ),
            agent=agent.name,
            inviter=invitation.inviter,
        )

        return ActionResult.ok(
            f"You declined {invitation.inviter}'s invitation.",
            events=[event],
            data={
                "inviter": str(invitation.inviter),
            },
        )

    async def _execute_join_conversation(
        self, agent: Agent, action: JoinConversationAction, tick: int
    ) -> ActionResult:
        """Join an existing public conversation by naming a participant."""
        if self._conversation is None:
            return ActionResult.fail("Conversation system not initialized.")

        participant_name = AgentName(action.participant)

        # Check if already in a conversation
        if await self._conversation.is_agent_in_conversation(agent.name):
            return ActionResult.fail(
                "You are already in a conversation. Leave it first."
            )

        # Check the named participant exists
        participant = await self._agents.get_agent(participant_name)
        if participant is None:
            return ActionResult.fail(f"No one named {action.participant} is here.")

        # Check the participant is visible (reduced at night)
        distance = agent.position.distance_to(participant.position)
        if distance > self._get_effective_vision_radius():
            return ActionResult.fail(
                f"{action.participant} is too far away to see."
            )

        # Get the participant's conversation
        conv = await self._conversation.get_conversation_for_agent(participant_name)
        if conv is None:
            return ActionResult.fail(
                f"{action.participant} is not in a conversation."
            )

        # Check it's public
        if conv.privacy == "private":
            return ActionResult.fail(
                f"{action.participant}'s conversation is private."
            )

        # Join the conversation
        conv = await self._conversation.join_conversation(agent.name, conv.id, tick)

        if conv is None:
            return ActionResult.fail("Could not join the conversation.")

        others = conv.participants - {agent.name}
        others_str = ", ".join(str(n) for n in others)

        event = AgentJoinedConversationEvent(
            tick=tick,
            timestamp=datetime.now(HEARTH_TZ),
            agent=agent.name,
            conversation_id=conv.id,
        )

        return ActionResult.ok(
            f"You joined the conversation with {others_str}.",
            events=[event],
            data={
                "conversation_id": str(conv.id),
                "participants": [str(n) for n in conv.participants],
            },
        )

    async def _execute_leave_conversation(
        self, agent: Agent, action: LeaveConversationAction, tick: int
    ) -> ActionResult:
        """Leave the current conversation."""
        if self._conversation is None:
            return ActionResult.fail("Conversation system not initialized.")

        conv, was_ended = await self._conversation.leave_conversation(
            agent.name, tick
        )

        if conv is None:
            return ActionResult.fail("You are not in a conversation.")

        events = [
            AgentLeftConversationEvent(
                tick=tick,
                timestamp=datetime.now(HEARTH_TZ),
                agent=agent.name,
                conversation_id=conv.id,
            )
        ]

        if was_ended:
            events.append(
                ConversationEndedEvent(
                    tick=tick,
                    timestamp=datetime.now(HEARTH_TZ),
                    conversation_id=conv.id,
                    reason="all_left",
                )
            )

        msg = "You left the conversation."
        if was_ended:
            msg = "You left the conversation. It has ended."

        return ActionResult.ok(
            msg,
            events=events,
            data={
                "conversation_id": str(conv.id),
                "ended": was_ended,
            },
        )

    # -------------------------------------------------------------------------
    # State Actions
    # -------------------------------------------------------------------------

    async def _execute_sleep(
        self, agent: Agent, action: SleepAction, tick: int
    ) -> ActionResult:
        """Full rest - go to sleep."""
        await self._agents.set_sleeping(agent.name, True)

        event = AgentSleptEvent(
            tick=tick,
            timestamp=datetime.now(HEARTH_TZ),
            agent=agent.name,
            at_position=agent.position,
        )

        return ActionResult.ok(
            "You drift off to sleep.",
            events=[event],
        )
