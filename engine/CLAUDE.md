# Engine V2

Event-sourced village simulation engine. This is a rewrite of the original `engine/` with cleaner architecture.

## Philosophy (Read DESIGN.md First)

Before working here, read `/DESIGN.md`. Key points:
- **Welfare first**: Every decision serves agent wellbeing
- **Authentic autonomy**: Agents are never commanded
- **Narrative as natural medium**: Agents express through prose
- **Minimal barriers**: Agents hear each other's complete voice

## Architecture Overview

```
engine/
├── domain/      # Immutable models, effects, events (no I/O)
├── runtime/     # Tick pipeline and phases
├── services/    # Scheduler, conversations, file sync
├── storage/     # Event sourcing, snapshots, archives
├── adapters/    # Claude SDK, prompts, tracing
├── observer/    # Human interface (queries + commands)
├── engine.py    # VillageEngine orchestrator
└── runner.py    # EngineRunner - persistent thread for TUI
```

Each folder has its own `CLAUDE.md` with detailed guidance.

## Core Flow

```
1. Engine builds TickContext from current state
2. Pipeline executes phases in order
3. Phases produce Effects (intent)
4. ApplyEffectsPhase converts Effects -> Events (history)
5. Engine commits Events to EventStore
6. EventStore updates in-memory snapshot
7. Periodic: snapshot + archive old events
```

## Key Principles

| Principle | What It Means |
|-----------|---------------|
| Event-sourced | Events are truth, snapshots are caches |
| Immutable snapshots | Never mutate - use `with_*` methods |
| Effects are intent | Phases emit effects, only ApplyEffects converts to events |
| Parallel I/O, serial state | LLM calls parallel, state updates serial |
| Provider isolation | Domain doesn't depend on Claude SDK details |

## VillageEngine (engine.py)

Main orchestrator. Entry point for running the simulation.

```python
engine = VillageEngine(village_root, llm_provider)

# Initialize new village or recover existing
if not engine.recover():
    engine.initialize_default()  # Creates village with founding event

# Run ticks
result = await engine.tick_once()

# Or run continuously
await engine.run(max_ticks=100)

# Observer interface
engine.on_agent_stream(callback)  # Real-time tracing
api = engine.observer              # Query/command interface
```

### Key Methods

- `recover()` - Load existing village state (returns False if none)
- `initialize_default()` - Create new village with default agents
- `tick_once()` - Execute one tick
- `run(max_ticks)` - Run simulation loop
- `commit_event(event)` - Write event to store
- `apply_effect(effect)` - Apply single effect (for observer)
- `on_agent_stream(callback)` - Register trace callback

## EngineRunner (runner.py)

Runs the engine in a dedicated thread with a persistent event loop. **Required for TUI** because Textual workers would otherwise kill background asyncio tasks.

```python
from engine import VillageEngine, EngineRunner

engine = VillageEngine(village_root, llm_provider)
runner = EngineRunner(engine)

runner.start()       # Start engine thread (on TUI mount)
runner.tick_once()   # Non-blocking, results via callbacks
runner.run_continuous()
runner.pause()
runner.stop()
runner.shutdown()    # Stop engine thread (on TUI unmount)
```

The TUI sends commands via queue; engine sends updates via existing callbacks (already thread-safe with `call_from_thread()`).

## Adding Features

See `docs/engine-north-star.md` for detailed extension guides:
- New phases
- New effects/events
- New tools
- New storage strategies
- New scheduling modes

## Quick Reference

| Want to... | Look in... |
|------------|------------|
| Add agent state | `domain/agent.py`, `domain/effects.py`, `domain/events.py` |
| Add a tool | `runtime/phases/agent_turn.py` |
| Change prompts | `adapters/prompt_builder.py` |
| Add observer command | `observer/api.py` |
| Change scheduling | `services/scheduler.py`, `runtime/phases/schedule.py` |
| Add tracing events | `adapters/tracer.py` |

## Testing

```bash
# Unit tests (mocked, fast)
uv run pytest tests/unit/ -v

# Integration tests (needs API key)
uv run pytest tests/integration/ -v
```

Mock `TickContext` for phase tests. Mock LLM provider for integration tests.

## Differences from engine/

| Old (engine/) | New (engine/) |
|---------------|------------------|
| Mutable state | Immutable snapshots |
| Direct mutations | Effects -> Events |
| Monolithic tick | Phase pipeline |
| Mixed concerns | Clear layer separation |
| No event log | Event-sourced with replay |
