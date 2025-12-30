# Domain Layer

Pure domain models. No I/O, no side effects, no dependencies on other layers.

## Core Principle

**Immutable snapshots + discriminated unions.** All models use Pydantic with `frozen=True`. State never mutates - you create new instances.

## Key Types

| Type | Purpose |
|------|---------|
| `AgentSnapshot` | Agent state at a moment (location, mood, energy, sleep, relationships) |
| `WorldSnapshot` | World state (tick, time, weather, locations, agent_locations) |
| `Conversation` | Active conversation (participants, history, next_speaker) |
| `Invitation` | Pending conversation invite |
| `TimeSnapshot` | Current time with computed properties (period, day_number, formatted) |

## Type Aliases

```python
AgentName = NewType("AgentName", str)
LocationId = NewType("LocationId", str)
ConversationId = NewType("ConversationId", str)
```

Use these for type safety. Don't pass raw strings where these are expected.

## Effects vs Events

**Effects** = intent (what should happen)
**Events** = history (what did happen)

```
Effect -> ApplyEffectsPhase -> Event -> EventStore
```

### Effects (effects.py)

Discriminated union with `type` field. Created by phases, consumed by ApplyEffectsPhase.

- `MoveAgentEffect` - agent wants to move
- `UpdateMoodEffect` - mood changed
- `AgentSleepEffect` / `AgentWakeEffect` - sleep state
- `InviteToConversationEffect` - invite someone
- `AcceptInviteEffect` / `DeclineInviteEffect` - respond to invite
- `AddConversationTurnEffect` - spoke in conversation
- `SetNextSpeakerEffect` - suggest next speaker

### Events (events.py)

Discriminated union with `type` field. All have `tick` and `timestamp`. Written to EventStore.

- `AgentMovedEvent`, `AgentMoodChangedEvent`, `AgentSleptEvent`, etc.
- `ConversationStartedEvent`, `ConversationTurnEvent`, `ConversationEndedEvent`, etc.
- `WorldEventOccurred`, `WeatherChangedEvent`

## Adding New State

1. Add field to appropriate Snapshot in this layer
2. Add Effect in `effects.py`, add to `Effect` union
3. Add Event in `events.py`, add to `DomainEvent` union
4. Export both in `__init__.py`
5. Handle in `ApplyEffectsPhase` (effect -> event)
6. Handle in `EventStore._apply_event` (event -> snapshot update)

## Files

| File | Contents |
|------|----------|
| `types.py` | NewType aliases (AgentName, LocationId, ConversationId) |
| `agent.py` | AgentSnapshot, AgentLLMModel |
| `world.py` | WorldSnapshot, Location, Weather |
| `time.py` | TimeSnapshot, TimePeriod enum |
| `conversation.py` | Conversation, ConversationTurn, Invitation |
| `effects.py` | All Effect types + Effect union |
| `events.py` | All DomainEvent types + DomainEvent union |
