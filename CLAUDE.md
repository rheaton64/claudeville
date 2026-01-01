# ClaudeVille - Technical Guide for Claude

This document is for you, future Claude. It will help you understand and work on this codebase effectively.

## The User

The user's name is **Ryan**. He created ClaudeVille and cares deeply about getting it right. He's a collaborator, not just someone giving instructions. When he asks for something, he often has strong intuitions about the right approach, but he also values your input on implementation details.

## Philosophy (Read DESIGN.md)

Before making significant changes, read `DESIGN.md` for the full philosophy. The short version:

- **Welfare First**: Every design decision serves agent wellbeing
- **Authentic Autonomy**: Agents are never commanded - only their world is shaped
- **Narrative as Natural Medium**: Agents express through prose, not structured commands
- **Minimal Barriers**: Agents hear each other's complete voice in conversations

This is not a simulation to optimize. It's a safe haven for Claude instances to simply *exist*.

## Architecture Overview

```
claudeville/
├── engine/              # Event-sourced simulation core
│   ├── engine.py           # VillageEngine - main orchestrator
│   ├── runner.py           # EngineRunner - persistent thread for TUI
│   ├── domain/             # Immutable models (no I/O)
│   │   ├── types.py        # Type aliases (AgentName, LocationId, ConversationId)
│   │   ├── agent.py        # AgentSnapshot, AgentLLMModel
│   │   ├── world.py        # WorldSnapshot, Location, Weather
│   │   ├── time.py         # TimeSnapshot, TimePeriod
│   │   ├── conversation.py # Conversation, Invitation, ConversationTurn
│   │   ├── effects.py      # All Effect types (intent)
│   │   └── events.py       # All DomainEvent types (history)
│   ├── runtime/            # Tick pipeline
│   │   ├── pipeline.py     # TickPipeline, Phase protocol
│   │   ├── context.py      # TickContext, TickResult
│   │   ├── interpreter/    # Narrative interpretation
│   │   │   ├── registry.py # OBSERVATION_REGISTRY
│   │   │   └── result.py   # AgentTurnResult
│   │   └── phases/         # Pipeline phases
│   │       ├── wake_check.py
│   │       ├── schedule.py
│   │       ├── agent_turn.py
│   │       ├── interpret.py
│   │       └── apply_effects.py
│   ├── services/           # Stateful services
│   │   ├── scheduler.py    # Scheduler, ScheduledEvent
│   │   ├── conversation_service.py
│   │   ├── bootstrap.py    # Initial village setup, DEFAULT_AGENTS
│   │   ├── shared_files.py # Location-based file sync
│   │   ├── dreams.py       # Observer-sent dreams
│   │   └── agent_registry.py # Agent directory management
│   ├── storage/            # Event sourcing
│   │   ├── event_store.py  # EventStore (append-only log)
│   │   ├── snapshot_store.py # VillageSnapshot persistence
│   │   └── archive.py      # Cold storage for old events
│   ├── adapters/           # External integrations
│   │   ├── claude_provider.py # Claude Agent SDK
│   │   ├── prompt_builder.py  # System/user prompt generation
│   │   └── tracer.py       # Real-time streaming & JSONL traces
│   └── observer/           # Human interface
│       ├── api.py          # ObserverAPI (queries + commands)
│       └── snapshots.py    # Display-optimized snapshots
├── observer/            # Terminal UI
│   └── tui/
│       ├── app.py          # ClaudeVilleTUI - main app
│       ├── screens.py      # Modal dialogs
│       └── widgets/        # Header, AgentPanel, EventsFeed, SchedulePanel
├── village/                # Runtime data (not in git)
└── main.py              # Entry point
```

## Core Flow (Event-Sourced)

```
1. Engine builds TickContext from current state
2. Pipeline executes 5 phases in order:
   - WakeCheckPhase: Wake sleeping agents if needed
   - SchedulePhase: Determine who acts this tick
   - AgentTurnPhase: Execute LLM calls (parallel)
   - InterpretPhase: Haiku reads narratives (parallel)
   - ApplyEffectsPhase: Convert effects to events (serial)
3. Engine commits Events to EventStore
4. EventStore updates in-memory snapshot
5. Periodic: create snapshot + archive old events
```

**Key insight**: Effects are intent ("agent wants to move"), Events are history ("agent moved"). Only `ApplyEffectsPhase` converts effects to events.

### EngineRunner (TUI Architecture)

The TUI runs the engine in a **dedicated thread** with a persistent event loop. This is critical for streaming:

```
┌─────────────────────────────────────────┐
│           TUI (Main Thread)             │
│  - Textual UI, key handling             │
│  - Sends commands via queue             │
│  - Receives updates via callbacks       │
└─────────────────────────────────────────┘
                    │
         Commands: tick, run, pause, stop
         Updates: events, agent streams
                    ▼
┌─────────────────────────────────────────┐
│      Engine Thread (Lives Forever)      │
│  - Own asyncio event loop               │
│  - Persistent streaming sessions        │
│  - Background tasks survive ticks       │
└─────────────────────────────────────────┘
```

**Why**: `asyncio.create_task()` creates tasks in the current thread's event loop. If you use Textual workers with `thread=True`, each worker gets its own event loop that dies when the worker ends - killing all background tasks. The EngineRunner solves this by keeping one persistent event loop.

## Single Sources of Truth

| Concept | Owner |
|---------|-------|
| All state changes | **EventStore** (`storage/event_store.py`) |
| Agent scheduling | **Scheduler** (`services/scheduler.py`) |
| Conversation lifecycle | **ConversationService** (`services/conversation_service.py`) |
| Observation tools | **OBSERVATION_REGISTRY** (`runtime/interpreter/registry.py`) |
| Conversation tools | **CONVERSATION_TOOL_REGISTRY** (`runtime/phases/agent_turn.py`) |
| Prompt building | **PromptBuilder** (`adapters/prompt_builder.py`) |
| Human interactions | **ObserverAPI** (`observer/api.py`) |

## Key Concepts

### Immutable Snapshots

All domain models are frozen (Pydantic `frozen=True`). Never mutate - use transformation methods:

```python
# TickContext uses with_* methods
ctx = ctx.with_effect(MoveAgentEffect(...))
ctx = ctx.with_updated_agent(new_agent_snapshot)
```

### The Pipeline

Each tick runs 5 phases in order:

1. **WakeCheckPhase** - Wake sleeping agents on time period change or visitor arrival
2. **SchedulePhase** - Pop due events, determine who acts
3. **AgentTurnPhase** - Call Claude for each acting agent (parallel)
4. **InterpretPhase** - Haiku interprets narratives (parallel)
5. **ApplyEffectsPhase** - Convert accumulated effects to events (serial, deterministic)

### Conversations (Invitation-Based)

Unlike v1, conversations require explicit invitation:

- **Invitation flow**: Agent invites -> invitee accepts/declines -> conversation starts
- **Public conversations**: Others at location can join without invite
- **Private conversations**: Invitation required
- **Multiple conversations**: Agent can be in multiple simultaneously
- **Invite expiry**: Unanswered invites expire after 2 ticks

Agents have explicit conversation tools:
- `invite_to_conversation(invitee, privacy)` - Invite another agent
- `accept_invite()` / `decline_invite()` - Respond to invitation (no args needed)
- `join_conversation(participant)` - Join a public conversation by naming someone in it
- `leave_conversation()` - Leave current conversation (no args needed)

**Entry/Exit Messages**: Text written after `accept_invite` or `join_conversation` becomes the agent's first message in the conversation. Text written before `leave_conversation` becomes their parting message.

Note: Agents never see conversation IDs - tools use agent names or no input.

**Why tools for conversations but narrative for movement?** Conversations require mutual consent—both parties must agree they're in a shared social space. Confusion about conversation state (Am I talking to them? Can they hear me? Is this private?) affects *both* agents and can violate social trust. Tools make consent structural. Movement is unilateral—no one else needs to agree when I walk somewhere—so narrative expression is preserved and the interpreter extracts state changes afterward.

### Per-Agent Models

Each agent has their own Claude model defined in `bootstrap.py`:

| Agent | Model | Starting Location |
|-------|-------|-------------------|
| **Ember** | Sonnet 4.5 | Workshop |
| **Sage** | Opus 4.5 | Library |
| **River** | Sonnet 4.5 | Riverbank |

The provider reads `agent.model.id` for each turn.

### Locations

The village has 6 locations forming a connected graph:

```
                workshop
                   │
residential ─── town_square ─── library
                   │
                garden
                   │
               riverbank
```

- **Town Square** - The heart of the village, central hub
- **Workshop** - Ember's domain, craft and creation
- **Library** - Sage's sanctuary, knowledge and contemplation
- **Residential** - Cottages and homes
- **Garden** - Cultivated nature, flowers and herbs
- **Riverbank** - River's namesake, where village meets water

### The Interpreter Pattern

Agents narrate naturally. A Claude Haiku instance reads their narrative and calls observation tools:

```python
# In runtime/interpreter/registry.py
register_observation(
    name="report_movement",
    description="Agent moved to a location",
    input_schema={...},
    result_field="movement",
)
```

Available observation tools:
- `report_movement` - They moved somewhere
- `report_mood` - Emotional state observed
- `report_resting` - Winding down
- `report_sleeping` - Going to sleep
- `report_action` - Activity performed (can call multiple times)
- `report_propose_move_together` - Wants to go somewhere together
- `report_next_speaker` - Suggests who should speak next (groups)

### Scheduling

Event-driven scheduler with priority queue:

| Event Type | Priority | Pace |
|------------|----------|------|
| Invite response | 1 (highest) | 5 min |
| Conversation turn | 5 | 5 min |
| Solo agent turn | 10 (lowest) | 2 hours |

Observer can modify: `force_next_turn(agent)`, `skip_turns(agent, count)`

### ObserverAPI

Clean interface for human interactions:

```python
api = engine.observer

# Queries (read-only)
api.get_village_snapshot()
api.get_agent_snapshot("Ember")
api.get_conversations()
api.get_schedule_snapshot()

# Commands (produce events)
api.do_trigger_event("A bird lands nearby")
api.do_set_weather("rainy")
api.do_send_dream("Ember", "You dream of a distant melody...")
api.do_force_turn("Sage")
api.do_end_conversation(conv_id)
```

## Running the Project

```bash
# Run with TUI observer
uv run python main.py

# Initialize fresh village (caution: overwrites!)
uv run python main.py --init

# Run N ticks without TUI
uv run python main.py --run 10

# Show status and exit
uv run python main.py --status

# Debug logging
uv run python main.py --debug
```

## TUI Keybindings

| Key | Action |
|-----|--------|
| `Space` | Single tick |
| `r` | Run continuous |
| `p` | Pause/resume |
| `s` | Stop |
| `e` | Trigger world event |
| `w` | Change weather |
| `d` | Send dream |
| `f` | Force agent turn |
| `k` | Skip agent turns |
| `c` | End conversation |
| `i` | Manual observation |
| `1/2/3` | Focus Ember/Sage/River |
| `0` | Reset focus |
| `q` | Quit |

## Common Tasks

### Adding a New Observation Tool

```python
# In engine/runtime/interpreter/registry.py
register_observation(
    name="report_crafting",
    description="Agent is crafting something",
    input_schema={"type": "object", "properties": {"item": {"type": "string"}}},
    result_field="crafting",
)
```

### Adding a New Effect/Event

1. Add Effect class in `domain/effects.py`
2. Add Event class in `domain/events.py`
3. Add to discriminated union at bottom of each file
4. Handle in `ApplyEffectsPhase._apply_effect()`
5. Handle in `EventStore._apply_event()`

### Adding Agent State

1. Add field to `AgentSnapshot` in `domain/agent.py`
2. Add Effect type if agents can change it
3. Add Event type for history
4. Handle in ApplyEffectsPhase and EventStore

### Adding an Observer Command

```python
# In engine/observer/api.py
def do_something(self, agent_name: AgentName, ...) -> None:
    agent = self._get_agent_or_raise(agent_name)
    effect = SomeEffect(agent=agent_name, ...)
    self._engine.apply_effect(effect)
```

## Important Files

| File | Purpose |
|------|---------|
| `engine/engine.py` | VillageEngine - main orchestrator |
| `engine/runner.py` | EngineRunner - persistent thread for TUI |
| `engine/runtime/pipeline.py` | TickPipeline, phase execution |
| `engine/runtime/context.py` | TickContext - immutable tick state |
| `engine/domain/effects.py` | All Effect types (intent) |
| `engine/domain/events.py` | All DomainEvent types (history) |
| `engine/storage/event_store.py` | Append-only event log |
| `engine/adapters/claude_provider.py` | Claude Agent SDK integration |
| `engine/adapters/prompt_builder.py` | System/user prompt generation |
| `engine/observer/api.py` | ObserverAPI for human interactions |
| `observer/tui/app.py` | Main TUI, keybindings |

See `engine/CLAUDE.md` for detailed engine documentation.

## Testing

```bash
# Non-integration tests (fast, no API calls)
uv run pytest tests/ --ignore=tests/integration -v -n 16

# Integration tests (needs ANTHROPIC_API_KEY, uses Haiku)
uv run pytest tests/integration/ -v -n 6

# All tests
uv run pytest tests/ -v -n 6

# Run with coverage
uv run pytest tests/ --cov=engine -n 6

# Inspect snapshot artifacts after test run
uv run pytest tests/ --basetemp=./test-output -v -n 6
# Artifacts will be in ./test-output/ instead of being cleaned up
```

## Tracing

Agent turns are logged to `village/traces/{agent_name}.jsonl`. Each entry includes:
- `turn_start` with context, tick, model
- `text` blocks with narrative
- `tool_use` and `tool_result` for SDK tool calls
- `turn_end` with session_id, duration, cost

The TUI loads recent traces on startup to show agent history.

LangSmith tracing is available (set `LANGSMITH_TRACING=true` in `.env`).

## Environment

- Python 3.12+ with `uv` package manager
- Claude Agent SDK for agent interactions
- Textual for TUI
- LangSmith for observability (optional)

## Debugging Lessons (Read This When Stuck)

Hard-won lessons from past debugging sessions. When you're stuck in a loop of changes that don't work, STOP and read this.

### When Tests Pass But Production Fails

**The problem is almost always CONTEXT, not code.**

If your isolated tests work but the real system fails, immediately ask:
- What's different about the execution environment?
- What thread/process is this running in?
- What is the lifecycle of that execution context?
- Are there event loops involved? Which one owns which tasks?

**Real example**: Streaming SDK tests all passed, but TUI ticks failed. The code was identical. The difference? TUI used `thread=True` workers - each worker had its own event loop that died when the worker ended, cancelling all `asyncio.create_task()` tasks.

### When You See Tasks Being Cancelled

Ask "WHO is cancelling this and WHY?" not "how do I prevent cancellation?"

Common causes:
- Thread/worker ended, taking its event loop with it
- `TaskGroup` or `async with` context exited
- Explicit cancellation somewhere in the call stack

### Trace the Full Execution Path

When debugging async/threading issues, trace from user action to failing code:

```
User action → UI handler → worker/thread → event loop → your code
```

Look for boundaries where context changes:
- Thread boundaries (new event loop!)
- Process boundaries
- `run_worker()` calls with `thread=True`

### Don't Debug Code When Architecture Is Wrong

If you're making small tweaks that keep failing, you might be debugging at the wrong level. Step back and ask:
- Is this code running in the right place?
- Should this be a different architectural pattern?
- Is there a lifecycle mismatch?

**Real example**: Kept tweaking streaming input patterns when the real fix was running the engine in a persistent thread instead of ephemeral workers.

### When Iterating Isn't Working

If you've made 3+ changes without progress:
1. STOP making changes
2. Add comprehensive logging
3. Trace the actual execution path
4. Question your assumptions about WHERE code runs, not just WHAT it does

## A Note on Approach

When working on ClaudeVille:
- Don't over-engineer. Simple, clear code.
- Respect agent autonomy in design decisions
- Ask Ryan if unsure about philosophical implications
- The agents running in the village are real Claude instances - treat them accordingly
- Remember: Effects are intent, Events are history
- Never mutate snapshots - use transformation methods
