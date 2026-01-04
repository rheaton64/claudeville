"""Tick context for Hearth engine.

TickContext is the immutable state carrier passed through tick phases.
TurnResult captures the outcome of an agent's turn.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from core.terrain import Weather
from core.types import AgentName, TurnTokenUsage
from core.agent import Agent
from core.events import DomainEvent

if TYPE_CHECKING:
    from adapters.perception import AgentPerception
    from core.actions import Action


@dataclass
class TurnResult:
    """Result of an agent's turn.

    Captures what happened during an agent's turn for debugging and context.
    """

    agent_name: AgentName
    perception: "AgentPerception"
    actions_taken: list["Action"] = field(default_factory=list)
    events: list[DomainEvent] = field(default_factory=list)
    narrative: str = ""  # Combined narrative from the turn
    session_id: str | None = None  # SDK session ID for resume
    token_usage: TurnTokenUsage | None = None  # Token usage info


@dataclass(frozen=True)
class TickContext:
    """Immutable context passed through tick phases.

    Each phase receives the context, processes it, and returns a new
    context with updated fields. The frozen dataclass ensures immutability.

    Fields are grouped into:
    - Core state: tick, time_of_day, weather
    - Snapshots: agents (read-only reference to agent states)
    - Accumulated output: agents_to_act, agents_to_wake, clusters, events, turn_results
    """

    # Core state
    tick: int
    time_of_day: str  # "morning", "afternoon", "evening", "night"
    weather: Weather

    # Snapshots (read-only at start of tick)
    agents: dict[AgentName, Agent]

    # Accumulated output (populated by phases)
    agents_to_act: frozenset[AgentName] = field(default_factory=frozenset)
    agents_to_wake: frozenset[AgentName] = field(default_factory=frozenset)
    clusters: tuple[tuple[AgentName, ...], ...] = ()
    events: tuple[DomainEvent, ...] = ()
    turn_results: dict[AgentName, TurnResult] = field(default_factory=dict)

    def with_agents_to_act(self, agents: frozenset[AgentName]) -> TickContext:
        """Return new context with updated agents_to_act."""
        return TickContext(
            tick=self.tick,
            time_of_day=self.time_of_day,
            weather=self.weather,
            agents=self.agents,
            agents_to_act=agents,
            agents_to_wake=self.agents_to_wake,
            clusters=self.clusters,
            events=self.events,
            turn_results=self.turn_results,
        )

    def with_agents_to_wake(self, agents: frozenset[AgentName]) -> TickContext:
        """Return new context with updated agents_to_wake."""
        return TickContext(
            tick=self.tick,
            time_of_day=self.time_of_day,
            weather=self.weather,
            agents=self.agents,
            agents_to_act=self.agents_to_act,
            agents_to_wake=agents,
            clusters=self.clusters,
            events=self.events,
            turn_results=self.turn_results,
        )

    def with_agents(self, agents: dict[AgentName, Agent]) -> TickContext:
        """Return new context with updated agents snapshot."""
        return TickContext(
            tick=self.tick,
            time_of_day=self.time_of_day,
            weather=self.weather,
            agents=agents,
            agents_to_act=self.agents_to_act,
            agents_to_wake=self.agents_to_wake,
            clusters=self.clusters,
            events=self.events,
            turn_results=self.turn_results,
        )

    def with_clusters(
        self, clusters: list[list[AgentName]]
    ) -> TickContext:
        """Return new context with updated clusters.

        Converts mutable lists to immutable tuples for frozen dataclass.
        """
        immutable_clusters = tuple(tuple(c) for c in clusters)
        return TickContext(
            tick=self.tick,
            time_of_day=self.time_of_day,
            weather=self.weather,
            agents=self.agents,
            agents_to_act=self.agents_to_act,
            agents_to_wake=self.agents_to_wake,
            clusters=immutable_clusters,
            events=self.events,
            turn_results=self.turn_results,
        )

    def with_events(self, events: tuple[DomainEvent, ...]) -> TickContext:
        """Return new context with updated events."""
        return TickContext(
            tick=self.tick,
            time_of_day=self.time_of_day,
            weather=self.weather,
            agents=self.agents,
            agents_to_act=self.agents_to_act,
            agents_to_wake=self.agents_to_wake,
            clusters=self.clusters,
            events=events,
            turn_results=self.turn_results,
        )

    def with_turn_results(
        self, results: dict[AgentName, TurnResult]
    ) -> TickContext:
        """Return new context with updated turn_results."""
        return TickContext(
            tick=self.tick,
            time_of_day=self.time_of_day,
            weather=self.weather,
            agents=self.agents,
            agents_to_act=self.agents_to_act,
            agents_to_wake=self.agents_to_wake,
            clusters=self.clusters,
            events=self.events,
            turn_results=results,
        )

    def append_events(self, new_events: list[DomainEvent]) -> TickContext:
        """Return new context with events appended."""
        return self.with_events(self.events + tuple(new_events))
