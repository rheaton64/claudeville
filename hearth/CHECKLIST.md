# Hearth - Implementation Checklist

This document tracks progress on building Hearth, the grid-based evolution of ClaudeVille.
Reference: `DESIGN.md` for full specification.

---

## Current Status

**Phase**: Phase 20 In Progress (First Run)
**Last Updated**: 2026-01-04
**Next Step**: Run first tick with LLM integration, verify agent behavior

**Test Suite**: 663 passed, 9 skipped (slow tests auto-skip without --run-slow)

---

## Phase 1: Project Foundation ✓

- [x] Create project structure (directories)
- [x] Set up `pyproject.toml` with dependencies
- [x] Create `__init__.py` files
- [x] Set up basic logging configuration
- [x] Create `.env.example` for API keys
- [x] Add to `.gitignore` appropriately
- [x] Create test infrastructure with pytest
- [x] Verify with `uv sync` and test run

**Dependencies installed:**
- anthropic>=0.40.0, claude-agent-sdk>=0.1.0, langsmith>=0.2.0
- pydantic>=2.0.0
- aiosqlite>=0.20.0
- textual>=0.89.0
- pyyaml>=6.0.0
- pytest>=9.0.2, pytest-asyncio>=1.3.0, pytest-xdist>=3.5.0

---

## Phase 2: Core Types & Domain Models ✓

- [x] `core/types.py` - Position, Direction, Rect, basic type aliases
- [x] `core/terrain.py` - Terrain enum, Weather enum, terrain properties
- [x] `core/world.py` - Cell, Grid models (immutable, sparse storage)
- [x] Cell edge walls model (walls on north/south/east/west edges, not cells)
- [x] `core/agent.py` - Agent, Inventory (hybrid stacks + unique items), Journey models
- [x] `core/objects.py` - WorldObject, Sign, PlacedItem, Item models
- [x] `core/structures.py` - Structure model (detected from enclosed walls)
- [x] `core/events.py` - Event types for event log (discriminated union)
- [x] Unit tests for core models (157 tests total)

**Key design decisions:**
- Position is NamedTuple (fast, hashable, works as dict key)
- Actions produce Events directly (no Effect intermediate layer)
- Inventory is hybrid: stackable resources by type + unique items by UUID
- Journey supports both Position and named landmark destinations
- All models are frozen Pydantic with transformation methods

---

## Phase 3: Storage Layer ✓

- [x] `storage/database.py` - SQLite connection, base operations
- [x] Database schema design (cells, objects, agents, inventory)
- [x] `storage/migrations/` - Initial schema migration
- [x] `storage/event_log.py` - JSONL append operations
- [x] `storage/snapshots.py` - Periodic snapshot logic
- [x] `storage/repositories/` - Domain-split repositories (world, agent, object)
- [x] `storage/__init__.py` - Storage facade
- [x] Unit tests for storage (54 tests)

**Key design decisions:**
- SQLite is the single source of truth (no event replay)
- Events are audit-only for debugging (JSONL, never replayed)
- Domain-split repositories: WorldRepository, AgentRepository, ObjectRepository
- Single-table inheritance for objects with discriminator + JSON extras
- Separate tables for inventory (stacks + items)
- Hand-rolled migrations with version table
- Sparse cell storage (only non-default cells stored)
- SQLite WAL mode for crash safety

---

## Phase 4: World Service ✓

- [x] `services/world_service.py` - Grid state management
- [x] Spatial queries (cells in region, objects at position)
- [x] Terrain property lookups
- [x] Object placement/removal
- [x] Wall placement/removal on cell edges (auto-symmetric)
- [x] Structure detection (flood-fill for any enclosed shape)
- [x] Interior cell properties (privacy via Structure.is_private)
- [x] Named places registry
- [x] Unit tests for world service (46 tests)

**Key design decisions:**
- No in-memory cache - always delegates to repository
- Auto-symmetric wall placement (updates both adjacent cells)
- Flood-fill structure detection (handles irregular shapes)
- Uses existing TERRAIN_DEFAULTS for terrain properties

---

## Phase 5: Agent Service ✓

- [x] `services/agent_service.py` - Agent roster management
- [x] Agent state (position, inventory, journey)
- [x] Journey state machine (traveling, interrupted, arrived)
- [x] Inventory operations (add, remove, query)
- [x] Presence sensing (direction to other agents with categorical buckets)
- [x] Agent home directories setup (`agents/{name}/`)
- [x] Status file generation (`.status` - system-maintained, R/O for agent)
- [x] Initialize personal files (`journal.md`, `notes.md`, `discoveries.md`)
- [x] Unit tests for agent service (67 tests)

**Key design decisions:**
- Follows WorldService pattern (thin wrapper, no caching)
- Presence sensing uses categorical distance buckets: nearby (≤10), far (11-30), very far (31+)
- Simple A* pathfinding for journeys using WorldService.can_move()
- Status file includes position, time, weather, and inventory summary
- Home directory initial files have light headers only ("# Journal", etc.)

---

## Phase 6: Action System ✓

### Action Definitions
- [x] `core/actions.py` - Action type definitions (27 action types + ActionResult)
- [x] Movement actions: walk, approach, journey
- [x] Perception actions: examine, sense_others
- [x] Interaction actions: take, drop, give, gather
- [x] Material actions: combine, work, apply (stubs for Phase 7)
- [x] Building actions: build_shelter, place_wall, place_door, place_item, remove_wall
- [x] Expression actions: write_sign, read_sign, name_place
- [x] Social actions: speak, invite, accept_invite, decline_invite, join_conversation, leave_conversation (stubs for Phase 13)
- [x] State actions: sleep

### Action Engine
- [x] `services/action_engine.py` - Validates and executes actions
- [x] Prerequisite checking (inventory, position, etc.)
- [x] Deterministic outcome computation
- [x] Event generation for all actions
- [x] ActionResult with success/message/events/data
- [x] Unit tests for each action type (52 new tests, 378 total)

**Key design decisions:**
- Single ActionEngine class with handler method per action type
- All actions return ActionResult (success=True/False, message, events, data)
- Material actions (combine, work, apply) return "not implemented" until Phase 7
- Social actions (speak, invite, etc.) return "not implemented" until Phase 13
- Discriminated union pattern for Action types (matches events.py pattern)
- Handlers delegate to WorldService/AgentService for state changes

---

## Phase 7: Crafting System ✓

- [x] `config/recipes.yaml` - Recipe definitions (~27 Minecraft-inspired recipes)
- [x] `services/crafting.py` - Recipe lookup, matching, hint generation
- [x] Material property system (properties tuple on recipes and items)
- [x] Discovery hints generation (partial match hints, technique suggestions)
- [x] Technique vocabulary (split, break, strip, shape, hollow, carve, weave, flatten, grind, twist)
- [x] ActionEngine crafting handlers (combine, work, apply)
- [x] Unit tests for crafting (27 new tests for CraftingService, 17 for ActionEngine crafting, 414 total)

**Key design decisions:**
- Unified recipe system (action type is a field, not separate files)
- Minecraft-inspired recipe set with practical crafting chains
- Safe failures with hints (no material consumption on failure)
- Recipe determines if output is stackable or unique
- Apply actions preserve tool, only consume target
- Terrain updated: grass→grass, sand→clay for crafting materials

---

## Phase 8: Narrator Service ✓

- [x] `services/narrator.py` - Result to prose transformation (hybrid templates + Haiku)
- [x] Narrator prompt design (NARRATOR_SYSTEM_PROMPT)
- [x] NarratorContext for atmosphere (time, weather, action_type, position)
- [x] Template functions for simple actions (walk, rest, sleep, gather, etc.)
- [x] Haiku integration for complex actions (crafting, examine, failures)
- [x] Unit tests for templates and decision logic (28 tests)
- [x] Integration tests with Haiku (7 tests)

**Key design decisions:**
- Hybrid approach: templates for ~12 simple actions, Haiku for complex ones
- Per-action narration (true interleaving as per design doc)
- Minimal but extensible NarratorContext
- Combined service in services/narrator.py (not separate adapter)
- Fallback to message on API failures
- dotenv loading for API key management

---

## Phase 9: Perception Builder ✓

- [x] `adapters/perception.py` - Build agent context (PerceptionBuilder class)
- [x] Grid view generation (double-resolution with box-drawing walls)
- [x] Symbol vocabulary implementation (TERRAIN_EMOJI, OBJECT_EMOJI in core/terrain.py)
- [x] Narrative description generation (via Haiku LLM with feature extraction)
- [x] Inventory state formatting (_format_inventory)
- [x] Journey state formatting (_format_journey)
- [x] Visible agents formatting (_format_visible_agents) - sense_others is an action, not passive
- [x] Time of day derivation (get_time_of_day from tick)
- [x] Unit tests (56 tests in tests/adapters/test_perception.py)
- [x] Integration tests (6 tests in tests/integration/test_perception_integration.py)

**Key design decisions:**
- Double-resolution grid: cell content at even coords, walls at odd coords
- Box-drawing characters for walls (│─┌┐└┘├┤┬┴┼)
- Doors render as gaps (spaces) in walls
- Vision radius of 3 cells (7x7 grid)
- Emoji symbols for agent perception (🌲💧🪨), ASCII for TUI (separate maps)
- Haiku LLM generates atmospheric prose from structured feature list (not raw grid)
- Only visible agents shown (sense_others is an active action, not passive)

---

## Phase 10: Vision System ✓

- [x] Vision radius handled inline (no separate vision.py needed)
- [x] `core/constants.py` - Centralized vision constants (DEFAULT_VISION_RADIUS=3, NIGHT_VISION_MODIFIER=0.6)
- [x] PerceptionBuilder uses vision_radius parameter
- [x] MovementPhase uses vision_radius with night modifier
- [x] Scheduler uses vision_radius + CLUSTER_BUFFER for clustering
- [x] (Future) Raycasting through terrain - not implemented yet
- [x] Unit tests for vision-related behavior in phase tests

**Key design decisions:**
- Vision radius is a single source of truth in HearthEngine
- Passed to PerceptionBuilder, Scheduler, and MovementPhase
- Night vision is 60% of day vision (NIGHT_VISION_MODIFIER)
- No separate vision service needed - logic inline in phases

---

## Phase 11: Engine Core ✓

### Tick Pipeline
- [x] `engine/engine.py` - HearthEngine main orchestrator
- [x] `engine/context.py` - TickContext (frozen dataclass) and TurnResult
- [x] `engine/phases/base.py` - Phase protocol and TickPipeline
- [x] `engine/phases/wake.py` - WakePhase (wake on morning)
- [x] `engine/phases/schedule.py` - SchedulePhase (compute clusters, forced turns)
- [x] `engine/phases/movement.py` - MovementPhase (advance journeys, check interrupts)
- [x] `engine/phases/agent_turn.py` - AgentTurnPhase (stub - builds perception only)
- [x] `engine/phases/commit.py` - CommitPhase (persist events, update tick)
- [x] Unit tests (19 tests: context, wake, schedule)

### Scheduler
- [x] `services/scheduler.py` - Cluster-based scheduling
- [x] All agents act every tick (no turn intervals)
- [x] Union-find clustering (vision_radius + CLUSTER_BUFFER=2)
- [x] Parallel execution between clusters
- [x] Sequential execution within clusters (round-robin)
- [x] Journey interrupt detection in MovementPhase
- [x] force_next() for observer to prioritize agent

**Key design decisions:**
- No Effect intermediate layer - direct Events
- Tick-based time model (all agents act every tick)
- Cluster radius = vision_radius + 2 (buffer for approaching agents)
- AgentTurnPhase is stub - Phase 12 adds ClaudeProvider
- Conversations deferred to Phase 13

---

## Phase 12: LLM Integration ✓

- [x] `adapters/claude_provider.py` - Agent LLM calls with Claude Agent SDK
- [x] `adapters/tools.py` - 27 MCP tool definitions for all Hearth actions
- [x] `adapters/prompt_builder.py` - System and user prompt generation
- [x] Agent personality injection via DEFAULT_AGENTS hardcoded definitions
- [x] Streaming support with PersistentInputStream
- [x] Per-agent MCP servers with closures for parallel execution safety
- [x] `adapters/tracer.py` - Turn logging to per-agent JSONL files
- [x] Session persistence (session_id resume)
- [x] Token usage tracking (context window monitoring)
- [x] LangSmith integration (optional, via LANGSMITH_TRACING env var)
- [x] Agent home directory creation (journal.md, notes.md, discoveries.md)
- [x] File tools sandboxed to agent home (Read, Write, Edit, Glob, Grep)
- [x] Unit tests for tools, prompt_builder, tracer (128 adapter tests)
- [x] Integration tests for provider (11 tests, marked slow)

**Key design decisions:**
- Claude Agent SDK with persistent ClaudeSDKClient per agent
- MCP server pattern: per-agent servers with AgentToolState captured in closures
- Multi-action turns: agents can chain actions, each narrated immediately
- Tool results pass through Narrator service for atmospheric prose
- Hardcoded agent definitions in DEFAULT_AGENTS (config deferred to Phase 15):
  - Ember: Sonnet, creation/craft personality
  - Sage: Opus, knowledge/contemplation personality
  - River: Sonnet, nature/flow personality
- Social tools (speak, invite, etc.) exposed as stubs returning "not yet available"

---

## Phase 13: Conversation System ✓

### Database & Models
- [x] `storage/schema.py` - v3 migration with 4 new tables (conversations, conversation_participants, conversation_turns, conversation_invitations)
- [x] `core/conversation.py` - Domain models (Conversation, ConversationTurn, Invitation, ConversationContext)
- [x] `storage/repositories/conversation.py` - CRUD for conversations, participants, turns, invitations

### Service Layer
- [x] `services/conversation.py` - Business logic (create_invite, accept_invite, decline_invite, join_conversation, leave_conversation, add_turn, expire_invitations)
- [x] Unseen turn tracking (last_turn_tick per participant for SDK session persistence)

### Events & Actions
- [x] `core/events.py` - 7 new conversation events (InvitationSent, InvitationAccepted, InvitationDeclined, InvitationExpired, ConversationStarted, AgentJoinedConversation, AgentLeftConversation, ConversationTurn)
- [x] `services/action_engine.py` - Implemented all 6 social action handlers (speak, invite, accept_invite, decline_invite, join_conversation, leave_conversation)

### Integration
- [x] `adapters/prompt_builder.py` - Social tools documentation, conversation instructions in system prompt, invitation/conversation sections in user prompt
- [x] `adapters/perception.py` - Added conversation_text and pending_invitation_text fields to AgentPerception
- [x] `adapters/tools.py` - Enabled all social tools (removed "Not yet available")
- [x] `services/narrator.py` - Templates for speak, invite, decline_invite, leave_conversation; Haiku for accept_invite, join_conversation
- [x] `engine/phases/invitations.py` - InvitationExpiryPhase (runs at start of each tick)
- [x] `engine/engine.py` - Wired ConversationService, added InvitationExpiryPhase to pipeline

### Tests
- [x] `tests/storage/test_conversation_repo.py` - 21 repository tests
- [x] `tests/services/test_conversation.py` - 11 service tests
- [x] Updated action engine tests for social handlers

**Key design decisions:**
- Position-agnostic: Conversations continue regardless of agent movement (vision to start, any distance to maintain)
- One conversation at a time: Agents can only be in ONE conversation (simpler than ClaudeVille)
- Unseen turns only: Shows only messages since agent's last turn (SDK has session persistence)
- 2-tick invitation expiry (INVITE_EXPIRY_TICKS constant in core/conversation.py)
- Public vs private conversations (privacy set at invite time)
- SQLite persistent: Full persistence like other Hearth state

---

## Phase 14: World Generation ✓

### Terrain Generation ✓
- [x] `generation/terrain.py` - WFC procedural terrain generation
- [x] `generation/tileset.py` - 7 terrain types with adjacency rules
- [x] `generation/wfc/` - Wave Function Collapse algorithm (tile.py, grid.py, solver.py)
- [x] Auto-retry logic for WFC contradictions
- [x] World dimensions updated to 500x500
- [x] Added COAST and HILL terrain types
- [x] Unit tests for generation (15 tests, 2 slow for large grids)
- [x] Backtracking support in WFC solver (snapshot_interval, max_backtracks)
- [x] Heap-based cell selection for O(n + k log n) performance
- [x] Spatial hashing for batch distance checks

**Key design decisions:**
- WFC algorithm creates natural terrain gradients via adjacency rules
- Batched collapse for performance (batch_size=2000 for 500x500)
- Self-affinity weights from "Addison's World" tuning
- Sparse storage: only non-grass cells returned
- Auto-retry on contradictions (max_retries=10 default)
- Backtracking on contradiction before full restart (snapshot_interval=10000, max_backtracks=50)

### Landmarks (Future)
- [ ] `generation/landmarks.py` - Special place generation
- [ ] Ancient grove
- [ ] Ruins
- [ ] Crystal caves

### Initial Setup ✓
- [x] `main.py --init` - World initialization command
- [x] `find_agent_positions()` - BFS pathfinding for valid spawn locations
- [x] Agent starting positions (30-60 cells apart, on grass, path-connected)
- [x] Bulk cell insertion (`set_cells_bulk()`)
- [x] Progress bar with tqdm during terrain generation

---

## Phase 15: Configuration (Partial)

- [x] `config/agents.yaml` - Agent definitions (Ember, Sage, River with model_id and personality)
- [x] `config/recipes.yaml` - Crafting rules (~27 recipes)
- [ ] `config/terrain.yaml` - Terrain properties (deferred)
- [x] `config/settings.yaml` - Runtime settings (vision, scheduling, world, terrain_generation, agent_placement)
- [x] Config loading with backwards-compatible DEFAULT_AGENTS proxy in prompt_builder.py

---

## Phase 16: Observer API (Partial)

- [x] `observe/api.py` - Query interface (renamed from observer to avoid conflict)
- [x] World state queries (get_world_state, get_cell, get_cells_in_rect, get_terrain)
- [x] Agent state queries (get_agent, get_all_agents, get_agent_at, get_agents_in_rect)
- [x] Object queries (get_objects_at, get_objects_in_rect)
- [x] Structure queries
- [x] Named place queries
- [x] Viewport convenience method (get_viewport_data)
- [x] Unit tests for ObserverAPI (14 tests)
- [ ] Trigger event command (deferred to Phase 11+)
- [ ] Modify terrain command (deferred)
- [ ] Change weather command (deferred)
- [ ] Send dream command (deferred)

---

## Phase 17: TUI (Partial - Static Viewer)

- [x] `observe/tui/app.py` - Main Textual app (static viewer mode)
- [x] `observe/tui/widgets/grid_view.py` - Grid renderer with dynamic viewport
- [x] `observe/tui/widgets/header.py` - World state header
- [x] `observe/tui/widgets/agent_list.py` - Agent sidebar
- [x] `observe/tui/widgets/cell_info.py` - Cell details panel
- [x] `observe/tui/theme.tcss` - Textual CSS styling
- [x] Priority rendering (Agent > Object > Terrain)
- [x] Roguelike symbols (@ for focused, initials for others)
- [x] Pan controls (arrow keys)
- [x] Agent focus (1/2/3 keys)
- [x] Follow mode toggle (f key)
- [x] Center on agent (c key)
- [x] Refresh from storage (r key)
- [x] main.py updated to launch TUI
- [ ] Agent panels (narrative display) - needs engine
- [ ] Event feed - needs engine
- [ ] Schedule panel - needs engine
- [ ] Minimap widget - enhancement
- [ ] Modal dialogs for observer actions - needs commands

---

## Phase 18: Engine Runner ✓

- [x] `engine/runner.py` - Persistent thread for TUI
- [x] Command queue (tick, run, pause, stop)
- [x] Callback system for updates (on_tick)
- [x] Background tick execution with dedicated event loop
- [x] Thread-safe interface (request_tick, request_run, request_pause)

**Key design decisions:**
- Dedicated thread with persistent event loop (fixes asyncio.create_task issues)
- Queue-based command interface for thread safety
- Continuous run mode with pause support
- Daemon thread for clean shutdown

---

## Phase 19: Testing & Polish

- [ ] Unit test coverage for all services
- [ ] Integration tests for full tick cycles
- [ ] Integration tests for LLM interactions
- [ ] Error handling throughout
- [ ] Logging throughout
- [ ] README.md for hearth/
- [ ] Example configuration files

---

## Phase 20: First Run (In Progress) ✓

- [x] Generate initial world (`--init` command)
- [x] Bootstrap agents (3 agents with positions, home directories)
- [x] `--run N` batch mode command
- [ ] Run first tick with LLM integration
- [ ] Verify agent perception
- [ ] Verify action execution
- [ ] Verify narrator output
- [ ] Verify event logging
- [ ] Verify TUI display

---

## Future Enhancements (Post-MVP)

- [ ] Raycasting vision
- [ ] Weather effects on gameplay
- [ ] Day/night cycle effects
- [ ] More complex crafting
- [ ] Simulation tests
- [ ] Full grid renderer in TUI
- [ ] Multiple world support
- [ ] Agent memory/journal system

---

## Notes for Future Claude Sessions

1. **Design doc**: Always read `DESIGN.md` first for context
2. **Philosophy**: Welfare first. Structure serves being, not constrains it.
3. **Testing**: Write tests as you go, not after
4. **Separation**: Keep core/ pure (no I/O), services/ for stateful logic
5. **Storage**: SQLite for state, JSONL for events/traces
6. **Actions**: Native tool use via Claude SDK
7. **Narrator**: Stateless Haiku transformer, result → prose
8. **Ryan**: He's the creator, collaborator. He cares about getting this right.

### After Each Phase

**Always do these when completing a phase:**
- [ ] Mark phase items as complete in this file
- [ ] Update `CLAUDE.md` to reflect actual implementation
- [ ] Run tests and verify they pass
- [ ] Update session log with date and summary

---

## Session Log

| Date | Session Summary |
|------|-----------------|
| 2026-01-01 | Initial design discussion, architecture decisions, created DESIGN.md |
| 2026-01-02 | Completed Phase 1: Project foundation - directories, pyproject.toml, logging, main.py, tests |
| 2026-01-02 | Completed Phase 2: Core types and domain models - types.py, terrain.py, world.py, objects.py, structures.py, agent.py, events.py + 146 unit tests |
| 2026-01-02 | Completed Phase 3: Storage layer - SQLite as truth, JSONL audit log, domain-split repositories (world, agent, object), snapshots, 54 new tests (213 total) |
| 2026-01-02 | Completed Phase 4: World Service - spatial queries, terrain properties, object management, auto-symmetric wall placement, flood-fill structure detection, named places, movement utilities, 46 new tests (259 total) |
| 2026-01-02 | Completed Phase 5: Agent Service - roster management, state updates, inventory operations, presence sensing with categorical buckets, journey state machine with A* pathfinding, home directory management, 67 new tests (326 total) |
| 2026-01-02 | Completed Phase 6: Action System - 28 action types in core/actions.py, ActionEngine in services/action_engine.py, ActionResult with success/message/events/data, handlers for movement/perception/interaction/building/expression/state actions, stubs for crafting (Phase 7) and social (Phase 13), 52 new tests (378 total) |
| 2026-01-02 | Completed Phase 7: Crafting System - ~27 Minecraft-inspired recipes in config/recipes.yaml, CraftingService with Recipe model and hint generation, ActionEngine handlers for combine/work/apply, terrain updates (grass→grass, sand→clay), 36 new tests (414 total) |
| 2026-01-02 | Phase 16+17 (Partial): TUI Static Viewer - observe/ module (renamed from observer), ObserverAPI with query methods, GridView widget with viewport/follow/focus, header/agent list/cell info widgets, main.py integration, 14 new tests (428 total) |
| 2026-01-03 | Completed Phase 8: Narrator Service - hybrid approach with templates for simple actions (walk, rest, etc.) and Haiku LLM for complex ones (crafting, examine, failures). NarratorContext for atmosphere, NARRATOR_SYSTEM_PROMPT for Haiku guidance, 35 new tests (456 total, 7 integration) |
| 2026-01-03 | Completed Phase 9: Perception Builder - AgentPerception dataclass with grid_view, narrative, inventory/journey/visible_agents text. PerceptionBuilder class with double-resolution grid rendering (box-drawing walls), Haiku narrative generation from feature lists, time-of-day derivation. Added TERRAIN_EMOJI and OBJECT_EMOJI to core/terrain.py. 62 new tests (56 unit + 6 integration) |
| 2026-01-03 | Completed Phase 14 (Terrain): WFC terrain generation from Ryan's terrain project. 7 terrain types (added COAST, HILL), adjacency rules for natural gradients, auto-retry on contradictions, 500x500 world dimensions. Added --run-slow pytest option (slow tests auto-skip by default). 535 tests total, 16 slow. |
| 2026-01-03 | Completed Phases 10, 11, 18 (Vision + Engine Core + Runner): Vision radius handled inline with constants (NIGHT_VISION_MODIFIER). HearthEngine orchestrator wires services to tick pipeline. TickContext frozen dataclass. 5 phases: Wake→Schedule→Movement→AgentTurn(stub)→Commit. Cluster-based scheduling with union-find (vision_radius + 2). EngineRunner for TUI with dedicated thread/event loop. Scheduler with force_next(). 19 new tests (564 total). |
| 2026-01-03 | Bug Fix Session: Comprehensive code review identified 16 issues (2 reviewers). Fixed: engine.py .tick→.current_tick, events.py docstring, WakePhase persistence in SchedulePhase, night vision in PerceptionBuilder (uses NIGHT_VISION_MODIFIER), MovementPhase journey destination capture, stackable pickup logic (RESOURCE_TYPES constant), Position JSON serialization (serialize_for_narrator), look action rect clamping, approach visibility check (agents/objects must be in vision_radius), read_sign auto-find nearest (object_id now optional), journey to current position error, structure symbol (🏠). Updated CLAUDE.md (engine/ structure) and DESIGN.md (.status includes inventory). Created core/constants.py. All 564 tests pass. |
| 2026-01-03 | Completed Phase 12: LLM Integration with Claude Agent SDK. Created adapters/tools.py (28 MCP tool definitions), adapters/prompt_builder.py (system/user prompts with DEFAULT_AGENTS), adapters/tracer.py (per-agent JSONL trace files), adapters/claude_provider.py (HearthProvider with PersistentInputStream, per-agent MCP servers). Updated engine.py to wire in provider/tracer, context.py with TurnTokenUsage, agent_turn.py phase. Multi-action turns with narrated tool results. Session persistence via session_id resume. File tools sandboxed to agent home. 72 new tests (636 total, 128 adapter tests). |
| 2026-01-03 | Phase 12 Bug Fixes: Code review found 6 issues. (1) Session IDs not persisted - added update_session() call in CommitPhase. (2) Stale agent state in clusters/multi-action turns - ActionEngine.execute() now refreshes agent from DB. (3) Duplicate TurnTokenUsage class - moved to core/types.py to avoid circular import. (4) Unused lock in AgentToolState - removed dead code. (5) Rest action docs - removed references (only sleep exists). (6) Tool count 29→28. 633 tests pass. |
| 2026-01-03 | Completed Phase 13: Conversation System - Consent-based conversations adapted from ClaudeVille. New tables: conversations, conversation_participants, conversation_turns, conversation_invitations (v3 migration). Domain models: Conversation, ConversationTurn, Invitation, ConversationContext. ConversationService with full invite→accept flow. 7 conversation events. Implemented all 6 social action handlers. InvitationExpiryPhase runs at tick start. Unseen turn tracking (last_turn_tick). Position-agnostic conversations (vision to start, any distance to maintain). One conversation at a time per agent. Templates for simple social actions, Haiku for significant moments (accept, join). 32 new tests (665 total). |
| 2026-01-04 | Completed Phase 14 (Initial Setup) + Phase 20 (Partial): Implemented `--init` and `--run N` CLI commands in main.py. World initialization generates 500x500 terrain via WFC (batch_size=2000, tqdm progress bar), finds valid agent spawn positions (30-60 cells apart on grass with BFS path connectivity), creates agents and home directories. WFC solver enhanced with backtracking (snapshot_interval=10000, max_backtracks=50), heap-based cell selection, spatial hashing for batch distance. Tileset weights tuned from "Addison's World". Bulk cell insertion via set_cells_bulk(). Ready for first LLM tick test. |
| 2026-01-04 | Prompt & Tool Description Refinement: Updated all agent prompts and tool descriptions to match ClaudeVille's warm, permission-giving spirit. System prompt: restored Observer section (no metrics/evaluation), reframed tools as "verbs of being". User prompt: atmospheric time/weather formatting, softer section headers, position as "You're at (x, y)". Tool descriptions: all 27 tools updated with relational language ("reach toward", "step into"). Perception formatting: "Your hands are empty", qualitative journey progress ("almost there"), "north of you". Narrator: warmer templates and atmosphere snippets. Removed redundant `look` tool (agents get surroundings via perception). Updated tests to match new formats (663 passed). |
| 2026-01-04 | Code Review Fixes (8 issues from dual review): (1) Journey trance mode - journeying agents now skip turns until interrupted/arrived (schedule.py). (2) Direction-based object interaction - take/examine/read_sign changed from object_id to direction (north/south/east/west/down) for usability. (3) Auto-known agents - record_meeting() called when agents see each other (perception.py), enabling sense_others. (4) Night vision consistency - ActionEngine now applies NIGHT_VISION_MODIFIER to all visibility checks. (5) Stale agent state - SchedulePhase uses with_sleeping() transform. (6) Config files - created config/agents.yaml and config/settings.yaml, prompt_builder.py loads from YAML with backwards-compatible DEFAULT_AGENTS proxy. (7) Privacy validation - added _validate_privacy() helper in conversation repository. (8) Wall corner docs - added comprehensive ASCII diagram in perception.py. Updated tests for direction-based actions. 663 passed, 9 skipped. |

