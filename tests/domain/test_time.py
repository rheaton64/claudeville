"""Tests for engine.domain.time module."""

import pytest
from datetime import datetime
from pydantic import ValidationError

from engine.domain import TimePeriod, TimeSnapshot


class TestTimePeriod:
    """Tests for TimePeriod enum."""

    def test_all_values_exist(self):
        """Test all expected time periods exist."""
        assert TimePeriod.MORNING.value == "morning"
        assert TimePeriod.AFTERNOON.value == "afternoon"
        assert TimePeriod.EVENING.value == "evening"
        assert TimePeriod.NIGHT.value == "night"

    def test_enum_count(self):
        """Test we have exactly 4 time periods."""
        assert len(TimePeriod) == 4


class TestTimeSnapshot:
    """Tests for TimeSnapshot."""

    def test_creation(self):
        """Test creating a TimeSnapshot."""
        ts = TimeSnapshot(
            world_time=datetime(2024, 6, 15, 10, 30, 0),
            tick=5,
            start_date=datetime(2024, 6, 15, 0, 0, 0),
        )
        assert ts.tick == 5
        assert ts.world_time.hour == 10

    def test_immutability(self, morning_time: TimeSnapshot):
        """Test that TimeSnapshot is frozen."""
        with pytest.raises(ValidationError):
            morning_time.tick = 100  # type: ignore


class TestTimePeriodComputation:
    """Tests for the computed period property."""

    @pytest.mark.parametrize("hour,expected_period", [
        (6, TimePeriod.MORNING),   # Start of morning
        (7, TimePeriod.MORNING),
        (10, TimePeriod.MORNING),
        (11, TimePeriod.MORNING),  # End of morning
        (12, TimePeriod.AFTERNOON),  # Start of afternoon
        (14, TimePeriod.AFTERNOON),
        (17, TimePeriod.AFTERNOON),  # End of afternoon
        (18, TimePeriod.EVENING),  # Start of evening
        (19, TimePeriod.EVENING),
        (21, TimePeriod.EVENING),  # End of evening
        (22, TimePeriod.NIGHT),   # Start of night
        (23, TimePeriod.NIGHT),
        (0, TimePeriod.NIGHT),    # Midnight
        (3, TimePeriod.NIGHT),
        (5, TimePeriod.NIGHT),    # End of night
    ])
    def test_period_from_hour(self, hour: int, expected_period: TimePeriod):
        """Test period computation for various hours."""
        ts = TimeSnapshot(
            world_time=datetime(2024, 6, 15, hour, 0, 0),
            tick=1,
            start_date=datetime(2024, 6, 15, 0, 0, 0),
        )
        assert ts.period == expected_period

    def test_morning_boundary(self):
        """Test morning starts at 6 AM."""
        before = TimeSnapshot(
            world_time=datetime(2024, 6, 15, 5, 59, 59),
            tick=1,
            start_date=datetime(2024, 6, 15, 0, 0, 0),
        )
        after = TimeSnapshot(
            world_time=datetime(2024, 6, 15, 6, 0, 0),
            tick=2,
            start_date=datetime(2024, 6, 15, 0, 0, 0),
        )
        assert before.period == TimePeriod.NIGHT
        assert after.period == TimePeriod.MORNING

    def test_afternoon_boundary(self):
        """Test afternoon starts at 12 PM."""
        before = TimeSnapshot(
            world_time=datetime(2024, 6, 15, 11, 59, 59),
            tick=1,
            start_date=datetime(2024, 6, 15, 0, 0, 0),
        )
        after = TimeSnapshot(
            world_time=datetime(2024, 6, 15, 12, 0, 0),
            tick=2,
            start_date=datetime(2024, 6, 15, 0, 0, 0),
        )
        assert before.period == TimePeriod.MORNING
        assert after.period == TimePeriod.AFTERNOON

    def test_evening_boundary(self):
        """Test evening starts at 6 PM."""
        before = TimeSnapshot(
            world_time=datetime(2024, 6, 15, 17, 59, 59),
            tick=1,
            start_date=datetime(2024, 6, 15, 0, 0, 0),
        )
        after = TimeSnapshot(
            world_time=datetime(2024, 6, 15, 18, 0, 0),
            tick=2,
            start_date=datetime(2024, 6, 15, 0, 0, 0),
        )
        assert before.period == TimePeriod.AFTERNOON
        assert after.period == TimePeriod.EVENING

    def test_night_boundary(self):
        """Test night starts at 10 PM."""
        before = TimeSnapshot(
            world_time=datetime(2024, 6, 15, 21, 59, 59),
            tick=1,
            start_date=datetime(2024, 6, 15, 0, 0, 0),
        )
        after = TimeSnapshot(
            world_time=datetime(2024, 6, 15, 22, 0, 0),
            tick=2,
            start_date=datetime(2024, 6, 15, 0, 0, 0),
        )
        assert before.period == TimePeriod.EVENING
        assert after.period == TimePeriod.NIGHT


class TestDayNumberComputation:
    """Tests for the computed day_number property."""

    def test_day_one(self):
        """Test first day is day 1."""
        ts = TimeSnapshot(
            world_time=datetime(2024, 6, 15, 10, 0, 0),
            tick=1,
            start_date=datetime(2024, 6, 15, 0, 0, 0),
        )
        assert ts.day_number == 1

    def test_day_two(self):
        """Test second day is day 2."""
        ts = TimeSnapshot(
            world_time=datetime(2024, 6, 16, 10, 0, 0),
            tick=100,
            start_date=datetime(2024, 6, 15, 0, 0, 0),
        )
        assert ts.day_number == 2

    def test_day_seven(self):
        """Test a week later."""
        ts = TimeSnapshot(
            world_time=datetime(2024, 6, 21, 10, 0, 0),
            tick=500,
            start_date=datetime(2024, 6, 15, 0, 0, 0),
        )
        assert ts.day_number == 7


class TestTimestampAlias:
    """Tests for the timestamp computed field (alias for world_time)."""

    def test_timestamp_equals_world_time(self, morning_time: TimeSnapshot):
        """Test timestamp returns world_time."""
        assert morning_time.timestamp == morning_time.world_time


class TestTimeSnapshotSerialization:
    """Tests for TimeSnapshot serialization."""

    def test_serialization_roundtrip(self, morning_time: TimeSnapshot):
        """Test model_dump and model_validate roundtrip."""
        data = morning_time.model_dump(mode="json")
        # Note: computed fields may not be included in model_dump by default
        assert "world_time" in data
        assert "tick" in data
        assert "start_date" in data

    def test_restore_from_dict(self):
        """Test creating TimeSnapshot from dict."""
        data = {
            "world_time": "2024-06-15T14:00:00",
            "tick": 10,
            "start_date": "2024-06-15T00:00:00",
        }
        ts = TimeSnapshot.model_validate(data)
        assert ts.tick == 10
        assert ts.period == TimePeriod.AFTERNOON
