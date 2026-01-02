"""Tests for terrain and weather types."""

from hearth.core import (
    Terrain,
    Weather,
    TERRAIN_DEFAULTS,
    is_passable,
    get_symbol,
    get_gather_resource,
)


class TestTerrain:
    """Tests for Terrain enum."""

    def test_all_terrains_exist(self):
        """All expected terrain types exist."""
        assert Terrain.GRASS
        assert Terrain.WATER
        assert Terrain.STONE
        assert Terrain.SAND
        assert Terrain.FOREST

    def test_terrain_values(self):
        """Terrain values are lowercase strings."""
        assert Terrain.GRASS.value == "grass"
        assert Terrain.WATER.value == "water"
        assert Terrain.STONE.value == "stone"
        assert Terrain.SAND.value == "sand"
        assert Terrain.FOREST.value == "forest"

    def test_all_terrains_have_defaults(self):
        """All terrain types have default properties."""
        for terrain in Terrain:
            assert terrain in TERRAIN_DEFAULTS


class TestWeather:
    """Tests for Weather enum."""

    def test_all_weather_types_exist(self):
        """All expected weather types exist."""
        assert Weather.CLEAR
        assert Weather.CLOUDY
        assert Weather.RAINY
        assert Weather.FOGGY

    def test_weather_values(self):
        """Weather values are lowercase strings."""
        assert Weather.CLEAR.value == "clear"
        assert Weather.CLOUDY.value == "cloudy"
        assert Weather.RAINY.value == "rainy"
        assert Weather.FOGGY.value == "foggy"


class TestTerrainHelpers:
    """Tests for terrain helper functions."""

    def test_grass_is_passable(self):
        """Grass terrain is passable."""
        assert is_passable(Terrain.GRASS)

    def test_water_is_not_passable(self):
        """Water terrain is not passable."""
        assert not is_passable(Terrain.WATER)

    def test_stone_is_passable(self):
        """Stone terrain is passable."""
        assert is_passable(Terrain.STONE)

    def test_forest_is_passable(self):
        """Forest terrain is passable."""
        assert is_passable(Terrain.FOREST)

    def test_get_symbol_grass(self):
        """Grass has period symbol."""
        assert get_symbol(Terrain.GRASS) == "."

    def test_get_symbol_water(self):
        """Water has water emoji."""
        assert get_symbol(Terrain.WATER) == "💧"

    def test_get_symbol_forest(self):
        """Forest has tree emoji."""
        assert get_symbol(Terrain.FOREST) == "🌲"

    def test_gather_resource_from_water(self):
        """Can gather water from water terrain."""
        assert get_gather_resource(Terrain.WATER) == "water"

    def test_gather_resource_from_forest(self):
        """Can gather wood from forest terrain."""
        assert get_gather_resource(Terrain.FOREST) == "wood"

    def test_gather_resource_from_stone(self):
        """Can gather stone from stone terrain."""
        assert get_gather_resource(Terrain.STONE) == "stone"

    def test_gather_resource_from_grass(self):
        """Cannot gather resources from grass terrain."""
        assert get_gather_resource(Terrain.GRASS) is None
