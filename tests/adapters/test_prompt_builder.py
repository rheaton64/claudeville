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
    UnseenConversationEnding,
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
        """Test user prompt includes available paths with 'set off toward' framing."""
        prompt = prompt_builder.build_user_prompt(basic_agent_context)

        assert "set off toward" in prompt
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

        assert "conversation is happening" in prompt.lower()
        assert "Sage" in prompt
        assert "join_conversation" in prompt


class TestBuildUserPromptNonParticipants:
    """Tests for non-participants note in conversation section."""

    def test_shows_non_participant_note_single(
        self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext
    ):
        """Test that single non-participant at location gets a note."""
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
            **{
                **basic_agent_context.__dict__,
                "conversation": conv,
                "others_present": ["Sage", "River"],  # River is not in conversation
            }
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        assert "River is nearby but not part of this conversation" in prompt
        assert "invite_to_conversation" in prompt

    def test_shows_non_participant_note_multiple(
        self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext
    ):
        """Test that multiple non-participants at location get a note."""
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
            **{
                **basic_agent_context.__dict__,
                "conversation": conv,
                "others_present": ["Sage", "River", "Luna"],  # River and Luna not in conversation
            }
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        assert "River and Luna are nearby but not part of this conversation" in prompt
        assert "invite_to_conversation" in prompt

    def test_no_note_when_all_present_are_participants(
        self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext
    ):
        """Test no note when everyone present is in the conversation."""
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
            **{
                **basic_agent_context.__dict__,
                "conversation": conv,
                "others_present": ["Sage"],  # Sage is in conversation
            }
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        assert "can't hear your words" not in prompt

    def test_no_note_when_alone_at_location(
        self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext
    ):
        """Test no note when alone at location."""
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
            **{
                **basic_agent_context.__dict__,
                "conversation": conv,
                "others_present": [],
            }
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        assert "can't hear your words" not in prompt

    def test_shows_note_when_not_in_conversation_single(
        self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext
    ):
        """Test note shown when not in conversation with single other present."""
        ctx = AgentContext(
            **{
                **basic_agent_context.__dict__,
                "conversation": None,
                "others_present": ["Sage"],
            }
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        assert "If you'd like to talk with Sage" in prompt
        assert "invite_to_conversation" in prompt

    def test_shows_note_when_not_in_conversation_multiple(
        self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext
    ):
        """Test note shown when not in conversation with multiple others present."""
        ctx = AgentContext(
            **{
                **basic_agent_context.__dict__,
                "conversation": None,
                "others_present": ["Sage", "River"],
            }
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        assert "If you'd like to talk with Sage and River" in prompt
        assert "invite_to_conversation" in prompt

    def test_no_note_when_alone_not_in_conversation(
        self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext
    ):
        """Test no note when alone and not in conversation."""
        ctx = AgentContext(
            **{
                **basic_agent_context.__dict__,
                "conversation": None,
                "others_present": [],
            }
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        assert "can't hear your words" not in prompt


class TestBuildUserPromptDeparture:
    """Tests for departure indicators in conversation section."""

    def test_shows_departure_indicator_after_message(
        self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext
    ):
        """Test that departure messages show indicator after the message."""
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
            {
                "speaker": "Sage",
                "narrative": "Farewell, I must go!",
                "is_departure": True,
            },
        ]
        ctx = AgentContext(
            **{
                **basic_agent_context.__dict__,
                "conversation": conv,
                "unseen_history": unseen,
            }
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        assert "Farewell, I must go!" in prompt
        assert "[Sage then left the conversation]" in prompt

    def test_no_departure_indicator_for_regular_message(
        self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext
    ):
        """Test that regular messages don't show departure indicator."""
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
            {
                "speaker": "Sage",
                "narrative": "Hello there!",
                "is_departure": False,
            },
        ]
        ctx = AgentContext(
            **{
                **basic_agent_context.__dict__,
                "conversation": conv,
                "unseen_history": unseen,
            }
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        assert "Hello there!" in prompt
        assert "then left the conversation" not in prompt

    def test_shows_just_left_in_header(
        self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext
    ):
        """Test that conversation header shows who just left."""
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
            {
                "speaker": "River",
                "narrative": "See you all later!",
                "is_departure": True,
            },
        ]
        ctx = AgentContext(
            **{
                **basic_agent_context.__dict__,
                "conversation": conv,
                "unseen_history": unseen,
            }
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        # Should show River just left in the header
        assert "River just left" in prompt

    def test_multiple_departures_in_header(
        self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext
    ):
        """Test that multiple departures are shown in header."""
        # Conversation still has one other participant remaining
        conv = Conversation(
            id=ConversationId("conv1"),
            location=LocationId("workshop"),
            participants=frozenset({AgentName("Ember"), AgentName("Luna")}),
            privacy="public",
            started_at_tick=1,
            created_by=AgentName("Ember"),
            history=(),
        )
        unseen = [
            {
                "speaker": "Sage",
                "narrative": "I must go!",
                "is_departure": True,
            },
            {
                "speaker": "River",
                "narrative": "Me too!",
                "is_departure": True,
            },
        ]
        ctx = AgentContext(
            **{
                **basic_agent_context.__dict__,
                "conversation": conv,
                "unseen_history": unseen,
            }
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        # Both departures should be mentioned in the header
        assert "Sage" in prompt
        assert "River" in prompt
        assert "just left" in prompt

    def test_mixed_messages_with_departure(
        self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext
    ):
        """Test a mix of regular messages and departures."""
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
            {
                "speaker": "River",
                "narrative": "What a nice day!",
                "is_departure": False,
            },
            {
                "speaker": "River",
                "narrative": "Well, I'm off now.",
                "is_departure": True,
            },
        ]
        ctx = AgentContext(
            **{
                **basic_agent_context.__dict__,
                "conversation": conv,
                "unseen_history": unseen,
            }
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        assert "What a nice day!" in prompt
        assert "Well, I'm off now." in prompt
        # Only the departure message should have the indicator
        assert "[River then left the conversation]" in prompt


class TestBuildUserPromptUnseenEndings:
    """Tests for unseen conversation endings section."""

    def test_shows_unseen_ending_with_final_message(
        self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext
    ):
        """Test that unseen endings with final message are shown."""
        ending = UnseenConversationEnding(
            conversation_id=ConversationId("conv1"),
            other_participant=AgentName("Sage"),
            final_message="Goodbye, my friend!",
            ended_at_tick=5,
        )
        ctx = AgentContext(
            **{**basic_agent_context.__dict__, "unseen_endings": [ending]}
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        assert "While you were away" in prompt
        assert "Sage" in prompt
        assert "Goodbye, my friend!" in prompt
        assert "parting words" in prompt

    def test_shows_unseen_ending_without_final_message(
        self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext
    ):
        """Test that unseen endings without final message are shown."""
        ending = UnseenConversationEnding(
            conversation_id=ConversationId("conv1"),
            other_participant=AgentName("River"),
            final_message=None,
            ended_at_tick=3,
        )
        ctx = AgentContext(
            **{**basic_agent_context.__dict__, "unseen_endings": [ending]}
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        assert "While you were away" in prompt
        assert "River" in prompt
        # No parting words since there's no final message
        assert "parting words" not in prompt

    def test_shows_multiple_unseen_endings(
        self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext
    ):
        """Test that multiple unseen endings are shown."""
        ending1 = UnseenConversationEnding(
            conversation_id=ConversationId("conv1"),
            other_participant=AgentName("Sage"),
            final_message="See you later!",
            ended_at_tick=5,
        )
        ending2 = UnseenConversationEnding(
            conversation_id=ConversationId("conv2"),
            other_participant=AgentName("River"),
            final_message="Take care!",
            ended_at_tick=6,
        )
        ctx = AgentContext(
            **{**basic_agent_context.__dict__, "unseen_endings": [ending1, ending2]}
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        assert "Sage" in prompt
        assert "River" in prompt
        assert "See you later!" in prompt
        assert "Take care!" in prompt

    def test_no_unseen_endings_section_when_empty(
        self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext
    ):
        """Test that no endings section appears when there are none."""
        ctx = AgentContext(
            **{**basic_agent_context.__dict__, "unseen_endings": []}
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        assert "While you were away" not in prompt


class TestBuildUserPromptArrival:
    """Tests for arrival acknowledgment in user prompt."""

    def test_shows_arrival_from_location(
        self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext
    ):
        """Test that arrival acknowledgment shows previous location."""
        ctx = AgentContext(
            **{**basic_agent_context.__dict__, "arrived_from": LocationId("town_square")}
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        assert "arrived here" in prompt.lower()
        assert "town square" in prompt  # Underscores replaced

    def test_no_arrival_when_not_moved(
        self, prompt_builder: PromptBuilder, basic_agent_context: AgentContext
    ):
        """Test that no arrival text appears when agent hasn't moved."""
        ctx = AgentContext(
            **{**basic_agent_context.__dict__, "arrived_from": None}
        )

        prompt = prompt_builder.build_user_prompt(ctx)

        assert "arrived here" not in prompt.lower()
