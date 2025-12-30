"""Tests for engine.observer.api module."""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

from engine.domain import (
    AgentName,
    AgentSnapshot,
    AgentLLMModel,
    Conversation,
    ConversationId,
    Invitation,
    Location,
    LocationId,
    Weather,
    WorldSnapshot,
    TimeSnapshot,
    TimePeriod,
)
from engine.observer.api import (
    ObserverAPI,
    ObserverError,
    AgentNotFoundError,
    InvalidLocationError,
    ConversationError,
)
from engine.services.scheduler import Scheduler


@pytest.fixture
def mock_engine(sample_agent: AgentSnapshot, all_locations: dict[LocationId, Location]):
    """Create a mock VillageEngine."""
    engine = Mock()

    # Basic properties
    engine.tick = 10
    engine.world = Mock()
    engine.world.weather = Weather.CLEAR
    engine.world.locations = all_locations

    # Time snapshot
    engine.time_snapshot = TimeSnapshot(
        world_time=datetime(2024, 6, 15, 12, 0),
        tick=10,
        start_date=datetime(2024, 6, 15, 0, 0, 0),
    )

    # Agents
    engine.agents = {sample_agent.name: sample_agent}

    # Conversations
    engine.conversations = {}

    # Pending invites
    engine.pending_invites = {}

    # Scheduler
    engine.scheduler = Scheduler()

    # Event store
    engine.event_store = Mock()
    engine.event_store.get_events_since = Mock(return_value=[])

    # Methods
    engine.commit_event = Mock()
    engine.apply_effect = Mock()
    engine.write_to_agent_dreams = Mock()
    engine.end_conversation = Mock(return_value=None)

    return engine


@pytest.fixture
def api(mock_engine) -> ObserverAPI:
    """Create an ObserverAPI with mock engine."""
    return ObserverAPI(mock_engine)


class TestObserverAPIQueryVillage:
    """Tests for village-level queries."""

    def test_get_village_snapshot(self, api: ObserverAPI):
        """Test getting complete village snapshot."""
        snapshot = api.get_village_snapshot()

        assert snapshot.tick == 10
        assert snapshot.weather == "clear"

    def test_get_time_snapshot(self, api: ObserverAPI):
        """Test getting time snapshot."""
        snapshot = api.get_time_snapshot()

        assert snapshot.tick == 10
        assert snapshot.day_number == 1
        assert snapshot.time_of_day == "afternoon"  # 12:00 is afternoon

    def test_get_weather(self, api: ObserverAPI):
        """Test getting weather."""
        weather = api.get_weather()

        assert weather == "clear"


class TestObserverAPIQueryAgents:
    """Tests for agent queries."""

    def test_get_agent_snapshot(self, api: ObserverAPI, sample_agent: AgentSnapshot):
        """Test getting single agent snapshot."""
        snapshot = api.get_agent_snapshot(sample_agent.name)

        assert snapshot is not None
        assert snapshot.name == sample_agent.name
        assert snapshot.mood == sample_agent.mood

    def test_get_agent_snapshot_not_found(self, api: ObserverAPI):
        """Test getting nonexistent agent returns None."""
        snapshot = api.get_agent_snapshot(AgentName("Unknown"))

        assert snapshot is None

    def test_get_all_agents_snapshot(self, api: ObserverAPI, sample_agent: AgentSnapshot):
        """Test getting all agents."""
        snapshots = api.get_all_agents_snapshot()

        assert sample_agent.name in snapshots
        assert snapshots[sample_agent.name].name == sample_agent.name

    def test_get_agent_location(self, api: ObserverAPI, sample_agent: AgentSnapshot):
        """Test getting agent location."""
        location = api.get_agent_location(sample_agent.name)

        assert location == sample_agent.location

    def test_get_agent_location_not_found(self, api: ObserverAPI):
        """Test getting location of nonexistent agent."""
        location = api.get_agent_location(AgentName("Unknown"))

        assert location is None

    def test_get_agents_at_location(self, api: ObserverAPI, mock_engine, sample_agent: AgentSnapshot):
        """Test getting agents at a location."""
        agents = api.get_agents_at_location(sample_agent.location)

        assert sample_agent.name in agents


class TestObserverAPIQueryConversations:
    """Tests for conversation queries."""

    def test_get_conversations_empty(self, api: ObserverAPI):
        """Test getting conversations when none exist."""
        convs = api.get_conversations()

        assert convs == []

    def test_get_conversations(self, api: ObserverAPI, mock_engine, sample_conversation: Conversation):
        """Test getting conversations."""
        mock_engine.conversations = {sample_conversation.id: sample_conversation}

        convs = api.get_conversations()

        assert len(convs) == 1
        assert convs[0].id == sample_conversation.id

    def test_get_conversation_for_agent(self, api: ObserverAPI, mock_engine, sample_conversation: Conversation):
        """Test getting conversation for a participant."""
        mock_engine.conversations = {sample_conversation.id: sample_conversation}

        # frozenset is not subscriptable, use next(iter(...))
        participant = next(iter(sample_conversation.participants))
        conv = api.get_conversation_for_agent(participant)

        assert conv is not None
        assert conv.id == sample_conversation.id

    def test_get_conversation_for_agent_none(self, api: ObserverAPI):
        """Test getting conversation for agent not in any."""
        conv = api.get_conversation_for_agent(AgentName("Lonely"))

        assert conv is None

    def test_has_active_conversation_false(self, api: ObserverAPI):
        """Test checking for active conversations when none."""
        assert api.has_active_conversation() is False

    def test_has_active_conversation_true(self, api: ObserverAPI, mock_engine, sample_conversation: Conversation):
        """Test checking for active conversations when one exists."""
        mock_engine.conversations = {sample_conversation.id: sample_conversation}

        assert api.has_active_conversation() is True

    def test_get_conversation_participants(self, api: ObserverAPI, mock_engine, sample_conversation: Conversation):
        """Test getting all conversation participants."""
        mock_engine.conversations = {sample_conversation.id: sample_conversation}

        participants = api.get_conversation_participants()

        for p in sample_conversation.participants:
            assert p in participants


class TestObserverAPIQueryInvites:
    """Tests for invite queries."""

    def test_get_pending_invites_empty(self, api: ObserverAPI):
        """Test getting invites when none exist."""
        invites = api.get_pending_invites()

        assert invites == []

    def test_get_pending_invites(self, api: ObserverAPI, mock_engine, sample_invitation: Invitation):
        """Test getting pending invites."""
        mock_engine.pending_invites = {sample_invitation.invitee: sample_invitation}

        invites = api.get_pending_invites()

        assert len(invites) == 1

    def test_get_invites_for_agent(self, api: ObserverAPI, mock_engine, sample_invitation: Invitation):
        """Test getting invites for specific agent."""
        mock_engine.pending_invites = {sample_invitation.invitee: sample_invitation}

        invites = api.get_invites_for_agent(sample_invitation.invitee)

        assert len(invites) == 1

    def test_get_invites_for_agent_none(self, api: ObserverAPI):
        """Test getting invites for agent with none."""
        invites = api.get_invites_for_agent(AgentName("NoInvites"))

        assert invites == []


class TestObserverAPIQuerySchedule:
    """Tests for schedule queries."""

    def test_get_schedule_snapshot(self, api: ObserverAPI):
        """Test getting schedule snapshot."""
        snapshot = api.get_schedule_snapshot()

        assert snapshot is not None
        assert snapshot.forced_next is None


class TestObserverAPIQueryEvents:
    """Tests for event queries."""

    def test_get_recent_events(self, api: ObserverAPI, mock_engine):
        """Test getting recent events."""
        events = api.get_recent_events(since_tick=5)

        mock_engine.event_store.get_events_since.assert_called_once_with(5)


class TestObserverAPICommandWorldEvents:
    """Tests for world event commands."""

    def test_do_trigger_event(self, api: ObserverAPI, mock_engine):
        """Test triggering a world event."""
        event = api.do_trigger_event("A storm approaches!")

        assert event.description == "A storm approaches!"
        mock_engine.commit_event.assert_called_once()

    def test_do_set_weather(self, api: ObserverAPI, mock_engine):
        """Test setting weather."""
        event = api.do_set_weather("rainy")

        assert event.new_weather == "rainy"
        mock_engine.commit_event.assert_called_once()

    def test_do_send_dream(self, api: ObserverAPI, mock_engine, sample_agent: AgentSnapshot):
        """Test sending a dream."""
        event = api.do_send_dream(sample_agent.name, "A vision of stars...")

        mock_engine.write_to_agent_dreams.assert_called_once_with(
            sample_agent.name, "A vision of stars..."
        )
        mock_engine.commit_event.assert_called_once()

    def test_do_send_dream_unknown_agent(self, api: ObserverAPI):
        """Test sending dream to unknown agent raises."""
        with pytest.raises(AgentNotFoundError):
            api.do_send_dream(AgentName("Unknown"), "Dream")


class TestObserverAPICommandScheduling:
    """Tests for scheduling commands."""

    def test_do_force_turn(self, api: ObserverAPI, mock_engine, sample_agent: AgentSnapshot):
        """Test forcing an agent's turn."""
        api.do_force_turn(sample_agent.name)

        assert mock_engine.scheduler.get_forced_next() == sample_agent.name

    def test_do_force_turn_unknown_agent(self, api: ObserverAPI):
        """Test forcing turn for unknown agent raises."""
        with pytest.raises(AgentNotFoundError):
            api.do_force_turn(AgentName("Unknown"))

    def test_do_skip_turns(self, api: ObserverAPI, mock_engine, sample_agent: AgentSnapshot):
        """Test skipping agent turns."""
        api.do_skip_turns(sample_agent.name, 3)

        assert mock_engine.scheduler._skip_counts[sample_agent.name] == 3

    def test_do_skip_turns_unknown_agent(self, api: ObserverAPI):
        """Test skipping turns for unknown agent raises."""
        with pytest.raises(AgentNotFoundError):
            api.do_skip_turns(AgentName("Unknown"), 2)

    def test_do_clear_all_modifiers(self, api: ObserverAPI, mock_engine, sample_agent: AgentSnapshot):
        """Test clearing all scheduling modifiers."""
        mock_engine.scheduler.force_next_turn(sample_agent.name)
        mock_engine.scheduler.skip_turns(sample_agent.name, 2)

        api.do_clear_all_modifiers()

        assert mock_engine.scheduler.get_forced_next() is None
        assert mock_engine.scheduler._skip_counts == {}


class TestObserverAPICommandAgentManipulation:
    """Tests for agent manipulation commands."""

    def test_do_move_agent(self, api: ObserverAPI, mock_engine, sample_agent: AgentSnapshot):
        """Test moving an agent."""
        destination = LocationId("library")

        effect = api.do_move_agent(sample_agent.name, destination)

        assert effect.agent == sample_agent.name
        assert effect.to_location == destination
        mock_engine.apply_effect.assert_called_once()

    def test_do_move_agent_unknown(self, api: ObserverAPI):
        """Test moving unknown agent raises."""
        with pytest.raises(AgentNotFoundError):
            api.do_move_agent(AgentName("Unknown"), LocationId("library"))

    def test_do_move_agent_invalid_location(self, api: ObserverAPI, sample_agent: AgentSnapshot):
        """Test moving to invalid location raises."""
        with pytest.raises(InvalidLocationError):
            api.do_move_agent(sample_agent.name, LocationId("nonexistent"))

    def test_do_set_mood(self, api: ObserverAPI, mock_engine, sample_agent: AgentSnapshot):
        """Test setting agent mood."""
        effect = api.do_set_mood(sample_agent.name, "joyful")

        assert effect.agent == sample_agent.name
        assert effect.mood == "joyful"
        mock_engine.apply_effect.assert_called_once()

    def test_do_set_mood_unknown_agent(self, api: ObserverAPI):
        """Test setting mood for unknown agent raises."""
        with pytest.raises(AgentNotFoundError):
            api.do_set_mood(AgentName("Unknown"), "happy")

    def test_do_set_sleeping_sleep(self, api: ObserverAPI, mock_engine, sample_agent: AgentSnapshot):
        """Test putting agent to sleep."""
        effect = api.do_set_sleeping(sample_agent.name, True)

        assert effect is not None
        mock_engine.apply_effect.assert_called_once()

    def test_do_set_sleeping_wake(self, api: ObserverAPI, mock_engine, sample_agent: AgentSnapshot):
        """Test waking an agent."""
        # Make agent sleeping
        sleeping_agent = AgentSnapshot(**{**sample_agent.model_dump(), "is_sleeping": True})
        mock_engine.agents = {sleeping_agent.name: sleeping_agent}

        effect = api.do_set_sleeping(sleeping_agent.name, False)

        assert effect is not None
        mock_engine.apply_effect.assert_called_once()

    def test_do_set_sleeping_no_change(self, api: ObserverAPI, mock_engine, sample_agent: AgentSnapshot):
        """Test no effect when already in desired state."""
        # Agent is already awake
        result = api.do_set_sleeping(sample_agent.name, False)

        assert result is None
        mock_engine.apply_effect.assert_not_called()

    def test_do_set_sleeping_unknown_agent(self, api: ObserverAPI):
        """Test sleeping unknown agent raises."""
        with pytest.raises(AgentNotFoundError):
            api.do_set_sleeping(AgentName("Unknown"), True)

    def test_do_boost_energy(self, api: ObserverAPI, mock_engine, sample_agent: AgentSnapshot):
        """Test boosting agent energy."""
        effect = api.do_boost_energy(sample_agent.name, 25)

        assert effect.agent == sample_agent.name
        mock_engine.apply_effect.assert_called_once()

    def test_do_boost_energy_caps_at_100(self, api: ObserverAPI, mock_engine, sample_agent: AgentSnapshot):
        """Test energy boost is capped at 100."""
        # Agent has 85 energy
        effect = api.do_boost_energy(sample_agent.name, 50)

        assert effect.energy == 100  # Capped

    def test_do_boost_energy_unknown_agent(self, api: ObserverAPI):
        """Test boosting energy for unknown agent raises."""
        with pytest.raises(AgentNotFoundError):
            api.do_boost_energy(AgentName("Unknown"), 20)

    def test_do_record_action(self, api: ObserverAPI, mock_engine, sample_agent: AgentSnapshot):
        """Test recording an action."""
        event = api.do_record_action(sample_agent.name, "Built a chair")

        assert event.agent == sample_agent.name
        assert event.description == "Built a chair"
        mock_engine.commit_event.assert_called_once()

    def test_do_record_action_unknown_agent(self, api: ObserverAPI):
        """Test recording action for unknown agent raises."""
        with pytest.raises(AgentNotFoundError):
            api.do_record_action(AgentName("Unknown"), "Did something")


class TestObserverAPICommandConversation:
    """Tests for conversation commands."""

    def test_do_end_conversation_by_id(self, api: ObserverAPI, mock_engine, sample_conversation: Conversation):
        """Test ending specific conversation."""
        mock_engine.conversations = {sample_conversation.id: sample_conversation}

        api.do_end_conversation(sample_conversation.id)

        mock_engine.end_conversation.assert_called_once_with(
            sample_conversation.id, reason="observer_ended"
        )

    def test_do_end_conversation_not_found(self, api: ObserverAPI):
        """Test ending nonexistent conversation raises."""
        with pytest.raises(ConversationError):
            api.do_end_conversation(ConversationId("nonexistent"))

    def test_do_end_conversation_first(self, api: ObserverAPI, mock_engine, sample_conversation: Conversation):
        """Test ending first conversation when no ID given."""
        mock_engine.conversations = {sample_conversation.id: sample_conversation}

        api.do_end_conversation()

        mock_engine.end_conversation.assert_called_once()

    def test_do_end_conversation_none(self, api: ObserverAPI):
        """Test ending conversation when none exist returns None."""
        result = api.do_end_conversation()

        assert result is None
