"""Main TUI application for Hearth observer.

Now uses EngineRunner for tick execution and streaming support.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer

from core.types import Position, AgentName
from .widgets import GridView, WorldHeader, AgentList, CellInfo, AgentStreamPanel

if TYPE_CHECKING:
    from engine.runner import EngineRunner
    from engine.context import TickContext


class HearthTUI(App):
    """Hearth world viewer TUI application.

    A viewer for the Hearth grid world with tick execution support.
    Shows terrain, objects, and agents. Supports panning, following agents,
    inspecting cells, streaming agent turns, and executing ticks.
    """

    CSS_PATH = "theme.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("space", "tick_once", "Tick", show=True),
        Binding("v", "toggle_stream_view", "Stream", show=True),
        Binding("up", "pan_north", "Pan North", show=False),
        Binding("down", "pan_south", "Pan South", show=False),
        Binding("left", "pan_west", "Pan West", show=False),
        Binding("right", "pan_east", "Pan East", show=False),
        Binding("f", "toggle_follow", "Follow"),
        Binding("c", "center_on_focused", "Center"),
        Binding("1", "focus_agent('Ember')", "Ember", show=False),
        Binding("2", "focus_agent('Sage')", "Sage", show=False),
        Binding("3", "focus_agent('River')", "River", show=False),
        Binding("0", "clear_focus", "Clear", show=False),
    ]

    def __init__(self, runner: "EngineRunner"):
        """Initialize HearthTUI.

        Args:
            runner: EngineRunner for tick execution and streaming
        """
        super().__init__()
        self._runner = runner
        self._engine = runner._engine
        self._api = self._engine.observer
        self._focused_agent: str | None = None
        self._following: bool = False
        self._stream_view_active: bool = False
        self._tick_in_progress: bool = False

    def compose(self) -> ComposeResult:
        """Compose the app layout."""
        yield WorldHeader(id="header")
        with Horizontal(id="main"):
            yield GridView(self._api, id="grid")
            yield AgentStreamPanel(id="agent-stream")
            with Vertical(id="sidebar"):
                yield AgentList(id="agent-list")
                yield CellInfo(id="cell-info")
        yield Footer()

    async def on_mount(self) -> None:
        """Handle app mount - start runner and register callbacks."""
        # Start the engine thread
        self._runner.start()

        # Register tick callback (called from engine thread)
        self._runner.on_tick(self._on_tick_complete)

        # Register stream callback for agent panels
        self._engine.tracer.register_callback(self._on_agent_stream)

        # Load initial data
        await self._refresh_all()

    def on_unmount(self) -> None:
        """Clean shutdown of engine runner."""
        self._runner.stop()

    async def _refresh_all(self) -> None:
        """Refresh all data from API."""
        # Get world state
        world_state = await self._api.get_world_state()
        dimensions = await self._api.get_world_dimensions()

        # Update grid first so we have center coords
        grid = self.query_one("#grid", GridView)
        grid.set_focused(self._focused_agent)
        if self._following and self._focused_agent:
            grid.set_follow(self._focused_agent)
        await grid.refresh_data()

        # Update header with center from grid
        header = self.query_one("#header", WorldHeader)
        status = "RUNNING" if self._tick_in_progress or self._runner.is_running else "IDLE"
        header.update_state(
            tick=world_state.current_tick,
            weather=world_state.weather.value,
            dimensions=dimensions,
            center=(grid.center_x, grid.center_y),
            status=status,
            followed_agent=self._focused_agent if self._following else "",
        )

        # Update agent list
        agents = await self._api.get_all_agents()
        agent_list = self.query_one("#agent-list", AgentList)
        agent_list.update_agents(agents)
        agent_list.select(self._focused_agent)

        # Update stream panel if visible and agent focused
        if self._stream_view_active and self._focused_agent:
            stream_panel = self.query_one("#agent-stream", AgentStreamPanel)
            agent = await self._api.get_agent(AgentName(self._focused_agent))
            if agent:
                stream_panel.update_agent(agent)

        # Update cell info if cursor is set
        await self._update_cell_info()

    def _update_header_center(self) -> None:
        """Update the header with current grid center coordinates."""
        grid = self.query_one("#grid", GridView)
        header = self.query_one("#header", WorldHeader)
        header.update_state(center=(grid.center_x, grid.center_y))

    async def _update_cell_info(self) -> None:
        """Update cell info panel based on cursor position."""
        grid = self.query_one("#grid", GridView)
        cell_info = self.query_one("#cell-info", CellInfo)

        cursor_pos = grid.get_cursor_position()
        if cursor_pos is None:
            cell_info.clear()
            return

        # Get cell data
        cell = await self._api.get_cell(cursor_pos)
        objects = await self._api.get_objects_at(cursor_pos)
        agent = await self._api.get_agent_at(cursor_pos)

        # Get place name
        named_places = await self._api.get_named_places()
        place_name = None
        for name, pos in named_places.items():
            if pos == cursor_pos:
                place_name = name
                break

        cell_info.update_cell(
            position=cursor_pos,
            cell=cell,
            objects=objects,
            agent=agent,
            place_name=place_name,
        )

    # -------------------------------------------------------------------------
    # Engine Callbacks (called from engine thread)
    # -------------------------------------------------------------------------

    def _on_tick_complete(self, ctx: "TickContext") -> None:
        """Called from engine thread after tick."""
        self.call_from_thread(self._handle_tick_ui, ctx)

    def _handle_tick_ui(self, ctx: "TickContext") -> None:
        """Update UI after tick (main thread)."""
        self._tick_in_progress = False
        header = self.query_one("#header", WorldHeader)
        status = "RUNNING" if self._runner.is_running else "IDLE"
        header.update_state(status=status, tick=ctx.tick)
        # Refresh all data
        asyncio.create_task(self._refresh_all())

    def _on_agent_stream(self, event_type: str, data: dict) -> None:
        """Called from engine thread for streaming events."""
        self.call_from_thread(self._handle_stream_ui, event_type, data)

    def _handle_stream_ui(self, event_type: str, data: dict) -> None:
        """Handle streaming events (main thread)."""
        if not self._stream_view_active:
            return

        agent_name = data.get("agent", "")
        if agent_name != self._focused_agent:
            return

        try:
            panel = self.query_one("#agent-stream", AgentStreamPanel)
        except Exception:
            return

        if event_type == "turn_start":
            panel.start_turn()
        elif event_type == "text":
            content = data.get("content", "")
            if content:
                panel.append_text(content)
        elif event_type == "tool_use":
            tool = data.get("tool", "")
            tool_input = data.get("input", {})
            panel.append_tool_call(tool, tool_input)
        elif event_type == "tool_result":
            result = data.get("result")
            is_error = data.get("is_error", False)
            panel.append_tool_result(result, is_error)
        elif event_type == "turn_end":
            panel.mark_turn_complete()

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    async def action_tick_once(self) -> None:
        """Execute a single tick."""
        if self._runner.is_running or self._tick_in_progress:
            return

        self._tick_in_progress = True
        header = self.query_one("#header", WorldHeader)
        header.update_state(status="RUNNING")

        # Request tick (non-blocking, uses engine thread)
        self._runner.request_tick()

    async def action_toggle_stream_view(self) -> None:
        """Toggle between grid view and agent stream view."""
        if not self._focused_agent:
            return  # Need a focused agent

        self._stream_view_active = not self._stream_view_active

        grid = self.query_one("#grid", GridView)
        stream_panel = self.query_one("#agent-stream", AgentStreamPanel)

        if self._stream_view_active:
            # Show stream panel, hide grid
            grid.add_class("hidden")
            stream_panel.remove_class("hidden")
            stream_panel.add_class("active")

            # Update stream panel with current agent
            agent = await self._api.get_agent(AgentName(self._focused_agent))
            if agent:
                stream_panel.update_agent(agent)
                # Add agent-specific class for styling
                stream_panel.remove_class("ember", "sage", "river")
                stream_panel.add_class(self._focused_agent.lower())

            # Load recent turns
            trace_dir = self._engine._storage.data_dir / "traces"
            stream_panel.load_recent_turns(trace_dir, count=20)
        else:
            # Show grid, hide stream panel
            grid.remove_class("hidden")
            stream_panel.add_class("hidden")
            stream_panel.remove_class("active")

    async def action_refresh(self) -> None:
        """Refresh all data from storage."""
        await self._refresh_all()

    async def action_pan_north(self) -> None:
        """Pan viewport north (higher y values)."""
        grid = self.query_one("#grid", GridView)
        grid.pan(0, 1)
        await grid.refresh_data()
        self._update_header_center()
        await self._update_cell_info()

    async def action_pan_south(self) -> None:
        """Pan viewport south (lower y values)."""
        grid = self.query_one("#grid", GridView)
        grid.pan(0, -1)
        await grid.refresh_data()
        self._update_header_center()
        await self._update_cell_info()

    async def action_pan_east(self) -> None:
        """Pan viewport east."""
        grid = self.query_one("#grid", GridView)
        grid.pan(1, 0)
        await grid.refresh_data()
        self._update_header_center()
        await self._update_cell_info()

    async def action_pan_west(self) -> None:
        """Pan viewport west."""
        grid = self.query_one("#grid", GridView)
        grid.pan(-1, 0)
        await grid.refresh_data()
        self._update_header_center()
        await self._update_cell_info()

    async def action_toggle_follow(self) -> None:
        """Toggle follow mode for focused agent."""
        if not self._focused_agent:
            return

        self._following = not self._following
        grid = self.query_one("#grid", GridView)

        if self._following:
            grid.set_follow(self._focused_agent)
        else:
            grid.set_follow(None)

        # Update header
        header = self.query_one("#header", WorldHeader)
        header.update_state(
            followed_agent=self._focused_agent if self._following else ""
        )

        await grid.refresh_data()
        self._update_header_center()

    async def action_center_on_focused(self) -> None:
        """Center viewport on focused agent."""
        if not self._focused_agent:
            return

        agent = await self._api.get_agent(AgentName(self._focused_agent))
        if agent:
            grid = self.query_one("#grid", GridView)
            grid.center_on(agent.position)
            await grid.refresh_data()
            self._update_header_center()

    async def action_focus_agent(self, agent_name: str) -> None:
        """Focus on a specific agent.

        Args:
            agent_name: Name of agent to focus
        """
        self._focused_agent = agent_name

        # Update UI
        agent_list = self.query_one("#agent-list", AgentList)
        agent_list.select(agent_name)

        grid = self.query_one("#grid", GridView)
        grid.set_focused(agent_name)

        # Center on agent
        agent = await self._api.get_agent(AgentName(agent_name))
        if agent:
            grid.center_on(agent.position)

        # If following was enabled, update follow target
        if self._following:
            grid.set_follow(agent_name)
            header = self.query_one("#header", WorldHeader)
            header.update_state(followed_agent=agent_name)

        # If stream view is active, update the panel
        if self._stream_view_active:
            stream_panel = self.query_one("#agent-stream", AgentStreamPanel)
            if agent:
                stream_panel.update_agent(agent)
                # Update agent-specific class for styling
                stream_panel.remove_class("ember", "sage", "river")
                stream_panel.add_class(agent_name.lower())
                # Reload turns for new agent
                stream_panel.clear_log()
                trace_dir = self._engine._storage.data_dir / "traces"
                stream_panel.load_recent_turns(trace_dir, count=20)

        await grid.refresh_data()
        self._update_header_center()

    async def action_clear_focus(self) -> None:
        """Clear agent focus."""
        self._focused_agent = None
        self._following = False

        # Exit stream view if active
        if self._stream_view_active:
            self._stream_view_active = False
            grid = self.query_one("#grid", GridView)
            stream_panel = self.query_one("#agent-stream", AgentStreamPanel)
            grid.remove_class("hidden")
            stream_panel.add_class("hidden")
            stream_panel.remove_class("active")

        agent_list = self.query_one("#agent-list", AgentList)
        agent_list.select(None)

        grid = self.query_one("#grid", GridView)
        grid.set_focused(None)
        grid.set_follow(None)

        header = self.query_one("#header", WorldHeader)
        header.update_state(followed_agent="")

        await grid.refresh_data()
        self._update_header_center()


async def run_tui(runner: "EngineRunner") -> None:
    """Run the TUI application.

    Args:
        runner: EngineRunner instance
    """
    app = HearthTUI(runner)
    await app.run_async()
