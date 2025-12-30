from dataclasses import dataclass
from pathlib import Path
import json
from typing import Any, TYPE_CHECKING

from engine.domain import (
    AgentSnapshot,
    WorldSnapshot,
    Conversation,
    ConversationId,
    Invitation,
    AgentName,
    UnseenConversationEnding,
)

if TYPE_CHECKING:
    from engine.services.scheduler import SchedulerState


@dataclass(frozen=True)
class VillageSnapshot:
    """Complete village state at a point in time (immutable)."""
    world: WorldSnapshot
    agents: dict[AgentName, AgentSnapshot]
    conversations: dict[ConversationId, Conversation]
    pending_invites: dict[AgentName, Invitation]
    scheduler_state: "SchedulerState | None" = None
    unseen_endings: dict[AgentName, list[UnseenConversationEnding]] | None = None

    @property
    def tick(self) -> int:
        return self.world.tick

    def to_dict(self) -> dict[str, Any]:
        result = {
            "world": self.world.model_dump(mode="json"),
            "agents": {name: agent.model_dump(mode="json") for name, agent in self.agents.items()},
            "conversations": {id: conversation.model_dump(mode="json") for id, conversation in self.conversations.items()},
            "pending_invites": {name: invite.model_dump(mode="json") for name, invite in self.pending_invites.items()},
        }
        if self.scheduler_state is not None:
            result["scheduler_state"] = self.scheduler_state.to_dict()
        if self.unseen_endings:
            result["unseen_endings"] = {
                name: [ending.model_dump(mode="json") for ending in endings]
                for name, endings in self.unseen_endings.items()
            }
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VillageSnapshot":
        scheduler_state = None
        if "scheduler_state" in data:
            # Runtime import to avoid circular dependency
            from engine.services.scheduler import SchedulerState
            scheduler_state = SchedulerState.from_dict(data["scheduler_state"])

        unseen_endings = None
        if "unseen_endings" in data:
            unseen_endings = {
                name: [UnseenConversationEnding.model_validate(ending) for ending in endings]
                for name, endings in data["unseen_endings"].items()
            }

        return cls(
            world=WorldSnapshot.model_validate(data["world"]),
            agents={name: AgentSnapshot.model_validate(agent) for name, agent in data["agents"].items()},
            conversations={id: Conversation.model_validate(conversation) for id, conversation in data["conversations"].items()},
            pending_invites={
                name: Invitation.model_validate(invite)
                for name, invite in data.get("pending_invites", {}).items()
            },
            scheduler_state=scheduler_state,
            unseen_endings=unseen_endings,
        )

class SnapshotStore:
    """Handles saving and loading village snapshots."""
    def __init__(self, village_root: Path):
        self.village_root = village_root
        self.snapshots_dir = village_root / "snapshots"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

    def save(self, snapshot: VillageSnapshot) -> Path:
        """Save a snapshot to disk. Returns the path to the saved snapshot."""
        path = self.snapshots_dir / f"state_{snapshot.tick}.json"
        with open(path, "w") as f:
            json.dump(snapshot.to_dict(), f, indent=2, default=str)
        return path

    def load(self, tick: int) -> VillageSnapshot | None:
        """Load a snapshot from disk. Returns None if the snapshot does not exist."""
        path = self.snapshots_dir / f"state_{tick}.json"
        if not path.exists():
            return None
        with open(path, "r") as f:
            return VillageSnapshot.from_dict(json.load(f))

    def load_latest(self) -> VillageSnapshot | None:
        """Load the latest snapshot from disk. Returns None if no snapshots exist."""
        snapshots = list(self.snapshots_dir.glob("state_*.json"))
        if not snapshots:
            return None
        latest = max(snapshots, key=lambda x: int(x.stem.split("_")[1]))
        with open(latest, "r") as f:
            return VillageSnapshot.from_dict(json.load(f))

    def get_latest_tick(self) -> int | None:
        """Get the tick number of the latest snapshot. Returns None if no snapshots exist."""
        snapshots = list(self.snapshots_dir.glob("state_*.json"))
        if not snapshots:
            return None
        return max(int(x.stem.split("_")[1]) for x in snapshots)

    def list_snapshots(self) -> list[int]:
        """List all available snapshot tick numbers."""
        return sorted(
            int(x.stem.split("_")[1]) for x in self.snapshots_dir.glob("state_*.json")
        )
