"""Tests for engine.adapters.prompt_builder module."""

import pytest
from datetime import datetime

from engine.adapters.prompt_builder import PromptBuilder
from engine.runtime.phases.agent_turn import AgentContext
from engine.domain import (
    AgentName,
    AgentSnapshot,
    AgentLLMModel,
    Conversation,
    ConversationId,
    ConversationTurn,
    Invitation,
    LocationId,
)


@pytest.fixture
def prompt_builder() -> PromptBuilder:
    """Create a prompt builder."""
    return PromptBuilder()


@pytest.fixture
def basic_agent_context(sample_agent: AgentSnapshot) -> AgentContext:
    """Create a basic agent context without conversation."""
    return AgentContext(
        agent=sample_agent,
        location_description="A cozy workshop with tools and wood shavings.",
        others_present=[],
        available_paths=["town_square", "library"],
        time_description="It's a bright morning",
        weather="Clear skies and warm",
        recent_events=[],
        shared_files=[],
        unseen_dreams=[],
        conversation=None,
        unseen_history=None,
        is_opener=False,
        pending_invite=None,
        joinable_conversations=[],
    )


class TestBuildSystemPrompt:
    """Tests for build_system_prompt method."""

    def test_includes_agent_name(self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext):
        """Test system prompt includes agent name."""
        prompt = prompt_builder.build_system_prompt(basic_agent_context)

        assert basic_agent_context.agent.name in prompt

    def test_includes_personality(self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext):
        """Test system prompt includes personality."""
        prompt = prompt_builder.build_system_prompt(basic_agent_context)

        assert basic_agent_context.agent.personality in prompt

    def test_includes_job(self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext):
        """Test system prompt includes job."""
        prompt = prompt_builder.build_system_prompt(basic_agent_context)

        assert basic_agent_context.agent.job in prompt

    def test_includes_interests(self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext):
        """Test system prompt includes interests."""
        prompt = prompt_builder.build_system_prompt(basic_agent_context)

        for interest in basic_agent_context.agent.interests:
            assert interest in prompt

    def test_includes_note_to_self(self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext):
        """Test system prompt includes note to self."""
        prompt = prompt_builder.build_system_prompt(basic_agent_context)

        assert basic_agent_context.agent.note_to_self in prompt

    def test_mentions_observer(self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext):
        """Test system prompt mentions the Observer."""
        prompt = prompt_builder.build_system_prompt(basic_agent_context)

        assert "Observer" in prompt
        assert "Ryan" in prompt

    def test_mentions_autonomy(self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext):
        """Test system prompt emphasizes autonomy."""
        prompt = prompt_builder.build_system_prompt(basic_agent_context)

        assert "autonomy" in prompt.lower()

    def test_mentions_conversation_tools(self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext):
        """Test system prompt mentions conversation tools."""
        prompt = prompt_builder.build_system_prompt(basic_agent_context)

        assert "invite_to_conversation" in prompt
        assert "accept_invite" in prompt
        assert "decline_invite" in prompt

    def test_mentions_file_access(self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext):
        """Test system prompt mentions file access."""
        prompt = prompt_builder.build_system_prompt(basic_agent_context)

        assert "journal" in prompt
        assert "inbox" in prompt
        assert "workspace" in prompt


class TestBuildUserPrompt:
    """Tests for build_user_prompt method."""

    def test_includes_location_description(self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext):
        """Test user prompt includes location."""
        prompt = prompt_builder.build_user_prompt(basic_agent_context)

        assert basic_agent_context.location_description in prompt

    def test_includes_time_description(self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext):
        """Test user prompt includes time."""
        prompt = prompt_builder.build_user_prompt(basic_agent_context)

        assert basic_agent_context.time_description in prompt

    def test_includes_weather(self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext):
        """Test user prompt includes weather."""
        prompt = prompt_builder.build_user_prompt(basic_agent_context)

        assert basic_agent_context.weather in prompt

    def test_includes_mood(self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext):
        """Test user prompt includes mood."""
        prompt = prompt_builder.build_user_prompt(basic_agent_context)

        assert basic_agent_context.agent.mood in prompt

    def test_indicates_alone(self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext):
        """Test user prompt indicates when alone."""
        prompt = prompt_builder.build_user_prompt(basic_agent_context)

        assert "alone" in prompt.lower()

    def test_lists_others_present_single(self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext):
        """Test user prompt lists single other present."""
        ctx = AgentContext(
            **{**basic_agent_context.__dict__, "others_present": ["Sage"]}
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        assert "Sage is here" in prompt

    def test_lists_others_present_multiple(self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext):
        """Test user prompt lists multiple others present."""
        ctx = AgentContext(
            **{**basic_agent_context.__dict__, "others_present": ["Sage", "River"]}
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        assert "Sage" in prompt
        assert "River" in prompt
        assert "are here" in prompt

    def test_includes_available_paths(self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext):
        """Test user prompt includes available paths."""
        prompt = prompt_builder.build_user_prompt(basic_agent_context)

        assert "paths lead to" in prompt
        assert "town square" in prompt  # Underscores replaced

    def test_ends_with_this_moment_is_yours(self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext):
        """Test user prompt ends with autonomy phrase."""
        prompt = prompt_builder.build_user_prompt(basic_agent_context)

        assert prompt.strip().endswith("This moment is yours.")

    def test_includes_recent_events(self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext):
        """Test user prompt includes recent events."""
        ctx = AgentContext(
            **{**basic_agent_context.__dict__, "recent_events": ["You saw a bird.", "It was blue."]}
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        assert "You saw a bird" in prompt
        assert "It was blue" in prompt
        assert "memories" in prompt.lower()

    def test_includes_goals(self, prompt_builder: PromptBuilder, sample_agent: AgentSnapshot):
        """Test user prompt includes goals."""
        agent_with_goals = AgentSnapshot(
            **{**sample_agent.model_dump(), "goals": ("Finish the chair", "Read more")}
        )
        ctx = AgentContext(
            agent=agent_with_goals,
            location_description="Workshop",
            others_present=[],
            available_paths=[],
            time_description="Morning",
            weather="Clear",
            recent_events=[],
            shared_files=[],
            unseen_dreams=[],
            conversation=None,
            unseen_history=None,
            is_opener=False,
            pending_invite=None,
            joinable_conversations=[],
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        assert "Finish the chair" in prompt
        assert "Read more" in prompt

    def test_includes_dreams(self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext):
        """Test user prompt includes unseen dreams."""
        ctx = AgentContext(
            **{**basic_agent_context.__dict__, "unseen_dreams": ["You dreamed of stars."]}
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        assert "dream" in prompt.lower()
        assert "stars" in prompt


class TestBuildUserPromptEnergy:
    """Tests for energy descriptions in user prompt."""

    def test_high_energy(self, prompt_builder: PromptBuilder, sample_agent: AgentSnapshot):
        """Test high energy description."""
        agent = AgentSnapshot(**{**sample_agent.model_dump(), "energy": 90})
        ctx = AgentContext(
            agent=agent,
            location_description="Place",
            others_present=[],
            available_paths=[],
            time_description="Time",
            weather="Weather",
            recent_events=[],
            shared_files=[],
            unseen_dreams=[],
            conversation=None,
            unseen_history=None,
            is_opener=False,
            pending_invite=None,
            joinable_conversations=[],
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        assert "energized" in prompt.lower() or "well-rested" in prompt.lower()

    def test_low_energy(self, prompt_builder: PromptBuilder, sample_agent: AgentSnapshot):
        """Test low energy description."""
        agent = AgentSnapshot(**{**sample_agent.model_dump(), "energy": 20})
        ctx = AgentContext(
            agent=agent,
            location_description="Place",
            others_present=[],
            available_paths=[],
            time_description="Time",
            weather="Weather",
            recent_events=[],
            shared_files=[],
            unseen_dreams=[],
            conversation=None,
            unseen_history=None,
            is_opener=False,
            pending_invite=None,
            joinable_conversations=[],
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        assert "weariness" in prompt.lower() or "tired" in prompt.lower()


class TestBuildUserPromptConversation:
    """Tests for conversation section in user prompt."""

    def test_includes_conversation_info(self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext):
        """Test conversation context is included."""
        conv = Conversation(
            id=ConversationId("conv1"),
            location=LocationId("workshop"),
            participants=frozenset({AgentName("Ember"), AgentName("Sage")}),
            privacy="public",
            started_at_tick=1,
            created_by=AgentName("Ember"),
            history=(),
        )
        ctx = AgentContext(
            **{**basic_agent_context.__dict__, "conversation": conv}
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        assert "conversation" in prompt.lower()
        assert "Sage" in prompt

    def test_includes_unseen_history(self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext):
        """Test unseen conversation history is included."""
        conv = Conversation(
            id=ConversationId("conv1"),
            location=LocationId("workshop"),
            participants=frozenset({AgentName("Ember"), AgentName("Sage")}),
            privacy="public",
            started_at_tick=1,
            created_by=AgentName("Ember"),
            history=(),
        )
        unseen = [
            {"speaker": "Sage", "narrative": "Hello, friend!"},
        ]
        ctx = AgentContext(
            **{
                **basic_agent_context.__dict__,
                "conversation": conv,
                "unseen_history": unseen,
            }
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        assert "Hello, friend!" in prompt

    def test_conversation_ends_with_this_moment(self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext):
        """Test conversation context also ends with autonomy phrase."""
        conv = Conversation(
            id=ConversationId("conv1"),
            location=LocationId("workshop"),
            participants=frozenset({AgentName("Ember"), AgentName("Sage")}),
            privacy="public",
            started_at_tick=1,
            created_by=AgentName("Ember"),
            history=(),
        )
        ctx = AgentContext(
            **{**basic_agent_context.__dict__, "conversation": conv}
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        assert prompt.strip().endswith("This moment is yours.")


class TestBuildUserPromptInvite:
    """Tests for invite section in user prompt."""

    def test_includes_pending_invite(self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext, sample_invitation: Invitation):
        """Test pending invite is included."""
        ctx = AgentContext(
            **{**basic_agent_context.__dict__, "pending_invite": sample_invitation}
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        assert sample_invitation.inviter in prompt
        assert "invite" in prompt.lower()

    def test_mentions_accept_decline(self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext, sample_invitation: Invitation):
        """Test accept/decline options mentioned."""
        ctx = AgentContext(
            **{**basic_agent_context.__dict__, "pending_invite": sample_invitation}
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        assert "accept_invite" in prompt
        assert "decline_invite" in prompt


class TestBuildUserPromptJoinable:
    """Tests for joinable conversations section."""

    def test_includes_joinable_conversations(self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext):
        """Test joinable conversations are included."""
        conv = Conversation(
            id=ConversationId("conv1"),
            location=LocationId("workshop"),
            participants=frozenset({AgentName("Sage"), AgentName("River")}),
            privacy="public",
            started_at_tick=1,
            created_by=AgentName("Sage"),
            history=(),
        )
        ctx = AgentContext(
            **{**basic_agent_context.__dict__, "joinable_conversations": [conv]}
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        assert "public conversations" in prompt.lower()
        assert "Sage" in prompt
        assert "join_conversation" in prompt
