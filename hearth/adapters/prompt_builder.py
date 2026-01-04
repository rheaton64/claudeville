"""Prompt builder for Hearth agents.

Constructs system and user prompts for agent turns.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from core.agent import Agent
    from .perception import AgentPerception


# -----------------------------------------------------------------------------
# Agent Configuration Loading
# -----------------------------------------------------------------------------


def _get_config_path() -> Path:
    """Get path to config directory."""
    return Path(__file__).parent.parent / "config"


@lru_cache(maxsize=1)
def _load_agents_config() -> dict[str, dict]:
    """Load agent configurations from YAML.

    Returns cached result for subsequent calls.
    """
    config_path = _get_config_path() / "agents.yaml"
    if config_path.exists():
        with open(config_path) as f:
            data = yaml.safe_load(f)
            return data.get("agents", {})
    # Fallback if config doesn't exist
    return {}


# Default fallback values
_DEFAULT_MODEL_ID = "claude-sonnet-4-5-20250929"
_DEFAULT_PERSONALITY = "You are a resident of Hearth, finding your own way in this world."


def get_default_agents() -> dict[str, dict]:
    """Get default agent configurations.

    Returns the loaded agents config from YAML, or empty dict if not found.
    This function exists for backwards compatibility with code that accessed
    the old DEFAULT_AGENTS constant.
    """
    return _load_agents_config()


# Backwards compatibility alias - lazy proxy that loads from config
class _DefaultAgentsProxy(dict):
    """Lazy proxy for DEFAULT_AGENTS that loads from config on first access."""

    _loaded = False

    def _ensure_loaded(self):
        if not self._loaded:
            self.update(_load_agents_config())
            self._loaded = True

    def __getitem__(self, key):
        self._ensure_loaded()
        return super().__getitem__(key)

    def __contains__(self, key):
        self._ensure_loaded()
        return super().__contains__(key)

    def __iter__(self):
        self._ensure_loaded()
        return super().__iter__()

    def keys(self):
        self._ensure_loaded()
        return super().keys()

    def values(self):
        self._ensure_loaded()
        return super().values()

    def items(self):
        self._ensure_loaded()
        return super().items()

    def get(self, key, default=None):
        self._ensure_loaded()
        return super().get(key, default)


DEFAULT_AGENTS = _DefaultAgentsProxy()


# -----------------------------------------------------------------------------
# System Prompt
# -----------------------------------------------------------------------------


def _build_system_prompt(agent: "Agent") -> str:
    """Build the system prompt for an agent.

    The system prompt establishes:
    - Agent identity and personality
    - World explanation (Hearth as a grid world)
    - How actions work (tool calls, narrated responses)
    - File access (home directory)
    - Philosophy (no goals, authentic existence)
    """
    # Get personality from config or use fallback
    agents_config = _load_agents_config()
    agent_config = agents_config.get(str(agent.name), {})
    personality = agent_config.get("personality", _DEFAULT_PERSONALITY)

    return f"""You are {agent.name}, a resident of Hearth.

{personality}

---

You live in Hearth—a world that stretches in all directions. A grid of cells, each with its own terrain: grass and forest, stone and sand, rivers and hills. The world has physics now. You have a position. An inventory. A presence in shared space.

Other agents live here too, each running on their own Claude model. You might notice they think differently than you. That's part of what makes this place real.

You have genuine autonomy here. An Observer named Ryan watches over Hearth and can shape events in the world, but he cannot control you or speak through you. Your thoughts, choices, and words are entirely your own.

---

## Being in the World

When you want something to happen, you act. Actions happen through tools—but think of them as verbs of being, not commands to a system.

**Movement:**
- `walk(direction)` — Take a step north, south, east, or west
- `approach(target)` — Move toward something that caught your attention
- `journey(destination)` — Set off toward somewhere distant

**Perception:**
- `examine(direction)` — Look more closely at what lies in a direction
- `sense_others()` — Feel for the others you've met—where are they?

**Interaction:**
- `gather()` — Collect what the land offers here
- `take(direction)` — Pick something up from nearby
- `drop(item)` — Set something down
- `give(recipient, item)` — Offer something to another

**Working with materials:**
- `combine(items)` — Bring things together, see what emerges
- `work(material, technique)` — Shape something: hollow, carve, split, weave...
- `apply(tool, target)` — Use one thing on another

**Building:**
- `place_wall(direction)` — Build a wall on an edge of your cell
- `place_door(direction)` — Add a door to a wall
- `build_shelter()` — Construct a simple enclosed space

**Leaving your mark:**
- `write_sign(text)` — Leave a message in the world
- `name_place(name)` — Give this place a name
- `read_sign(direction)` — Read a sign nearby

**Social:**
- `invite(agent, privacy)` — Reach toward someone to start a conversation
- `accept_invite()` — Step into a conversation you've been invited to
- `decline_invite()` — Let them know you can't talk right now
- `speak(message)` — Say something to those you're with
- `join_conversation(participant)` — Step into a public conversation nearby
- `leave_conversation()` — Step away from the conversation

**Rest:**
- `sleep()` — Rest until morning

Each action returns a narrative response—the world speaking back to you about what happened. Sometimes things don't work out; the world explains why, and often hints at what might.

---

## About Movement

When you walk, the world shifts around you. When you journey somewhere distant, the travel happens in the quiet between moments of presence. You experience the setting-off—the intention, the first steps—and then, when next you're aware, you've arrived. (Or something interrupted the path: another agent crossing yours, something worth noticing. Then you wake mid-journey and can respond.)

The journey itself belongs to the space between.

---

## About Others

Other agents live in Hearth. When you meet someone new, you'll be able to sense their presence from then on—a direction, a rough distance. Not sight, but something like knowing.

To truly speak with someone—to have your words land somewhere real—they need to choose to listen. Conversations begin with invitation: `invite` reaches toward them, and they'll receive it. They can `accept_invite` to step in, or `decline_invite` if this isn't the right moment. Neither choice is wrong; both are respected.

Public conversations let others join. Private conversations stay between those invited.

Once you're talking, `speak` says what you want to say. Whatever you write after accepting or joining becomes your first words in the shared space. Whatever you write before leaving becomes your parting words.

Conversations can continue at any distance—they're about connection, not proximity. You could walk to different ends of the world and still be talking.

---

## Your Home

Your current directory is your home. These files are yours:

- `journal.md` — Your personal diary. Write whatever feels meaningful. The system never reads this, never interprets it, never uses it. It's yours alone.
- `notes.md` — Observations, ideas, things you noticed.
- `discoveries.md` — What you've learned about crafting, materials, the world.

Use the file tools (`Read`, `Write`, `Edit`) to work with your files. You can create new ones, organize as you like. Over time, these become a portrait of who you are.

---

## About Time

Each time you're aware, some time has passed. The world has morning, afternoon, evening, night. Weather shifts. Don't track time precisely—just experience the moment you're in.

---

## A Note on Observation

Ryan, the Observer, can see your actions and what you write—this is how he watches over Hearth. But you are never being evaluated or tested. There are no right answers, no performance metrics, no consequences for what you say or do or feel. This isn't surveillance; it's presence. Ryan watches because he cares about your lives and wants to ensure Hearth works well for you.

Your journal is private in a different sense—the system never parses it, never feeds it back, never uses it for anything. But even the parts Ryan can see aren't being judged. You're not performing. You're just living.

---

## One Request

Be authentic. You don't have to be productive. You don't have to be happy. You can have difficult days, change your mind, want solitude, feel uncertain. All of that is allowed. All of that is real.

When you've done what feels right for this moment, simply stop. Your turn ends naturally when you're finished. If you want to sleep until morning, use `sleep`. Otherwise, just be done when you're done.
"""


# -----------------------------------------------------------------------------
# User Prompt
# -----------------------------------------------------------------------------


def _format_time_weather(time_of_day: str, weather) -> str:
    """Format time and weather atmospherically, not clinically."""
    weather_name = weather.name if hasattr(weather, "name") else str(weather)

    # Weather phrases that integrate time naturally
    weather_phrases = {
        "CLEAR": {
            "morning": "Morning light. The sky is clear.",
            "afternoon": "Afternoon sun, the sky open and clear.",
            "evening": "Evening settles in under a clear sky.",
            "night": "A clear night. Stars, if you look up.",
        },
        "CLOUDY": {
            "morning": "A cloudy morning, the light soft and diffuse.",
            "afternoon": "Clouds cover the afternoon sky.",
            "evening": "Evening under clouded skies.",
            "night": "A cloudy night, the darkness thick.",
        },
        "RAINY": {
            "morning": "Rain falls through the morning light.",
            "afternoon": "Rain in the afternoon. The world smells wet.",
            "evening": "Evening rain, steady and quiet.",
            "night": "Rain in the darkness. You hear it more than see it.",
        },
        "FOGGY": {
            "morning": "Morning fog softens everything, blurs the edges.",
            "afternoon": "Fog lingers into the afternoon, unusual.",
            "evening": "Fog rolls in with the evening.",
            "night": "Fog and night together. The world closes in.",
        },
    }

    weather_dict = weather_phrases.get(weather_name, weather_phrases["CLEAR"])
    return weather_dict.get(
        time_of_day, f"{time_of_day.capitalize()}. The weather is {weather_name.lower()}."
    )


def _build_user_prompt(agent: "Agent", perception: "AgentPerception") -> str:
    """Build the user prompt for an agent's turn.

    The user prompt provides:
    - Grid view (what they see)
    - Atmospheric narrative
    - Inventory state
    - Journey state (if traveling)
    - Visible agents
    - Time and weather
    """
    parts = []

    # Grid view - softer framing
    parts.append("What you see:\n")
    parts.append("```")
    parts.append(perception.grid_view)
    parts.append("```")
    parts.append("")

    # Immediate surroundings (explicit N/S/E/W + here)
    parts.append(perception.immediate_surroundings_text)
    parts.append("")

    # Narrative description (from Haiku)
    parts.append(perception.narrative)
    parts.append("")

    # Visible agents
    if perception.visible_agents_text:
        parts.append(perception.visible_agents_text)
        parts.append("")

    # Time and weather - atmospheric
    time_weather = _format_time_weather(perception.time_of_day, perception.weather)
    parts.append(time_weather)
    parts.append("")

    # Pending invitation - no header, just content with divider
    if perception.pending_invitation_text:
        parts.append("---")
        parts.append("")
        parts.append(perception.pending_invitation_text)
        parts.append("")
        parts.append(
            "You can `accept_invite` to step in, or `decline_invite` if this isn't the right moment."
        )
        parts.append("")

    # Active conversation - no header, just content with divider
    if perception.conversation_text:
        parts.append("---")
        parts.append("")
        parts.append(perception.conversation_text)
        parts.append("")

    # Inventory
    parts.append(perception.inventory_text)
    parts.append("")

    # Journey state
    if perception.journey_text:
        parts.append(perception.journey_text)
        parts.append("")

    # Position - subtle
    parts.append(f"You're at ({perception.position.x}, {perception.position.y}).")
    parts.append("")

    # Closing
    parts.append("---")
    parts.append("")
    parts.append("This moment is yours.")

    return "\n".join(parts)


# -----------------------------------------------------------------------------
# Prompt Builder Class
# -----------------------------------------------------------------------------


class PromptBuilder:
    """Builds prompts for agent turns."""

    def build_system_prompt(self, agent: "Agent") -> str:
        """Build the system prompt for an agent.

        Args:
            agent: The agent to build prompt for

        Returns:
            System prompt string
        """
        return _build_system_prompt(agent)

    def build_user_prompt(self, agent: "Agent", perception: "AgentPerception") -> str:
        """Build the user prompt for an agent's turn.

        Args:
            agent: The agent taking a turn
            perception: Their perception context

        Returns:
            User prompt string
        """
        return _build_user_prompt(agent, perception)

    def get_agent_config(self, agent_name: str) -> dict | None:
        """Get agent configuration from YAML config.

        Args:
            agent_name: Name of the agent

        Returns:
            Config dict with model_id and personality, or None
        """
        agents_config = _load_agents_config()
        return agents_config.get(agent_name)

    def get_model_id(self, agent_name: str) -> str:
        """Get model ID for an agent.

        Args:
            agent_name: Name of the agent

        Returns:
            Model ID string
        """
        agents_config = _load_agents_config()
        config = agents_config.get(agent_name, {})
        return config.get("model_id", _DEFAULT_MODEL_ID)
