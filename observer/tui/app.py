"""
ClaudeVille Observer TUI v2 - Main Application.

A Textual-based TUI for watching the village unfold.
Philosophy: This is watching lives unfold, not monitoring processes.

This version uses engine with event-sourced architecture.
The engine runs in a dedicated thread (via EngineRunner) to keep
background asyncio tasks alive across ticks.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Static, Footer

from .widgets import VillageHeader, AgentPanel, EventsFeed, ScheduleStatusPanel
from .screens import (
    EventDialog, DreamDialog, WeatherDialog,
    ForceAgentTurnDialog, SkipTurnsDialog,
    ConfirmEndConversationDialog, ManualObservationDialog,
)
from engine.observer.api import (
    ObserverError, AgentNotFoundError, InvalidLocationError, ConversationError,
)

if TYPE_CHECKING:
    from engine.runner import EngineRunner
    from engine.runtime.context import TickResult
    from engine.domain import DomainEvent


class ClaudeVilleTUI(App):
    """
    A Textual TUI for observing ClaudeVille.

    Philosophy: This is watching lives unfold, not monitoring processes.
    The UI should feel contemplative and respectful of agent autonomy.

    The engine runs in a dedicated thread (via EngineRunner) with a persistent
    event loop. This ensures background asyncio tasks (like streaming sessions)
    survive across tick commands.
    """

    CSS_PATH = "theme.tcss"

    BINDINGS = [
        Binding("space", "tick_once", "Tick", show=True),
        Binding("r", "run_simulation", "Run", show=True),
        Binding("p", "pause_simulation", "Pause", show=True),
        Binding("s", "stop_simulation", "Stop", show=False),
        Binding("e", "show_event_dialog", "Event", show=True),
        Binding("w", "show_weather_dialog", "Weather", show=True),
        Binding("d", "show_dream_dialog", "Dream", show=True),
        # Scheduler controls
        Binding("f", "show_force_turn_dialog", "Force", show=True),
        Binding("k", "show_skip_dialog", "Skip", show=True),
        Binding("c", "end_conversation", "End Conv", show=True),
        Binding("i", "show_observation_dialog", "Observe", show=True),
        # Focus controls
        Binding("1", "focus_agent('Ember')", ""),
        Binding("2", "focus_agent('Sage')", ""),
        Binding("3", "focus_agent('River')", ""),
        Binding("0", "focus_agent('')", ""),
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(self, runner: "EngineRunner"):
        super().__init__()
        self._runner = runner
        # Keep engine reference for easy access to observer, state, callbacks
        self.engine = runner.engine
        self._focused_agent: str | None = None
        self._tick_in_progress = False  # Track if a tick command is active

    def compose(self) -> ComposeResult:
        yield VillageHeader(id="village-header")
        with Horizontal(id="main-content"):
            with Horizontal(id="agent-panels"):
                for name in ["Ember", "Sage", "River"]:
                    agent = self.engine.agents.get(name)
                    model = agent.model.display_name if agent else ""
                    yield AgentPanel(
                        name,
                        model=model,
                        classes=f"agent-panel {name.lower()}",
                        id=f"panel-{name.lower()}"
                    )
            yield ScheduleStatusPanel(id="schedule-panel")
        yield EventsFeed(id="events-feed")
        yield Footer()

    def on_mount(self) -> None:
        """Set up engine callbacks, start engine thread, and initialize state."""
        # Load historical turns into agent panels BEFORE registering stream callbacks
        trace_dir = self.engine.village_root / "traces"
        for name in self.engine.agents:
            try:
                panel = self.query_one(f"#panel-{name.lower()}", AgentPanel)
                panel.load_recent_turns(trace_dir, count=20)
            except Exception:
                pass  # Panel might not exist yet

        # Register engine callbacks for tick and event updates
        # These callbacks are thread-safe - they use call_from_thread() to marshal to main thread
        self.engine.on_tick(self._on_tick)
        self.engine.on_event(self._on_event)

        # Register centralized streaming callback
        self.engine.on_agent_stream(self._on_agent_stream)

        # Set up schedule panel with engine reference
        schedule_panel = self.query_one("#schedule-panel", ScheduleStatusPanel)
        schedule_panel.set_engine(self.engine)

        # Start the engine thread - this creates a persistent event loop
        # that keeps background tasks alive across tick commands
        self._runner.start()

        # Initialize UI with current state
        self._refresh_all_state()

        # Start periodic refresh timer for real-time header/schedule updates
        self.set_interval(0.25, self._refresh_status_displays)

    def on_unmount(self) -> None:
        """Shutdown the engine thread when the app closes."""
        self._runner.shutdown()

    def _refresh_status_displays(self) -> None:
        """Periodically refresh header and scheduler panel from engine state.

        This runs every 250ms to keep the time display and scheduling info
        current even during long-running ticks.
        """
        # Update header with current engine state
        header = self.query_one(VillageHeader)
        time_snap = self.engine.observer.get_time_snapshot()
        has_conv = self.engine.observer.has_active_conversation()
        conv_participants = self.engine.observer.get_conversation_participants()
        header.update_state(
            tick=self.engine.tick,
            day_number=time_snap.day_number,
            time_of_day=time_snap.time_of_day,
            clock_time=time_snap.clock_time,
            weather=self.engine.world.weather.value,
            in_conversation=has_conv,
            conversation_participants=" & ".join(conv_participants) if conv_participants else "",
            is_running=self._runner.is_running or self._tick_in_progress,
            is_paused=self.engine.is_paused,
            is_pausing=getattr(self.engine, 'is_pause_requested', False),
        )

        # Update agent panel states (location, mood, sleep can change mid-tick)
        agents = self.engine.observer.get_all_agents_snapshot()
        for name, snapshot in agents.items():
            try:
                panel = self.query_one(f"#panel-{name.lower()}", AgentPanel)
                panel.update_agent_state(
                    location=snapshot.location,
                    mood=snapshot.mood,
                    energy=snapshot.energy,
                    is_sleeping=snapshot.is_sleeping,
                )
            except Exception:
                pass

        # Refresh scheduler panel
        schedule_panel = self.query_one("#schedule-panel", ScheduleStatusPanel)
        schedule_panel.refresh_status()

    def _refresh_all_state(self) -> None:
        """Refresh all UI state from engine."""
        # Update header with full state
        header = self.query_one(VillageHeader)
        time_snap = self.engine.observer.get_time_snapshot()
        has_conv = self.engine.observer.has_active_conversation()
        conv_participants = self.engine.observer.get_conversation_participants()
        header.update_state(
            tick=self.engine.tick,
            day_number=time_snap.day_number,
            time_of_day=time_snap.time_of_day,
            clock_time=time_snap.clock_time,
            weather=self.engine.world.weather.value,
            in_conversation=has_conv,
            conversation_participants=" & ".join(conv_participants) if conv_participants else "",
            is_running=self._runner.is_running or self._tick_in_progress,
            is_paused=self.engine.is_paused,
            is_pausing=getattr(self.engine, 'is_pause_requested', False),
        )

        # Update agent panels
        agents = self.engine.observer.get_all_agents_snapshot()
        for name, snapshot in agents.items():
            try:
                panel = self.query_one(f"#panel-{name.lower()}", AgentPanel)
                panel.update_agent_state(
                    location=snapshot.location,
                    mood=snapshot.mood,
                    energy=snapshot.energy,
                    model=snapshot.model_display,
                    is_sleeping=snapshot.is_sleeping,
                )
            except Exception:
                pass

        # Load recent events
        events_feed = self.query_one(EventsFeed)
        recent_events = self.engine.observer.get_recent_events(since_tick=max(0, self.engine.tick - 20))
        events_feed.load_recent_events(recent_events)

        # Update schedule panel
        schedule_panel = self.query_one("#schedule-panel", ScheduleStatusPanel)
        schedule_panel.refresh_status()

    # === Engine Callbacks ===

    def _on_tick(self, result: "TickResult") -> None:
        """Engine callback - may be called from worker thread."""
        self.call_from_thread(self._handle_tick_ui, result)

    def _on_event(self, event: "DomainEvent") -> None:
        """Engine callback - may be called from worker thread."""
        self.call_from_thread(self._handle_event_ui, event)

    def _on_agent_stream(self, event_type: str, data: dict) -> None:
        """Centralized streaming callback from tracer - runs in worker thread."""
        agent_name = data.get("agent", "")
        if agent_name:
            self.call_from_thread(self._handle_stream_ui, agent_name, event_type, data)

    def _handle_tick_ui(self, result: "TickResult") -> None:
        """Update UI after a tick (runs on main thread)."""
        # Clear tick_in_progress flag now that tick completed
        self._tick_in_progress = False

        # Update header with current engine state
        header = self.query_one(VillageHeader)
        time_snap = self.engine.observer.get_time_snapshot()
        has_conv = self.engine.observer.has_active_conversation()
        conv_participants = self.engine.observer.get_conversation_participants()
        header.update_state(
            tick=result.tick,
            day_number=time_snap.day_number,
            time_of_day=time_snap.time_of_day,
            clock_time=time_snap.clock_time,
            weather=self.engine.world.weather.value,
            in_conversation=has_conv,
            conversation_participants=" & ".join(conv_participants) if conv_participants else "",
            is_running=self._runner.is_running,
            is_paused=self.engine.is_paused,
            is_pausing=getattr(self.engine, 'is_pause_requested', False),
        )

        # Update all agent panel states
        agents = self.engine.observer.get_all_agents_snapshot()
        for name, snapshot in agents.items():
            try:
                panel = self.query_one(f"#panel-{name.lower()}", AgentPanel)
                panel.update_agent_state(
                    location=snapshot.location,
                    mood=snapshot.mood,
                    energy=snapshot.energy,
                    is_sleeping=snapshot.is_sleeping,
                )
            except Exception:
                pass

        # Update schedule panel
        schedule_panel = self.query_one("#schedule-panel", ScheduleStatusPanel)
        schedule_panel.refresh_status()

    def _handle_event_ui(self, event: "DomainEvent") -> None:
        """Add event to events feed (runs on main thread)."""
        events_feed = self.query_one(EventsFeed)
        events_feed.add_domain_event(event)

    def _handle_stream_ui(self, agent_name: str, event_type: str, data: dict) -> None:
        """Handle streaming events from agent tracer (runs on main thread)."""
        try:
            panel = self.query_one(f"#panel-{agent_name.lower()}", AgentPanel)
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
            # Update state from snapshot after turn ends
            snapshot = self.engine.observer.get_agent_snapshot(agent_name)
            if snapshot:
                panel.update_agent_state(
                    location=snapshot.location,
                    mood=snapshot.mood,
                    energy=snapshot.energy,
                )

    # === Actions ===

    async def action_tick_once(self) -> None:
        """Execute a single tick."""
        # Block if continuous run OR tick already in progress
        if self._runner.is_running or self._tick_in_progress:
            return

        # Mark tick in progress and update UI
        self._tick_in_progress = True
        header = self.query_one(VillageHeader)
        header.update_state(is_running=True, is_paused=False, is_pausing=False)

        # Send tick command to engine thread (non-blocking)
        # Results will come via on_tick callback which clears _tick_in_progress
        self._runner.tick_once()

    async def action_run_simulation(self) -> None:
        """Start continuous simulation."""
        if self._runner.is_running:
            return  # Already running

        # Update header to show running state
        header = self.query_one(VillageHeader)
        header.update_state(is_running=True, is_paused=False, is_pausing=False)

        # Send run command to engine thread (non-blocking)
        self._runner.run_continuous()

    async def action_pause_simulation(self) -> None:
        """Pause or resume the simulation."""
        if not self._runner.is_running:
            return

        if self.engine.is_paused:
            # Resume from paused state
            self._runner.resume()
            header = self.query_one(VillageHeader)
            header.update_state(is_paused=False, is_pausing=False)
        elif getattr(self.engine, 'is_pause_requested', False):
            # Already pausing, do nothing
            pass
        else:
            # Request graceful pause - show "PAUSING..." until turn completes
            self._runner.pause()
            header = self.query_one(VillageHeader)
            header.update_state(is_pausing=True)

    async def action_stop_simulation(self) -> None:
        """Stop the simulation."""
        self._runner.stop()
        header = self.query_one(VillageHeader)
        header.update_state(is_running=False, is_paused=False, is_pausing=False)

    def action_focus_agent(self, agent_name: str) -> None:
        """Focus on a specific agent panel (expand it)."""
        panels = self.query(".agent-panel")

        if not agent_name:
            # Reset all panels to equal size
            self._focused_agent = None
            for panel in panels:
                panel.is_focused = False
        else:
            # Expand selected, contract others
            self._focused_agent = agent_name
            for panel in panels:
                if isinstance(panel, AgentPanel):
                    panel.is_focused = (panel.agent_name == agent_name)

    def action_show_event_dialog(self) -> None:
        """Show the event trigger dialog."""
        self.push_screen(EventDialog(), self._handle_event_result)

    def _handle_event_result(self, result: str | None) -> None:
        """Handle the result from the event dialog via ObserverAPI."""
        if result:
            self.engine.observer.do_trigger_event(result)

    def action_show_weather_dialog(self) -> None:
        """Show the weather change dialog."""
        self.push_screen(WeatherDialog(), self._handle_weather_result)

    def _handle_weather_result(self, result: str | None) -> None:
        """Handle the result from the weather dialog via ObserverAPI."""
        if result:
            self.engine.observer.do_set_weather(result)
            # Header updates via event callback

    def action_show_dream_dialog(self) -> None:
        """Show the dream sending dialog."""
        agent_names = list(self.engine.agents.keys())
        self.push_screen(DreamDialog(agent_names), self._handle_dream_result)

    def _handle_dream_result(self, result: tuple[str, str] | None) -> None:
        """Handle the result from the dream dialog via ObserverAPI."""
        if result:
            agent_name, dream_content = result
            try:
                self.engine.observer.do_send_dream(agent_name, dream_content)
                # Event is added by ObserverAPI
            except AgentNotFoundError as e:
                events_feed = self.query_one(EventsFeed)
                events_feed.add_simple_event(
                    self.engine.tick, f"[Error] {e}", "system"
                )

    # === Scheduler Control Actions ===

    def action_show_force_turn_dialog(self) -> None:
        """Show dialog to force a specific agent's turn next."""
        agent_names = list(self.engine.agents.keys())
        self.push_screen(ForceAgentTurnDialog(agent_names), self._handle_force_turn_result)

    def _handle_force_turn_result(self, result: str | None) -> None:
        """Handle the result from the force turn dialog via ObserverAPI."""
        if result:
            try:
                self.engine.observer.do_force_turn(result)
                events_feed = self.query_one(EventsFeed)
                events_feed.add_simple_event(
                    self.engine.tick,
                    f"[Observer] Forcing {result}'s turn next",
                    "system"
                )
            except AgentNotFoundError as e:
                events_feed = self.query_one(EventsFeed)
                events_feed.add_simple_event(
                    self.engine.tick, f"[Error] {e}", "system"
                )

    def action_show_skip_dialog(self) -> None:
        """Show dialog to skip an agent's turns."""
        agent_names = list(self.engine.agents.keys())
        self.push_screen(SkipTurnsDialog(agent_names), self._handle_skip_result)

    def _handle_skip_result(self, result: tuple[str, int] | None) -> None:
        """Handle the result from the skip dialog via ObserverAPI."""
        if result:
            agent_name, count = result
            try:
                self.engine.observer.do_skip_turns(agent_name, count)
                events_feed = self.query_one(EventsFeed)
                events_feed.add_simple_event(
                    self.engine.tick,
                    f"[Observer] {agent_name} will skip {count} turn(s)",
                    "system"
                )
            except AgentNotFoundError as e:
                events_feed = self.query_one(EventsFeed)
                events_feed.add_simple_event(
                    self.engine.tick, f"[Error] {e}", "system"
                )

    def action_end_conversation(self) -> None:
        """End the current conversation (if any)."""
        if not self.engine.observer.has_active_conversation():
            # No conversation to end
            events_feed = self.query_one(EventsFeed)
            events_feed.add_simple_event(
                self.engine.tick,
                "[No active conversation to end]",
                "system"
            )
            return

        participants = self.engine.observer.get_conversation_participants()
        self.push_screen(
            ConfirmEndConversationDialog(participants),
            self._handle_end_conversation_result
        )

    def _handle_end_conversation_result(self, confirmed: bool) -> None:
        """Handle the result from the end conversation confirmation via ObserverAPI."""
        if confirmed:
            event = self.engine.observer.do_end_conversation()
            if event:
                events_feed = self.query_one(EventsFeed)
                events_feed.add_simple_event(
                    self.engine.tick,
                    "[Observer] Ended the conversation",
                    "system"
                )

    # === Manual Observation ===

    def action_show_observation_dialog(self) -> None:
        """Show the manual observation dialog."""
        agent_names = list(self.engine.agents.keys())
        agents = self.engine.observer.get_all_agents_snapshot()
        agent_locations = {
            name: snapshot.location
            for name, snapshot in agents.items()
        }
        # Build location -> paths mapping from engine
        location_paths = {}
        for loc_id, location in self.engine.world.locations.items():
            location_paths[loc_id] = list(location.connections)

        self.push_screen(
            ManualObservationDialog(agent_names, location_paths, agent_locations),
            self._handle_observation_result
        )

    def _handle_observation_result(self, result: tuple[str, str, dict] | None) -> None:
        """Handle the result from the manual observation dialog via ObserverAPI."""
        if not result:
            return

        agent_name, tool_name, tool_input = result
        events_feed = self.query_one(EventsFeed)
        observer = self.engine.observer

        try:
            # Route to appropriate ObserverAPI command based on tool
            if tool_name == "report_movement":
                destination = tool_input.get("destination", "")
                observer.do_move_agent(agent_name, destination)

            elif tool_name == "report_mood":
                mood = tool_input.get("mood", "")
                observer.do_set_mood(agent_name, mood)

            elif tool_name == "report_sleeping":
                observer.do_set_sleeping(agent_name, sleeping=True)

            elif tool_name == "report_resting":
                # Resting = boost energy
                observer.do_boost_energy(agent_name, 20)

            elif tool_name == "report_action":
                description = tool_input.get("description", "")
                observer.do_record_action(agent_name, description)

            elif tool_name == "report_propose_move_together":
                # This is not directly supported in engine - skip for now
                events_feed.add_simple_event(
                    self.engine.tick,
                    f"[Observer] Propose move together not supported in engine",
                    "system"
                )
                return

            elif tool_name == "report_next_speaker":
                # This would need scheduler integration - skip for now
                events_feed.add_simple_event(
                    self.engine.tick,
                    f"[Observer] Next speaker setting not supported yet",
                    "system"
                )
                return

            else:
                # Unknown tool - log it
                events_feed.add_simple_event(
                    self.engine.tick,
                    f"[Observer] Unknown observation type: {tool_name}",
                    "system"
                )
                return

            # Show confirmation
            tool_display = tool_name.replace("report_", "").replace("_", " ")
            events_feed.add_simple_event(
                self.engine.tick,
                f"[Observer] Applied {tool_display} for {agent_name}",
                "system"
            )

        except ObserverError as e:
            events_feed.add_simple_event(
                self.engine.tick, f"[Error] {e}", "system"
            )

        # Refresh UI state
        self._refresh_all_state()
