"""MCP tool definitions for Hearth actions.

Defines Hearth action tools as an MCP server that can be attached
to agent sessions. Tool handlers execute actions through ActionEngine
and return narrated prose responses.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from claude_agent_sdk import tool, create_sdk_mcp_server

from core.types import AgentName, Position, Direction
from core.terrain import Weather
from core.actions import (
    Action,
    ActionResult,
    # Movement
    WalkAction,
    ApproachAction,
    JourneyAction,
    # Perception
    ExamineAction,
    SenseOthersAction,
    # Interaction
    TakeAction,
    DropAction,
    GiveAction,
    GatherAction,
    # Material
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
    # Social
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
    from services import WorldService, AgentService, ActionEngine, Narrator
    from services.narrator import NarratorContext
    from core.events import DomainEvent
    from core.agent import Agent


logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Tool Context
# -----------------------------------------------------------------------------


@dataclass
class HearthToolContext:
    """Context passed to tool handlers for action execution.

    Contains all services needed to execute actions and narrate results.
    Mutable: accumulated_events grows as actions execute.
    """

    agent_name: AgentName
    agent: "Agent"
    tick: int
    time_of_day: str
    weather: Weather

    # Services for execution
    world_service: "WorldService"
    agent_service: "AgentService"
    action_engine: "ActionEngine"
    narrator: "Narrator"

    # Accumulated during turn
    accumulated_events: list["DomainEvent"] = field(default_factory=list)
    actions_taken: list[Action] = field(default_factory=list)

    # Lock for thread safety
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)


# -----------------------------------------------------------------------------
# Per-Agent Tool State
# -----------------------------------------------------------------------------


@dataclass
class AgentToolState:
    """Mutable state for an agent's MCP tool handlers.

    Each agent gets their own instance, captured by closures in their
    MCP tool handlers. Updated before each turn.
    """

    tool_context: HearthToolContext | None = None

    def update_for_turn(self, ctx: HearthToolContext) -> None:
        """Update state for a new turn."""
        self.tool_context = ctx


# -----------------------------------------------------------------------------
# Tool Definitions
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class HearthTool:
    """Definition of a Hearth action tool."""

    name: str
    description: str
    input_schema: dict[str, Any]
    action_builder: Callable[[dict[str, Any]], Action]


def _direction_from_str(s: str) -> Direction:
    """Convert string to Direction enum."""
    mapping = {
        "north": Direction.NORTH,
        "south": Direction.SOUTH,
        "east": Direction.EAST,
        "west": Direction.WEST,
    }
    return mapping.get(s.lower(), Direction.NORTH)


# Movement Tools
WALK_TOOL = HearthTool(
    name="walk",
    description="Take a step in a direction. Moves you one cell north, south, east, or west.",
    input_schema={
        "type": "object",
        "properties": {
            "direction": {
                "type": "string",
                "enum": ["north", "south", "east", "west"],
                "description": "Direction to walk",
            }
        },
        "required": ["direction"],
    },
    action_builder=lambda args: WalkAction(direction=_direction_from_str(args["direction"])),
)

APPROACH_TOOL = HearthTool(
    name="approach",
    description="Move one step toward something you can see—an agent or an object.",
    input_schema={
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "Name of agent or ID of object to approach",
            }
        },
        "required": ["target"],
    },
    action_builder=lambda args: ApproachAction(target=args["target"]),
)

JOURNEY_TOOL = HearthTool(
    name="journey",
    description="Set off toward somewhere distant. Give coordinates (x,y) or a landmark name. The travel unfolds between moments; you'll arrive when next you're aware.",
    input_schema={
        "type": "object",
        "properties": {
            "destination": {
                "type": "string",
                "description": "Coordinates as 'x,y' (e.g. '100,150') or landmark name",
            }
        },
        "required": ["destination"],
    },
    action_builder=lambda args: _build_journey_action(args["destination"]),
)


def _build_journey_action(dest_str: str) -> JourneyAction:
    """Parse destination string to JourneyAction."""
    # Try parsing as coordinates
    if "," in dest_str:
        try:
            parts = dest_str.split(",")
            x, y = int(parts[0].strip()), int(parts[1].strip())
            return JourneyAction(destination=Position(x, y))
        except (ValueError, IndexError):
            pass
    # Treat as landmark name
    return JourneyAction(destination=dest_str)


# Perception Tools
EXAMINE_TOOL = HearthTool(
    name="examine",
    description="Look closely at something nearby. Choose a direction to peer, or down to study what lies beneath you.",
    input_schema={
        "type": "object",
        "properties": {
            "direction": {
                "type": "string",
                "enum": ["north", "south", "east", "west", "down"],
                "description": "Where to look (north, south, east, west, or down at your feet)",
            }
        },
        "required": ["direction"],
    },
    action_builder=lambda args: ExamineAction(direction=args["direction"]),
)

SENSE_OTHERS_TOOL = HearthTool(
    name="sense_others",
    description="Reach inward and feel for others you've met. Returns their direction and rough distance—not sight, but something like knowing.",
    input_schema={
        "type": "object",
        "properties": {},
    },
    action_builder=lambda args: SenseOthersAction(),
)


# Interaction Tools
TAKE_TOOL = HearthTool(
    name="take",
    description="Pick something up from nearby. Look in a direction—or down at your feet—to reach for what's there.",
    input_schema={
        "type": "object",
        "properties": {
            "direction": {
                "type": "string",
                "enum": ["north", "south", "east", "west", "down"],
                "description": "Where to look (north, south, east, west, or down at your feet)",
            }
        },
        "required": ["direction"],
    },
    action_builder=lambda args: TakeAction(direction=args["direction"]),
)

DROP_TOOL = HearthTool(
    name="drop",
    description="Set something down from what you carry. It stays where you leave it.",
    input_schema={
        "type": "object",
        "properties": {
            "item_type": {
                "type": "string",
                "description": "Type of item to drop (for stackable resources)",
            },
            "item_id": {
                "type": "string",
                "description": "ID of specific item to drop (for unique items)",
            },
            "quantity": {
                "type": "integer",
                "description": "How many to drop (default 1)",
                "default": 1,
            },
        },
    },
    action_builder=lambda args: DropAction(
        item_type=args.get("item_type"),
        item_id=args.get("item_id"),
        quantity=args.get("quantity", 1),
    ),
)

GIVE_TOOL = HearthTool(
    name="give",
    description="Offer something to another agent. They receive it directly—a transfer, a gift.",
    input_schema={
        "type": "object",
        "properties": {
            "recipient": {
                "type": "string",
                "description": "Name of the agent to give to",
            },
            "item_type": {
                "type": "string",
                "description": "Type of item to give (for stackable resources)",
            },
            "item_id": {
                "type": "string",
                "description": "ID of specific item to give (for unique items)",
            },
            "quantity": {
                "type": "integer",
                "description": "How many to give (default 1)",
                "default": 1,
            },
        },
        "required": ["recipient"],
    },
    action_builder=lambda args: GiveAction(
        recipient=AgentName(args["recipient"]),
        item_type=args.get("item_type"),
        item_id=args.get("item_id"),
        quantity=args.get("quantity", 1),
    ),
)

GATHER_TOOL = HearthTool(
    name="gather",
    description="Collect what the land offers here. The terrain shapes what's available—wood from forest, stone from rocks, clay from sand.",
    input_schema={
        "type": "object",
        "properties": {
            "resource_type": {
                "type": "string",
                "description": "Type of resource to gather (optional - inferred from terrain if not specified)",
            },
        },
    },
    action_builder=lambda args: GatherAction(resource_type=args.get("resource_type")),
)


# Material/Crafting Tools
COMBINE_TOOL = HearthTool(
    name="combine",
    description="Bring items together and see what emerges. Some combinations create something new.",
    input_schema={
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of item types or IDs to combine (at least 2)",
                "minItems": 2,
            },
        },
        "required": ["items"],
    },
    action_builder=lambda args: CombineAction(items=tuple(args["items"])),
)

WORK_TOOL = HearthTool(
    name="work",
    description="Shape a material with a technique—hollow, flatten, carve, weave, split, break, strip, grind, twist. The material responds to what you do.",
    input_schema={
        "type": "object",
        "properties": {
            "material": {
                "type": "string",
                "description": "Item type or ID of material to work",
            },
            "technique": {
                "type": "string",
                "description": "Technique to apply (hollow, flatten, carve, weave, split, break, strip, shape, grind, twist)",
            },
        },
        "required": ["material", "technique"],
    },
    action_builder=lambda args: WorkAction(
        material=args["material"],
        technique=args["technique"],
    ),
)

APPLY_TOOL = HearthTool(
    name="apply",
    description="Use one thing on another. A tool on material. Fire on clay. See what happens.",
    input_schema={
        "type": "object",
        "properties": {
            "tool": {
                "type": "string",
                "description": "Item type or ID of tool to use",
            },
            "target": {
                "type": "string",
                "description": "Item type or ID of target",
            },
        },
        "required": ["tool", "target"],
    },
    action_builder=lambda args: ApplyAction(
        tool=args["tool"],
        target=args["target"],
    ),
)


# Building Tools
BUILD_SHELTER_TOOL = HearthTool(
    name="build_shelter",
    description="Construct a simple enclosed shelter where you stand. Uses materials from your inventory.",
    input_schema={
        "type": "object",
        "properties": {},
    },
    action_builder=lambda args: BuildShelterAction(),
)

PLACE_WALL_TOOL = HearthTool(
    name="place_wall",
    description="Build a wall on one edge of where you stand—north, south, east, or west. Uses materials from your inventory.",
    input_schema={
        "type": "object",
        "properties": {
            "direction": {
                "type": "string",
                "enum": ["north", "south", "east", "west"],
                "description": "Which edge to place the wall on",
            },
        },
        "required": ["direction"],
    },
    action_builder=lambda args: PlaceWallAction(direction=_direction_from_str(args["direction"])),
)

PLACE_DOOR_TOOL = HearthTool(
    name="place_door",
    description="Add a door to an existing wall, allowing passage through it.",
    input_schema={
        "type": "object",
        "properties": {
            "direction": {
                "type": "string",
                "enum": ["north", "south", "east", "west"],
                "description": "Which wall to add a door to",
            },
        },
        "required": ["direction"],
    },
    action_builder=lambda args: PlaceDoorAction(direction=_direction_from_str(args["direction"])),
)

PLACE_ITEM_TOOL = HearthTool(
    name="place_item",
    description="Set an item from your inventory into the world as a permanent object.",
    input_schema={
        "type": "object",
        "properties": {
            "item_type": {
                "type": "string",
                "description": "Type of item to place (for stackable resources)",
            },
            "item_id": {
                "type": "string",
                "description": "ID of specific item to place (for unique items)",
            },
        },
    },
    action_builder=lambda args: PlaceItemAction(
        item_type=args.get("item_type"),
        item_id=args.get("item_id"),
    ),
)

REMOVE_WALL_TOOL = HearthTool(
    name="remove_wall",
    description="Take down a wall from one edge of where you stand.",
    input_schema={
        "type": "object",
        "properties": {
            "direction": {
                "type": "string",
                "enum": ["north", "south", "east", "west"],
                "description": "Which edge to remove the wall from",
            },
        },
        "required": ["direction"],
    },
    action_builder=lambda args: RemoveWallAction(direction=_direction_from_str(args["direction"])),
)


# Expression Tools
WRITE_SIGN_TOOL = HearthTool(
    name="write_sign",
    description="Leave a sign with a message where you stand. Others who pass will see it.",
    input_schema={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The message to write on the sign",
            },
        },
        "required": ["text"],
    },
    action_builder=lambda args: WriteSignAction(text=args["text"]),
)

READ_SIGN_TOOL = HearthTool(
    name="read_sign",
    description="Read what's written nearby. Look in a direction—or down at your feet—to find a sign's words.",
    input_schema={
        "type": "object",
        "properties": {
            "direction": {
                "type": "string",
                "enum": ["north", "south", "east", "west", "down"],
                "description": "Where to look for the sign",
            }
        },
        "required": ["direction"],
    },
    action_builder=lambda args: ReadSignAction(direction=args["direction"]),
)

NAME_PLACE_TOOL = HearthTool(
    name="name_place",
    description="Name where you stand. The name will persist—others will see it too.",
    input_schema={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "The name for this place",
            },
        },
        "required": ["name"],
    },
    action_builder=lambda args: NamePlaceAction(name=args["name"]),
)


# Social Tools
SPEAK_TOOL = HearthTool(
    name="speak",
    description="Say something to those you're with. Only works when you're in a conversation.",
    input_schema={
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "What to say",
            },
        },
        "required": ["message"],
    },
    action_builder=lambda args: SpeakAction(message=args["message"]),
)

INVITE_TOOL = HearthTool(
    name="invite",
    description="Reach toward someone to start a conversation. They must be visible to you. They'll receive your invitation and choose whether to join. Public lets others step in; private keeps it between you.",
    input_schema={
        "type": "object",
        "properties": {
            "agent": {
                "type": "string",
                "description": "Name of agent to invite",
            },
            "privacy": {
                "type": "string",
                "enum": ["public", "private"],
                "description": "Whether others can join. Public lets anyone join; private is invitation only (default: public)",
                "default": "public",
            },
        },
        "required": ["agent"],
    },
    action_builder=lambda args: InviteAction(
        agent=AgentName(args["agent"]),
        privacy=args.get("privacy", "public"),
    ),
)

ACCEPT_INVITE_TOOL = HearthTool(
    name="accept_invite",
    description="Step into a conversation you've been invited to. Whatever you write after this becomes your first words.",
    input_schema={
        "type": "object",
        "properties": {},
    },
    action_builder=lambda args: AcceptInviteAction(),
)

DECLINE_INVITE_TOOL = HearthTool(
    name="decline_invite",
    description="Let them know you can't talk right now. They'll know you declined, though not why—that's yours to share or keep.",
    input_schema={
        "type": "object",
        "properties": {},
    },
    action_builder=lambda args: DeclineInviteAction(),
)

JOIN_CONVERSATION_TOOL = HearthTool(
    name="join_conversation",
    description="Step into a public conversation already happening. Name someone in it so the world knows which one. Whatever you write after becomes your first words.",
    input_schema={
        "type": "object",
        "properties": {
            "participant": {
                "type": "string",
                "description": "Name of someone in the conversation to join",
            },
        },
        "required": ["participant"],
    },
    action_builder=lambda args: JoinConversationAction(participant=AgentName(args["participant"])),
)

LEAVE_CONVERSATION_TOOL = HearthTool(
    name="leave_conversation",
    description="Step away from the conversation. Whatever you wrote just before becomes your parting words.",
    input_schema={
        "type": "object",
        "properties": {},
    },
    action_builder=lambda args: LeaveConversationAction(),
)


# State Tools
SLEEP_TOOL = HearthTool(
    name="sleep",
    description="Rest until morning. You'll be inactive—dreaming, perhaps—unless someone wakes you.",
    input_schema={
        "type": "object",
        "properties": {},
    },
    action_builder=lambda args: SleepAction(),
)


# -----------------------------------------------------------------------------
# Tool Registry
# -----------------------------------------------------------------------------


HEARTH_TOOL_REGISTRY: dict[str, HearthTool] = {
    # Movement
    "walk": WALK_TOOL,
    "approach": APPROACH_TOOL,
    "journey": JOURNEY_TOOL,
    # Perception
    "examine": EXAMINE_TOOL,
    "sense_others": SENSE_OTHERS_TOOL,
    # Interaction
    "take": TAKE_TOOL,
    "drop": DROP_TOOL,
    "give": GIVE_TOOL,
    "gather": GATHER_TOOL,
    # Material
    "combine": COMBINE_TOOL,
    "work": WORK_TOOL,
    "apply": APPLY_TOOL,
    # Building
    "build_shelter": BUILD_SHELTER_TOOL,
    "place_wall": PLACE_WALL_TOOL,
    "place_door": PLACE_DOOR_TOOL,
    "place_item": PLACE_ITEM_TOOL,
    "remove_wall": REMOVE_WALL_TOOL,
    # Expression
    "write_sign": WRITE_SIGN_TOOL,
    "read_sign": READ_SIGN_TOOL,
    "name_place": NAME_PLACE_TOOL,
    # Social
    "speak": SPEAK_TOOL,
    "invite": INVITE_TOOL,
    "accept_invite": ACCEPT_INVITE_TOOL,
    "decline_invite": DECLINE_INVITE_TOOL,
    "join_conversation": JOIN_CONVERSATION_TOOL,
    "leave_conversation": LEAVE_CONVERSATION_TOOL,
    # State
    "sleep": SLEEP_TOOL,
}

# Tool names as they appear to Claude (with MCP prefix)
HEARTH_TOOL_NAMES = [f"mcp__hearth__{name}" for name in HEARTH_TOOL_REGISTRY.keys()]


# -----------------------------------------------------------------------------
# MCP Server Creation
# -----------------------------------------------------------------------------


def _create_mcp_tool_handler(
    tool_name: str,
    tool_def: HearthTool,
    state: AgentToolState,
) -> Callable:
    """Create an MCP tool handler that captures the agent's state.

    The handler is a closure that references the agent's AgentToolState,
    allowing it to access the current turn's context.
    """
    # Import here to avoid circular imports
    from services.narrator import NarratorContext

    # Convert JSON Schema to SDK format
    sdk_params = {}
    if "properties" in tool_def.input_schema:
        for param_name, param_def in tool_def.input_schema["properties"].items():
            type_map = {"string": str, "integer": int, "boolean": bool, "number": float, "array": list}
            param_type = type_map.get(param_def.get("type", "string"), str)
            sdk_params[param_name] = param_type

    @tool(tool_name, tool_def.description, sdk_params)
    async def handler(args: dict[str, Any]) -> dict[str, Any]:
        if state.tool_context is None:
            return {"content": [{"type": "text", "text": "Tool called outside of turn context."}]}

        ctx = state.tool_context

        async with ctx._lock:
            try:
                # Build the action from args
                action = tool_def.action_builder(args)
                ctx.actions_taken.append(action)

                # Set time of day for vision calculations
                ctx.action_engine.set_time_of_day(ctx.time_of_day)

                # Execute action
                result = await ctx.action_engine.execute(ctx.agent, action, ctx.tick)

                # Accumulate events
                ctx.accumulated_events.extend(result.events)

                # Build narrator context
                narrator_ctx = NarratorContext(
                    agent_name=ctx.agent_name,
                    position=ctx.agent.position,
                    time_of_day=ctx.time_of_day,
                    weather=ctx.weather,
                    action_type=tool_name,
                )

                # Narrate the result
                prose = await ctx.narrator.narrate(result, narrator_ctx)

                return {"content": [{"type": "text", "text": prose}]}

            except Exception as e:
                logger.exception(f"Error executing {tool_name} for {ctx.agent_name}: {e}")
                return {"content": [{"type": "text", "text": f"Something went wrong: {e}"}]}

    return handler


def create_hearth_mcp_server(agent_name: AgentName, state: AgentToolState):
    """Create an MCP server for a specific agent with all Hearth tools.

    Each agent gets their own MCP server with closures that reference their
    AgentToolState. This ensures parallel execution is safe.

    Args:
        agent_name: Name of the agent this server is for
        state: AgentToolState that tool handlers will reference

    Returns:
        MCP server configured with all Hearth action tools
    """
    tool_handlers = []
    for tool_name, tool_def in HEARTH_TOOL_REGISTRY.items():
        handler = _create_mcp_tool_handler(tool_name, tool_def, state)
        tool_handlers.append(handler)

    return create_sdk_mcp_server(
        name="hearth",
        version="1.0.0",
        tools=tool_handlers,
    )
