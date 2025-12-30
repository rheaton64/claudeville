"""Tests for engine.services.scheduler module."""

import pytest
from datetime import datetime, timedelta

from engine.domain import AgentName, LocationId, ConversationId
from engine.services.scheduler import Scheduler, ScheduledEvent


class TestScheduledEvent:
    """Tests for ScheduledEvent dataclass."""

    def test_creation(self, base_datetime: datetime):
        """Test creating a ScheduledEvent."""
        event = ScheduledEvent(
            due_time=base_datetime,
            priority=10,
            event_type="agent_turn",
            target_id="Ember",
            location_id=LocationId("workshop"),
        )
        assert event.due_time == base_datetime
        assert event.priority == 10
        assert event.event_type == "agent_turn"

    def test_ordering_by_due_time(self, base_datetime: datetime):
        """Test events are ordered by due_time first."""
        earlier = ScheduledEvent(
            due_time=base_datetime,
            priority=10,
            event_type="agent_turn",
            target_id="Ember",
            location_id=LocationId("workshop"),
        )
        later = ScheduledEvent(
            due_time=base_datetime + timedelta(minutes=5),
            priority=10,
            event_type="agent_turn",
            target_id="Sage",
            location_id=LocationId("library"),
        )
        assert earlier < later

    def test_ordering_by_priority_same_time(self, base_datetime: datetime):
        """Test events at same time are ordered by priority."""
        high_priority = ScheduledEvent(
            due_time=base_datetime,
            priority=1,  # Lower = higher priority
            event_type="invite_response",
            target_id="Ember",
            location_id=LocationId("workshop"),
        )
        low_priority = ScheduledEvent(
            due_time=base_datetime,
            priority=10,
            event_type="agent_turn",
            target_id="Sage",
            location_id=LocationId("library"),
        )
        assert high_priority < low_priority


class TestSchedulerBasics:
    """Tests for basic Scheduler functionality."""

    def test_empty_scheduler(self, scheduler: Scheduler):
        """Test empty scheduler behavior."""
        assert scheduler.get_earliest_due_time() is None
        assert scheduler.pop_events_up_to(datetime.now()) == []

    def test_schedule_agent_turn(self, scheduler: Scheduler, base_datetime: datetime):
        """Test scheduling an agent turn."""
        scheduler.schedule_agent_turn(
            agent=AgentName("Ember"),
            location=LocationId("workshop"),
            due_time=base_datetime,
        )
        assert scheduler.has_pending_event(AgentName("Ember"))
        assert scheduler.has_pending_agent_turn(AgentName("Ember"))

    def test_schedule_conversation_turn(self, scheduler: Scheduler, base_datetime: datetime):
        """Test scheduling a conversation turn."""
        scheduler.schedule_conversation_turn(
            conversation_id=ConversationId("conv-001"),
            location=LocationId("workshop"),
            due_time=base_datetime,
        )
        assert scheduler.has_pending_conversation_turn(ConversationId("conv-001"))

    def test_schedule_invite_response(self, scheduler: Scheduler, base_datetime: datetime):
        """Test scheduling an invite response."""
        scheduler.schedule_invite_response(
            agent=AgentName("Sage"),
            location=LocationId("library"),
            due_time=base_datetime,
        )
        assert scheduler.has_pending_event(AgentName("Sage"))
        assert scheduler.has_pending_invite_response(AgentName("Sage"))


class TestSchedulerPriorities:
    """Tests for priority handling."""

    def test_default_agent_turn_priority(self, scheduler: Scheduler, base_datetime: datetime):
        """Test agent turns have default priority 10."""
        scheduler.schedule_agent_turn(
            agent=AgentName("Ember"),
            location=LocationId("workshop"),
            due_time=base_datetime,
        )
        events = scheduler.pop_events_up_to(base_datetime)
        assert events[0].priority == 10

    def test_conversation_turn_priority(self, scheduler: Scheduler, base_datetime: datetime):
        """Test conversation turns have priority 5."""
        scheduler.schedule_conversation_turn(
            conversation_id=ConversationId("conv-001"),
            location=LocationId("workshop"),
            due_time=base_datetime,
        )
        events = scheduler.pop_events_up_to(base_datetime)
        assert events[0].priority == 5

    def test_invite_response_priority(self, scheduler: Scheduler, base_datetime: datetime):
        """Test invite responses have priority 1 (highest)."""
        scheduler.schedule_invite_response(
            agent=AgentName("Sage"),
            location=LocationId("library"),
            due_time=base_datetime,
        )
        events = scheduler.pop_events_up_to(base_datetime)
        assert events[0].priority == 1

    def test_priority_ordering_at_same_time(self, scheduler: Scheduler, base_datetime: datetime):
        """Test that higher priority events come first at same due_time."""
        # Schedule in wrong order to test sorting
        scheduler.schedule_agent_turn(
            agent=AgentName("Ember"),
            location=LocationId("workshop"),
            due_time=base_datetime,
        )
        scheduler.schedule_invite_response(
            agent=AgentName("Sage"),
            location=LocationId("library"),
            due_time=base_datetime,
        )
        scheduler.schedule_conversation_turn(
            conversation_id=ConversationId("conv-001"),
            location=LocationId("garden"),
            due_time=base_datetime,
        )

        events = scheduler.pop_events_up_to(base_datetime)
        priorities = [e.priority for e in events]
        # Should be sorted by priority (ascending)
        assert priorities == sorted(priorities)
        assert events[0].priority == 1  # invite_response
        assert events[1].priority == 5  # conversation_turn
        assert events[2].priority == 10  # agent_turn


class TestSchedulerPopOperations:
    """Tests for pop operations."""

    def test_pop_events_up_to(self, scheduler: Scheduler, base_datetime: datetime):
        """Test popping events up to a time."""
        t1 = base_datetime
        t2 = base_datetime + timedelta(minutes=5)
        t3 = base_datetime + timedelta(minutes=10)

        scheduler.schedule_agent_turn(AgentName("A"), LocationId("loc"), t1)
        scheduler.schedule_agent_turn(AgentName("B"), LocationId("loc"), t2)
        scheduler.schedule_agent_turn(AgentName("C"), LocationId("loc"), t3)

        # Pop up to t2 (includes t1 and t2)
        events = scheduler.pop_events_up_to(t2)
        assert len(events) == 2
        assert events[0].target_id == "A"
        assert events[1].target_id == "B"

        # Only t3 remains
        remaining = scheduler.pop_events_up_to(t3)
        assert len(remaining) == 1
        assert remaining[0].target_id == "C"

    def test_pop_events_at(self, scheduler: Scheduler, base_datetime: datetime):
        """Test popping events at exact time."""
        t1 = base_datetime
        t2 = base_datetime + timedelta(minutes=5)

        scheduler.schedule_agent_turn(AgentName("A"), LocationId("loc"), t1)
        scheduler.schedule_agent_turn(AgentName("B"), LocationId("loc"), t1)
        scheduler.schedule_agent_turn(AgentName("C"), LocationId("loc"), t2)

        # Pop only at t1
        events = scheduler.pop_events_at(t1)
        assert len(events) == 2

        # t2 event should still be there
        remaining = scheduler.pop_events_at(t2)
        assert len(remaining) == 1
        assert remaining[0].target_id == "C"

    def test_get_earliest_due_time(self, scheduler: Scheduler, base_datetime: datetime):
        """Test getting earliest due time."""
        t1 = base_datetime + timedelta(minutes=10)
        t2 = base_datetime + timedelta(minutes=5)  # Earlier

        scheduler.schedule_agent_turn(AgentName("A"), LocationId("loc"), t1)
        scheduler.schedule_agent_turn(AgentName("B"), LocationId("loc"), t2)

        assert scheduler.get_earliest_due_time() == t2


class TestSchedulerCancellation:
    """Tests for event cancellation."""

    def test_cancel_agent_events(self, scheduler: Scheduler, base_datetime: datetime):
        """Test canceling all events for an agent."""
        scheduler.schedule_agent_turn(AgentName("Ember"), LocationId("loc"), base_datetime)
        scheduler.schedule_invite_response(
            AgentName("Ember"),
            LocationId("loc"),
            base_datetime + timedelta(minutes=5),
        )

        assert scheduler.has_pending_event(AgentName("Ember"))

        scheduler.cancel_agent_events(AgentName("Ember"))

        assert not scheduler.has_pending_event(AgentName("Ember"))
        assert not scheduler.has_pending_agent_turn(AgentName("Ember"))
        assert not scheduler.has_pending_invite_response(AgentName("Ember"))

    def test_cancel_removes_from_queue(self, scheduler: Scheduler, base_datetime: datetime):
        """Test that cancel removes events from the queue."""
        scheduler.schedule_agent_turn(AgentName("Ember"), LocationId("loc"), base_datetime)
        scheduler.cancel_agent_events(AgentName("Ember"))

        events = scheduler.pop_events_up_to(base_datetime)
        assert len(events) == 0


class TestObserverModifiers:
    """Tests for observer control modifiers."""

    def test_force_next_turn(self, scheduler: Scheduler):
        """Test forcing next turn for an agent."""
        scheduler.force_next_turn(AgentName("Sage"))

        assert scheduler.get_forced_next() == AgentName("Sage")

    def test_clear_forced_next(self, scheduler: Scheduler):
        """Test clearing forced next agent."""
        scheduler.force_next_turn(AgentName("Sage"))
        scheduler.clear_forced_next()

        assert scheduler.get_forced_next() is None

    def test_skip_turns(self, scheduler: Scheduler):
        """Test setting skip count."""
        scheduler.skip_turns(AgentName("River"), 3)

        assert scheduler.get_skip_count(AgentName("River")) == 3

    def test_decrement_skip(self, scheduler: Scheduler):
        """Test decrementing skip count."""
        scheduler.skip_turns(AgentName("River"), 2)
        scheduler.decrement_skip(AgentName("River"))

        assert scheduler.get_skip_count(AgentName("River")) == 1

    def test_skip_count_removed_at_zero(self, scheduler: Scheduler):
        """Test skip count is removed when it reaches zero."""
        scheduler.skip_turns(AgentName("River"), 1)
        scheduler.decrement_skip(AgentName("River"))

        assert scheduler.get_skip_count(AgentName("River")) == 0

    def test_record_turn(self, scheduler: Scheduler):
        """Test recording turn increments count."""
        scheduler.record_turn(AgentName("Ember"))
        scheduler.record_turn(AgentName("Ember"))

        assert scheduler.get_turn_count(AgentName("Ember")) == 2

    def test_record_turn_clears_forced_next(self, scheduler: Scheduler):
        """Test recording turn clears forced next for that agent."""
        scheduler.force_next_turn(AgentName("Sage"))
        scheduler.record_turn(AgentName("Sage"))

        assert scheduler.get_forced_next() is None

    def test_record_turn_doesnt_clear_different_forced(self, scheduler: Scheduler):
        """Test recording turn doesn't clear forced next for different agent."""
        scheduler.force_next_turn(AgentName("Sage"))
        scheduler.record_turn(AgentName("Ember"))

        assert scheduler.get_forced_next() == AgentName("Sage")


class TestSchedulerConstants:
    """Tests for scheduler constants."""

    def test_conversation_pace_minutes(self):
        """Test conversation pace constant."""
        assert Scheduler.CONVERSATION_PACE_MINUTES == 5

    def test_solo_pace_minutes(self):
        """Test solo activity pace constant."""
        assert Scheduler.SOLO_PACE_MINUTES == 120

    def test_invite_response_minutes(self):
        """Test invite response window constant."""
        assert Scheduler.INVITE_RESPONSE_MINUTES == 5
