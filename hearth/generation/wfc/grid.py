"""
Grid representation for Wave Function Collapse.

The Grid is the "wave function" - a 2D array of cells where each cell
is in superposition (multiple possibilities) until it collapses to a
single definite tile.

This is where we track the state of the generation process.
"""

from dataclasses import dataclass, field
from typing import Iterator
import random

from .tile import Direction


@dataclass
class Cell:
    """
    A single cell in the WFC grid.

    Before collapse: holds a set of possible tile IDs
    After collapse: holds exactly one tile ID

    The "entropy" of a cell is how uncertain we are about it.
    Lower entropy = fewer possibilities = more constrained.
    """
    x: int
    y: int
    possibilities: set[str] = field(default_factory=set)

    def __hash__(self):
        """Hash by position - cells are unique by their grid location."""
        return hash((self.x, self.y))

    def __eq__(self, other):
        """Two cells are equal if they have the same position."""
        if not isinstance(other, Cell):
            return False
        return self.x == other.x and self.y == other.y

    @property
    def collapsed(self) -> bool:
        """A cell is collapsed when it has exactly one possibility."""
        return len(self.possibilities) == 1

    @property
    def tile_id(self) -> str | None:
        """The chosen tile ID, or None if not yet collapsed."""
        if self.collapsed:
            return next(iter(self.possibilities))
        return None

    @property
    def entropy(self) -> int:
        """
        How uncertain this cell is.

        We use simple count of possibilities.
        Lower = more constrained = should be collapsed first.
        """
        return len(self.possibilities)

    def collapse_to(self, tile_id: str):
        """Force this cell to a specific tile."""
        self.possibilities = {tile_id}

    def remove_possibility(self, tile_id: str) -> bool:
        """
        Remove a possibility from this cell.

        Returns True if the possibility was actually removed (cell changed).
        Returns False if the tile wasn't a possibility anyway.
        """
        if tile_id in self.possibilities:
            self.possibilities.discard(tile_id)
            return True
        return False

    def constrain_to(self, allowed: set[str]) -> bool:
        """
        Constrain this cell to only the given possibilities.

        Returns True if the cell changed (lost possibilities).
        """
        old_count = len(self.possibilities)
        self.possibilities &= allowed
        return len(self.possibilities) < old_count


class Grid:
    """
    The 2D grid of cells representing the wave function.

    Initially all cells can be any tile (maximum superposition).
    As the algorithm runs, cells collapse and constrain their neighbors
    until every cell has exactly one tile.
    """

    def __init__(self, width: int, height: int, tile_ids: set[str]):
        """
        Create a grid with all cells in maximum superposition.

        Args:
            width: Number of cells horizontally
            height: Number of cells vertically
            tile_ids: Set of all possible tile IDs (initial superposition)
        """
        self.width = width
        self.height = height
        self.tile_ids = tile_ids

        # Create 2D array of cells, each starting with all possibilities
        self.cells: list[list[Cell]] = [
            [
                Cell(x=x, y=y, possibilities=set(tile_ids))
                for x in range(width)
            ]
            for y in range(height)
        ]

    def get_cell(self, x: int, y: int) -> Cell | None:
        """Get cell at position, or None if out of bounds."""
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.cells[y][x]
        return None

    def neighbors(self, cell: Cell) -> Iterator[tuple[Cell, Direction]]:
        """
        Yield all valid neighbors of a cell with their directions.

        Direction is FROM the input cell TO the neighbor.
        e.g., (neighbor_cell, Direction.NORTH) means neighbor is north of cell.
        """
        for direction in Direction:
            nx = cell.x + direction.dx
            ny = cell.y + direction.dy
            neighbor = self.get_cell(nx, ny)
            if neighbor is not None:
                yield neighbor, direction

    def min_entropy_cell(self) -> Cell | None:
        """
        Find the uncollapsed cell with minimum entropy (fewest possibilities).

        Returns None if all cells are collapsed.

        When there are ties, we pick randomly to add variety.
        This is important - always picking top-left would create biased patterns.
        """
        min_entropy = float("inf")
        candidates: list[Cell] = []

        for row in self.cells:
            for cell in row:
                # Skip already collapsed cells
                if cell.collapsed:
                    continue

                if cell.entropy < min_entropy:
                    min_entropy = cell.entropy
                    candidates = [cell]
                elif cell.entropy == min_entropy:
                    candidates.append(cell)

        if not candidates:
            return None  # All collapsed

        # Random selection among ties
        return random.choice(candidates)

    def is_complete(self) -> bool:
        """Check if all cells have collapsed."""
        return all(cell.collapsed for row in self.cells for cell in row)

    def reset(self):
        """Reset all cells to maximum superposition."""
        for row in self.cells:
            for cell in row:
                cell.possibilities = set(self.tile_ids)

    def all_cells(self) -> Iterator[Cell]:
        """Iterate over all cells in the grid."""
        for row in self.cells:
            yield from row
