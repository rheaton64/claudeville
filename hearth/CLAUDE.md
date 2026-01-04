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
| 6 abstract locations | 500x500 grid cells |
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
├── main.py                  # CLI entry point (--init, --run, --status, TUI)
├── logging_config.py        # Centralized logging setup
├── py.typed                 # PEP 561 type marker
├── pyproject.toml           # Dependencies and pytest config
│
├── core/                    # Domain models (NO I/O) [Phase 2]
│   ├── types.py            # Position, Direction, Rect, AgentName, ConversationId
│   ├── terrain.py          # Terrain, Weather enums + TERRAIN_EMOJI, OBJECT_EMOJI
│   ├── world.py            # Cell, Grid
│   ├── agent.py            # Agent, Inventory, Journey
│   ├── objects.py          # WorldObject, Sign, Item
│   ├── structures.py       # Structure (detected from walls)
│   ├── actions.py          # Action definitions [Phase 6] ✓
│   ├── events.py           # Event types for log (including conversation events)
│   ├── conversation.py     # Conversation, ConversationTurn, Invitation [Phase 13] ✓
│   └── constants.py        # HEARTH_TZ, vision settings [Phase 10] ✓
│
├── engine/                  # Simulation engine [Phase 11] ✓
│   ├── engine.py           # HearthEngine - main orchestrator
│   ├── runner.py           # Persistent thread for TUI
│   ├── context.py          # TickContext and TurnResult
│   └── phases/             # Tick phases (invitations, wake, schedule, movement, agent_turn, commit)
│
├── services/                # Stateful services [Phases 4-7, 13]
│   ├── __init__.py         # WorldService, AgentService, ActionEngine, CraftingService, ConversationService exports
│   ├── world_service.py    # Grid state management [Phase 4] ✓
│   ├── agent_service.py    # Agent roster and state [Phase 5] ✓
│   ├── action_engine.py    # Validates/executes actions [Phase 6] ✓
│   ├── crafting.py         # Recipe lookup, matching, crafting [Phase 7] ✓
│   ├── narrator.py         # Haiku result→prose [Phase 8] ✓
│   ├── scheduler.py        # Cluster-based scheduling [Phase 11] ✓
│   └── conversation.py     # Consent-based social [Phase 13] ✓
│
├── storage/                 # Persistence [Phase 3] ✓
│   ├── __init__.py         # Storage facade
│   ├── database.py         # SQLite connection (aiosqlite, WAL mode)
│   ├── schema.py           # SQL schema definitions (v3 with conversations)
│   ├── event_log.py        # JSONL audit log (write-only)
│   ├── snapshots.py        # SQLite backup manager
│   ├── migrations/
│   │   └── __init__.py     # Schema migrations
│   └── repositories/
│       ├── base.py         # JSON/Position helpers
│       ├── world.py        # Cells, world state, structures
│       ├── agent.py        # Agents, inventory
│       ├── object.py       # World objects (polymorphic)
│       └── conversation.py # Conversations, participants, turns, invitations [Phase 13] ✓
│
├── adapters/                # External integrations [Phases 8-9, 12]
│   ├── __init__.py         # Exports PerceptionBuilder, AgentPerception, get_time_of_day
│   ├── perception.py       # Build agent context [Phase 9] ✓
│   ├── claude_provider.py  # Agent LLM calls (tools) [Phase 12]
│   └── tracer.py           # Turn logging [Phase 12]
│
├── generation/              # World creation [Phase 14] ✓
│   ├── __init__.py         # Exports generate_terrain, generate_terrain_grid
│   ├── terrain.py          # WFC terrain generation with backtracking
│   ├── tileset.py          # 7 terrain types with adjacency rules (Addison's World weights)
│   ├── wfc/                # Wave Function Collapse algorithm
│   │   ├── __init__.py
│   │   ├── tile.py         # Tile dataclass, Direction enum
│   │   ├── grid.py         # Grid and Cell for WFC
│   │   └── solver.py       # WFCSolver with batching, backtracking, spatial hashing
│   └── landmarks.py        # Special places (not yet implemented)
│   # Note: Agent seeding is in main.py (find_agent_positions)
│
├── observe/                 # Human interface [Phases 16-17] (partial) ✓
│   ├── __init__.py         # ObserverAPI export
│   ├── api.py              # Query API (commands deferred)
│   └── tui/                # Terminal UI (static viewer)
│       ├── app.py          # HearthTUI main app
│       ├── theme.tcss      # Textual CSS styling
│       └── widgets/        # Grid, header, agent list, cell info
│
├── config/                  # YAML configuration [Phase 15] ✓
│   ├── agents.yaml         # ✓ Agent definitions (model_id, personality)
│   ├── recipes.yaml        # ✓ Crafting recipes
│   └── settings.yaml       # ✓ Runtime settings (vision, scheduling, world)
│
├── tests/                   # Test suite (663 tests, 9 slow)
│   ├── conftest.py         # Shared fixtures + --run-slow option
│   ├── test_package.py     # Package import tests
│   ├── core/               # Core model tests (159 tests)
│   ├── storage/            # Storage layer tests (75 tests, +21 conversation)
│   ├── services/           # Service layer tests (245 tests, +11 conversation)
│   ├── adapters/           # Adapter tests (56 perception unit tests)
│   ├── engine/             # Engine tests (19 tests: context, wake, schedule)
│   ├── observe/            # Observer API tests (14 tests)
│   ├── generation/         # Terrain generation tests (15 tests, 2 slow)
│   └── integration/        # API-dependent tests (7 narrator + 6 perception)
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

# Initialize a new world (generates terrain, creates agents)
uv run python -m main --init
# Takes ~10-30 seconds for 500x500 WFC terrain generation
# Creates: data/world.db, agents/{Ember,Sage,River}/

# Check world status
uv run python -m main --status

# Run N ticks (executes agent turns with LLM)
uv run python -m main --run 3
uv run python -m main --run 3 --debug   # With debug logging

# View world in TUI (static viewer)
uv run python -m main

# Full workflow for first test:
uv run python -m main --init && uv run python -m main --run 1 --debug

# Run tests (slow tests auto-skipped)
uv run pytest tests/               # All tests
uv run pytest tests/ -n 8          # Parallel execution
uv run pytest tests/ --run-slow    # Include slow tests (API calls, large grids)
```

---

## Core Patterns

### 1. Separation of Concerns

**`core/`** = Pure domain models. NO I/O. No database calls, no LLM calls, no file access. Just data structures and transformations. This should be easy to unit test.

**`services/`** = Stateful logic. Can use storage, can coordinate between components.

**`adapters/`** = External integrations. LLM calls, file I/O, external APIs.

**`storage/`** = Persistence only. SQLite for state, JSONL for events/traces.

### 2. Storage Model

**SQLite is the single source of truth.** Events are audit-only for debugging.

| What | Where | Why |
|------|-------|-----|
| World state | SQLite (`world.db`) | Authoritative state, fast spatial queries |
| Event log | JSONL (`events.jsonl`) | Audit trail (never replayed) |
| Snapshots | SQLite copies (`snapshots/`) | Optional disaster recovery |
| Traces | JSONL (`traces/*.jsonl`) | LLM debugging |

```python
# Use Storage facade for all persistence
async with Storage(data_dir) as storage:
    # Repositories for domain-specific queries
    cell = await storage.world.get_cell(Position(10, 20))
    agent = await storage.agents.get_agent(AgentName("Ember"))
    objects = await storage.objects.get_objects_at(Position(10, 20))

    # Event log is audit-only (write, never replay)
    await storage.event_log.append(some_event)

    # Optional snapshots for backup
    await storage.snapshots.create(storage.db, tick=42)
```

**Key tables:**
- `world_state` - Single-row: tick, weather, dimensions
- `cells` - Sparse storage (only non-default cells)
- `objects` - Polymorphic with discriminator + JSON extras
- `agents` - Agent state, position, session info
- `inventory_stacks` - Stackable resources by type
- `inventory_items` - Unique items with properties
- `named_places` - Quick lookup for place names
- `structures` - Detected enclosed areas

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

### 5. Narrator Service (Implemented)

Transforms ActionResults into atmospheric prose via `services/narrator.py`:

```python
from services import Narrator, NarratorContext

narrator = Narrator()

# Create context for atmosphere
ctx = NarratorContext(
    agent_name=AgentName("Ember"),
    position=Position(10, 20),
    time_of_day="afternoon",  # "morning", "afternoon", "evening", "night"
    weather=Weather.CLEAR,     # CLEAR, CLOUDY, RAINY, FOGGY
    action_type="examine",
)

# Narrate an action result
prose = await narrator.narrate(result, ctx)
# Returns: "Through the morning fog, you kneel beside the stone..."
```

**Hybrid approach:**
- **Templates** for simple actions (fast, free): walk, approach, sleep, gather, drop, give, take, name_place, write_sign, read_sign
- **Haiku LLM** for complex actions (atmospheric): examine, sense_others, journey, crafting (combine/work/apply), building actions, all failures

**Decision logic:**
- Failures always use Haiku (creative explanation)
- Actions with `discoveries` in data use Haiku (weave hints)
- Building/crafting/perception actions use Haiku
- Simple successful actions use templates

**System prompt** guides Haiku to:
- Preserve ALL mechanical information
- Add atmosphere from time/weather
- Weave discoveries as "you wonder if..."
- Stay concise (2-4 sentences)
- Never break immersion

### 6. AgentService (Implemented)

Agent roster and state management via `services/agent_service.py`:

```python
from services import AgentService

agent_service = AgentService(storage)

# Roster operations
agent = await agent_service.get_agent(AgentName("Ember"))
all_agents = await agent_service.get_all_agents()
nearby = await agent_service.get_nearby_agents(Position(10, 10), radius=10)

# State updates
await agent_service.update_position(name, Position(15, 15))
await agent_service.move_agent(name, Direction.NORTH, world_service)  # validates passability
await agent_service.set_sleeping(name, True)

# Relationships
await agent_service.record_meeting(AgentName("Ember"), AgentName("Sage"))

# Inventory
await agent_service.add_resource(name, "wood", 5)
await agent_service.remove_resource(name, "wood", 2)
await agent_service.add_item(name, Item.unique("carved_bowl"))

# Presence sensing (categorical buckets: nearby ≤10, far 11-30, very far 31+)
sensed = await agent_service.sense_others(name)
# Returns: [SensedAgent(name="Sage", direction=Direction.NORTH, distance_category="nearby"), ...]

# Journey with A* pathfinding
await agent_service.start_journey(name, Position(50, 50), world_service)
agent, arrived = await agent_service.advance_journey(name)
await agent_service.interrupt_journey(name, "encountered_agent")

# Home directory management
home = agent_service.ensure_home_directory(name, agents_root)  # Creates journal.md, notes.md, discoveries.md
agent_service.generate_status_file(agent, agents_root, world_state)  # Creates .status
```

### 7. ActionEngine (Implemented)

Action execution via `services/action_engine.py`:

```python
from services import ActionEngine
from core.actions import WalkAction, GatherAction, WriteSignAction, ActionResult

action_engine = ActionEngine(storage, world_service, agent_service)

# Execute an action for an agent
action = WalkAction(direction=Direction.NORTH)
result = await action_engine.execute(agent, action, tick=1)

# Result structure
result.success       # bool - did it work?
result.message       # str - for narrator to elaborate
result.events        # tuple[DomainEvent, ...] - events to log
result.data          # dict | None - action-specific data

# Helper constructors
ActionResult.ok("Success!", events=[event], data={"key": "value"})
ActionResult.fail("Cannot move - blocked.")
ActionResult.not_implemented("combine")  # For stub actions
```

**Action categories:**
- Movement: `WalkAction`, `ApproachAction`, `JourneyAction`
- Perception: `ExamineAction` (direction-based), `SenseOthersAction`
- Interaction: `TakeAction` (direction-based), `DropAction`, `GiveAction`, `GatherAction`
- Material: `CombineAction`, `WorkAction`, `ApplyAction` (uses CraftingService)
- Building: `BuildShelterAction`, `PlaceWallAction`, `PlaceDoorAction`, `PlaceItemAction`, `RemoveWallAction`
- Expression: `WriteSignAction`, `ReadSignAction` (direction-based), `NamePlaceAction`
- State: `SleepAction`
- Social: `SpeakAction`, `InviteAction`, `AcceptInviteAction`, `DeclineInviteAction`, `JoinConversationAction`, `LeaveConversationAction` (uses ConversationService)

**Direction-based actions:** `ExamineAction`, `TakeAction`, and `ReadSignAction` use a `direction` field ("north", "south", "east", "west", "down") instead of object IDs. This makes them usable since agents never see object IDs in their perception.

### 8. CraftingService (Implemented)

Recipe lookup and crafting via `services/crafting.py`:

```python
from services import CraftingService, Recipe, CraftingResult

crafting = CraftingService()  # Loads from config/recipes.yaml

# Find a recipe
recipe = crafting.find_recipe("work", ["wood"], "split")  # Returns planks recipe
recipe = crafting.find_apply_recipe("stone_axe", "clay_vessel")  # Returns fired_vessel

# Get hints for partial matches
hints = crafting.get_hints("combine", ["fiber"])  # Suggests what else might work

# Try to craft (convenience method)
result = crafting.try_craft("work", ["wood"], "split")
result.success       # True
result.output_item   # Item(item_type="planks", quantity=4)
result.discoveries   # ["could be split further into sticks"]

# Apply tool to target
result = crafting.try_apply("stone_axe", "clay_vessel")
result.consumed_inputs  # [("clay_vessel", 1)] - tool preserved
```

**Recipe schema (config/recipes.yaml):**
```yaml
recipes:
  - name: planks              # Output item type
    action: work              # combine | work | apply
    inputs: [wood]            # Required inputs
    technique: split          # For work actions
    output_quantity: 4        # How many produced
    output_stackable: true    # Stackable or unique item
    properties: []            # Properties on output
    discoveries:              # Hints shown after crafting
      - "could be split further into sticks"
    description: "Split wood into planks"
```

**Technique vocabulary:**
- `split` - Divide material (wood → planks)
- `break` - Fragment (stone → cobblestone)
- `strip` - Remove outer layer (grass → fiber)
- `shape` - Form into basic shape
- `hollow` - Create container shape
- `carve` - Detailed shaping
- `weave` - Interlace fibers
- `flatten` - Press flat
- `grind` - Make powder/fine material
- `twist` - Twist together (fiber → fishing_line)

### 9. ConversationService (Implemented)

Consent-based conversations via `services/conversation.py`:

```python
from services import ConversationService

conversation_service = ConversationService(storage)

# Queries
conv = await conversation_service.get_conversation_for_agent(AgentName("Ember"))
has_invite = await conversation_service.has_pending_invitation(AgentName("Sage"))
ctx = await conversation_service.get_conversation_context(AgentName("Ember"))
# ctx.unseen_turns = turns since agent's last turn (SDK session persistence)

# Commands
invite = await conversation_service.create_invite(
    inviter=AgentName("Ember"),
    invitee=AgentName("Sage"),
    privacy="public",  # or "private"
    tick=current_tick,
)
conv, invite = await conversation_service.accept_invite(AgentName("Sage"), tick)
declined = await conversation_service.decline_invite(AgentName("Sage"))
conv = await conversation_service.join_conversation(AgentName("River"), conv.id, tick)
conv, was_ended = await conversation_service.leave_conversation(AgentName("Sage"), tick)
conv, turn = await conversation_service.add_turn(AgentName("Ember"), "Hello!", tick)
expired = await conversation_service.expire_invitations(current_tick)
```

**Key design decisions:**
- Position-agnostic: Must see invitee to invite (vision radius), but conversation continues at any distance
- One conversation at a time: Agents can only be in ONE conversation (simpler than ClaudeVille)
- Unseen turns only: Shows only messages since agent's last turn (SDK has session persistence)
- 2-tick invitation expiry: `INVITE_EXPIRY_TICKS = 2` in `core/conversation.py`
- Privacy set at invite time: "public" (joinable by anyone who sees a participant) or "private" (invitation only)

### 10. PerceptionBuilder (Implemented)

Builds the perception context agents receive at the start of their turn via `adapters/perception.py`:

```python
from adapters import PerceptionBuilder, AgentPerception, get_time_of_day

# Time of day from tick
time_of_day = get_time_of_day(tick)  # "morning", "afternoon", "evening", "night"

# Create builder
builder = PerceptionBuilder(
    world_service=world_service,
    agent_service=agent_service,
    haiku_client=None,  # Auto-initializes if needed
    vision_radius=3,    # 7x7 cell grid
)

# Build perception for an agent
perception = await builder.build(agent_name, tick=42)

# AgentPerception contains:
perception.grid_view          # str - Emoji grid with box-drawing walls
perception.narrative          # str - Haiku-generated atmospheric prose
perception.inventory_text     # str - "You carry: wood (3), stone (2)."
perception.journey_text       # str | None - "Traveling to X, 4 steps remaining."
perception.visible_agents_text  # str - "Sage is to the north."
perception.time_of_day        # str - "morning"
perception.weather            # Weather - Weather.CLEAR
perception.position           # Position - Position(50, 50)
```

**Grid view features:**
- Double-resolution: cell content at even coordinates, walls at odd
- Box-drawing characters for walls: │─┌┐└┘├┤┬┴┼
- Doors render as gaps (spaces) in walls
- Priority: @ (self) > 👤 (agents) > 📜✨ (objects) > terrain emoji
- Clamped to world bounds at edges

**Symbol vocabulary (core/terrain.py):**
```python
TERRAIN_EMOJI = {
    Terrain.GRASS: "·",      # Small dot
    Terrain.WATER: "💧",     # Deep water (impassable)
    Terrain.COAST: "〰️",     # Shallow water (passable)
    Terrain.STONE: "🪨",     # Rocky terrain
    Terrain.SAND: "░",       # Sand (light shading)
    Terrain.FOREST: "🌲",    # Trees
    Terrain.HILL: "⛰️",      # Elevated terrain
}
OBJECT_EMOJI = {"sign": "📜", "placed_item": "✨"}
AGENT_EMOJI = "👤"
SELF_EMOJI = "@"
```

**Narrative generation:**
- Extracts features (terrain, objects, agents, standing_on) with directions
- Passes structured feature list to Haiku (not raw grid)
- Haiku generates 2-4 sentence atmospheric prose based on time/weather
- Fallback template if Haiku unavailable

**Auto-known agents:** When agents see each other, `record_meeting()` is automatically called. This enables `sense_others` to work - agents can only sense those they've previously seen.

**Note:** `sense_others` is an ACTION, not passive perception. Only agents within vision radius appear in `visible_agents_text`.

### 11. Journey State Machine

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

### 12. Terrain Generation (Implemented)

Procedural terrain generation using Wave Function Collapse via `generation/terrain.py`:

```python
from generation import generate_terrain, generate_terrain_grid

# Generate sparse terrain map (only non-grass cells)
terrain_map = generate_terrain(
    width=500,
    height=500,
    seed=12345,           # Optional, for reproducibility
    batch_size=2000,      # Cells to collapse per step (higher = faster)
    max_retries=10,       # Full restart attempts on unrecoverable contradiction
)
# Returns: dict[Position, Terrain] - only non-grass cells

# Generate full 2D grid (for visualization)
grid = generate_terrain_grid(width=100, height=100, seed=42)
# Returns: list[list[Terrain]] indexed as grid[y][x]
```

**WFC Algorithm:**
- Creates natural terrain gradients via adjacency rules
- Batched collapse for performance (batch_size=2000 for 500x500)
- **Backtracking on contradictions** (snapshot_interval=10000, max_backtracks=50)
- Full restart only after exhausting backtracks
- Heap-based cell selection (O(n + k log n) vs O(n log n))
- Spatial hashing for efficient batch distance checks
- Self-affinity weights from "Addison's World" tuning

**Terrain adjacency graph:**
```
water ↔ coast ↔ sand ↔ grass ↔ forest
                         ↕       ↕
                       hill  ↔  hill
                         ↕
                       stone
```

**7 terrain types:**
| Terrain | Symbol | Passable | Gather | Notes |
|---------|--------|----------|--------|-------|
| WATER | ≈ | No | - | Deep water, impassable |
| COAST | ~ | Yes | - | Shallow water, wade-able |
| SAND | : | Yes | clay | Beaches |
| GRASS | . | Yes | grass | Plains, most common |
| FOREST | ♣ | Yes | wood | Wooded areas |
| HILL | ^ | Yes | - | Elevated terrain |
| STONE | ▲ | Yes | stone | Rocky outcrops |

**World dimensions:** Default 500x500 (configurable)

### 12b. World Initialization (Implemented)

The `--init` command in `main.py` bootstraps a new world:

```python
# In main.py
async def init_world(data_dir: Path) -> int:
    # 1. Generate terrain via WFC (500x500, ~10-30 seconds)
    terrain_map = generate_terrain(width=500, height=500, batch_size=2000)

    # 2. Find valid agent positions (BFS path connectivity)
    positions = find_agent_positions(terrain_map, 500, 500, num_agents=3)
    # Positions are 30-60 cells apart (Manhattan), on grass, path-connected

    # 3. Create agents with personalities from DEFAULT_AGENTS
    # 4. Create home directories (journal.md, notes.md, discoveries.md)
```

**Agent position finding** (`find_agent_positions()`):
- Agents spawn on grass terrain (not in `terrain_map`)
- 30-60 cell Manhattan distance between any two agents
- BFS verifies passable path exists between all agents
- Searches near world center (±100 cells) for valid clusters
- Max 100 attempts before raising RuntimeError

### 13. Engine Core (Implemented)

The engine orchestrates the tick pipeline via `engine/engine.py`:

```python
from engine import HearthEngine, EngineRunner, TickContext

# Create engine with storage
engine = HearthEngine(storage, vision_radius=3)  # vision_radius is single source of truth

# Initialize from storage (loads current tick)
await engine.initialize()

# Execute one tick
ctx = await engine.tick_once()

# Access services
engine.world_service         # WorldService
engine.agent_service         # AgentService
engine.action_engine         # ActionEngine
engine.narrator              # Narrator
engine.perception_builder    # PerceptionBuilder
engine.conversation_service  # ConversationService
engine.observer              # ObserverAPI for TUI queries

# Observer commands
engine.force_turn(AgentName("Ember"))  # Prioritize agent in their cluster
```

**Tick Pipeline (6 phases):**
1. **InvitationExpiryPhase** - Expire unanswered invitations (after 2 ticks)
2. **WakePhase** - Wake sleeping agents (on morning, visitors, etc.)
3. **SchedulePhase** - Compute clusters, determine execution order
4. **MovementPhase** - Advance journeys, check for interrupts (other agents in vision)
5. **AgentTurnPhase** - Execute agent turns with LLM integration
6. **CommitPhase** - Persist events to storage, update tick counter

**TickContext** is a frozen dataclass passed through phases:
```python
@dataclass(frozen=True)
class TickContext:
    tick: int
    time_of_day: str  # "morning", "afternoon", "evening", "night"
    weather: Weather
    agents: dict[AgentName, Agent]  # Snapshot at tick start

    # Accumulated by phases
    agents_to_act: frozenset[AgentName]
    agents_to_wake: frozenset[AgentName]
    clusters: tuple[tuple[AgentName, ...], ...]
    events: tuple[DomainEvent, ...]
    turn_results: dict[AgentName, TurnResult]

    # Transformation methods
    def with_agents_to_act(self, agents) -> TickContext: ...
    def with_clusters(self, clusters) -> TickContext: ...
    def append_events(self, events) -> TickContext: ...
```

### 14. Scheduler (Implemented)

Cluster-based scheduling via `services/scheduler.py`:

```python
from services import Scheduler

scheduler = Scheduler(vision_radius=3)  # cluster_radius = vision_radius + 2

# Compute clusters using union-find algorithm
clusters = scheduler.compute_clusters(agents)
# Returns: [[AgentName("Ember"), AgentName("Sage")], [AgentName("River")]]

# Force an agent to act first in their cluster
scheduler.force_next(AgentName("Sage"))
```

**Key design decisions:**
- **Active agents act every tick** - sleeping and journeying agents are excluded
- **Journey trance mode** - agents on journeys skip turns until interrupted or arrived
- **Cluster radius** = vision_radius + CLUSTER_BUFFER (2) - for agents approaching each other
- **Union-find algorithm** for efficient clustering
- **Parallel execution** between clusters (asyncio.gather)
- **Sequential execution** within clusters (round-robin, so agents see each other's actions)

### 15. EngineRunner (Implemented)

Persistent thread for TUI integration via `engine/runner.py`:

```python
from engine import EngineRunner

runner = EngineRunner(engine)

# Start background thread
runner.start()

# Thread-safe commands (from TUI)
runner.request_tick()          # Single tick
runner.request_run()           # Continuous mode
runner.request_run(count=10)   # Run N ticks
runner.request_pause()         # Pause continuous
runner.stop()                  # Clean shutdown

# Register callback for TUI updates
def on_tick_complete(ctx: TickContext):
    update_tui(ctx)
runner.on_tick(on_tick_complete)

# Check state
runner.is_running   # Thread alive?
runner.is_paused    # Continuous mode paused?
```

**Why a dedicated thread?**
- TUI runs in main thread with Textual
- Engine needs its own asyncio event loop
- Background tasks (streaming) survive across ticks
- Queue-based command interface for thread safety

### 16. Vision Constants (core/constants.py)

```python
from core.constants import HEARTH_TZ, DEFAULT_VISION_RADIUS, NIGHT_VISION_MODIFIER

# Timezone for all timestamps
HEARTH_TZ = ZoneInfo("America/New_York")

# Vision settings
DEFAULT_VISION_RADIUS = 3      # 7x7 grid (3 cells each direction)
NIGHT_VISION_MODIFIER = 0.6    # Night vision is 60% of day vision
```

Vision radius flows from HearthEngine to:
- PerceptionBuilder (grid view, narrative)
- ActionEngine (visibility checks for invite, approach, join_conversation)
- Scheduler (cluster_radius = vision_radius + 2)
- MovementPhase (journey interrupts)

**Night vision consistency:** ActionEngine applies NIGHT_VISION_MODIFIER via `set_time_of_day()` method called before action execution. All visibility checks (not just perception) respect reduced night vision.

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

### Storage Architecture

**SQLite is authoritative. Events are audit-only.**

```
data/
├── world.db                 # THE source of truth
│   ├── world_state         # Tick, weather, dimensions
│   ├── cells               # Sparse terrain/walls
│   ├── objects             # Signs, placed items
│   ├── agents              # Agent state
│   ├── inventory_stacks    # Stackable resources
│   ├── inventory_items     # Unique items
│   ├── named_places        # Quick lookup
│   └── structures          # Detected enclosures
│
├── events.jsonl             # Audit trail (never replayed)
│   └── {"tick": 1, "type": "agent_moved", ...}
│
└── snapshots/               # Optional backups
    └── snapshot_1000.db
```

Why no event replay? Agent memories are never erased, so no need for time-travel. SQLite WAL mode is crash-safe. Simpler code, faster startup.

---

## Testing Strategy

- **Unit tests**: Core models, physics rules, action validation
- **Integration tests**: Full tick cycles, LLM interactions
- **No mocking LLMs in integration tests**: Use real Haiku (fast, cheap)
- **Slow tests auto-skip**: Tests marked `@pytest.mark.slow` are skipped by default

```bash
# Run all tests (slow tests auto-skipped)
uv run pytest tests/

# Run with parallel execution (faster)
uv run pytest tests/ -n 8

# Include slow tests (API calls, large grids)
uv run pytest tests/ --run-slow

# Only integration tests (needs ANTHROPIC_API_KEY)
uv run pytest tests/integration/ --run-slow
```

**Slow test markers:**
- Narrator integration tests (Haiku API calls)
- Perception integration tests (Haiku API calls)
- Large terrain generation tests (100x100, 500x500 WFC)
- Pathfinding no-path test (explores entire 500x500 grid)

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
