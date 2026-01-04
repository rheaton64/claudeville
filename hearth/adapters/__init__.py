"""External integrations for Hearth (LLM providers, etc.)."""

import warnings

# Suppress langsmith deprecation warning about moved module
warnings.filterwarnings(
    "ignore",
    message="langsmith.wrappers._openai_agents is deprecated",
    category=DeprecationWarning,
)

from langsmith.integrations.claude_agent_sdk import configure_claude_agent_sdk

# Configure LangSmith tracing for Claude Agent SDK (must run before creating clients)
configure_claude_agent_sdk()

from .perception import AgentPerception, PerceptionBuilder, get_time_of_day
from .claude_provider import HearthProvider, ProviderTurnResult, TurnTokenUsage
from .prompt_builder import PromptBuilder, DEFAULT_AGENTS
from .tracer import HearthTracer
from .tools import (
    HearthTool,
    HearthToolContext,
    AgentToolState,
    HEARTH_TOOL_REGISTRY,
    HEARTH_TOOL_NAMES,
    create_hearth_mcp_server,
)

__all__ = [
    # Perception
    "AgentPerception",
    "PerceptionBuilder",
    "get_time_of_day",
    # Provider
    "HearthProvider",
    "ProviderTurnResult",
    "TurnTokenUsage",
    # Prompts
    "PromptBuilder",
    "DEFAULT_AGENTS",
    # Tracing
    "HearthTracer",
    # Tools
    "HearthTool",
    "HearthToolContext",
    "AgentToolState",
    "HEARTH_TOOL_REGISTRY",
    "HEARTH_TOOL_NAMES",
    "create_hearth_mcp_server",
]
