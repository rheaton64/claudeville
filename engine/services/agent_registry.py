"""
Agent registry - manages agent state and provides lookup methods.

This separates agent identity/state from scheduling concerns.
Runner management will be added in the adapters layer.
"""

from engine.domain import (
    AgentSnapshot,
    AgentName,
    LocationId,
    TimePeriod,
)


class AgentRegistry:
    """
    Registry of all agents in the village.

    Provides:
    - Agent state storage and lookup
    - Location-based queries
    - Sleep state management
    - State updates (returns new snapshots, doesn't mutate)

    Note: This doesn't manage Claude SDK runners - that's in adapters/claude_provider.py.
    This keeps the domain logic separate from external integrations.
    """

    def __init__(self):
        self._agents: dict[AgentName, AgentSnapshot] = {}

    def load_state(self, agents: dict[AgentName, AgentSnapshot]) -> None:
        """
        Load agent state from snapshot.

        Called during initialization or recovery.
        """
        self._agents = dict(agents)

    # =========================================================================
    # Basic CRUD
    # =========================================================================

    def register(self, agent: AgentSnapshot) -> None:
        """Register a new agent."""
        self._agents[agent.name] = agent

    def update(self, agent: AgentSnapshot) -> None:
        """
        Update an agent's state.

        Since AgentSnapshot is frozen, this replaces the old snapshot entirely.
        """
        self._agents[agent.name] = agent

    def get(self, name: AgentName) -> AgentSnapshot | None:
        """Get an agent by name."""
        return self._agents.get(name)

    def get_all(self) -> dict[AgentName, AgentSnapshot]:
        """Get all agents."""
        return dict(self._agents)

    def names(self) -> list[AgentName]:
        """Get all agent names."""
        return list(self._agents.keys())

    def count(self) -> int:
        """Get the number of registered agents."""
        return len(self._agents)

    # =========================================================================
    # Location queries
    # =========================================================================

    def get_at_location(self, location: LocationId) -> list[AgentSnapshot]:
        """Get all agents at a specific location."""
        return [a for a in self._agents.values() if a.location == location]

    def get_others_at_location(self, location: LocationId, exclude: AgentName) -> list[AgentSnapshot]:
        """Get all agents at a location except one."""
        return [
            a for a in self._agents.values()
            if a.location == location and a.name != exclude
        ]

    def count_at_location(self, location: LocationId) -> int:
        """Count agents at a location."""
        return sum(1 for a in self._agents.values() if a.location == location)

    def get_locations(self) -> dict[LocationId, list[AgentName]]:
        """Get a mapping of locations to agent names."""
        result: dict[LocationId, list[AgentName]] = {}
        for agent in self._agents.values():
            if agent.location not in result:
                result[agent.location] = []
            result[agent.location].append(agent.name)
        return result

    # =========================================================================
    # Sleep state queries
    # =========================================================================

    def get_awake(self) -> list[AgentSnapshot]:
        """Get all awake agents."""
        return [a for a in self._agents.values() if not a.is_sleeping]

    def get_sleeping(self) -> list[AgentSnapshot]:
        """Get all sleeping agents."""
        return [a for a in self._agents.values() if a.is_sleeping]

    def all_sleeping(self) -> bool:
        """Check if all agents are sleeping."""
        if not self._agents:
            return True
        return all(a.is_sleeping for a in self._agents.values())

    def any_awake(self) -> bool:
        """Check if any agent is awake."""
        return any(not a.is_sleeping for a in self._agents.values())

    # =========================================================================
    # State update helpers (return new snapshots)
    # =========================================================================

    def with_location(self, name: AgentName, location: LocationId) -> AgentSnapshot | None:
        """
        Create a new agent snapshot with updated location.

        Returns new snapshot or None if agent not found.
        Does NOT update the registry - caller must call update().
        """
        agent = self._agents.get(name)
        if agent is None:
            return None
        return AgentSnapshot(**{**agent.model_dump(), "location": location})

    def with_mood(self, name: AgentName, mood: str) -> AgentSnapshot | None:
        """Create a new agent snapshot with updated mood."""
        agent = self._agents.get(name)
        if agent is None:
            return None
        return AgentSnapshot(**{**agent.model_dump(), "mood": mood})

    def with_energy(self, name: AgentName, energy: int) -> AgentSnapshot | None:
        """Create a new agent snapshot with updated energy."""
        agent = self._agents.get(name)
        if agent is None:
            return None
        # Clamp energy to valid range
        energy = max(0, min(100, energy))
        return AgentSnapshot(**{**agent.model_dump(), "energy": energy})

    def with_sleep_state(
        self,
        name: AgentName,
        is_sleeping: bool,
        tick: int | None = None,
        period: TimePeriod | None = None,
    ) -> AgentSnapshot | None:
        """
        Create a new agent snapshot with updated sleep state.

        If is_sleeping is True, tick and period should be provided.
        If is_sleeping is False, sleep fields are cleared.
        """
        agent = self._agents.get(name)
        if agent is None:
            return None

        if is_sleeping:
            return AgentSnapshot(**{
                **agent.model_dump(),
                "is_sleeping": True,
                "sleep_started_tick": tick,
                "sleep_started_time_period": period,
            })
        else:
            return AgentSnapshot(**{
                **agent.model_dump(),
                "is_sleeping": False,
                "sleep_started_tick": None,
                "sleep_started_time_period": None,
            })

    def with_session_id(
        self,
        name: AgentName,
        session_id: str | None,
    ) -> AgentSnapshot | None:
        """Create a new agent snapshot with updated session ID."""
        agent = self._agents.get(name)
        if agent is None:
            return None
        return AgentSnapshot(**{
            **agent.model_dump(),
            "session_id": session_id,
        })
