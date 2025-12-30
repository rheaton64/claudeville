"""
Runtime layer - tick execution pipeline and phases.

The runtime layer orchestrates tick execution through a series of phases:

1. Context building (TickContext)
2. Phase execution (TickPipeline)
3. Result extraction (TickResult)

Each phase transforms the context, accumulating effects and events.
After all phases complete, the engine commits events to storage.
"""

from .context import TickContext, TickResult
from .pipeline import TickPipeline, Phase, BasePhase, PhaseError, PipelineMetrics
from .interpreter import (
    NarrativeInterpreter,
    AgentTurnResult,
    MutableTurnResult,
    InterpreterError,
    InterpreterContext,
    OBSERVATION_REGISTRY,
    get_interpreter_tools,
    get_tool_names,
)
from .phases import (
    WakeCheckPhase,
    SchedulePhase,
    AgentTurnPhase,
    InterpretPhase,
    ApplyEffectsPhase,
    LLMProvider,
    AgentContext,
    ToolContext,
    TurnResult,
    ConversationTool,
    CONVERSATION_TOOL_REGISTRY,
    get_conversation_tools,
    get_tool_processor,
    register_conversation_tool,
)

__all__ = [
    # Context
    "TickContext",
    "TickResult",
    # Pipeline
    "TickPipeline",
    "Phase",
    "BasePhase",
    "PhaseError",
    "PipelineMetrics",
    # Interpreter
    "NarrativeInterpreter",
    "AgentTurnResult",
    "MutableTurnResult",
    "InterpreterError",
    "InterpreterContext",
    "OBSERVATION_REGISTRY",
    "get_interpreter_tools",
    "get_tool_names",
    # Phases
    "WakeCheckPhase",
    "SchedulePhase",
    "AgentTurnPhase",
    "InterpretPhase",
    "ApplyEffectsPhase",
    # LLM types
    "LLMProvider",
    "AgentContext",
    "ToolContext",
    "TurnResult",
    "ConversationTool",
    "CONVERSATION_TOOL_REGISTRY",
    "get_conversation_tools",
    "get_tool_processor",
    "register_conversation_tool",
]
