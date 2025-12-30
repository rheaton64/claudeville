# Engine v2 North Star

This document captures the core design and architecture principles of the
current `engine` implementation, plus extension guides for the scalable
features we expect to keep evolving. Use this as the north star when adding
new behavior, providers, or storage changes.

## Core Principles

- Event-sourced state: `DomainEvent` is the source of truth. Snapshots are
  caches derived from events. Rebuild state by replaying events.
- Immutable domain snapshots: `AgentSnapshot`, `WorldSnapshot`, and
  `Conversation` are treated as frozen. All updates create new instances.
- Effects are intent: phases emit `Effect` objects; only ApplyEffects converts
  them into events and state updates.
- Narrow phase responsibilities: each phase is small and focused, and returns
  a new `TickContext`. Any heavy I/O is isolated to `AgentTurnPhase`.
- Deterministic updates after I/O: the system runs agent turns concurrently
  and then applies effects serially and deterministically.
- Provider isolation: LLM providers are adapters. Domain + runtime do not
  depend on provider internals or API details.
- Filesystem as persistence: the village directory is canonical storage for
  agent files and shared files; changes flow through services.
- Observer is add-only: Observer commands add events or effects, never rewrite
  agent output or conversation history.
- Global time is single source: scheduler sets due times; engine advances time
  to the next scheduled event and writes one `TimeSnapshot` per tick.
- Prompt philosophy is stable: agent prompts stay narrative, non-imperative,
  and end with "This moment is yours."

## System Shape (Current)

```
engine/domain     - immutable models, effects, events
engine/runtime    - TickContext + phase pipeline
engine/services   - scheduler, conversation service, shared files, bootstrap
engine/storage    - event log, snapshots, archives
engine/adapters   - Claude Agent SDK provider
engine/observer   - API + UI entry points
```

Pipeline order (engine default):
1) WakeCheckPhase
2) SchedulePhase
3) AgentTurnPhase (LLM + tools)
4) InterpretPhase
5) ApplyEffectsPhase

Event commit + snapshot/archive happens after the pipeline in the engine.

## Extension Guides (Core Scalable Features)

### 1) Phases / Tick Pipeline

When adding a new phase:
- Create a `BasePhase` subclass in `engine/runtime/phases`.
- Keep the phase focused and mostly pure (no I/O unless unavoidable).
- Use `TickContext.with_*` helpers; do not mutate snapshots in place.
- Wire it into `VillageEngine._build_pipeline()` in the desired order.
- If a phase needs services, pass them in via the constructor, not globals.

### 2) Effects + Events (State Updates)

When adding new state changes:
- Add a new Effect in `engine/domain/effects.py`.
- Add a matching DomainEvent in `engine/domain/events.py`.
- Export both in `engine/domain/__init__.py`.
- Convert effect -> event in `ApplyEffectsPhase` and update context.
- Update `EventStore._apply_event` so replay updates snapshots correctly.
- If snapshots change shape, update `VillageSnapshot` serialization.

### 3) Scheduler + Time Pacing

Current scheduler is event-driven using `ScheduledEvent` with:
`agent_turn`, `conversation_turn`, and `invite_response`.

To add a new scheduling mode:
- Extend `ScheduledEvent.event_type` and update indexes in `Scheduler`.
- Update `SchedulePhase` to translate scheduled events into `agents_to_act`.
- Seed the schedule in `VillageEngine._ensure_schedule()` (or service call).
- Ensure any new scheduling logic is time-based and uses `due_time`.

### 4) Conversations (Invites, Turns, Next Speaker)

Conversation state lives in `ConversationService` + events.

To add a new conversation behavior:
- Add the domain fields needed in `engine/domain/conversation.py`.
- Add effect(s) and event(s) for the behavior.
- Update `ApplyEffectsPhase` and `EventStore._apply_event`.
- If the behavior affects who speaks next, update `SchedulePhase`.
- If the behavior is agent-driven, add a conversation tool and prompt guidance.

### 5) Tools (Agent Actions)

Tools are registered in `AgentTurnPhase` and processed via tool handlers.

To add a new tool:
- Add a processor function that returns `Effect` objects.
- Register the tool in `AgentTurnPhase` using `register_conversation_tool`.
- Update `PromptBuilder` if the tool needs new agent-facing instructions.

### 6) Storage (Event Log + Snapshots)

EventStore is the single write path. Snapshots are created every 100 ticks.

To add new persistent fields or retention behavior:
- Extend domain models and update event replay in `EventStore._apply_event`.
- Update `VillageSnapshot.to_dict/from_dict` if new state is added.
- If you need a new archive strategy, implement it in `storage/archive.py` and
  call it from `EventStore.create_snapshot_and_archive()`.

### 7) Shared Files (Location-based)

Shared files are copied into `./shared/` per turn and synced back out.

To add new shared spaces or a new sync strategy:
- Update `LOCATION_SHARED_DIRS` in `services/shared_files.py`.
- Keep `sync_shared_files_in/out` as the only sync entry points.
- Update `PromptBuilder` if the agent needs new instructions.

### 8) LLM Providers (Adapters)

`LLMProvider` is the contract for agent turns.

To add a new provider:
- Implement `execute_turn()` to build prompts from `AgentContext`.
- Run tool processors through the registry and return effects.
- Keep provider-specific options (tools, permissions, cwd) inside the adapter.
- Keep the interface identical so the engine can swap providers.

### 9) Observer Commands

Observer actions must be add-only and event-driven.

To add a command:
- Implement it in `engine/observer/api.py`.
- Produce effects or domain events, then commit through the engine.
- Do not mutate agent state directly outside ApplyEffects / EventStore.

### 10) Agent Files (Dreams, Inbox, Workspace)

Agent files live under `village/agents/<name>/`.

To add a new agent file surface:
- Extend `ensure_agent_directory()` to create the new directory.
- Add a service module for read/write logic.
- Wire it into `AgentTurnPhase` + `PromptBuilder` if it affects context.
- Avoid mixing it into journal behavior unless explicitly intended.

### 11) Tracing (Real-time Streaming)

`VillageTracer` emits events for TUI streaming and debugging. Events are written
to per-agent JSONL files and streamed to registered callbacks.

Events: `turn_start`, `text`, `tool_use`, `tool_result`, `turn_end`,
`interpret_complete`.

To add new trace events:
- Add a method to `VillageTracer` in `engine/adapters/tracer.py`.
- Call it from the appropriate phase or provider.
- Update TUI handlers if the event needs display.
- Keep events lightweight; truncate large payloads.

### 12) Interpreter (Observation Extraction)

`NarrativeInterpreter` extracts structured observations from agent narratives
using Claude Haiku. It reports movement, mood, actions, sleep intent, and
conversation flow suggestions.

To add a new observation type:
- Add the field to `AgentTurnResult` in `engine/runtime/interpreter.py`.
- Add a tool definition in the interpreter's tool list.
- Update `InterpretPhase._observations_to_effects()` to convert to an Effect.
- Update `VillageTracer.log_interpret_complete()` if it should be traced.

## Concurrency Model

- **AgentTurnPhase**: Runs agent turns in parallel (one task per agent).
- **InterpretPhase**: Runs interpretation in parallel (one task per narrative).
- **ApplyEffectsPhase**: Strictly serial and deterministic. Effects are applied
  in a consistent order to ensure reproducible state.
- **Other phases**: Sequential, lightweight, no I/O.

This means: parallel I/O, serial state updates.

## Error Handling

Philosophy: log and continue. A single agent failure should not halt the tick.

- **LLM call fails**: Log error, skip that agent's turn, continue with others.
- **Interpretation fails**: Log warning, use empty observations, apply no effects.
- **Effect application fails**: Log error, skip that effect, continue pipeline.
- **Phase throws**: Catch at engine level, log, attempt graceful degradation.

Critical errors (storage corruption, missing snapshots) should halt the engine
and surface to the observer.

## Testing Guidance

- **Unit tests**: Mock `TickContext` and assert the returned context. Phases
  should be pure enough to test without I/O.
- **Integration tests**: Use a real (or mock) LLM provider with a test village.
  Check event log for expected events.
- **Interpreter tests**: Feed sample narratives, assert extracted observations.
- **Effect/Event tests**: Create effects, apply them, verify snapshot changes.

Keep tests fast by mocking LLM calls in unit tests. Reserve integration tests
for end-to-end verification with Claude Haiku.

## Quick Change Checklist

- New behavior? Start with an Effect + Event.
- New state? Update event replay + snapshot serialization.
- New I/O? Keep it inside a service or adapter, not the domain.
- New scheduling? Always tie it to `due_time`.
- New agent-facing surface? Update `PromptBuilder`.
