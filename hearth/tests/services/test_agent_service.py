"""Tests for AgentService."""

import pytest
from pathlib import Path

from core.types import Position, Direction, Rect, AgentName, ObjectId, LandmarkName
from core.agent import Agent, AgentModel, Inventory, InventoryStack, Journey
from core.objects import Item
from core.terrain import Terrain
from core.world import Cell

from services import (
    AgentService,
    WorldService,
    AgentNotFoundError,
    InvalidAgentStateError,
    JourneyError,
    InventoryError,
    SensedAgent,
)
from storage import Storage


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def sample_agent() -> Agent:
    """Create a sample agent for testing."""
    return Agent(
        name=AgentName("Ember"),
        model=AgentModel(id="claude-sonnet-4-5", display_name="Sonnet"),
        personality="Creative and curious",
        position=Position(10, 10),
    )


@pytest.fixture
def sample_agent_sage() -> Agent:
    """Create a second sample agent."""
    return Agent(
        name=AgentName("Sage"),
        model=AgentModel(id="claude-opus-4-5", display_name="Opus"),
        personality="Thoughtful and wise",
        position=Position(20, 20),
    )


@pytest.fixture
def sample_agent_river() -> Agent:
    """Create a third sample agent."""
    return Agent(
        name=AgentName("River"),
        model=AgentModel(id="claude-sonnet-4-5", display_name="Sonnet"),
        personality="Flowing and adaptable",
        position=Position(50, 50),
    )


@pytest.fixture
async def agent_service(storage: Storage) -> AgentService:
    """Create AgentService with connected storage."""
    return AgentService(storage)


# -----------------------------------------------------------------------------
# Roster Operations (CRUD)
# -----------------------------------------------------------------------------


class TestRosterCRUD:
    """Test basic CRUD operations."""

    async def test_get_agent_returns_none_for_missing(
        self, agent_service: AgentService
    ):
        """Should return None when agent doesn't exist."""
        result = await agent_service.get_agent(AgentName("Nonexistent"))
        assert result is None

    async def test_get_agent_or_raise_raises_for_missing(
        self, agent_service: AgentService
    ):
        """Should raise AgentNotFoundError when agent doesn't exist."""
        with pytest.raises(AgentNotFoundError) as exc_info:
            await agent_service.get_agent_or_raise(AgentName("Nonexistent"))
        assert exc_info.value.agent_name == AgentName("Nonexistent")

    async def test_save_and_get_agent(
        self, agent_service: AgentService, sample_agent: Agent
    ):
        """Should save and retrieve agent."""
        await agent_service.save_agent(sample_agent)

        retrieved = await agent_service.get_agent(sample_agent.name)
        assert retrieved is not None
        assert retrieved.name == sample_agent.name
        assert retrieved.position == sample_agent.position
        assert retrieved.personality == sample_agent.personality

    async def test_get_all_agents(
        self,
        agent_service: AgentService,
        sample_agent: Agent,
        sample_agent_sage: Agent,
    ):
        """Should return all agents."""
        await agent_service.save_agent(sample_agent)
        await agent_service.save_agent(sample_agent_sage)

        agents = await agent_service.get_all_agents()
        assert len(agents) == 2
        names = {a.name for a in agents}
        assert AgentName("Ember") in names
        assert AgentName("Sage") in names

    async def test_delete_agent(
        self, agent_service: AgentService, sample_agent: Agent
    ):
        """Should delete agent."""
        await agent_service.save_agent(sample_agent)
        await agent_service.delete_agent(sample_agent.name)

        result = await agent_service.get_agent(sample_agent.name)
        assert result is None


# -----------------------------------------------------------------------------
# Spatial Queries
# -----------------------------------------------------------------------------


class TestSpatialQueries:
    """Test spatial query operations."""

    async def test_get_agents_at_position(
        self,
        agent_service: AgentService,
        sample_agent: Agent,
        sample_agent_sage: Agent,
    ):
        """Should return agents at exact position."""
        # Place both at same position
        ember = sample_agent.with_position(Position(15, 15))
        sage = sample_agent_sage.with_position(Position(15, 15))

        await agent_service.save_agent(ember)
        await agent_service.save_agent(sage)

        agents = await agent_service.get_agents_at(Position(15, 15))
        assert len(agents) == 2

    async def test_get_agents_at_empty_position(
        self, agent_service: AgentService, sample_agent: Agent
    ):
        """Should return empty list for position with no agents."""
        await agent_service.save_agent(sample_agent)

        agents = await agent_service.get_agents_at(Position(99, 99))
        assert len(agents) == 0

    async def test_get_agents_in_rect(
        self,
        agent_service: AgentService,
        sample_agent: Agent,
        sample_agent_sage: Agent,
        sample_agent_river: Agent,
    ):
        """Should return agents within rectangle."""
        await agent_service.save_agent(sample_agent)  # at (10, 10)
        await agent_service.save_agent(sample_agent_sage)  # at (20, 20)
        await agent_service.save_agent(sample_agent_river)  # at (50, 50)

        rect = Rect(5, 5, 25, 25)
        agents = await agent_service.get_agents_in_rect(rect)

        assert len(agents) == 2
        names = {a.name for a in agents}
        assert AgentName("Ember") in names
        assert AgentName("Sage") in names
        assert AgentName("River") not in names

    async def test_get_nearby_agents(
        self,
        agent_service: AgentService,
        sample_agent: Agent,
        sample_agent_sage: Agent,
    ):
        """Should return agents within radius by Manhattan distance."""
        ember = sample_agent.with_position(Position(10, 10))
        sage = sample_agent_sage.with_position(Position(15, 15))  # 10 away

        await agent_service.save_agent(ember)
        await agent_service.save_agent(sage)

        # Radius 10 should include Sage (exactly 10 Manhattan distance)
        nearby = await agent_service.get_nearby_agents(Position(10, 10), radius=10)
        assert len(nearby) == 2  # Includes self (Ember) at (10,10)

        # Radius 9 should exclude Sage
        nearby = await agent_service.get_nearby_agents(Position(10, 10), radius=9)
        assert len(nearby) == 1
        assert nearby[0].name == AgentName("Ember")


# -----------------------------------------------------------------------------
# State Queries
# -----------------------------------------------------------------------------


class TestStateQueries:
    """Test state-based queries."""

    async def test_get_awake_agents(
        self,
        agent_service: AgentService,
        sample_agent: Agent,
        sample_agent_sage: Agent,
    ):
        """Should return only awake agents."""
        ember = sample_agent.with_sleeping(False)
        sage = sample_agent_sage.with_sleeping(True)

        await agent_service.save_agent(ember)
        await agent_service.save_agent(sage)

        awake = await agent_service.get_awake_agents()
        assert len(awake) == 1
        assert awake[0].name == AgentName("Ember")

    async def test_get_sleeping_agents(
        self,
        agent_service: AgentService,
        sample_agent: Agent,
        sample_agent_sage: Agent,
    ):
        """Should return only sleeping agents."""
        ember = sample_agent.with_sleeping(False)
        sage = sample_agent_sage.with_sleeping(True)

        await agent_service.save_agent(ember)
        await agent_service.save_agent(sage)

        sleeping = await agent_service.get_sleeping_agents()
        assert len(sleeping) == 1
        assert sleeping[0].name == AgentName("Sage")

    async def test_get_traveling_agents(
        self,
        agent_service: AgentService,
        sample_agent: Agent,
        sample_agent_sage: Agent,
    ):
        """Should return only agents with active journeys."""
        from core.agent import JourneyDestination

        # Ember is not traveling
        ember = sample_agent

        # Sage is traveling
        dest = JourneyDestination.to_position(Position(30, 30))
        journey = Journey.create(
            destination=dest,
            path=(Position(20, 20), Position(21, 20), Position(22, 20)),
        )
        sage = sample_agent_sage.with_journey(journey)

        await agent_service.save_agent(ember)
        await agent_service.save_agent(sage)

        traveling = await agent_service.get_traveling_agents()
        assert len(traveling) == 1
        assert traveling[0].name == AgentName("Sage")


# -----------------------------------------------------------------------------
# Relationship Queries
# -----------------------------------------------------------------------------


class TestRelationshipQueries:
    """Test relationship queries."""

    async def test_get_known_agents(
        self,
        agent_service: AgentService,
        sample_agent: Agent,
        sample_agent_sage: Agent,
    ):
        """Should return known agents set."""
        ember = sample_agent.with_known_agent(AgentName("Sage"))
        await agent_service.save_agent(ember)
        await agent_service.save_agent(sample_agent_sage)

        known = await agent_service.get_known_agents(AgentName("Ember"))
        assert AgentName("Sage") in known

    async def test_have_met_true(
        self,
        agent_service: AgentService,
        sample_agent: Agent,
        sample_agent_sage: Agent,
    ):
        """Should return True when agents have met."""
        ember = sample_agent.with_known_agent(AgentName("Sage"))
        sage = sample_agent_sage.with_known_agent(AgentName("Ember"))

        await agent_service.save_agent(ember)
        await agent_service.save_agent(sage)

        assert await agent_service.have_met(AgentName("Ember"), AgentName("Sage"))

    async def test_have_met_false(
        self, agent_service: AgentService, sample_agent: Agent
    ):
        """Should return False when agents haven't met."""
        await agent_service.save_agent(sample_agent)

        assert not await agent_service.have_met(
            AgentName("Ember"), AgentName("Nonexistent")
        )


# -----------------------------------------------------------------------------
# Position Updates
# -----------------------------------------------------------------------------


class TestPositionUpdates:
    """Test position update operations."""

    async def test_update_position(
        self, agent_service: AgentService, sample_agent: Agent
    ):
        """Should update agent's position."""
        await agent_service.save_agent(sample_agent)

        updated = await agent_service.update_position(
            AgentName("Ember"), Position(25, 25)
        )
        assert updated.position == Position(25, 25)

        # Verify persisted
        retrieved = await agent_service.get_agent(AgentName("Ember"))
        assert retrieved.position == Position(25, 25)

    async def test_update_position_nonexistent_agent(
        self, agent_service: AgentService
    ):
        """Should raise error for nonexistent agent."""
        with pytest.raises(AgentNotFoundError):
            await agent_service.update_position(
                AgentName("Nonexistent"), Position(25, 25)
            )

    async def test_move_agent_success(
        self,
        agent_service: AgentService,
        world_service: WorldService,
        sample_agent: Agent,
    ):
        """Should move agent one cell in direction."""
        await agent_service.save_agent(sample_agent)

        updated = await agent_service.move_agent(
            AgentName("Ember"), Direction.NORTH, world_service
        )
        assert updated.position == Position(10, 11)

    async def test_move_agent_blocked_by_wall(
        self,
        agent_service: AgentService,
        world_service: WorldService,
        sample_agent: Agent,
    ):
        """Should raise error when blocked by wall."""
        await agent_service.save_agent(sample_agent)
        await world_service.place_wall(Position(10, 10), Direction.NORTH)

        with pytest.raises(InvalidAgentStateError):
            await agent_service.move_agent(
                AgentName("Ember"), Direction.NORTH, world_service
            )


# -----------------------------------------------------------------------------
# Sleep State
# -----------------------------------------------------------------------------


class TestSleepState:
    """Test sleep state operations."""

    async def test_set_sleeping_true(
        self, agent_service: AgentService, sample_agent: Agent
    ):
        """Should set agent to sleeping."""
        await agent_service.save_agent(sample_agent)

        updated = await agent_service.set_sleeping(AgentName("Ember"), True)
        assert updated.is_sleeping is True

    async def test_set_sleeping_false(
        self, agent_service: AgentService, sample_agent: Agent
    ):
        """Should set agent to awake."""
        sleeping = sample_agent.with_sleeping(True)
        await agent_service.save_agent(sleeping)

        updated = await agent_service.set_sleeping(AgentName("Ember"), False)
        assert updated.is_sleeping is False

    async def test_wake_agent(
        self, agent_service: AgentService, sample_agent: Agent
    ):
        """Should wake sleeping agent."""
        sleeping = sample_agent.with_sleeping(True)
        await agent_service.save_agent(sleeping)

        updated = await agent_service.wake_agent(AgentName("Ember"))
        assert updated.is_sleeping is False

    async def test_sleep_agent(
        self, agent_service: AgentService, sample_agent: Agent
    ):
        """Should put agent to sleep."""
        await agent_service.save_agent(sample_agent)

        updated = await agent_service.sleep_agent(AgentName("Ember"))
        assert updated.is_sleeping is True


# -----------------------------------------------------------------------------
# Relationships
# -----------------------------------------------------------------------------


class TestRelationships:
    """Test relationship recording."""

    async def test_record_meeting(
        self,
        agent_service: AgentService,
        sample_agent: Agent,
        sample_agent_sage: Agent,
    ):
        """Should update both agents to know each other."""
        await agent_service.save_agent(sample_agent)
        await agent_service.save_agent(sample_agent_sage)

        ember, sage = await agent_service.record_meeting(
            AgentName("Ember"), AgentName("Sage")
        )

        assert AgentName("Sage") in ember.known_agents
        assert AgentName("Ember") in sage.known_agents

    async def test_record_meeting_idempotent(
        self,
        agent_service: AgentService,
        sample_agent: Agent,
        sample_agent_sage: Agent,
    ):
        """Recording same meeting twice should be safe."""
        await agent_service.save_agent(sample_agent)
        await agent_service.save_agent(sample_agent_sage)

        await agent_service.record_meeting(AgentName("Ember"), AgentName("Sage"))
        ember, sage = await agent_service.record_meeting(
            AgentName("Ember"), AgentName("Sage")
        )

        assert AgentName("Sage") in ember.known_agents
        assert AgentName("Ember") in sage.known_agents


# -----------------------------------------------------------------------------
# Session Tracking
# -----------------------------------------------------------------------------


class TestSessionTracking:
    """Test session ID tracking."""

    async def test_update_session(
        self, agent_service: AgentService, sample_agent: Agent
    ):
        """Should update session ID and tick."""
        await agent_service.save_agent(sample_agent)

        updated = await agent_service.update_session(
            AgentName("Ember"), "session-123", tick=42
        )

        assert updated.session_id == "session-123"
        assert updated.last_active_tick == 42

    async def test_update_session_to_none(
        self, agent_service: AgentService, sample_agent: Agent
    ):
        """Should clear session ID."""
        with_session = sample_agent.with_session_id("old-session")
        await agent_service.save_agent(with_session)

        updated = await agent_service.update_session(
            AgentName("Ember"), None, tick=50
        )

        assert updated.session_id is None
        assert updated.last_active_tick == 50


# -----------------------------------------------------------------------------
# Inventory Operations
# -----------------------------------------------------------------------------


class TestInventoryOperations:
    """Test inventory management."""

    async def test_add_resource(
        self, agent_service: AgentService, sample_agent: Agent
    ):
        """Should add stackable resource."""
        await agent_service.save_agent(sample_agent)

        updated = await agent_service.add_resource(AgentName("Ember"), "wood", 5)

        assert updated.inventory.get_resource_quantity("wood") == 5

    async def test_add_resource_multiple_times(
        self, agent_service: AgentService, sample_agent: Agent
    ):
        """Should accumulate resource quantities."""
        await agent_service.save_agent(sample_agent)

        await agent_service.add_resource(AgentName("Ember"), "wood", 5)
        updated = await agent_service.add_resource(AgentName("Ember"), "wood", 3)

        assert updated.inventory.get_resource_quantity("wood") == 8

    async def test_remove_resource(
        self, agent_service: AgentService, sample_agent: Agent
    ):
        """Should remove stackable resource."""
        with_wood = sample_agent.add_resource("wood", 10)
        await agent_service.save_agent(with_wood)

        updated = await agent_service.remove_resource(AgentName("Ember"), "wood", 3)

        assert updated.inventory.get_resource_quantity("wood") == 7

    async def test_remove_resource_insufficient(
        self, agent_service: AgentService, sample_agent: Agent
    ):
        """Should raise error when insufficient quantity."""
        with_wood = sample_agent.add_resource("wood", 5)
        await agent_service.save_agent(with_wood)

        with pytest.raises(InventoryError):
            await agent_service.remove_resource(AgentName("Ember"), "wood", 10)

    async def test_get_resource_quantity(
        self, agent_service: AgentService, sample_agent: Agent
    ):
        """Should return resource quantity."""
        with_wood = sample_agent.add_resource("wood", 15)
        await agent_service.save_agent(with_wood)

        qty = await agent_service.get_resource_quantity(AgentName("Ember"), "wood")
        assert qty == 15

    async def test_get_resource_quantity_zero(
        self, agent_service: AgentService, sample_agent: Agent
    ):
        """Should return 0 for missing resource."""
        await agent_service.save_agent(sample_agent)

        qty = await agent_service.get_resource_quantity(AgentName("Ember"), "gold")
        assert qty == 0

    async def test_has_resource_true(
        self, agent_service: AgentService, sample_agent: Agent
    ):
        """Should return True when has enough resource."""
        with_wood = sample_agent.add_resource("wood", 10)
        await agent_service.save_agent(with_wood)

        assert await agent_service.has_resource(AgentName("Ember"), "wood", 5)
        assert await agent_service.has_resource(AgentName("Ember"), "wood", 10)

    async def test_has_resource_false(
        self, agent_service: AgentService, sample_agent: Agent
    ):
        """Should return False when insufficient resource."""
        with_wood = sample_agent.add_resource("wood", 5)
        await agent_service.save_agent(with_wood)

        assert not await agent_service.has_resource(AgentName("Ember"), "wood", 10)

    async def test_add_unique_item(
        self, agent_service: AgentService, sample_agent: Agent
    ):
        """Should add unique item to inventory."""
        await agent_service.save_agent(sample_agent)

        item = Item.unique("carved_bowl", properties=("decorated",))
        updated = await agent_service.add_item(AgentName("Ember"), item)

        assert updated.inventory.has_item(item.id)

    async def test_remove_unique_item(
        self, agent_service: AgentService, sample_agent: Agent
    ):
        """Should remove unique item from inventory."""
        item = Item.unique("carved_bowl", properties=("decorated",))
        with_item = sample_agent.add_item(item)
        await agent_service.save_agent(with_item)

        updated = await agent_service.remove_item(AgentName("Ember"), item.id)

        assert not updated.inventory.has_item(item.id)

    async def test_remove_nonexistent_item(
        self, agent_service: AgentService, sample_agent: Agent
    ):
        """Should raise error for nonexistent item."""
        await agent_service.save_agent(sample_agent)

        with pytest.raises(InventoryError):
            await agent_service.remove_item(
                AgentName("Ember"), ObjectId("nonexistent")
            )

    async def test_get_item(
        self, agent_service: AgentService, sample_agent: Agent
    ):
        """Should get specific item from inventory."""
        item = Item.unique("carved_bowl", properties=("decorated",))
        with_item = sample_agent.add_item(item)
        await agent_service.save_agent(with_item)

        retrieved = await agent_service.get_item(AgentName("Ember"), item.id)
        assert retrieved is not None
        assert retrieved.item_type == "carved_bowl"

    async def test_get_inventory(
        self, agent_service: AgentService, sample_agent: Agent
    ):
        """Should get full inventory."""
        with_stuff = sample_agent.add_resource("wood", 10).add_resource("stone", 5)
        await agent_service.save_agent(with_stuff)

        inv = await agent_service.get_inventory(AgentName("Ember"))
        assert inv.get_resource_quantity("wood") == 10
        assert inv.get_resource_quantity("stone") == 5

    async def test_set_inventory(
        self, agent_service: AgentService, sample_agent: Agent
    ):
        """Should replace entire inventory."""
        await agent_service.save_agent(sample_agent)

        new_inv = Inventory(
            stacks=(
                InventoryStack(item_type="gold", quantity=100),
            )
        )
        updated = await agent_service.set_inventory(AgentName("Ember"), new_inv)

        assert updated.inventory.get_resource_quantity("gold") == 100


# -----------------------------------------------------------------------------
# Presence Sensing
# -----------------------------------------------------------------------------


class TestPresenceSensing:
    """Test presence sensing."""

    async def test_sense_others_returns_known_only(
        self,
        agent_service: AgentService,
        sample_agent: Agent,
        sample_agent_sage: Agent,
        sample_agent_river: Agent,
    ):
        """Should only sense known agents."""
        # Ember knows Sage but not River
        ember = sample_agent.with_known_agent(AgentName("Sage"))

        await agent_service.save_agent(ember)
        await agent_service.save_agent(sample_agent_sage)
        await agent_service.save_agent(sample_agent_river)

        sensed = await agent_service.sense_others(AgentName("Ember"))

        names = {s.name for s in sensed}
        assert AgentName("Sage") in names
        assert AgentName("River") not in names

    async def test_sense_others_excludes_sleeping(
        self,
        agent_service: AgentService,
        sample_agent: Agent,
        sample_agent_sage: Agent,
    ):
        """Should exclude sleeping agents from sensing."""
        ember = sample_agent.with_known_agent(AgentName("Sage"))
        sage = sample_agent_sage.with_sleeping(True)

        await agent_service.save_agent(ember)
        await agent_service.save_agent(sage)

        sensed = await agent_service.sense_others(AgentName("Ember"))
        assert len(sensed) == 0

    async def test_sense_others_nearby_category(
        self,
        agent_service: AgentService,
        sample_agent: Agent,
        sample_agent_sage: Agent,
    ):
        """Should categorize nearby agents (≤10 cells)."""
        ember = sample_agent.with_known_agent(AgentName("Sage")).with_position(
            Position(10, 10)
        )
        sage = sample_agent_sage.with_position(Position(15, 12))  # 7 away

        await agent_service.save_agent(ember)
        await agent_service.save_agent(sage)

        sensed = await agent_service.sense_others(AgentName("Ember"))
        assert len(sensed) == 1
        assert sensed[0].distance_category == "nearby"

    async def test_sense_others_far_category(
        self,
        agent_service: AgentService,
        sample_agent: Agent,
        sample_agent_sage: Agent,
    ):
        """Should categorize far agents (11-30 cells)."""
        ember = sample_agent.with_known_agent(AgentName("Sage")).with_position(
            Position(10, 10)
        )
        sage = sample_agent_sage.with_position(Position(25, 15))  # 20 away

        await agent_service.save_agent(ember)
        await agent_service.save_agent(sage)

        sensed = await agent_service.sense_others(AgentName("Ember"))
        assert len(sensed) == 1
        assert sensed[0].distance_category == "far"

    async def test_sense_others_very_far_category(
        self,
        agent_service: AgentService,
        sample_agent: Agent,
        sample_agent_sage: Agent,
    ):
        """Should categorize very far agents (31+ cells)."""
        ember = sample_agent.with_known_agent(AgentName("Sage")).with_position(
            Position(10, 10)
        )
        sage = sample_agent_sage.with_position(Position(50, 50))  # 80 away

        await agent_service.save_agent(ember)
        await agent_service.save_agent(sage)

        sensed = await agent_service.sense_others(AgentName("Ember"))
        assert len(sensed) == 1
        assert sensed[0].distance_category == "very far"

    async def test_sense_others_direction(
        self,
        agent_service: AgentService,
        sample_agent: Agent,
        sample_agent_sage: Agent,
    ):
        """Should report direction to sensed agents."""
        ember = sample_agent.with_known_agent(AgentName("Sage")).with_position(
            Position(10, 10)
        )
        sage = sample_agent_sage.with_position(Position(10, 20))  # North

        await agent_service.save_agent(ember)
        await agent_service.save_agent(sage)

        sensed = await agent_service.sense_others(AgentName("Ember"))
        assert len(sensed) == 1
        assert sensed[0].direction == Direction.NORTH


# -----------------------------------------------------------------------------
# Journey State Machine
# -----------------------------------------------------------------------------


class TestJourneyStateMachine:
    """Test journey operations."""

    async def test_start_journey_to_position(
        self,
        agent_service: AgentService,
        world_service: WorldService,
        sample_agent: Agent,
    ):
        """Should start journey to a position."""
        await agent_service.save_agent(sample_agent)

        updated = await agent_service.start_journey(
            AgentName("Ember"), Position(15, 10), world_service
        )

        assert updated.is_journeying
        assert updated.journey is not None

    async def test_start_journey_to_landmark(
        self,
        agent_service: AgentService,
        world_service: WorldService,
        sample_agent: Agent,
    ):
        """Should start journey to a named landmark."""
        await world_service.name_place("The Grove", Position(20, 10))
        await agent_service.save_agent(sample_agent)

        updated = await agent_service.start_journey(
            AgentName("Ember"), LandmarkName("The Grove"), world_service
        )

        assert updated.is_journeying

    async def test_start_journey_unknown_landmark(
        self,
        agent_service: AgentService,
        world_service: WorldService,
        sample_agent: Agent,
    ):
        """Should raise error for unknown landmark."""
        await agent_service.save_agent(sample_agent)

        with pytest.raises(JourneyError):
            await agent_service.start_journey(
                AgentName("Ember"), LandmarkName("Unknown"), world_service
            )

    async def test_advance_journey(
        self,
        agent_service: AgentService,
        world_service: WorldService,
        sample_agent: Agent,
    ):
        """Should advance agent one step along journey."""
        await agent_service.save_agent(sample_agent)
        await agent_service.start_journey(
            AgentName("Ember"), Position(13, 10), world_service
        )

        updated, arrived = await agent_service.advance_journey(AgentName("Ember"))

        assert updated.position == Position(11, 10)
        assert not arrived

    async def test_advance_journey_arrival(
        self,
        agent_service: AgentService,
        world_service: WorldService,
        sample_agent: Agent,
    ):
        """Should detect arrival at destination."""
        await agent_service.save_agent(sample_agent)
        await agent_service.start_journey(
            AgentName("Ember"), Position(11, 10), world_service
        )

        updated, arrived = await agent_service.advance_journey(AgentName("Ember"))

        assert arrived
        assert updated.journey is None  # Journey cleared on arrival

    async def test_advance_journey_not_traveling(
        self, agent_service: AgentService, sample_agent: Agent
    ):
        """Should raise error if not on journey."""
        await agent_service.save_agent(sample_agent)

        with pytest.raises(JourneyError):
            await agent_service.advance_journey(AgentName("Ember"))

    async def test_interrupt_journey(
        self,
        agent_service: AgentService,
        world_service: WorldService,
        sample_agent: Agent,
    ):
        """Should clear journey on interruption."""
        await agent_service.save_agent(sample_agent)
        await agent_service.start_journey(
            AgentName("Ember"), Position(20, 10), world_service
        )

        updated = await agent_service.interrupt_journey(
            AgentName("Ember"), "encountered_agent"
        )

        assert updated.journey is None
        assert not updated.is_journeying

    async def test_is_traveling(
        self,
        agent_service: AgentService,
        world_service: WorldService,
        sample_agent: Agent,
    ):
        """Should check if agent is traveling."""
        await agent_service.save_agent(sample_agent)

        assert not await agent_service.is_traveling(AgentName("Ember"))

        await agent_service.start_journey(
            AgentName("Ember"), Position(20, 10), world_service
        )

        assert await agent_service.is_traveling(AgentName("Ember"))

    async def test_get_journey_progress(
        self,
        agent_service: AgentService,
        world_service: WorldService,
        sample_agent: Agent,
    ):
        """Should return journey progress."""
        await agent_service.save_agent(sample_agent)
        await agent_service.start_journey(
            AgentName("Ember"), Position(15, 10), world_service
        )

        progress = await agent_service.get_journey_progress(AgentName("Ember"))
        assert progress is not None
        current, total = progress
        assert current == 0
        assert total == 5  # 5 steps from (10,10) to (15,10)

    async def test_get_journey_progress_not_traveling(
        self, agent_service: AgentService, sample_agent: Agent
    ):
        """Should return None when not traveling."""
        await agent_service.save_agent(sample_agent)

        progress = await agent_service.get_journey_progress(AgentName("Ember"))
        assert progress is None


# -----------------------------------------------------------------------------
# Pathfinding (A*)
# -----------------------------------------------------------------------------


class TestPathfinding:
    """Test A* pathfinding."""

    async def test_pathfinding_straight_line(
        self,
        agent_service: AgentService,
        world_service: WorldService,
    ):
        """Should find straight path when no obstacles."""
        path = await agent_service._compute_path(
            Position(10, 10), Position(15, 10), world_service
        )

        assert len(path) == 6  # Start + 5 steps
        assert path[0] == Position(10, 10)
        assert path[-1] == Position(15, 10)

    async def test_pathfinding_around_wall(
        self,
        agent_service: AgentService,
        world_service: WorldService,
    ):
        """Should find path around walls."""
        # Place wall blocking direct east path
        await world_service.place_wall(Position(11, 10), Direction.WEST)

        path = await agent_service._compute_path(
            Position(10, 10), Position(12, 10), world_service
        )

        # Path should go around (e.g., north then east then south)
        assert len(path) > 3  # Longer than direct path
        assert path[0] == Position(10, 10)
        assert path[-1] == Position(12, 10)

    async def test_pathfinding_same_position(
        self,
        agent_service: AgentService,
        world_service: WorldService,
    ):
        """Should handle same start and goal."""
        path = await agent_service._compute_path(
            Position(10, 10), Position(10, 10), world_service
        )

        assert path == (Position(10, 10),)

    @pytest.mark.slow  # A* explores entire 500x500 grid when no path exists
    async def test_pathfinding_no_path(
        self,
        agent_service: AgentService,
        world_service: WorldService,
    ):
        """Should raise error when no path exists."""
        # Completely wall off destination
        await world_service.place_wall(Position(12, 10), Direction.NORTH)
        await world_service.place_wall(Position(12, 10), Direction.SOUTH)
        await world_service.place_wall(Position(12, 10), Direction.EAST)
        await world_service.place_wall(Position(12, 10), Direction.WEST)

        with pytest.raises(JourneyError):
            await agent_service._compute_path(
                Position(10, 10), Position(12, 10), world_service
            )


# -----------------------------------------------------------------------------
# Home Directory Management
# -----------------------------------------------------------------------------


class TestHomeDirectoryManagement:
    """Test home directory creation and status file generation."""

    def test_ensure_home_directory_creates_structure(
        self, agent_service: AgentService, temp_data_dir: Path
    ):
        """Should create home directory with initial files."""
        agents_root = temp_data_dir / "agents"

        home = agent_service.ensure_home_directory(AgentName("Ember"), agents_root)

        assert home.exists()
        assert (home / "journal.md").exists()
        assert (home / "notes.md").exists()
        assert (home / "discoveries.md").exists()

    def test_ensure_home_directory_initial_content(
        self, agent_service: AgentService, temp_data_dir: Path
    ):
        """Should create files with light headers."""
        agents_root = temp_data_dir / "agents"

        home = agent_service.ensure_home_directory(AgentName("Ember"), agents_root)

        assert (home / "journal.md").read_text() == "# Journal\n"
        assert (home / "notes.md").read_text() == "# Notes\n"
        assert (home / "discoveries.md").read_text() == "# Discoveries\n"

    def test_ensure_home_directory_does_not_overwrite(
        self, agent_service: AgentService, temp_data_dir: Path
    ):
        """Should not overwrite existing files."""
        agents_root = temp_data_dir / "agents"
        home = agents_root / "Ember"
        home.mkdir(parents=True)

        # Create existing file with custom content
        (home / "journal.md").write_text("My precious notes!")

        agent_service.ensure_home_directory(AgentName("Ember"), agents_root)

        # Should preserve existing content
        assert (home / "journal.md").read_text() == "My precious notes!"

    def test_generate_status_file(
        self,
        agent_service: AgentService,
        sample_agent: Agent,
        temp_data_dir: Path,
    ):
        """Should generate status file with position, time, weather, inventory."""
        from storage.repositories.world import WorldState
        from core.terrain import Weather

        agents_root = temp_data_dir / "agents"
        agent_service.ensure_home_directory(AgentName("Ember"), agents_root)

        world_state = WorldState(
            current_tick=42, weather=Weather.RAINY, width=100, height=100
        )

        agent_with_inv = sample_agent.add_resource("wood", 10).add_resource("stone", 5)

        agent_service.generate_status_file(agent_with_inv, agents_root, world_state)

        status_path = agents_root / "Ember" / ".status"
        assert status_path.exists()

        content = status_path.read_text()
        assert "x: 10" in content
        assert "y: 10" in content
        assert "Tick: 42" in content
        assert "Weather: rainy" in content
        assert "wood: 10" in content
        assert "stone: 5" in content


# -----------------------------------------------------------------------------
# Initialization / Bootstrap
# -----------------------------------------------------------------------------


class TestInitialization:
    """Test agent initialization."""

    async def test_initialize_agent(
        self,
        agent_service: AgentService,
        sample_agent: Agent,
        temp_data_dir: Path,
    ):
        """Should save agent and create home directory."""
        agents_root = temp_data_dir / "agents"

        result = await agent_service.initialize_agent(sample_agent, agents_root)

        # Agent should be saved
        retrieved = await agent_service.get_agent(AgentName("Ember"))
        assert retrieved is not None

        # Home directory should exist
        home = agents_root / "Ember"
        assert home.exists()
        assert (home / "journal.md").exists()

    async def test_initialize_agents_bulk(
        self,
        agent_service: AgentService,
        sample_agent: Agent,
        sample_agent_sage: Agent,
        temp_data_dir: Path,
    ):
        """Should initialize multiple agents."""
        agents_root = temp_data_dir / "agents"

        results = await agent_service.initialize_agents(
            [sample_agent, sample_agent_sage], agents_root
        )

        assert len(results) == 2

        # Both should be saved
        agents = await agent_service.get_all_agents()
        assert len(agents) == 2

        # Both home directories should exist
        assert (agents_root / "Ember").exists()
        assert (agents_root / "Sage").exists()
