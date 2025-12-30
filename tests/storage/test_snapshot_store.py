"""Tests for engine.storage.snapshot_store module."""

import pytest
from datetime import datetime
from pathlib import Path

from engine.domain import (
    AgentName,
    LocationId,
    ConversationId,
    AgentSnapshot,
    WorldSnapshot,
    Weather,
    Conversation,
    Invitation,
)
from engine.storage.snapshot_store import VillageSnapshot, SnapshotStore
from engine.services.scheduler import SchedulerState


class TestVillageSnapshot:
    """Tests for VillageSnapshot dataclass."""

    def test_creation(self, world_snapshot: WorldSnapshot, sample_agent: AgentSnapshot):
        """Test creating a VillageSnapshot."""
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
        )

        assert snapshot.world == world_snapshot
        assert sample_agent.name in snapshot.agents
        assert snapshot.scheduler_state is None

    def test_tick_property(self, world_snapshot: WorldSnapshot, sample_agent: AgentSnapshot):
        """Test tick property delegates to world."""
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
        )

        assert snapshot.tick == world_snapshot.tick

    def test_immutability(self, world_snapshot: WorldSnapshot, sample_agent: AgentSnapshot):
        """Test VillageSnapshot is frozen."""
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            snapshot.world = world_snapshot

    def test_with_scheduler_state(self, world_snapshot: WorldSnapshot, sample_agent: AgentSnapshot):
        """Test creating snapshot with scheduler state."""
        scheduler_state = SchedulerState(
            queue=(),
            forced_next=AgentName("Ember"),
            skip_counts={},
            turn_counts={},
        )
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
            scheduler_state=scheduler_state,
        )

        assert snapshot.scheduler_state is not None
        assert snapshot.scheduler_state.forced_next == AgentName("Ember")


class TestVillageSnapshotSerialization:
    """Tests for VillageSnapshot serialization."""

    def test_to_dict(self, world_snapshot: WorldSnapshot, sample_agent: AgentSnapshot):
        """Test serializing to dict."""
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
        )

        data = snapshot.to_dict()

        assert "world" in data
        assert "agents" in data
        assert "conversations" in data
        assert "pending_invites" in data

    def test_from_dict_roundtrip(self, world_snapshot: WorldSnapshot, sample_agent: AgentSnapshot):
        """Test serialization roundtrip."""
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
        )

        data = snapshot.to_dict()
        restored = VillageSnapshot.from_dict(data)

        assert restored.tick == snapshot.tick
        assert sample_agent.name in restored.agents
        assert restored.agents[sample_agent.name].name == sample_agent.name

    def test_with_conversations(
        self,
        world_snapshot: WorldSnapshot,
        sample_agent: AgentSnapshot,
        sample_conversation: Conversation,
    ):
        """Test roundtrip with conversations."""
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={sample_conversation.id: sample_conversation},
            pending_invites={},
        )

        data = snapshot.to_dict()
        restored = VillageSnapshot.from_dict(data)

        assert sample_conversation.id in restored.conversations

    def test_with_invites(
        self,
        world_snapshot: WorldSnapshot,
        sample_agent: AgentSnapshot,
        sample_invitation: Invitation,
    ):
        """Test roundtrip with pending invites."""
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={sample_invitation.invitee: sample_invitation},
        )

        data = snapshot.to_dict()
        restored = VillageSnapshot.from_dict(data)

        assert sample_invitation.invitee in restored.pending_invites

    def test_with_scheduler_state_roundtrip(self, world_snapshot: WorldSnapshot, sample_agent: AgentSnapshot):
        """Test roundtrip with scheduler state."""
        scheduler_state = SchedulerState(
            queue=(),
            forced_next=AgentName("Ember"),
            skip_counts={AgentName("Sage"): 2},
            turn_counts={AgentName("Ember"): 10},
        )
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
            scheduler_state=scheduler_state,
        )

        data = snapshot.to_dict()
        restored = VillageSnapshot.from_dict(data)

        assert restored.scheduler_state is not None
        assert restored.scheduler_state.forced_next == AgentName("Ember")
        assert restored.scheduler_state.skip_counts[AgentName("Sage")] == 2


class TestSnapshotStore:
    """Tests for SnapshotStore."""

    def test_creates_snapshots_dir(self, temp_village_dir: Path):
        """Test SnapshotStore creates snapshots directory."""
        store = SnapshotStore(temp_village_dir)

        assert store.snapshots_dir.exists()

    def test_save_snapshot(self, temp_village_dir: Path, world_snapshot: WorldSnapshot, sample_agent: AgentSnapshot):
        """Test saving a snapshot."""
        store = SnapshotStore(temp_village_dir)
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
        )

        path = store.save(snapshot)

        assert path.exists()
        assert path.name == f"state_{snapshot.tick}.json"

    def test_load_snapshot(self, temp_village_dir: Path, world_snapshot: WorldSnapshot, sample_agent: AgentSnapshot):
        """Test loading a saved snapshot."""
        store = SnapshotStore(temp_village_dir)
        snapshot = VillageSnapshot(
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
        )
        store.save(snapshot)

        loaded = store.load(snapshot.tick)

        assert loaded is not None
        assert loaded.tick == snapshot.tick
        assert sample_agent.name in loaded.agents

    def test_load_nonexistent_returns_none(self, temp_village_dir: Path):
        """Test loading nonexistent snapshot returns None."""
        store = SnapshotStore(temp_village_dir)

        loaded = store.load(999)

        assert loaded is None

    def test_load_latest(self, temp_village_dir: Path, sample_agent: AgentSnapshot, all_locations):
        """Test loading the latest snapshot."""
        store = SnapshotStore(temp_village_dir)

        # Save multiple snapshots
        for tick in [1, 5, 10]:
            world = WorldSnapshot(
                tick=tick,
                world_time=datetime.now(),
                start_date=datetime(2024, 6, 15, 0, 0, 0),
                weather=Weather.CLEAR,
                locations=all_locations,
                agent_locations={sample_agent.name: sample_agent.location},
            )
            snapshot = VillageSnapshot(
                world=world,
                agents={sample_agent.name: sample_agent},
                conversations={},
                pending_invites={},
            )
            store.save(snapshot)

        latest = store.load_latest()

        assert latest is not None
        assert latest.tick == 10

    def test_load_latest_empty_returns_none(self, temp_village_dir: Path):
        """Test load_latest with no snapshots returns None."""
        store = SnapshotStore(temp_village_dir)

        latest = store.load_latest()

        assert latest is None

    def test_get_latest_tick(self, temp_village_dir: Path, sample_agent: AgentSnapshot, all_locations):
        """Test getting the latest tick number."""
        store = SnapshotStore(temp_village_dir)

        for tick in [1, 5, 10]:
            world = WorldSnapshot(
                tick=tick,
                world_time=datetime.now(),
                start_date=datetime(2024, 6, 15, 0, 0, 0),
                weather=Weather.CLEAR,
                locations=all_locations,
                agent_locations={sample_agent.name: sample_agent.location},
            )
            snapshot = VillageSnapshot(
                world=world,
                agents={sample_agent.name: sample_agent},
                conversations={},
                pending_invites={},
            )
            store.save(snapshot)

        assert store.get_latest_tick() == 10

    def test_get_latest_tick_empty_returns_none(self, temp_village_dir: Path):
        """Test get_latest_tick with no snapshots returns None."""
        store = SnapshotStore(temp_village_dir)

        assert store.get_latest_tick() is None

    def test_list_snapshots(self, temp_village_dir: Path, sample_agent: AgentSnapshot, all_locations):
        """Test listing all snapshot ticks."""
        store = SnapshotStore(temp_village_dir)

        for tick in [5, 1, 10]:  # Out of order
            world = WorldSnapshot(
                tick=tick,
                world_time=datetime.now(),
                start_date=datetime(2024, 6, 15, 0, 0, 0),
                weather=Weather.CLEAR,
                locations=all_locations,
                agent_locations={sample_agent.name: sample_agent.location},
            )
            snapshot = VillageSnapshot(
                world=world,
                agents={sample_agent.name: sample_agent},
                conversations={},
                pending_invites={},
            )
            store.save(snapshot)

        ticks = store.list_snapshots()

        assert ticks == [1, 5, 10]  # Sorted

    def test_list_snapshots_empty(self, temp_village_dir: Path):
        """Test listing snapshots when none exist."""
        store = SnapshotStore(temp_village_dir)

        assert store.list_snapshots() == []
