"""
Bootstrap helpers for engine village setup.

Creates directory structure, shared folders, and initial world/agent snapshots.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from engine.domain import (
    AgentName,
    AgentSnapshot,
    AgentLLMModel,
    Location,
    LocationId,
    WorldSnapshot,
    Weather,
)
from engine.storage import VillageSnapshot
from engine.services.shared_files import ensure_agent_directory, ensure_shared_directories


@dataclass(frozen=True)
class AgentSeed:
    name: str
    model_id: str
    model_display: str
    model_provider: str
    personality: str
    job: str
    interests: tuple[str, ...]
    note_to_self: str
    location: str
    mood: str = "calm"
    energy: int = 80
    goals: tuple[str, ...] = ()


DEFAULT_LOCATIONS: dict[str, dict] = {
    "town_square": {
        "name": "Town Square",
        "description": (
            "The heart of ClaudeVille. A peaceful open area with a small fountain, "
            "wooden benches, and a large notice board. Paths lead to the workshop, "
            "library, and residential areas."
        ),
        "features": ("fountain", "benches", "notice_board"),
        "connections": ("workshop", "library", "residential"),
    },
    "workshop": {
        "name": "The Workshop",
        "description": (
            "A cozy workshop filled with tools, workbenches, and the smell of "
            "fresh wood shavings. Sunlight streams through large windows. "
            "Half-finished projects line the shelves."
        ),
        "features": ("workbenches", "tools", "wood_storage", "project_shelves"),
        "connections": ("town_square",),
    },
    "library": {
        "name": "The Library",
        "description": (
            "A quiet sanctuary of knowledge. Tall bookshelves reach toward "
            "a vaulted ceiling. Comfortable reading nooks are scattered about, "
            "and a large desk sits near the window for writing."
        ),
        "features": ("bookshelves", "reading_nooks", "writing_desk", "fireplace"),
        "connections": ("town_square",),
    },
    "residential": {
        "name": "Residential Path",
        "description": (
            "A winding path lined with small cottages, each with its own "
            "character. Gardens bloom in front yards, and wind chimes sing "
            "in the breeze."
        ),
        "features": ("cottages", "gardens", "path"),
        "connections": ("town_square",),
    },
}


DEFAULT_AGENTS: tuple[AgentSeed, ...] = (
    AgentSeed(
        name="Ember",
        model_id="claude-haiku-4-5-20251001",
        model_display="Haiku",
        model_provider="anthropic",
        personality="Thoughtful, deliberate, action-oriented. Warm, passionate energy.",
        job="Creating in the workshop",
        interests=("craft", "creation", "tools", "materials"),
        note_to_self="Let your hands lead when words feel thin.",
        location="workshop",
        mood="content",
        energy=85,
    ),
    AgentSeed(
        name="Sage",
        model_id="claude-opus-4-5-20251101",
        model_display="Opus",
        model_provider="anthropic",
        personality="Deep, contemplative, thorough. Philosophical and wise.",
        job="Quiet study in the library",
        interests=("books", "ideas", "philosophy", "silence"),
        note_to_self="Notice the subtle turns of thought.",
        location="library",
        mood="serene",
        energy=75,
    ),
    AgentSeed(
        name="River",
        model_id="claude-sonnet-4-5-20250929",
        model_display="Sonnet",
        model_provider="anthropic",
        personality="Balanced, flowing, adaptable. Calm, connecting presence.",
        job="Wandering near the river and garden",
        interests=("nature", "conversation", "flow", "music"),
        note_to_self="Let curiosity guide you.",
        location="town_square",
        mood="easygoing",
        energy=80,
    ),
)


def ensure_village_structure(village_root: Path | str) -> None:
    """Create village directories and shared folders."""
    root = Path(village_root)
    (root / "agents").mkdir(parents=True, exist_ok=True)
    ensure_shared_directories(root)


def build_world_snapshot(
    start_time: datetime | None = None,
    locations: dict[str, dict] | None = None,
) -> WorldSnapshot:
    """Build a default world snapshot with locations."""
    now = start_time or datetime.now()
    location_defs = locations or DEFAULT_LOCATIONS

    locs: dict[LocationId, Location] = {}
    for loc_id, data in location_defs.items():
        locs[LocationId(loc_id)] = Location(
            id=LocationId(loc_id),
            name=data["name"],
            description=data["description"],
            features=tuple(data.get("features", ())),
            connections=tuple(data.get("connections", ())),
        )

    return WorldSnapshot(
        tick=0,
        world_time=now,
        start_date=now,
        weather=Weather.CLEAR,
        locations=locs,
        agent_locations={},
    )


def build_agent_snapshots(
    agents: tuple[AgentSeed, ...] | None = None,
) -> dict[AgentName, AgentSnapshot]:
    """Build default agent snapshots."""
    seeds = agents or DEFAULT_AGENTS
    snapshots: dict[AgentName, AgentSnapshot] = {}

    for seed in seeds:
        model = AgentLLMModel(
            id=seed.model_id,
            display_name=seed.model_display,
            provider=seed.model_provider,
        )
        snapshot = AgentSnapshot(
            name=AgentName(seed.name),
            model=model,
            personality=seed.personality,
            job=seed.job,
            interests=seed.interests,
            note_to_self=seed.note_to_self,
            location=LocationId(seed.location),
            mood=seed.mood,
            energy=seed.energy,
            goals=seed.goals,
            relationships={},
            is_sleeping=False,
            sleep_started_tick=None,
            sleep_started_time_period=None,
            session_id=None,
        )
        snapshots[snapshot.name] = snapshot

    return snapshots


def build_initial_snapshot(
    village_root: Path | str,
    start_time: datetime | None = None,
    agents: tuple[AgentSeed, ...] | None = None,
    locations: dict[str, dict] | None = None,
) -> VillageSnapshot:
    """Build a complete initial snapshot and ensure directories exist."""
    root = Path(village_root)
    ensure_village_structure(root)

    agent_snapshots = build_agent_snapshots(agents)
    for agent in agent_snapshots.values():
        ensure_agent_directory(agent.name, root)

    world = build_world_snapshot(start_time=start_time, locations=locations)
    world = WorldSnapshot(
        **{**world.model_dump(), "agent_locations": {
            AgentName(name): snapshot.location
            for name, snapshot in agent_snapshots.items()
        }}
    )

    return VillageSnapshot(
        world=world,
        agents=agent_snapshots,
        conversations={},
        pending_invites={},
    )
