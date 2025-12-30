"""
Interpreter Registry - declarative registration of observation extractors.

The interpreter extracts OBSERVATIONS from agent narratives:
- Movement (where they went)
- Mood (emotional state)
- Actions (what they did)
- Sleep/rest state
- Group conversation flow suggestions

NOT included here (handled by agent tool calls):
- Conversation lifecycle (invite, accept, join, leave)
- Starting/ending conversations

This separation ensures agents have explicit control over conversation actions
while the interpreter handles implicit observations.
"""

from dataclasses import dataclass
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from .result import MutableTurnResult


@dataclass
class ObservationAction:
    """Definition of an interpreter observation action/tool."""

    name: str
    description: str
    input_schema: dict
    result_field: str  # Field name on MutableTurnResult
    is_list_field: bool = False  # Whether to append to a list
    is_bool_field: bool = False  # Whether to set True
    processor: Callable[[dict, "MutableTurnResult", "InterpreterContext"], None] | None = None


@dataclass
class InterpreterContext:
    """Context available to observation processors."""

    current_location: str
    available_paths: list[str]
    present_agents: list[str]


# Global registry of all observation actions
OBSERVATION_REGISTRY: dict[str, ObservationAction] = {}


def register_observation(
    name: str,
    description: str,
    input_schema: dict,
    result_field: str,
    is_list_field: bool = False,
    is_bool_field: bool = False,
    processor: Callable[[dict, "MutableTurnResult", InterpreterContext], None] | None = None,
) -> None:
    """
    Register a new observation action.

    Args:
        name: Tool name (e.g., "report_movement")
        description: Tool description for Claude
        input_schema: JSON schema for tool input
        result_field: Field on MutableTurnResult to populate
        is_list_field: If True, append to list field
        is_bool_field: If True, set field to True
        processor: Custom processor function (tool_input, result, context) -> None
    """
    OBSERVATION_REGISTRY[name] = ObservationAction(
        name=name,
        description=description,
        input_schema=input_schema,
        result_field=result_field,
        is_list_field=is_list_field,
        is_bool_field=is_bool_field,
        processor=processor,
    )


def get_interpreter_tools() -> list[dict]:
    """Generate tool definitions for Claude API from registry."""
    return [
        {
            "name": action.name,
            "description": action.description,
            "input_schema": action.input_schema,
        }
        for action in OBSERVATION_REGISTRY.values()
    ]


def get_tool_names() -> list[str]:
    """Get list of all registered tool names."""
    return list(OBSERVATION_REGISTRY.keys())


# =============================================================================
# Path Matching Helper
# =============================================================================


def match_destination(destination: str, available_paths: list[str]) -> str | None:
    """
    Match a destination string to available paths.

    Uses fuzzy matching: exact match, substring match, then word match.
    Returns the matched path or None.
    """
    if not destination or not available_paths:
        return None

    dest_lower = destination.lower().replace(" ", "_")

    # Exact or substring match
    for path in available_paths:
        if dest_lower in path.lower() or path.lower() in dest_lower:
            return path

    # Word-based partial match
    for path in available_paths:
        if any(word in path.lower() for word in dest_lower.split("_")):
            return path

    return None


# =============================================================================
# Custom Processors
# =============================================================================


def process_movement(
    tool_input: dict,
    result: "MutableTurnResult",
    context: InterpreterContext,
) -> None:
    """Process movement with path matching and arrival narrative tracking."""
    destination = tool_input.get("destination", "")
    matched = match_destination(destination, context.available_paths)
    if matched:
        result.movement = matched
        # Store where the "at destination" narrative begins
        arrival_start = tool_input.get("arrival_starts_with", "")
        if arrival_start:
            result.movement_narrative_start = arrival_start


def process_propose_move_together(
    tool_input: dict,
    result: "MutableTurnResult",
    context: InterpreterContext,
) -> None:
    """Process move-together proposal with path matching."""
    destination = tool_input.get("destination", "")
    matched = match_destination(destination, context.available_paths)
    if matched:
        result.proposes_moving_together = matched


def process_next_speaker(
    tool_input: dict,
    result: "MutableTurnResult",
    context: InterpreterContext,
) -> None:
    """Process next speaker suggestion for group conversations."""
    next_speaker = tool_input.get("next_speaker", "")
    if next_speaker and next_speaker in context.present_agents:
        result.suggested_next_speaker = next_speaker


# =============================================================================
# Register Standard Observations
# =============================================================================

register_observation(
    name="report_movement",
    description=(
        "Report that the agent moved to a different location. "
        "Only call this if they actually traveled somewhere, not just thought about it."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "destination": {
                "type": "string",
                "description": (
                    "The location they moved to. "
                    "Use the exact location ID from the available paths."
                ),
            },
            "arrival_starts_with": {
                "type": "string",
                "description": (
                    "The first 5-10 words of the FIRST sentence where the agent "
                    "arrives at or is acting in the new location. This marks where "
                    "the 'at destination' narrative begins."
                ),
            },
        },
        "required": ["destination", "arrival_starts_with"],
    },
    result_field="movement",
    processor=process_movement,
)

register_observation(
    name="report_mood",
    description=(
        "Report the emotional state you observed in the narrative. "
        "How does the agent seem to be feeling?"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "mood": {
                "type": "string",
                "description": (
                    "One or two words describing their emotional state "
                    "(e.g., 'contemplative', 'joyful', 'tired and peaceful')"
                ),
            },
        },
        "required": ["mood"],
    },
    result_field="mood_expressed",
)

register_observation(
    name="report_resting",
    description=(
        "Report that the agent is settling in, resting, or ending their turn. "
        "Call this if they seem to be winding down."
    ),
    input_schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
    result_field="wants_to_rest",
    is_bool_field=True,
)

register_observation(
    name="report_action",
    description=(
        "Report an activity or action the agent engaged in. "
        "You can call this multiple times for different actions. "
        "Use for any physical action: crafting, reading, gesturing, showing something, etc."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": (
                    "Brief description of what they did "
                    "(e.g., 'worked on the chair', 'showed the bench design', 'gestured toward the window')"
                ),
            },
        },
        "required": ["description"],
    },
    result_field="actions_described",
    is_list_field=True,
)

register_observation(
    name="report_propose_move_together",
    description=(
        "Report that the agent suggests moving together with their conversation partner(s) "
        "to a new location (e.g., 'Let's go to the library'). "
        "Use this instead of report_movement when they want to go TOGETHER."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "destination": {
                "type": "string",
                "description": (
                    "The location they want to go to together. "
                    "Use the exact location ID from available paths."
                ),
            },
        },
        "required": ["destination"],
    },
    result_field="proposes_moving_together",
    processor=process_propose_move_together,
)

register_observation(
    name="report_sleeping",
    description=(
        "Report that the agent is going to sleep. "
        "Use when they explicitly indicate settling in for sleep - not just resting. "
        "Sleep is deeper than rest."
    ),
    input_schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
    result_field="wants_to_sleep",
    is_bool_field=True,
)

register_observation(
    name="report_next_speaker",
    description=(
        "In a group conversation (3+ participants), suggest who should speak next "
        "based on the narrative. Use when the speaker addressed someone specifically, "
        "asked them a question, or the flow naturally leads to someone."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "next_speaker": {
                "type": "string",
                "description": "Name of the agent who should respond next",
            },
            "reason": {
                "type": "string",
                "description": (
                    "Brief reason (e.g., 'addressed them directly', "
                    "'asked them a question', 'topic relates to their expertise')"
                ),
            },
        },
        "required": ["next_speaker"],
    },
    result_field="suggested_next_speaker",
    processor=process_next_speaker,
)


# =============================================================================
# TUI Helpers
# =============================================================================


def get_tool_options_for_tui() -> list[tuple[str, str]]:
    """
    Get observation tool options formatted for TUI dropdown.

    Returns:
        List of (display_name, tool_name) tuples for use in Select widgets.
    """
    return [
        (action.name.replace("report_", "").replace("_", " ").title(), action.name)
        for action in OBSERVATION_REGISTRY.values()
    ]
