"""Tests for engine.storage.archive module."""

import pytest
import json
from pathlib import Path

from engine.storage.archive import EventArchive


class TestEventArchiveInitialization:
    """Tests for EventArchive initialization."""

    def test_creates_archive_dir(self, temp_village_dir: Path):
        """Test EventArchive creates archive directory."""
        archive = EventArchive(temp_village_dir)

        assert archive.archive_dir.exists()

    def test_points_to_active_log(self, temp_village_dir: Path):
        """Test EventArchive points to correct active log."""
        archive = EventArchive(temp_village_dir)

        assert archive.active_log == temp_village_dir / "events.jsonl"


class TestArchiveEventsBefore:
    """Tests for archiving events."""

    def test_no_active_log_returns_zero(self, temp_village_dir: Path):
        """Test archiving with no active log returns 0."""
        archive = EventArchive(temp_village_dir)

        count = archive.archive_events_before(100)

        assert count == 0

    def test_empty_log_returns_zero(self, temp_village_dir: Path):
        """Test archiving with empty log returns 0."""
        archive = EventArchive(temp_village_dir)
        archive.active_log.write_text("")

        count = archive.archive_events_before(100)

        assert count == 0

    def test_archives_old_events(self, temp_village_dir: Path):
        """Test old events are moved to archive."""
        archive = EventArchive(temp_village_dir)

        # Create events at different ticks
        events = [
            {"tick": 1, "type": "test", "data": "event1"},
            {"tick": 2, "type": "test", "data": "event2"},
            {"tick": 5, "type": "test", "data": "event3"},
            {"tick": 10, "type": "test", "data": "event4"},
        ]
        with open(archive.active_log, "w") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")

        count = archive.archive_events_before(5)

        assert count == 2  # Events at tick 1 and 2

    def test_keeps_new_events(self, temp_village_dir: Path):
        """Test new events remain in active log."""
        archive = EventArchive(temp_village_dir)

        events = [
            {"tick": 1, "type": "test", "data": "event1"},
            {"tick": 5, "type": "test", "data": "event2"},
            {"tick": 10, "type": "test", "data": "event3"},
        ]
        with open(archive.active_log, "w") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")

        archive.archive_events_before(5)

        # Check remaining events
        with open(archive.active_log) as f:
            remaining = [json.loads(line) for line in f if line.strip()]

        assert len(remaining) == 2
        assert remaining[0]["tick"] == 5
        assert remaining[1]["tick"] == 10

    def test_creates_archive_file(self, temp_village_dir: Path):
        """Test archive file is created with correct name."""
        archive = EventArchive(temp_village_dir)

        events = [
            {"tick": 1, "type": "test", "data": "event1"},
            {"tick": 3, "type": "test", "data": "event2"},
        ]
        with open(archive.active_log, "w") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")

        archive.archive_events_before(5)

        # Should create events_1_3.jsonl
        archive_files = list(archive.archive_dir.glob("events_*.jsonl"))
        assert len(archive_files) == 1
        assert "events_1_3" in archive_files[0].name

    def test_no_events_to_archive_returns_zero(self, temp_village_dir: Path):
        """Test returns 0 when no events need archiving."""
        archive = EventArchive(temp_village_dir)

        events = [
            {"tick": 10, "type": "test", "data": "event1"},
            {"tick": 20, "type": "test", "data": "event2"},
        ]
        with open(archive.active_log, "w") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")

        count = archive.archive_events_before(5)

        assert count == 0


class TestGetArchiveRanges:
    """Tests for getting archive ranges."""

    def test_no_archives_returns_empty(self, temp_village_dir: Path):
        """Test empty archive dir returns empty list."""
        archive = EventArchive(temp_village_dir)

        assert archive.get_archive_ranges() == []

    def test_returns_sorted_ranges(self, temp_village_dir: Path):
        """Test ranges are returned sorted."""
        archive = EventArchive(temp_village_dir)

        # Create archive files
        (archive.archive_dir / "events_100_200.jsonl").write_text("")
        (archive.archive_dir / "events_1_50.jsonl").write_text("")
        (archive.archive_dir / "events_51_99.jsonl").write_text("")

        ranges = archive.get_archive_ranges()

        assert ranges == [(1, 50), (51, 99), (100, 200)]


class TestLoadArchivedEvents:
    """Tests for loading archived events."""

    def test_loads_events_in_range(self, temp_village_dir: Path):
        """Test loading events within tick range."""
        archive = EventArchive(temp_village_dir)

        # Create archive file
        events = [
            {"tick": 1, "type": "test", "data": "event1"},
            {"tick": 2, "type": "test", "data": "event2"},
            {"tick": 3, "type": "test", "data": "event3"},
        ]
        archive_file = archive.archive_dir / "events_1_3.jsonl"
        with open(archive_file, "w") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")

        loaded = archive.load_archived_events(2, 3)

        assert len(loaded) == 2

    def test_no_matching_files_returns_empty(self, temp_village_dir: Path):
        """Test no matching archive files returns empty."""
        archive = EventArchive(temp_village_dir)

        loaded = archive.load_archived_events(1, 10)

        assert loaded == []

    def test_filters_by_tick_within_file(self, temp_village_dir: Path):
        """Test events are filtered by tick within archive file."""
        archive = EventArchive(temp_village_dir)

        events = [
            {"tick": 1, "type": "test"},
            {"tick": 5, "type": "test"},
            {"tick": 10, "type": "test"},
        ]
        archive_file = archive.archive_dir / "events_1_10.jsonl"
        with open(archive_file, "w") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")

        loaded = archive.load_archived_events(3, 7)

        assert len(loaded) == 1
        assert json.loads(loaded[0])["tick"] == 5
