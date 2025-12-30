"""Shared pytest fixtures for engine tests."""

import pytest
import tempfile
from datetime import datetime
from pathlib import Path

from engine.domain import (
    AgentName,
    LocationId,
    ConversationId,
    AgentSnapshot,
    AgentLLMModel,
    Location,
    WorldSnapshot,
    Weather,
    TimeSnapshot,
    TimePeriod,
    Conversation,
    ConversationTurn,
    Invitation,
)
from engine.services.scheduler import Scheduler, ScheduledEvent
from engine.services.agent_registry import AgentRegistry
from engine.services.conversation_service import ConversationService
from engine.runtime.context import TickContext


# =============================================================================
# Basic Types
# =============================================================================

@pytest.fixture
def agent_name() -> AgentName:
    """A sample agent name."""
    return AgentName("Ember")


@pytest.fixture
def location_id() -> LocationId:
    """A sample location ID."""
    return LocationId("library")


@pytest.fixture
def conversation_id() -> ConversationId:
    """A sample conversation ID."""
    return ConversationId("conv-001")


# =============================================================================
# Agent Fixtures
# =============================================================================

@pytest.fixture
def sample_llm_model() -> AgentLLMModel:
    """A sample LLM model config."""
    return AgentLLMModel(
        id="claude-3-5-sonnet-20241022",
        display_name="Claude 3.5 Sonnet",
        provider="anthropic",
    )


@pytest.fixture
def sample_agent(sample_llm_model: AgentLLMModel) -> AgentSnapshot:
    """A sample awake agent."""
    return AgentSnapshot(
        name=AgentName("Ember"),
        model=sample_llm_model,
        personality="Curious and creative, loves exploring ideas.",
        job="Artist",
        interests=("painting", "music", "philosophy"),
        note_to_self="Remember to be patient with others.",
        location=LocationId("workshop"),
        mood="curious",
        energy=80,
        goals=("create a new painting", "learn something new"),
        relationships={
            AgentName("Sage"): "close friend",
            AgentName("River"): "acquaintance",
        },
        is_sleeping=False,
    )


@pytest.fixture
def second_agent(sample_llm_model: AgentLLMModel) -> AgentSnapshot:
    """A second sample agent at a different location."""
    return AgentSnapshot(
        name=AgentName("Sage"),
        model=sample_llm_model,
        personality="Thoughtful and wise, enjoys deep conversations.",
        job="Librarian",
        interests=("reading", "history", "tea"),
        note_to_self="Listen more than you speak.",
        location=LocationId("library"),
        mood="contemplative",
        energy=70,
        goals=("organize the archives", "help others find knowledge"),
        relationships={
            AgentName("Ember"): "close friend",
            AgentName("River"): "colleague",
        },
        is_sleeping=False,
    )


@pytest.fixture
def third_agent(sample_llm_model: AgentLLMModel) -> AgentSnapshot:
    """A third sample agent at same location as sample_agent."""
    return AgentSnapshot(
        name=AgentName("River"),
        model=sample_llm_model,
        personality="Energetic and social, always up for an adventure.",
        job="Messenger",
        interests=("running", "meeting people", "stories"),
        note_to_self="Slow down sometimes.",
        location=LocationId("workshop"),  # Same as sample_agent
        mood="excited",
        energy=90,
        goals=("deliver messages", "make new friends"),
        relationships={
            AgentName("Ember"): "acquaintance",
            AgentName("Sage"): "colleague",
        },
        is_sleeping=False,
    )


@pytest.fixture
def sleeping_agent(sample_llm_model: AgentLLMModel) -> AgentSnapshot:
    """A sleeping agent."""
    return AgentSnapshot(
        name=AgentName("Luna"),
        model=sample_llm_model,
        personality="Quiet and introspective, prefers solitude.",
        job="Night watchperson",
        interests=("stargazing", "poetry", "silence"),
        note_to_self="The night reveals truths the day hides.",
        location=LocationId("garden"),
        mood="peaceful",
        energy=40,
        goals=("rest", "observe the stars"),
        relationships={},
        is_sleeping=True,
        sleep_started_tick=10,
        sleep_started_time_period=TimePeriod.EVENING,
    )


# =============================================================================
# Location Fixtures
# =============================================================================

@pytest.fixture
def workshop_location() -> Location:
    """The workshop location."""
    return Location(
        id=LocationId("workshop"),
        name="The Workshop",
        description="A cozy space filled with tools and half-finished projects.",
        features=("workbench", "art supplies", "fireplace"),
        connections=(LocationId("library"), LocationId("garden")),
    )


@pytest.fixture
def library_location() -> Location:
    """The library location."""
    return Location(
        id=LocationId("library"),
        name="The Library",
        description="Tall shelves of books surround comfortable reading nooks.",
        features=("bookshelves", "reading nook", "fireplace"),
        connections=(LocationId("workshop"), LocationId("garden")),
    )


@pytest.fixture
def garden_location() -> Location:
    """The garden location."""
    return Location(
        id=LocationId("garden"),
        name="The Garden",
        description="A peaceful outdoor space with winding paths and flowers.",
        features=("flowers", "bench", "fountain"),
        connections=(LocationId("workshop"), LocationId("library")),
    )


@pytest.fixture
def all_locations(
    workshop_location: Location,
    library_location: Location,
    garden_location: Location,
) -> dict[LocationId, Location]:
    """All locations as a dict."""
    return {
        workshop_location.id: workshop_location,
        library_location.id: library_location,
        garden_location.id: garden_location,
    }


# =============================================================================
# Time Fixtures
# =============================================================================

@pytest.fixture
def base_datetime() -> datetime:
    """A base datetime for tests."""
    return datetime(2024, 6, 15, 10, 0, 0)  # 10 AM


@pytest.fixture
def time_snapshot(base_datetime: datetime) -> TimeSnapshot:
    """Default time snapshot (alias for morning_time)."""
    return TimeSnapshot(
        world_time=base_datetime,  # 10 AM = MORNING
        tick=1,
        start_date=datetime(2024, 6, 15, 0, 0, 0),
    )


@pytest.fixture
def morning_time(base_datetime: datetime) -> TimeSnapshot:
    """A morning TimeSnapshot."""
    return TimeSnapshot(
        world_time=base_datetime,  # 10 AM = MORNING
        tick=1,
        start_date=datetime(2024, 6, 15, 0, 0, 0),
    )


@pytest.fixture
def afternoon_time() -> TimeSnapshot:
    """An afternoon TimeSnapshot."""
    return TimeSnapshot(
        world_time=datetime(2024, 6, 15, 14, 0, 0),  # 2 PM
        tick=5,
        start_date=datetime(2024, 6, 15, 0, 0, 0),
    )


@pytest.fixture
def evening_time() -> TimeSnapshot:
    """An evening TimeSnapshot."""
    return TimeSnapshot(
        world_time=datetime(2024, 6, 15, 19, 0, 0),  # 7 PM
        tick=10,
        start_date=datetime(2024, 6, 15, 0, 0, 0),
    )


@pytest.fixture
def night_time() -> TimeSnapshot:
    """A night TimeSnapshot."""
    return TimeSnapshot(
        world_time=datetime(2024, 6, 15, 23, 0, 0),  # 11 PM
        tick=15,
        start_date=datetime(2024, 6, 15, 0, 0, 0),
    )


# =============================================================================
# World Fixtures
# =============================================================================

@pytest.fixture
def world_snapshot(
    base_datetime: datetime,
    all_locations: dict[LocationId, Location],
    sample_agent: AgentSnapshot,
    second_agent: AgentSnapshot,
) -> WorldSnapshot:
    """A sample world snapshot."""
    return WorldSnapshot(
        tick=1,
        world_time=base_datetime,
        start_date=datetime(2024, 6, 15, 0, 0, 0),
        weather=Weather.CLEAR,
        locations=all_locations,
        agent_locations={
            sample_agent.name: sample_agent.location,
            second_agent.name: second_agent.location,
        },
    )


# =============================================================================
# Conversation Fixtures
# =============================================================================

@pytest.fixture
def sample_conversation_turn(base_datetime: datetime) -> ConversationTurn:
    """A sample conversation turn."""
    return ConversationTurn(
        speaker=AgentName("Ember"),
        narrative="Hello, Sage! I was hoping to find you here.",
        tick=1,
        timestamp=base_datetime,
    )


@pytest.fixture
def sample_invitation(base_datetime: datetime) -> Invitation:
    """A sample invitation."""
    return Invitation(
        conversation_id=ConversationId("conv-001"),
        inviter=AgentName("Ember"),
        invitee=AgentName("Sage"),
        location=LocationId("workshop"),
        privacy="private",
        created_at_tick=1,
        expires_at_tick=2,
        invited_at=base_datetime,
    )


@pytest.fixture
def sample_conversation(
    base_datetime: datetime,
    sample_conversation_turn: ConversationTurn,
) -> Conversation:
    """A sample active conversation."""
    return Conversation(
        id=ConversationId("conv-001"),
        location=LocationId("workshop"),
        privacy="private",
        participants=frozenset({AgentName("Ember"), AgentName("Sage")}),
        history=(sample_conversation_turn,),
        started_at_tick=1,
        created_by=AgentName("Ember"),
        next_speaker=AgentName("Sage"),
    )


@pytest.fixture
def public_conversation(base_datetime: datetime) -> Conversation:
    """A sample public conversation."""
    return Conversation(
        id=ConversationId("conv-002"),
        location=LocationId("library"),
        privacy="public",
        participants=frozenset({AgentName("Sage"), AgentName("River")}),
        history=(),
        started_at_tick=3,
        created_by=AgentName("Sage"),
    )


# =============================================================================
# Service Fixtures
# =============================================================================

@pytest.fixture
def scheduler() -> Scheduler:
    """A fresh Scheduler instance."""
    return Scheduler()


@pytest.fixture
def agent_registry() -> AgentRegistry:
    """A fresh AgentRegistry instance."""
    return AgentRegistry()


@pytest.fixture
def populated_agent_registry(
    agent_registry: AgentRegistry,
    sample_agent: AgentSnapshot,
    second_agent: AgentSnapshot,
    sleeping_agent: AgentSnapshot,
) -> AgentRegistry:
    """An AgentRegistry with agents already registered."""
    agent_registry.register(sample_agent)
    agent_registry.register(second_agent)
    agent_registry.register(sleeping_agent)
    return agent_registry


@pytest.fixture
def conversation_service() -> ConversationService:
    """A fresh ConversationService instance."""
    return ConversationService()


@pytest.fixture
def populated_conversation_service(
    conversation_service: ConversationService,
    sample_conversation: Conversation,
    sample_invitation: Invitation,
) -> ConversationService:
    """A ConversationService with existing data."""
    conversation_service._conversations[sample_conversation.id] = sample_conversation
    for participant in sample_conversation.participants:
        if participant not in conversation_service._agent_conversations:
            conversation_service._agent_conversations[participant] = set()
        conversation_service._agent_conversations[participant].add(sample_conversation.id)
    return conversation_service


# =============================================================================
# Context Fixtures
# =============================================================================

@pytest.fixture
def tick_context(
    morning_time: TimeSnapshot,
    world_snapshot: WorldSnapshot,
    sample_agent: AgentSnapshot,
    second_agent: AgentSnapshot,
) -> TickContext:
    """A basic TickContext for tests."""
    return TickContext(
        tick=1,
        timestamp=morning_time.world_time,
        time_snapshot=morning_time,
        world=world_snapshot,
        agents={
            sample_agent.name: sample_agent,
            second_agent.name: second_agent,
        },
        conversations={},
        pending_invites={},
    )


@pytest.fixture
def tick_context_with_conversation(
    morning_time: TimeSnapshot,
    world_snapshot: WorldSnapshot,
    sample_agent: AgentSnapshot,
    second_agent: AgentSnapshot,
    sample_conversation: Conversation,
) -> TickContext:
    """A TickContext with an active conversation."""
    return TickContext(
        tick=1,
        timestamp=morning_time.world_time,
        time_snapshot=morning_time,
        world=world_snapshot,
        agents={
            sample_agent.name: sample_agent,
            second_agent.name: second_agent,
        },
        conversations={sample_conversation.id: sample_conversation},
        pending_invites={},
    )


# =============================================================================
# Storage Fixtures
# =============================================================================

@pytest.fixture
def temp_village_dir():
    """Create a temporary village directory for storage tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        village_path = Path(tmpdir) / "village"
        village_path.mkdir()
        (village_path / "snapshots").mkdir()
        (village_path / "archive").mkdir()
        yield village_path


# =============================================================================
# Scheduled Event Fixtures
# =============================================================================

@pytest.fixture
def agent_turn_event(base_datetime: datetime) -> ScheduledEvent:
    """A scheduled agent turn event."""
    return ScheduledEvent(
        due_time=base_datetime,
        priority=10,
        event_type="agent_turn",
        target_id="Ember",
        location_id=LocationId("workshop"),
    )


@pytest.fixture
def conversation_turn_event(base_datetime: datetime) -> ScheduledEvent:
    """A scheduled conversation turn event."""
    return ScheduledEvent(
        due_time=base_datetime,
        priority=5,
        event_type="conversation_turn",
        target_id="conv-001",
        location_id=LocationId("workshop"),
    )


@pytest.fixture
def invite_response_event(base_datetime: datetime) -> ScheduledEvent:
    """A scheduled invite response event."""
    return ScheduledEvent(
        due_time=base_datetime,
        priority=1,
        event_type="invite_response",
        target_id="Sage",
        location_id=LocationId("library"),
    )
