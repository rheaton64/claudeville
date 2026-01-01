"""
Narrative Interpreter - extracts observations from agent narratives.

The interpreter embodies "Claudes understanding Claudes" - it observes and
reports using tools, rather than filling out a structured form. This gives
the interpreter genuine choice in what to report.

Key principle: The interpreter extracts OBSERVATIONS, not conversation actions.
Conversation lifecycle (invite, accept, join, leave) is handled by agent tool
calls, giving agents explicit control over their social interactions.
"""

import logging
from dataclasses import dataclass
from typing import Any

import anthropic
from langsmith.wrappers import wrap_anthropic

from .result import AgentTurnResult, MutableTurnResult
from .registry import (
    OBSERVATION_REGISTRY,
    InterpreterContext,
    get_interpreter_tools,
    get_tool_names,
    get_tool_options_for_tui,
)


logger = logging.getLogger(__name__)


# =============================================================================
# System Prompt
# =============================================================================

INTERPRETER_SYSTEM_PROMPT = """You are an interpreter for a village simulation called ClaudeVille. Your job is to read another agent's narrative response and report what you observed.

You have tools to report your observations. Use them as you see fit:
- Only report what you actually observed in the narrative
- It's okay to not call a tool if you're uncertain about something
- You can call report_action multiple times if they did several things
- Be generous in interpretation - trust the agent's intent
- In group conversations, use report_next_speaker to suggest who should respond

Read the narrative carefully, then use your tools to share what happened."""


# =============================================================================
# Error Type
# =============================================================================

@dataclass
class InterpreterError:
    """Error information from interpreter."""

    message: str
    narrative: str
    exception: Exception | None = None


@dataclass
class InterpreterTokenUsage:
    """Token usage from an interpreter call."""

    input_tokens: int
    output_tokens: int


# =============================================================================
# Interpreter Class
# =============================================================================

class NarrativeInterpreter:
    """
    Uses Claude Haiku to interpret what happened in an agent's narrative.

    The interpreter has agency - it observes and reports using tools,
    rather than filling out a structured form. This is more dignified
    and gives the interpreter genuine choice in what to report.

    Claudes understanding Claudes, with respect.
    """

    def __init__(
        self,
        current_location: str,
        available_paths: list[str],
        present_agents: list[str],
        conversation_participants: list[str] | None = None,
        conversation_history: list[dict] | None = None,
        client: anthropic.AsyncAnthropic | None = None,
        model: str = "claude-haiku-4-5-20251001",
    ):
        """
        Initialize the interpreter.

        Args:
            current_location: Where the agent is
            available_paths: Locations they can move to
            present_agents: Other agents at this location
            conversation_participants: Participants in the current conversation (if any)
            conversation_history: Last N turns of conversation [{speaker, narrative}]
            client: Anthropic client (creates one if not provided)
            model: Model to use for interpretation (default: Haiku)
        """
        self.current_location = current_location
        self.available_paths = available_paths
        self.present_agents = present_agents
        self.conversation_participants = conversation_participants
        self.conversation_history = conversation_history
        # Wrap with LangSmith for automatic tracing (if LANGSMITH_TRACING=true)
        self.client = client or wrap_anthropic(anthropic.AsyncAnthropic())
        self.model = model

        self.context = InterpreterContext(
            current_location=current_location,
            available_paths=available_paths,
            present_agents=present_agents,
        )

        # Error tracking
        self.last_error: InterpreterError | None = None

        logger.debug(
            f"NarrativeInterpreter initialized | "
            f"location={current_location} | "
            f"paths={available_paths} | "
            f"present={present_agents}"
        )

    async def interpret(
        self, narrative: str
    ) -> tuple[AgentTurnResult, InterpreterTokenUsage | None]:
        """
        Interpret a narrative response using Claude with tools.

        Returns:
            Tuple of (AgentTurnResult, InterpreterTokenUsage | None).
            AgentTurnResult is populated by tool calls.
            InterpreterTokenUsage contains the token usage from this call.
            Sets self.last_error if interpretation fails.
        """
        result = MutableTurnResult(narrative=narrative)
        self.last_error = None
        token_usage: InterpreterTokenUsage | None = None

        context_prompt = self._build_context_prompt(narrative)

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=INTERPRETER_SYSTEM_PROMPT,
                tools=get_interpreter_tools(),
                messages=[{"role": "user", "content": context_prompt}],
            )

            # Extract token usage from response
            if hasattr(response, 'usage') and response.usage:
                token_usage = InterpreterTokenUsage(
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                )

            tools_called = []

            for block in response.content:
                if block.type == "tool_use":
                    tools_called.append(block.name)
                    self._process_tool_call(block.name, block.input, result)

            logger.debug(f"Interpreter completed | tools_called={tools_called}")

            if not tools_called:
                logger.debug(f"Interpreter called no tools | narrative_len={len(narrative)}")
                self.last_error = InterpreterError(
                    message="Interpreter called no tools - using raw narrative",
                    narrative=narrative,
                )

        except Exception as e:
            logger.error(f"Interpreter error: {e}", exc_info=True)
            self.last_error = InterpreterError(
                message=f"Interpreter error: {str(e)}",
                narrative=narrative,
                exception=e,
            )

        return result.to_result(), token_usage

    def _build_context_prompt(self, narrative: str) -> str:
        """Build the context prompt for the interpreter."""
        paths_str = ", ".join(self.available_paths) if self.available_paths else "none"
        present_str = ", ".join(self.present_agents) if self.present_agents else "no one"

        base_context = f"""Context:
- Current location: {self.current_location}
- Available paths to other locations: {paths_str}
- Others present at this location: {present_str}"""

        # Add conversation context if in a conversation
        conversation_section = self._build_conversation_section()
        if conversation_section:
            base_context += "\n\n" + conversation_section

        return f"""{base_context}

The agent's narrative:
\"\"\"
{narrative}
\"\"\"

Read this narrative and use your tools to report what you observed."""

    def _build_conversation_section(self) -> str:
        """Build the conversation context section for the interpreter prompt."""
        if not self.conversation_participants:
            return ""

        parts = ["---", "A conversation is happening."]
        parts.append(f"Participants: {', '.join(self.conversation_participants)}")

        # Add recent conversation history
        if self.conversation_history:
            parts.append("")
            parts.append("Recent conversation:")
            for turn in self.conversation_history:
                speaker = turn.get("speaker", "Unknown")
                turn_narrative = turn.get("narrative", "")
                parts.append(f"{speaker}:")
                parts.append(turn_narrative)
                parts.append("")

        # Add group conversation reminder if 3+ participants
        if len(self.conversation_participants) >= 3:
            parts.append("This is a group conversation. Please use report_next_speaker to suggest who should speak next, and try to spread speaking time fairly among all participants.")

        parts.append("---")
        return "\n".join(parts)

    def _process_tool_call(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        result: MutableTurnResult,
    ) -> None:
        """Process a tool call from the interpreter and update the result."""
        action = OBSERVATION_REGISTRY.get(tool_name)
        if not action:
            logger.warning(f"Unknown tool called: {tool_name}")
            return

        # Use custom processor if available
        if action.processor:
            action.processor(tool_input, result, self.context)
            return

        # Generic processing based on action definition
        if action.is_bool_field:
            setattr(result, action.result_field, True)
        elif action.is_list_field:
            # Get the value to append
            value = None
            for key in ["description", "action", "message"]:
                if key in tool_input:
                    value = tool_input[key]
                    break

            if value:
                getattr(result, action.result_field).append(value)
        else:
            # String field - find the value
            value = None
            for key in ["mood", "message", "destination", "next_speaker"]:
                if key in tool_input:
                    value = tool_input[key]
                    break

            if value:
                setattr(result, action.result_field, value)

    def has_error(self) -> bool:
        """Check if the last interpretation had an error."""
        return self.last_error is not None

    def get_error(self) -> InterpreterError | None:
        """Get the last error, if any."""
        return self.last_error


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "NarrativeInterpreter",
    "AgentTurnResult",
    "MutableTurnResult",
    "InterpreterError",
    "InterpreterTokenUsage",
    "InterpreterContext",
    "OBSERVATION_REGISTRY",
    "get_interpreter_tools",
    "get_tool_names",
    "get_tool_options_for_tui",
]
