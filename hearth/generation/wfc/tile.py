"""
Tile definition for Wave Function Collapse.

A Tile is a discrete unit that can occupy a cell in the grid.
Each tile knows what other tiles can be adjacent to it in each direction.
This is the core data that drives the constraint propagation.
"""

from dataclasses import dataclass, field
from enum import Enum


class Direction(Enum):
    """
    Cardinal directions for adjacency rules.

    The opposite() method is crucial for propagation:
    if tile A allows tile B to its NORTH, then tile B must allow A to its SOUTH.
    """
    NORTH = (0, -1)
    SOUTH = (0, 1)
    EAST = (1, 0)
    WEST = (-1, 0)

    def opposite(self) -> "Direction":
        """Return the opposite direction."""
        opposites = {
            Direction.NORTH: Direction.SOUTH,
            Direction.SOUTH: Direction.NORTH,
            Direction.EAST: Direction.WEST,
            Direction.WEST: Direction.EAST,
        }
        return opposites[self]

    @property
    def dx(self) -> int:
        return self.value[0]

    @property
    def dy(self) -> int:
        return self.value[1]


@dataclass
class Tile:
    """
    A tile type that can appear in the generated output.

    Attributes:
        id: Unique identifier for this tile type (e.g., "water", "grass")
        color: RGB tuple for rendering (kept for compatibility, not used in Hearth)
        weight: Probability weight - higher means more common in output.
                When collapsing a cell, tiles are chosen proportionally to their weights.
        self_affinity: How much this tile "likes" being next to itself.
                      During collapse, weight is multiplied by self_affinity^(number of same-type neighbors).
                      1.0 = neutral (default), 2.0 = strongly clusters, 0.5 = avoids clustering.
        allowed_neighbors: For each direction, the set of tile IDs that can be adjacent.
                          This is the heart of WFC - local constraints that create global structure.
    """
    id: str
    color: tuple[int, int, int] = (128, 128, 128)  # Default gray
    weight: float = 1.0
    self_affinity: float = 1.0
    allowed_neighbors: dict[Direction, set[str]] = field(default_factory=dict)

    def __post_init__(self):
        # Initialize empty neighbor sets for all directions if not provided
        for direction in Direction:
            if direction not in self.allowed_neighbors:
                self.allowed_neighbors[direction] = set()

    def allow_neighbor(self, direction: Direction, neighbor_id: str):
        """Allow a specific tile to be adjacent in the given direction."""
        self.allowed_neighbors[direction].add(neighbor_id)

    def get_allowed_neighbors(self, direction: Direction) -> set[str]:
        """Get all tile IDs allowed in the given direction."""
        return self.allowed_neighbors.get(direction, set())


def make_bidirectional_rule(tiles: dict[str, Tile], tile_a_id: str, tile_b_id: str):
    """
    Create a bidirectional adjacency rule: A and B can be neighbors in all directions.

    This is a convenience function for defining symmetric rules.
    If A can have B to its north, then B can have A to its south, etc.
    """
    tile_a = tiles[tile_a_id]
    tile_b = tiles[tile_b_id]

    for direction in Direction:
        tile_a.allow_neighbor(direction, tile_b_id)
        tile_b.allow_neighbor(direction.opposite(), tile_a_id)
