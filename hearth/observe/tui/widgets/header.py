"""Header widget for Hearth TUI.

Shows world state: tick, weather, dimensions, and status.
"""

from __future__ import annotations

from textual.widgets import Static
from textual.reactive import reactive


class WorldHeader(Static):
    """Header widget showing world state."""

    tick: reactive[int] = reactive(0)
    weather: reactive[str] = reactive("clear")
    dimensions: reactive[str] = reactive("100x100")
    center: reactive[str] = reactive("50, 50")
    status: reactive[str] = reactive("IDLE")
    followed_agent: reactive[str | None] = reactive(None)

    def render(self) -> str:
        """Render the header."""
        parts = [
            "Hearth",
            f"Tick: {self.tick}",
            f"Weather: {self.weather}",
            f"World: {self.dimensions}",
            f"View: ({self.center})",
        ]

        if self.followed_agent:
            parts.append(f"Following: {self.followed_agent}")

        parts.append(f"[{self.status}]")

        return " | ".join(parts)

    def update_state(
        self,
        tick: int | None = None,
        weather: str | None = None,
        dimensions: tuple[int, int] | None = None,
        center: tuple[int, int] | None = None,
        status: str | None = None,
        followed_agent: str | None = None,
    ) -> None:
        """Update header state.

        Args:
            tick: Current tick
            weather: Weather string
            dimensions: (width, height) tuple
            center: (x, y) center of viewport
            status: Status string
            followed_agent: Name of followed agent (use empty string to clear)
        """
        if tick is not None:
            self.tick = tick
        if weather is not None:
            self.weather = weather
        if dimensions is not None:
            self.dimensions = f"{dimensions[0]}x{dimensions[1]}"
        if center is not None:
            self.center = f"{center[0]}, {center[1]}"
        if status is not None:
            self.status = status
        if followed_agent is not None:
            self.followed_agent = followed_agent if followed_agent else None
