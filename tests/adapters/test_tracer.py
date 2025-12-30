"""Tests for engine.adapters.tracer module."""

import pytest
import json
import threading
from pathlib import Path
from unittest.mock import Mock, MagicMock

from engine.adapters.tracer import VillageTracer


class TestVillageTracerInitialization:
    """Tests for VillageTracer initialization."""

    def test_creates_trace_dir(self, tmp_path: Path):
        """Test trace directory is created."""
        trace_dir = tmp_path / "traces"
        tracer = VillageTracer(trace_dir)

        assert trace_dir.exists()
        assert tracer.trace_dir == trace_dir

    def test_initializes_empty_callbacks(self, tmp_path: Path):
        """Test callbacks list starts empty."""
        tracer = VillageTracer(tmp_path / "traces")

        assert tracer._callbacks == []

    def test_initializes_empty_turn_ids(self, tmp_path: Path):
        """Test turn IDs dict starts empty."""
        tracer = VillageTracer(tmp_path / "traces")

        assert tracer._turn_ids == {}


class TestCallbackManagement:
    """Tests for callback registration."""

    def test_register_callback(self, tmp_path: Path):
        """Test registering a callback."""
        tracer = VillageTracer(tmp_path / "traces")
        callback = Mock()

        tracer.register_callback(callback)

        assert callback in tracer._callbacks

    def test_unregister_callback(self, tmp_path: Path):
        """Test unregistering a callback."""
        tracer = VillageTracer(tmp_path / "traces")
        callback = Mock()
        tracer.register_callback(callback)

        tracer.unregister_callback(callback)

        assert callback not in tracer._callbacks

    def test_unregister_nonexistent_callback(self, tmp_path: Path):
        """Test unregistering callback that wasn't registered."""
        tracer = VillageTracer(tmp_path / "traces")
        callback = Mock()

        # Should not raise
        tracer.unregister_callback(callback)


class TestStartTurn:
    """Tests for start_turn method."""

    def test_returns_turn_id(self, tmp_path: Path):
        """Test start_turn returns a turn ID."""
        tracer = VillageTracer(tmp_path / "traces")

        turn_id = tracer.start_turn(
            agent_name="Ember",
            tick=5,
            location="workshop",
            model="claude-opus-4",
            context="Test context",
        )

        assert turn_id is not None
        assert len(turn_id) == 8  # UUID prefix

    def test_stores_turn_id(self, tmp_path: Path):
        """Test turn ID is stored for agent."""
        tracer = VillageTracer(tmp_path / "traces")

        turn_id = tracer.start_turn(
            agent_name="Ember",
            tick=5,
            location="workshop",
            model="claude-opus-4",
            context="Test context",
        )

        assert tracer._turn_ids["Ember"] == turn_id

    def test_writes_to_file(self, tmp_path: Path):
        """Test event is written to trace file."""
        trace_dir = tmp_path / "traces"
        tracer = VillageTracer(trace_dir)

        tracer.start_turn(
            agent_name="Ember",
            tick=5,
            location="workshop",
            model="claude-opus-4",
            context="Test context",
        )

        trace_file = trace_dir / "Ember.jsonl"
        assert trace_file.exists()

        with open(trace_file) as f:
            event = json.loads(f.readline())

        assert event["event"] == "turn_start"
        assert event["agent"] == "Ember"
        assert event["tick"] == 5
        assert event["location"] == "workshop"

    def test_notifies_callbacks(self, tmp_path: Path):
        """Test callbacks are notified."""
        tracer = VillageTracer(tmp_path / "traces")
        callback = Mock()
        tracer.register_callback(callback)

        tracer.start_turn(
            agent_name="Ember",
            tick=5,
            location="workshop",
            model="claude-opus-4",
            context="Test context",
        )

        callback.assert_called_once()
        event_type, data = callback.call_args[0]
        assert event_type == "turn_start"
        assert data["agent"] == "Ember"


class TestLogText:
    """Tests for log_text method."""

    def test_writes_text_event(self, tmp_path: Path):
        """Test text event is written."""
        trace_dir = tmp_path / "traces"
        tracer = VillageTracer(trace_dir)
        tracer.start_turn("Ember", 1, "workshop", "test", "ctx")

        tracer.log_text("Ember", "Hello, world!")

        trace_file = trace_dir / "Ember.jsonl"
        with open(trace_file) as f:
            lines = f.readlines()

        text_event = json.loads(lines[1])
        assert text_event["event"] == "text"
        assert text_event["content"] == "Hello, world!"


class TestLogToolUse:
    """Tests for log_tool_use method."""

    def test_writes_tool_use_event(self, tmp_path: Path):
        """Test tool use event is written."""
        trace_dir = tmp_path / "traces"
        tracer = VillageTracer(trace_dir)
        tracer.start_turn("Ember", 1, "workshop", "test", "ctx")

        tracer.log_tool_use(
            agent_name="Ember",
            tool_id="tool123",
            tool_name="read_file",
            tool_input={"path": "/test"},
        )

        trace_file = trace_dir / "Ember.jsonl"
        with open(trace_file) as f:
            lines = f.readlines()

        tool_event = json.loads(lines[1])
        assert tool_event["event"] == "tool_use"
        assert tool_event["tool_id"] == "tool123"
        assert tool_event["tool"] == "read_file"
        assert tool_event["input"]["path"] == "/test"


class TestLogToolResult:
    """Tests for log_tool_result method."""

    def test_writes_tool_result_event(self, tmp_path: Path):
        """Test tool result event is written."""
        trace_dir = tmp_path / "traces"
        tracer = VillageTracer(trace_dir)
        tracer.start_turn("Ember", 1, "workshop", "test", "ctx")

        tracer.log_tool_result(
            agent_name="Ember",
            tool_use_id="tool123",
            content="File contents here",
            is_error=False,
        )

        trace_file = trace_dir / "Ember.jsonl"
        with open(trace_file) as f:
            lines = f.readlines()

        result_event = json.loads(lines[1])
        assert result_event["event"] == "tool_result"
        assert result_event["tool_id"] == "tool123"
        assert result_event["result"] == "File contents here"
        assert result_event["is_error"] is False

    def test_truncates_long_content(self, tmp_path: Path):
        """Test long content is truncated."""
        trace_dir = tmp_path / "traces"
        tracer = VillageTracer(trace_dir)
        tracer.start_turn("Ember", 1, "workshop", "test", "ctx")

        long_content = "x" * 1000

        tracer.log_tool_result(
            agent_name="Ember",
            tool_use_id="tool123",
            content=long_content,
        )

        trace_file = trace_dir / "Ember.jsonl"
        with open(trace_file) as f:
            lines = f.readlines()

        result_event = json.loads(lines[1])
        assert len(result_event["result"]) == 500  # Truncated


class TestEndTurn:
    """Tests for end_turn method."""

    def test_writes_turn_end_event(self, tmp_path: Path):
        """Test turn end event is written."""
        trace_dir = tmp_path / "traces"
        tracer = VillageTracer(trace_dir)
        tracer.start_turn("Ember", 1, "workshop", "test", "ctx")

        tracer.end_turn(
            agent_name="Ember",
            narrative="A peaceful day.",
            session_id="sess123",
            duration_ms=1500,
            cost_usd=0.05,
            num_turns=2,
        )

        trace_file = trace_dir / "Ember.jsonl"
        with open(trace_file) as f:
            lines = f.readlines()

        end_event = json.loads(lines[1])
        assert end_event["event"] == "turn_end"
        assert end_event["narrative"] == "A peaceful day."
        assert end_event["session_id"] == "sess123"
        assert end_event["duration_ms"] == 1500
        assert end_event["cost_usd"] == 0.05
        assert end_event["sdk_turns"] == 2

    def test_clears_turn_id(self, tmp_path: Path):
        """Test turn ID is cleared after end."""
        tracer = VillageTracer(tmp_path / "traces")
        tracer.start_turn("Ember", 1, "workshop", "test", "ctx")

        tracer.end_turn("Ember", "Done.")

        assert tracer._turn_ids["Ember"] is None


class TestLogInterpretComplete:
    """Tests for log_interpret_complete method."""

    def test_writes_interpret_event(self, tmp_path: Path):
        """Test interpret complete event is written."""
        trace_dir = tmp_path / "traces"
        tracer = VillageTracer(trace_dir)

        # Create a mock result
        result = Mock()
        result.mood_expressed = "happy"
        result.movement = "library"
        result.proposes_moving_together = None
        result.actions_described = ("reading", "writing")
        result.wants_to_rest = False
        result.wants_to_sleep = False
        result.suggested_next_speaker = None

        tracer.log_interpret_complete("Ember", result, tick=5)

        trace_file = trace_dir / "Ember.jsonl"
        with open(trace_file) as f:
            event = json.loads(f.readline())

        assert event["event"] == "interpret_complete"
        assert event["tick"] == 5
        assert event["mood"] == "happy"
        assert event["movement"] == "library"
        assert event["actions"] == ["reading", "writing"]


class TestThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_writes(self, tmp_path: Path):
        """Test concurrent writes from multiple threads."""
        trace_dir = tmp_path / "traces"
        tracer = VillageTracer(trace_dir)

        results = []

        def write_events(agent_name: str, count: int):
            turn_id = tracer.start_turn(agent_name, 1, "workshop", "test", "ctx")
            for i in range(count):
                tracer.log_text(agent_name, f"Message {i}")
            tracer.end_turn(agent_name, "Done.")
            results.append(turn_id)

        threads = [
            threading.Thread(target=write_events, args=("Ember", 10)),
            threading.Thread(target=write_events, args=("Sage", 10)),
            threading.Thread(target=write_events, args=("River", 10)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads completed
        assert len(results) == 3

        # Each agent has their own file with correct events
        for agent in ["Ember", "Sage", "River"]:
            trace_file = trace_dir / f"{agent}.jsonl"
            assert trace_file.exists()
            with open(trace_file) as f:
                lines = f.readlines()
            # 1 start + 10 text + 1 end = 12
            assert len(lines) == 12

    def test_callback_errors_dont_break_tracing(self, tmp_path: Path):
        """Test callback exceptions don't affect other callbacks."""
        tracer = VillageTracer(tmp_path / "traces")

        # Bad callback that raises
        bad_callback = Mock(side_effect=Exception("Boom!"))
        good_callback = Mock()

        tracer.register_callback(bad_callback)
        tracer.register_callback(good_callback)

        # Should not raise, and good callback should still be called
        tracer.start_turn("Ember", 1, "workshop", "test", "ctx")

        bad_callback.assert_called_once()
        good_callback.assert_called_once()
