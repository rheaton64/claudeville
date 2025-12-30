from datetime import datetime
from dataclasses import dataclass, field
from typing import Literal, Any
import heapq

from engine.domain import AgentName, LocationId, ConversationId


@dataclass(frozen=True)
class SchedulerState:
    """Serializable scheduler state for snapshots."""
    queue: tuple["ScheduledEvent", ...]
    forced_next: AgentName | None
    skip_counts: dict[AgentName, int]
    turn_counts: dict[AgentName, int]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON storage."""
        return {
            "queue": [
                {
                    "due_time": e.due_time.isoformat(),
                    "priority": e.priority,
                    "event_type": e.event_type,
                    "target_id": e.target_id,
                    "location_id": e.location_id,
                }
                for e in self.queue
            ],
            "forced_next": self.forced_next,
            "skip_counts": dict(self.skip_counts),
            "turn_counts": dict(self.turn_counts),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SchedulerState":
        """Deserialize from dict."""
        queue = tuple(
            ScheduledEvent(
                due_time=datetime.fromisoformat(e["due_time"]),
                priority=e["priority"],
                event_type=e["event_type"],
                target_id=e["target_id"],
                location_id=LocationId(e["location_id"]),
            )
            for e in data.get("queue", [])
        )
        return cls(
            queue=queue,
            forced_next=data.get("forced_next"),
            skip_counts={AgentName(k): v for k, v in data.get("skip_counts", {}).items()},
            turn_counts={AgentName(k): v for k, v in data.get("turn_counts", {}).items()},
        )


@dataclass(order=True)
class ScheduledEvent:
    """A future action due at a specific time."""
    due_time: datetime
    priority: int = field(compare=True)  # Lower = higher priority
    event_type: Literal["agent_turn", "conversation_turn", "invite_response"] = field(compare=False)
    target_id: str = field(compare=False)  # agent name or conversation id
    location_id: LocationId = field(compare=False)

    def __post_init__(self):
        # Ensure comparison works correctly with heapq
        pass


class Scheduler:
    """
    Event-driven scheduler with priority queue.

    Manages when agents take turns based on:
    - Conversation participation (5 min pace)
    - Invite responses (5 min window)
    - Solo activity (accumulated time threshold)
    """

    CONVERSATION_PACE_MINUTES = 5
    SOLO_PACE_MINUTES = 120
    INVITE_RESPONSE_MINUTES = 5

    def __init__(self):
        self._queue: list[ScheduledEvent] = []  # heapq
        self._agent_events: dict[str, ScheduledEvent] = {}  # agent -> turn
        self._invite_events: dict[str, ScheduledEvent] = {}  # agent -> invite response
        self._conversation_events: dict[str, ScheduledEvent] = {}  # conversation -> turn

        # Modifiers (observer controls)
        self._forced_next: AgentName | None = None
        self._skip_counts: dict[AgentName, int] = {}
        self._turn_counts: dict[AgentName, int] = {}

    def schedule(self, event: ScheduledEvent) -> None:
        """Schedule a new event."""
        heapq.heappush(self._queue, event)
        if event.event_type == "agent_turn":
            self._agent_events[event.target_id] = event
        elif event.event_type == "invite_response":
            self._invite_events[event.target_id] = event
        elif event.event_type == "conversation_turn":
            self._conversation_events[event.target_id] = event

    def schedule_agent_turn(
        self,
        agent: AgentName,
        location: LocationId,
        due_time: datetime,
        priority: int = 10,
    ) -> None:
        """Schedule an agent's next turn."""
        event = ScheduledEvent(
            due_time=due_time,
            priority=priority,
            event_type="agent_turn",
            target_id=agent,
            location_id=location,
        )
        self.schedule(event)

    def schedule_conversation_turn(
        self,
        conversation_id: ConversationId,
        location: LocationId,
        due_time: datetime,
    ) -> None:
        """Schedule a conversation's next turn."""
        event = ScheduledEvent(
            due_time=due_time,
            priority=5,  # Conversations have higher priority
            event_type="conversation_turn",
            target_id=conversation_id,
            location_id=location,
        )
        self.schedule(event)

    def schedule_invite_response(
        self,
        agent: AgentName,
        location: LocationId,
        due_time: datetime,
    ) -> None:
        """Schedule an invite response window."""
        event = ScheduledEvent(
            due_time=due_time,
            priority=1,  # Invite responses are highest priority
            event_type="invite_response",
            target_id=agent,
            location_id=location,
        )
        self.schedule(event)

    def get_earliest_due_time(self) -> datetime | None:
        """Get the earliest due time, or None if queue is empty."""
        while self._queue:
            # Peek at the top
            event = self._queue[0]
            return event.due_time
        return None

    def pop_events_at(self, time: datetime) -> list[ScheduledEvent]:
        """Pop all events due at exactly this time."""
        events = []
        while self._queue and self._queue[0].due_time == time:
            event = heapq.heappop(self._queue)
            events.append(event)
            self._discard_indexed_event(event)
        return events

    def pop_events_up_to(self, time: datetime) -> list[ScheduledEvent]:
        """Pop all events due at or before this time."""
        events = []
        while self._queue and self._queue[0].due_time <= time:
            event = heapq.heappop(self._queue)
            events.append(event)
            self._discard_indexed_event(event)
        return events

    def cancel_agent_events(self, agent: AgentName) -> None:
        """Cancel all pending events for an agent."""
        self._agent_events.pop(agent, None)
        self._invite_events.pop(agent, None)
        self._queue = [e for e in self._queue if e.target_id != agent]
        heapq.heapify(self._queue)

    def has_pending_event(self, agent: AgentName) -> bool:
        """Check if an agent has a pending scheduled event."""
        return agent in self._agent_events or agent in self._invite_events

    def has_pending_agent_turn(self, agent: AgentName) -> bool:
        """Check if an agent has a pending turn event."""
        return agent in self._agent_events

    def has_pending_invite_response(self, agent: AgentName) -> bool:
        """Check if an agent has a pending invite response event."""
        return agent in self._invite_events

    def has_pending_conversation_turn(self, conversation_id: ConversationId) -> bool:
        """Check if a conversation has a pending turn event."""
        return conversation_id in self._conversation_events

    def _discard_indexed_event(self, event: ScheduledEvent) -> None:
        """Remove event from index dictionaries."""
        if event.event_type == "agent_turn":
            self._agent_events.pop(event.target_id, None)
        elif event.event_type == "invite_response":
            self._invite_events.pop(event.target_id, None)
        elif event.event_type == "conversation_turn":
            self._conversation_events.pop(event.target_id, None)

    # --- Observer modifiers ---

    def force_next_turn(self, agent: AgentName) -> None:
        """Force this agent to act next."""
        self._forced_next = agent

    def clear_forced_next(self) -> None:
        """Clear the forced next agent."""
        self._forced_next = None

    def get_forced_next(self) -> AgentName | None:
        """Get the forced next agent, if any."""
        return self._forced_next

    def skip_turns(self, agent: AgentName, count: int) -> None:
        """Skip N turns for an agent."""
        self._skip_counts[agent] = count

    def get_skip_count(self, agent: AgentName) -> int:
        """Get remaining skip count for an agent."""
        return self._skip_counts.get(agent, 0)

    def decrement_skip(self, agent: AgentName) -> None:
        """Decrement skip count after a skipped turn."""
        if agent in self._skip_counts:
            self._skip_counts[agent] -= 1
            if self._skip_counts[agent] <= 0:
                del self._skip_counts[agent]

    def record_turn(self, agent: AgentName) -> None:
        """Record that an agent took a turn."""
        self._turn_counts[agent] = self._turn_counts.get(agent, 0) + 1
        if self._forced_next == agent:
            self._forced_next = None

    def get_turn_count(self, agent: AgentName) -> int:
        """Get total turn count for an agent."""
        return self._turn_counts.get(agent, 0)

    # --- State persistence ---

    def to_state(self) -> SchedulerState:
        """Export current state for snapshot persistence."""
        return SchedulerState(
            queue=tuple(self._queue),
            forced_next=self._forced_next,
            skip_counts=dict(self._skip_counts),
            turn_counts=dict(self._turn_counts),
        )

    def load_state(self, state: SchedulerState) -> None:
        """Load state from a snapshot."""
        # Rebuild queue from state
        self._queue = list(state.queue)
        heapq.heapify(self._queue)

        # Rebuild indexes from queue
        self._agent_events.clear()
        self._invite_events.clear()
        self._conversation_events.clear()
        for event in self._queue:
            if event.event_type == "agent_turn":
                self._agent_events[event.target_id] = event
            elif event.event_type == "invite_response":
                self._invite_events[event.target_id] = event
            elif event.event_type == "conversation_turn":
                self._conversation_events[event.target_id] = event

        # Restore modifiers
        self._forced_next = state.forced_next
        self._skip_counts = dict(state.skip_counts)
        self._turn_counts = dict(state.turn_counts)
