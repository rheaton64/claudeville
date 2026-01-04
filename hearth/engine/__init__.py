"""Simulation engine for Hearth.

The engine orchestrates the tick pipeline:
1. WakePhase - Wake sleeping agents
2. SchedulePhase - Compute clusters and execution order
3. MovementPhase - Advance journeys
4. AgentTurnPhase - Execute agent turns
5. CommitPhase - Persist events to storage
"""

import warnings

# Suppress langsmith deprecation warning about moved module
warnings.filterwarnings(
    "ignore",
    message="langsmith.wrappers._openai_agents is deprecated",
    category=DeprecationWarning,
)

# Suppress langsmith Pydantic V1 warning on Python 3.14+
warnings.filterwarnings(
    "ignore",
    message="Core Pydantic V1 functionality isn't compatible with Python 3.14",
    category=UserWarning,
)

from langsmith.integrations.claude_agent_sdk import configure_claude_agent_sdk

# Configure LangSmith tracing for Claude Agent SDK (hearth agents)
configure_claude_agent_sdk()

from .context import TickContext, TurnResult
from .engine import HearthEngine
from .runner import EngineRunner
from .phases import (
    Phase,
    TickPipeline,
    WakePhase,
    SchedulePhase,
    MovementPhase,
    AgentTurnPhase,
    CommitPhase,
)

__all__ = [
    # Context
    "TickContext",
    "TurnResult",
    # Engine
    "HearthEngine",
    "EngineRunner",
    # Phases
    "Phase",
    "TickPipeline",
    "WakePhase",
    "SchedulePhase",
    "MovementPhase",
    "AgentTurnPhase",
    "CommitPhase",
]
