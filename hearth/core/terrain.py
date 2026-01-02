"""Terrain and weather types for Hearth.

This module defines terrain types and weather conditions that affect the world.
Terrain properties can be extended via config, but these are the core types.
"""

from __future__ import annotations

from enum import Enum
from typing import TypedDict


class Terrain(Enum):
    """Types of terrain in the world."""

    GRASS = "grass"
    WATER = "water"
    STONE = "stone"
    SAND = "sand"
    FOREST = "forest"


class Weather(Enum):
    """Weather conditions that affect atmosphere and visibility."""

    CLEAR = "clear"
    CLOUDY = "cloudy"
    RAINY = "rainy"
    FOGGY = "foggy"


class TerrainProperties(TypedDict, total=False):
    """Properties for a terrain type."""

    passable: bool
    symbol: str
    gather_resource: str | None  # What resource can be gathered here


# Default terrain properties (can be extended via config)
TERRAIN_DEFAULTS: dict[Terrain, TerrainProperties] = {
    Terrain.GRASS: {
        "passable": True,
        "symbol": ".",
        "gather_resource": None,
    },
    Terrain.WATER: {
        "passable": False,
        "symbol": "💧",
        "gather_resource": "water",
    },
    Terrain.STONE: {
        "passable": True,
        "symbol": "🪨",
        "gather_resource": "stone",
    },
    Terrain.SAND: {
        "passable": True,
        "symbol": "~",
        "gather_resource": "sand",
    },
    Terrain.FOREST: {
        "passable": True,
        "symbol": "🌲",
        "gather_resource": "wood",
    },
}


def is_passable(terrain: Terrain) -> bool:
    """Check if terrain can be walked through."""
    return TERRAIN_DEFAULTS.get(terrain, {}).get("passable", True)


def get_symbol(terrain: Terrain) -> str:
    """Get the display symbol for terrain."""
    return TERRAIN_DEFAULTS.get(terrain, {}).get("symbol", "?")


def get_gather_resource(terrain: Terrain) -> str | None:
    """Get what resource can be gathered from this terrain, if any."""
    return TERRAIN_DEFAULTS.get(terrain, {}).get("gather_resource")
