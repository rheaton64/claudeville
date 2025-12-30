"""Tests for engine.runtime.phases.schedule module."""

import pytest
from datetime import datetime

from engine.domain import (
    AgentName,
    LocationId,
    ConversationId,
    AgentSnapshot,
    Conversation,
)
from engine.services.scheduler import Scheduler, ScheduledEvent
from engine.runtime.context import TickContext
from engine.runtime.phases import SchedulePhase


class TestSchedulePhaseBasics:
    """Basic tests for SchedulePhase."""

    @pytest.mark.asyncio
    async def test_empty_events_no_agents(
        self,
        tick_context: TickContext,
        scheduler: Scheduler,
    ):
        """Test no agents scheduled when no events."""
        phase = SchedulePhase(scheduler)

        result = await phase.execute(tick_context)

        assert result.agents_to_act == frozenset()

    @pytest.mark.asyncio
    async def test_phase_name(self, scheduler: Scheduler):
        """Test phase has correct name."""
        phase = SchedulePhase(scheduler)

        assert phase.name == "schedule"


class TestAgentTurnScheduling:
    """Tests for agent turn scheduling."""

    @pytest.mark.asyncio
    async def test_agent_turn_event_schedules_agent(
        self,
        tick_context: TickContext,
        scheduler: Scheduler,
        agent_turn_event: ScheduledEvent,
    ):
        """Test agent turn event schedules the agent."""
        ctx = tick_context.model_copy(
            update={"scheduled_events": [agent_turn_event]}
        )

        phase = SchedulePhase(scheduler)
        result = await phase.execute(ctx)

        assert AgentName("Ember") in result.agents_to_act

    @pytest.mark.asyncio
    async def test_sleeping_agent_not_scheduled(
        self,
        tick_context: TickContext,
        scheduler: Scheduler,
        sleeping_agent: AgentSnapshot,
        base_datetime: datetime,
    ):
        """Test sleeping agent is not scheduled for turn."""
        event = ScheduledEvent(
            due_time=base_datetime,
            priority=10,
            event_type="agent_turn",
            target_id=str(sleeping_agent.name),
            location_id=sleeping_agent.location,
        )

        ctx = tick_context.model_copy(
            update={
                "scheduled_events": [event],
                "agents": {**tick_context.agents, sleeping_agent.name: sleeping_agent},
            }
        )

        phase = SchedulePhase(scheduler)
        result = await phase.execute(ctx)

        assert sleeping_agent.name not in result.agents_to_act

    @pytest.mark.asyncio
    async def test_nonexistent_agent_not_scheduled(
        self,
        tick_context: TickContext,
        scheduler: Scheduler,
        base_datetime: datetime,
    ):
        """Test nonexistent agent is not scheduled."""
        event = ScheduledEvent(
            due_time=base_datetime,
            priority=10,
            event_type="agent_turn",
            target_id="NonexistentAgent",
            location_id=LocationId("workshop"),
        )

        ctx = tick_context.model_copy(
            update={"scheduled_events": [event]}
        )

        phase = SchedulePhase(scheduler)
        result = await phase.execute(ctx)

        assert AgentName("NonexistentAgent") not in result.agents_to_act


class TestSkipCount:
    """Tests for skip count handling."""

    @pytest.mark.asyncio
    async def test_skip_count_skips_agent(
        self,
        tick_context: TickContext,
        scheduler: Scheduler,
        agent_turn_event: ScheduledEvent,
    ):
        """Test agent with skip count is skipped."""
        scheduler.skip_turns(AgentName("Ember"), 2)

        ctx = tick_context.model_copy(
            update={"scheduled_events": [agent_turn_event]}
        )

        phase = SchedulePhase(scheduler)
        result = await phase.execute(ctx)

        assert AgentName("Ember") not in result.agents_to_act
        # Skip count should be decremented
        assert scheduler.get_skip_count(AgentName("Ember")) == 1

    @pytest.mark.asyncio
    async def test_skip_count_zero_allows_turn(
        self,
        tick_context: TickContext,
        scheduler: Scheduler,
        agent_turn_event: ScheduledEvent,
    ):
        """Test agent with zero skip count is scheduled."""
        # No skip count set

        ctx = tick_context.model_copy(
            update={"scheduled_events": [agent_turn_event]}
        )

        phase = SchedulePhase(scheduler)
        result = await phase.execute(ctx)

        assert AgentName("Ember") in result.agents_to_act


class TestForcedNextTurn:
    """Tests for forced next turn (observer override)."""

    @pytest.mark.asyncio
    async def test_forced_next_schedules_agent(
        self,
        tick_context: TickContext,
        scheduler: Scheduler,
    ):
        """Test forced next turn schedules the agent."""
        scheduler.force_next_turn(AgentName("Ember"))

        phase = SchedulePhase(scheduler)
        result = await phase.execute(tick_context)

        assert AgentName("Ember") in result.agents_to_act

    @pytest.mark.asyncio
    async def test_forced_sleeping_agent_not_scheduled(
        self,
        tick_context: TickContext,
        scheduler: Scheduler,
        sleeping_agent: AgentSnapshot,
    ):
        """Test forced sleeping agent is still not scheduled."""
        ctx = tick_context.model_copy(
            update={
                "agents": {**tick_context.agents, sleeping_agent.name: sleeping_agent},
            }
        )

        scheduler.force_next_turn(sleeping_agent.name)

        phase = SchedulePhase(scheduler)
        result = await phase.execute(ctx)

        assert sleeping_agent.name not in result.agents_to_act


class TestConversationTurnScheduling:
    """Tests for conversation turn scheduling."""

    @pytest.mark.asyncio
    async def test_conversation_turn_schedules_speaker(
        self,
        tick_context: TickContext,
        scheduler: Scheduler,
        sample_conversation: Conversation,
        conversation_turn_event: ScheduledEvent,
    ):
        """Test conversation turn schedules a speaker."""
        ctx = tick_context.model_copy(
            update={
                "scheduled_events": [conversation_turn_event],
                "conversations": {sample_conversation.id: sample_conversation},
            }
        )

        phase = SchedulePhase(scheduler)
        result = await phase.execute(ctx)

        # Should schedule one of the conversation participants
        scheduled_participants = [
            a for a in result.agents_to_act
            if a in sample_conversation.participants
        ]
        assert len(scheduled_participants) == 1

    @pytest.mark.asyncio
    async def test_conversation_uses_next_speaker(
        self,
        tick_context: TickContext,
        scheduler: Scheduler,
        sample_conversation: Conversation,
        base_datetime: datetime,
    ):
        """Test conversation uses next_speaker if set."""
        # Conversation has next_speaker set to Sage
        assert sample_conversation.next_speaker == AgentName("Sage")

        event = ScheduledEvent(
            due_time=base_datetime,
            priority=5,
            event_type="conversation_turn",
            target_id=str(sample_conversation.id),
            location_id=sample_conversation.location,
        )

        ctx = tick_context.model_copy(
            update={
                "scheduled_events": [event],
                "conversations": {sample_conversation.id: sample_conversation},
            }
        )

        phase = SchedulePhase(scheduler)
        result = await phase.execute(ctx)

        assert AgentName("Sage") in result.agents_to_act

    @pytest.mark.asyncio
    async def test_conversation_nonexistent_not_scheduled(
        self,
        tick_context: TickContext,
        scheduler: Scheduler,
        conversation_turn_event: ScheduledEvent,
    ):
        """Test nonexistent conversation doesn't schedule anyone."""
        ctx = tick_context.model_copy(
            update={
                "scheduled_events": [conversation_turn_event],
                # No conversations
            }
        )

        phase = SchedulePhase(scheduler)
        result = await phase.execute(ctx)

        assert result.agents_to_act == frozenset()


class TestInviteResponseScheduling:
    """Tests for invite response scheduling."""

    @pytest.mark.asyncio
    async def test_invite_response_schedules_agent(
        self,
        tick_context: TickContext,
        scheduler: Scheduler,
        invite_response_event: ScheduledEvent,
    ):
        """Test invite response event schedules agent."""
        ctx = tick_context.model_copy(
            update={"scheduled_events": [invite_response_event]}
        )

        phase = SchedulePhase(scheduler)
        result = await phase.execute(ctx)

        assert AgentName("Sage") in result.agents_to_act

    @pytest.mark.asyncio
    async def test_invite_response_ignores_skip_count(
        self,
        tick_context: TickContext,
        scheduler: Scheduler,
        invite_response_event: ScheduledEvent,
    ):
        """Test invite response ignores skip count."""
        scheduler.skip_turns(AgentName("Sage"), 5)

        ctx = tick_context.model_copy(
            update={"scheduled_events": [invite_response_event]}
        )

        phase = SchedulePhase(scheduler)
        result = await phase.execute(ctx)

        # Should still be scheduled despite skip count
        assert AgentName("Sage") in result.agents_to_act


class TestMultipleEvents:
    """Tests for multiple scheduled events."""

    @pytest.mark.asyncio
    async def test_multiple_agent_turns_scheduled(
        self,
        tick_context: TickContext,
        scheduler: Scheduler,
        base_datetime: datetime,
    ):
        """Test multiple agent turns can be scheduled."""
        events = [
            ScheduledEvent(
                due_time=base_datetime,
                priority=10,
                event_type="agent_turn",
                target_id="Ember",
                location_id=LocationId("workshop"),
            ),
            ScheduledEvent(
                due_time=base_datetime,
                priority=10,
                event_type="agent_turn",
                target_id="Sage",
                location_id=LocationId("library"),
            ),
        ]

        ctx = tick_context.model_copy(
            update={"scheduled_events": events}
        )

        phase = SchedulePhase(scheduler)
        result = await phase.execute(ctx)

        assert AgentName("Ember") in result.agents_to_act
        assert AgentName("Sage") in result.agents_to_act
