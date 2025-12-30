"""
AgentTurnPhase - executes agent turns by calling the LLM.

This phase:
1. Builds context for each agent scheduled to act
2. Calls the LLM provider with tools and their processors
3. LLM provider executes tool calls via processors (stateful API pattern)
4. Collects narratives and effects from completed turns

The conversation tools have processors that run inside the LLM provider,
similar to how the interpreter has OBSERVATION_REGISTRY.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol, runtime_checkable, TYPE_CHECKING

from engine.domain import (
    AgentName,
    AgentSnapshot,
    LocationId,
    ConversationId,
    Conversation,
    Invitation,
    DomainEvent,
    Effect,
    InviteToConversationEffect,
    AcceptInviteEffect,
    DeclineInviteEffect,
    JoinConversationEffect,
    LeaveConversationEffect,
    WorldEventOccurred,
    WeatherChangedEvent,
    UpdateLastActiveTickEffect,
)
from engine.runtime.context import TickContext
from engine.runtime.pipeline import BasePhase
from engine.runtime.interpreter import AgentTurnResult

if TYPE_CHECKING:
    from engine.storage import EventStore


logger = logging.getLogger(__name__)


# =============================================================================
# Agent Context (provided to LLM)
# =============================================================================


@dataclass
class AgentContext:
    """Context provided to the LLM for an agent's turn."""

    agent: AgentSnapshot
    location_description: str
    weather: str
    time_description: str
    others_present: list[AgentName]
    available_paths: list[LocationId]

    # Conversation context (if in conversation)
    conversation: Conversation | None = None
    unseen_history: list[dict] | None = None
    is_opener: bool = False
    is_group: bool = False

    # Pending invite (if any)
    pending_invite: Invitation | None = None

    # Public conversations at location (for join opportunity)
    joinable_conversations: list[Conversation] | None = None

    # Private conversations at location (for awareness only)
    private_conversations: list[Conversation] | None = None

    # Shared files available at this location
    shared_files: list[str] | None = None

    # Recent world events to remember
    recent_events: list[str] | None = None

    # Dreams since the last time this agent acted
    unseen_dreams: list[str] | None = None


# =============================================================================
# Tool Context (passed to processors)
# =============================================================================


@dataclass
class ToolContext:
    """Context available to tool processors."""

    agent_name: AgentName
    agent: AgentSnapshot
    tick_context: TickContext


# =============================================================================
# Conversation Tool Registry
# =============================================================================


@dataclass
class ConversationTool:
    """Definition of a conversation tool with its processor."""

    name: str
    description: str
    input_schema: dict
    processor: Callable[[dict, ToolContext], list[Effect]]


# Global registry of conversation tools
CONVERSATION_TOOL_REGISTRY: dict[str, ConversationTool] = {}


def register_conversation_tool(
    name: str,
    description: str,
    input_schema: dict,
    processor: Callable[[dict, ToolContext], list[Effect]],
) -> None:
    """Register a conversation tool with its processor."""
    CONVERSATION_TOOL_REGISTRY[name] = ConversationTool(
        name=name,
        description=description,
        input_schema=input_schema,
        processor=processor,
    )


def get_conversation_tools() -> list[dict]:
    """Get tool definitions for the LLM API."""
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
        }
        for tool in CONVERSATION_TOOL_REGISTRY.values()
    ]


def get_tool_processor(name: str) -> Callable[[dict, ToolContext], list[Effect]] | None:
    """Get the processor for a tool by name."""
    tool = CONVERSATION_TOOL_REGISTRY.get(name)
    return tool.processor if tool else None


# =============================================================================
# Tool Processors
# =============================================================================


def process_invite(tool_input: dict, ctx: ToolContext) -> list[Effect]:
    """Process invite_to_conversation tool call."""
    invitee = AgentName(tool_input.get("invitee", ""))
    privacy = tool_input.get("privacy", "public")
    topic = tool_input.get("topic")

    # Validate invitee exists and is at same location
    invitee_agent = ctx.tick_context.agents.get(invitee)

    if not invitee_agent:
        logger.warning(f"Invalid invite: {invitee} not found")
        return []

    if invitee_agent.location != ctx.agent.location:
        logger.warning(f"Invalid invite: {invitee} not at same location")
        return []

    return [InviteToConversationEffect(
        inviter=ctx.agent_name,
        invitee=invitee,
        location=ctx.agent.location,
        privacy=privacy,
        topic=topic,
    )]


def process_accept_invite(tool_input: dict, ctx: ToolContext) -> list[Effect]:
    """Process accept_invite tool call."""
    invite = ctx.tick_context.pending_invites.get(ctx.agent_name)

    if not invite:
        logger.warning(f"Invalid accept: no pending invite for {ctx.agent_name}")
        return []

    return [AcceptInviteEffect(
        agent=ctx.agent_name,
        conversation_id=invite.conversation_id,
    )]


def process_decline_invite(tool_input: dict, ctx: ToolContext) -> list[Effect]:
    """Process decline_invite tool call."""
    invite = ctx.tick_context.pending_invites.get(ctx.agent_name)

    if not invite:
        logger.warning(f"Invalid decline: no pending invite for {ctx.agent_name}")
        return []

    return [DeclineInviteEffect(
        agent=ctx.agent_name,
        conversation_id=invite.conversation_id,
    )]


def process_join_conversation(tool_input: dict, ctx: ToolContext) -> list[Effect]:
    """Process join_conversation tool call.

    Finds a public conversation at the agent's location by participant name.
    """
    participant = tool_input.get("participant", "")

    if not participant:
        logger.warning(f"Invalid join: no participant specified")
        return []

    # Find a public conversation at this location containing the named participant
    agent_location = ctx.agent.location
    matching_conv = None

    for conv in ctx.tick_context.conversations.values():
        if (conv.privacy == "public"
            and conv.location == agent_location
            and participant in conv.participants
            and ctx.agent_name not in conv.participants):
            matching_conv = conv
            break

    if not matching_conv:
        logger.warning(f"Invalid join: no public conversation with {participant} at {agent_location}")
        return []

    return [JoinConversationEffect(
        agent=ctx.agent_name,
        conversation_id=matching_conv.id,
    )]


def process_leave_conversation(tool_input: dict, ctx: ToolContext) -> list[Effect]:
    """Process leave_conversation tool call.

    Leaves the agent's current conversation. No input required.
    """
    # Find conversations the agent is in
    agent_conversations = [
        conv for conv in ctx.tick_context.conversations.values()
        if ctx.agent_name in conv.participants
    ]

    if not agent_conversations:
        logger.warning(f"Invalid leave: {ctx.agent_name} not in any conversation")
        return []

    # Leave the first one (usually there's only one)
    conv = agent_conversations[0]
    if len(agent_conversations) > 1:
        logger.warning(f"{ctx.agent_name} in multiple conversations, leaving first one: {conv.id}")

    return [LeaveConversationEffect(
        agent=ctx.agent_name,
        conversation_id=conv.id,
    )]


# =============================================================================
# Register Conversation Tools
# =============================================================================

register_conversation_tool(
    name="invite_to_conversation",
    description=(
        "Invite another agent to have a conversation with you. "
        "They must accept before the conversation begins."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "invitee": {
                "type": "string",
                "description": "Name of the agent to invite",
            },
            "privacy": {
                "type": "string",
                "enum": ["public", "private"],
                "description": (
                    "Public conversations can be joined by others; "
                    "private conversations require invitation"
                ),
            },
            "topic": {
                "type": "string",
                "description": "Optional topic or reason for the conversation",
            },
        },
        "required": ["invitee", "privacy"],
    },
    processor=process_invite,
)

register_conversation_tool(
    name="accept_invite",
    description="Accept a pending conversation invitation from another agent.",
    input_schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
    processor=process_accept_invite,
)

register_conversation_tool(
    name="decline_invite",
    description="Politely decline a pending conversation invitation.",
    input_schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
    processor=process_decline_invite,
)

register_conversation_tool(
    name="join_conversation",
    description=(
        "Join a public conversation happening at your location. "
        "Specify the name of someone already in the conversation."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "participant": {
                "type": "string",
                "description": "Name of someone in the conversation you want to join",
            },
        },
        "required": ["participant"],
    },
    processor=process_join_conversation,
)

register_conversation_tool(
    name="leave_conversation",
    description="Leave the conversation you're currently in.",
    input_schema={
        "type": "object",
        "properties": {},
    },
    processor=process_leave_conversation,
)


# =============================================================================
# LLM Provider Protocol
# =============================================================================


@dataclass
class TurnResult:
    """Result from LLM provider for an agent's turn."""

    narrative: str
    effects: list[Effect]  # Already processed by tool handlers


@runtime_checkable
class LLMProvider(Protocol):
    """
    Protocol for LLM providers.

    The provider is responsible for:
    1. Managing stateful sessions (Claude Agent SDK pattern)
    2. Executing tool calls via processors
    3. Continuing the agentic loop until completion

    Implemented by adapters/claude_provider.py.
    """

    async def execute_turn(
        self,
        agent_context: AgentContext,
        tool_context: ToolContext,
        tools: dict[str, ConversationTool],
        agent_dir: str | None = None,
    ) -> TurnResult:
        """
        Execute an agent's turn.

        Args:
            agent_context: Context for building the prompt
            tool_context: Context passed to tool processors
            tools: Tool registry with processors
            agent_dir: Agent working directory for filesystem tools

        Returns:
            TurnResult with final narrative and effects from tool calls
        """
        ...


# =============================================================================
# AgentTurnPhase
# =============================================================================


class AgentTurnPhase(BasePhase):
    """
    Execute turns for all scheduled agents.

    This phase:
    1. Builds context for each agent
    2. Calls the LLM provider with tools + processors
    3. LLM provider runs the agentic loop, executing tools
    4. Collects narratives and effects
    """

    def __init__(self, llm_provider: LLMProvider):
        """
        Initialize the phase.

        Args:
            llm_provider: Provider for LLM calls (from adapters layer)
        """
        self._llm_provider = llm_provider
        self._village_root: Path | None = None
        self._event_store: EventStore | None = None

    def set_village_root(self, village_root: Path | str | None) -> None:
        """Configure the village root for shared file syncing."""
        self._village_root = Path(village_root) if village_root else None

    def set_event_store(self, event_store: "EventStore" | None) -> None:
        """Configure the event store for recent event context."""
        self._event_store = event_store

    async def _execute(self, ctx: TickContext) -> TickContext:
        """Execute turns for all scheduled agents."""
        if not ctx.agents_to_act:
            logger.debug("No agents scheduled to act")
            return ctx

        # Execute turns in parallel
        recent_events = self._get_recent_events()

        tasks = []
        for agent_name in ctx.agents_to_act:
            agent = ctx.agents.get(agent_name)
            if agent is None:
                continue
            task = self._execute_agent_turn(agent, ctx, recent_events)
            tasks.append((agent_name, task))

        # Gather results
        results = await asyncio.gather(
            *[t for _, t in tasks],
            return_exceptions=True,
        )

        # Process results
        new_ctx = ctx
        for (agent_name, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                logger.error(f"Turn failed for {agent_name}: {result}")
                continue

            turn_result = result

            # Create interpreter-ready result (just narrative for now)
            agent_turn_result = AgentTurnResult(narrative=turn_result.narrative)

            new_ctx = new_ctx.with_turn_result(agent_name, agent_turn_result)
            new_ctx = new_ctx.with_effects(turn_result.effects)
            new_ctx = new_ctx.with_effect(UpdateLastActiveTickEffect(agent=agent_name))
            new_ctx = new_ctx.with_agent_acted(agent_name)

        logger.info(f"Executed {len(new_ctx.agents_acted)} agent turns")
        return new_ctx

    async def _execute_agent_turn(
        self,
        agent: AgentSnapshot,
        ctx: TickContext,
        recent_events: list[DomainEvent],
    ) -> TurnResult:
        """Execute a single agent's turn."""
        shared_files: list[str] | None = None
        unseen_dreams: list[str] | None = None
        agent_dir: Path | None = None
        shared_master_dir: Path | None = None
        start_location = agent.location

        if self._village_root:
            from engine.services import (
                ensure_agent_directory,
                ensure_shared_directories,
                sync_shared_files_in,
                sync_shared_files_out,
            )

            ensure_shared_directories(self._village_root)
            agent_dir = ensure_agent_directory(agent.name, self._village_root)
            shared_master_dir = self._village_root / "shared"
            shared_files = sync_shared_files_in(
                agent_dir,
                str(start_location),
                shared_master_dir,
            )
            from engine.services import get_unseen_dreams

            unseen_dreams = get_unseen_dreams(agent_dir, agent.last_active_tick)

        agent_dir_str = str(agent_dir) if agent_dir else None

        try:
            # Build contexts
            agent_context = self._build_agent_context(
                agent,
                ctx,
                shared_files,
                recent_events,
                unseen_dreams,
            )
            tool_context = ToolContext(
                agent_name=agent.name,
                agent=agent,
                tick_context=ctx,
            )

            # Call LLM with tools and processors
            result = await self._llm_provider.execute_turn(
                agent_context=agent_context,
                tool_context=tool_context,
                tools=CONVERSATION_TOOL_REGISTRY,
                agent_dir=agent_dir_str,
            )

            return result
        finally:
            if agent_dir and shared_master_dir:
                from engine.services import sync_shared_files_out

                sync_shared_files_out(
                    agent_dir,
                    str(start_location),
                    shared_master_dir,
                )

    def _build_agent_context(
        self,
        agent: AgentSnapshot,
        ctx: TickContext,
        shared_files: list[str] | None = None,
        recent_events: list[DomainEvent] | None = None,
        unseen_dreams: list[str] | None = None,
    ) -> AgentContext:
        """Build the context for an agent's turn."""
        # Get location info
        location = ctx.world.locations.get(agent.location)
        location_description = location.description if location else "Unknown location"

        # Get others present (excluding self, excluding sleeping)
        others = [
            a.name for a in ctx.agents.values()
            if a.location == agent.location
            and a.name != agent.name
            and not a.is_sleeping
        ]

        # Get available paths
        available_paths = list(location.connections) if location else []

        # Get conversation context if in one
        conversations = ctx.get_conversations_for_agent(agent.name)
        conversation = conversations[0] if conversations else None
        unseen_history = None
        is_opener = False
        is_group = False

        if conversation:
            # Find unseen history
            agent_last_turn_idx = -1
            for i, turn in enumerate(conversation.history):
                if turn.speaker == agent.name:
                    agent_last_turn_idx = i

            if agent_last_turn_idx >= 0:
                unseen_history = [
                    {"speaker": t.speaker, "narrative": t.narrative}
                    for t in conversation.history[agent_last_turn_idx + 1:]
                ]
            else:
                unseen_history = [
                    {"speaker": t.speaker, "narrative": t.narrative}
                    for t in conversation.history
                ]

            is_opener = len(conversation.history) == 0
            is_group = len(conversation.participants) > 2

        # Get pending invite
        pending_invite = ctx.pending_invites.get(agent.name)

        # Get joinable conversations (public ones agent can join)
        joinable = ctx.get_public_conversations_at_location(agent.location)
        joinable = [c for c in joinable if agent.name not in c.participants]

        # Get private conversations (for awareness only)
        private = ctx.get_private_conversations_at_location(agent.location)
        private = [c for c in private if agent.name not in c.participants]

        recent_event_descriptions = self._filter_recent_event_descriptions(
            agent,
            ctx,
            recent_events or [],
        )

        return AgentContext(
            agent=agent,
            location_description=location_description,
            weather=ctx.world.weather.value,
            time_description=self._format_time(ctx),
            others_present=others,
            available_paths=available_paths,
            conversation=conversation,
            unseen_history=unseen_history,
            is_opener=is_opener,
            is_group=is_group,
            pending_invite=pending_invite,
            joinable_conversations=joinable if joinable else None,
            private_conversations=private if private else None,
            shared_files=shared_files if shared_files else None,
            recent_events=recent_event_descriptions if recent_event_descriptions else None,
            unseen_dreams=unseen_dreams if unseen_dreams else None,
        )

    def _get_recent_events(self) -> list[DomainEvent]:
        """Fetch recent world-related events for context."""
        if self._event_store is None:
            return []
        return self._event_store.get_recent_events(
            limit=20,
            event_types={"world_event", "weather_changed"},
        )

    def _filter_recent_event_descriptions(
        self,
        agent: AgentSnapshot,
        ctx: TickContext,
        events: list[DomainEvent],
    ) -> list[str]:
        """Filter events to those relevant for this agent."""
        descriptions: list[str] = []
        agent_location = agent.location

        for event in events:
            match event:
                case WorldEventOccurred():
                    if event.agents_involved == (agent.name,):
                        continue
                    if (
                        event.location is None
                        or event.location == agent_location
                        or agent.name in event.agents_involved
                    ):
                        descriptions.append(event.description)
                case WeatherChangedEvent():
                    descriptions.append(
                        f"The weather has changed to {event.new_weather}."
                    )

        return descriptions

    def _format_time(self, ctx: TickContext) -> str:
        """Format time for display in context."""
        ts = ctx.time_snapshot
        hour = ts.world_time.hour
        period = ts.period.value

        if hour == 0:
            time_str = "midnight"
        elif hour == 12:
            time_str = "noon"
        elif hour < 12:
            time_str = f"{hour}:00 AM"
        else:
            time_str = f"{hour - 12}:00 PM"

        return f"{time_str} ({period})"
