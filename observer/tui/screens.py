"""Modal dialog screens for ClaudeVille Observer TUI v2."""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Input, Button, Select, Label

from engine.runtime.interpreter.registry import get_tool_options_for_tui


class EventDialog(ModalScreen[str | None]):
    """Modal dialog for triggering world events."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog", id="event-dialog"):
            yield Static("Trigger World Event", classes="dialog-title")
            yield Static(
                "Describe what happens in the world. "
                "This will be perceived by all agents.",
                classes="dialog-help"
            )
            yield Input(
                placeholder="A mysterious traveler arrives at the village gate...",
                id="event-input",
                classes="dialog-input"
            )
            with Horizontal(classes="dialog-buttons"):
                yield Button("Trigger", variant="primary", id="trigger-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def on_mount(self) -> None:
        """Focus the input on mount."""
        self.query_one("#event-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "trigger-btn":
            input_widget = self.query_one("#event-input", Input)
            if input_widget.value.strip():
                self.dismiss(input_widget.value.strip())
            return
        self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input."""
        if event.value.strip():
            self.dismiss(event.value.strip())

    def action_cancel(self) -> None:
        self.dismiss(None)


class DreamDialog(ModalScreen[tuple[str, str] | None]):
    """Modal dialog for sending dreams to agents."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, agent_names: list[str] | None = None):
        super().__init__()
        self.agent_names = agent_names or ["Ember", "Sage", "River"]

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog", id="dream-dialog"):
            yield Static("Send a Dream", classes="dialog-title")
            yield Static(
                "Send a gentle inspiration to an agent. "
                "This is a nudge, not a command.",
                classes="dialog-help"
            )
            yield Select(
                [(name, name) for name in self.agent_names],
                prompt="Choose recipient",
                id="agent-select",
            )
            yield Input(
                placeholder="You dream of a book you haven't yet written...",
                id="dream-input",
                classes="dialog-input"
            )
            with Horizontal(classes="dialog-buttons"):
                yield Button("Send Dream", variant="primary", id="send-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def on_mount(self) -> None:
        """Focus the select on mount."""
        self.query_one("#agent-select", Select).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send-btn":
            select = self.query_one("#agent-select", Select)
            input_widget = self.query_one("#dream-input", Input)
            if select.value and input_widget.value.strip():
                self.dismiss((str(select.value), input_widget.value.strip()))
            return
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class WeatherDialog(ModalScreen[str | None]):
    """Modal dialog for changing weather."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    WEATHER_OPTIONS = [
        ("clear", "Clear skies"),
        ("cloudy", "Cloudy"),
        ("rainy", "Rainy"),
        ("stormy", "Stormy"),
        ("foggy", "Foggy"),
        ("snowy", "Snowy"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog", id="weather-dialog"):
            yield Static("Change Weather", classes="dialog-title")
            yield Static(
                "The weather affects the mood and activities of the village.",
                classes="dialog-help"
            )
            yield Select(
                [(desc, val) for val, desc in self.WEATHER_OPTIONS],
                prompt="Select weather",
                id="weather-select",
            )
            with Horizontal(classes="dialog-buttons"):
                yield Button("Set Weather", variant="primary", id="set-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def on_mount(self) -> None:
        """Focus the select on mount."""
        self.query_one("#weather-select", Select).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "set-btn":
            select = self.query_one("#weather-select", Select)
            if select.value:
                self.dismiss(str(select.value))
            return
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


# === Scheduler Control Dialogs ===


class ForceAgentTurnDialog(ModalScreen[str | None]):
    """Modal dialog for forcing a specific agent's turn next."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, agent_names: list[str] | None = None):
        super().__init__()
        self.agent_names = agent_names or ["Ember", "Sage", "River"]

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog", id="force-turn-dialog"):
            yield Static("Force Agent Turn", classes="dialog-title")
            yield Static(
                "Select an agent to act next, regardless of the scheduler.",
                classes="dialog-help"
            )
            yield Select(
                [(name, name) for name in self.agent_names],
                prompt="Choose agent",
                id="agent-select",
            )
            with Horizontal(classes="dialog-buttons"):
                yield Button("Force Turn", variant="primary", id="force-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def on_mount(self) -> None:
        self.query_one("#agent-select", Select).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "force-btn":
            select = self.query_one("#agent-select", Select)
            if select.value:
                self.dismiss(str(select.value))
            return
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class SkipTurnsDialog(ModalScreen[tuple[str, int] | None]):
    """Modal dialog for skipping an agent's turns."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    SKIP_OPTIONS = [
        ("1 turn", 1),
        ("3 turns", 3),
        ("5 turns", 5),
        ("10 turns", 10),
    ]

    def __init__(self, agent_names: list[str] | None = None):
        super().__init__()
        self.agent_names = agent_names or ["Ember", "Sage", "River"]

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog", id="skip-dialog"):
            yield Static("Skip Agent Turns", classes="dialog-title")
            yield Static(
                "Skip this agent's turns for a while. Good for giving them rest.",
                classes="dialog-help"
            )
            yield Select(
                [(name, name) for name in self.agent_names],
                prompt="Choose agent",
                id="agent-select",
            )
            yield Select(
                [(desc, val) for desc, val in self.SKIP_OPTIONS],
                prompt="Number of turns to skip",
                id="skip-select",
            )
            with Horizontal(classes="dialog-buttons"):
                yield Button("Skip Turns", variant="primary", id="skip-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def on_mount(self) -> None:
        self.query_one("#agent-select", Select).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "skip-btn":
            agent_select = self.query_one("#agent-select", Select)
            skip_select = self.query_one("#skip-select", Select)
            if agent_select.value and skip_select.value:
                self.dismiss((str(agent_select.value), int(skip_select.value)))
            return
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ConfirmEndConversationDialog(ModalScreen[bool]):
    """Modal dialog to confirm ending the current conversation."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, participants: list[str] | None = None):
        super().__init__()
        self.participants = participants or []

    def compose(self) -> ComposeResult:
        participants_str = " and ".join(self.participants) if self.participants else "the agents"
        with Vertical(classes="dialog", id="end-convo-dialog"):
            yield Static("End Conversation?", classes="dialog-title")
            yield Static(
                f"This will end the conversation between {participants_str}. "
                "They'll part ways without saying goodbye.",
                classes="dialog-help"
            )
            with Horizontal(classes="dialog-buttons"):
                yield Button("End It", variant="warning", id="end-btn")
                yield Button("Let It Continue", variant="default", id="cancel-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "end-btn":
            self.dismiss(True)
            return
        self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)


# === Manual Observation Dialog ===


class ManualObservationDialog(ModalScreen[tuple[str, str, dict] | None]):
    """
    Modal dialog for manually invoking interpreter observations.

    Lets the Observer correct interpreter misses by manually
    reporting movements, moods, actions, etc.

    Note: In engine, conversation-related tools are not available
    as conversations are handled by explicit agent tool calls.
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    # Tool options are auto-generated from the interpreter registry
    # This ensures TUI stays in sync when new tools are added
    @property
    def tool_options(self) -> list[tuple[str, str]]:
        return get_tool_options_for_tui()

    def __init__(
        self,
        agent_names: list[str],
        location_paths: dict[str, list[str]],
        agent_locations: dict[str, str],
    ):
        """
        Args:
            agent_names: List of agent names
            location_paths: Map of location_id -> list of connected locations
            agent_locations: Map of agent_name -> current location
        """
        super().__init__()
        self.agent_names = agent_names
        self.location_paths = location_paths
        self.agent_locations = agent_locations
        self._selected_agent: str | None = None
        self._selected_tool: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog", id="observation-dialog"):
            yield Static("Manual Observation", classes="dialog-title")
            yield Static(
                "Correct an interpreter miss by manually reporting what happened.",
                classes="dialog-help"
            )
            yield Label("Agent:")
            yield Select(
                [(name, name) for name in self.agent_names],
                prompt="Select agent",
                id="agent-select",
            )
            yield Label("Observation type:")
            yield Select(
                [(desc, val) for desc, val in self.tool_options],
                prompt="Select observation",
                id="tool-select",
            )
            # Dynamic input container - will be populated based on tool selection
            yield Vertical(id="input-container")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Apply", variant="primary", id="apply-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def on_mount(self) -> None:
        self.query_one("#agent-select", Select).focus()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle selection changes to update dynamic inputs."""
        if event.select.id == "agent-select":
            self._selected_agent = str(event.value) if event.value else None
            self._update_inputs()
        elif event.select.id == "tool-select":
            self._selected_tool = str(event.value) if event.value else None
            self._update_inputs()

    def _update_inputs(self) -> None:
        """Update the input container based on selected tool."""
        container = self.query_one("#input-container", Vertical)
        container.remove_children()

        if not self._selected_tool:
            return

        tool = self._selected_tool

        if tool == "report_movement" or tool == "report_propose_move_together":
            # Show path selector based on agent's current location
            paths = []
            if self._selected_agent:
                agent_loc = self.agent_locations.get(self._selected_agent, "")
                paths = self.location_paths.get(agent_loc, [])

            if paths:
                container.mount(Label("Destination:"))
                container.mount(Select(
                    [(p.replace("_", " ").title(), p) for p in paths],
                    prompt="Select destination",
                    id="destination-select",
                ))
            else:
                container.mount(Label("No paths available from current location"))

        elif tool == "report_mood":
            container.mount(Label("Mood:"))
            container.mount(Input(
                placeholder="contemplative, joyful, tired...",
                id="mood-input",
            ))

        elif tool == "report_resting":
            container.mount(Label("(No additional input needed)"))

        elif tool == "report_sleeping":
            container.mount(Label("(Agent will sleep until woken by time change or visitor)"))

        elif tool == "report_action":
            container.mount(Label("Action description:"))
            container.mount(Input(
                placeholder="worked on the chair, read a book...",
                id="action-input",
            ))

        elif tool == "report_next_speaker":
            # Show agent selector for next speaker (excluding current agent)
            other_agents = [a for a in self.agent_names if a != self._selected_agent]
            if other_agents:
                container.mount(Label("Next speaker:"))
                container.mount(Select(
                    [(name, name) for name in other_agents],
                    prompt="Select next speaker",
                    id="next-speaker-select",
                ))
            else:
                container.mount(Label("No other agents available"))

    def _build_tool_input(self) -> dict:
        """Build the tool input dict based on current selections."""
        if not self._selected_tool:
            return {}

        tool = self._selected_tool
        result = {}

        try:
            if tool == "report_movement" or tool == "report_propose_move_together":
                select = self.query_one("#destination-select", Select)
                if select.value:
                    result["destination"] = str(select.value)

            elif tool == "report_mood":
                input_widget = self.query_one("#mood-input", Input)
                result["mood"] = input_widget.value.strip()

            elif tool == "report_action":
                input_widget = self.query_one("#action-input", Input)
                result["description"] = input_widget.value.strip()

            elif tool == "report_next_speaker":
                select = self.query_one("#next-speaker-select", Select)
                if select.value:
                    result["next_speaker"] = str(select.value)

            # report_resting and report_sleeping have no inputs

        except Exception:
            pass  # Widget might not exist yet

        return result

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "apply-btn":
            if self._selected_agent and self._selected_tool:
                tool_input = self._build_tool_input()
                self.dismiss((self._selected_agent, self._selected_tool, tool_input))
            return
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


# === Compaction Dialog ===


class CompactDialog(ModalScreen[str | None]):
    """Modal dialog for manually triggering context compaction for an agent."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(
        self,
        agent_names: list[str],
        compaction_states: dict[str, dict] | None = None,
    ):
        """
        Args:
            agent_names: List of agent names
            compaction_states: Dict of agent_name -> {tokens, threshold, percent, is_compacting}
        """
        super().__init__()
        self.agent_names = agent_names
        self.compaction_states = compaction_states or {}

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog", id="compact-dialog"):
            yield Static("Force Compaction", classes="dialog-title")
            yield Static(
                "Manually trigger context compaction to reduce an agent's token usage.",
                classes="dialog-help"
            )
            # Build options with current token counts
            options = []
            for name in self.agent_names:
                state = self.compaction_states.get(name, {})
                tokens = state.get("tokens", 0)
                percent = state.get("percent", 0)
                if tokens > 0:
                    label = f"{name} ({tokens/1000:.0f}K tokens, {percent}%)"
                else:
                    label = f"{name} (no token data)"
                options.append((label, name))

            yield Select(
                options,
                prompt="Select agent to compact",
                id="agent-select",
            )
            with Horizontal(classes="dialog-buttons"):
                yield Button("Compact", variant="primary", id="compact-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def on_mount(self) -> None:
        self.query_one("#agent-select", Select).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "compact-btn":
            select = self.query_one("#agent-select", Select)
            if select.value:
                self.dismiss(str(select.value))
            return
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
