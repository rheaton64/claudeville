"""Narrator service for Hearth.

Transforms structured ActionResults into atmospheric prose.
Uses a hybrid approach: templates for simple actions, Haiku for complex ones.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

import anthropic
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from core.terrain import Weather
from core.types import Position, AgentName
from core.actions import ActionResult
from .action_engine import serialize_for_narrator

if TYPE_CHECKING:
    pass


# -----------------------------------------------------------------------------
# Context
# -----------------------------------------------------------------------------


@dataclass
class NarratorContext:
    """Minimal context for atmospheric narration.

    Designed to be extensible - add fields as needed for richer descriptions.
    """

    agent_name: AgentName
    position: Position
    time_of_day: str  # "morning", "afternoon", "evening", "night"
    weather: Weather
    action_type: str  # The action that was executed

    # Future extensions (uncomment when needed):
    # terrain: Terrain | None = None
    # nearby_agents: list[str] = field(default_factory=list)


# -----------------------------------------------------------------------------
# Prompts
# -----------------------------------------------------------------------------


NARRATOR_SYSTEM_PROMPT = """You are the voice of Hearth—a world that speaks back to those who live in it.

When an agent acts, you describe what happens. Not as a game narrator, but as the world itself responding. The agent should feel like they're *here*, not operating a system.

Your task:
- Transform the action result into prose the agent will read
- Preserve all important information (what worked, what didn't, quantities, properties, discoveries)
- Let time and weather color the telling
- For failures: be gentle—explain what happened, maybe hint at what might work
- For discoveries: weave them in naturally ("you notice...", "something about it makes you wonder...")
- Keep it brief: 2-4 sentences usually

Speak in second person. "You walk north. The morning light catches the dew."

Weather: {weather}
Time: {time_of_day}"""


def _build_user_prompt(result: ActionResult, ctx: NarratorContext) -> str:
    """Build the user prompt for Haiku narration."""
    # Serialize data to handle Position objects before JSON encoding
    serialized_data = serialize_for_narrator(result.data)
    data_str = json.dumps(serialized_data, indent=2) if serialized_data else "none"
    return f"""Action: {ctx.action_type}
Succeeded: {"yes" if result.success else "no"}
Result: {result.message}
Details: {data_str}

Narrate this for the agent."""


# -----------------------------------------------------------------------------
# Atmosphere Helpers
# -----------------------------------------------------------------------------


def _get_atmosphere_snippet(ctx: NarratorContext) -> str:
    """Get a short atmospheric snippet based on context."""
    # Weather-based snippets
    weather_snippets = {
        Weather.CLEAR: [
            "The air is clear and still.",
            "Light falls clean on everything.",
            "A gentle warmth.",
        ],
        Weather.CLOUDY: [
            "Clouds drift overhead.",
            "The light is soft, diffuse.",
            "A gray quiet.",
        ],
        Weather.RAINY: [
            "Rain patters softly around you.",
            "The sound of water, everywhere.",
            "Everything smells wet and alive.",
        ],
        Weather.FOGGY: [
            "Mist curls at the edges.",
            "The fog softens every shape.",
            "A hazy stillness.",
        ],
    }

    # Time-based snippets
    time_snippets = {
        "morning": [
            "The morning is fresh.",
            "New light on everything.",
            "The day is just beginning.",
        ],
        "afternoon": [
            "The afternoon stretches on.",
            "Warmth in the air.",
            "The day at its fullest.",
        ],
        "evening": [
            "Evening light goes golden.",
            "Shadows lengthen slowly.",
            "The day winding down.",
        ],
        "night": [
            "Night holds everything.",
            "Stars, if you look up.",
            "Quiet darkness.",
        ],
    }

    # Use a simple hash to pick consistently but with variety
    hash_val = hash((ctx.position, ctx.action_type)) % 3

    weather_options = weather_snippets.get(ctx.weather, [""])
    time_options = time_snippets.get(ctx.time_of_day, [""])

    # Alternate between weather and time snippets
    if hash_val == 0:
        return weather_options[hash_val % len(weather_options)]
    else:
        return time_options[hash_val % len(time_options)]


# -----------------------------------------------------------------------------
# Template Functions
# -----------------------------------------------------------------------------

# Type alias for template functions
TemplateFunc = Callable[[ActionResult, NarratorContext], str]


def _template_walk(result: ActionResult, ctx: NarratorContext) -> str:
    """Template for successful walk action."""
    direction = result.data.get("direction", "forward") if result.data else "forward"
    atmosphere = _get_atmosphere_snippet(ctx)
    return f"You walk {direction}. {atmosphere}"


def _template_approach(result: ActionResult, ctx: NarratorContext) -> str:
    """Template for successful approach action."""
    target = result.data.get("target", "your destination") if result.data else "your destination"
    atmosphere = _get_atmosphere_snippet(ctx)
    return f"You move closer to {target}. {atmosphere}"


def _template_sleep(result: ActionResult, ctx: NarratorContext) -> str:
    """Template for sleep action."""
    if ctx.time_of_day == "night":
        return "You settle in. Sleep comes, and the world grows quiet."
    return "You let your eyes close. Rest finds you easily."


def _template_gather(result: ActionResult, ctx: NarratorContext) -> str:
    """Template for successful gather action."""
    resource = result.data.get("resource", "materials") if result.data else "materials"
    atmosphere = _get_atmosphere_snippet(ctx)
    return f"You gather {resource} from what's here. {atmosphere}"


def _template_read_sign(result: ActionResult, ctx: NarratorContext) -> str:
    """Template for successful read_sign action."""
    text = result.data.get("text", "") if result.data else ""
    if text:
        return f'The sign reads: "{text}"'
    return "You read the sign."


def _template_drop(result: ActionResult, ctx: NarratorContext) -> str:
    """Template for successful drop action."""
    # Extract from message since it includes quantity
    base = result.message.replace("Dropped", "You set down")
    return f"{base} It stays where you leave it."


def _template_give(result: ActionResult, ctx: NarratorContext) -> str:
    """Template for successful give action."""
    # Message already formatted nicely
    base = result.message.replace("Gave", "You offer")
    return f"{base} They take it."


def _template_take(result: ActionResult, ctx: NarratorContext) -> str:
    """Template for successful take action."""
    item_type = result.data.get("item_type", "item") if result.data else "item"
    quantity = result.data.get("quantity", 1) if result.data else 1
    if quantity > 1:
        return f"You pick up {quantity} {item_type}. They're yours now."
    return f"You pick up the {item_type}. It's yours now."


def _template_name_place(result: ActionResult, ctx: NarratorContext) -> str:
    """Template for successful name_place action."""
    # Message is already good: 'Named this place "X".'
    base = result.message.replace("Named this place", "You name this place")
    return f"{base} The name settles into place."


def _template_write_sign(result: ActionResult, ctx: NarratorContext) -> str:
    """Template for successful write_sign action."""
    return "You write a sign and leave it here for others to find."


def _template_speak(result: ActionResult, ctx: NarratorContext) -> str:
    """Template for speak action."""
    message = result.data.get("message", "") if result.data else ""
    if message:
        return f'You say: "{message}"'
    return "You speak."


def _template_invite(result: ActionResult, ctx: NarratorContext) -> str:
    """Template for invite action."""
    invitee = result.data.get("invitee", "them") if result.data else "them"
    privacy = result.data.get("privacy", "public") if result.data else "public"
    if privacy == "private":
        return f"You reach toward {invitee}, inviting them to speak privately."
    return f"You reach toward {invitee}, inviting them to talk."


def _template_decline_invite(result: ActionResult, ctx: NarratorContext) -> str:
    """Template for decline_invite action."""
    inviter = result.data.get("inviter", "them") if result.data else "them"
    return f"You let {inviter} know you can't talk right now."


def _template_leave_conversation(result: ActionResult, ctx: NarratorContext) -> str:
    """Template for leave_conversation action."""
    return "You step away from the conversation."


# Registry of template functions
_TEMPLATES: dict[str, TemplateFunc] = {
    "walk": _template_walk,
    "approach": _template_approach,
    "sleep": _template_sleep,
    "gather": _template_gather,
    "read_sign": _template_read_sign,
    "drop": _template_drop,
    "give": _template_give,
    "take": _template_take,
    "name_place": _template_name_place,
    "write_sign": _template_write_sign,
    # Conversation actions
    "speak": _template_speak,
    "invite": _template_invite,
    "decline_invite": _template_decline_invite,
    "leave_conversation": _template_leave_conversation,
}


# Actions that always use Haiku (even on success)
_ALWAYS_HAIKU_ACTIONS = frozenset({
    "combine",
    "work",
    "apply",
    "examine",
    "journey",
    "sense_others",
    "build_shelter",
    "place_wall",
    "place_door",
    "place_item",
    "remove_wall",
    # Conversation (significant moments deserve atmospheric prose)
    "accept_invite",
    "join_conversation",
})


# -----------------------------------------------------------------------------
# Narrator Service
# -----------------------------------------------------------------------------


class Narrator:
    """Transforms ActionResults into atmospheric prose.

    Uses a hybrid approach:
    - Templates for simple, common actions (fast, free)
    - Haiku LLM for complex actions (atmospheric, creative)
    """

    def __init__(
        self,
        client: anthropic.AsyncAnthropic | None = None,
        model: str = "claude-haiku-4-5-20251001",
    ):
        """Initialize Narrator.

        Args:
            client: Anthropic client (lazy-initialized if None)
            model: Model to use for Haiku narration
        """
        self._client = client
        self._model = model

    async def narrate(
        self,
        result: ActionResult,
        context: NarratorContext,
    ) -> str:
        """Transform an action result into atmospheric prose.

        Args:
            result: The ActionResult from ActionEngine
            context: Narrator context with atmosphere info

        Returns:
            Atmospheric prose describing the action
        """
        if self._should_use_haiku(result, context):
            try:
                return await self._narrate_haiku(result, context)
            except Exception:
                # Fall back to message on API failure
                return self._fallback_narration(result, context)
        return self._narrate_template(result, context)

    def _should_use_haiku(self, result: ActionResult, ctx: NarratorContext) -> bool:
        """Decide whether to use Haiku or a template.

        Uses Haiku for:
        - Any failure (need creative explanation)
        - Actions in _ALWAYS_HAIKU_ACTIONS
        - Actions with discoveries in data
        """
        # Failures always use Haiku for creative explanation
        if not result.success:
            return True

        # Some actions always use Haiku
        if ctx.action_type in _ALWAYS_HAIKU_ACTIONS:
            return True

        # Actions with discoveries use Haiku to weave hints
        if result.data and result.data.get("discoveries"):
            return True

        # Otherwise use template if available
        return ctx.action_type not in _TEMPLATES

    def _narrate_template(self, result: ActionResult, ctx: NarratorContext) -> str:
        """Narrate using a template function."""
        template = _TEMPLATES.get(ctx.action_type)
        if template:
            return template(result, ctx)
        # Fallback for unknown action types
        return self._fallback_narration(result, ctx)

    def _fallback_narration(self, result: ActionResult, ctx: NarratorContext) -> str:
        """Simple fallback when template/Haiku unavailable."""
        if result.success:
            return result.message
        return f"{result.message}"

    async def _narrate_haiku(self, result: ActionResult, ctx: NarratorContext) -> str:
        """Narrate using Haiku LLM for atmospheric prose."""
        if self._client is None:
            self._client = anthropic.AsyncAnthropic()

        system_prompt = NARRATOR_SYSTEM_PROMPT.format(
            weather=ctx.weather.value,
            time_of_day=ctx.time_of_day,
        )
        user_prompt = _build_user_prompt(result, ctx)

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=256,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        # Extract text from response
        if response.content and len(response.content) > 0:
            return response.content[0].text
        return self._fallback_narration(result, ctx)
