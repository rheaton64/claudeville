"""World service for Hearth.

Provides grid state management as a thin service layer over storage repositories.
No in-memory caching - always delegates to storage.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.types import Position, Direction, Rect, ObjectId, AgentName
from core.terrain import Terrain, TERRAIN_DEFAULTS, TerrainProperties
from core.world import Cell
from core.structures import Structure
from core.objects import AnyWorldObject

if TYPE_CHECKING:
    from storage import Storage


# -----------------------------------------------------------------------------
# Exceptions
# -----------------------------------------------------------------------------


class WorldServiceError(Exception):
    """Base exception for WorldService errors."""

    pass


class InvalidPositionError(WorldServiceError):
    """Position is outside world bounds."""

    def __init__(self, message: str, position: Position | None = None):
        super().__init__(message)
        self.position = position


class WallPlacementError(WorldServiceError):
    """Cannot place or remove wall at specified location."""

    pass


class ObjectPlacementError(WorldServiceError):
    """Cannot place object at location."""

    pass


class ObjectNotFoundError(WorldServiceError):
    """Object with given ID not found."""

    pass


# -----------------------------------------------------------------------------
# WorldService
# -----------------------------------------------------------------------------


class WorldService:
    """Grid state management for Hearth.

    A thin service layer over WorldRepository and ObjectRepository.
    No in-memory caching - always delegates to storage.
    """

    def __init__(self, storage: "Storage"):
        """Initialize WorldService.

        Args:
            storage: Connected Storage instance
        """
        self._storage = storage

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def _world_repo(self):
        """Get world repository."""
        return self._storage.world

    @property
    def _object_repo(self):
        """Get object repository."""
        return self._storage.objects

    # -------------------------------------------------------------------------
    # Spatial Queries
    # -------------------------------------------------------------------------

    async def get_cell(self, pos: Position) -> Cell:
        """Get cell at position. Returns default if not stored."""
        return await self._world_repo.get_cell(pos)

    async def get_cells_in_rect(self, rect: Rect) -> list[Cell]:
        """Get all cells in a rectangle (includes defaults)."""
        return await self._world_repo.get_cells_in_rect(rect)

    async def get_objects_at(self, pos: Position) -> list[AnyWorldObject]:
        """Get all world objects at a position."""
        return await self._object_repo.get_objects_at(pos)

    async def get_objects_in_rect(self, rect: Rect) -> list[AnyWorldObject]:
        """Get all world objects in a rectangle."""
        return await self._object_repo.get_objects_in_rect(rect)

    async def get_world_dimensions(self) -> tuple[int, int]:
        """Get world (width, height)."""
        state = await self._world_repo.get_world_state()
        return state.width, state.height

    async def get_world_state(self):
        """Get full world state (tick, weather, dimensions)."""
        return await self._world_repo.get_world_state()

    # -------------------------------------------------------------------------
    # Terrain Properties (pure functions using TERRAIN_DEFAULTS)
    # -------------------------------------------------------------------------

    def get_terrain_properties(self, terrain: Terrain) -> TerrainProperties:
        """Get all properties for a terrain type."""
        return TERRAIN_DEFAULTS.get(terrain, {})

    def is_terrain_passable(self, terrain: Terrain) -> bool:
        """Check if terrain can be walked through."""
        return TERRAIN_DEFAULTS.get(terrain, {}).get("passable", True)

    def get_terrain_symbol(self, terrain: Terrain) -> str:
        """Get display symbol for terrain."""
        return TERRAIN_DEFAULTS.get(terrain, {}).get("symbol", "?")

    def get_gather_resource(self, terrain: Terrain) -> str | None:
        """Get resource that can be gathered from terrain, if any."""
        return TERRAIN_DEFAULTS.get(terrain, {}).get("gather_resource")

    # -------------------------------------------------------------------------
    # Object Management
    # -------------------------------------------------------------------------

    async def place_object(self, obj: AnyWorldObject) -> None:
        """Place an object in the world."""
        # Validate position is in bounds
        width, height = await self.get_world_dimensions()
        if not obj.position.in_bounds(width, height):
            raise InvalidPositionError(
                f"Position {obj.position} is out of bounds", obj.position
            )
        await self._object_repo.save_object(obj)

    async def remove_object(self, object_id: ObjectId) -> None:
        """Remove an object from the world."""
        # Check object exists
        obj = await self._object_repo.get_object(object_id)
        if obj is None:
            raise ObjectNotFoundError(f"Object {object_id} not found")
        await self._object_repo.delete_object(object_id)

    async def move_object(self, object_id: ObjectId, new_pos: Position) -> None:
        """Move an object to a new position.

        Args:
            object_id: ID of object to move
            new_pos: New position

        Raises:
            ObjectNotFoundError: Object doesn't exist
            InvalidPositionError: New position is out of bounds
        """
        obj = await self._object_repo.get_object(object_id)
        if obj is None:
            raise ObjectNotFoundError(f"Object {object_id} not found")

        # Validate new position
        width, height = await self.get_world_dimensions()
        if not new_pos.in_bounds(width, height):
            raise InvalidPositionError(
                f"Position {new_pos} is out of bounds", new_pos
            )

        # Create updated object with new position
        updated = obj.model_copy(update={"position": new_pos})
        await self._object_repo.save_object(updated)

    # -------------------------------------------------------------------------
    # Wall Placement (auto-symmetric)
    # -------------------------------------------------------------------------

    async def place_wall(self, pos: Position, direction: Direction) -> None:
        """Place a wall on a cell edge. Automatically updates both adjacent cells.

        Args:
            pos: Position of the cell
            direction: Which edge to place wall on

        Raises:
            InvalidPositionError: If position is out of bounds
        """
        state = await self._world_repo.get_world_state()

        if not pos.in_bounds(state.width, state.height):
            raise InvalidPositionError(f"Position {pos} is out of bounds", pos)

        adjacent = pos + direction

        if not adjacent.in_bounds(state.width, state.height):
            # At world edge - only update this cell
            cell = await self._world_repo.get_cell(pos)
            await self._world_repo.set_cell(cell.with_wall(direction))
            return

        # Update both cells in transaction
        async with self._storage.db.transaction():
            cell = await self._world_repo.get_cell(pos)
            adjacent_cell = await self._world_repo.get_cell(adjacent)

            await self._world_repo.set_cell(cell.with_wall(direction))
            await self._world_repo.set_cell(
                adjacent_cell.with_wall(direction.opposite)
            )

    async def remove_wall(self, pos: Position, direction: Direction) -> None:
        """Remove a wall from a cell edge. Automatically updates both adjacent cells.

        Args:
            pos: Position of the cell
            direction: Which edge to remove wall from

        Raises:
            InvalidPositionError: If position is out of bounds
        """
        state = await self._world_repo.get_world_state()

        if not pos.in_bounds(state.width, state.height):
            raise InvalidPositionError(f"Position {pos} is out of bounds", pos)

        adjacent = pos + direction

        if not adjacent.in_bounds(state.width, state.height):
            # At world edge - only update this cell
            cell = await self._world_repo.get_cell(pos)
            await self._world_repo.set_cell(cell.without_wall(direction))
            return

        # Update both cells in transaction
        async with self._storage.db.transaction():
            cell = await self._world_repo.get_cell(pos)
            adjacent_cell = await self._world_repo.get_cell(adjacent)

            await self._world_repo.set_cell(cell.without_wall(direction))
            await self._world_repo.set_cell(
                adjacent_cell.without_wall(direction.opposite)
            )

    async def place_door(self, pos: Position, direction: Direction) -> None:
        """Place a door in a wall. Automatically updates both adjacent cells.

        Adds a wall first if one doesn't exist.

        Args:
            pos: Position of the cell
            direction: Which edge to place door on

        Raises:
            InvalidPositionError: If position is out of bounds
        """
        state = await self._world_repo.get_world_state()

        if not pos.in_bounds(state.width, state.height):
            raise InvalidPositionError(f"Position {pos} is out of bounds", pos)

        adjacent = pos + direction

        if not adjacent.in_bounds(state.width, state.height):
            # At world edge - only update this cell
            cell = await self._world_repo.get_cell(pos)
            await self._world_repo.set_cell(cell.with_door(direction))
            return

        # Update both cells in transaction
        async with self._storage.db.transaction():
            cell = await self._world_repo.get_cell(pos)
            adjacent_cell = await self._world_repo.get_cell(adjacent)

            await self._world_repo.set_cell(cell.with_door(direction))
            await self._world_repo.set_cell(
                adjacent_cell.with_door(direction.opposite)
            )

    async def remove_door(self, pos: Position, direction: Direction) -> None:
        """Remove a door from a wall (wall remains). Updates both adjacent cells.

        Args:
            pos: Position of the cell
            direction: Which edge to remove door from

        Raises:
            InvalidPositionError: If position is out of bounds
        """
        state = await self._world_repo.get_world_state()

        if not pos.in_bounds(state.width, state.height):
            raise InvalidPositionError(f"Position {pos} is out of bounds", pos)

        adjacent = pos + direction

        if not adjacent.in_bounds(state.width, state.height):
            # At world edge - only update this cell
            cell = await self._world_repo.get_cell(pos)
            await self._world_repo.set_cell(cell.without_door(direction))
            return

        # Update both cells in transaction
        async with self._storage.db.transaction():
            cell = await self._world_repo.get_cell(pos)
            adjacent_cell = await self._world_repo.get_cell(adjacent)

            await self._world_repo.set_cell(cell.without_door(direction))
            await self._world_repo.set_cell(
                adjacent_cell.without_door(direction.opposite)
            )

    # -------------------------------------------------------------------------
    # Named Places
    # -------------------------------------------------------------------------

    async def name_place(self, name: str, pos: Position) -> None:
        """Name a location. Updates named_places table and cell.place_name."""
        width, height = await self.get_world_dimensions()
        if not pos.in_bounds(width, height):
            raise InvalidPositionError(f"Position {pos} is out of bounds", pos)
        await self._world_repo.set_named_place(name, pos)

    async def get_place_position(self, name: str) -> Position | None:
        """Look up position by place name."""
        return await self._world_repo.get_named_place(name)

    async def get_all_named_places(self) -> dict[str, Position]:
        """Get all named places."""
        return await self._world_repo.get_all_named_places()

    async def remove_place_name(self, name: str) -> None:
        """Remove a named place."""
        await self._world_repo.remove_named_place(name)

    # -------------------------------------------------------------------------
    # Movement Utilities
    # -------------------------------------------------------------------------

    async def is_position_valid(self, pos: Position) -> bool:
        """Check if position is within world bounds."""
        width, height = await self.get_world_dimensions()
        return pos.in_bounds(width, height)

    async def is_position_passable(self, pos: Position) -> bool:
        """Check if position can be walked through (terrain + objects).

        Considers:
        - Position must be in bounds
        - Terrain must be passable
        - No impassable objects at position
        """
        width, height = await self.get_world_dimensions()
        if not pos.in_bounds(width, height):
            return False

        cell = await self.get_cell(pos)
        if not self.is_terrain_passable(cell.terrain):
            return False

        # Check for impassable objects
        objects = await self.get_objects_at(pos)
        for obj in objects:
            if not obj.passable:
                return False

        return True

    async def can_move(self, from_pos: Position, direction: Direction) -> bool:
        """Check if movement is possible from one cell to an adjacent cell.

        Considers:
        - Grid bounds
        - Terrain passability
        - Walls on cell edges (both source and destination cells)
        - Impassable objects
        """
        to_pos = from_pos + direction

        # Check bounds
        if not await self.is_position_valid(to_pos):
            return False

        # Check destination is passable (terrain + objects)
        if not await self.is_position_passable(to_pos):
            return False

        # Check walls - need to check both sides of the edge
        from_cell = await self.get_cell(from_pos)
        to_cell = await self.get_cell(to_pos)

        # Can't exit if there's a wall (without door) on our side
        if not from_cell.can_exit(direction):
            return False

        # Can't enter if there's a wall (without door) on their side
        if not to_cell.can_exit(direction.opposite):
            return False

        return True

    # -------------------------------------------------------------------------
    # Structure Detection (flood-fill)
    # -------------------------------------------------------------------------

    async def _flood_fill_enclosed(
        self, start: Position, max_cells: int = 1000
    ) -> frozenset[Position] | None:
        """Find enclosed area containing start position via flood-fill.

        Algorithm:
        1. BFS from start position
        2. For each cell, check all 4 directions
        3. If can_exit (no wall or has door), explore neighbor
        4. If reach world boundary without wall -> NOT enclosed (return None)
        5. If search exhausts without hitting boundary -> IS enclosed
        6. Return visited positions as interior cells

        Args:
            start: Starting position to flood-fill from
            max_cells: Maximum cells to explore before giving up

        Returns:
            frozenset of interior positions if enclosed, None if not enclosed
        """
        state = await self._world_repo.get_world_state()
        width, height = state.width, state.height

        # Check start is valid
        if not start.in_bounds(width, height):
            return None

        visited: set[Position] = set()
        to_visit: list[Position] = [start]

        while to_visit:
            if len(visited) > max_cells:
                # Too large to be a structure, or not enclosed
                return None

            current = to_visit.pop()
            if current in visited:
                continue
            visited.add(current)

            # Check all four directions
            for direction in Direction:
                current_cell = await self._world_repo.get_cell(current)

                if current_cell.can_exit(direction):
                    # No wall blocking us (or there's a door)
                    neighbor = current + direction

                    if not neighbor.in_bounds(width, height):
                        # We reached world boundary without wall - NOT enclosed
                        return None

                    neighbor_cell = await self._world_repo.get_cell(neighbor)
                    if neighbor_cell.can_exit(direction.opposite):
                        # Can enter neighbor too - add to search
                        if neighbor not in visited:
                            to_visit.append(neighbor)

        # Exhausted search without hitting unblocked boundary = enclosed!
        return frozenset(visited)

    async def detect_structure_at(
        self,
        pos: Position,
        created_by: AgentName | None = None,
        max_cells: int = 1000,
    ) -> Structure | None:
        """Detect if pos is inside an enclosed structure.

        Uses flood-fill to find enclosed area. Returns None if not enclosed.

        Args:
            pos: Position to check
            created_by: Optional creator to assign to detected structure
            max_cells: Maximum cells to explore

        Returns:
            Structure if enclosed, None otherwise
        """
        interior = await self._flood_fill_enclosed(pos, max_cells)
        if interior is None:
            return None

        return Structure.create(
            interior_cells=interior,
            created_by=created_by,
        )

    async def detect_structures_in_rect(
        self, rect: Rect, max_cells_per_structure: int = 1000
    ) -> list[Structure]:
        """Detect all enclosed structures within a rectangle.

        Scans the rectangle and flood-fills from each unvisited position.
        Returns all detected structures.

        Args:
            rect: Rectangle to scan
            max_cells_per_structure: Max cells per structure

        Returns:
            List of detected structures
        """
        state = await self._world_repo.get_world_state()
        clamped = rect.clamp(state.width, state.height)

        structures: list[Structure] = []
        visited: set[Position] = set()

        for pos in clamped.positions():
            if pos in visited:
                continue

            interior = await self._flood_fill_enclosed(pos, max_cells_per_structure)
            if interior is not None:
                # Found an enclosed area
                structures.append(Structure.create(interior_cells=interior))
                visited.update(interior)
            else:
                # Not enclosed - mark as visited so we don't re-check
                visited.add(pos)

        return structures

    async def save_structure(self, structure: Structure) -> None:
        """Save a detected structure and update interior cells.

        Sets structure_id on all interior cells.
        """
        await self._world_repo.save_structure(structure)

    async def delete_structure(self, structure_id: ObjectId) -> None:
        """Delete a structure and clear cell references."""
        await self._world_repo.delete_structure(structure_id)

    async def get_structure(self, structure_id: ObjectId) -> Structure | None:
        """Get structure by ID."""
        return await self._world_repo.get_structure(structure_id)

    async def get_structure_at(self, pos: Position) -> Structure | None:
        """Get structure that contains this position, if any.

        Checks if the cell has a structure_id set and retrieves that structure.
        """
        cell = await self.get_cell(pos)
        if cell.structure_id is None:
            return None
        return await self._world_repo.get_structure(cell.structure_id)
