# Storage Layer

Event sourcing and persistence. All state changes flow through here as DomainEvents.

## Core Principle: Event Sourcing

```
Events are truth. Snapshots are caches.
```

State is rebuilt by replaying events. Snapshots are periodic checkpoints for fast recovery.

## EventStore (event_store.py)

The primary persistence mechanism. Single write path for all state changes.

```python
store = EventStore(village_root)
store.initialize(initial_snapshot)   # New village
store.recover()                       # Load existing village
store.append(event)                   # Write single event
store.append_all(events)              # Write batch (atomic)
store.get_current_snapshot()          # Current state
```

### Event Replay

On `recover()`:
1. Load latest snapshot
2. Read events from `events.jsonl` since snapshot tick
3. Apply each event to rebuild current state

### Snapshot Interval

`SNAPSHOT_INTERVAL = 100` ticks

Every 100 ticks, `create_snapshot_and_archive()` saves a snapshot and archives old events.

## VillageSnapshot (snapshot_store.py)

Complete village state at a point in time:

```python
@dataclass
class VillageSnapshot:
    world: WorldSnapshot
    agents: dict[AgentName, AgentSnapshot]
    conversations: dict[ConversationId, Conversation]
    pending_invites: dict[AgentName, Invitation]
    tick: int  # Computed from world.tick
```

## SnapshotStore (snapshot_store.py)

Saves/loads snapshots to `village/snapshots/`.

```python
store.save(snapshot)        # Save to snapshots/snapshot_{tick}.json
store.load_latest()         # Load most recent
store.load(tick)            # Load specific tick
```

## EventArchive (archive.py)

Moves old events to cold storage.

```python
archive.archive_events_before(tick)  # Move old events to archives/
```

Archives go to `village/archives/events_{from}_{to}.jsonl`.

## File Layout

```
village/
├── events.jsonl              # Active event log
├── snapshots/
│   ├── snapshot_100.json
│   ├── snapshot_200.json
│   └── ...
└── archives/
    ├── events_0_100.jsonl
    └── ...
```

## Adding New State

When you add new fields to domain models:

1. Add to domain layer (see domain/CLAUDE.md)
2. Update `EventStore._apply_event()` to handle new event types
3. Update `VillageSnapshot.to_dict/from_dict` if needed
4. Test with event replay to ensure state rebuilds correctly

## Key Insight

The engine never modifies snapshots directly. It:
1. Creates Effects (intent)
2. ApplyEffectsPhase converts to Events
3. Events go to EventStore
4. EventStore updates in-memory snapshot

This ensures all changes are logged and replayable.
