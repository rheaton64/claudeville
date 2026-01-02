# Hearth - Implementation Checklist

This document tracks progress on building Hearth, the grid-based evolution of ClaudeVille.
Reference: `DESIGN.md` for full specification.

---

## Current Status

**Phase**: Phase 2 Complete
**Last Updated**: 2026-01-02
**Next Step**: Phase 3 - Storage Layer

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

## Phase 3: Storage Layer

- [ ] `storage/database.py` - SQLite connection, base operations
- [ ] Database schema design (cells, objects, agents, inventory)
- [ ] `storage/migrations/` - Initial schema migration
- [ ] `storage/event_log.py` - JSONL append operations
- [ ] `storage/snapshots.py` - Periodic snapshot logic
- [ ] `storage/repository.py` - High-level data access
- [ ] Unit tests for storage

---

## Phase 4: World Service

- [ ] `services/world_service.py` - Grid state management
- [ ] Spatial queries (cells in region, objects at position)
- [ ] Terrain property lookups
- [ ] Object placement/removal
- [ ] Wall placement/removal on cell edges
- [ ] Structure detection (recognize when walls enclose an area)
- [ ] Interior cell properties (privacy; weather protection TBD)
- [ ] Named places registry
- [ ] Unit tests for world service

---

## Phase 5: Agent Service

- [ ] `services/agent_service.py` - Agent roster management
- [ ] Agent state (position, inventory, journey)
- [ ] Journey state machine (traveling, interrupted, arrived)
- [ ] Inventory operations (add, remove, query)
- [ ] Presence sensing (direction to other agents)
- [ ] Agent home directories setup (`agents/{name}/`)
- [ ] Status file generation (`.status` - system-maintained, R/O for agent)
- [ ] Initialize personal files (`journal.md`, `notes.md`, `discoveries.md`)
- [ ] Unit tests for agent service

---

## Phase 6: Action System

### Action Definitions
- [ ] `core/actions.py` - Action type definitions
- [ ] Movement actions: walk, approach, journey
- [ ] Perception actions: look, examine, sense_others
- [ ] Interaction actions: take, drop, give, gather
- [ ] Material actions: combine, work, apply
- [ ] Building actions: build_shelter, place_wall, place_door, place, remove_wall
- [ ] Expression actions: write_sign, read_sign, name_place
- [ ] Social actions: speak, invite, accept_invite, decline_invite, join_conversation, leave_conversation
- [ ] State actions: rest, sleep

### Action Engine
- [ ] `services/action_engine.py` - Validates and executes actions
- [ ] Prerequisite checking (inventory, position, etc.)
- [ ] Deterministic outcome computation
- [ ] Effect generation
- [ ] Action result structures
- [ ] Unit tests for each action type

---

## Phase 7: Crafting System

- [ ] `config/recipes.yaml` - Recipe definitions
- [ ] `services/crafting.py` - Recipe lookup and matching
- [ ] Material property system
- [ ] Discovery hints generation
- [ ] Technique vocabulary (hollow, flatten, carve, etc.)
- [ ] Unit tests for crafting

---

## Phase 8: Narrator Service

- [ ] `adapters/haiku_provider.py` - Haiku API integration
- [ ] `services/narrator.py` - Result to prose transformation
- [ ] Narrator prompt design
- [ ] Context building (time, weather, location)
- [ ] Success/failure narrative templates
- [ ] Integration tests with Haiku

---

## Phase 9: Perception Builder

- [ ] `adapters/perception.py` - Build agent context
- [ ] Grid view generation (ASCII/Unicode)
- [ ] Symbol vocabulary implementation
- [ ] Narrative description generation (via Haiku or template)
- [ ] Inventory state formatting
- [ ] Journey state formatting
- [ ] Sense of others formatting
- [ ] Integration tests

---

## Phase 10: Vision System

- [ ] `engine/vision.py` - Visibility calculation
- [ ] Simple radius implementation
- [ ] Cells in radius query
- [ ] (Future) Raycasting through terrain
- [ ] Vision radius by time of day
- [ ] Unit tests

---

## Phase 11: Engine Core

### Tick Pipeline
- [ ] `engine/engine.py` - Main orchestrator
- [ ] `engine/context.py` - Tick context
- [ ] `engine/phases/schedule.py` - Who acts this tick
- [ ] `engine/phases/movement.py` - Journey progression, interrupts
- [ ] `engine/phases/agent_turn.py` - LLM call orchestration
- [ ] `engine/phases/effects.py` - Apply effects to state

### Scheduler
- [ ] `services/scheduler.py` - Priority-based scheduling
- [ ] Turn scheduling (solo vs clustered agents)
- [ ] Journey interrupt detection
- [ ] Round-robin for close agents

---

## Phase 12: LLM Integration

- [ ] `adapters/claude_provider.py` - Agent LLM calls
- [ ] Tool definitions for all actions
- [ ] System prompt design
- [ ] Agent personality injection
- [ ] Streaming support
- [ ] `adapters/tracer.py` - Turn logging to JSONL
- [ ] Integration tests

---

## Phase 13: Conversation System

- [ ] `services/conversation.py` - Consent-based conversations
- [ ] Invitation flow
- [ ] Join/leave mechanics
- [ ] Conversation context in agent turns
- [ ] (Adapt from ClaudeVille where applicable)

---

## Phase 14: World Generation

- [ ] `generation/terrain.py` - Procedural terrain generation
- [ ] Biome distribution
- [ ] River/water placement
- [ ] Elevation (hills, valleys)
- [ ] `generation/landmarks.py` - Special place generation
- [ ] Ancient grove
- [ ] Ruins
- [ ] Crystal caves
- [ ] `generation/seeding.py` - Initial world setup
- [ ] Agent starting positions
- [ ] Initial resources

---

## Phase 15: Configuration

- [ ] `config/agents.yaml` - Agent definitions
- [ ] `config/recipes.yaml` - Crafting rules
- [ ] `config/terrain.yaml` - Terrain properties
- [ ] `config/settings.yaml` - Runtime settings
- [ ] Config loading and validation

---

## Phase 16: Observer API

- [ ] `observer/api.py` - Query and command interface
- [ ] World state queries
- [ ] Agent state queries
- [ ] Trigger event command
- [ ] Modify terrain command
- [ ] Change weather command
- [ ] Send dream command

---

## Phase 17: TUI

- [ ] `observer/tui/app.py` - Main Textual app
- [ ] Agent panels (narrative display)
- [ ] Event feed
- [ ] Schedule panel
- [ ] Minimap widget
- [ ] Follow mode toggle
- [ ] Key bindings
- [ ] Modal dialogs for observer actions

---

## Phase 18: Engine Runner

- [ ] `engine/runner.py` - Persistent thread for TUI
- [ ] Command queue (tick, run, pause, stop)
- [ ] Callback system for updates
- [ ] Background tick execution

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

## Phase 20: First Run

- [ ] Generate initial world
- [ ] Bootstrap agents
- [ ] Run first tick
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

