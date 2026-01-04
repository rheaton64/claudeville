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
    COAST = "coast"
    STONE = "stone"
    SAND = "sand"
    FOREST = "forest"
    HILL = "hill"


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
# Symbols are distinct ASCII/Unicode so agents can differentiate without color
TERRAIN_DEFAULTS: dict[Terrain, TerrainProperties] = {
    Terrain.GRASS: {
        "passable": True,
        "symbol": ".",
        "gather_resource": "grass",  # Useful for fiber/rope crafting
    },
    Terrain.WATER: {
        "passable": False,
        "symbol": "≈",  # Deep water, impassable
        # No gather_resource - water requires a vessel to collect
    },
    Terrain.COAST: {
        "passable": True,
        "symbol": "~",  # Shallow water, wade-able
        # No gather_resource - transition zone
    },
    Terrain.STONE: {
        "passable": True,
        "symbol": "▲",  # Rocky outcrops, mountains
        "gather_resource": "stone",
    },
    Terrain.SAND: {
        "passable": True,
        "symbol": ":",  # Dots for sand grains
        "gather_resource": "clay",  # Clay found at water's edge (sand terrain)
    },
    Terrain.FOREST: {
        "passable": True,
        "symbol": "♣",  # Club/tree shape
        "gather_resource": "wood",
    },
    Terrain.HILL: {
        "passable": True,
        "symbol": "^",  # Elevated terrain
        # No gather_resource - just elevation
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


# -----------------------------------------------------------------------------
# Emoji Symbol Vocabulary (for agent perception)
# -----------------------------------------------------------------------------

# Emoji symbols for agent perception (richer visual vocabulary than TUI ASCII)
TERRAIN_EMOJI: dict[Terrain, str] = {
    Terrain.GRASS: "·",  # Small dot - open grassland
    Terrain.WATER: "💧",  # Deep water (impassable)
    Terrain.COAST: "〰️",  # Shallow water (passable) - wavy line
    Terrain.STONE: "🪨",  # Rocky terrain
    Terrain.SAND: "░",  # Sand - light shading block (distinct from grass)
    Terrain.FOREST: "🌲",  # Trees
    Terrain.HILL: "⛰️",  # Elevated terrain
}

OBJECT_EMOJI: dict[str, str] = {
    "sign": "📜",
    "placed_item": "✨",
    "structure": "🏠",
}

AGENT_EMOJI = "👤"
SELF_EMOJI = "@"


def get_terrain_emoji(terrain: Terrain) -> str:
    """Get the emoji symbol for terrain (for agent perception)."""
    return TERRAIN_EMOJI.get(terrain, "?")
