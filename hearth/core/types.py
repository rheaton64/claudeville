"""Foundational types for Hearth.

This module defines the core types used throughout the system:
- Position: Grid coordinates (x, y)
- Direction: Cardinal directions with offsets
- Rect: Rectangular regions for queries
- Type aliases for domain identifiers
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, NewType, NamedTuple

# Type aliases for domain identifiers
AgentName = NewType("AgentName", str)
ObjectId = NewType("ObjectId", str)
LandmarkName = NewType("LandmarkName", str)
ConversationId = NewType("ConversationId", str)


class Direction(Enum):
    """Cardinal directions for movement and wall placement."""

    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"

    @property
    def offset(self) -> tuple[int, int]:
        """Get the (dx, dy) offset for this direction.

        Coordinate system: x increases east, y increases north.
        """
        return _DIRECTION_OFFSETS[self]

    @property
    def opposite(self) -> Direction:
        """Get the opposite direction."""
        return _DIRECTION_OPPOSITES[self]


# Lookup tables for Direction properties
_DIRECTION_OFFSETS: dict[Direction, tuple[int, int]] = {
    Direction.NORTH: (0, 1),
    Direction.SOUTH: (0, -1),
    Direction.EAST: (1, 0),
    Direction.WEST: (-1, 0),
}

_DIRECTION_OPPOSITES: dict[Direction, Direction] = {
    Direction.NORTH: Direction.SOUTH,
    Direction.SOUTH: Direction.NORTH,
    Direction.EAST: Direction.WEST,
    Direction.WEST: Direction.EAST,
}


class Position(NamedTuple):
    """A position in the grid world.

    Coordinates use standard Cartesian orientation:
    - x increases to the east (right)
    - y increases to the north (up)
    - (0, 0) is the southwest corner of the world
    """

    x: int
    y: int

    def __add__(self, other: object) -> Position:
        """Add a direction offset or tuple to this position."""
        if isinstance(other, Direction):
            dx, dy = other.offset
            return Position(self.x + dx, self.y + dy)
        if isinstance(other, tuple) and len(other) == 2:
            return Position(self.x + other[0], self.y + other[1])
        return NotImplemented

    def __sub__(self, other: object) -> Position:
        """Subtract a direction offset or tuple from this position."""
        if isinstance(other, Direction):
            dx, dy = other.offset
            return Position(self.x - dx, self.y - dy)
        if isinstance(other, tuple) and len(other) == 2:
            return Position(self.x - other[0], self.y - other[1])
        return NotImplemented

    def distance_to(self, other: Position) -> int:
        """Calculate Manhattan distance to another position."""
        return abs(self.x - other.x) + abs(self.y - other.y)

    def direction_to(self, other: Position) -> Direction | None:
        """Get the primary cardinal direction toward another position.

        Returns the direction of greatest difference, or None if positions are equal.
        Ties favor the x-axis (east/west).
        """
        dx = other.x - self.x
        dy = other.y - self.y

        if dx == 0 and dy == 0:
            return None

        # Favor x-axis on ties
        if abs(dx) >= abs(dy):
            return Direction.EAST if dx > 0 else Direction.WEST
        else:
            return Direction.NORTH if dy > 0 else Direction.SOUTH

    def neighbors(self) -> dict[Direction, Position]:
        """Get all adjacent positions keyed by direction."""
        return {d: self + d for d in Direction}

    def in_bounds(self, width: int, height: int) -> bool:
        """Check if position is within grid bounds (0 to width-1, 0 to height-1)."""
        return 0 <= self.x < width and 0 <= self.y < height


class Rect(NamedTuple):
    """A rectangular region for vision and spatial queries.

    Coordinates are inclusive on all sides.
    """

    min_x: int
    min_y: int
    max_x: int
    max_y: int

    def contains(self, pos: Position) -> bool:
        """Check if a position is within this rectangle."""
        return self.min_x <= pos.x <= self.max_x and self.min_y <= pos.y <= self.max_y

    def expand(self, radius: int) -> Rect:
        """Create a new rectangle expanded by radius in all directions."""
        return Rect(
            self.min_x - radius,
            self.min_y - radius,
            self.max_x + radius,
            self.max_y + radius,
        )

    def clamp(self, width: int, height: int) -> Rect:
        """Clamp rectangle to grid bounds."""
        return Rect(
            max(0, self.min_x),
            max(0, self.min_y),
            min(width - 1, self.max_x),
            min(height - 1, self.max_y),
        )

    @classmethod
    def around(cls, center: Position, radius: int) -> Rect:
        """Create a rectangle centered on a position with given radius."""
        return cls(
            center.x - radius,
            center.y - radius,
            center.x + radius,
            center.y + radius,
        )

    def positions(self) -> list[Position]:
        """Get all positions within this rectangle."""
        return [
            Position(x, y)
            for x in range(self.min_x, self.max_x + 1)
            for y in range(self.min_y, self.max_y + 1)
        ]

    @property
    def width(self) -> int:
        """Width of the rectangle."""
        return self.max_x - self.min_x + 1

    @property
    def height(self) -> int:
        """Height of the rectangle."""
        return self.max_y - self.min_y + 1
