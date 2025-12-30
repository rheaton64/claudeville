"""Tests for engine.runtime.context module."""

import pytest
from datetime import datetime

from engine.domain import (
    AgentName,
    LocationId,
    ConversationId,
    AgentSnapshot,
    Conversation,
    Invitation,
    TimePeriod,
    MoveAgentEffect,
    UpdateMoodEffect,
    AgentMovedEvent,
)
from engine.runtime.context import TickContext, TickResult
from engine.runtime.interpreter import AgentTurnResult


class TestTickContextCreation:
    """Tests for TickContext creation."""

    def test_creation_minimal(
        self,
        time_snapshot,
        world_snapshot,
        sample_agent: AgentSnapshot,
    ):
        """Test creating context with minimal fields."""
        ctx = TickContext(
            tick=1,
            timestamp=datetime(2024, 1, 1, 10, 0),
            time_snapshot=time_snapshot,
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={},
            pending_invites={},
        )

        assert ctx.tick == 1
        assert ctx.effects == ()
        assert ctx.events == ()
        assert ctx.turn_results == {}
        assert ctx.agents_to_act == frozenset()
        assert ctx.agents_acted == frozenset()

    def test_creation_full(
        self,
        time_snapshot,
        world_snapshot,
        sample_agent: AgentSnapshot,
        sample_conversation: Conversation,
        sample_invitation: Invitation,
    ):
        """Test creating context with all fields."""
        ctx = TickContext(
            tick=5,
            timestamp=datetime(2024, 1, 1, 10, 0),
            time_snapshot=time_snapshot,
            world=world_snapshot,
            agents={sample_agent.name: sample_agent},
            conversations={sample_conversation.id: sample_conversation},
            pending_invites={sample_invitation.invitee: sample_invitation},
            scheduled_events=[],
        )

        assert ctx.tick == 5
        assert sample_agent.name in ctx.agents
        assert sample_conversation.id in ctx.conversations
        assert sample_invitation.invitee in ctx.pending_invites


class TestTickContextEffectsAndEvents:
    """Tests for effect and event accumulation."""

    def test_with_effect(self, tick_context: TickContext):
        """Test adding a single effect."""
        effect = MoveAgentEffect(
            agent=AgentName("Ember"),
            from_location=LocationId("workshop"),
            to_location=LocationId("garden"),
        )

        new_ctx = tick_context.with_effect(effect)

        assert len(new_ctx.effects) == 1
        assert new_ctx.effects[0] == effect
        # Original unchanged
        assert len(tick_context.effects) == 0

    def test_with_effects_multiple(self, tick_context: TickContext):
        """Test adding multiple effects."""
        effects = [
            MoveAgentEffect(
                agent=AgentName("Ember"),
                from_location=LocationId("workshop"),
                to_location=LocationId("garden"),
            ),
            UpdateMoodEffect(agent=AgentName("Ember"), mood="happy"),
        ]

        new_ctx = tick_context.with_effects(effects)

        assert len(new_ctx.effects) == 2

    def test_with_effect_accumulates(self, tick_context: TickContext):
        """Test that effects accumulate across calls."""
        ctx1 = tick_context.with_effect(
            MoveAgentEffect(
                agent=AgentName("Ember"),
                from_location=LocationId("workshop"),
                to_location=LocationId("garden"),
            )
        )
        ctx2 = ctx1.with_effect(
            UpdateMoodEffect(agent=AgentName("Ember"), mood="happy")
        )

        assert len(ctx2.effects) == 2

    def test_with_event(self, tick_context: TickContext):
        """Test adding a single event."""
        event = AgentMovedEvent(
            tick=1,
            timestamp=tick_context.timestamp,
            agent=AgentName("Ember"),
            from_location=LocationId("workshop"),
            to_location=LocationId("garden"),
        )

        new_ctx = tick_context.with_event(event)

        assert len(new_ctx.events) == 1
        assert new_ctx.events[0] == event

    def test_with_events_multiple(self, tick_context: TickContext):
        """Test adding multiple events."""
        events = [
            AgentMovedEvent(
                tick=1,
                timestamp=tick_context.timestamp,
                agent=AgentName("Ember"),
                from_location=LocationId("workshop"),
                to_location=LocationId("garden"),
            ),
            AgentMovedEvent(
                tick=1,
                timestamp=tick_context.timestamp,
                agent=AgentName("Sage"),
                from_location=LocationId("library"),
                to_location=LocationId("workshop"),
            ),
        ]

        new_ctx = tick_context.with_events(events)

        assert len(new_ctx.events) == 2


class TestTickContextTurnResults:
    """Tests for turn result tracking."""

    def test_with_turn_result(self, tick_context: TickContext):
        """Test adding a turn result."""
        result = AgentTurnResult(narrative="I walked to the garden.")

        new_ctx = tick_context.with_turn_result(AgentName("Ember"), result)

        assert AgentName("Ember") in new_ctx.turn_results
        assert new_ctx.turn_results[AgentName("Ember")] == result

    def test_with_turn_result_multiple_agents(self, tick_context: TickContext):
        """Test adding turn results for multiple agents."""
        result1 = AgentTurnResult(narrative="I read a book.")
        result2 = AgentTurnResult(narrative="I tended the garden.")

        ctx1 = tick_context.with_turn_result(AgentName("Ember"), result1)
        ctx2 = ctx1.with_turn_result(AgentName("Sage"), result2)

        assert len(ctx2.turn_results) == 2


class TestTickContextAgentTracking:
    """Tests for agent action tracking."""

    def test_with_agents_to_act(self, tick_context: TickContext):
        """Test setting agents to act."""
        agents = frozenset([AgentName("Ember"), AgentName("Sage")])

        new_ctx = tick_context.with_agents_to_act(agents)

        assert new_ctx.agents_to_act == agents
        # Original unchanged
        assert tick_context.agents_to_act == frozenset()

    def test_with_agent_acted(self, tick_context: TickContext):
        """Test marking an agent as acted."""
        ctx = tick_context.with_agents_to_act(
            frozenset([AgentName("Ember"), AgentName("Sage")])
        )

        new_ctx = ctx.with_agent_acted(AgentName("Ember"))

        assert AgentName("Ember") in new_ctx.agents_acted
        assert AgentName("Sage") not in new_ctx.agents_acted

    def test_with_agent_acted_accumulates(self, tick_context: TickContext):
        """Test that acted agents accumulate."""
        ctx1 = tick_context.with_agent_acted(AgentName("Ember"))
        ctx2 = ctx1.with_agent_acted(AgentName("Sage"))

        assert len(ctx2.agents_acted) == 2


class TestTickContextStateUpdates:
    """Tests for agent and conversation state updates."""

    def test_with_updated_agent(
        self,
        tick_context: TickContext,
        sample_agent: AgentSnapshot,
    ):
        """Test updating an agent snapshot."""
        updated_agent = AgentSnapshot(
            **{**sample_agent.model_dump(), "mood": "excited"}
        )

        new_ctx = tick_context.with_updated_agent(updated_agent)

        assert new_ctx.agents[sample_agent.name].mood == "excited"
        # Original unchanged
        assert tick_context.agents[sample_agent.name].mood == "curious"

    def test_with_updated_conversation(
        self,
        tick_context: TickContext,
        sample_conversation: Conversation,
    ):
        """Test updating a conversation."""
        # Add conversation to context first
        ctx = tick_context.model_copy(
            update={"conversations": {sample_conversation.id: sample_conversation}}
        )

        updated_conv = Conversation(
            **{**sample_conversation.model_dump(), "next_speaker": AgentName("Ember")}
        )

        new_ctx = ctx.with_updated_conversation(updated_conv)

        assert new_ctx.conversations[sample_conversation.id].next_speaker == AgentName("Ember")

    def test_with_removed_conversation(
        self,
        tick_context: TickContext,
        sample_conversation: Conversation,
    ):
        """Test removing a conversation."""
        ctx = tick_context.model_copy(
            update={"conversations": {sample_conversation.id: sample_conversation}}
        )

        new_ctx = ctx.with_removed_conversation(sample_conversation.id)

        assert sample_conversation.id not in new_ctx.conversations

    def test_with_added_invite(
        self,
        tick_context: TickContext,
        sample_invitation: Invitation,
    ):
        """Test adding an invite."""
        new_ctx = tick_context.with_added_invite(sample_invitation)

        assert sample_invitation.invitee in new_ctx.pending_invites
        assert new_ctx.pending_invites[sample_invitation.invitee] == sample_invitation

    def test_with_removed_invite(
        self,
        tick_context: TickContext,
        sample_invitation: Invitation,
    ):
        """Test removing an invite."""
        ctx = tick_context.model_copy(
            update={"pending_invites": {sample_invitation.invitee: sample_invitation}}
        )

        new_ctx = ctx.with_removed_invite(sample_invitation.invitee)

        assert sample_invitation.invitee not in new_ctx.pending_invites


class TestTickContextQueries:
    """Tests for query helpers."""

    def test_get_agent(
        self,
        tick_context: TickContext,
        sample_agent: AgentSnapshot,
    ):
        """Test getting an agent by name."""
        agent = tick_context.get_agent(sample_agent.name)

        assert agent == sample_agent

    def test_get_agent_nonexistent(self, tick_context: TickContext):
        """Test getting nonexistent agent returns None."""
        agent = tick_context.get_agent(AgentName("Nobody"))

        assert agent is None

    def test_get_agents_at_location(
        self,
        time_snapshot,
        world_snapshot,
        sample_agent: AgentSnapshot,
        second_agent: AgentSnapshot,
    ):
        """Test getting agents at a location."""
        # sample_agent is at workshop, second_agent is at library
        ctx = TickContext(
            tick=1,
            timestamp=datetime(2024, 1, 1, 10, 0),
            time_snapshot=time_snapshot,
            world=world_snapshot,
            agents={
                sample_agent.name: sample_agent,
                second_agent.name: second_agent,
            },
            conversations={},
            pending_invites={},
        )

        agents = ctx.get_agents_at_location(LocationId("workshop"))

        assert len(agents) == 1
        assert agents[0].name == sample_agent.name

    def test_get_conversation(
        self,
        tick_context: TickContext,
        sample_conversation: Conversation,
    ):
        """Test getting a conversation by ID."""
        ctx = tick_context.model_copy(
            update={"conversations": {sample_conversation.id: sample_conversation}}
        )

        conv = ctx.get_conversation(sample_conversation.id)

        assert conv == sample_conversation

    def test_get_conversations_for_agent(
        self,
        tick_context: TickContext,
        sample_conversation: Conversation,
    ):
        """Test getting conversations for an agent."""
        ctx = tick_context.model_copy(
            update={"conversations": {sample_conversation.id: sample_conversation}}
        )

        convs = ctx.get_conversations_for_agent(AgentName("Ember"))

        assert len(convs) == 1
        assert convs[0].id == sample_conversation.id

    def test_get_public_conversations_at_location(
        self,
        tick_context: TickContext,
        public_conversation: Conversation,
    ):
        """Test getting public conversations at a location."""
        ctx = tick_context.model_copy(
            update={"conversations": {public_conversation.id: public_conversation}}
        )

        convs = ctx.get_public_conversations_at_location(public_conversation.location)

        assert len(convs) == 1


class TestTickResult:
    """Tests for TickResult."""

    def test_from_context(self, tick_context: TickContext):
        """Test creating TickResult from context."""
        effect = MoveAgentEffect(
            agent=AgentName("Ember"),
            from_location=LocationId("workshop"),
            to_location=LocationId("garden"),
        )
        event = AgentMovedEvent(
            tick=1,
            timestamp=tick_context.timestamp,
            agent=AgentName("Ember"),
            from_location=LocationId("workshop"),
            to_location=LocationId("garden"),
        )
        turn_result = AgentTurnResult(narrative="I walked away.")

        ctx = (
            tick_context
            .with_effect(effect)
            .with_event(event)
            .with_turn_result(AgentName("Ember"), turn_result)
            .with_agent_acted(AgentName("Ember"))
        )

        result = TickResult.from_context(ctx)

        assert result.tick == ctx.tick
        assert result.timestamp == ctx.timestamp
        assert len(result.effects) == 1
        assert len(result.events) == 1
        assert AgentName("Ember") in result.turn_results
        assert AgentName("Ember") in result.agents_acted

    def test_from_context_empty(self, tick_context: TickContext):
        """Test creating TickResult from empty context."""
        result = TickResult.from_context(tick_context)

        assert result.effects == ()
        assert result.events == ()
        assert result.turn_results == {}
        assert result.agents_acted == frozenset()
