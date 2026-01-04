"""Cell info widget for Hearth TUI.

Shows details about the cell at the cursor position.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual.widget import Widget
from textual.reactive import reactive

from core.types import Position, Direction
from core.terrain import Terrain
from core.objects import Sign, PlacedItem, AnyWorldObject

if TYPE_CHECKING:
    from core.world import Cell
    from core.agent import Agent


class CellInfo(Widget):
    """Widget showing details about a specific cell."""

    _position: Position | None
    _cell: "Cell | None"
    _objects: list[AnyWorldObject]
    _agent: "Agent | None"
    _place_name: str | None

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ):
        """Initialize CellInfo."""
        super().__init__(name=name, id=id, classes=classes)
        self._position = None
        self._cell = None
        self._objects = []
        self._agent = None
        self._place_name = None

    def update_cell(
        self,
        position: Position | None,
        cell: "Cell | None" = None,
        objects: list[AnyWorldObject] | None = None,
        agent: "Agent | None" = None,
        place_name: str | None = None,
    ) -> None:
        """Update the displayed cell info.

        Args:
            position: Cell position
            cell: Cell data
            objects: Objects at this cell
            agent: Agent at this cell, if any
            place_name: Named place at this cell, if any
        """
        self._position = position
        self._cell = cell
        self._objects = objects or []
        self._agent = agent
        self._place_name = place_name
        self.refresh()

    def clear(self) -> None:
        """Clear the cell info."""
        self._position = None
        self._cell = None
        self._objects = []
        self._agent = None
        self._place_name = None
        self.refresh()

    def render(self) -> Text:
        """Render the cell info."""
        text = Text()
        text.append("Cell Info\n", style="bold underline")
        text.append("\n")

        if self._position is None:
            text.append("No cell selected\n", style="dim")
            text.append("\n")
            text.append("Use arrow keys to move cursor\n", style="dim")
            return text

        # Position
        text.append("Position: ", style="bold")
        text.append(f"({self._position.x}, {self._position.y})\n")

        # Named place
        if self._place_name:
            text.append("Name: ", style="bold")
            text.append(f'"{self._place_name}"\n', style="yellow")

        # Terrain
        if self._cell:
            text.append("Terrain: ", style="bold")
            terrain_name = self._cell.terrain.value.title()
            text.append(f"{terrain_name}\n")

            # Walls
            if self._cell.walls:
                text.append("Walls: ", style="bold")
                wall_names = [d.value for d in self._cell.walls]
                text.append(", ".join(wall_names) + "\n")

            # Doors
            if self._cell.doors:
                text.append("Doors: ", style="bold")
                door_names = [d.value for d in self._cell.doors]
                text.append(", ".join(door_names) + "\n")

            # Structure
            if self._cell.structure_id:
                text.append("In structure: ", style="bold")
                text.append("Yes\n", style="green")

        # Agent
        if self._agent:
            text.append("\n")
            text.append("Agent: ", style="bold")
            color = self._get_agent_color(str(self._agent.name))
            text.append(f"{self._agent.name}\n", style=color)

            if self._agent.is_sleeping:
                text.append("  Status: ", style="bold")
                text.append("Sleeping\n", style="blue")
            elif self._agent.is_journeying:
                text.append("  Status: ", style="bold")
                text.append("Traveling\n", style="yellow")

        # Objects
        if self._objects:
            text.append("\n")
            text.append("Objects:\n", style="bold")
            for obj in self._objects:
                self._render_object(text, obj)

        return text

    def _render_object(self, text: Text, obj: AnyWorldObject) -> None:
        """Render a single object."""
        if isinstance(obj, Sign):
            text.append("  - Sign: ", style="yellow")
            # Truncate long sign text
            sign_text = obj.text
            if len(sign_text) > 30:
                sign_text = sign_text[:27] + "..."
            text.append(f'"{sign_text}"\n')
        elif isinstance(obj, PlacedItem):
            text.append("  - Item: ", style="cyan")
            text.append(f"{obj.item_type}")
            if obj.quantity > 1:
                text.append(f" x{obj.quantity}")
            text.append("\n")
        else:
            text.append(f"  - {type(obj).__name__}\n")

    def _get_agent_color(self, name: str) -> str:
        """Get color for agent name."""
        colors = {
            "Ember": "red",
            "Sage": "magenta",
            "River": "cyan",
        }
        return colors.get(name, "white")
