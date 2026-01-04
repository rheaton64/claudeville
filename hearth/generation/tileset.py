"""
Hearth terrain tileset for Wave Function Collapse.

Defines 7 terrain types with adjacency rules that create natural gradients:
    water -> coast -> sand -> grass -> forest/hill -> stone

The key insight: by only allowing certain tiles to neighbor each other,
we get emergent large-scale structure (coastlines, mountain ranges, forests)
from purely local rules.
"""

from core.terrain import Terrain
from .wfc import Tile, make_bidirectional_rule


def create_hearth_tileset() -> dict[str, Tile]:
    """
    Create the terrain tileset with all adjacency rules defined.

    Returns a dict mapping tile ID to Tile object.
    """
    # Define tiles with weights and self-affinity
    # Higher weight = more common in output
    # Higher self_affinity = stronger clustering (smoother biomes)
    # Settings from "Addison's World" in terrain project
    tiles = {
        "water": Tile(
            id="water",
            color=(26, 82, 118),      # Deep blue
            weight=1.12,              # From Addison's World
            self_affinity=3.98,       # Strong clustering for lakes/oceans
        ),
        "coast": Tile(
            id="coast",
            color=(133, 193, 233),    # Light blue
            weight=2.0,               # From Addison's World
            self_affinity=1.12,       # Slight clustering for coastlines
        ),
        "sand": Tile(
            id="sand",
            color=(244, 208, 63),     # Tan/yellow
            weight=1.5,               # Default (not in Addison's overrides)
            self_affinity=0.9,
        ),
        "grass": Tile(
            id="grass",
            color=(39, 174, 96),      # Green
            weight=4.03,              # From Addison's World - most common
            self_affinity=3.98,       # Strong clustering for large plains
        ),
        "forest": Tile(
            id="forest",
            color=(30, 132, 73),      # Dark green
            weight=2.07,              # From Addison's World
            self_affinity=2.23,       # Strong clustering for forest patches
        ),
        "hill": Tile(
            id="hill",
            color=(160, 64, 0),       # Brown
            weight=1.93,              # From Addison's World
            self_affinity=1.09,       # Moderate - rolling hills
        ),
        "stone": Tile(
            id="stone",
            color=(127, 140, 141),    # Gray
            weight=1.32,              # From Addison's World (was "mountain")
            self_affinity=2.16,       # Strong clustering for mountain ranges
        ),
    }

    # Define adjacency rules
    # These create natural terrain gradients:
    #
    #   water <-> coast <-> sand <-> grass <-> forest
    #                                   |         |
    #                                 hill  <->  hill
    #                                   |
    #                                stone
    #

    # Water gradient: water -> coast -> sand -> grass
    make_bidirectional_rule(tiles, "water", "water")
    make_bidirectional_rule(tiles, "water", "coast")
    make_bidirectional_rule(tiles, "coast", "coast")
    make_bidirectional_rule(tiles, "coast", "sand")
    make_bidirectional_rule(tiles, "sand", "sand")
    make_bidirectional_rule(tiles, "sand", "grass")

    # Land: grass is the hub - connects to sand, forest, and hills
    make_bidirectional_rule(tiles, "grass", "grass")
    make_bidirectional_rule(tiles, "grass", "forest")
    make_bidirectional_rule(tiles, "grass", "hill")

    # Forest connects to grass and hills (forested foothills)
    make_bidirectional_rule(tiles, "forest", "forest")
    make_bidirectional_rule(tiles, "forest", "hill")

    # Elevation: hill -> stone (mountains)
    make_bidirectional_rule(tiles, "hill", "hill")
    make_bidirectional_rule(tiles, "hill", "stone")
    make_bidirectional_rule(tiles, "stone", "stone")

    return tiles


# Map WFC tile IDs to Hearth Terrain enum
TILE_TO_TERRAIN: dict[str, Terrain] = {
    "water": Terrain.WATER,
    "coast": Terrain.COAST,
    "sand": Terrain.SAND,
    "grass": Terrain.GRASS,
    "forest": Terrain.FOREST,
    "hill": Terrain.HILL,
    "stone": Terrain.STONE,
}


# Quick reference for the adjacency graph:
#
# water:  [water, coast]
# coast:  [water, coast, sand]
# sand:   [coast, sand, grass]
# grass:  [sand, grass, forest, hill]
# forest: [grass, forest, hill]
# hill:   [grass, forest, hill, stone]
# stone:  [hill, stone]
