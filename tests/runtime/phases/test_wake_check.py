"""Tests for engine.runtime.phases.wake_check module."""

import pytest
from datetime import datetime

from engine.domain import (
    AgentName,
    LocationId,
    AgentSnapshot,
    AgentWakeEffect,
    TimePeriod,
    TimeSnapshot,
)
from engine.runtime.context import TickContext
from engine.runtime.phases import WakeCheckPhase


class TestWakeCheckPhaseBasics:
    """Basic tests for WakeCheckPhase."""

    @pytest.mark.asyncio
    async def test_awake_agents_not_affected(self, tick_context: TickContext):
        """Test that awake agents are not affected."""
        phase = WakeCheckPhase()

        result = await phase.execute(tick_context)

        # No wake effects for awake agents
        wake_effects = [e for e in result.effects if isinstance(e, AgentWakeEffect)]
        assert len(wake_effects) == 0

    @pytest.mark.asyncio
    async def test_phase_name(self):
        """Test phase has correct name."""
        phase = WakeCheckPhase()

        assert phase.name == "wake_check"


class TestTimePeriodWake:
    """Tests for time period based waking."""

    @pytest.mark.asyncio
    async def test_morning_wakes_night_sleeper(
        self,
        morning_time: TimeSnapshot,
        world_snapshot,
        sleeping_agent: AgentSnapshot,
    ):
        """Test sleeping agent wakes when morning arrives after night sleep."""
        # Agent slept during evening, now it's morning
        assert sleeping_agent.sleep_started_time_period == TimePeriod.EVENING
        assert morning_time.period == TimePeriod.MORNING

        ctx = TickContext(
            tick=1,
            timestamp=morning_time.world_time,
            time_snapshot=morning_time,
            world=world_snapshot,
            agents={sleeping_agent.name: sleeping_agent},
            conversations={},
            pending_invites={},
        )

        phase = WakeCheckPhase()
        result = await phase.execute(ctx)

        wake_effects = [e for e in result.effects if isinstance(e, AgentWakeEffect)]
        assert len(wake_effects) == 1
        assert wake_effects[0].agent == sleeping_agent.name
        assert wake_effects[0].reason == "time_period_changed"

    @pytest.mark.asyncio
    async def test_same_period_doesnt_wake(
        self,
        evening_time: TimeSnapshot,
        world_snapshot,
        sleeping_agent: AgentSnapshot,
    ):
        """Test sleeping agent stays asleep in same time period."""
        # Agent slept during evening, still evening
        assert sleeping_agent.sleep_started_time_period == TimePeriod.EVENING
        assert evening_time.period == TimePeriod.EVENING

        ctx = TickContext(
            tick=1,
            timestamp=evening_time.world_time,
            time_snapshot=evening_time,
            world=world_snapshot,
            agents={sleeping_agent.name: sleeping_agent},
            conversations={},
            pending_invites={},
        )

        phase = WakeCheckPhase()
        result = await phase.execute(ctx)

        wake_effects = [e for e in result.effects if isinstance(e, AgentWakeEffect)]
        assert len(wake_effects) == 0

    @pytest.mark.asyncio
    async def test_night_to_morning_wakes(
        self,
        morning_time: TimeSnapshot,
        world_snapshot,
        sample_llm_model,
    ):
        """Test agent who slept at night wakes in morning."""
        night_sleeper = AgentSnapshot(
            name=AgentName("NightOwl"),
            model=sample_llm_model,
            personality="Test",
            job="Test",
            interests=(),
            note_to_self="",
            location=LocationId("workshop"),
            mood="tired",
            energy=20,
            goals=(),
            relationships={},
            is_sleeping=True,
            sleep_started_tick=5,
            sleep_started_time_period=TimePeriod.NIGHT,
        )

        ctx = TickContext(
            tick=10,
            timestamp=morning_time.world_time,
            time_snapshot=morning_time,
            world=world_snapshot,
            agents={night_sleeper.name: night_sleeper},
            conversations={},
            pending_invites={},
        )

        phase = WakeCheckPhase()
        result = await phase.execute(ctx)

        wake_effects = [e for e in result.effects if isinstance(e, AgentWakeEffect)]
        assert len(wake_effects) == 1


class TestVisitorWake:
    """Tests for visitor-based waking."""

    @pytest.mark.asyncio
    async def test_visitor_arrival_wakes_agent(
        self,
        evening_time: TimeSnapshot,
        world_snapshot,
        sleeping_agent: AgentSnapshot,
        sample_agent: AgentSnapshot,
    ):
        """Test sleeping agent wakes when visitor arrives."""
        # Use evening time so the sleeping agent (who slept in evening) won't wake from time change
        # Put visitor at same location as sleeping agent
        visitor = AgentSnapshot(**{
            **sample_agent.model_dump(),
            "location": sleeping_agent.location,
        })

        ctx = TickContext(
            tick=1,
            timestamp=evening_time.world_time,
            time_snapshot=evening_time,
            world=world_snapshot,
            agents={
                sleeping_agent.name: sleeping_agent,
                visitor.name: visitor,
            },
            conversations={},
            pending_invites={},
        )

        phase = WakeCheckPhase(recent_arrivals={visitor.name})
        result = await phase.execute(ctx)

        wake_effects = [e for e in result.effects if isinstance(e, AgentWakeEffect)]
        assert len(wake_effects) == 1
        assert wake_effects[0].agent == sleeping_agent.name
        assert "visitor_arrived" in wake_effects[0].reason
        assert str(visitor.name) in wake_effects[0].reason

    @pytest.mark.asyncio
    async def test_self_arrival_doesnt_wake(
        self,
        evening_time: TimeSnapshot,
        world_snapshot,
        sleeping_agent: AgentSnapshot,
    ):
        """Test agent can't wake themselves by moving."""
        # Use evening time so the sleeping agent won't wake from time change
        ctx = TickContext(
            tick=1,
            timestamp=evening_time.world_time,
            time_snapshot=evening_time,
            world=world_snapshot,
            agents={sleeping_agent.name: sleeping_agent},
            conversations={},
            pending_invites={},
        )

        # Agent somehow moved while sleeping
        phase = WakeCheckPhase(recent_arrivals={sleeping_agent.name})
        result = await phase.execute(ctx)

        wake_effects = [e for e in result.effects if isinstance(e, AgentWakeEffect)]
        assert len(wake_effects) == 0

    @pytest.mark.asyncio
    async def test_visitor_different_location_doesnt_wake(
        self,
        evening_time: TimeSnapshot,
        world_snapshot,
        sleeping_agent: AgentSnapshot,
        sample_agent: AgentSnapshot,
    ):
        """Test visitor at different location doesn't wake agent."""
        # Use evening time so the sleeping agent won't wake from time change
        # Visitor at workshop, sleeper at garden
        assert sample_agent.location != sleeping_agent.location

        ctx = TickContext(
            tick=1,
            timestamp=evening_time.world_time,
            time_snapshot=evening_time,
            world=world_snapshot,
            agents={
                sleeping_agent.name: sleeping_agent,
                sample_agent.name: sample_agent,
            },
            conversations={},
            pending_invites={},
        )

        phase = WakeCheckPhase(recent_arrivals={sample_agent.name})
        result = await phase.execute(ctx)

        wake_effects = [e for e in result.effects if isinstance(e, AgentWakeEffect)]
        assert len(wake_effects) == 0

    @pytest.mark.asyncio
    async def test_set_recent_arrivals(self):
        """Test set_recent_arrivals updates the arrivals set."""
        phase = WakeCheckPhase()

        phase.set_recent_arrivals({AgentName("Ember"), AgentName("Sage")})

        assert AgentName("Ember") in phase._recent_arrivals
        assert AgentName("Sage") in phase._recent_arrivals


class TestMultipleAgents:
    """Tests for multiple sleeping agents."""

    @pytest.mark.asyncio
    async def test_multiple_agents_can_wake(
        self,
        morning_time: TimeSnapshot,
        world_snapshot,
        sample_llm_model,
    ):
        """Test multiple agents can wake simultaneously."""
        sleeper1 = AgentSnapshot(
            name=AgentName("Sleeper1"),
            model=sample_llm_model,
            personality="Test",
            job="Test",
            interests=(),
            note_to_self="",
            location=LocationId("workshop"),
            mood="tired",
            energy=20,
            goals=(),
            relationships={},
            is_sleeping=True,
            sleep_started_tick=5,
            sleep_started_time_period=TimePeriod.EVENING,
        )

        sleeper2 = AgentSnapshot(
            name=AgentName("Sleeper2"),
            model=sample_llm_model,
            personality="Test",
            job="Test",
            interests=(),
            note_to_self="",
            location=LocationId("library"),
            mood="tired",
            energy=30,
            goals=(),
            relationships={},
            is_sleeping=True,
            sleep_started_tick=5,
            sleep_started_time_period=TimePeriod.EVENING,
        )

        ctx = TickContext(
            tick=10,
            timestamp=morning_time.world_time,
            time_snapshot=morning_time,
            world=world_snapshot,
            agents={
                sleeper1.name: sleeper1,
                sleeper2.name: sleeper2,
            },
            conversations={},
            pending_invites={},
        )

        phase = WakeCheckPhase()
        result = await phase.execute(ctx)

        wake_effects = [e for e in result.effects if isinstance(e, AgentWakeEffect)]
        assert len(wake_effects) == 2
        names = {e.agent for e in wake_effects}
        assert sleeper1.name in names
        assert sleeper2.name in names
