"""Observer API for Hearth.

Query-only interface for viewing world state. Wraps storage and services
to provide a clean API for the TUI and other observers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.types import Position, Rect, AgentName, ObjectId
from core.terrain import Terrain
from core.world import Cell, WorldState
from core.agent import Agent
from core.structures import Structure
from core.objects import AnyWorldObject

if TYPE_CHECKING:
    from storage import Storage
    from services import WorldService, AgentService


class ObserverAPI:
    """Query-only interface for observing the Hearth world.

    This API provides read-only access to world state for the TUI
    and other observer tools. No mutation methods - just queries.
    """

    def __init__(
        self,
        storage: "Storage",
        world_service: "WorldService",
        agent_service: "AgentService",
    ):
        """Initialize ObserverAPI.

        Args:
            storage: Connected Storage instance
            world_service: WorldService for grid queries
            agent_service: AgentService for agent queries
        """
        self._storage = storage
        self._world = world_service
        self._agents = agent_service

    # -------------------------------------------------------------------------
    # World State Queries
    # -------------------------------------------------------------------------

    async def get_world_state(self) -> WorldState:
        """Get current world state (tick, weather, dimensions)."""
        return await self._world.get_world_state()

    async def get_world_dimensions(self) -> tuple[int, int]:
        """Get world (width, height)."""
        return await self._world.get_world_dimensions()

    # -------------------------------------------------------------------------
    # Cell Queries
    # -------------------------------------------------------------------------

    async def get_cell(self, pos: Position) -> Cell:
        """Get cell at position. Returns default cell if not stored."""
        return await self._world.get_cell(pos)

    async def get_cells_in_rect(self, rect: Rect) -> list[Cell]:
        """Get all cells in a rectangle (includes defaults for empty cells)."""
        return await self._world.get_cells_in_rect(rect)

    async def get_terrain(self, pos: Position) -> Terrain:
        """Get terrain type at position."""
        cell = await self._world.get_cell(pos)
        return cell.terrain

    async def is_passable(self, pos: Position) -> bool:
        """Check if position can be walked through."""
        return await self._world.is_position_passable(pos)

    # -------------------------------------------------------------------------
    # Object Queries
    # -------------------------------------------------------------------------

    async def get_objects_at(self, pos: Position) -> list[AnyWorldObject]:
        """Get all world objects at a position."""
        return await self._world.get_objects_at(pos)

    async def get_objects_in_rect(self, rect: Rect) -> list[AnyWorldObject]:
        """Get all world objects in a rectangle."""
        return await self._world.get_objects_in_rect(rect)

    async def get_object(self, object_id: ObjectId) -> AnyWorldObject | None:
        """Get a specific object by ID."""
        return await self._storage.objects.get_object(object_id)

    # -------------------------------------------------------------------------
    # Agent Queries
    # -------------------------------------------------------------------------

    async def get_agent(self, name: AgentName) -> Agent | None:
        """Get agent by name."""
        return await self._agents.get_agent(name)

    async def get_all_agents(self) -> list[Agent]:
        """Get all agents."""
        return await self._agents.get_all_agents()

    async def get_agent_at(self, pos: Position) -> Agent | None:
        """Get agent at a specific position, if any."""
        agents = await self._agents.get_agents_at(pos)
        return agents[0] if agents else None

    async def get_agents_at(self, pos: Position) -> list[Agent]:
        """Get all agents at a specific position."""
        return await self._agents.get_agents_at(pos)

    async def get_agents_in_rect(self, rect: Rect) -> list[Agent]:
        """Get all agents within a rectangle."""
        return await self._agents.get_agents_in_rect(rect)

    # -------------------------------------------------------------------------
    # Structure Queries
    # -------------------------------------------------------------------------

    async def get_structure(self, structure_id: ObjectId) -> Structure | None:
        """Get structure by ID."""
        return await self._world.get_structure(structure_id)

    async def get_structure_at(self, pos: Position) -> Structure | None:
        """Get structure containing this position, if any."""
        return await self._world.get_structure_at(pos)

    # -------------------------------------------------------------------------
    # Named Places
    # -------------------------------------------------------------------------

    async def get_named_places(self) -> dict[str, Position]:
        """Get all named places as {name: position}."""
        return await self._world.get_all_named_places()

    async def get_place_position(self, name: str) -> Position | None:
        """Get position of a named place."""
        return await self._world.get_place_position(name)

    # -------------------------------------------------------------------------
    # Convenience Methods for TUI
    # -------------------------------------------------------------------------

    async def get_viewport_data(
        self, rect: Rect
    ) -> tuple[list[Cell], list[AnyWorldObject], list[Agent]]:
        """Get all data needed to render a viewport region.

        Returns cells, objects, and agents in the given rectangle.
        This is more efficient than making separate calls.

        Args:
            rect: Rectangle to query

        Returns:
            Tuple of (cells, objects, agents)
        """
        cells = await self._world.get_cells_in_rect(rect)
        objects = await self._world.get_objects_in_rect(rect)
        agents = await self._agents.get_agents_in_rect(rect)
        return cells, objects, agents
