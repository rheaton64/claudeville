"""Unit tests for Hearth tracer."""

import json
import pytest
from pathlib import Path

from adapters.tracer import HearthTracer
from core.types import Position


@pytest.fixture
def trace_dir(tmp_path):
    """Create a temporary trace directory."""
    return tmp_path / "traces"


@pytest.fixture
def tracer(trace_dir):
    """Create a tracer instance."""
    return HearthTracer(trace_dir)


class TestTracerInit:
    """Tests for tracer initialization."""

    def test_creates_trace_dir(self, trace_dir):
        """Tracer should create trace directory if it doesn't exist."""
        assert not trace_dir.exists()
        HearthTracer(trace_dir)
        assert trace_dir.exists()

    def test_accepts_existing_dir(self, trace_dir):
        """Tracer should accept existing directory."""
        trace_dir.mkdir(parents=True)
        tracer = HearthTracer(trace_dir)
        assert tracer.trace_dir == trace_dir


class TestCallbackRegistration:
    """Tests for callback registration."""

    def test_register_callback(self, tracer):
        """Should register a callback."""
        events = []

        def callback(event_type, data):
            events.append((event_type, data))

        tracer.register_callback(callback)

        # Trigger an event
        tracer._write_event("TestAgent", "test", {"key": "value"})

        assert len(events) == 1
        assert events[0][0] == "test"
        assert events[0][1]["key"] == "value"

    def test_unregister_callback(self, tracer):
        """Should unregister a callback."""
        events = []

        def callback(event_type, data):
            events.append((event_type, data))

        tracer.register_callback(callback)
        tracer.unregister_callback(callback)

        # Trigger an event - callback shouldn't receive it
        tracer._write_event("TestAgent", "test", {"key": "value"})

        assert len(events) == 0

    def test_multiple_callbacks(self, tracer):
        """Should support multiple callbacks."""
        events1, events2 = [], []

        def callback1(event_type, data):
            events1.append(event_type)

        def callback2(event_type, data):
            events2.append(event_type)

        tracer.register_callback(callback1)
        tracer.register_callback(callback2)

        tracer._write_event("TestAgent", "test", {})

        assert len(events1) == 1
        assert len(events2) == 1

    def test_callback_error_doesnt_break_tracing(self, tracer):
        """Callback errors should not break tracing."""
        events = []

        def bad_callback(event_type, data):
            raise ValueError("Intentional error")

        def good_callback(event_type, data):
            events.append(event_type)

        tracer.register_callback(bad_callback)
        tracer.register_callback(good_callback)

        # Should not raise
        tracer._write_event("TestAgent", "test", {})

        # Good callback should still receive event
        assert len(events) == 1


class TestTurnLifecycle:
    """Tests for turn lifecycle events."""

    def test_start_turn(self, tracer, trace_dir):
        """start_turn should log turn_start event."""
        turn_id = tracer.start_turn(
            agent_name="Ember",
            tick=42,
            position=Position(100, 100),
            model="claude-sonnet-4-5-20250514",
            context="Test context prompt",
        )

        assert turn_id  # Should return a turn ID
        assert len(turn_id) == 8  # 8-char UUID

        # Check file was created
        trace_file = trace_dir / "Ember.jsonl"
        assert trace_file.exists()

        # Check content
        with open(trace_file) as f:
            entry = json.loads(f.read().strip())

        assert entry["event"] == "turn_start"
        assert entry["agent"] == "Ember"
        assert entry["tick"] == 42
        assert entry["position"] == {"x": 100, "y": 100}
        assert entry["model"] == "claude-sonnet-4-5-20250514"
        assert entry["context"] == "Test context prompt"
        assert entry["turn_id"] == turn_id

    def test_log_text(self, tracer, trace_dir):
        """log_text should log text event."""
        tracer.start_turn("Ember", 1, Position(0, 0), "model", "context")
        tracer.log_text("Ember", "Hello, world!")

        entries = _read_all_entries(trace_dir / "Ember.jsonl")
        text_entry = entries[1]

        assert text_entry["event"] == "text"
        assert text_entry["content"] == "Hello, world!"

    def test_log_tool_use(self, tracer, trace_dir):
        """log_tool_use should log tool_use event."""
        tracer.start_turn("Ember", 1, Position(0, 0), "model", "context")
        tracer.log_tool_use(
            agent_name="Ember",
            tool_id="tool_123",
            tool_name="walk",
            tool_input={"direction": "north"},
        )

        entries = _read_all_entries(trace_dir / "Ember.jsonl")
        tool_entry = entries[1]

        assert tool_entry["event"] == "tool_use"
        assert tool_entry["tool_id"] == "tool_123"
        assert tool_entry["tool"] == "walk"
        assert tool_entry["input"] == {"direction": "north"}

    def test_log_tool_result(self, tracer, trace_dir):
        """log_tool_result should log tool_result event."""
        tracer.start_turn("Ember", 1, Position(0, 0), "model", "context")
        tracer.log_tool_result(
            agent_name="Ember",
            tool_use_id="tool_123",
            content="You walk north.",
            is_error=False,
        )

        entries = _read_all_entries(trace_dir / "Ember.jsonl")
        result_entry = entries[1]

        assert result_entry["event"] == "tool_result"
        assert result_entry["tool_id"] == "tool_123"
        assert result_entry["result"] == "You walk north."
        assert result_entry["is_error"] is False

    def test_log_tool_result_truncates_long_content(self, tracer, trace_dir):
        """log_tool_result should truncate content over 500 chars."""
        tracer.start_turn("Ember", 1, Position(0, 0), "model", "context")
        long_content = "x" * 1000
        tracer.log_tool_result("Ember", "tool_123", long_content)

        entries = _read_all_entries(trace_dir / "Ember.jsonl")
        result_entry = entries[1]

        assert len(result_entry["result"]) == 500

    def test_end_turn(self, tracer, trace_dir):
        """end_turn should log turn_end event."""
        turn_id = tracer.start_turn("Ember", 1, Position(0, 0), "model", "context")
        tracer.end_turn(
            agent_name="Ember",
            narrative="The agent rested.",
            session_id="session_abc",
            duration_ms=1500,
            cost_usd=0.01,
            num_turns=3,
        )

        entries = _read_all_entries(trace_dir / "Ember.jsonl")
        end_entry = entries[1]

        assert end_entry["event"] == "turn_end"
        assert end_entry["narrative"] == "The agent rested."
        assert end_entry["session_id"] == "session_abc"
        assert end_entry["duration_ms"] == 1500
        assert end_entry["cost_usd"] == 0.01
        assert end_entry["sdk_turns"] == 3

    def test_turn_id_cleared_after_end(self, tracer, trace_dir):
        """Turn ID should be cleared after turn ends."""
        tracer.start_turn("Ember", 1, Position(0, 0), "model", "context")
        tracer.end_turn("Ember", "Done.")

        # Start a new turn and check it gets a new ID
        tracer._write_event("Ember", "test", {})

        entries = _read_all_entries(trace_dir / "Ember.jsonl")
        last_entry = entries[-1]

        assert last_entry["turn_id"] is None


class TestTokenTracking:
    """Tests for token tracking events."""

    def test_log_token_update(self, tracer, trace_dir):
        """log_token_update should log token_update event."""
        tracer.log_token_update("Ember", 50000, threshold=150000)

        entries = _read_all_entries(trace_dir / "Ember.jsonl")
        token_entry = entries[0]

        assert token_entry["event"] == "token_update"
        assert token_entry["tokens"] == 50000
        assert token_entry["threshold"] == 150000
        assert token_entry["percent"] == 33  # 50000/150000 * 100

    def test_token_update_percent_capped_at_100(self, tracer, trace_dir):
        """Percent should be capped at 100."""
        tracer.log_token_update("Ember", 200000, threshold=150000)

        entries = _read_all_entries(trace_dir / "Ember.jsonl")
        token_entry = entries[0]

        assert token_entry["percent"] == 100


class TestLoadEntries:
    """Tests for loading trace entries."""

    def test_load_recent_entries(self, tracer, trace_dir):
        """load_recent_entries should return recent entries."""
        tracer.start_turn("Ember", 1, Position(0, 0), "model", "context")
        tracer.log_text("Ember", "Text 1")
        tracer.log_text("Ember", "Text 2")

        entries = tracer.load_recent_entries("Ember", limit=10)

        assert len(entries) == 3
        assert entries[0]["event"] == "turn_start"
        assert entries[1]["content"] == "Text 1"
        assert entries[2]["content"] == "Text 2"

    def test_load_recent_entries_with_limit(self, tracer, trace_dir):
        """load_recent_entries should respect limit."""
        tracer.start_turn("Ember", 1, Position(0, 0), "model", "context")
        for i in range(10):
            tracer.log_text("Ember", f"Text {i}")

        entries = tracer.load_recent_entries("Ember", limit=3)

        assert len(entries) == 3
        # Should be the last 3 entries
        assert entries[2]["content"] == "Text 9"

    def test_load_recent_entries_nonexistent_agent(self, tracer):
        """load_recent_entries should return empty list for unknown agent."""
        entries = tracer.load_recent_entries("Unknown")
        assert entries == []

    def test_get_turn_history(self, tracer, trace_dir):
        """get_turn_history should return events for specific turn."""
        turn_id = tracer.start_turn("Ember", 1, Position(0, 0), "model", "context")
        tracer.log_text("Ember", "Text 1")
        tracer.end_turn("Ember", "Done.")

        # Start another turn
        tracer.start_turn("Ember", 2, Position(0, 0), "model", "context")
        tracer.log_text("Ember", "Text 2")

        history = tracer.get_turn_history("Ember", turn_id)

        # Should only include events from first turn
        assert len(history) == 3
        assert all(e["turn_id"] == turn_id for e in history)


class TestPerAgentFiles:
    """Tests for per-agent trace files."""

    def test_separate_files_per_agent(self, tracer, trace_dir):
        """Each agent should have their own trace file."""
        tracer.start_turn("Ember", 1, Position(0, 0), "model", "context")
        tracer.start_turn("Sage", 1, Position(1, 1), "model", "context")
        tracer.start_turn("River", 1, Position(2, 2), "model", "context")

        assert (trace_dir / "Ember.jsonl").exists()
        assert (trace_dir / "Sage.jsonl").exists()
        assert (trace_dir / "River.jsonl").exists()

    def test_agent_events_dont_mix(self, tracer, trace_dir):
        """Events should only appear in the correct agent's file."""
        tracer.start_turn("Ember", 1, Position(0, 0), "model", "context")
        tracer.log_text("Ember", "Ember text")

        tracer.start_turn("Sage", 1, Position(1, 1), "model", "context")
        tracer.log_text("Sage", "Sage text")

        ember_entries = tracer.load_recent_entries("Ember")
        sage_entries = tracer.load_recent_entries("Sage")

        assert len(ember_entries) == 2  # turn_start + text
        assert len(sage_entries) == 2
        assert ember_entries[1]["content"] == "Ember text"
        assert sage_entries[1]["content"] == "Sage text"


def _read_all_entries(trace_file: Path) -> list[dict]:
    """Helper to read all entries from a trace file."""
    entries = []
    with open(trace_file) as f:
        for line in f:
            if line.strip():
                entries.append(json.loads(line))
    return entries
