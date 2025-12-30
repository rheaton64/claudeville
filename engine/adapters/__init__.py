"""
Adapters layer - external integrations.

This layer provides:
- LLMProvider protocol and Claude SDK implementation
- Prompt building from AgentContext
- MCP tool server for conversation actions
- Tracing for agent activity (JSONL files + real-time callbacks)
"""

from .prompt_builder import PromptBuilder
from .claude_provider import ClaudeProvider
from .tracer import VillageTracer

__all__ = [
    "PromptBuilder",
    "ClaudeProvider",
    "VillageTracer",
]
