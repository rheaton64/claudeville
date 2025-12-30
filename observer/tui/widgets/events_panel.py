"""Events feed widget showing recent village events."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, RichLog
from rich.text import Text

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.domain import DomainEvent


# Event types to hide from the feed (descriptive only, no state change)
HIDDEN_EVENT_TYPES = {
    "agent_action",  # Interpreter-reported actions (just prose, no state change)
}

# Map DomainEvent type literals to display colors
DOMAIN_EVENT_COLORS = {
    # Agent events
    "agent_moved": "cyan",
    "agent_action": "green",
    "agent_slept": "dim cyan",
    "agent_woke": "cyan",
    "agent_mood_changed": "dim",
    "agent_energy_changed": "dim",
    "agent_last_active_tick_updated": "dim",

    # Conversation events
    "conversation_started": "yellow",
    "conversation_joined": "yellow",
    "conversation_left": "yellow",
    "conversation_turn": "yellow",
    "conversation_ended": "yellow",
    "conversation_invited": "yellow",
    "conversation_invite_accepted": "yellow",
    "conversation_invite_declined": "dim yellow",
    "conversation_invite_expired": "dim yellow",
    "conversation_next_speaker_set": "dim yellow",

    # World events
    "world_event": "magenta",
    "weather_changed": "magenta",
}


def _get_event_description(event: "DomainEvent") -> str:
    """Extract a human-readable description from a DomainEvent."""
    event_type = event.type

    match event_type:
        # Agent events
        case "agent_moved":
            loc = event.to_location.replace("_", " ")
            return f"{event.agent} went to the {loc}."
        case "agent_action":
            return f"{event.agent}: {event.description}"
        case "agent_slept":
            return f"{event.agent} fell asleep."
        case "agent_woke":
            return f"{event.agent} woke up ({event.reason})."
        case "agent_mood_changed":
            return f"{event.agent}'s mood: {event.new_mood}"
        case "agent_energy_changed":
            return f"{event.agent}'s energy: {event.new_energy}"
        case "agent_last_active_tick_updated":
            return f"{event.agent} active tick updated"

        # Conversation events
        case "conversation_started":
            participants = " and ".join(event.initial_participants)
            return f"{participants} started a conversation."
        case "conversation_joined":
            return f"{event.agent} joined the conversation."
        case "conversation_left":
            return f"{event.agent} left the conversation."
        case "conversation_turn":
            preview = event.narrative[:60] + "..." if len(event.narrative) > 60 else event.narrative
            return f"{event.speaker}: {preview}"
        case "conversation_ended":
            return f"Conversation ended: {event.reason}"
        case "conversation_invited":
            return f"{event.inviter} invited {event.invitee} to chat."
        case "conversation_invite_accepted":
            return f"{event.invitee} accepted {event.inviter}'s invitation."
        case "conversation_invite_declined":
            return f"{event.invitee} declined {event.inviter}'s invitation."
        case "conversation_invite_expired":
            return f"Invitation from {event.inviter} to {event.invitee} expired."
        case "conversation_next_speaker_set":
            return f"Next speaker: {event.next_speaker}"

        # World events
        case "world_event":
            return event.description
        case "weather_changed":
            return f"Weather changed to {event.new_weather}."

        case _:
            return f"[{event_type}] event occurred"


class EventsFeed(Vertical):
    """
    A scrolling feed of recent village events.

    Events are displayed with tick numbers and color-coded by type.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._max_events = 50

    def compose(self) -> ComposeResult:
        yield Static("Recent Events", id="events-feed-label")
        yield RichLog(wrap=True, highlight=False, markup=True, id="events-log")

    def add_domain_event(self, event: "DomainEvent") -> None:
        """Add a DomainEvent to the feed."""
        # Skip hidden event types (descriptive only, no state change)
        if event.type in HIDDEN_EVENT_TYPES:
            return

        log = self.query_one("#events-log", RichLog)

        text = Text()

        # Tick number
        text.append(f"[{event.tick:03d}] ", style="dim")

        # Event description with type-based color
        color = DOMAIN_EVENT_COLORS.get(event.type, "white")
        description = _get_event_description(event)
        text.append(description, style=color)

        log.write(text)

    def add_event_dict(self, event_dict: dict) -> None:
        """Add an event from a dictionary (for engine callbacks)."""
        log = self.query_one("#events-log", RichLog)

        text = Text()

        # Tick number
        tick = event_dict.get("tick", 0)
        text.append(f"[{tick:03d}] ", style="dim")

        # Event description
        event_type = event_dict.get("type", "activity")
        description = event_dict.get("description", "Something happened")
        color = DOMAIN_EVENT_COLORS.get(event_type, "white")
        text.append(description, style=color)

        log.write(text)

    def add_simple_event(self, tick: int, description: str, event_type: str = "activity") -> None:
        """Add an event with simple parameters."""
        log = self.query_one("#events-log", RichLog)

        text = Text()
        text.append(f"[{tick:03d}] ", style="dim")

        color = DOMAIN_EVENT_COLORS.get(event_type, "white")
        text.append(description, style=color)

        log.write(text)

    def load_recent_events(self, events: list) -> None:
        """Load a batch of recent events (e.g., on startup)."""
        log = self.query_one("#events-log", RichLog)
        log.clear()

        for event in events[-self._max_events:]:
            if hasattr(event, "type") and hasattr(event, "tick"):
                # DomainEvent object - add_domain_event handles filtering
                self.add_domain_event(event)
            elif isinstance(event, dict):
                # Dict events - check for hidden types
                if event.get("type") in HIDDEN_EVENT_TYPES:
                    continue
                self.add_event_dict(event)

    def clear(self) -> None:
        """Clear the events log."""
        log = self.query_one("#events-log", RichLog)
        log.clear()
