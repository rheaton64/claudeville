"""Village header widget showing time, weather, tick count, and status."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static
from textual.reactive import reactive


WEATHER_ICONS = {
    "clear": "☀",
    "cloudy": "☁",
    "rainy": "☂",
    "stormy": "⛈",
    "foggy": "░",
    "snowy": "❄",
}

TIME_OF_DAY_ICONS = {
    "morning": "☀",
    "afternoon": "☀",
    "evening": "☽",
    "night": "☾",
}


class VillageHeader(Horizontal):
    """
    Header showing village info, time, weather, conversation, and status.

    Layout: ClaudeVille | Day 1 | 07:41 morning | Weather | Tick: 11 | Conv | [status]
    """

    tick: reactive[int] = reactive(0)
    formatted_time: reactive[str] = reactive("")
    day_number: reactive[int] = reactive(1)
    time_of_day: reactive[str] = reactive("morning")
    clock_time: reactive[str] = reactive("07:00")
    weather: reactive[str] = reactive("clear")
    in_conversation: reactive[bool] = reactive(False)
    conversation_participants: reactive[str] = reactive("")
    is_running: reactive[bool] = reactive(False)
    is_paused: reactive[bool] = reactive(False)
    is_pausing: reactive[bool] = reactive(False)

    def compose(self) -> ComposeResult:
        yield Static("ClaudeVille", classes="title", id="title")
        yield Static("Day 1", classes="day-display", id="day-display")
        yield Static("07:00", classes="time-display", id="time-display")
        yield Static("☀ Clear", classes="weather", id="weather-display")
        yield Static("Tick: 0", classes="tick-count", id="tick-display")
        yield Static("", classes="conversation-indicator", id="conv-display")
        yield Static("○ IDLE", classes="status-indicator", id="status-display")

    def on_mount(self) -> None:
        """Initialize displays on mount."""
        self._update_displays()

    def _status_display(self) -> tuple[str, str]:
        """Get status text and CSS class for styling."""
        if self.is_pausing:
            return "● PAUSING...", "status-pausing"
        elif self.is_paused:
            return "■ PAUSED", "status-paused"
        elif self.is_running:
            return "▶ RUNNING", "status-running"
        else:
            return "○ IDLE", "status-idle"

    def _update_displays(self) -> None:
        """Update all display widgets."""
        # Day display
        self.query_one("#day-display", Static).update(f"Day {self.day_number}")

        # Time display with icon
        icon = TIME_OF_DAY_ICONS.get(self.time_of_day, "")
        self.query_one("#time-display", Static).update(f"{icon} {self.clock_time} {self.time_of_day}")

        # Weather display
        weather_icon = WEATHER_ICONS.get(self.weather, "?")
        self.query_one("#weather-display", Static).update(f"{weather_icon} {self.weather.title()}")

        # Tick display
        self.query_one("#tick-display", Static).update(f"Tick: {self.tick}")

        # Conversation indicator
        if self.in_conversation and self.conversation_participants:
            self.query_one("#conv-display", Static).update(f"♡ {self.conversation_participants}")
        else:
            self.query_one("#conv-display", Static).update("")

        # Status indicator with styling
        status_text, status_class = self._status_display()
        status_widget = self.query_one("#status-display", Static)
        status_widget.update(status_text)
        status_widget.remove_class("status-running", "status-paused", "status-pausing", "status-idle")
        status_widget.add_class(status_class)

    def watch_tick(self, tick: int) -> None:
        self._update_displays()

    def watch_day_number(self, day: int) -> None:
        self._update_displays()

    def watch_time_of_day(self, tod: str) -> None:
        self._update_displays()

    def watch_clock_time(self, ct: str) -> None:
        self._update_displays()

    def watch_weather(self, weather: str) -> None:
        self._update_displays()

    def watch_in_conversation(self, in_conv: bool) -> None:
        self._update_displays()

    def watch_conversation_participants(self, p: str) -> None:
        self._update_displays()

    def watch_is_running(self, is_running: bool) -> None:
        self._update_displays()

    def watch_is_paused(self, is_paused: bool) -> None:
        self._update_displays()

    def watch_is_pausing(self, is_pausing: bool) -> None:
        self._update_displays()

    def update_state(
        self,
        tick: int | None = None,
        time: str | None = None,
        day_number: int | None = None,
        time_of_day: str | None = None,
        clock_time: str | None = None,
        weather: str | None = None,
        in_conversation: bool | None = None,
        conversation_participants: str | None = None,
        is_running: bool | None = None,
        is_paused: bool | None = None,
        is_pausing: bool | None = None,
    ) -> None:
        """Update header state in one call."""
        if tick is not None:
            self.tick = tick
        if time is not None:
            self.formatted_time = time
        if day_number is not None:
            self.day_number = day_number
        if time_of_day is not None:
            self.time_of_day = time_of_day
        if clock_time is not None:
            self.clock_time = clock_time
        if weather is not None:
            self.weather = weather
        if in_conversation is not None:
            self.in_conversation = in_conversation
        if conversation_participants is not None:
            self.conversation_participants = conversation_participants
        if is_running is not None:
            self.is_running = is_running
        if is_paused is not None:
            self.is_paused = is_paused
        if is_pausing is not None:
            self.is_pausing = is_pausing
