"""
TickContext - immutable context passed through tick phases.

The context carries all state needed for a tick and accumulates effects/events
as phases execute. Each phase returns a new context with updates applied via
the with_* methods.

Design principles:
- Treat as immutable (use with_* methods to create new instances)
- Phases read from context, produce effects/events
- Engine commits changes after all phases complete
"""

from datetime import datetime
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field

from engine.domain import (
    AgentName,
    AgentSnapshot,
    LocationId,
    ConversationId,
    Conversation,
    Invitation,
    TimeSnapshot,
    WorldSnapshot,
    Effect,
    DomainEvent,
)
from engine.services.scheduler import ScheduledEvent
from engine.runtime.interpreter import AgentTurnResult


class TickContext(BaseModel):
    """
    Immutable context passed through tick phases.

    Contains all state needed for tick execution plus accumulated
    effects and events from phase processing.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    # --- Tick identity ---
    tick: int
    timestamp: datetime
    time_snapshot: TimeSnapshot

    # --- World state (read from services at tick start) ---
    world: WorldSnapshot
    agents: dict[AgentName, AgentSnapshot]
    conversations: dict[ConversationId, Conversation]
    pending_invites: dict[AgentName, Invitation]

    # --- Scheduled events that triggered this tick ---
    scheduled_events: list[ScheduledEvent] = Field(default_factory=list)

    # --- Accumulated during phase execution ---
    effects: tuple[Effect, ...] = ()
    events: tuple[DomainEvent, ...] = ()
    turn_results: dict[AgentName, AgentTurnResult] = Field(default_factory=dict)

    # --- Tracking which agents act ---
    agents_to_act: frozenset[AgentName] = frozenset()
    agents_acted: frozenset[AgentName] = frozenset()

    # ==========================================================================
    # Transformation methods (return new context)
    # ==========================================================================

    def with_effect(self, effect: Effect) -> "TickContext":
        """Add a single effect."""
        return self.model_copy(update={"effects": (*self.effects, effect)})

    def with_effects(self, effects: Iterable[Effect]) -> "TickContext":
        """Add multiple effects."""
        return self.model_copy(update={"effects": (*self.effects, *effects)})

    def with_event(self, event: DomainEvent) -> "TickContext":
        """Add a single domain event."""
        return self.model_copy(update={"events": (*self.events, event)})

    def with_events(self, events: Iterable[DomainEvent]) -> "TickContext":
        """Add multiple domain events."""
        return self.model_copy(update={"events": (*self.events, *events)})

    def with_turn_result(
        self, agent: AgentName, result: AgentTurnResult
    ) -> "TickContext":
        """Add a turn result for an agent."""
        new_results = {**self.turn_results, agent: result}
        return self.model_copy(update={"turn_results": new_results})

    def with_agents_to_act(self, agents: frozenset[AgentName]) -> "TickContext":
        """Set which agents should act this tick."""
        return self.model_copy(update={"agents_to_act": agents})

    def with_agent_acted(self, agent: AgentName) -> "TickContext":
        """Mark an agent as having acted."""
        return self.model_copy(update={"agents_acted": self.agents_acted | {agent}})

    def with_updated_agent(self, agent: AgentSnapshot) -> "TickContext":
        """Update an agent's snapshot in the context."""
        new_agents = {**self.agents, agent.name: agent}
        return self.model_copy(update={"agents": new_agents})

    def with_updated_conversation(self, conv: Conversation) -> "TickContext":
        """Update a conversation in the context."""
        new_convs = {**self.conversations, conv.id: conv}
        return self.model_copy(update={"conversations": new_convs})

    def with_removed_conversation(self, conv_id: ConversationId) -> "TickContext":
        """Remove a conversation from the context."""
        new_convs = {k: v for k, v in self.conversations.items() if k != conv_id}
        return self.model_copy(update={"conversations": new_convs})

    def with_removed_invite(self, invitee: AgentName) -> "TickContext":
        """Remove a pending invite from the context."""
        new_invites = {k: v for k, v in self.pending_invites.items() if k != invitee}
        return self.model_copy(update={"pending_invites": new_invites})

    def with_added_invite(self, invite: Invitation) -> "TickContext":
        """Add a pending invite to the context."""
        new_invites = {**self.pending_invites, invite.invitee: invite}
        return self.model_copy(update={"pending_invites": new_invites})

    # ==========================================================================
    # Query helpers
    # ==========================================================================

    def get_agent(self, name: AgentName) -> AgentSnapshot | None:
        """Get an agent by name."""
        return self.agents.get(name)

    def get_agents_at_location(self, location: LocationId) -> list[AgentSnapshot]:
        """Get all agents at a specific location."""
        return [a for a in self.agents.values() if a.location == location]

    def get_conversation(self, conv_id: ConversationId) -> Conversation | None:
        """Get a conversation by ID."""
        return self.conversations.get(conv_id)

    def get_conversations_for_agent(self, agent: AgentName) -> list[Conversation]:
        """Get all conversations an agent is participating in."""
        return [c for c in self.conversations.values() if agent in c.participants]

    def get_public_conversations_at_location(
        self, location: LocationId
    ) -> list[Conversation]:
        """Get public conversations at a location (for join opportunities)."""
        return [
            c for c in self.conversations.values()
            if c.location == location and c.privacy == "public"
        ]

    def get_private_conversations_at_location(
        self, location: LocationId
    ) -> list[Conversation]:
        """Get private conversations at a location (for awareness only)."""
        return [
            c for c in self.conversations.values()
            if c.location == location and c.privacy == "private"
        ]


class TickResult(BaseModel):
    """
    Result of executing a tick.

    This is what the engine receives after pipeline execution.
    Contains all events to commit and effects that were applied.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    tick: int
    timestamp: datetime
    events: tuple[DomainEvent, ...]
    effects: tuple[Effect, ...]
    turn_results: dict[AgentName, AgentTurnResult]
    agents_acted: frozenset[AgentName]

    @classmethod
    def from_context(cls, ctx: TickContext) -> "TickResult":
        """Create a TickResult from a completed TickContext."""
        return cls(
            tick=ctx.tick,
            timestamp=ctx.timestamp,
            events=ctx.events,
            effects=ctx.effects,
            turn_results=dict(ctx.turn_results),
            agents_acted=ctx.agents_acted,
        )
