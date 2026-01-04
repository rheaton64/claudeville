"""Tests for EventLog."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from core.types import Position, AgentName
from core.events import AgentMovedEvent, TimeAdvancedEvent, WeatherChangedEvent
from core.terrain import Weather

from storage.event_log import EventLog


class TestEventLogAppend:
    """Test event appending."""

    async def test_append_single_event(self, temp_data_dir: Path):
        """Should append a single event."""
        log = EventLog(temp_data_dir / "events.jsonl")

        event = AgentMovedEvent(
            tick=1,
            timestamp=datetime.now(timezone.utc),
            agent=AgentName("Ember"),
            from_position=Position(10, 10),
            to_position=Position(11, 10),
        )
        await log.append(event)

        assert log.path.exists()

        events = await log.read_all()
        assert len(events) == 1
        assert events[0].agent == AgentName("Ember")

    async def test_append_multiple_events(self, temp_data_dir: Path):
        """Should append multiple events atomically."""
        log = EventLog(temp_data_dir / "events.jsonl")

        events = [
            TimeAdvancedEvent(
                tick=i,
                timestamp=datetime.now(timezone.utc),
                new_tick=i,
            )
            for i in range(5)
        ]
        await log.append_all(events)

        read_events = await log.read_all()
        assert len(read_events) == 5

    async def test_append_preserves_order(self, temp_data_dir: Path):
        """Events should be read in append order."""
        log = EventLog(temp_data_dir / "events.jsonl")

        for i in range(10):
            await log.append(TimeAdvancedEvent(
                tick=i,
                timestamp=datetime.now(timezone.utc),
                new_tick=i,
            ))

        events = await log.read_all()
        for i, event in enumerate(events):
            assert event.tick == i


class TestEventLogRead:
    """Test event reading."""

    async def test_read_empty_log(self, temp_data_dir: Path):
        """Should return empty list for nonexistent file."""
        log = EventLog(temp_data_dir / "events.jsonl")
        events = await log.read_all()
        assert events == []

    async def test_tail(self, temp_data_dir: Path):
        """Should return last N events."""
        log = EventLog(temp_data_dir / "events.jsonl")

        for i in range(20):
            await log.append(TimeAdvancedEvent(
                tick=i,
                timestamp=datetime.now(timezone.utc),
                new_tick=i,
            ))

        last_5 = await log.tail(5)
        assert len(last_5) == 5
        assert last_5[0].tick == 15
        assert last_5[4].tick == 19

    async def test_tail_less_than_n(self, temp_data_dir: Path):
        """Tail should return all events if fewer than N exist."""
        log = EventLog(temp_data_dir / "events.jsonl")

        for i in range(3):
            await log.append(TimeAdvancedEvent(
                tick=i,
                timestamp=datetime.now(timezone.utc),
                new_tick=i,
            ))

        last_10 = await log.tail(10)
        assert len(last_10) == 3

    async def test_count(self, temp_data_dir: Path):
        """Should count events correctly."""
        log = EventLog(temp_data_dir / "events.jsonl")

        assert await log.count() == 0

        for i in range(7):
            await log.append(TimeAdvancedEvent(
                tick=i,
                timestamp=datetime.now(timezone.utc),
                new_tick=i,
            ))

        assert await log.count() == 7


class TestEventPolymorphism:
    """Test that different event types serialize/deserialize correctly."""

    async def test_different_event_types(self, temp_data_dir: Path):
        """Should handle different event types."""
        log = EventLog(temp_data_dir / "events.jsonl")

        events = [
            AgentMovedEvent(
                tick=1,
                timestamp=datetime.now(timezone.utc),
                agent=AgentName("Ember"),
                from_position=Position(10, 10),
                to_position=Position(11, 10),
            ),
            WeatherChangedEvent(
                tick=2,
                timestamp=datetime.now(timezone.utc),
                old_weather=Weather.CLEAR,
                new_weather=Weather.RAINY,
            ),
            TimeAdvancedEvent(
                tick=3,
                timestamp=datetime.now(timezone.utc),
                new_tick=3,
            ),
        ]
        await log.append_all(events)

        read_events = await log.read_all()
        assert len(read_events) == 3

        # Check types
        assert isinstance(read_events[0], AgentMovedEvent)
        assert isinstance(read_events[1], WeatherChangedEvent)
        assert isinstance(read_events[2], TimeAdvancedEvent)

        # Check data
        assert read_events[0].agent == AgentName("Ember")
        assert read_events[1].new_weather == Weather.RAINY
        assert read_events[2].new_tick == 3


class TestEventLogManagement:
    """Test log management operations."""

    async def test_exists(self, temp_data_dir: Path):
        """Should correctly report file existence."""
        log = EventLog(temp_data_dir / "events.jsonl")

        assert not log.exists()

        await log.append(TimeAdvancedEvent(
            tick=1,
            timestamp=datetime.now(timezone.utc),
            new_tick=1,
        ))

        assert log.exists()

    async def test_clear(self, temp_data_dir: Path):
        """Should clear the log."""
        log = EventLog(temp_data_dir / "events.jsonl")

        await log.append(TimeAdvancedEvent(
            tick=1,
            timestamp=datetime.now(timezone.utc),
            new_tick=1,
        ))
        assert log.exists()
        assert await log.count() == 1

        await log.clear()

        assert not log.exists()
        assert await log.count() == 0
