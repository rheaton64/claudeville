"""
Pytest configuration for integration tests.

Provides fixtures for real Haiku interpreter, mock LLM provider,
and full engine tests.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from tests.integration.fixtures import (
    MockLLMProvider,
    create_test_village,
    create_test_locations,
    SAMPLE_NARRATIVES,
)
from tests.integration.fixtures.test_village import (
    create_test_village_with_conversation,
    create_test_village_with_group_conversation,
    create_test_agents,
    create_test_world,
)
from engine.domain import AgentName, LocationId
from engine.runtime.interpreter import NarrativeInterpreter

if TYPE_CHECKING:
    from engine.engine import VillageEngine


# =============================================================================
# Pytest Markers
# =============================================================================

def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    )
    config.addinivalue_line(
        "markers",
        "expensive: marks tests as expensive in API costs",
    )
    config.addinivalue_line(
        "markers",
        "haiku: marks tests that require real Claude Haiku API calls",
    )


# =============================================================================
# Skip Conditions
# =============================================================================

# Skip Haiku tests without API key
requires_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)


# =============================================================================
# Basic Fixtures
# =============================================================================

@pytest.fixture
def temp_village(tmp_path: Path) -> Path:
    """Fresh village directory for each test."""
    village_path = tmp_path / "village"
    village_path.mkdir()
    (village_path / "snapshots").mkdir()
    (village_path / "archive").mkdir()
    (village_path / "agents").mkdir()
    (village_path / "traces").mkdir()
    (village_path / "shared").mkdir()
    return village_path


@pytest.fixture
def sample_narratives() -> dict[str, str]:
    """Sample narratives for testing."""
    return SAMPLE_NARRATIVES


# =============================================================================
# Mock LLM Provider Fixtures
# =============================================================================

@pytest.fixture
def mock_provider() -> MockLLMProvider:
    """Deterministic LLM provider for predictable tests."""
    return MockLLMProvider()


# =============================================================================
# Real Haiku Interpreter Fixtures
# =============================================================================

@pytest.fixture
def haiku_interpreter() -> NarrativeInterpreter:
    """
    Real Claude Haiku interpreter for integration tests.

    Uses default location context (workshop, can go to library/garden).
    No other agents present.
    """
    return NarrativeInterpreter(
        current_location="workshop",
        available_paths=["library", "garden"],
        present_agents=[],
        model="claude-haiku-4-5-20251001",
    )


@pytest.fixture
def haiku_interpreter_with_others() -> NarrativeInterpreter:
    """
    Real Claude Haiku interpreter with other agents present.

    For testing group conversation features like next_speaker detection.
    """
    return NarrativeInterpreter(
        current_location="workshop",
        available_paths=["library", "garden"],
        present_agents=["Bob", "Carol"],
        model="claude-haiku-4-5-20251001",
    )


@pytest.fixture
def haiku_interpreter_in_library() -> NarrativeInterpreter:
    """Real Claude Haiku interpreter in the library."""
    return NarrativeInterpreter(
        current_location="library",
        available_paths=["workshop", "garden"],
        present_agents=[],
        model="claude-haiku-4-5-20251001",
    )


@pytest.fixture
def haiku_interpreter_in_garden() -> NarrativeInterpreter:
    """Real Claude Haiku interpreter in the garden."""
    return NarrativeInterpreter(
        current_location="garden",
        available_paths=["workshop", "library"],
        present_agents=[],
        model="claude-haiku-4-5-20251001",
    )


# =============================================================================
# Village Snapshot Fixtures
# =============================================================================

@pytest.fixture
def test_village_snapshot():
    """Fresh test village snapshot with 3 agents."""
    return create_test_village()


@pytest.fixture
def test_village_snapshot_with_conversation():
    """Test village with Alice and Bob in a conversation at workshop."""
    return create_test_village_with_conversation(
        participant1="Alice",
        participant2="Bob",
        location="workshop",
    )


@pytest.fixture
def test_village_snapshot_with_group():
    """Test village with all three agents in a group conversation."""
    return create_test_village_with_group_conversation(
        participants=["Alice", "Bob", "Carol"],
        location="workshop",
    )


# =============================================================================
# Engine Fixtures (Mock LLM)
# =============================================================================

@pytest.fixture
async def test_engine(
    temp_village: Path,
    mock_provider: MockLLMProvider,
) -> "VillageEngine":
    """
    Engine with mock LLM for deterministic tests.

    Initialized with standard test village (Alice, Bob, Carol).
    """
    from engine.engine import VillageEngine

    engine = VillageEngine(
        village_root=temp_village,
        llm_provider=mock_provider,
    )
    snapshot = create_test_village()
    engine.initialize(snapshot)

    yield engine

    await engine.shutdown()


@pytest.fixture
async def test_engine_with_conversation(
    temp_village: Path,
    mock_provider: MockLLMProvider,
) -> "VillageEngine":
    """
    Engine with mock LLM and an active conversation.

    Alice and Bob are in a conversation at the workshop.
    """
    from engine.engine import VillageEngine

    engine = VillageEngine(
        village_root=temp_village,
        llm_provider=mock_provider,
    )
    snapshot = create_test_village_with_conversation()
    engine.initialize(snapshot)

    yield engine

    await engine.shutdown()


@pytest.fixture
async def test_engine_with_group_conversation(
    temp_village: Path,
    mock_provider: MockLLMProvider,
) -> "VillageEngine":
    """
    Engine with mock LLM and a group conversation.

    Alice, Bob, and Carol are in a conversation at the workshop.
    """
    from engine.engine import VillageEngine

    engine = VillageEngine(
        village_root=temp_village,
        llm_provider=mock_provider,
    )
    snapshot = create_test_village_with_group_conversation()
    engine.initialize(snapshot)

    yield engine

    await engine.shutdown()


# =============================================================================
# Engine Fixtures (Real Haiku)
# =============================================================================

@pytest.fixture
def haiku_engine(temp_village: Path) -> "VillageEngine":
    """
    Engine with real Claude Haiku provider.

    Use for behavior validation tests.
    Marked slow/expensive - skip in fast CI runs.

    Note: Model is configured per-agent in create_test_village(),
    not in the provider constructor.
    """
    from engine.engine import VillageEngine
    from engine.adapters import ClaudeProvider

    provider = ClaudeProvider()

    engine = VillageEngine(
        village_root=temp_village,
        llm_provider=provider,
    )
    snapshot = create_test_village()
    engine.initialize(snapshot)

    return engine
    # No explicit shutdown needed - temp_village cleanup handles it


# =============================================================================
# LLM-as-Judge Fixtures
# =============================================================================

@pytest.fixture
def llm_judge():
    """
    LLM judge for evaluating behavioral tests.

    Returns a callable that takes (question, context) and returns
    a structured judgment.
    """
    import anthropic
    from pydantic import BaseModel

    client = anthropic.Anthropic()

    class BehaviorJudgment(BaseModel):
        """Structured output from LLM judge."""
        passed: bool
        reasoning: str
        confidence: float  # 0-1

    def judge(question: str, context: str) -> BehaviorJudgment:
        """Use Haiku to judge behavioral correctness."""
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": f"""Evaluate this behavioral test.

Context:
{context}

Question:
{question}

Judge whether the behavior is correct. Return JSON:
{{"passed": bool, "reasoning": str, "confidence": float}}"""
            }],
        )

        import json
        text = response.content[0].text
        # Try to extract JSON from the response
        if "{" in text and "}" in text:
            json_str = text[text.index("{"):text.rindex("}") + 1]
            data = json.loads(json_str)
            return BehaviorJudgment(**data)

        # Fallback if parsing fails
        return BehaviorJudgment(
            passed=False,
            reasoning="Failed to parse LLM response",
            confidence=0.0,
        )

    return judge


# =============================================================================
# Event Store Fixtures
# =============================================================================

@pytest.fixture
def event_store(temp_village: Path):
    """Fresh EventStore for testing."""
    from engine.storage import EventStore
    return EventStore(temp_village)


@pytest.fixture
def initialized_event_store(event_store, test_village_snapshot):
    """EventStore initialized with test village."""
    event_store.initialize(test_village_snapshot)
    return event_store


# =============================================================================
# Auto-use Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def reset_registries():
    """
    Reset global registries between tests.

    This ensures test isolation when registries are modified.
    """
    # Currently no registries need resetting, but this is here
    # for future use if needed.
    yield
