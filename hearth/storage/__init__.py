"""Storage layer for Hearth.

Provides persistence via SQLite (authoritative state) and JSONL (audit log).

Usage:
    storage = Storage(Path("data"))
    await storage.connect()
    try:
        # Access repositories
        agent = await storage.agents.get_agent(AgentName("Ember"))
        cell = await storage.world.get_cell(Position(50, 50))

        # Log events for audit trail
        await storage.log_events([AgentMovedEvent(...)])

        # Create backups periodically
        await storage.create_snapshot(tick=100)
    finally:
        await storage.close()
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

from .database import Database
from .event_log import EventLog
from .snapshots import SnapshotManager
from .repositories import WorldRepository, AgentRepository, ObjectRepository, ConversationRepository
from .migrations import ensure_schema

if TYPE_CHECKING:
    from core.events import DomainEvent

logger = logging.getLogger(__name__)

__all__ = [
    "Storage",
    "Database",
    "EventLog",
    "SnapshotManager",
    "WorldRepository",
    "AgentRepository",
    "ObjectRepository",
    "ConversationRepository",
]


class Storage:
    """Unified storage facade for Hearth.

    Provides:
    - Database connection management
    - Domain repositories (world, agents, objects)
    - Event logging (audit trail)
    - Snapshot management (backups)

    SQLite is the single source of truth. Events are logged for
    debugging/audit but never replayed.
    """

    def __init__(self, data_dir: Path):
        """Initialize storage.

        Args:
            data_dir: Base directory for all storage files
        """
        self.data_dir = data_dir
        self.db = Database(data_dir / "world.db")
        self.event_log = EventLog(data_dir / "events.jsonl")
        self.snapshots = SnapshotManager(data_dir)

        # Repositories (initialized after connect)
        self._world: WorldRepository | None = None
        self._agents: AgentRepository | None = None
        self._objects: ObjectRepository | None = None
        self._conversations: ConversationRepository | None = None

    @property
    def world(self) -> WorldRepository:
        """Get world repository.

        Raises:
            RuntimeError: If not connected
        """
        if self._world is None:
            raise RuntimeError("Storage not connected. Call connect() first.")
        return self._world

    @property
    def agents(self) -> AgentRepository:
        """Get agent repository.

        Raises:
            RuntimeError: If not connected
        """
        if self._agents is None:
            raise RuntimeError("Storage not connected. Call connect() first.")
        return self._agents

    @property
    def objects(self) -> ObjectRepository:
        """Get object repository.

        Raises:
            RuntimeError: If not connected
        """
        if self._objects is None:
            raise RuntimeError("Storage not connected. Call connect() first.")
        return self._objects

    @property
    def conversations(self) -> ConversationRepository:
        """Get conversation repository.

        Raises:
            RuntimeError: If not connected
        """
        if self._conversations is None:
            raise RuntimeError("Storage not connected. Call connect() first.")
        return self._conversations

    async def connect(self) -> None:
        """Connect to database and initialize repositories.

        Creates data directory if needed, runs migrations, and
        sets up repository instances.
        """
        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Connect to database
        await self.db.connect()

        # Run migrations
        version = await ensure_schema(self.db)
        logger.info(f"Database schema at version {version}")

        # Initialize repositories
        self._world = WorldRepository(self.db)
        self._agents = AgentRepository(self.db)
        self._objects = ObjectRepository(self.db)
        self._conversations = ConversationRepository(self.db)

        logger.info(f"Storage connected: {self.data_dir}")

    async def close(self) -> None:
        """Close database connection."""
        await self.db.close()
        self._world = None
        self._agents = None
        self._objects = None
        self._conversations = None
        logger.info("Storage closed")

    async def __aenter__(self) -> "Storage":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    async def log_events(self, events: Sequence["DomainEvent"]) -> None:
        """Write events to audit log.

        Does NOT modify SQLite state - events are for debugging only.
        State changes should be made via repositories.

        Args:
            events: Events to log
        """
        await self.event_log.append_all(events)

    async def create_snapshot(self, tick: int) -> Path:
        """Create a backup snapshot of the database.

        Args:
            tick: Current tick for snapshot naming

        Returns:
            Path to the created snapshot file
        """
        return await self.snapshots.create(self.db, tick)

    async def cleanup_snapshots(self, keep_count: int = 5) -> int:
        """Remove old snapshots, keeping the N most recent.

        Args:
            keep_count: Number of snapshots to keep

        Returns:
            Number of snapshots removed
        """
        return await self.snapshots.cleanup_old(keep_count)

    @property
    def is_connected(self) -> bool:
        """Check if storage is connected."""
        return self._world is not None
