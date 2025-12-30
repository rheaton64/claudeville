"""
Display snapshots - Read-only views of village state for the TUI/CLI.

These types are optimized for display, not for domain logic.
They flatten nested structures and compute derived values.
"""

from dataclasses import dataclass
from datetime import datetime

from engine.domain import (
    AgentName,
    AgentSnapshot,
    Conversation,
    ConversationId,
    Invitation,
    LocationId,
    TimeSnapshot,
    WorldSnapshot,
)
from engine.services.scheduler import ScheduledEvent


@dataclass(frozen=True)
class AgentDisplaySnapshot:
    """Flattened agent state for display."""

    name: str
    model_display: str
    location: str
    mood: str
    energy: int
    is_sleeping: bool

    # Computed from conversation state
    in_conversation: bool
    has_pending_invite: bool

    @classmethod
    def from_domain(
        cls,
        agent: AgentSnapshot,
        in_conversation: bool = False,
        has_pending_invite: bool = False,
    ) -> "AgentDisplaySnapshot":
        """Create from domain AgentSnapshot."""
        return cls(
            name=agent.name,
            model_display=agent.model.display_name,
            location=agent.location,
            mood=agent.mood,
            energy=agent.energy,
            is_sleeping=agent.is_sleeping,
            in_conversation=in_conversation,
            has_pending_invite=has_pending_invite,
        )


@dataclass(frozen=True)
class ConversationDisplaySnapshot:
    """Conversation state for display."""

    id: str
    location: str
    participants: tuple[str, ...]
    privacy: str
    turn_count: int
    last_speaker: str | None

    @classmethod
    def from_domain(cls, conv: Conversation) -> "ConversationDisplaySnapshot":
        """Create from domain Conversation."""
        last_speaker = None
        if conv.history:
            last_speaker = conv.history[-1].speaker

        return cls(
            id=conv.id,
            location=conv.location,
            participants=tuple(sorted(conv.participants)),  # frozenset -> sorted tuple
            privacy=conv.privacy,
            turn_count=len(conv.history),
            last_speaker=last_speaker,
        )


@dataclass(frozen=True)
class InviteDisplaySnapshot:
    """Pending invitation for display."""

    conversation_id: str
    inviter: str
    invitee: str
    location: str
    privacy: str
    invited_at: datetime

    @classmethod
    def from_domain(cls, invite: Invitation) -> "InviteDisplaySnapshot":
        """Create from domain Invitation."""
        return cls(
            conversation_id=invite.conversation_id,
            inviter=invite.inviter,
            invitee=invite.invitee,
            location=invite.location,
            privacy=invite.privacy,
            invited_at=invite.invited_at,
        )


@dataclass(frozen=True)
class ScheduleDisplaySnapshot:
    """Scheduling state for display."""

    pending_events: tuple["ScheduledEventDisplay", ...]
    forced_next: str | None
    skip_counts: dict[str, int]
    turn_counts: dict[str, int]


@dataclass(frozen=True)
class ScheduledEventDisplay:
    """Single scheduled event for display."""

    due_time: datetime
    event_type: str
    target_id: str
    location: str

    @classmethod
    def from_domain(cls, event: ScheduledEvent) -> "ScheduledEventDisplay":
        """Create from ScheduledEvent."""
        return cls(
            due_time=event.due_time,
            event_type=event.event_type,
            target_id=event.target_id,
            location=event.location_id,
        )


@dataclass(frozen=True)
class TimeDisplaySnapshot:
    """Time state for display."""

    tick: int
    timestamp: datetime
    day_number: int
    time_of_day: str
    clock_time: str

    @classmethod
    def from_domain(cls, tick: int, time_snapshot: TimeSnapshot) -> "TimeDisplaySnapshot":
        """Create from domain TimeSnapshot."""
        # Format clock time as HH:MM
        hour = time_snapshot.timestamp.hour
        minute = time_snapshot.timestamp.minute
        clock_time = f"{hour:02d}:{minute:02d}"

        return cls(
            tick=tick,
            timestamp=time_snapshot.timestamp,
            day_number=time_snapshot.day_number,
            time_of_day=time_snapshot.period.value,
            clock_time=clock_time,
        )


@dataclass(frozen=True)
class VillageDisplaySnapshot:
    """Complete village state for display."""

    tick: int
    time: TimeDisplaySnapshot
    weather: str
    agents: dict[str, AgentDisplaySnapshot]
    conversations: list[ConversationDisplaySnapshot]
    pending_invites: list[InviteDisplaySnapshot]
    schedule: ScheduleDisplaySnapshot
