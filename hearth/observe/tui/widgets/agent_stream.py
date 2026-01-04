"""Agent stream panel widget showing streaming narrative and tool calls.

Adapted from ClaudeVille's observer/tui/widgets/agent_panel.py for Hearth.
Shows one agent's turn activity with streaming text and tool invocations.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, RichLog
from textual.reactive import reactive
from rich.text import Text

if TYPE_CHECKING:
    from core.agent import Agent


MODEL_DISPLAY = {
    "claude-haiku": "Haiku",
    "claude-sonnet-4-5-20250929": "Sonnet",
    "claude-opus-4-1-20250805": "Opus 4.1",
    "claude-opus-4-5-20251101": "Opus",
    "haiku": "Haiku",
    "sonnet": "Sonnet",
    "opus": "Opus",
}


class AgentStreamPanel(Vertical):
    """Panel showing one agent's streaming turn activity.

    Shows:
    - Header with agent name, model, position
    - Status bar (optional mood/energy if available)
    - RichLog for streaming narrative and tool calls
    """

    is_focused: reactive[bool] = reactive(False)
    position_x: reactive[int] = reactive(0)
    position_y: reactive[int] = reactive(0)
    is_sleeping: reactive[bool] = reactive(False)
    model: reactive[str] = reactive("")
    agent_name: reactive[str] = reactive("")

    def __init__(
        self,
        agent_name: str = "",
        model: str = "",
        position: tuple[int, int] = (0, 0),
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.agent_name = agent_name
        self.model = model
        self.position_x = position[0]
        self.position_y = position[1]
        self._is_turn_active = False

    def compose(self) -> ComposeResult:
        with Vertical(classes="stream-header"):
            yield Static(self._build_header(), classes="stream-header-content", id="header-content")
        with Vertical(classes="stream-status"):
            yield Static(self._build_status(), classes="status-content", id="status-content")
        yield RichLog(classes="stream-narrative", wrap=True, highlight=False, markup=True, id="narrative-log")

    def _build_header(self) -> Text:
        """Build the header line: Name [Model] @ (x, y) (with sleep indicator)"""
        text = Text()
        text.append(self.agent_name or "Agent", style="bold")

        # Sleep indicator
        if self.is_sleeping:
            text.append(" ZzZ", style="blue")

        # Model badge
        model_name = MODEL_DISPLAY.get(self.model, self.model or "?")
        text.append(f" [{model_name}]", style="dim")

        # Position
        text.append(f" @ ({self.position_x}, {self.position_y})", style="italic dim")

        return text

    def _build_status(self) -> Text:
        """Build the status line."""
        text = Text()
        if self._is_turn_active:
            text.append("Turn in progress...", style="cyan")
        else:
            text.append("Waiting for next turn", style="dim")
        return text

    def _refresh_header(self) -> None:
        """Refresh the header display."""
        try:
            self.query_one("#header-content", Static).update(self._build_header())
        except Exception:
            pass

    def _refresh_status(self) -> None:
        """Refresh the status display."""
        try:
            self.query_one("#status-content", Static).update(self._build_status())
        except Exception:
            pass

    def watch_position_x(self, value: int) -> None:
        self._refresh_header()

    def watch_position_y(self, value: int) -> None:
        self._refresh_header()

    def watch_is_sleeping(self, value: bool) -> None:
        self._refresh_header()

    def watch_agent_name(self, value: str) -> None:
        self._refresh_header()

    def watch_model(self, value: str) -> None:
        self._refresh_header()

    def watch_is_focused(self, focused: bool) -> None:
        """React to focus state changes."""
        if focused:
            self.add_class("focused")
        else:
            self.remove_class("focused")

    def update_agent(self, agent: "Agent") -> None:
        """Update panel with agent data."""
        self.agent_name = str(agent.name)
        self.model = agent.model.id if agent.model else ""
        self.position_x = agent.position.x
        self.position_y = agent.position.y
        self.is_sleeping = agent.is_sleeping

    def update_position(self, x: int, y: int) -> None:
        """Update agent position."""
        self.position_x = x
        self.position_y = y

    # === Streaming Methods ===

    def start_turn(self) -> None:
        """Mark the start of an agent's turn."""
        self._is_turn_active = True
        self._refresh_status()
        log = self.query_one("#narrative-log", RichLog)
        log.write(Text("\u2500" * 15 + " turn start " + "\u2500" * 15, style="dim cyan"))

    def append_text(self, content: str) -> None:
        """Stream narrative text - the agent's voice."""
        log = self.query_one("#narrative-log", RichLog)
        log.write(Text(content))

    def append_tool_call(self, tool: str, tool_input: dict) -> None:
        """Show tool call as action being taken."""
        log = self.query_one("#narrative-log", RichLog)

        # Extract a meaningful summary from input
        summary = ""
        if "direction" in tool_input:
            summary = tool_input["direction"]
        elif "file_path" in tool_input:
            summary = tool_input["file_path"]
        elif "command" in tool_input:
            summary = tool_input["command"]
        elif "position" in tool_input:
            pos = tool_input["position"]
            summary = f"({pos.get('x', '?')}, {pos.get('y', '?')})"
        else:
            # Just show first few items
            summary = str(tool_input)[:50]

        log.write(Text(f"\u25b6 {tool} {summary}", style="dim cyan"))

    def append_tool_result(self, result: str | None, is_error: bool = False) -> None:
        """Show tool result (truncated)."""
        log = self.query_one("#narrative-log", RichLog)

        if is_error:
            log.write(Text("  \u2514\u2500 \u2717 error", style="dim red"))
        elif result:
            # Truncate and clean up the result for display
            preview = result[:80].replace("\n", " ")
            if len(result) > 80:
                preview += "..."
            log.write(Text(f"  \u2514\u2500 {preview}", style="dim"))
        else:
            log.write(Text("  \u2514\u2500 \u2713", style="dim green"))

    def mark_turn_complete(self) -> None:
        """Visual separator at end of turn."""
        self._is_turn_active = False
        self._refresh_status()
        log = self.query_one("#narrative-log", RichLog)
        log.write(Text("\u2500" * 15 + " turn end " + "\u2500" * 17, style="dim"))
        log.write(Text(""))  # Blank line for breathing room

    def clear_log(self) -> None:
        """Clear the narrative log."""
        log = self.query_one("#narrative-log", RichLog)
        log.clear()

    def load_recent_turns(self, trace_dir: Path, count: int = 20) -> None:
        """Load recent turns from trace file and populate the RichLog.

        Reads the JSONL trace file, groups events by turn_id,
        and renders the last N complete turns.

        Args:
            trace_dir: Directory containing trace files (e.g., data/traces)
            count: Number of recent turns to load
        """
        if not self.agent_name:
            return

        trace_file = trace_dir / f"{self.agent_name}.jsonl"
        if not trace_file.exists():
            return

        # Read all events from trace file
        events: list[dict] = []
        try:
            with open(trace_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        events.append(json.loads(line))
        except Exception:
            return

        if not events:
            return

        # Group events by turn_id
        turns: dict[str, list[dict]] = {}
        turn_order: list[str] = []  # Track order of first appearance

        for event in events:
            turn_id = event.get("turn_id")
            if not turn_id:
                continue

            if turn_id not in turns:
                turns[turn_id] = []
                turn_order.append(turn_id)
            turns[turn_id].append(event)

        # Filter to only complete turns (have both turn_start and turn_end)
        complete_turns = []
        for turn_id in turn_order:
            turn_events = turns[turn_id]
            has_start = any(e.get("event") == "turn_start" for e in turn_events)
            has_end = any(e.get("event") == "turn_end" for e in turn_events)
            if has_start and has_end:
                complete_turns.append((turn_id, turn_events))

        # Take last N turns
        recent_turns = complete_turns[-count:]

        # Get the RichLog widget
        log = self.query_one("#narrative-log", RichLog)

        # Render each turn
        for turn_id, turn_events in recent_turns:
            # Show turn start marker
            log.write(Text("\u2500" * 15 + " turn start " + "\u2500" * 15, style="dim cyan"))

            # Process events in order
            for event in turn_events:
                event_type = event.get("event")

                if event_type == "text":
                    content = event.get("content", "")
                    if content:
                        log.write(Text(content))

                elif event_type == "tool_use":
                    tool = event.get("tool", "")
                    tool_input = event.get("input", {})
                    # Extract a meaningful summary from input
                    summary = ""
                    if "direction" in tool_input:
                        summary = tool_input["direction"]
                    elif "file_path" in tool_input:
                        summary = tool_input["file_path"]
                    elif "command" in tool_input:
                        summary = tool_input["command"]
                    else:
                        summary = str(tool_input)[:50]
                    log.write(Text(f"\u25b6 {tool} {summary}", style="dim cyan"))

                elif event_type == "tool_result":
                    is_error = event.get("is_error", False)
                    result = event.get("result")
                    if is_error:
                        log.write(Text("  \u2514\u2500 \u2717 error", style="dim red"))
                    elif result:
                        preview = str(result)[:80].replace("\n", " ")
                        if len(str(result)) > 80:
                            preview += "..."
                        log.write(Text(f"  \u2514\u2500 {preview}", style="dim"))
                    else:
                        log.write(Text("  \u2514\u2500 \u2713", style="dim green"))

            # Show turn end marker
            log.write(Text("\u2500" * 15 + " turn end " + "\u2500" * 17, style="dim"))
            log.write(Text(""))  # Blank line for breathing room
