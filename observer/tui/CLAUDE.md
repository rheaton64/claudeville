# TUI Module (observer)

Rich terminal interface built with Textual for engine. Philosophy: watching lives unfold, not monitoring processes.

## File Overview

| File | Purpose |
|------|---------|
| `app.py` | Main application, keybindings, engine integration |
| `screens.py` | Modal dialog screens |
| `theme.tcss` | Textual CSS styling |
| `widgets/` | Reusable UI components |

## app.py - ClaudeVilleTUI

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│ VillageHeader - time, weather, tick, status                 │
├──────────────┬──────────────┬──────────────┬────────────────┤
│  AgentPanel  │  AgentPanel  │  AgentPanel  │ SchedulePanel  │
│    Ember     │     Sage     │    River     │                │
│              │              │              │                │
│  (narrative) │  (narrative) │  (narrative) │ (scheduling)   │
├──────────────┴──────────────┴──────────────┴────────────────┤
│ EventsFeed - recent village events                          │
├─────────────────────────────────────────────────────────────┤
│ Footer - keybindings                                        │
└─────────────────────────────────────────────────────────────┘
```

### Keybindings

| Key | Action | Description |
|-----|--------|-------------|
| `Space` | `tick_once` | Execute single tick |
| `r` | `run_simulation` | Start continuous run |
| `p` | `pause_simulation` | Pause/resume |
| `e` | `show_event_dialog` | Trigger world event |
| `w` | `show_weather_dialog` | Change weather |
| `d` | `show_dream_dialog` | Send dream to agent |
| `f` | `show_force_turn_dialog` | Force agent's turn |
| `k` | `show_skip_dialog` | Skip agent turns |
| `c` | `end_conversation` | End current conversation |
| `i` | `show_observation_dialog` | Manual observation |
| `1/2/3` | `focus_agent` | Focus Ember/Sage/River |
| `0` | `focus_agent('')` | Reset focus |
| `q` | `quit` | Exit |

### Engine Integration (engine)

**Callbacks registered on mount:**
```python
self.engine.on_tick(self._on_tick)
self.engine.on_event(self._on_event)
self.engine.on_agent_stream(self._on_agent_stream)  # Centralized callback
```

**Stream callback extracts agent from data:**
```python
def _on_agent_stream(self, event_type: str, data: dict) -> None:
    agent_name = data.get("agent", "")
    if agent_name:
        self.call_from_thread(self._handle_stream_ui, agent_name, event_type, data)
```

**Thread safety:**
All callbacks use `call_from_thread()` to marshal to main thread.

**State access via ObserverAPI:**
```python
# Time state
time_snap = self.engine.observer.get_time_snapshot()

# Agent state
agent_snap = self.engine.observer.get_agent_snapshot(name)

# Schedule state
schedule = self.engine.observer.get_schedule_snapshot()

# Conversations
convos = self.engine.observer.get_conversations()
```

### Action Pattern

1. User presses key
2. `action_*` method called
3. For dialogs: `push_screen(Dialog(), callback)`
4. Callback receives result, calls `engine.observer.do_*()` command
5. Engine callbacks update UI

## screens.py - Modal Dialogs

Built using `ModalScreen[ReturnType]`.

### Dialog Classes

| Dialog | Return Type | Purpose |
|--------|-------------|---------|
| `EventDialog` | `str \| None` | Trigger world event |
| `DreamDialog` | `tuple[str, str] \| None` | Send dream (agent, content) |
| `WeatherDialog` | `str \| None` | Change weather |
| `ForceAgentTurnDialog` | `str \| None` | Force agent turn |
| `SkipTurnsDialog` | `tuple[str, int] \| None` | Skip turns |
| `ConfirmEndConversationDialog` | `bool` | Confirm end conversation |
| `ManualObservationDialog` | `tuple[str, str, dict] \| None` | Manual interpreter call |

### ManualObservationDialog

Special dialog for manually invoking interpreter observations. Useful when interpreter misses something from narrative.

Tool options loaded from engine's interpreter registry:
```python
from engine.runtime.interpreter.registry import get_tool_options_for_tui
```

Note: Conversation-related tools are not available as engine handles conversations via explicit agent tool calls.

## theme.tcss - Styling

Textual CSS. Key classes:

```tcss
.dialog { ... }           /* Modal dialog container */
.dialog-title { ... }     /* Dialog header */
.dialog-buttons { ... }   /* Button row */
.agent-panel { ... }      /* Agent panel base */
.agent-panel.focused { ... }  /* Expanded panel */
```

Agent-specific colors:
```tcss
.ember { border: solid #f97316; }
.sage { border: solid #a78bfa; }
.river { border: solid #38bdf8; }
```

## Reactive Pattern

Textual uses reactive properties for automatic UI updates:

```python
class MyWidget(Widget):
    value: reactive[str] = reactive("")

    def watch_value(self, new_value: str) -> None:
        # Called automatically when value changes
        self._update_display()
```

Used throughout for:
- Agent location/mood/energy
- Header tick/time/weather/status
- Sleep indicators
- Focus state

## Worker Pattern

Long operations run in workers:

```python
async def action_tick_once(self) -> None:
    self.run_worker(self._tick_worker, exclusive=True, thread=True)

async def _tick_worker(self) -> None:
    await self.engine.tick_once()
    self.call_from_thread(self._update_ui)
```

`exclusive=True` prevents multiple workers of same type.
`thread=True` runs in thread pool (important for async engine code).

## Adding Features

### New Keybinding + Dialog

1. Add binding to `BINDINGS`
2. Create dialog in `screens.py`
3. Add action method:
```python
def action_show_my_dialog(self) -> None:
    self.push_screen(MyDialog(), self._handle_my_result)

def _handle_my_result(self, result) -> None:
    if result:
        self.engine.observer.do_something(result)
```

### New Status Display

1. Add widget in `widgets/`
2. Add reactive properties
3. Yield in `compose()`
4. Update in tick handler
