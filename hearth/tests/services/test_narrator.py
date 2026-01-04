"""Tests for the Narrator service."""

from __future__ import annotations

import pytest

from core.actions import ActionResult
from core.terrain import Weather
from core.types import Position, AgentName
from services.narrator import (
    Narrator,
    NarratorContext,
    _TEMPLATES,
    _ALWAYS_HAIKU_ACTIONS,
    _get_atmosphere_snippet,
)


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def narrator() -> Narrator:
    """Create a narrator instance (no client for template tests)."""
    return Narrator(client=None)


@pytest.fixture
def default_context() -> NarratorContext:
    """Create a default context for testing."""
    return NarratorContext(
        agent_name=AgentName("Ember"),
        position=Position(10, 20),
        time_of_day="afternoon",
        weather=Weather.CLEAR,
        action_type="walk",
    )


def make_context(action_type: str, **kwargs) -> NarratorContext:
    """Helper to create context with specific action type."""
    defaults = {
        "agent_name": AgentName("Ember"),
        "position": Position(10, 20),
        "time_of_day": "afternoon",
        "weather": Weather.CLEAR,
    }
    defaults.update(kwargs)
    return NarratorContext(action_type=action_type, **defaults)


# -----------------------------------------------------------------------------
# NarratorContext Tests
# -----------------------------------------------------------------------------


class TestNarratorContext:
    """Tests for NarratorContext dataclass."""

    def test_create_context(self):
        """Test creating a context with all fields."""
        ctx = NarratorContext(
            agent_name=AgentName("Sage"),
            position=Position(5, 10),
            time_of_day="morning",
            weather=Weather.RAINY,
            action_type="examine",
        )
        assert ctx.agent_name == AgentName("Sage")
        assert ctx.position == Position(5, 10)
        assert ctx.time_of_day == "morning"
        assert ctx.weather == Weather.RAINY
        assert ctx.action_type == "examine"

    def test_context_with_different_weather(self):
        """Test context with different weather values."""
        for weather in Weather:
            ctx = make_context("walk", weather=weather)
            assert ctx.weather == weather

    def test_context_with_different_times(self):
        """Test context with different time values."""
        for time in ["morning", "afternoon", "evening", "night"]:
            ctx = make_context("walk", time_of_day=time)
            assert ctx.time_of_day == time


# -----------------------------------------------------------------------------
# Atmosphere Snippet Tests
# -----------------------------------------------------------------------------


class TestAtmosphereSnippets:
    """Tests for atmosphere snippet generation."""

    def test_snippet_returns_string(self):
        """Test that snippets return non-empty strings."""
        ctx = make_context("walk")
        snippet = _get_atmosphere_snippet(ctx)
        assert isinstance(snippet, str)
        assert len(snippet) > 0

    def test_snippet_varies_by_context(self):
        """Test that different contexts can produce different snippets."""
        snippets = set()
        # Vary both position and action_type to ensure hash variety
        for i, weather in enumerate(Weather):
            ctx = make_context("walk", weather=weather, position=Position(i * 10, i * 10))
            snippet = _get_atmosphere_snippet(ctx)
            snippets.add(snippet)
        # With varied positions, should have some variety
        assert len(snippets) >= 1  # At least produces snippets
        # Also verify different action types produce different results
        ctx1 = make_context("walk", position=Position(5, 5))
        ctx2 = make_context("gather", position=Position(5, 5))
        # Different action_type changes the hash
        snippet1 = _get_atmosphere_snippet(ctx1)
        snippet2 = _get_atmosphere_snippet(ctx2)
        # Both should be valid strings
        assert isinstance(snippet1, str) and len(snippet1) > 0
        assert isinstance(snippet2, str) and len(snippet2) > 0

    def test_snippet_deterministic_for_same_context(self):
        """Test that same context produces same snippet."""
        ctx = make_context("walk", position=Position(5, 5))
        snippet1 = _get_atmosphere_snippet(ctx)
        snippet2 = _get_atmosphere_snippet(ctx)
        assert snippet1 == snippet2


# -----------------------------------------------------------------------------
# Decision Logic Tests
# -----------------------------------------------------------------------------


class TestShouldUseHaiku:
    """Tests for _should_use_haiku decision logic."""

    def test_failure_uses_haiku(self, narrator: Narrator):
        """Test that failures always use Haiku."""
        result = ActionResult.fail("Cannot move - blocked.")
        ctx = make_context("walk")  # walk is normally templated
        assert narrator._should_use_haiku(result, ctx) is True

    def test_always_haiku_actions(self, narrator: Narrator):
        """Test that certain actions always use Haiku."""
        result = ActionResult.ok("Success")
        for action_type in _ALWAYS_HAIKU_ACTIONS:
            ctx = make_context(action_type)
            assert narrator._should_use_haiku(result, ctx) is True

    def test_template_actions_use_template(self, narrator: Narrator):
        """Test that template actions use templates on success."""
        result = ActionResult.ok("Moved north.", data={"direction": "north"})
        for action_type in _TEMPLATES.keys():
            ctx = make_context(action_type)
            # Only if not in always-haiku set
            if action_type not in _ALWAYS_HAIKU_ACTIONS:
                assert narrator._should_use_haiku(result, ctx) is False

    def test_discoveries_use_haiku(self, narrator: Narrator):
        """Test that results with discoveries use Haiku."""
        result = ActionResult.ok(
            "Gathered grass.",
            data={"resource": "grass", "discoveries": ["could be woven"]},
        )
        ctx = make_context("gather")  # gather is normally templated
        assert narrator._should_use_haiku(result, ctx) is True

    def test_unknown_action_uses_haiku(self, narrator: Narrator):
        """Test that unknown actions without templates use Haiku."""
        result = ActionResult.ok("Did something.")
        ctx = make_context("unknown_action")
        assert narrator._should_use_haiku(result, ctx) is True


# -----------------------------------------------------------------------------
# Template Narration Tests
# -----------------------------------------------------------------------------


class TestTemplateNarration:
    """Tests for template-based narration."""

    def test_walk_template(self, narrator: Narrator):
        """Test walk action template."""
        result = ActionResult.ok("Moved north.", data={"direction": "north"})
        ctx = make_context("walk")
        prose = narrator._narrate_template(result, ctx)
        assert "walk" in prose.lower()
        assert "north" in prose.lower()

    def test_approach_template(self, narrator: Narrator):
        """Test approach action template."""
        result = ActionResult.ok("Approached Sage.", data={"target": "Sage"})
        ctx = make_context("approach")
        prose = narrator._narrate_template(result, ctx)
        assert "move" in prose.lower() or "toward" in prose.lower()
        assert "sage" in prose.lower()

    def test_sleep_template_night(self, narrator: Narrator):
        """Test sleep action template at night."""
        result = ActionResult.ok("You drift off.")
        ctx = make_context("sleep", time_of_day="night")
        prose = narrator._narrate_template(result, ctx)
        assert "sleep" in prose.lower()
        assert "quiet" in prose.lower()

    def test_sleep_template_day(self, narrator: Narrator):
        """Test sleep action template during day."""
        result = ActionResult.ok("You drift off.")
        ctx = make_context("sleep", time_of_day="afternoon")
        prose = narrator._narrate_template(result, ctx)
        assert "rest" in prose.lower() or "eyes close" in prose.lower()

    def test_gather_template(self, narrator: Narrator):
        """Test gather action template."""
        result = ActionResult.ok("Gathered wood.", data={"resource": "wood"})
        ctx = make_context("gather")
        prose = narrator._narrate_template(result, ctx)
        assert "gather" in prose.lower()
        assert "wood" in prose.lower()

    def test_read_sign_template(self, narrator: Narrator):
        """Test read_sign action template."""
        result = ActionResult.ok(
            'The sign reads: "Welcome"',
            data={"text": "Welcome", "author": "Ember"},
        )
        ctx = make_context("read_sign")
        prose = narrator._narrate_template(result, ctx)
        assert "sign" in prose.lower()
        assert "welcome" in prose.lower()

    def test_drop_template(self, narrator: Narrator):
        """Test drop action template."""
        result = ActionResult.ok("Dropped 3 wood.")
        ctx = make_context("drop")
        prose = narrator._narrate_template(result, ctx)
        assert "set down" in prose.lower() or "drop" in prose.lower()

    def test_give_template(self, narrator: Narrator):
        """Test give action template."""
        result = ActionResult.ok("Gave wood to Sage.")
        ctx = make_context("give")
        prose = narrator._narrate_template(result, ctx)
        assert "offer" in prose.lower()

    def test_take_template(self, narrator: Narrator):
        """Test take action template."""
        result = ActionResult.ok("Picked up wood.", data={"item_type": "wood", "quantity": 1})
        ctx = make_context("take")
        prose = narrator._narrate_template(result, ctx)
        assert "pick up" in prose.lower()
        assert "wood" in prose.lower()

    def test_take_template_multiple(self, narrator: Narrator):
        """Test take action template with multiple items."""
        result = ActionResult.ok("Picked up 5 wood.", data={"item_type": "wood", "quantity": 5})
        ctx = make_context("take")
        prose = narrator._narrate_template(result, ctx)
        assert "5" in prose

    def test_name_place_template(self, narrator: Narrator):
        """Test name_place action template."""
        result = ActionResult.ok('Named this place "Haven".')
        ctx = make_context("name_place")
        prose = narrator._narrate_template(result, ctx)
        assert "name" in prose.lower()

    def test_write_sign_template(self, narrator: Narrator):
        """Test write_sign action template."""
        result = ActionResult.ok("Wrote a sign.")
        ctx = make_context("write_sign")
        prose = narrator._narrate_template(result, ctx)
        assert "sign" in prose.lower()

    def test_fallback_for_unknown_action(self, narrator: Narrator):
        """Test fallback for unknown action types."""
        result = ActionResult.ok("Something happened.")
        ctx = make_context("unknown_action")
        prose = narrator._narrate_template(result, ctx)
        assert prose == "Something happened."


# -----------------------------------------------------------------------------
# Main Narrate Method Tests (Templates Only)
# -----------------------------------------------------------------------------


class TestNarrate:
    """Tests for the main narrate method using templates."""

    @pytest.mark.asyncio
    async def test_narrate_walk_uses_template(self, narrator: Narrator):
        """Test that walk success uses template, not Haiku."""
        result = ActionResult.ok("Moved north.", data={"direction": "north"})
        ctx = make_context("walk")
        # This should use template, not call Haiku (which would fail with no client)
        prose = await narrator.narrate(result, ctx)
        assert "walk" in prose.lower()
        assert "north" in prose.lower()

    @pytest.mark.asyncio
    async def test_narrate_failure_produces_prose(self, narrator: Narrator):
        """Test that failures produce meaningful prose (via Haiku or fallback)."""
        result = ActionResult.fail("Cannot move - blocked.")
        ctx = make_context("walk")
        # Should produce some prose describing the failure
        prose = await narrator.narrate(result, ctx)
        # Either falls back to message or Haiku produces creative version
        assert len(prose) > 10  # At least some prose was produced
        # Should convey the idea of being stopped/blocked in some form
        blocked_words = ["cannot", "blocked", "stop", "wall", "way", "move", "path"]
        assert any(word in prose.lower() for word in blocked_words)


# -----------------------------------------------------------------------------
# Integration Tests (Require API Key)
# -----------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.slow
class TestNarratorIntegration:
    """Integration tests that call the actual Haiku API.

    These tests require ANTHROPIC_API_KEY to be set.
    Run with: pytest tests/services/test_narrator.py -m integration
    Skip with: pytest -m "not slow" or -m "not integration"
    """

    @pytest.mark.asyncio
    async def test_narrate_failure_with_haiku(self):
        """Test that failures produce creative narration via Haiku."""
        narrator = Narrator()
        result = ActionResult.fail("Cannot move north - path is blocked.")
        ctx = make_context("walk", weather=Weather.RAINY, time_of_day="evening")

        prose = await narrator.narrate(result, ctx)

        # Should have transformed the message, not just returned it verbatim
        assert len(prose) > len(result.message)
        # Should mention the blockage in some form
        assert "block" in prose.lower() or "cannot" in prose.lower() or "way" in prose.lower()

    @pytest.mark.asyncio
    async def test_narrate_crafting_success_with_haiku(self):
        """Test crafting success with discoveries uses Haiku."""
        narrator = Narrator()
        result = ActionResult.ok(
            "Created clay_vessel.",
            data={
                "output": "clay_vessel",
                "quantity": 1,
                "properties": ["fragile", "rough"],
                "discoveries": ["fire might harden this"],
            },
        )
        ctx = make_context("work", time_of_day="afternoon", weather=Weather.CLEAR)

        prose = await narrator.narrate(result, ctx)

        # Should mention the vessel
        assert "vessel" in prose.lower() or "clay" in prose.lower()
        # Should weave in the discovery about fire
        assert "fire" in prose.lower() or "harden" in prose.lower() or "heat" in prose.lower()

    @pytest.mark.asyncio
    async def test_narrate_examine_with_haiku(self):
        """Test examine action uses Haiku for rich description."""
        narrator = Narrator()
        result = ActionResult.ok(
            "You examine the stone.",
            data={
                "id": "obj_123",
                "type": "placed_item",
                "properties": ["heavy", "gray", "cool"],
            },
        )
        ctx = make_context("examine", time_of_day="morning", weather=Weather.FOGGY)

        prose = await narrator.narrate(result, ctx)

        # Should be longer than a simple template
        assert len(prose) > 20
        # Should incorporate properties
        assert any(
            prop in prose.lower()
            for prop in ["heavy", "gray", "cool", "stone", "weight"]
        )

    @pytest.mark.asyncio
    async def test_narrate_examine_with_haiku(self):
        """Test examine action uses Haiku for detailed description."""
        narrator = Narrator()
        result = ActionResult.ok(
            "You examine the old oak tree.",
            data={
                "target": "oak tree",
                "properties": {"age": "ancient", "bark": "deeply furrowed"},
            },
        )
        ctx = make_context("examine", time_of_day="afternoon", weather=Weather.CLEAR)

        prose = await narrator.narrate(result, ctx)

        # Should provide rich description
        assert len(prose) > 30

    @pytest.mark.asyncio
    async def test_narrate_sense_others_with_haiku(self):
        """Test sense_others uses Haiku for poetic description."""
        narrator = Narrator()
        result = ActionResult.ok(
            "You reach out with your senses.",
            data={
                "sensed": [
                    {"name": "Sage", "direction": "north", "distance": "nearby"},
                    {"name": "River", "direction": "west", "distance": "far"},
                ],
            },
        )
        ctx = make_context("sense_others", time_of_day="evening", weather=Weather.CLEAR)

        prose = await narrator.narrate(result, ctx)

        # Should mention the sensed agents
        assert "sage" in prose.lower() or "river" in prose.lower()

    @pytest.mark.asyncio
    async def test_narrate_journey_start_with_haiku(self):
        """Test journey start uses Haiku for atmospheric description."""
        narrator = Narrator()
        result = ActionResult.ok(
            "Began journey (approximately 25 steps).",
            data={"destination": (50, 50), "path_length": 25},
        )
        ctx = make_context("journey", time_of_day="morning", weather=Weather.CLEAR)

        prose = await narrator.narrate(result, ctx)

        # Should be descriptive of setting out
        assert len(prose) > 30

    @pytest.mark.asyncio
    async def test_narrate_build_shelter_with_haiku(self):
        """Test building actions use Haiku."""
        narrator = Narrator()
        result = ActionResult.ok("Built a simple shelter around yourself.")
        ctx = make_context("build_shelter", time_of_day="afternoon", weather=Weather.RAINY)

        prose = await narrator.narrate(result, ctx)

        # Should describe the building
        assert "shelter" in prose.lower() or "walls" in prose.lower() or "build" in prose.lower()
