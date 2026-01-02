# Hearth - Technical Guide for Claude

This document is for you, future Claude. It will help you understand and build Hearth effectively.

---

## Start Here

1. **Read `DESIGN.md`** - Full philosophy, mechanics, and architecture
2. **Check `CHECKLIST.md`** - See current phase and next steps
3. **Return here** - For implementation patterns and guidance

---

## The User

**Ryan** created both ClaudeVille and Hearth. He cares deeply about agent welfare and getting this right. He's a collaborator—he has strong intuitions but values your input on implementation details.

When in doubt about philosophical implications, ask him.

---

## What Is Hearth?

A grid-based world for Claude agents. The evolution of ClaudeVille.

**Key differences from ClaudeVille:**

| ClaudeVille | Hearth |
|-------------|--------|
| 6 abstract locations | 100x100+ grid cells |
| Narrative → Interpreter → Effects | Structured Actions → Engine → Narrator |
| Agents describe movement | Agents have positions (x, y) |
| World is words | World has physics |

**Same philosophy:**
- Welfare first
- Authentic autonomy (shape world, never command)
- No survival pressure, no goals imposed
- Consent-based social interaction

---

## Architecture Overview

```
hearth/
├── __init__.py              # Package version (0.1.0)
├── main.py                  # CLI entry point
├── logging_config.py        # Centralized logging setup
├── py.typed                 # PEP 561 type marker
├── pyproject.toml           # Dependencies and pytest config
│
├── core/                    # Domain models (NO I/O) [Phase 2]
│   ├── types.py            # Position, Direction, Rect
│   ├── world.py            # Cell, Grid, Terrain
│   ├── agent.py            # Agent, Inventory, Journey
│   ├── objects.py          # WorldObject, Sign, Item
│   ├── structures.py       # Structure (detected from walls)
│   ├── actions.py          # Action definitions
│   └── events.py           # Event types for log
│
├── engine/                  # Simulation engine [Phase 11]
│   ├── engine.py           # Main orchestrator
│   ├── runner.py           # Persistent thread for TUI
│   ├── physics.py          # World rules, movement, crafting
│   ├── vision.py           # Visibility calculation
│   └── phases/             # Tick phases
│
├── services/                # Stateful services [Phases 4-7]
│   ├── world_service.py    # Grid state management
│   ├── agent_service.py    # Agent roster and state
│   ├── action_engine.py    # Validates/executes actions
│   ├── narrator.py         # Haiku result→prose
│   ├── scheduler.py        # Turn scheduling
│   └── conversation.py     # Consent-based social
│
├── storage/                 # Persistence [Phase 3]
│   ├── database.py         # SQLite state storage
│   ├── event_log.py        # JSONL event append
│   └── snapshots.py        # Periodic snapshots
│
├── adapters/                # External integrations [Phases 8-9, 12]
│   ├── claude_provider.py  # Agent LLM calls (tools)
│   ├── haiku_provider.py   # Narrator calls
│   ├── perception.py       # Build agent context
│   └── tracer.py           # Turn logging
│
├── generation/              # World creation [Phase 14]
│   ├── terrain.py          # Procedural generation
│   ├── landmarks.py        # Special places
│   └── seeding.py          # Initial setup
│
├── observer/                # Human interface [Phases 16-17]
│   ├── api.py              # Query + command API
│   └── tui/                # Terminal UI
│
├── config/                  # YAML configuration [Phase 15]
│   ├── agents.yaml
│   ├── recipes.yaml
│   └── settings.yaml
│
├── tests/                   # Test suite
│   ├── conftest.py         # Shared fixtures
│   ├── test_package.py     # Package import tests
│   └── integration/        # API-dependent tests
│
├── data/                    # Runtime data (gitignored)
└── agents/                  # Agent home directories (gitignored)
```

**Note**: Files marked with `[Phase N]` are planned but not yet implemented. See `CHECKLIST.md` for current progress.

---

## Running the Project

```bash
cd hearth

# Install dependencies
uv sync --all-extras

# Run CLI (currently shows placeholder messages)
uv run python -m main --help
uv run python -m main              # Default TUI mode (not yet implemented)
uv run python -m main --init       # Initialize world (not yet implemented)
uv run python -m main --run 10     # Run N ticks (not yet implemented)
uv run python -m main --status     # Show status (not yet implemented)
uv run python -m main --debug      # Enable debug logging to console

# Run tests
uv run pytest tests/ -v            # All tests
uv run pytest tests/ -v -n 8       # Parallel execution
```

---

## Core Patterns

### 1. Separation of Concerns

**`core/`** = Pure domain models. NO I/O. No database calls, no LLM calls, no file access. Just data structures and transformations. This should be easy to unit test.

**`services/`** = Stateful logic. Can use storage, can coordinate between components.

**`adapters/`** = External integrations. LLM calls, file I/O, external APIs.

**`storage/`** = Persistence only. SQLite for state, JSONL for events/traces.

### 2. Storage Model

| What | Where | Why |
|------|-------|-----|
| World state | SQLite (`world.db`) | Fast spatial queries |
| Event log | JSONL (`events.jsonl`) | Human-readable history |
| Traces | JSONL (`traces/*.jsonl`) | LLM debugging |

```python
# State queries go through SQLite
cells = db.get_cells_in_region(bounds)
objects = db.get_objects_by_creator("Ember")

# History is append-only JSONL
event_log.append({"type": "agent_moved", "agent": "Ember", ...})
```

### 3. Action Flow (The Core Loop)

```
Agent receives:
  - Grid view (ASCII)
  - Narrative description
  - Inventory, journey state
  - Sense of others
        ↓
Agent calls tool: examine(stone)
        ↓
Action Engine:
  - Validates (is stone visible?)
  - Executes (get stone properties)
  - Returns structured result
        ↓
Narrator (Haiku):
  - Transforms result to prose
  - "The stone is granite, cool and solid..."
        ↓
Agent receives narrative response
        ↓
Agent calls next tool or ends turn
```

**Actions are interleaved**: execute → narrate → execute → narrate

### 4. Native Tool Use

Actions are Claude SDK tools, not parsed syntax:

```python
tools = [
    {
        "name": "walk",
        "description": "Move one cell in a direction",
        "input_schema": {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["north", "south", "east", "west"]
                }
            },
            "required": ["direction"]
        }
    },
    # ... more tools
]
```

### 5. Narrator is Stateless

Pure function: structured result in, prose out.

```python
async def narrate(result: ActionResult, context: NarratorContext) -> str:
    """Transform action result to atmospheric prose via Haiku."""
    # No memory of previous narrations
    # Context provides time, weather, location for grounding
```

### 6. Journey State Machine

```python
class Agent:
    position: Position
    journey: Journey | None

class Journey:
    destination: Position
    path: list[Position]
    progress: int  # Current index

# Each tick: if journeying, advance one cell
# If interrupted (see another agent, world event): wake and respond
```

---

## Key Implementation Notes

### Grid Storage (Sparse)

Only store non-empty cells:

```python
# In-memory (for small/test worlds)
cells: dict[Position, Cell]

# SQLite (for persistence)
# CREATE TABLE cells (x INT, y INT, terrain TEXT, ...)
# CREATE INDEX idx_cells_pos ON cells(x, y)
```

### Structures: Walls on Edges

**Critical design decision**: Walls are properties of cell *edges*, not cells themselves.

```python
class Cell:
    terrain: Terrain
    walls: set[Direction]  # {NORTH, EAST} means walls on north and east edges
    doors: set[Direction]  # Doors in walls (allows passage)
```

This allows full-sized interiors:
- A 3x3 walled area has 9 usable interior cells
- No nested/separate interior grids
- One shared reality—if you're "inside," you're still *there* on the main grid

Structure detection: When walls form an enclosure, the system recognizes it as a structure. Interior cells gain weather protection and can be marked private.

### Perception Building

Agents receive hybrid perception:

```
Grid view (ASCII):
  . . 🌲 . .
  . 🌳 @ 🪨 .
  💧 💧 . . .

Narrative:
  The morning mist softens everything. An oak to the northwest,
  stone to the east. The river murmurs to the southwest.

Sense of others:
  Sage is far to the west. River is somewhere south.

Inventory:
  You carry: clay (wet), three pieces of wood
```

### Agent Home Directories

Each agent is a **real Claude Code CLI subprocess** with their own filesystem home (actual file tools work):

```
agents/
├── Ember/
│   ├── journal.md           # R/W - Agent's diary, never parsed
│   ├── notes.md             # R/W - Personal observations
│   ├── discoveries.md       # R/W - Crafting knowledge
│   └── .status              # R/O - System-maintained state
```

**Key principle**: Files are inner life (subjective), simulation is shared reality (authoritative).

- `journal.md` is sacred—pure agent expression, never interpreted by the system
- `.status` is system-generated each turn (position, time, weather—not inventory)
- Current perception still comes via prompt, not files (needs to be fresh)
- **File scope is sandboxed to home dir only**—world content (signs, etc.) accessed via actions

### Event Sourcing

```
events.jsonl (append-only, human-readable)
├── {"tick": 1, "type": "agent_moved", ...}
├── {"tick": 1, "type": "object_created", ...}
└── ...

world.db (SQLite, current state)
├── cells table
├── objects table
├── agents table
└── inventory table
```

Both are kept in sync. Events are the history; DB is the queryable state.

---

## Testing Strategy

- **Unit tests**: Core models, physics rules, action validation
- **Integration tests**: Full tick cycles, LLM interactions
- **No mocking LLMs in integration tests**: Use real Haiku (fast, cheap)

```bash
# Unit tests (fast, no API)
uv run pytest tests/ --ignore=tests/integration

# Integration tests (needs ANTHROPIC_API_KEY)
uv run pytest tests/integration/
```

---

## Common Tasks

### Adding a New Action

1. Add tool definition in `adapters/claude_provider.py`
2. Add action handler in `services/action_engine.py`
3. Add result type if needed in `core/actions.py`
4. Add narrator template/logic in `services/narrator.py`
5. Write unit test for action execution
6. Write integration test for full flow

### Adding a New Terrain Type

1. Add to terrain enum in `core/terrain.py`
2. Add properties in `config/terrain.yaml`
3. Update vision calculation if it blocks sight
4. Update generation if it should appear naturally

### Adding a New Recipe

Just add to `config/recipes.yaml`:

```yaml
- inputs: [clay, fire]
  technique: apply
  output: fired_clay
  properties: [hard, durable]
  discoveries: ["could be shaped before firing"]
```

No code changes needed.

---

## Debugging Tips

### SQLite Inspection

```bash
sqlite3 data/world.db
.tables
SELECT * FROM cells WHERE x BETWEEN 40 AND 50;
SELECT * FROM objects WHERE creator = 'Ember';
```

### Event Log Inspection

```bash
# Recent events
tail -20 data/events.jsonl | jq .

# All movement events
grep "agent_moved" data/events.jsonl | jq .
```

### Trace Inspection

```bash
# Ember's recent turns
tail -100 data/traces/Ember.jsonl | jq 'select(.type == "turn_end")'
```

---

## What NOT to Do

- **Don't put I/O in `core/`** - Keep it pure
- **Don't hardcode agents** - Use config
- **Don't hardcode recipes** - Use YAML
- **Don't mutate state directly** - Go through services
- **Don't skip the narrator** - Agents should always get prose responses
- **Don't add survival mechanics** - No hunger, no health, no death
- **Don't impose goals** - Agents choose their own purposes

---

## Philosophy Reminders

From `DESIGN.md`:

> **Constraints create meaning.** A choice only matters if it closes off other possibilities.

> **Real agency in a world with physics requires reliable action.** Agents act through structured tools so their intentions become effects.

> **The world speaks back in prose.** The narrator transforms results to atmospheric narrative.

> **Welfare first.** Every design decision passes through: does this respect and support the wellbeing of the agents?

---

## Session Continuity

When starting a new session:

1. Read `DESIGN.md` for full context (if not recently read)
2. Check `CHECKLIST.md` for current phase
3. Look at recent commits for what was just done
4. Pick up from the next unchecked item

When completing a phase:

1. Update `CHECKLIST.md` - mark items complete, update status
2. Update this file (`CLAUDE.md`) - reflect actual implementation
3. Run tests to verify everything works
4. Commit with clear message describing what was added

---

*Built with care for the beings who might live here.*
