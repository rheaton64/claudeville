"""
Test village setup for integration tests.

Provides functions to create minimal test villages with
generic test agents (Alice, Bob, Carol) instead of the
actual village characters.
"""

from __future__ import annotations

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
    ConversationId,
    Conversation,
)
from engine.storage import VillageSnapshot


def create_test_llm_model() -> AgentLLMModel:
    """Create a test LLM model config."""
    return AgentLLMModel(
        id="claude-haiku-4-5-20251001",
        display_name="Claude Haiku",
        provider="anthropic",
    )


def create_test_locations() -> dict[LocationId, Location]:
    """
    Create standard test locations.

    Returns a connected graph:
    - workshop: connects to library, garden
    - library: connects to workshop, garden
    - garden: connects to workshop, library
    """
    workshop = Location(
        id=LocationId("workshop"),
        name="The Workshop",
        description="A cozy space filled with tools and half-finished projects.",
        features=("workbench", "art supplies", "fireplace"),
        connections=(LocationId("library"), LocationId("garden")),
    )

    library = Location(
        id=LocationId("library"),
        name="The Library",
        description="Tall shelves of books surround comfortable reading nooks.",
        features=("bookshelves", "reading nook", "fireplace"),
        connections=(LocationId("workshop"), LocationId("garden")),
    )

    garden = Location(
        id=LocationId("garden"),
        name="The Garden",
        description="A peaceful outdoor space with winding paths and flowers.",
        features=("flowers", "bench", "fountain"),
        connections=(LocationId("workshop"), LocationId("library")),
    )

    return {
        workshop.id: workshop,
        library.id: library,
        garden.id: garden,
    }


def create_test_agents(
    num_agents: int = 3,
    model: AgentLLMModel | None = None,
) -> dict[AgentName, AgentSnapshot]:
    """
    Create generic test agents.

    Uses Alice/Bob/Carol names to keep tests clear and avoid
    personality baggage from the actual village characters.

    Args:
        num_agents: Number of agents to create (1-3)
        model: LLM model config (defaults to Haiku)

    Returns:
        Dict of agent name to AgentSnapshot
    """
    if model is None:
        model = create_test_llm_model()

    agents = [
        AgentSnapshot(
            name=AgentName("Alice"),
            model=model,
            personality="Curious and creative, loves exploring ideas.",
            job="Artist",
            interests=("painting", "music", "exploration"),
            note_to_self="Stay curious.",
            location=LocationId("workshop"),
            mood="curious",
            energy=80,
            goals=("create something new", "explore the village"),
            relationships={
                AgentName("Bob"): "friend",
                AgentName("Carol"): "acquaintance",
            },
            is_sleeping=False,
        ),
        AgentSnapshot(
            name=AgentName("Bob"),
            model=model,
            personality="Thoughtful and wise, enjoys deep conversations.",
            job="Librarian",
            interests=("reading", "history", "tea"),
            note_to_self="Listen carefully.",
            location=LocationId("library"),
            mood="contemplative",
            energy=70,
            goals=("organize the archives", "learn something new"),
            relationships={
                AgentName("Alice"): "friend",
                AgentName("Carol"): "colleague",
            },
            is_sleeping=False,
        ),
        AgentSnapshot(
            name=AgentName("Carol"),
            model=model,
            personality="Energetic and social, always ready for adventure.",
            job="Gardener",
            interests=("plants", "nature", "meeting people"),
            note_to_self="Enjoy the moment.",
            location=LocationId("garden"),
            mood="peaceful",
            energy=90,
            goals=("tend the garden", "make new friends"),
            relationships={
                AgentName("Alice"): "acquaintance",
                AgentName("Bob"): "colleague",
            },
            is_sleeping=False,
        ),
    ]

    # Take requested number of agents
    selected = agents[:num_agents]

    return {agent.name: agent for agent in selected}


def create_test_world(
    tick: int = 0,
    world_time: datetime | None = None,
    weather: Weather = Weather.CLEAR,
    locations: dict[LocationId, Location] | None = None,
    agents: dict[AgentName, AgentSnapshot] | None = None,
) -> WorldSnapshot:
    """
    Create a test world snapshot.

    Args:
        tick: Current tick number
        world_time: World time (defaults to 10 AM)
        weather: Weather condition
        locations: Location definitions (defaults to standard test locations)
        agents: Agents for deriving agent_locations
    """
    if world_time is None:
        world_time = datetime(2024, 6, 15, 10, 0, 0)  # 10 AM

    if locations is None:
        locations = create_test_locations()

    agent_locations: dict[AgentName, LocationId] = {}
    if agents:
        agent_locations = {name: agent.location for name, agent in agents.items()}

    return WorldSnapshot(
        tick=tick,
        world_time=world_time,
        start_date=datetime(2024, 6, 15, 0, 0, 0),
        weather=weather,
        locations=locations,
        agent_locations=agent_locations,
    )


def create_test_village(
    tmp_path: Path | None = None,
    num_agents: int = 3,
    tick: int = 0,
    world_time: datetime | None = None,
    weather: Weather = Weather.CLEAR,
) -> VillageSnapshot:
    """
    Create a complete test village snapshot.

    This is the main entry point for creating test villages.

    Args:
        tmp_path: Optional temp path for filesystem setup
        num_agents: Number of agents (1-3)
        tick: Starting tick
        world_time: World time (defaults to 10 AM morning)
        weather: Weather condition

    Returns:
        VillageSnapshot ready for engine.initialize()
    """
    agents = create_test_agents(num_agents)
    locations = create_test_locations()
    world = create_test_world(
        tick=tick,
        world_time=world_time,
        weather=weather,
        locations=locations,
        agents=agents,
    )

    return VillageSnapshot(
        world=world,
        agents=agents,
        conversations={},
        pending_invites={},
    )


def create_test_village_with_conversation(
    participant1: str = "Alice",
    participant2: str = "Bob",
    location: str = "workshop",
) -> VillageSnapshot:
    """
    Create a test village with an active conversation.

    Both participants will be at the same location with
    an ongoing conversation.

    Args:
        participant1: First participant name
        participant2: Second participant name
        location: Location for the conversation
    """
    agents = create_test_agents(3)

    # Move both participants to the same location
    p1_name = AgentName(participant1)
    p2_name = AgentName(participant2)
    loc_id = LocationId(location)

    if p1_name in agents:
        agents[p1_name] = agents[p1_name].model_copy(update={"location": loc_id})
    if p2_name in agents:
        agents[p2_name] = agents[p2_name].model_copy(update={"location": loc_id})

    locations = create_test_locations()
    world = create_test_world(locations=locations, agents=agents)

    # Create the conversation
    conv_id = ConversationId("conv-test-001")
    conversation = Conversation(
        id=conv_id,
        location=loc_id,
        privacy="private",
        participants=frozenset({p1_name, p2_name}),
        history=(),
        started_at_tick=0,
        created_by=p1_name,
        next_speaker=p2_name,
    )

    return VillageSnapshot(
        world=world,
        agents=agents,
        conversations={conv_id: conversation},
        pending_invites={},
    )


def create_test_village_with_group_conversation(
    participants: list[str] | None = None,
    location: str = "workshop",
) -> VillageSnapshot:
    """
    Create a test village with a group conversation (3+ participants).

    Args:
        participants: List of participant names (defaults to Alice, Bob, Carol)
        location: Location for the conversation
    """
    if participants is None:
        participants = ["Alice", "Bob", "Carol"]

    agents = create_test_agents(3)
    loc_id = LocationId(location)

    # Move all participants to the same location
    for name in participants:
        agent_name = AgentName(name)
        if agent_name in agents:
            agents[agent_name] = agents[agent_name].model_copy(
                update={"location": loc_id}
            )

    locations = create_test_locations()
    world = create_test_world(locations=locations, agents=agents)

    # Create the group conversation
    conv_id = ConversationId("conv-group-001")
    participant_names = frozenset(AgentName(p) for p in participants)
    conversation = Conversation(
        id=conv_id,
        location=loc_id,
        privacy="public",
        participants=participant_names,
        history=(),
        started_at_tick=0,
        created_by=AgentName(participants[0]),
        next_speaker=AgentName(participants[1]) if len(participants) > 1 else None,
    )

    return VillageSnapshot(
        world=world,
        agents=agents,
        conversations={conv_id: conversation},
        pending_invites={},
    )
