"""Snapshot manager for Hearth.

Creates periodic SQLite database backups for disaster recovery.
Snapshots are optional - normal startup just opens world.db.
"""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .database import Database

logger = logging.getLogger(__name__)

# Pattern for snapshot filenames
SNAPSHOT_PATTERN = re.compile(r"snapshot_(\d+)\.db$")


class SnapshotManager:
    """Manages SQLite database snapshots.

    Creates periodic backups of the database for disaster recovery.
    Snapshots are stored as `data/snapshots/snapshot_{tick}.db`.

    Usage:
        manager = SnapshotManager(Path("data"))
        await manager.create(db, tick=100)

        # Disaster recovery
        tick, path = await manager.load_latest()
        shutil.copy(path, "data/world.db")
    """

    def __init__(self, data_dir: Path):
        """Initialize snapshot manager.

        Args:
            data_dir: Base data directory (contains world.db)
        """
        self.data_dir = data_dir
        self.snapshots_dir = data_dir / "snapshots"

    async def create(self, db: "Database", tick: int) -> Path:
        """Create a snapshot of the current database.

        Uses SQLite's backup API via file copy after ensuring
        all changes are flushed to disk.

        Args:
            db: Connected database to snapshot
            tick: Current tick number for naming

        Returns:
            Path to the created snapshot file
        """
        # Ensure snapshots directory exists
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

        # Flush any pending writes
        await db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        await db.commit()

        # Create snapshot path
        snapshot_path = self.snapshots_dir / f"snapshot_{tick}.db"

        # Copy database file
        # Note: This is safe because we just checkpointed
        shutil.copy2(db.path, snapshot_path)

        logger.info(f"Created snapshot at tick {tick}: {snapshot_path}")
        return snapshot_path

    async def list_snapshots(self) -> list[tuple[int, Path]]:
        """List all snapshots ordered by tick (ascending).

        Returns:
            List of (tick, path) tuples, ordered by tick
        """
        if not self.snapshots_dir.exists():
            return []

        snapshots = []
        for path in self.snapshots_dir.iterdir():
            match = SNAPSHOT_PATTERN.match(path.name)
            if match:
                tick = int(match.group(1))
                snapshots.append((tick, path))

        # Sort by tick ascending
        snapshots.sort(key=lambda x: x[0])
        return snapshots

    async def load_latest(self) -> tuple[int, Path] | None:
        """Get the most recent snapshot.

        Returns:
            (tick, path) for latest snapshot, or None if no snapshots exist
        """
        snapshots = await self.list_snapshots()
        if not snapshots:
            return None
        return snapshots[-1]

    async def cleanup_old(self, keep_count: int = 5) -> int:
        """Remove old snapshots, keeping the N most recent.

        Args:
            keep_count: Number of snapshots to keep

        Returns:
            Number of snapshots removed
        """
        snapshots = await self.list_snapshots()
        if len(snapshots) <= keep_count:
            return 0

        # Remove oldest snapshots
        to_remove = snapshots[:-keep_count]
        for tick, path in to_remove:
            path.unlink()
            logger.info(f"Removed old snapshot: {path}")

        return len(to_remove)

    async def get_snapshot(self, tick: int) -> Path | None:
        """Get a specific snapshot by tick.

        Args:
            tick: Tick number to get

        Returns:
            Path to snapshot, or None if not found
        """
        path = self.snapshots_dir / f"snapshot_{tick}.db"
        if path.exists():
            return path
        return None

    async def restore_from_latest(self, target_path: Path) -> int | None:
        """Restore database from latest snapshot.

        Copies the latest snapshot to the target path.

        Args:
            target_path: Where to restore the database

        Returns:
            Tick of restored snapshot, or None if no snapshots
        """
        latest = await self.load_latest()
        if latest is None:
            logger.warning("No snapshots available for restore")
            return None

        tick, snapshot_path = latest

        # Backup current if it exists
        if target_path.exists():
            backup_path = target_path.with_suffix(".db.backup")
            shutil.copy2(target_path, backup_path)
            logger.info(f"Backed up current database to {backup_path}")

        # Restore from snapshot
        shutil.copy2(snapshot_path, target_path)
        logger.info(f"Restored database from snapshot at tick {tick}")

        return tick

    def clear_all(self) -> int:
        """Remove all snapshots.

        WARNING: Destroys all backups! Use only in tests.

        Returns:
            Number of snapshots removed
        """
        if not self.snapshots_dir.exists():
            return 0

        count = 0
        for path in self.snapshots_dir.iterdir():
            if SNAPSHOT_PATTERN.match(path.name):
                path.unlink()
                count += 1

        logger.warning(f"Cleared {count} snapshot(s)")
        return count
