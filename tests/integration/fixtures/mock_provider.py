"""
Mock LLM Provider for deterministic integration tests.

Implements the LLMProvider protocol with configurable narratives
and tool call behavior for predictable testing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from engine.domain import Effect
from engine.runtime.phases.agent_turn import (
    AgentContext,
    ToolContext,
    TurnResult,
    ConversationTool,
)

if TYPE_CHECKING:
    from engine.domain import AgentName


@dataclass
class ToolCallConfig:
    """Configuration for a scheduled tool call."""

    tool_name: str
    tool_input: dict


@dataclass
class MockLLMProvider:
    """
    Deterministic LLM provider for integration tests.

    Returns pre-configured narratives based on agent name.
    Can simulate tool calls with predictable behavior.

    Example:
        provider = MockLLMProvider()
        provider.set_narrative("Alice", "I walk to the garden.")
        provider.set_tool_call("Bob", "invite_to_conversation", {"invitee": "Alice"})

        # Later in test:
        result = await provider.execute_turn(context, tool_context, tools)
        assert "garden" in result.narrative
    """

    # Configured narratives per agent
    narratives: dict[str, str] = field(default_factory=dict)

    # Configured tool calls per agent (one per turn)
    tool_calls: dict[str, ToolCallConfig] = field(default_factory=dict)

    # Log of all execute_turn calls for verification
    call_log: list[AgentContext] = field(default_factory=list)

    # Log of all tool calls made
    tool_call_log: list[tuple[str, str, dict]] = field(default_factory=list)

    # Default narrative for unconfigured agents
    default_narrative: str = "{agent} quietly contemplates the day."

    async def execute_turn(
        self,
        agent_context: AgentContext,
        tool_context: ToolContext,
        tools: dict[str, ConversationTool],
        agent_dir: str | None = None,
    ) -> TurnResult:
        """
        Execute a mock agent turn.

        Returns configured narrative and processes any configured tool calls.
        """
        agent_name = agent_context.agent.name

        # Log the call
        self.call_log.append(agent_context)

        # Get narrative
        if agent_name in self.narratives:
            narrative = self.narratives[agent_name]
        else:
            narrative = self.default_narrative.format(agent=agent_name)

        # Process configured tool call if any
        effects: list[Effect] = []

        if agent_name in self.tool_calls:
            tool_config = self.tool_calls[agent_name]
            tool_name = tool_config.tool_name
            tool_input = tool_config.tool_input

            # Log tool call
            self.tool_call_log.append((agent_name, tool_name, tool_input))

            # Execute the tool processor if it exists
            tool = tools.get(tool_name)
            if tool and tool.processor:
                try:
                    new_effects = tool.processor(tool_input, tool_context)
                    effects.extend(new_effects)
                except Exception as e:
                    # Log but don't crash - mirrors real LLM behavior
                    import logging

                    logging.getLogger(__name__).warning(
                        f"Tool call failed for {agent_name}: {e}"
                    )

        return TurnResult(narrative=narrative, effects=effects)

    def set_narrative(self, agent: str, narrative: str) -> None:
        """Configure narrative for specific agent."""
        self.narratives[agent] = narrative

    def set_tool_call(
        self,
        agent: str,
        tool_name: str,
        tool_input: dict,
    ) -> None:
        """
        Configure agent to call a specific tool during their turn.

        The tool will be called with the provided input, and its
        processor will generate the appropriate effects.

        Args:
            agent: Agent name
            tool_name: Name of tool to call (e.g., "invite_to_conversation")
            tool_input: Input arguments for the tool
        """
        self.tool_calls[agent] = ToolCallConfig(
            tool_name=tool_name,
            tool_input=tool_input,
        )

    def clear_tool_call(self, agent: str) -> None:
        """Clear configured tool call for agent."""
        if agent in self.tool_calls:
            del self.tool_calls[agent]

    def clear_all(self) -> None:
        """Clear all configured narratives and tool calls."""
        self.narratives.clear()
        self.tool_calls.clear()
        self.call_log.clear()
        self.tool_call_log.clear()

    def get_calls_for_agent(self, agent: str) -> list[AgentContext]:
        """Get all execute_turn calls for a specific agent."""
        return [ctx for ctx in self.call_log if ctx.agent.name == agent]

    def get_last_context(self, agent: str) -> AgentContext | None:
        """Get the most recent context for an agent."""
        calls = self.get_calls_for_agent(agent)
        return calls[-1] if calls else None

    def was_called(self, agent: str) -> bool:
        """Check if execute_turn was called for this agent."""
        return any(ctx.agent.name == agent for ctx in self.call_log)

    def tool_was_called(self, agent: str, tool_name: str) -> bool:
        """Check if a specific tool was called by an agent."""
        return any(
            a == agent and t == tool_name
            for a, t, _ in self.tool_call_log
        )
