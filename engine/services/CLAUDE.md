# Services Layer

Stateful services and utilities. These handle scheduling, conversations, file sync, and bootstrap.

## Scheduler (scheduler.py)

Event-driven scheduler with priority queue. Manages when agents act.

```python
scheduler = Scheduler()
scheduler.schedule_agent_turn(agent, location, due_time)
scheduler.schedule_conversation_turn(conv_id, location, due_time)
scheduler.schedule_invite_response(agent, location, due_time)
```

### Pacing Constants
- `CONVERSATION_PACE_MINUTES = 5` - Conversation turns
- `SOLO_PACE_MINUTES = 120` - Solo activity
- `INVITE_RESPONSE_MINUTES = 5` - Time to respond to invite

### Priority (lower = higher priority)
1. Invite responses (priority=1)
2. Conversation turns (priority=5)
3. Agent turns (priority=10)

### Observer Modifiers
```python
scheduler.force_next_turn(agent)     # Agent acts next
scheduler.skip_turns(agent, count)   # Skip N turns
scheduler.record_turn(agent)         # Track turn counts
```

## ConversationService (conversation_service.py)

Manages conversation lifecycle. Used by ApplyEffectsPhase.

- Creates conversations when invites are accepted
- Tracks participants joining/leaving
- Handles next speaker selection

## Shared Files (shared_files.py)

Location-based shared files that agents can read/write.

```python
# Location -> shared directories
LOCATION_SHARED_DIRS = {
    "town_square": ["bulletin_board"],
    "library": ["reading_room"],
    "workshop": ["projects"],
    ...
}
```

Key functions:
- `sync_shared_files_in(agent_dir, location)` - Copy shared files to agent's `./shared/`
- `sync_shared_files_out(agent_dir, location)` - Copy agent's changes back
- `get_shared_file_list(agent_dir)` - List files for prompt

## Bootstrap (bootstrap.py)

Initial village setup.

```python
# Default agents
DEFAULT_AGENTS = [
    AgentSeed(name="Ember", model=CLAUDE_OPUS_4, location="workshop", ...),
    AgentSeed(name="Sage", model=CLAUDE_OPUS, location="library", ...),
    AgentSeed(name="River", model=CLAUDE_SONNET, location="riverbank", ...),
]

# Create initial state
snapshot = build_initial_snapshot()
```

## Dreams (dreams.py)

Observer-sent dreams that appear in agent context.

```python
append_dream(agent_dir, content)           # Write dream file
get_unseen_dreams(agent_dir, last_tick)    # Get dreams since tick
```

## Agent Registry (agent_registry.py)

Tracks agent directories and ensures structure exists.

```python
ensure_agent_directory(village_root, agent_name)
# Creates: journal/, inbox/, workspace/, home/, shared/, dreams/
```

## Files

| File | Purpose |
|------|---------|
| `scheduler.py` | `Scheduler`, `ScheduledEvent` |
| `conversation_service.py` | `ConversationService` |
| `shared_files.py` | Shared file sync utilities |
| `bootstrap.py` | Initial village setup |
| `dreams.py` | Dream file handling |
| `agent_registry.py` | Agent directory management |
