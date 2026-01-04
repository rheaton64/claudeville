"""
Terrain generation using Wave Function Collapse.

This module provides the main entry point for generating Hearth world terrain.
The WFC algorithm creates natural-looking terrain with biomes that flow into
each other based on adjacency rules.
"""

import random
from typing import Callable

from core.types import Position
from core.terrain import Terrain
from .tileset import create_hearth_tileset, TILE_TO_TERRAIN
from .wfc import Grid, WFCSolver, SolverState


def generate_terrain(
    width: int = 500,
    height: int = 500,
    seed: int | None = None,
    batch_size: int = 100,
    min_batch_distance: int = 4,
    max_water_ratio: float = 0.3,
    fill_bias: float = 0.5,
    progress_callback: Callable[[int, int], None] | None = None,
    max_retries: int = 10,
) -> dict[Position, Terrain]:
    """
    Generate terrain using Wave Function Collapse.

    Creates a natural-looking terrain map with biomes that flow into each other:
    water -> coast -> sand -> grass -> forest/hill -> stone

    Args:
        width: World width in cells
        height: World height in cells
        seed: Random seed for reproducibility (None = random)
        batch_size: Cells to collapse per step (higher = faster)
        min_batch_distance: Minimum Manhattan distance between simultaneous collapses
        max_water_ratio: Max fraction of batch that can be water (0.0-1.0)
        fill_bias: Bias toward filling interior cells (0 = spread, 1+ = fill)
        progress_callback: Optional callback(step, total_cells) for progress updates
        max_retries: Max attempts before giving up (WFC can hit contradictions)

    Returns:
        Dict mapping Position to Terrain for non-grass cells.
        (Grass is the default terrain, so only non-default cells are returned)

    Raises:
        RuntimeError: If terrain generation fails after max_retries attempts
    """
    if seed is not None:
        random.seed(seed)

    tileset = create_hearth_tileset()
    total_cells = width * height

    for attempt in range(max_retries):
        # Create fresh grid for each attempt
        grid = Grid(width, height, set(tileset.keys()))

        solver = WFCSolver(
            grid,
            tileset,
            batch_size=batch_size,
            min_batch_distance=min_batch_distance,
            max_water_ratio=max_water_ratio,
            fill_bias=fill_bias,
            snapshot_interval=10000,  # Save every 10k cells for backtracking
            max_backtracks=50,        # Allow many backtracks before full restart
        )

        # Run the solver
        contradiction = False
        while True:
            state = solver.step()

            if progress_callback is not None:
                # Use solver's internal count (O(1) instead of O(n))
                progress_callback(solver.collapsed_count, total_cells)

            if state == SolverState.COMPLETE:
                break
            if state == SolverState.CONTRADICTION:
                contradiction = True
                break

        if not contradiction:
            # Success! Convert to Hearth terrain
            result: dict[Position, Terrain] = {}
            for cell in grid.all_cells():
                terrain = TILE_TO_TERRAIN[cell.tile_id]
                if terrain != Terrain.GRASS:
                    result[Position(cell.x, cell.y)] = terrain
            return result

        # Contradiction after exhausting backtracks - full restart
        print(f"\n  [Full restart: attempt {attempt + 1}/{max_retries}]")
        # (random state advances naturally, giving us a new seed effectively)

    raise RuntimeError(
        f"Terrain generation failed after {max_retries} attempts. "
        "Try adjusting parameters or tileset rules."
    )


def generate_terrain_grid(
    width: int = 500,
    height: int = 500,
    seed: int | None = None,
    **kwargs,
) -> list[list[Terrain]]:
    """
    Generate terrain as a 2D grid (for visualization/debugging).

    This is a convenience wrapper that returns a full grid instead of
    sparse storage. Useful for visualization and testing.

    Args:
        width: World width in cells
        height: World height in cells
        seed: Random seed for reproducibility
        **kwargs: Additional arguments passed to generate_terrain()

    Returns:
        2D list of Terrain values, indexed as grid[y][x]
    """
    terrain_map = generate_terrain(width, height, seed, **kwargs)

    # Build full grid with grass as default
    grid = [
        [Terrain.GRASS for _ in range(width)]
        for _ in range(height)
    ]

    # Fill in non-grass terrain
    for pos, terrain in terrain_map.items():
        grid[pos.y][pos.x] = terrain

    return grid
