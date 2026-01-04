"""World models for Hearth: Cell, Grid, and WorldState.

The grid uses sparse storage - only non-default cells are stored.
Walls are properties of cell edges, not separate entities.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from .types import Position, Direction, Rect, ObjectId
from .terrain import Terrain, Weather


@dataclass(frozen=True)
class WorldState:
    """Snapshot of world-level state.

    Contains global world properties that apply across the entire grid.
    """

    current_tick: int
    weather: Weather
    width: int
    height: int


class Cell(BaseModel):
    """A single cell in the grid.

    Walls are stored as a frozenset of directions indicating which edges have walls.
    Doors are openings in walls that allow passage.
    """

    model_config = ConfigDict(frozen=True)

    position: Position
    terrain: Terrain = Terrain.GRASS

    # Walls on cell edges (frozenset for hashability)
    walls: frozenset[Direction] = Field(default_factory=frozenset)
    doors: frozenset[Direction] = Field(default_factory=frozenset)

    # Optional associations
    place_name: str | None = None  # Named location
    structure_id: ObjectId | None = None  # Part of a structure

    def has_wall(self, direction: Direction) -> bool:
        """Check if there's a wall on the given edge."""
        return direction in self.walls

    def has_door(self, direction: Direction) -> bool:
        """Check if there's a door on the given edge."""
        return direction in self.doors

    def can_exit(self, direction: Direction) -> bool:
        """Check if an agent can exit in the given direction.

        Can exit if there's no wall, or if there's a door in the wall.
        """
        if direction not in self.walls:
            return True
        return direction in self.doors

    def with_wall(self, direction: Direction) -> Cell:
        """Return a new cell with a wall added on the given edge."""
        return self.model_copy(update={"walls": self.walls | {direction}})

    def without_wall(self, direction: Direction) -> Cell:
        """Return a new cell with the wall removed from the given edge."""
        new_walls = self.walls - {direction}
        new_doors = self.doors - {direction}  # Remove door if wall is removed
        return self.model_copy(update={"walls": new_walls, "doors": new_doors})

    def with_door(self, direction: Direction) -> Cell:
        """Return a new cell with a door added on the given edge.

        Adds a wall first if one doesn't exist.
        """
        new_walls = self.walls | {direction}
        new_doors = self.doors | {direction}
        return self.model_copy(update={"walls": new_walls, "doors": new_doors})

    def without_door(self, direction: Direction) -> Cell:
        """Return a new cell with the door removed (wall remains)."""
        return self.model_copy(update={"doors": self.doors - {direction}})

    def with_terrain(self, terrain: Terrain) -> Cell:
        """Return a new cell with different terrain."""
        return self.model_copy(update={"terrain": terrain})

    def with_place_name(self, name: str | None) -> Cell:
        """Return a new cell with a place name set or cleared."""
        return self.model_copy(update={"place_name": name})

    def with_structure_id(self, structure_id: ObjectId | None) -> Cell:
        """Return a new cell associated with a structure."""
        return self.model_copy(update={"structure_id": structure_id})


class Grid(BaseModel):
    """Sparse grid representation.

    Only non-default cells are stored. When querying a position that
    isn't in the cells dict, a default grass cell is returned.
    """

    model_config = ConfigDict(frozen=True)

    width: int = 500
    height: int = 500
    cells: dict[Position, Cell] = Field(default_factory=dict)

    def get_cell(self, pos: Position) -> Cell:
        """Get the cell at a position.

        Returns a default grass cell if the position isn't explicitly stored.
        """
        if pos in self.cells:
            return self.cells[pos]
        # Return default cell for this position
        return Cell(position=pos)

    def set_cell(self, cell: Cell) -> Grid:
        """Return a new grid with the cell set.

        If the cell is equivalent to default, it's removed from storage.
        """
        default = Cell(position=cell.position)
        new_cells = dict(self.cells)

        if cell == default:
            # Remove from storage if it's the default
            new_cells.pop(cell.position, None)
        else:
            new_cells[cell.position] = cell

        return self.model_copy(update={"cells": new_cells})

    def update_cell(self, pos: Position, **updates: object) -> Grid:
        """Return a new grid with the cell at pos updated.

        Convenience method that gets the cell, updates it, and sets it back.
        """
        cell = self.get_cell(pos)
        new_cell = cell.model_copy(update=updates)
        return self.set_cell(new_cell)

    def cells_in_rect(self, rect: Rect) -> list[Cell]:
        """Get all cells within a rectangle.

        Returns cells for all positions in the rect, creating default cells
        for positions not explicitly stored.
        """
        clamped = rect.clamp(self.width, self.height)
        return [self.get_cell(pos) for pos in clamped.positions()]

    def stored_cells_in_rect(self, rect: Rect) -> list[Cell]:
        """Get only explicitly stored cells within a rectangle.

        More efficient when you only need non-default cells.
        """
        clamped = rect.clamp(self.width, self.height)
        return [
            self.cells[pos]
            for pos in clamped.positions()
            if pos in self.cells
        ]

    def is_valid_position(self, pos: Position) -> bool:
        """Check if a position is within grid bounds."""
        return pos.in_bounds(self.width, self.height)

    def is_passable(self, pos: Position) -> bool:
        """Check if a position can be walked through.

        Position must be valid and have passable terrain.
        """
        if not self.is_valid_position(pos):
            return False
        from .terrain import is_passable as terrain_is_passable
        cell = self.get_cell(pos)
        return terrain_is_passable(cell.terrain)

    def can_move(self, from_pos: Position, direction: Direction) -> bool:
        """Check if movement is possible from one cell to an adjacent cell.

        Considers:
        - Grid bounds
        - Terrain passability
        - Walls on cell edges (both source and destination cells)
        """
        to_pos = from_pos + direction

        # Check bounds
        if not self.is_valid_position(to_pos):
            return False

        # Check terrain
        if not self.is_passable(to_pos):
            return False

        # Check walls - need to check both sides of the edge
        from_cell = self.get_cell(from_pos)
        to_cell = self.get_cell(to_pos)

        # Can't exit if there's a wall (without door) on our side
        if not from_cell.can_exit(direction):
            return False

        # Can't enter if there's a wall (without door) on their side
        if not to_cell.can_exit(direction.opposite):
            return False

        return True

    def with_dimensions(self, width: int, height: int) -> Grid:
        """Return a new grid with different dimensions.

        Cells outside the new bounds are removed.
        """
        new_cells = {
            pos: cell
            for pos, cell in self.cells.items()
            if pos.in_bounds(width, height)
        }
        return self.model_copy(update={"width": width, "height": height, "cells": new_cells})
