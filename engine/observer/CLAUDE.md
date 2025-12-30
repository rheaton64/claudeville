# Observer Layer

Human interface for the village. Query state for display, send commands.

## Core Principle: Queries vs Commands

**Queries** (`get_*`): Read-only, safe to call freely, no side effects
**Commands** (`do_*`): Produce effects/events, may raise `ObserverError`

The TUI can safely poll queries without affecting the simulation.

## ObserverAPI (api.py)

Clean interface wrapping the engine.

```python
api = ObserverAPI(engine)

# Queries
snapshot = api.get_village_snapshot()
agent = api.get_agent_snapshot(name)
convs = api.get_conversations()
schedule = api.get_schedule_snapshot()

# Commands
api.do_trigger_event("A storm approaches...")
api.do_set_weather("rainy")
api.do_send_dream(agent_name, "A vision of...")
api.do_force_turn(agent_name)
api.do_skip_turns(agent_name, 3)
api.do_move_agent(agent_name, "garden")
api.do_set_mood(agent_name, "contemplative")
api.do_end_conversation(conv_id)
```

### Observer Powers

| Can Do | Cannot Do |
|--------|-----------|
| Trigger world events | Command agents directly |
| Change weather | Override agent decisions |
| Send dreams | Access private thoughts |
| Force/skip turns | Reset memories |
| Move agents manually | Force interactions |
| End conversations | Rewrite history |

This matches the philosophy from DESIGN.md: Observer shapes the world, not the agents.

## Display Snapshots (snapshots.py)

Read-only views optimized for TUI display:

- `VillageDisplaySnapshot` - Complete village state
- `AgentDisplaySnapshot` - Single agent with derived state
- `ConversationDisplaySnapshot` - Conversation for display
- `InviteDisplaySnapshot` - Pending invite
- `ScheduleDisplaySnapshot` - Scheduling state
- `TimeDisplaySnapshot` - Time with formatting

These add computed fields useful for display:
- `AgentDisplaySnapshot.in_conversation: bool`
- `AgentDisplaySnapshot.has_pending_invite: bool`
- `TimeDisplaySnapshot.formatted: str`

## Error Handling

```python
class ObserverError(Exception): pass
class AgentNotFoundError(ObserverError): pass
class InvalidLocationError(ObserverError): pass
class ConversationError(ObserverError): pass
```

Commands raise specific errors. TUI should catch and display gracefully.

## Adding Observer Commands

1. Add `do_*` method to `ObserverAPI`
2. Validate inputs, raise appropriate `ObserverError` if invalid
3. Create Effect or Event
4. Call `engine.apply_effect()` or `engine.commit_event()`
5. Log the action with `logger.info(f"OBSERVER_CMD | ...")`

Commands are add-only: they produce new events, never rewrite history.
