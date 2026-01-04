"""Event log for Hearth.

Append-only JSONL audit log for debugging and history inspection.
Events are written here but NEVER replayed - SQLite is the source of truth.
"""

from __future__ import annotations

import aiofiles
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from pydantic import TypeAdapter

from core.events import DomainEvent

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# TypeAdapter for serializing/deserializing the discriminated union
EventAdapter: TypeAdapter[DomainEvent] = TypeAdapter(DomainEvent)


class EventLog:
    """Append-only JSONL event log.

    Events are written for audit/debugging purposes only.
    They are NOT replayed - SQLite is the authoritative state store.

    Usage:
        log = EventLog(Path("data/events.jsonl"))
        await log.append(AgentMovedEvent(...))

        # For debugging
        events = await log.tail(100)
    """

    def __init__(self, path: Path):
        """Initialize event log.

        Args:
            path: Path to JSONL file
        """
        self.path = path

    async def append(self, event: DomainEvent) -> None:
        """Append a single event to the log.

        Args:
            event: Event to append
        """
        await self.append_all([event])

    async def append_all(self, events: Sequence[DomainEvent]) -> None:
        """Append multiple events atomically.

        Events are written as JSON lines, one per line.

        Args:
            events: Events to append
        """
        if not events:
            return

        # Ensure parent directory exists
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # Serialize events to JSONL
        lines = []
        for event in events:
            json_str = EventAdapter.dump_json(event, by_alias=True).decode("utf-8")
            lines.append(json_str + "\n")

        # Append atomically
        async with aiofiles.open(self.path, "a") as f:
            await f.writelines(lines)

        logger.debug(f"Appended {len(events)} event(s) to {self.path}")

    async def read_all(self) -> list[DomainEvent]:
        """Read all events from the log.

        For debugging only - not used in normal operation.

        Returns:
            List of all events
        """
        if not self.path.exists():
            return []

        events = []
        async with aiofiles.open(self.path, "r") as f:
            async for line in f:
                line = line.strip()
                if line:
                    event = EventAdapter.validate_json(line)
                    events.append(event)

        logger.debug(f"Read {len(events)} event(s) from {self.path}")
        return events

    async def tail(self, n: int = 100) -> list[DomainEvent]:
        """Read the last N events from the log.

        For debugging only - reads entire file and returns tail.
        For large logs, consider using `head -n` externally.

        Args:
            n: Number of events to return

        Returns:
            Last N events
        """
        all_events = await self.read_all()
        return all_events[-n:] if len(all_events) > n else all_events

    async def count(self) -> int:
        """Count total events in the log.

        For debugging only.

        Returns:
            Number of events
        """
        if not self.path.exists():
            return 0

        count = 0
        async with aiofiles.open(self.path, "r") as f:
            async for line in f:
                if line.strip():
                    count += 1
        return count

    async def clear(self) -> None:
        """Clear the event log.

        WARNING: Destroys all history! Use only in tests.
        """
        if self.path.exists():
            self.path.unlink()
            logger.warning(f"Cleared event log: {self.path}")

    def exists(self) -> bool:
        """Check if the log file exists.

        Returns:
            True if file exists
        """
        return self.path.exists()
