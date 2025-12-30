# Observer v2 Module

The human interface to ClaudeVille using engine. The Observer watches lives unfold - a window, not a door.

## Philosophy

The Observer can:
- **Watch** - See agent narratives, actions, movements
- **Trigger events** - Introduce world happenings
- **Change weather** - Shift environmental conditions
- **Send dreams** - Gentle inspirations (nudges, not commands)
- **Adjust scheduling** - Shape *when* agents act, not *what* they do

The Observer cannot:
- Tell agents what to do
- Override their decisions
- Reset or modify memories
- Force interactions

These are ethical commitments, not technical limitations.

## Module Structure

```
observer/
├── __init__.py
├── CLAUDE.md          # This file
└── tui/
    ├── __init__.py
    ├── app.py         # Main TUI application
    ├── screens.py     # Modal dialog screens
    ├── theme.tcss     # CSS styling
    └── widgets/
        ├── __init__.py
        ├── header.py         # Village header
        ├── agent_panel.py    # Agent narrative panel
        ├── events_panel.py   # Events feed
        └── schedule_panel.py # Scheduling status
```

## Differences from observer/

This module is functionally equivalent to `observer/` but integrates with `engine` instead of the original engine. Key differences:

### 1. Callback Registration

```python
# Old (observer/)
self.engine.register_tick_callback(self._on_tick)
self.engine.register_event_callback(self._on_event)
agent.register_stream_callback(...)

# New (observer/)
self.engine.on_tick(self._on_tick)
self.engine.on_event(self._on_event)
self.engine.on_agent_stream(self._on_agent_stream)  # Centralized
```

### 2. State Access via ObserverAPI

All state access goes through immutable snapshots from `engine.observer`:

```python
# Time state
time_snap = self.engine.observer.get_time_snapshot()
time_snap.day_number, time_snap.time_of_day, time_snap.clock_time

# Agent state
agent_snap = self.engine.observer.get_agent_snapshot(name)
agent_snap.location, agent_snap.mood, agent_snap.energy

# All agents
agents = self.engine.observer.get_all_agents_snapshot()

# Schedule state
schedule = self.engine.observer.get_schedule_snapshot()
schedule.pending_events, schedule.forced_next, schedule.skip_counts

# Conversations
convos = self.engine.observer.get_conversations()
```

### 3. DomainEvent Discriminated Union

Events are typed discriminated unions with a `.type` literal:

```python
def _handle_event_ui(self, event: "DomainEvent") -> None:
    events_feed.add_domain_event(event)

    # Access via type checking
    if event.type == "agent_moved":
        # event has .agent, .from_location, .to_location
    elif event.type == "conversation_started":
        # event has .initial_participants, .location
```

### 4. Centralized Streaming

Instead of per-agent callbacks, there's one centralized stream callback:

```python
def _on_agent_stream(self, event_type: str, data: dict) -> None:
    agent_name = data.get("agent", "")  # Agent name in data
    self.call_from_thread(self._handle_stream_ui, agent_name, event_type, data)
```

### 5. Event-Driven Scheduler

The scheduler uses `ScheduledEvent` with `due_time` instead of accumulated time:

```python
schedule.pending_events  # List of ScheduledEventDisplay
# Each has: target_id, event_type, location, due_time
```

### 6. No Compaction

engine doesn't use memory compaction. All compaction-related UI code has been removed:
- No `is_compacting`, `token_count`, `compact_percent` in AgentPanel
- No compaction indicators in header
- No compaction event handling

## Running

```bash
uv run python main.py
```

## Key Files

- `tui/app.py` - Main app, keybindings, engine callbacks
- `tui/screens.py` - All modal dialogs
- `tui/widgets/` - Individual UI components

See `tui/CLAUDE.md` for detailed TUI documentation.
