"""Tests for the Hearth terrain tileset."""

import pytest

from generation.tileset import create_hearth_tileset, TILE_TO_TERRAIN
from generation.wfc import Direction
from core.terrain import Terrain


class TestTilesetCreation:
    """Test tileset creation."""

    def test_creates_all_terrain_types(self):
        """Should create a tile for each terrain type."""
        tileset = create_hearth_tileset()
        assert len(tileset) == 7
        assert set(tileset.keys()) == {"water", "coast", "sand", "grass", "forest", "hill", "stone"}

    def test_tiles_have_positive_weights(self):
        """All tiles should have positive weights."""
        tileset = create_hearth_tileset()
        for tile_id, tile in tileset.items():
            assert tile.weight > 0, f"{tile_id} has non-positive weight"

    def test_tiles_have_positive_self_affinity(self):
        """All tiles should have positive self-affinity."""
        tileset = create_hearth_tileset()
        for tile_id, tile in tileset.items():
            assert tile.self_affinity > 0, f"{tile_id} has non-positive self_affinity"


class TestAdjacencyRules:
    """Test adjacency rules."""

    def test_all_tiles_have_self_adjacency(self):
        """Every tile should be allowed to be adjacent to itself."""
        tileset = create_hearth_tileset()
        for tile_id, tile in tileset.items():
            for direction in Direction:
                assert tile_id in tile.get_allowed_neighbors(direction), \
                    f"{tile_id} is not self-adjacent in direction {direction}"

    def test_adjacency_is_bidirectional(self):
        """If A allows B to its north, B should allow A to its south."""
        tileset = create_hearth_tileset()
        for tile_a_id, tile_a in tileset.items():
            for direction in Direction:
                for neighbor_id in tile_a.get_allowed_neighbors(direction):
                    neighbor = tileset[neighbor_id]
                    opposite = direction.opposite()
                    assert tile_a_id in neighbor.get_allowed_neighbors(opposite), \
                        f"Non-bidirectional rule: {tile_a_id}->{neighbor_id} ({direction})"

    def test_adjacency_graph_is_connected(self):
        """All tiles should be reachable from any other tile."""
        tileset = create_hearth_tileset()
        tile_ids = set(tileset.keys())

        # BFS from grass (the hub)
        visited = {"grass"}
        queue = ["grass"]

        while queue:
            current = queue.pop(0)
            tile = tileset[current]
            for direction in Direction:
                for neighbor_id in tile.get_allowed_neighbors(direction):
                    if neighbor_id not in visited:
                        visited.add(neighbor_id)
                        queue.append(neighbor_id)

        assert visited == tile_ids, f"Not all tiles reachable: missing {tile_ids - visited}"

    def test_water_cannot_touch_grass_directly(self):
        """Water should require coast as transition to land."""
        tileset = create_hearth_tileset()
        water = tileset["water"]
        for direction in Direction:
            assert "grass" not in water.get_allowed_neighbors(direction), \
                "Water should not be directly adjacent to grass"

    def test_water_gradient_exists(self):
        """Should have water -> coast -> sand -> grass path."""
        tileset = create_hearth_tileset()

        # Water connects to coast
        water = tileset["water"]
        assert "coast" in water.get_allowed_neighbors(Direction.NORTH)

        # Coast connects to sand
        coast = tileset["coast"]
        assert "sand" in coast.get_allowed_neighbors(Direction.NORTH)

        # Sand connects to grass
        sand = tileset["sand"]
        assert "grass" in sand.get_allowed_neighbors(Direction.NORTH)

    def test_elevation_gradient_exists(self):
        """Should have grass -> hill -> stone path."""
        tileset = create_hearth_tileset()

        # Grass connects to hill
        grass = tileset["grass"]
        assert "hill" in grass.get_allowed_neighbors(Direction.NORTH)

        # Hill connects to stone
        hill = tileset["hill"]
        assert "stone" in hill.get_allowed_neighbors(Direction.NORTH)


class TestTerrainMapping:
    """Test tile ID to Terrain enum mapping."""

    def test_all_tiles_map_to_terrain(self):
        """Every tile should map to a Terrain enum value."""
        tileset = create_hearth_tileset()
        for tile_id in tileset.keys():
            assert tile_id in TILE_TO_TERRAIN, f"{tile_id} not in TILE_TO_TERRAIN"
            assert isinstance(TILE_TO_TERRAIN[tile_id], Terrain)

    def test_mapping_covers_all_terrain_types(self):
        """Mapping should cover all Terrain enum values."""
        terrain_values = set(TILE_TO_TERRAIN.values())
        expected = {Terrain.WATER, Terrain.COAST, Terrain.SAND, Terrain.GRASS,
                   Terrain.FOREST, Terrain.HILL, Terrain.STONE}
        assert terrain_values == expected
