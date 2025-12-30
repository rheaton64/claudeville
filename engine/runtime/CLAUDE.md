# Runtime Layer

Tick execution pipeline and phases. This is where the simulation loop lives.

## Core Concept: TickContext

Immutable context passed through phases. Each phase transforms it via `with_*` methods:

```python
ctx = ctx.with_effect(MoveAgentEffect(...))
ctx = ctx.with_agents_to_act(frozenset([agent_name]))
ctx = ctx.with_turn_result(agent_name, result)
```

**Never mutate context directly.** Always use `with_*` methods.

## Pipeline Architecture

```
TickContext -> [Phase1] -> [Phase2] -> ... -> TickResult
```

Phases execute in order. The default pipeline:

1. **WakeCheckPhase** - Wake sleeping agents if time period changed or visitor arrived
2. **SchedulePhase** - Determine `agents_to_act` from scheduled events
3. **AgentTurnPhase** - Execute LLM calls (parallel by agent)
4. **InterpretPhase** - Run Haiku interpreter on narratives (parallel)
5. **ApplyEffectsPhase** - Convert effects to events, update context (serial)

## Adding a New Phase

1. Create `engine/runtime/phases/my_phase.py`
2. Subclass `BasePhase`, implement `async _execute(self, ctx: TickContext) -> TickContext`
3. Export in `phases/__init__.py`
4. Add to pipeline in `VillageEngine._build_pipeline()`

```python
class MyPhase(BasePhase):
    async def _execute(self, ctx: TickContext) -> TickContext:
        # Do work, return new context
        return ctx.with_effect(SomeEffect(...))
```

## Key Files

### context.py
- `TickContext` - Immutable context with all state + accumulated effects/events
- `TickResult` - Final result extracted from context

### pipeline.py
- `Phase` - Protocol for phases
- `BasePhase` - Base class with logging/error handling
- `TickPipeline` - Orchestrates phase execution with metrics

### phases/

| Phase | Purpose | Parallel? |
|-------|---------|-----------|
| `wake_check.py` | Wake sleeping agents | No |
| `schedule.py` | Pick who acts | No |
| `agent_turn.py` | LLM calls + tools | Yes (by agent) |
| `interpret.py` | Haiku interpretation | Yes (by agent) |
| `apply_effects.py` | Effects -> Events | No (serial) |

### interpreter/

The NarrativeInterpreter extracts observations from agent narratives:

- `registry.py` - `OBSERVATION_REGISTRY` of interpreter tools
- `result.py` - `AgentTurnResult` with extracted observations
- `__init__.py` - `NarrativeInterpreter` class

Interpreter tools:
- `report_movement` - where they went
- `report_mood` - emotional state
- `report_action` - what they did (can call multiple times)
- `report_sleeping` - going to sleep
- `report_next_speaker` - suggests who speaks next in group

## Conversation Tools (agent_turn.py)

Tools agents can call during their turn:

```python
CONVERSATION_TOOL_REGISTRY = {
    "invite_to_conversation": ConversationTool(...),
    "accept_invite": ConversationTool(...),
    "decline_invite": ConversationTool(...),
    "join_conversation": ConversationTool(...),
    "leave_conversation": ConversationTool(...),
}
```

Each tool has a processor function that returns `list[Effect]`.

## Concurrency

- **AgentTurnPhase**: `asyncio.gather()` for parallel LLM calls
- **InterpretPhase**: `asyncio.gather()` for parallel interpretation
- **ApplyEffectsPhase**: Serial, deterministic order

This ensures parallel I/O but deterministic state updates.
