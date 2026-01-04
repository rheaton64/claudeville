"""Grid view widget for Hearth TUI.

Renders the visible portion of the world grid with terrain, objects, and agents.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual.widget import Widget
from textual.reactive import reactive

from core.types import Position, Rect, Direction, AgentName
from core.terrain import Terrain, TERRAIN_DEFAULTS
from core.world import Cell
from core.agent import Agent
from core.objects import Sign, PlacedItem, AnyWorldObject

if TYPE_CHECKING:
    from observe.api import ObserverAPI


# Symbol and color mappings
# Symbols are distinct so agents can differentiate without color
TERRAIN_RENDER: dict[Terrain, tuple[str, str]] = {
    Terrain.GRASS: (".", "green"),
    Terrain.WATER: ("≈", "blue"),           # Deep water, impassable
    Terrain.COAST: ("~", "bright_blue"),    # Shallow water, wade-able
    Terrain.STONE: ("▲", "bright_black"),   # Rocky outcrops, mountains
    Terrain.SAND: (":", "yellow"),          # Beaches, desert edges
    Terrain.FOREST: ("♣", "bright_green"),  # Wooded areas
    Terrain.HILL: ("^", "rgb(160,64,0)"),   # Elevated terrain (brown)
}

OBJECT_RENDER: dict[str, tuple[str, str]] = {
    "sign": ("?", "yellow"),
    "placed_item": ("*", "cyan"),
}

# Agent colors
AGENT_COLORS: dict[str, str] = {
    "Ember": "red",
    "Sage": "magenta",
    "River": "cyan",
}


def get_terrain_render(terrain: Terrain) -> tuple[str, str]:
    """Get (symbol, color) for terrain type."""
    return TERRAIN_RENDER.get(terrain, ("?", "white"))


def get_object_render(obj: AnyWorldObject) -> tuple[str, str]:
    """Get (symbol, color) for world object."""
    if isinstance(obj, Sign):
        return ("?", "yellow")
    elif isinstance(obj, PlacedItem):
        return ("*", "cyan")
    return ("o", "white")


class GridView(Widget):
    """Widget that renders a portion of the world grid.

    Features:
    - Dynamic viewport based on widget size
    - Pan with arrow keys or center on position
    - Follow mode to track an agent
    - Priority rendering: Agent > Object > Terrain
    - Roguelike symbols: @ for focused agent, initials for others
    """

    # Reactive properties
    center_x: reactive[int] = reactive(50)
    center_y: reactive[int] = reactive(50)
    follow_agent: reactive[str | None] = reactive(None)
    focused_agent: reactive[str | None] = reactive(None)
    cursor_x: reactive[int | None] = reactive(None)
    cursor_y: reactive[int | None] = reactive(None)

    # Cached data from last refresh
    _cells: list[Cell]
    _objects: list[AnyWorldObject]
    _agents: list[Agent]
    _world_width: int
    _world_height: int

    def __init__(
        self,
        api: "ObserverAPI",
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ):
        """Initialize GridView.

        Args:
            api: ObserverAPI for querying world state
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._api = api
        self._cells = []
        self._objects = []
        self._agents = []
        self._world_width = 100
        self._world_height = 100

    def get_visible_rect(self) -> Rect:
        """Calculate the rectangle of visible cells based on content region."""
        # Use content_region for actual renderable area
        # Each cell takes 2 characters (symbol + space)
        actual_width = max(1, self.content_region.width // 2)
        actual_height = max(1, self.content_region.height)
        half_w = actual_width // 2
        half_h = actual_height // 2
        return Rect(
            min_x=self.center_x - half_w,
            min_y=self.center_y - half_h,
            max_x=self.center_x + half_w,
            max_y=self.center_y + half_h,
        )

    async def refresh_data(self) -> None:
        """Refresh cached data from API."""
        # Get world dimensions
        self._world_width, self._world_height = await self._api.get_world_dimensions()

        # If following an agent, update center
        if self.follow_agent:
            agent = await self._api.get_agent(AgentName(self.follow_agent))
            if agent:
                self.center_x = agent.position.x
                self.center_y = agent.position.y

        # Get viewport data for current visible area
        rect = self.get_visible_rect()
        rect = rect.clamp(self._world_width, self._world_height)

        self._cells, self._objects, self._agents = await self._api.get_viewport_data(
            rect
        )

        self.refresh()

    def _build_cell_lookup(self) -> dict[Position, Cell]:
        """Build position -> cell lookup from cached cells."""
        return {cell.position: cell for cell in self._cells}

    def _build_object_lookup(self) -> dict[Position, list[AnyWorldObject]]:
        """Build position -> objects lookup from cached objects."""
        lookup: dict[Position, list[AnyWorldObject]] = {}
        for obj in self._objects:
            if obj.position not in lookup:
                lookup[obj.position] = []
            lookup[obj.position].append(obj)
        return lookup

    def _build_agent_lookup(self) -> dict[Position, list[Agent]]:
        """Build position -> agents lookup from cached agents."""
        lookup: dict[Position, list[Agent]] = {}
        for agent in self._agents:
            if agent.position not in lookup:
                lookup[agent.position] = []
            lookup[agent.position].append(agent)
        return lookup

    def render(self) -> Text:
        """Render the grid view."""
        rect = self.get_visible_rect()
        rect = rect.clamp(self._world_width, self._world_height)

        cell_lookup = self._build_cell_lookup()
        object_lookup = self._build_object_lookup()
        agent_lookup = self._build_agent_lookup()

        lines: list[Text] = []

        # Render from top to bottom (high Y to low Y)
        for y in range(rect.max_y, rect.min_y - 1, -1):
            line = Text()
            for x in range(rect.min_x, rect.max_x + 1):
                pos = Position(x, y)
                symbol, color = self._render_cell(
                    pos, cell_lookup, object_lookup, agent_lookup
                )

                # Highlight cursor position
                if self.cursor_x == x and self.cursor_y == y:
                    line.append(symbol, style=f"reverse {color}")
                else:
                    line.append(symbol, style=color)
                line.append(" ")  # Spacing between cells

            lines.append(line)

        # Join lines
        result = Text()
        for i, line in enumerate(lines):
            result.append(line)
            if i < len(lines) - 1:
                result.append("\n")

        return result

    def _render_cell(
        self,
        pos: Position,
        cell_lookup: dict[Position, Cell],
        object_lookup: dict[Position, list[AnyWorldObject]],
        agent_lookup: dict[Position, list[Agent]],
    ) -> tuple[str, str]:
        """Render a single cell with priority: Agent > Object > Terrain.

        Returns:
            (symbol, color) tuple
        """
        # Priority 1: Agents
        agents_here = agent_lookup.get(pos, [])
        if agents_here:
            agent = agents_here[0]  # Take first if multiple
            if self.focused_agent and agent.name == self.focused_agent:
                # Focused agent shown as @
                color = AGENT_COLORS.get(str(agent.name), "white")
                return ("@", color)
            else:
                # Other agents shown as initial
                initial = str(agent.name)[0].upper()
                color = AGENT_COLORS.get(str(agent.name), "white")
                return (initial, color)

        # Priority 2: Objects
        objects_here = object_lookup.get(pos, [])
        if objects_here:
            obj = objects_here[0]  # Take first if multiple
            return get_object_render(obj)

        # Priority 3: Terrain
        cell = cell_lookup.get(pos)
        if cell:
            return get_terrain_render(cell.terrain)

        # Default (shouldn't happen if data is loaded)
        return (".", "bright_black")

    def pan(self, dx: int, dy: int) -> None:
        """Pan the viewport by delta cells.

        Args:
            dx: Horizontal pan (positive = east)
            dy: Vertical pan (positive = north)
        """
        # Clear follow mode when manually panning
        self.follow_agent = None

        new_x = max(0, min(self._world_width - 1, self.center_x + dx))
        new_y = max(0, min(self._world_height - 1, self.center_y + dy))

        self.center_x = new_x
        self.center_y = new_y
        self.refresh()

    def center_on(self, pos: Position) -> None:
        """Center the viewport on a position.

        Args:
            pos: Position to center on
        """
        self.center_x = pos.x
        self.center_y = pos.y
        self.refresh()

    def set_follow(self, agent_name: str | None) -> None:
        """Set agent to follow (or None to disable follow mode).

        Args:
            agent_name: Name of agent to follow, or None
        """
        self.follow_agent = agent_name

    def set_focused(self, agent_name: str | None) -> None:
        """Set focused agent (shown as @).

        Args:
            agent_name: Name of agent to focus, or None
        """
        self.focused_agent = agent_name
        self.refresh()

    def move_cursor(self, dx: int, dy: int) -> None:
        """Move the cursor by delta cells.

        Args:
            dx: Horizontal move (positive = east)
            dy: Vertical move (positive = north)
        """
        if self.cursor_x is None or self.cursor_y is None:
            # Initialize cursor at center
            self.cursor_x = self.center_x
            self.cursor_y = self.center_y
        else:
            self.cursor_x = max(0, min(self._world_width - 1, self.cursor_x + dx))
            self.cursor_y = max(0, min(self._world_height - 1, self.cursor_y + dy))
        self.refresh()

    def get_cursor_position(self) -> Position | None:
        """Get current cursor position, if set."""
        if self.cursor_x is not None and self.cursor_y is not None:
            return Position(self.cursor_x, self.cursor_y)
        return None
