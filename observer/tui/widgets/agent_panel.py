"""Agent panel widget showing streaming narrative and tool calls."""

import json
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, RichLog
from textual.reactive import reactive
from rich.text import Text


MOOD_EMOJIS = {
    "focused": "\u26a1",        # Lightning
    "contemplative": "\U0001F4D6",  # Open book
    "warm": "\u2764",           # Heart
    "peaceful": "\U0001F30A",   # Wave
    "curious": "\U0001F50D",    # Magnifying glass
    "tired": "\U0001F634",      # Sleeping face
    "joyful": "\u2728",         # Sparkles
    "anxious": "\U0001F4AD",    # Thought bubble
    "creative": "\U0001F3A8",   # Palette
    "reflective": "\U0001F319", # Crescent moon
    "energetic": "\u2B50",      # Star
    "calm": "\U0001F343",       # Leaf
}

MODEL_DISPLAY = {
    "claude-haiku": "Haiku",
    "claude-sonnet-4-5-20250929": "Sonnet",
    "claude-opus-4-1-20250805": "Opus 4.1",
    "claude-opus-4-5-20251101": "Opus",
    "haiku": "Haiku",
    "sonnet": "Sonnet",
    "opus": "Opus",
}


class AgentPanel(Vertical):
    """
    A panel showing one agent's state and streaming narrative.

    The narrative area uses RichLog for scrollable, styled prose.
    Focus mode expands this panel when keys 1/2/3 are pressed.
    """

    is_focused: reactive[bool] = reactive(False)
    location: reactive[str] = reactive("")
    mood: reactive[str] = reactive("")
    energy: reactive[int] = reactive(100)
    is_sleeping: reactive[bool] = reactive(False)
    # Compaction tracking
    token_count: reactive[int] = reactive(0)
    token_threshold: reactive[int] = reactive(150_000)
    is_compacting: reactive[bool] = reactive(False)

    def __init__(self, agent_name: str, model: str = "", **kwargs):
        super().__init__(**kwargs)
        self.agent_name = agent_name
        self.model = model
        self._is_turn_active = False

    def compose(self) -> ComposeResult:
        with Vertical(classes="agent-header"):
            yield Static(self._build_header(), classes="agent-header-content", id="header-content")
        with Vertical(classes="agent-status"):
            yield Static(self._build_status(), classes="status-content", id="status-content")
        yield RichLog(classes="agent-narrative", wrap=True, highlight=False, markup=True, id="narrative-log")

    def _build_header(self) -> Text:
        """Build the header line: Name [Model] @ Location (with sleep indicator)"""
        text = Text()
        text.append(self.agent_name, style="bold")

        # Sleep indicator
        if self.is_sleeping:
            text.append(" 💤", style="")

        # Model badge
        model_name = MODEL_DISPLAY.get(self.model, self.model or "?")
        text.append(f" [{model_name}]", style="dim")

        # Location
        if self.location:
            loc_display = self.location.replace("_", " ").title()
            text.append(f" @ {loc_display}", style="italic dim")

        return text

    def _build_status(self) -> Text:
        """Build the status line: Mood emoji + energy bar + token count."""
        text = Text()

        # Mood emoji
        mood_word = self.mood.split()[0].lower() if self.mood else "calm"
        mood_emoji = MOOD_EMOJIS.get(mood_word, "\U0001F7E2")  # Default green circle
        text.append(f"{mood_emoji} {self.mood or 'calm'} ", style="")

        # Energy as visual bar
        energy_filled = self.energy // 10
        energy_empty = 10 - energy_filled
        bar = "\u2588" * energy_filled + "\u2591" * energy_empty
        text.append(f"[{bar}]", style="green")

        # Token count with color coding (only show if we have token data)
        if self.token_count > 0 or self.is_compacting:
            text.append(" | ", style="dim")

            if self.is_compacting:
                text.append("COMPACTING...", style="bold yellow")
            else:
                # Format token count (e.g., "45K/150K (30%)")
                token_k = self.token_count / 1000
                threshold_k = self.token_threshold / 1000
                percent = int((self.token_count / self.token_threshold) * 100) if self.token_threshold > 0 else 0

                # Color based on percentage
                if percent >= 95:
                    color = "bold red"
                elif percent >= 80:
                    color = "yellow"
                else:
                    color = "dim cyan"

                text.append(f"{token_k:.0f}K/{threshold_k:.0f}K ({percent}%)", style=color)

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

    def watch_location(self, location: str) -> None:
        """React to location changes."""
        self._refresh_header()

    def watch_mood(self, mood: str) -> None:
        """React to mood changes."""
        self._refresh_status()

    def watch_energy(self, energy: int) -> None:
        """React to energy changes."""
        self._refresh_status()

    def watch_is_sleeping(self, is_sleeping: bool) -> None:
        """React to sleep state changes."""
        self._refresh_header()

    def watch_token_count(self, token_count: int) -> None:
        """React to token count changes."""
        self._refresh_status()

    def watch_is_compacting(self, is_compacting: bool) -> None:
        """React to compaction state changes."""
        self._refresh_status()

    def watch_is_focused(self, focused: bool) -> None:
        """React to focus state changes."""
        if focused:
            self.add_class("focused")
        else:
            self.remove_class("focused")

    def update_agent_state(
        self,
        location: str | None = None,
        mood: str | None = None,
        energy: int | None = None,
        model: str | None = None,
        is_sleeping: bool | None = None,
        token_count: int | None = None,
        token_threshold: int | None = None,
        is_compacting: bool | None = None,
    ) -> None:
        """Update agent state in one call."""
        if location is not None:
            self.location = location
        if mood is not None:
            self.mood = mood
        if energy is not None:
            self.energy = energy
        if model is not None:
            self.model = model
            self._refresh_header()
        if is_sleeping is not None:
            self.is_sleeping = is_sleeping
        if token_count is not None:
            self.token_count = token_count
        if token_threshold is not None:
            self.token_threshold = token_threshold
        if is_compacting is not None:
            self.is_compacting = is_compacting

    # === Streaming Methods ===

    def start_turn(self) -> None:
        """Mark the start of an agent's turn."""
        self._is_turn_active = True
        log = self.query_one("#narrative-log", RichLog)
        log.write(Text("\u2500" * 15 + " turn start " + "\u2500" * 15, style="dim cyan"))

    def append_text(self, content: str) -> None:
        """Stream narrative text - the agent's voice."""
        log = self.query_one("#narrative-log", RichLog)
        log.write(Text(content))

    def append_tool_call(self, tool: str, tool_input: dict) -> None:
        """Show tool call as action being taken."""
        log = self.query_one("#narrative-log", RichLog)

        # Extract a meaningful path/command from input
        path = tool_input.get("file_path", "")
        if not path:
            path = tool_input.get("command", "")
        if not path:
            path = str(tool_input)[:50]

        log.write(Text(f"\u25b6 {tool} {path}", style="dim cyan"))

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
        log = self.query_one("#narrative-log", RichLog)
        log.write(Text("\u2500" * 15 + " turn end " + "\u2500" * 17, style="dim"))
        log.write(Text(""))  # Blank line for breathing room

    def clear_log(self) -> None:
        """Clear the narrative log."""
        log = self.query_one("#narrative-log", RichLog)
        log.clear()

    def load_recent_turns(self, trace_dir: Path, count: int = 20) -> None:
        """
        Load recent turns from trace file and populate the RichLog.

        Reads the JSONL trace file, groups events by turn_id,
        and renders the last N complete turns.
        """
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
                    # Extract a meaningful path/command from input
                    path = tool_input.get("file_path", "")
                    if not path:
                        path = tool_input.get("command", "")
                    if not path:
                        path = str(tool_input)[:50]
                    log.write(Text(f"\u25b6 {tool} {path}", style="dim cyan"))

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
