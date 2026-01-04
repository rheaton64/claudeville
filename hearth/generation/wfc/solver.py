"""
Wave Function Collapse solver.

This is the heart of WFC - the algorithm that observes (collapses) cells
and propagates constraints until the entire grid is determined.

The algorithm:
1. Find the cell with lowest entropy (most constrained)
2. Collapse it to one tile (weighted random choice)
3. Propagate: update neighbors based on adjacency rules
4. Repeat until complete or contradiction
"""

from collections import deque
from enum import Enum, auto
import heapq
import random
import time

from .grid import Grid, Cell
from .tile import Tile, Direction


class SolverState(Enum):
    """The current state of the WFC solver."""
    RUNNING = auto()      # Still solving, more steps needed
    COMPLETE = auto()     # All cells collapsed successfully
    CONTRADICTION = auto()  # Hit an impossible state (some cell has 0 possibilities)


class WFCSolver:
    """
    The WFC algorithm implementation.

    Usage:
        solver = WFCSolver(grid, tileset)
        while True:
            state = solver.step()
            if state != SolverState.RUNNING:
                break

    Or for bulk solving:
        solver.solve()  # Returns True on success, False on contradiction

    Supports batched collapsing for faster generation:
        solver = WFCSolver(grid, tileset, batch_size=10, min_batch_distance=6)

    Supports backtracking on contradiction:
        solver = WFCSolver(..., snapshot_interval=1000, max_backtracks=10)
    """

    def __init__(
        self,
        grid: Grid,
        tileset: dict[str, Tile],
        batch_size: int = 1,
        min_batch_distance: int = 6,
        max_water_ratio: float = 0.3,
        fill_bias: float = 0.5,
        snapshot_interval: int = 5000,
        max_backtracks: int = 20,
    ):
        """
        Initialize the solver.

        Args:
            grid: The Grid to solve (should be in initial superposition state)
            tileset: Dict mapping tile ID to Tile objects with adjacency rules
            batch_size: Max number of cells to collapse per step (1 = classic mode)
            min_batch_distance: Minimum Manhattan distance between simultaneously
                               collapsed cells (higher = safer, fewer parallel collapses)
            max_water_ratio: Max fraction of batch that can be water-dominant cells.
                            Prevents water from sweeping large viewports.
                            0.0 = no water, 1.0 = unlimited water.
            fill_bias: How much to prioritize cells with more collapsed neighbors.
                       Higher values favor "filling in" over "spreading out".
                       0 = pure entropy-based, 1+ = strongly prefer interior cells.
            snapshot_interval: Save a snapshot every N collapsed cells for backtracking.
            max_backtracks: Max number of backtracks before giving up.
        """
        self.grid = grid
        self.tileset = tileset
        self.batch_size = batch_size
        self.min_batch_distance = min_batch_distance
        self.max_water_ratio = max_water_ratio
        self.fill_bias = fill_bias
        self.snapshot_interval = snapshot_interval
        self.max_backtracks = max_backtracks
        self.step_count = 0

        # Track the last collapsed cells (for visualization/debugging)
        self.last_collapsed: list[Cell] = []

        # Track cells modified in last propagation (for visualization/debugging)
        self.last_propagated: set[Cell] = set()

        # Backtracking state
        self._snapshots: list[tuple[int, list[list[set[str]]]]] = []  # (collapsed_count, grid_state)
        self._collapsed_count = 0
        self._last_snapshot_at = 0
        self._backtrack_count = 0

    @property
    def collapsed_count(self) -> int:
        """Number of cells that have been collapsed."""
        return self._collapsed_count

    def _save_snapshot(self) -> None:
        """Save current grid state for backtracking."""
        state = [
            [set(cell.possibilities) for cell in row]
            for row in self.grid.cells
        ]
        self._snapshots.append((self._collapsed_count, state))
        self._last_snapshot_at = self._collapsed_count

    def _restore_snapshot(self) -> bool:
        """Restore to last snapshot. Returns False if no snapshots available."""
        if not self._snapshots:
            return False

        collapsed_count, state = self._snapshots.pop()
        for y, row in enumerate(state):
            for x, possibilities in enumerate(row):
                self.grid.cells[y][x].possibilities = set(possibilities)

        self._collapsed_count = collapsed_count
        self._last_snapshot_at = self._snapshots[-1][0] if self._snapshots else 0
        self._backtrack_count += 1
        return True

    def step(self) -> SolverState:
        """
        Perform one step of WFC: observe cells and propagate constraints.

        With batch_size=1 (default), collapses one cell per step.
        With batch_size>1, collapses multiple spatially-separated cells per step.

        Returns the current solver state after this step.
        """
        self.last_propagated.clear()
        self.last_collapsed.clear()

        # 1. Find cells to collapse (respecting batch_size and min_distance)
        cells_to_collapse = self._find_batch_cells()

        if not cells_to_collapse:
            return SolverState.COMPLETE

        if cells_to_collapse[0].entropy == 0:
            return self._handle_contradiction()

        if self._collapsed_count - self._last_snapshot_at >= self.snapshot_interval:
            self._save_snapshot()

        # 2. Collapse all selected cells
        for cell in cells_to_collapse:
            self._collapse(cell)
            self.last_collapsed.append(cell)
            self._collapsed_count += 1

        self.step_count += 1

        # 3. Propagate constraints
        success = self._propagate_batch(cells_to_collapse)

        if not success:
            return self._handle_contradiction()

        return SolverState.RUNNING

    def _handle_contradiction(self) -> SolverState:
        """Handle a contradiction by backtracking or giving up."""
        if self._backtrack_count >= self.max_backtracks:
            print(f"\n  [Max backtracks ({self.max_backtracks}) reached, giving up]")
            return SolverState.CONTRADICTION

        if self._restore_snapshot():
            print(f"\n  [Contradiction at {self._collapsed_count + self.snapshot_interval} cells, "
                  f"backtracking to {self._collapsed_count} (backtrack {self._backtrack_count}/{self.max_backtracks})]")
            return SolverState.RUNNING
        else:
            print(f"\n  [Contradiction with no snapshots to restore]")
            return SolverState.CONTRADICTION

    def _find_batch_cells(self) -> list[Cell]:
        """
        Find cells to collapse this step using heap-based selection.

        Uses heapq.nsmallest() instead of full sort for O(n + k log n) vs O(n log n).
        For 250k cells and k=batch_size*5, this is significantly faster.

        Priority is based on:
        - Entropy (lower = higher priority, more constrained)
        - Collapsed neighbor count (more neighbors = higher priority with fill_bias)

        Returns up to batch_size cells that are at least min_batch_distance apart.
        """
        # Get all uncollapsed cells - this is unavoidable O(n)
        uncollapsed = [c for c in self.grid.all_cells() if not c.collapsed]

        if not uncollapsed:
            return []

        # Fast path for early steps: when few cells are collapsed, all priorities
        # are nearly equal (same entropy, ~0 collapsed neighbors). Just pick randomly.
        collapsed_ratio = 1.0 - (len(uncollapsed) / (self.grid.width * self.grid.height))
        if collapsed_ratio < 0.01:  # Less than 1% collapsed
            random.shuffle(uncollapsed)
            candidates = uncollapsed[:self.batch_size * 10]
        else:
            def cell_priority(cell: Cell) -> float:
                collapsed_neighbors = self._count_collapsed_neighbors(cell)
                return cell.entropy - (collapsed_neighbors * self.fill_bias) + random.random() * 0.01

            candidate_count = min(len(uncollapsed), self.batch_size * 10)
            candidates = heapq.nsmallest(candidate_count, uncollapsed, key=cell_priority)

        # Check for contradiction (min entropy is 0)
        if candidates[0].entropy == 0:
            return [candidates[0]]

        if self.batch_size == 1:
            return [candidates[0]]

        # Greedily select spatially-separated cells from candidates
        # Use spatial hashing for O(1) average distance checks instead of O(n)
        selected: list[Cell] = []
        water_count = 0

        # Spatial hash: map bucket -> list of cells in that bucket
        bucket_size = self.min_batch_distance
        buckets: dict[tuple[int, int], list[Cell]] = {}

        def get_bucket(x: int, y: int) -> tuple[int, int]:
            return (x // bucket_size, y // bucket_size)

        def is_far_from_selected(cell: Cell) -> bool:
            bx, by = get_bucket(cell.x, cell.y)
            # Check 3x3 neighborhood of buckets
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    bucket_key = (bx + dx, by + dy)
                    if bucket_key in buckets:
                        for other in buckets[bucket_key]:
                            dist = abs(cell.x - other.x) + abs(cell.y - other.y)
                            if dist < self.min_batch_distance:
                                return False
            return True

        for cell in candidates:
            if len(selected) >= self.batch_size:
                break

            if not is_far_from_selected(cell):
                continue

            # Check water ratio constraint
            can_be_water = "water" in cell.possibilities

            if can_be_water:
                max_water_cells = max(1, int(self.batch_size * self.max_water_ratio))
                if water_count >= max_water_cells:
                    continue

                water_count += 1

            selected.append(cell)
            bucket_key = get_bucket(cell.x, cell.y)
            if bucket_key not in buckets:
                buckets[bucket_key] = []
            buckets[bucket_key].append(cell)

        # Skip expensive fallback - just use what we got
        # With 20k random candidates, we should get enough spatially-separated cells
        return selected

    def _count_collapsed_neighbors(self, cell: Cell) -> int:
        """Count how many of a cell's neighbors are already collapsed."""
        return sum(1 for neighbor, _ in self.grid.neighbors(cell) if neighbor.collapsed)

    def _is_far_from_all(self, cell: Cell, others: list[Cell]) -> bool:
        """Check if cell is at least min_batch_distance from all others."""
        for other in others:
            distance = abs(cell.x - other.x) + abs(cell.y - other.y)
            if distance < self.min_batch_distance:
                return False
        return True

    def _propagate_batch(self, start_cells: list[Cell]) -> bool:
        """
        Propagate constraints from multiple cells simultaneously.

        This merges the propagation wavefronts - all start cells go into
        the initial queue, and propagation proceeds normally. When wavefronts
        meet, they naturally merge.

        Returns True on success, False on contradiction.
        """
        if not start_cells:
            return True

        # Initialize queue with all start cells
        queue: deque[Cell] = deque(start_cells)
        in_queue: set[tuple[int, int]] = {(c.x, c.y) for c in start_cells}

        while queue:
            cell = queue.popleft()
            in_queue.discard((cell.x, cell.y))

            for neighbor, direction in self.grid.neighbors(cell):
                if neighbor.collapsed:
                    continue

                allowed = self._get_allowed_neighbors(cell, direction)
                changed = neighbor.constrain_to(allowed)

                if changed:
                    self.last_propagated.add(neighbor)

                    if neighbor.entropy == 0:
                        return False

                    if (neighbor.x, neighbor.y) not in in_queue:
                        queue.append(neighbor)
                        in_queue.add((neighbor.x, neighbor.y))

        return True

    def _collapse(self, cell: Cell):
        """
        Collapse a cell to a single tile using weighted random selection.

        Tiles with higher weights are more likely to be chosen.
        Self-affinity boosts weights when neighboring cells have the same tile,
        creating natural clustering behavior.
        """
        possibilities = list(cell.possibilities)

        # Get base weights
        weights = [self.tileset[tile_id].weight for tile_id in possibilities]

        # Apply self-affinity boost based on collapsed neighbors
        for i, tile_id in enumerate(possibilities):
            tile = self.tileset[tile_id]
            if tile.self_affinity != 1.0:
                # Count collapsed neighbors with the same tile type
                same_neighbor_count = sum(
                    1 for neighbor, _ in self.grid.neighbors(cell)
                    if neighbor.collapsed and neighbor.tile_id == tile_id
                )
                # Boost weight: base_weight * self_affinity^same_neighbor_count
                if same_neighbor_count > 0:
                    weights[i] *= tile.self_affinity ** same_neighbor_count

        # Weighted random choice
        chosen = random.choices(possibilities, weights=weights, k=1)[0]

        cell.collapse_to(chosen)

    def _get_allowed_neighbors(self, cell: Cell, direction: Direction) -> set[str]:
        """
        Get all tile IDs that are allowed adjacent to cell in the given direction.

        This unions the allowed neighbors of all tiles that cell could still be.
        """
        allowed: set[str] = set()

        for tile_id in cell.possibilities:
            tile = self.tileset[tile_id]
            allowed |= tile.get_allowed_neighbors(direction)

        return allowed

    def solve(self) -> bool:
        """
        Run the solver to completion.

        Returns True if solved successfully, False if contradiction occurred.
        """
        while True:
            state = self.step()
            if state == SolverState.COMPLETE:
                return True
            if state == SolverState.CONTRADICTION:
                return False

    def reset(self):
        """Reset the solver and grid for a new generation."""
        self.grid.reset()
        self.step_count = 0
        self.last_collapsed.clear()
        self.last_propagated.clear()
        self._snapshots.clear()
        self._collapsed_count = 0
        self._last_snapshot_at = 0
        self._backtrack_count = 0
