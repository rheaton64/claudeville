"""Scheduling status panel widget for ClaudeVille Observer v2."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static
from rich.text import Text

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.engine import VillageEngine


class ScheduleStatusPanel(Vertical):
    """
    A panel showing scheduling status and controls.

    Displays:
    - Current conversation status
    - Next scheduled events
    - Turn counts per agent
    - Active modifiers (forced, skips)
    """

    DEFAULT_CSS = """
    ScheduleStatusPanel {
        width: 30;
        min-width: 25;
        border-left: solid #30363d;
        padding: 0 1;
        background: #161b22;
    }

    #schedule-title {
        text-style: bold;
        color: #c9d1d9;
        padding: 0 0 1 0;
        text-align: center;
    }

    .schedule-section {
        margin-bottom: 1;
    }

    .schedule-section-label {
        color: #8b949e;
        text-style: bold;
        margin-bottom: 0;
    }

    .schedule-content {
        padding-left: 1;
    }

    .modifier-active {
        color: #f0883e;
    }

    .conversation-active {
        color: #a78bfa;
    }

    .agent-ember {
        color: #f97316;
    }

    .agent-sage {
        color: #a78bfa;
    }

    .agent-river {
        color: #38bdf8;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._engine: "VillageEngine | None" = None

    def compose(self) -> ComposeResult:
        yield Static("Scheduling", id="schedule-title")

        # Conversation status section
        with Vertical(classes="schedule-section"):
            yield Static("Conversation:", classes="schedule-section-label")
            yield Static("None active", id="conversation-status", classes="schedule-content")

        # Next up section
        with Vertical(classes="schedule-section"):
            yield Static("Next Up:", classes="schedule-section-label")
            yield Static("—", id="next-up-status", classes="schedule-content")

        # Time increment section
        with Vertical(classes="schedule-section"):
            yield Static("Time Increment:", classes="schedule-section-label")
            yield Static("—", id="time-increment", classes="schedule-content")

        # Turn counts section
        with Vertical(classes="schedule-section"):
            yield Static("Turn Counts:", classes="schedule-section-label")
            yield Static("—", id="turn-counts", classes="schedule-content")

        # Agent status section
        with Vertical(classes="schedule-section"):
            yield Static("Agent Status:", classes="schedule-section-label")
            yield Static("—", id="agent-status", classes="schedule-content")

        # Modifiers section
        with Vertical(classes="schedule-section"):
            yield Static("Modifiers:", classes="schedule-section-label")
            yield Static("None", id="modifiers-status", classes="schedule-content")

    def set_engine(self, engine: "VillageEngine") -> None:
        """Set the engine reference for updates."""
        self._engine = engine

    def refresh_status(self) -> None:
        """Refresh all status displays from the engine."""
        if not self._engine:
            return

        self._update_conversation_status()
        self._update_next_up()
        self._update_time_increment()
        self._update_turn_counts()
        self._update_agent_status()
        self._update_modifiers()

    def _update_conversation_status(self) -> None:
        """Update the conversation status display."""
        status_widget = self.query_one("#conversation-status", Static)

        conversations = self._engine.observer.get_conversations()
        if conversations:
            text = Text()
            for i, conv in enumerate(conversations):
                if i > 0:
                    text.append("\n---\n", style="dim")

                participants = " & ".join(conv.participants)
                location = conv.location.replace("_", " ")

                text.append(f"{participants}\n", style="bold #a78bfa")
                text.append(f"@ {location} ({conv.turn_count} turns)", style="dim")

            status_widget.update(text)
        else:
            status_widget.update(Text("None active", style="dim"))

    def _update_next_up(self) -> None:
        """Update the next-up display using scheduled events."""
        status_widget = self.query_one("#next-up-status", Static)

        schedule = self._engine.observer.get_schedule_snapshot()
        pending = schedule.pending_events[:5]  # Show first 5

        if not pending:
            status_widget.update(Text("No events scheduled", style="dim"))
            return

        text = Text()
        for i, event in enumerate(pending):
            if i > 0:
                text.append("\n")

            target = event.target_id
            location = event.location.replace("_", " ")
            event_type = event.event_type

            # Color based on event type and target
            if event_type == "agent_turn":
                color = self._get_agent_color(target)
                text.append(f"{target}", style=color)
                text.append(f" @ {location}", style="dim")
            elif event_type == "conversation_turn":
                text.append("Conv turn", style="#a78bfa")
                text.append(f" @ {location}", style="dim")
            elif event_type == "invite_response":
                text.append(f"Invite for {target}", style="#f0883e")
            else:
                text.append(f"{event_type}: {target}", style="dim")

        status_widget.update(text)

    def _update_time_increment(self) -> None:
        """Update the time increment display."""
        status_widget = self.query_one("#time-increment", Static)

        # Check if any conversation is active
        has_conversation = self._engine.observer.has_active_conversation()

        # Check if all agents are sleeping
        agents = self._engine.observer.get_all_agents_snapshot()
        all_sleeping = all(agent.is_sleeping for agent in agents.values()) if agents else False

        text = Text()

        if all_sleeping:
            text.append("⏭ Skip to next period\n", style="bold #a78bfa")
            text.append("  (all sleeping)", style="dim")
        elif has_conversation:
            text.append("💬 +5 minutes\n", style="bold")
            text.append("  (conversation)", style="dim")
        else:
            text.append("⏳ +2 hours\n", style="bold")
            text.append("  (normal)", style="dim")

        status_widget.update(text)

    def _update_turn_counts(self) -> None:
        """Update the turn counts display."""
        status_widget = self.query_one("#turn-counts", Static)

        schedule = self._engine.observer.get_schedule_snapshot()
        turn_counts = schedule.turn_counts

        if not turn_counts:
            status_widget.update(Text("No turns yet", style="dim"))
            return

        text = Text()
        for i, (name, count) in enumerate(sorted(turn_counts.items())):
            if i > 0:
                text.append("\n")
            color = self._get_agent_color(name)
            text.append(f"{name}: ", style=color)
            text.append(f"{count}", style="bold")

        status_widget.update(text)

    def _update_agent_status(self) -> None:
        """Update the agent status display."""
        status_widget = self.query_one("#agent-status", Static)

        agents = self._engine.observer.get_all_agents_snapshot()
        if not agents:
            status_widget.update(Text("No agents", style="dim"))
            return

        text = Text()
        for i, (name, agent) in enumerate(sorted(agents.items())):
            if i > 0:
                text.append("\n")

            color = self._get_agent_color(name)
            text.append(f"{name}: ", style=color)

            if agent.is_sleeping:
                text.append("💤 sleeping", style="dim")
            elif agent.in_conversation:
                text.append("💬 chatting", style="#a78bfa")
            elif agent.has_pending_invite:
                text.append("📨 has invite", style="#f0883e")
            else:
                text.append("✓ active", style="bold #3fb950")

        status_widget.update(text)

    def _update_modifiers(self) -> None:
        """Update the modifiers display."""
        status_widget = self.query_one("#modifiers-status", Static)

        schedule = self._engine.observer.get_schedule_snapshot()
        has_modifiers = False
        text = Text()

        # Forced next
        if schedule.forced_next:
            has_modifiers = True
            agent = schedule.forced_next
            color = self._get_agent_color(agent)
            text.append("Force: ", style="bold #f0883e")
            text.append(f"{agent}\n", style=color)

        # Skips
        for agent, count in schedule.skip_counts.items():
            if count > 0:
                has_modifiers = True
                color = self._get_agent_color(agent)
                text.append(f"{agent}: ", style=color)
                text.append(f"skip {count}\n", style="#d29922")

        if not has_modifiers:
            status_widget.update(Text("None", style="dim"))
        else:
            # Remove trailing newline while preserving styles
            text.rstrip()
            status_widget.update(text)

    def _get_agent_color(self, name: str) -> str:
        """Get the color for an agent name."""
        colors = {
            "Ember": "#f97316",
            "Sage": "#a78bfa",
            "River": "#38bdf8",
        }
        return colors.get(name, "#c9d1d9")
