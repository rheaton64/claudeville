"""
ClaudeVille Engine v2 - Event-sourced simulation engine.

This is the complete rewrite of the ClaudeVille engine with:
- Event sourcing for crash recovery
- Explicit conversation invitations
- Phase-based tick pipeline
- Scalable architecture for 10+ agents

Main entry points:
- VillageEngine: The main facade class
- ObserverAPI: Human interface for TUI/CLI

Example usage:
    from engine import VillageEngine
    from engine.adapters import ClaudeProvider

    engine = VillageEngine(
        village_root="village",
        llm_provider=ClaudeProvider(),
    )
    engine.recover()
    result = await engine.tick_once()
"""
import warnings

# Suppress langsmith deprecation warning about moved module
warnings.filterwarnings(
    "ignore",
    message="langsmith.wrappers._openai_agents is deprecated",
    category=DeprecationWarning,
)

from langsmith.integrations.claude_agent_sdk import configure_claude_agent_sdk

# Configure LangSmith tracing for Claude Agent SDK (village agents)
configure_claude_agent_sdk()

from .engine import VillageEngine
from .runner import EngineRunner
from .observer import ObserverAPI, ObserverError
from .logging_config import setup_logging

__all__ = [
    "VillageEngine",
    "EngineRunner",
    "ObserverAPI",
    "ObserverError",
    "setup_logging",
]
