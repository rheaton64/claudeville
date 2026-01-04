"""Unit tests for Hearth prompt builder."""

import pytest

from adapters.prompt_builder import PromptBuilder, DEFAULT_AGENTS
from core.types import Position, AgentName
from core.terrain import Weather
from core.agent import Agent, AgentModel, Inventory


@pytest.fixture
def prompt_builder():
    """Create a PromptBuilder instance."""
    return PromptBuilder()


@pytest.fixture
def ember_agent():
    """Create a test Ember agent."""
    return Agent(
        name=AgentName("Ember"),
        model=AgentModel(id="claude-sonnet-4-5-20250514", display_name="Claude Sonnet"),
        personality="Test personality",
        position=Position(100, 100),
    )


@pytest.fixture
def mock_perception():
    """Create a mock perception for testing."""
    from adapters.perception import AgentPerception

    return AgentPerception(
        grid_view="· · ·\n· @ ·\n· · ·",
        immediate_surroundings_text="One step north: open grass. One step south: open grass. One step east: open grass. One step west: open grass. Beneath you: open grass.",
        narrative="The morning sun warms the grassland.",
        inventory_text="You carry nothing.",
        journey_text=None,
        visible_agents_text="",
        time_of_day="morning",
        weather=Weather.CLEAR,
        position=Position(100, 100),
    )


class TestDefaultAgents:
    """Tests for hardcoded agent definitions."""

    def test_ember_exists(self):
        """Ember should be defined."""
        assert "Ember" in DEFAULT_AGENTS
        assert "personality" in DEFAULT_AGENTS["Ember"]
        assert "model_id" in DEFAULT_AGENTS["Ember"]

    def test_sage_exists(self):
        """Sage should be defined."""
        assert "Sage" in DEFAULT_AGENTS
        assert "personality" in DEFAULT_AGENTS["Sage"]
        assert "model_id" in DEFAULT_AGENTS["Sage"]

    def test_river_exists(self):
        """River should be defined."""
        assert "River" in DEFAULT_AGENTS
        assert "personality" in DEFAULT_AGENTS["River"]
        assert "model_id" in DEFAULT_AGENTS["River"]

    def test_sage_uses_opus(self):
        """Sage should use Opus model."""
        assert "opus" in DEFAULT_AGENTS["Sage"]["model_id"]

    def test_ember_uses_sonnet(self):
        """Ember should use Sonnet model."""
        assert "sonnet" in DEFAULT_AGENTS["Ember"]["model_id"]


class TestSystemPrompt:
    """Tests for system prompt generation."""

    def test_system_prompt_contains_agent_name(self, prompt_builder, ember_agent):
        """System prompt should contain agent's name."""
        prompt = prompt_builder.build_system_prompt(ember_agent)
        assert "Ember" in prompt

    def test_system_prompt_contains_world_explanation(self, prompt_builder, ember_agent):
        """System prompt should explain Hearth."""
        prompt = prompt_builder.build_system_prompt(ember_agent)
        assert "Hearth" in prompt
        assert "grid" in prompt.lower()

    def test_system_prompt_contains_action_instructions(self, prompt_builder, ember_agent):
        """System prompt should explain how to use tools."""
        prompt = prompt_builder.build_system_prompt(ember_agent)
        assert "walk" in prompt.lower()
        assert "gather" in prompt.lower()
        assert "examine" in prompt.lower()

    def test_system_prompt_mentions_file_access(self, prompt_builder, ember_agent):
        """System prompt should mention file access."""
        prompt = prompt_builder.build_system_prompt(ember_agent)
        assert "journal" in prompt.lower()
        assert "notes" in prompt.lower()

    def test_system_prompt_mentions_autonomy(self, prompt_builder, ember_agent):
        """System prompt should mention autonomy."""
        prompt = prompt_builder.build_system_prompt(ember_agent)
        assert "autonomy" in prompt.lower()

    def test_system_prompt_uses_hardcoded_personality(self, prompt_builder, ember_agent):
        """System prompt should use hardcoded personality for known agents."""
        prompt = prompt_builder.build_system_prompt(ember_agent)
        # Ember's personality mentions creation/craft
        assert "creation" in prompt.lower() or "craft" in prompt.lower()


class TestUserPrompt:
    """Tests for user prompt generation."""

    def test_user_prompt_contains_grid_view(self, prompt_builder, ember_agent, mock_perception):
        """User prompt should contain the grid view."""
        prompt = prompt_builder.build_user_prompt(ember_agent, mock_perception)
        assert mock_perception.grid_view in prompt

    def test_user_prompt_contains_narrative(self, prompt_builder, ember_agent, mock_perception):
        """User prompt should contain the narrative."""
        prompt = prompt_builder.build_user_prompt(ember_agent, mock_perception)
        assert mock_perception.narrative in prompt

    def test_user_prompt_contains_time_of_day(self, prompt_builder, ember_agent, mock_perception):
        """User prompt should mention time of day."""
        prompt = prompt_builder.build_user_prompt(ember_agent, mock_perception)
        assert "morning" in prompt.lower()

    def test_user_prompt_contains_weather(self, prompt_builder, ember_agent, mock_perception):
        """User prompt should mention weather."""
        prompt = prompt_builder.build_user_prompt(ember_agent, mock_perception)
        assert "clear" in prompt.lower()

    def test_user_prompt_contains_inventory(self, prompt_builder, ember_agent, mock_perception):
        """User prompt should contain inventory text."""
        prompt = prompt_builder.build_user_prompt(ember_agent, mock_perception)
        assert mock_perception.inventory_text in prompt

    def test_user_prompt_ends_with_moment_is_yours(self, prompt_builder, ember_agent, mock_perception):
        """User prompt should end with 'This moment is yours.'"""
        prompt = prompt_builder.build_user_prompt(ember_agent, mock_perception)
        assert "This moment is yours." in prompt

    def test_user_prompt_shows_position(self, prompt_builder, ember_agent, mock_perception):
        """User prompt should show position coordinates."""
        prompt = prompt_builder.build_user_prompt(ember_agent, mock_perception)
        assert "100" in prompt  # x coordinate
        assert "You're at" in prompt


class TestModelIdLookup:
    """Tests for model ID lookup."""

    def test_get_model_id_known_agent(self, prompt_builder):
        """Should return correct model ID for known agents."""
        assert prompt_builder.get_model_id("Ember") == DEFAULT_AGENTS["Ember"]["model_id"]
        assert prompt_builder.get_model_id("Sage") == DEFAULT_AGENTS["Sage"]["model_id"]
        assert prompt_builder.get_model_id("River") == DEFAULT_AGENTS["River"]["model_id"]

    def test_get_model_id_unknown_agent(self, prompt_builder):
        """Should return default model ID for unknown agents."""
        model_id = prompt_builder.get_model_id("UnknownAgent")
        assert "sonnet" in model_id  # Default is Sonnet

    def test_get_agent_config(self, prompt_builder):
        """Should return agent config for known agents."""
        config = prompt_builder.get_agent_config("Ember")
        assert config is not None
        assert "personality" in config
        assert "model_id" in config

    def test_get_agent_config_unknown(self, prompt_builder):
        """Should return None for unknown agents."""
        config = prompt_builder.get_agent_config("UnknownAgent")
        assert config is None
