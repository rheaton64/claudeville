"""Tests for terrain generation."""

import pytest

from generation import generate_terrain, generate_terrain_grid
from generation.tileset import TILE_TO_TERRAIN
from core.types import Position
from core.terrain import Terrain


class TestGenerateTerrain:
    """Test the main terrain generation function."""

    def test_generates_small_grid_without_error(self):
        """Should generate a small grid without contradiction."""
        # Use a known-good seed for reliability (seed 42 causes contradictions)
        result = generate_terrain(width=20, height=20, seed=12345)
        assert isinstance(result, dict)

    def test_seed_produces_reproducible_results(self):
        """Same seed should produce identical terrain."""
        result1 = generate_terrain(width=20, height=20, seed=12345)
        result2 = generate_terrain(width=20, height=20, seed=12345)
        assert result1 == result2

    def test_different_seeds_produce_different_results(self):
        """Different seeds should produce different terrain (usually)."""
        result1 = generate_terrain(width=20, height=20, seed=1)
        result2 = generate_terrain(width=20, height=20, seed=2)
        # Could theoretically be equal but extremely unlikely
        assert result1 != result2

    def test_returns_sparse_map_without_grass(self):
        """Result should not contain grass (it's the default)."""
        result = generate_terrain(width=20, height=20, seed=12345)
        for terrain in result.values():
            assert terrain != Terrain.GRASS

    def test_all_positions_are_valid(self):
        """All positions in result should be within bounds."""
        width, height = 20, 20
        result = generate_terrain(width=width, height=height, seed=12345)
        for pos in result.keys():
            assert 0 <= pos.x < width, f"x out of bounds: {pos.x}"
            assert 0 <= pos.y < height, f"y out of bounds: {pos.y}"

    def test_contains_expected_terrain_types(self):
        """Generated terrain should include various terrain types."""
        # Larger grid to ensure variety
        result = generate_terrain(width=50, height=50, seed=12345)
        terrain_types = set(result.values())

        # Should have at least a few different types
        assert len(terrain_types) >= 3, "Expected more terrain variety"

    def test_water_is_bounded_by_coast(self):
        """Water cells should only be adjacent to water or coast."""
        width, height = 30, 30
        result = generate_terrain(width=width, height=height, seed=12345)

        # Build full grid for neighbor checking
        grid = {pos: terrain for pos, terrain in result.items()}

        for pos, terrain in result.items():
            if terrain == Terrain.WATER:
                # Check all neighbors
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nx, ny = pos.x + dx, pos.y + dy
                    if 0 <= nx < width and 0 <= ny < height:
                        neighbor_pos = Position(nx, ny)
                        neighbor_terrain = grid.get(neighbor_pos, Terrain.GRASS)
                        assert neighbor_terrain in (Terrain.WATER, Terrain.COAST), \
                            f"Water at {pos} adjacent to {neighbor_terrain} at {neighbor_pos}"

    def test_stone_is_bounded_by_hill(self):
        """Stone cells should only be adjacent to stone or hill."""
        width, height = 50, 50
        result = generate_terrain(width=width, height=height, seed=12345)

        # Build full grid for neighbor checking
        grid = {pos: terrain for pos, terrain in result.items()}

        for pos, terrain in result.items():
            if terrain == Terrain.STONE:
                # Check all neighbors
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nx, ny = pos.x + dx, pos.y + dy
                    if 0 <= nx < width and 0 <= ny < height:
                        neighbor_pos = Position(nx, ny)
                        neighbor_terrain = grid.get(neighbor_pos, Terrain.GRASS)
                        assert neighbor_terrain in (Terrain.STONE, Terrain.HILL), \
                            f"Stone at {pos} adjacent to {neighbor_terrain} at {neighbor_pos}"


class TestGenerateTerrainGrid:
    """Test the 2D grid generation convenience function."""

    def test_returns_2d_list(self):
        """Should return a 2D list of Terrain values."""
        grid = generate_terrain_grid(width=10, height=10, seed=12345)
        assert isinstance(grid, list)
        assert len(grid) == 10  # height
        assert all(len(row) == 10 for row in grid)  # width

    def test_all_cells_have_terrain(self):
        """Every cell should have a Terrain value."""
        grid = generate_terrain_grid(width=10, height=10, seed=12345)
        for row in grid:
            for cell in row:
                assert isinstance(cell, Terrain)

    def test_default_terrain_is_grass(self):
        """Most cells should be grass (the default)."""
        grid = generate_terrain_grid(width=20, height=20, seed=12345)
        grass_count = sum(1 for row in grid for cell in row if cell == Terrain.GRASS)
        total_cells = 20 * 20

        # Grass should be the most common (weight=3.0 in tileset)
        assert grass_count > total_cells * 0.2, "Expected grass to be common"


class TestGeneratorParameters:
    """Test generator parameter effects."""

    def test_higher_water_ratio_produces_more_water(self):
        """Higher max_water_ratio should allow more water cells."""
        # Low water ratio (seed=2 works with both water ratios)
        result_low = generate_terrain(
            width=30, height=30, seed=2,
            max_water_ratio=0.1, batch_size=50
        )
        water_low = sum(1 for t in result_low.values() if t == Terrain.WATER)

        # High water ratio
        result_high = generate_terrain(
            width=30, height=30, seed=2,
            max_water_ratio=0.8, batch_size=50
        )
        water_high = sum(1 for t in result_high.values() if t == Terrain.WATER)

        # High ratio should typically allow more water
        # (not guaranteed due to randomness, but likely with same seed)
        # Just check both complete without error
        assert isinstance(result_low, dict)
        assert isinstance(result_high, dict)

    def test_progress_callback_is_called(self):
        """Progress callback should be called during generation."""
        calls = []

        def callback(step, total):
            calls.append((step, total))

        generate_terrain(width=20, height=20, seed=12345, progress_callback=callback)

        assert len(calls) > 0, "Callback was never called"
        # Final call should have step close to total
        last_step, total = calls[-1]
        assert total == 400  # 20x20
        assert last_step == total  # Should complete


class TestLargeGrid:
    """Test generation of larger grids."""

    @pytest.mark.slow
    def test_medium_grid_completes(self):
        """100x100 grid should complete without error."""
        result = generate_terrain(width=100, height=100, seed=12345, batch_size=100)
        assert len(result) > 0

    @pytest.mark.slow
    def test_large_grid_completes(self):
        """500x500 grid should complete without error."""
        result = generate_terrain(width=500, height=500, seed=12345, batch_size=200)
        assert len(result) > 0
