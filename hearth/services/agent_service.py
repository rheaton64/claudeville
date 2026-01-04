"""Agent service for Hearth.

Provides agent roster management as a thin service layer over storage repositories.
No in-memory caching - always delegates to storage.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from core.types import Position, Direction, Rect, AgentName, ObjectId, LandmarkName
from core.agent import Agent, Inventory, Journey, JourneyDestination, Item
from core.world import WorldState

if TYPE_CHECKING:
    from storage import Storage
    from .world_service import WorldService


# -----------------------------------------------------------------------------
# Exceptions
# -----------------------------------------------------------------------------


class AgentServiceError(Exception):
    """Base exception for AgentService errors."""

    pass


class AgentNotFoundError(AgentServiceError):
    """Agent with given name not found."""

    def __init__(self, message: str, agent_name: AgentName | None = None):
        super().__init__(message)
        self.agent_name = agent_name


class InvalidAgentStateError(AgentServiceError):
    """Agent is in invalid state for operation."""

    pass


class JourneyError(AgentServiceError):
    """Error related to journey operations."""

    pass


class InventoryError(AgentServiceError):
    """Error related to inventory operations."""

    pass


# -----------------------------------------------------------------------------
# Presence Sensing Types
# -----------------------------------------------------------------------------


DistanceCategory = Literal["nearby", "far", "very far"]


@dataclass(frozen=True)
class SensedAgent:
    """Information about a sensed agent.

    Categorical distance buckets:
    - nearby: ≤10 cells (Manhattan distance)
    - far: 11-30 cells
    - very far: 31+ cells
    """

    name: AgentName
    direction: Direction | None  # Primary direction (N/S/E/W), None if same position
    distance_category: DistanceCategory


# -----------------------------------------------------------------------------
# AgentService
# -----------------------------------------------------------------------------


class AgentService:
    """Agent roster management for Hearth.

    A thin service layer over AgentRepository.
    No in-memory caching - always delegates to storage.
    """

    def __init__(self, storage: "Storage"):
        """Initialize AgentService.

        Args:
            storage: Connected Storage instance
        """
        self._storage = storage

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def _agent_repo(self):
        """Get agent repository."""
        return self._storage.agents

    # -------------------------------------------------------------------------
    # Roster Operations (CRUD)
    # -------------------------------------------------------------------------

    async def get_agent(self, name: AgentName) -> Agent | None:
        """Get an agent by name.

        Args:
            name: Agent name

        Returns:
            Agent if found, None otherwise
        """
        return await self._agent_repo.get_agent(name)

    async def get_agent_or_raise(self, name: AgentName) -> Agent:
        """Get an agent by name, raising if not found.

        Args:
            name: Agent name

        Returns:
            Agent

        Raises:
            AgentNotFoundError: If agent doesn't exist
        """
        agent = await self._agent_repo.get_agent(name)
        if agent is None:
            raise AgentNotFoundError(f"Agent '{name}' not found", name)
        return agent

    async def get_all_agents(self) -> list[Agent]:
        """Get all agents.

        Returns:
            List of all agents
        """
        return await self._agent_repo.get_all_agents()

    async def save_agent(self, agent: Agent) -> None:
        """Save or update an agent.

        Args:
            agent: Agent to save
        """
        await self._agent_repo.save_agent(agent)

    async def delete_agent(self, name: AgentName) -> None:
        """Delete an agent.

        Args:
            name: Agent name to delete
        """
        await self._agent_repo.delete_agent(name)

    # -------------------------------------------------------------------------
    # Spatial Queries
    # -------------------------------------------------------------------------

    async def get_agents_at(self, position: Position) -> list[Agent]:
        """Get all agents at a specific position.

        Args:
            position: Position to query

        Returns:
            List of agents at that position
        """
        # Use rect query with single-cell rect
        rect = Rect(position.x, position.y, position.x, position.y)
        return await self._agent_repo.get_agents_in_rect(rect)

    async def get_agents_in_rect(self, rect: Rect) -> list[Agent]:
        """Get all agents within a rectangle.

        Args:
            rect: Rectangle to query

        Returns:
            List of agents in the rect
        """
        return await self._agent_repo.get_agents_in_rect(rect)

    async def get_nearby_agents(
        self, position: Position, radius: int = 10
    ) -> list[Agent]:
        """Get all agents within radius of a position.

        Args:
            position: Center position
            radius: Maximum distance (Manhattan)

        Returns:
            List of agents within radius
        """
        # Create bounding rect
        rect = Rect(
            position.x - radius,
            position.y - radius,
            position.x + radius,
            position.y + radius,
        )
        agents = await self._agent_repo.get_agents_in_rect(rect)

        # Filter by actual Manhattan distance
        return [
            a for a in agents if position.distance_to(a.position) <= radius
        ]

    # -------------------------------------------------------------------------
    # State Queries
    # -------------------------------------------------------------------------

    async def get_awake_agents(self) -> list[Agent]:
        """Get all agents that are not sleeping.

        Returns:
            List of awake agents
        """
        agents = await self.get_all_agents()
        return [a for a in agents if not a.is_sleeping]

    async def get_sleeping_agents(self) -> list[Agent]:
        """Get all agents that are sleeping.

        Returns:
            List of sleeping agents
        """
        agents = await self.get_all_agents()
        return [a for a in agents if a.is_sleeping]

    async def get_traveling_agents(self) -> list[Agent]:
        """Get all agents with active journeys.

        Returns:
            List of agents currently traveling
        """
        agents = await self.get_all_agents()
        return [a for a in agents if a.is_journeying]

    # -------------------------------------------------------------------------
    # Relationship Queries
    # -------------------------------------------------------------------------

    async def get_known_agents(self, name: AgentName) -> frozenset[AgentName]:
        """Get the set of agents that a specific agent knows.

        Args:
            name: Agent whose known agents to get

        Returns:
            frozenset of known agent names

        Raises:
            AgentNotFoundError: If agent doesn't exist
        """
        agent = await self.get_agent_or_raise(name)
        return agent.known_agents

    async def have_met(self, agent1: AgentName, agent2: AgentName) -> bool:
        """Check if two agents have met each other.

        Args:
            agent1: First agent name
            agent2: Second agent name

        Returns:
            True if they know each other, False otherwise
        """
        a1 = await self.get_agent(agent1)
        if a1 is None:
            return False
        return agent2 in a1.known_agents

    # -------------------------------------------------------------------------
    # Position Updates
    # -------------------------------------------------------------------------

    async def update_position(self, name: AgentName, new_position: Position) -> Agent:
        """Update an agent's position.

        Args:
            name: Agent name
            new_position: New position

        Returns:
            Updated agent

        Raises:
            AgentNotFoundError: If agent doesn't exist
        """
        agent = await self.get_agent_or_raise(name)
        updated = agent.with_position(new_position)
        await self.save_agent(updated)
        return updated

    async def move_agent(
        self, name: AgentName, direction: Direction, world_service: "WorldService"
    ) -> Agent:
        """Move an agent one cell in a direction, validating passability.

        Args:
            name: Agent name
            direction: Direction to move
            world_service: WorldService for passability checks

        Returns:
            Updated agent at new position

        Raises:
            AgentNotFoundError: If agent doesn't exist
            InvalidAgentStateError: If movement is blocked
        """
        agent = await self.get_agent_or_raise(name)

        if not await world_service.can_move(agent.position, direction):
            raise InvalidAgentStateError(
                f"Cannot move {direction.name} from {agent.position}"
            )

        new_position = agent.position + direction
        return await self.update_position(name, new_position)

    # -------------------------------------------------------------------------
    # Sleep State
    # -------------------------------------------------------------------------

    async def set_sleeping(self, name: AgentName, is_sleeping: bool) -> Agent:
        """Set an agent's sleep state.

        Args:
            name: Agent name
            is_sleeping: New sleep state

        Returns:
            Updated agent

        Raises:
            AgentNotFoundError: If agent doesn't exist
        """
        agent = await self.get_agent_or_raise(name)
        updated = agent.with_sleeping(is_sleeping)
        await self.save_agent(updated)
        return updated

    async def wake_agent(self, name: AgentName) -> Agent:
        """Wake an agent up.

        Args:
            name: Agent name

        Returns:
            Updated agent

        Raises:
            AgentNotFoundError: If agent doesn't exist
        """
        return await self.set_sleeping(name, False)

    async def sleep_agent(self, name: AgentName) -> Agent:
        """Put an agent to sleep.

        Args:
            name: Agent name

        Returns:
            Updated agent

        Raises:
            AgentNotFoundError: If agent doesn't exist
        """
        return await self.set_sleeping(name, True)

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------

    async def record_meeting(
        self, agent1: AgentName, agent2: AgentName
    ) -> tuple[Agent, Agent]:
        """Record that two agents have met each other.

        Updates both agents to know each other.

        Args:
            agent1: First agent name
            agent2: Second agent name

        Returns:
            Tuple of both updated agents

        Raises:
            AgentNotFoundError: If either agent doesn't exist
        """
        a1 = await self.get_agent_or_raise(agent1)
        a2 = await self.get_agent_or_raise(agent2)

        updated_a1 = a1.with_known_agent(agent2)
        updated_a2 = a2.with_known_agent(agent1)

        await self.save_agent(updated_a1)
        await self.save_agent(updated_a2)

        return updated_a1, updated_a2

    # -------------------------------------------------------------------------
    # Session Tracking
    # -------------------------------------------------------------------------

    async def update_session(
        self, name: AgentName, session_id: str | None, tick: int
    ) -> Agent:
        """Update an agent's session info.

        Args:
            name: Agent name
            session_id: New session ID (or None)
            tick: Current tick

        Returns:
            Updated agent

        Raises:
            AgentNotFoundError: If agent doesn't exist
        """
        agent = await self.get_agent_or_raise(name)
        updated = agent.with_session_id(session_id).with_last_active_tick(tick)
        await self.save_agent(updated)
        return updated

    # -------------------------------------------------------------------------
    # Inventory Operations
    # -------------------------------------------------------------------------

    async def add_resource(
        self, name: AgentName, item_type: str, quantity: int = 1
    ) -> Agent:
        """Add a stackable resource to agent's inventory.

        Args:
            name: Agent name
            item_type: Type of resource (e.g., "wood", "stone")
            quantity: Amount to add

        Returns:
            Updated agent

        Raises:
            AgentNotFoundError: If agent doesn't exist
        """
        agent = await self.get_agent_or_raise(name)
        updated = agent.add_resource(item_type, quantity)
        await self.save_agent(updated)
        return updated

    async def remove_resource(
        self, name: AgentName, item_type: str, quantity: int = 1
    ) -> Agent:
        """Remove a stackable resource from agent's inventory.

        Args:
            name: Agent name
            item_type: Type of resource
            quantity: Amount to remove

        Returns:
            Updated agent

        Raises:
            AgentNotFoundError: If agent doesn't exist
            InventoryError: If insufficient quantity
        """
        agent = await self.get_agent_or_raise(name)
        try:
            updated = agent.remove_resource(item_type, quantity)
        except ValueError as e:
            raise InventoryError(str(e)) from e
        await self.save_agent(updated)
        return updated

    async def get_resource_quantity(self, name: AgentName, item_type: str) -> int:
        """Get the quantity of a resource in agent's inventory.

        Args:
            name: Agent name
            item_type: Type of resource

        Returns:
            Quantity (0 if not present)

        Raises:
            AgentNotFoundError: If agent doesn't exist
        """
        agent = await self.get_agent_or_raise(name)
        return agent.inventory.get_resource_quantity(item_type)

    async def has_resource(
        self, name: AgentName, item_type: str, quantity: int = 1
    ) -> bool:
        """Check if agent has at least the specified quantity of a resource.

        Args:
            name: Agent name
            item_type: Type of resource
            quantity: Required amount

        Returns:
            True if agent has enough, False otherwise

        Raises:
            AgentNotFoundError: If agent doesn't exist
        """
        agent = await self.get_agent_or_raise(name)
        return agent.inventory.has_resource(item_type, quantity)

    async def add_item(self, name: AgentName, item: Item) -> Agent:
        """Add a unique item to agent's inventory.

        Args:
            name: Agent name
            item: Item to add

        Returns:
            Updated agent

        Raises:
            AgentNotFoundError: If agent doesn't exist
        """
        agent = await self.get_agent_or_raise(name)
        updated = agent.add_item(item)
        await self.save_agent(updated)
        return updated

    async def remove_item(self, name: AgentName, item_id: ObjectId) -> Agent:
        """Remove a unique item from agent's inventory.

        Args:
            name: Agent name
            item_id: ID of item to remove

        Returns:
            Updated agent

        Raises:
            AgentNotFoundError: If agent doesn't exist
            InventoryError: If item not found
        """
        agent = await self.get_agent_or_raise(name)
        try:
            updated = agent.remove_item(item_id)
        except ValueError as e:
            raise InventoryError(str(e)) from e
        await self.save_agent(updated)
        return updated

    async def get_item(self, name: AgentName, item_id: ObjectId) -> Item | None:
        """Get a specific item from agent's inventory.

        Args:
            name: Agent name
            item_id: Item ID to find

        Returns:
            Item if found, None otherwise

        Raises:
            AgentNotFoundError: If agent doesn't exist
        """
        agent = await self.get_agent_or_raise(name)
        return agent.inventory.get_item(item_id)

    async def get_inventory(self, name: AgentName) -> Inventory:
        """Get agent's full inventory.

        Args:
            name: Agent name

        Returns:
            Agent's inventory

        Raises:
            AgentNotFoundError: If agent doesn't exist
        """
        agent = await self.get_agent_or_raise(name)
        return agent.inventory

    async def set_inventory(self, name: AgentName, inventory: Inventory) -> Agent:
        """Replace agent's entire inventory.

        Args:
            name: Agent name
            inventory: New inventory

        Returns:
            Updated agent

        Raises:
            AgentNotFoundError: If agent doesn't exist
        """
        agent = await self.get_agent_or_raise(name)
        updated = agent.with_inventory(inventory)
        await self.save_agent(updated)
        return updated

    # -------------------------------------------------------------------------
    # Presence Sensing
    # -------------------------------------------------------------------------

    async def sense_others(self, name: AgentName) -> list[SensedAgent]:
        """Sense direction and rough distance to all known agents.

        Only senses agents that the querying agent has met.
        Sleeping agents are excluded from sensing.

        Distance categories:
        - nearby: ≤10 cells (Manhattan distance)
        - far: 11-30 cells
        - very far: 31+ cells

        Args:
            name: Agent doing the sensing

        Returns:
            List of sensed agent information

        Raises:
            AgentNotFoundError: If agent doesn't exist
        """
        agent = await self.get_agent_or_raise(name)

        results: list[SensedAgent] = []

        for other_name in agent.known_agents:
            other = await self.get_agent(other_name)
            if other is None or other.is_sleeping:
                continue

            distance = agent.position.distance_to(other.position)
            direction = agent.position.direction_to(other.position)

            if distance <= 10:
                category: DistanceCategory = "nearby"
            elif distance <= 30:
                category = "far"
            else:
                category = "very far"

            results.append(SensedAgent(other_name, direction, category))

        return results

    # -------------------------------------------------------------------------
    # Journey State Machine
    # -------------------------------------------------------------------------

    async def start_journey(
        self,
        name: AgentName,
        destination: Position | LandmarkName,
        world_service: "WorldService",
    ) -> Agent:
        """Start a journey to a destination.

        Computes path using A* and sets journey state.

        Args:
            name: Agent name
            destination: Target position or landmark name
            world_service: WorldService for pathfinding

        Returns:
            Updated agent with journey

        Raises:
            AgentNotFoundError: If agent doesn't exist
            JourneyError: If no path exists or destination invalid
        """
        agent = await self.get_agent_or_raise(name)

        # Resolve destination to position
        if isinstance(destination, str):
            # It's a landmark name
            landmark_pos = await world_service.get_place_position(destination)
            if landmark_pos is None:
                raise JourneyError(f"Unknown landmark: {destination}")
            dest = JourneyDestination.to_landmark(LandmarkName(destination))
            target_pos = landmark_pos
        else:
            dest = JourneyDestination.to_position(destination)
            target_pos = destination

        # Check if already at destination
        if agent.position == target_pos:
            raise JourneyError("Already at destination")

        # Compute path using A*
        path = await self._compute_path(agent.position, target_pos, world_service)

        # Create journey
        journey = Journey.create(destination=dest, path=path)
        updated = agent.with_journey(journey)
        await self.save_agent(updated)
        return updated

    async def advance_journey(self, name: AgentName) -> tuple[Agent, bool]:
        """Advance an agent one step along their journey.

        Args:
            name: Agent name

        Returns:
            Tuple of (updated agent, arrived at destination)

        Raises:
            AgentNotFoundError: If agent doesn't exist
            JourneyError: If agent is not on a journey
        """
        agent = await self.get_agent_or_raise(name)

        if agent.journey is None:
            raise JourneyError(f"Agent {name} is not on a journey")

        # Advance the journey
        new_journey = agent.journey.advance()

        # Get the new position
        new_pos = new_journey.current_position
        if new_pos is None:
            # Shouldn't happen if journey is set up correctly
            raise JourneyError("Journey has no valid position")

        # Check if arrived
        arrived = new_journey.is_complete

        # Update agent
        if arrived:
            # Clear journey on arrival
            updated = agent.with_position(new_pos).with_journey(None)
        else:
            updated = agent.with_position(new_pos).with_journey(new_journey)

        await self.save_agent(updated)
        return updated, arrived

    async def interrupt_journey(
        self,
        name: AgentName,
        reason: str,
    ) -> Agent:
        """Interrupt an agent's journey.

        Args:
            name: Agent name
            reason: Reason for interruption (e.g., "encountered_agent", "world_event")

        Returns:
            Updated agent with cleared journey

        Raises:
            AgentNotFoundError: If agent doesn't exist
        """
        agent = await self.get_agent_or_raise(name)

        # Clear journey (agent stays at current position)
        updated = agent.with_journey(None)
        await self.save_agent(updated)
        return updated

    async def is_traveling(self, name: AgentName) -> bool:
        """Check if an agent is currently on a journey.

        Args:
            name: Agent name

        Returns:
            True if traveling, False otherwise

        Raises:
            AgentNotFoundError: If agent doesn't exist
        """
        agent = await self.get_agent_or_raise(name)
        return agent.is_journeying

    async def get_journey_progress(
        self, name: AgentName
    ) -> tuple[int, int] | None:
        """Get journey progress as (current step, total steps).

        Args:
            name: Agent name

        Returns:
            Tuple of (current, total) or None if not journeying

        Raises:
            AgentNotFoundError: If agent doesn't exist
        """
        agent = await self.get_agent_or_raise(name)

        if agent.journey is None:
            return None

        return (agent.journey.progress, len(agent.journey.path) - 1)

    async def _compute_path(
        self,
        start: Position,
        goal: Position,
        world_service: "WorldService",
    ) -> tuple[Position, ...]:
        """Compute path from start to goal using A*.

        Args:
            start: Starting position
            goal: Goal position
            world_service: WorldService for passability checks

        Returns:
            Tuple of positions from start to goal (inclusive)

        Raises:
            JourneyError: If no path exists
        """
        if start == goal:
            return (start,)

        # A* algorithm
        # Priority queue: (f_score, counter, position)
        # counter is for tie-breaking when f_scores are equal
        counter = 0
        open_set: list[tuple[int, int, Position]] = []
        heapq.heappush(open_set, (0, counter, start))

        came_from: dict[Position, Position] = {}
        g_score: dict[Position, int] = {start: 0}

        while open_set:
            _, _, current = heapq.heappop(open_set)

            if current == goal:
                # Reconstruct path
                path = [current]
                while current in came_from:
                    current = came_from[current]
                    path.append(current)
                path.reverse()
                return tuple(path)

            for direction in Direction:
                if not await world_service.can_move(current, direction):
                    continue

                neighbor = current + direction
                tentative_g = g_score[current] + 1

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score = tentative_g + neighbor.distance_to(goal)
                    counter += 1
                    heapq.heappush(open_set, (f_score, counter, neighbor))

        raise JourneyError(f"No path from {start} to {goal}")

    # -------------------------------------------------------------------------
    # Home Directory Management
    # -------------------------------------------------------------------------

    def ensure_home_directory(self, name: AgentName, agents_root: Path) -> Path:
        """Create agent home directory with initial files if needed.

        Creates:
        - agents/{name}/journal.md - "# Journal\\n"
        - agents/{name}/notes.md - "# Notes\\n"
        - agents/{name}/discoveries.md - "# Discoveries\\n"

        Args:
            name: Agent name
            agents_root: Root directory for all agent homes

        Returns:
            Path to agent's home directory
        """
        home = agents_root / str(name)
        home.mkdir(parents=True, exist_ok=True)

        # Create initial files with light headers (only if they don't exist)
        files = {
            "journal.md": "# Journal\n",
            "notes.md": "# Notes\n",
            "discoveries.md": "# Discoveries\n",
        }
        for filename, content in files.items():
            filepath = home / filename
            if not filepath.exists():
                filepath.write_text(content)

        return home

    def generate_status_file(
        self,
        agent: Agent,
        agents_root: Path,
        world_state: WorldState,
    ) -> None:
        """Generate .status file for agent (R/O reference).

        Contains position, time, weather, and inventory summary.

        Args:
            agent: Agent to generate status for
            agents_root: Root directory for all agent homes
            world_state: Current world state
        """
        home = agents_root / str(agent.name)
        home.mkdir(parents=True, exist_ok=True)

        status_content = f"""# Status (System Generated)

## Position
x: {agent.position.x}
y: {agent.position.y}

## Time
Tick: {world_state.current_tick}
Weather: {world_state.weather.value}

## Inventory
{self._format_inventory(agent.inventory)}
"""
        (home / ".status").write_text(status_content)

    def _format_inventory(self, inventory: Inventory) -> str:
        """Format inventory for status file."""
        lines: list[str] = []

        for stack in inventory.stacks:
            lines.append(f"- {stack.item_type}: {stack.quantity}")

        for item in inventory.items:
            props = ", ".join(item.properties) if item.properties else "no properties"
            lines.append(f"- {item.item_type} ({props})")

        return "\n".join(lines) if lines else "Empty"

    # -------------------------------------------------------------------------
    # Initialization / Bootstrap
    # -------------------------------------------------------------------------

    async def initialize_agent(
        self,
        agent: Agent,
        agents_root: Path,
    ) -> Agent:
        """Initialize a new agent: save to DB and create home directory.

        Args:
            agent: Agent to initialize
            agents_root: Root directory for all agent homes

        Returns:
            The saved agent
        """
        await self.save_agent(agent)
        self.ensure_home_directory(agent.name, agents_root)
        return agent

    async def initialize_agents(
        self,
        agents: list[Agent],
        agents_root: Path,
    ) -> list[Agent]:
        """Bulk initialize multiple agents.

        Args:
            agents: List of agents to initialize
            agents_root: Root directory for all agent homes

        Returns:
            List of saved agents
        """
        results: list[Agent] = []
        for agent in agents:
            results.append(await self.initialize_agent(agent, agents_root))
        return results
