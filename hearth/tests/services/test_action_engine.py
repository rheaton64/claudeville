"""Tests for ActionEngine."""

import pytest

from core.types import Position, Direction, AgentName, ObjectId
from core.terrain import Terrain
from core.world import Cell
from core.agent import Agent, AgentModel, Inventory
from core.objects import Sign, PlacedItem, Item, generate_object_id
from core.actions import (
    WalkAction,
    ApproachAction,
    JourneyAction,
    LookAction,
    ExamineAction,
    SenseOthersAction,
    TakeAction,
    DropAction,
    GiveAction,
    GatherAction,
    CombineAction,
    WorkAction,
    ApplyAction,
    BuildShelterAction,
    PlaceWallAction,
    PlaceDoorAction,
    PlaceItemAction,
    RemoveWallAction,
    WriteSignAction,
    ReadSignAction,
    NamePlaceAction,
    SpeakAction,
    InviteAction,
    AcceptInviteAction,
    DeclineInviteAction,
    JoinConversationAction,
    LeaveConversationAction,
    SleepAction,
    ActionResult,
)

from services import WorldService, AgentService, ActionEngine, CraftingService
from storage import Storage


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def test_agent() -> Agent:
    """Create a test agent at position (50, 50)."""
    return Agent(
        name=AgentName("TestAgent"),
        model=AgentModel(id="test-model", display_name="Test Model"),
        personality="A test agent",
        position=Position(50, 50),
    )


@pytest.fixture
def test_agent_with_wood() -> Agent:
    """Create a test agent with wood in inventory."""
    return Agent(
        name=AgentName("TestAgent"),
        model=AgentModel(id="test-model", display_name="Test Model"),
        personality="A test agent",
        position=Position(50, 50),
        inventory=Inventory().add_resource("wood", 10),
    )


@pytest.fixture
def other_agent() -> Agent:
    """Create another agent nearby."""
    return Agent(
        name=AgentName("OtherAgent"),
        model=AgentModel(id="test-model", display_name="Test Model"),
        personality="Another test agent",
        position=Position(51, 50),
    )


@pytest.fixture
async def action_engine(
    storage: Storage, world_service: WorldService, agent_service: AgentService
) -> ActionEngine:
    """Create ActionEngine with all dependencies."""
    return ActionEngine(storage, world_service, agent_service)


@pytest.fixture
async def action_engine_with_crafting(
    storage: Storage, world_service: WorldService, agent_service: AgentService
) -> ActionEngine:
    """Create ActionEngine with CraftingService enabled."""
    crafting_service = CraftingService()
    return ActionEngine(storage, world_service, agent_service, crafting_service)


@pytest.fixture
async def saved_agent(agent_service: AgentService, test_agent: Agent) -> Agent:
    """Save a test agent and return it."""
    await agent_service.save_agent(test_agent)
    return test_agent


@pytest.fixture
async def saved_agent_with_wood(
    agent_service: AgentService, test_agent_with_wood: Agent
) -> Agent:
    """Save a test agent with wood and return it."""
    await agent_service.save_agent(test_agent_with_wood)
    return test_agent_with_wood


@pytest.fixture
async def saved_other_agent(agent_service: AgentService, other_agent: Agent) -> Agent:
    """Save another agent and return it."""
    await agent_service.save_agent(other_agent)
    return other_agent


# -----------------------------------------------------------------------------
# Movement Action Tests
# -----------------------------------------------------------------------------


class TestWalkAction:
    """Test walk action execution."""

    async def test_walk_success(
        self, action_engine: ActionEngine, saved_agent: Agent
    ):
        """Should move agent one cell in direction."""
        action = WalkAction(direction=Direction.NORTH)
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert result.success
        assert result.message == "Moved north."
        assert len(result.events) == 1
        assert result.events[0].to_position == Position(50, 51)
        assert result.data["direction"] == "north"
        assert result.data["new_position"] == Position(50, 51)

    async def test_walk_blocked_by_terrain(
        self,
        action_engine: ActionEngine,
        saved_agent: Agent,
        world_service: WorldService,
    ):
        """Should fail when blocked by impassable terrain."""
        # Put water to the north
        cell = Cell(position=Position(50, 51), terrain=Terrain.WATER)
        await world_service._world_repo.set_cell(cell)

        action = WalkAction(direction=Direction.NORTH)
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert not result.success
        assert "blocked" in result.message.lower()

    async def test_walk_blocked_by_wall(
        self,
        action_engine: ActionEngine,
        saved_agent: Agent,
        world_service: WorldService,
    ):
        """Should fail when blocked by wall."""
        await world_service.place_wall(Position(50, 50), Direction.NORTH)

        action = WalkAction(direction=Direction.NORTH)
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert not result.success
        assert "blocked" in result.message.lower()

    async def test_walk_through_door(
        self,
        action_engine: ActionEngine,
        saved_agent: Agent,
        world_service: WorldService,
    ):
        """Should allow walking through doors in walls."""
        await world_service.place_wall(Position(50, 50), Direction.NORTH)
        await world_service.place_door(Position(50, 50), Direction.NORTH)

        action = WalkAction(direction=Direction.NORTH)
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert result.success


class TestApproachAction:
    """Test approach action execution."""

    async def test_approach_agent(
        self,
        action_engine: ActionEngine,
        saved_agent: Agent,
        saved_other_agent: Agent,
        agent_service: AgentService,
    ):
        """Should move toward another agent."""
        # Move other agent further away
        await agent_service.update_position(
            saved_other_agent.name, Position(52, 50)
        )

        action = ApproachAction(target="OtherAgent")
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert result.success
        assert "OtherAgent" in result.message

    async def test_approach_nonexistent(
        self, action_engine: ActionEngine, saved_agent: Agent
    ):
        """Should fail when target doesn't exist."""
        action = ApproachAction(target="Nobody")
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert not result.success
        assert "Cannot find" in result.message


class TestJourneyAction:
    """Test journey action execution."""

    async def test_journey_to_position(
        self, action_engine: ActionEngine, saved_agent: Agent
    ):
        """Should start journey to a position."""
        action = JourneyAction(destination=Position(60, 60))
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert result.success
        assert "journey" in result.message.lower()
        assert len(result.events) == 1
        assert result.data["path_length"] > 0

    async def test_journey_to_named_place(
        self,
        action_engine: ActionEngine,
        saved_agent: Agent,
        world_service: WorldService,
    ):
        """Should start journey to a named landmark."""
        await world_service.name_place("Test Place", Position(70, 70))

        action = JourneyAction(destination="Test Place")
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert result.success

    async def test_journey_to_unknown_place(
        self, action_engine: ActionEngine, saved_agent: Agent
    ):
        """Should fail when landmark doesn't exist."""
        action = JourneyAction(destination="Nowhere")
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert not result.success
        assert "Unknown destination" in result.message


# -----------------------------------------------------------------------------
# Perception Action Tests
# -----------------------------------------------------------------------------


class TestLookAction:
    """Test look action execution."""

    async def test_look_returns_data(
        self, action_engine: ActionEngine, saved_agent: Agent
    ):
        """Should return information about surroundings."""
        action = LookAction()
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert result.success
        assert "cells" in result.data
        assert "objects" in result.data
        assert "agents" in result.data
        assert result.data["center"] == Position(50, 50)


class TestExamineAction:
    """Test examine action execution."""

    async def test_examine_down(
        self, action_engine: ActionEngine, saved_agent: Agent
    ):
        """Should return info about current position when looking down."""
        action = ExamineAction(direction="down")
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert result.success
        assert "terrain" in result.data

    async def test_examine_object_down(
        self,
        action_engine: ActionEngine,
        saved_agent: Agent,
        world_service: WorldService,
    ):
        """Should return info about an object when looking down at current position."""
        sign = Sign(
            id=ObjectId("test-sign"),
            position=Position(50, 50),  # Same as agent position
            text="Hello",
            created_tick=0,
        )
        await world_service.place_object(sign)

        action = ExamineAction(direction="down")
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert result.success
        assert "objects" in result.data
        assert result.data["objects"][0]["text"] == "Hello"

    async def test_examine_north(
        self,
        action_engine: ActionEngine,
        saved_agent: Agent,
        world_service: WorldService,
    ):
        """Should examine cell to the north."""
        sign = Sign(
            id=ObjectId("north-sign"),
            position=Position(50, 51),  # One cell north of agent at (50, 50)
            text="North sign",
            created_tick=0,
        )
        await world_service.place_object(sign)

        action = ExamineAction(direction="north")
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert result.success
        assert "objects" in result.data
        assert result.data["objects"][0]["text"] == "North sign"


class TestSenseOthersAction:
    """Test sense_others action execution."""

    async def test_sense_others(
        self,
        action_engine: ActionEngine,
        saved_agent: Agent,
        saved_other_agent: Agent,
        agent_service: AgentService,
    ):
        """Should return direction/distance to known agents."""
        # Record meeting
        await agent_service.record_meeting(
            saved_agent.name, saved_other_agent.name
        )

        action = SenseOthersAction()
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert result.success
        assert "sensed" in result.data


# -----------------------------------------------------------------------------
# Interaction Action Tests
# -----------------------------------------------------------------------------


class TestGatherAction:
    """Test gather action execution."""

    async def test_gather_from_forest(
        self,
        action_engine: ActionEngine,
        saved_agent: Agent,
        world_service: WorldService,
        agent_service: AgentService,
    ):
        """Should gather wood from forest terrain."""
        cell = Cell(position=Position(50, 50), terrain=Terrain.FOREST)
        await world_service._world_repo.set_cell(cell)

        action = GatherAction()
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert result.success
        assert result.data["resource"] == "wood"
        assert len(result.events) == 1

        # Verify inventory updated
        updated = await agent_service.get_agent(saved_agent.name)
        assert updated.inventory.has_resource("wood", 1)

    async def test_gather_from_grass_succeeds(
        self, action_engine: ActionEngine, saved_agent: Agent, agent_service: AgentService
    ):
        """Should gather grass from grass terrain (for fiber crafting)."""
        action = GatherAction()
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert result.success
        assert "Gathered grass" in result.message

        # Verify inventory updated
        updated = await agent_service.get_agent(saved_agent.name)
        assert updated.inventory.has_resource("grass", 1)

    async def test_gather_wrong_resource_fails(
        self, action_engine: ActionEngine, saved_agent: Agent
    ):
        """Should fail when requesting resource not available at terrain."""
        # Default terrain is grass, which provides "grass" not "wood"
        action = GatherAction(resource_type="wood")
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert not result.success
        assert "Cannot gather wood" in result.message

    async def test_gather_specific_resource(
        self,
        action_engine: ActionEngine,
        saved_agent: Agent,
        world_service: WorldService,
    ):
        """Should gather specific resource if available."""
        cell = Cell(position=Position(50, 50), terrain=Terrain.FOREST)
        await world_service._world_repo.set_cell(cell)

        action = GatherAction(resource_type="wood")
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert result.success

    async def test_gather_wrong_resource_fails(
        self,
        action_engine: ActionEngine,
        saved_agent: Agent,
        world_service: WorldService,
    ):
        """Should fail when requesting unavailable resource."""
        cell = Cell(position=Position(50, 50), terrain=Terrain.FOREST)
        await world_service._world_repo.set_cell(cell)

        action = GatherAction(resource_type="stone")
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert not result.success


class TestTakeAction:
    """Test take action execution."""

    async def test_take_placed_item_down(
        self,
        action_engine: ActionEngine,
        saved_agent: Agent,
        world_service: WorldService,
        agent_service: AgentService,
    ):
        """Should pick up a placed item at current position."""
        placed = PlacedItem(
            id=ObjectId("test-item"),
            position=Position(50, 50),  # Same as agent position
            item_type="bowl",
            created_tick=0,
        )
        await world_service.place_object(placed)

        action = TakeAction(direction="down")
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert result.success
        assert len(result.events) == 1

        # Item should be in inventory
        updated = await agent_service.get_agent(saved_agent.name)
        assert updated.inventory.get_item(ObjectId("test-item")) is not None

    async def test_take_from_north(
        self,
        action_engine: ActionEngine,
        saved_agent: Agent,
        world_service: WorldService,
        agent_service: AgentService,
    ):
        """Should pick up a placed item to the north."""
        placed = PlacedItem(
            id=ObjectId("north-item"),
            position=Position(50, 51),  # One cell north of agent at (50, 50)
            item_type="bowl",
            created_tick=0,
        )
        await world_service.place_object(placed)

        action = TakeAction(direction="north")
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert result.success
        assert len(result.events) == 1

        # Item should be in inventory
        updated = await agent_service.get_agent(saved_agent.name)
        assert updated.inventory.get_item(ObjectId("north-item")) is not None

    async def test_take_nothing_at_direction(
        self, action_engine: ActionEngine, saved_agent: Agent
    ):
        """Should fail when nothing to take at direction."""
        action = TakeAction(direction="east")
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert not result.success


class TestDropAction:
    """Test drop action execution."""

    async def test_drop_resource(
        self,
        action_engine: ActionEngine,
        saved_agent_with_wood: Agent,
        agent_service: AgentService,
        world_service: WorldService,
    ):
        """Should drop stackable resource."""
        action = DropAction(item_type="wood", quantity=1)
        result = await action_engine.execute(saved_agent_with_wood, action, tick=1)

        assert result.success
        assert len(result.events) == 1

        # Check inventory decreased
        updated = await agent_service.get_agent(saved_agent_with_wood.name)
        assert updated.inventory.get_resource_quantity("wood") == 9

        # Check item placed in world
        objects = await world_service.get_objects_at(Position(50, 50))
        assert len(objects) == 1

    async def test_drop_insufficient(
        self, action_engine: ActionEngine, saved_agent: Agent
    ):
        """Should fail when not enough resources."""
        action = DropAction(item_type="wood", quantity=1)
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert not result.success


class TestGiveAction:
    """Test give action execution."""

    async def test_give_resource(
        self,
        action_engine: ActionEngine,
        saved_agent_with_wood: Agent,
        saved_other_agent: Agent,
        agent_service: AgentService,
    ):
        """Should give resource to nearby agent."""
        action = GiveAction(
            recipient=AgentName("OtherAgent"),
            item_type="wood",
            quantity=5,
        )
        result = await action_engine.execute(saved_agent_with_wood, action, tick=1)

        assert result.success
        assert len(result.events) == 1

        # Check inventories
        giver = await agent_service.get_agent(saved_agent_with_wood.name)
        receiver = await agent_service.get_agent(saved_other_agent.name)

        assert giver.inventory.get_resource_quantity("wood") == 5
        assert receiver.inventory.get_resource_quantity("wood") == 5

    async def test_give_to_far_agent(
        self,
        action_engine: ActionEngine,
        saved_agent_with_wood: Agent,
        saved_other_agent: Agent,
        agent_service: AgentService,
    ):
        """Should fail when recipient is too far."""
        # Move other agent far away
        await agent_service.update_position(
            saved_other_agent.name, Position(60, 60)
        )

        action = GiveAction(
            recipient=AgentName("OtherAgent"),
            item_type="wood",
            quantity=5,
        )
        result = await action_engine.execute(saved_agent_with_wood, action, tick=1)

        assert not result.success
        assert "far" in result.message.lower()


# -----------------------------------------------------------------------------
# Building Action Tests
# -----------------------------------------------------------------------------


class TestPlaceWallAction:
    """Test place_wall action execution."""

    async def test_place_wall_success(
        self,
        action_engine: ActionEngine,
        saved_agent_with_wood: Agent,
        world_service: WorldService,
    ):
        """Should place wall when have materials."""
        action = PlaceWallAction(direction=Direction.NORTH)
        result = await action_engine.execute(saved_agent_with_wood, action, tick=1)

        assert result.success
        assert len(result.events) == 1

        # Check wall exists
        cell = await world_service.get_cell(Position(50, 50))
        assert Direction.NORTH in cell.walls

    async def test_place_wall_no_materials(
        self, action_engine: ActionEngine, saved_agent: Agent
    ):
        """Should fail when no materials."""
        action = PlaceWallAction(direction=Direction.NORTH)
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert not result.success
        assert "wood" in result.message.lower()


class TestPlaceDoorAction:
    """Test place_door action execution."""

    async def test_place_door_success(
        self,
        action_engine: ActionEngine,
        saved_agent: Agent,
        world_service: WorldService,
    ):
        """Should place door in existing wall."""
        await world_service.place_wall(Position(50, 50), Direction.NORTH)

        action = PlaceDoorAction(direction=Direction.NORTH)
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert result.success

        # Check door exists
        cell = await world_service.get_cell(Position(50, 50))
        assert Direction.NORTH in cell.doors

    async def test_place_door_no_wall(
        self, action_engine: ActionEngine, saved_agent: Agent
    ):
        """Should fail when no wall exists."""
        action = PlaceDoorAction(direction=Direction.NORTH)
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert not result.success
        assert "No wall" in result.message


class TestRemoveWallAction:
    """Test remove_wall action execution."""

    async def test_remove_wall_success(
        self,
        action_engine: ActionEngine,
        saved_agent: Agent,
        world_service: WorldService,
    ):
        """Should remove existing wall."""
        await world_service.place_wall(Position(50, 50), Direction.NORTH)

        action = RemoveWallAction(direction=Direction.NORTH)
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert result.success

        # Check wall removed
        cell = await world_service.get_cell(Position(50, 50))
        assert Direction.NORTH not in cell.walls

    async def test_remove_wall_none_exists(
        self, action_engine: ActionEngine, saved_agent: Agent
    ):
        """Should fail when no wall exists."""
        action = RemoveWallAction(direction=Direction.NORTH)
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert not result.success


class TestBuildShelterAction:
    """Test build_shelter action execution."""

    async def test_build_shelter_success(
        self,
        action_engine: ActionEngine,
        saved_agent_with_wood: Agent,
        world_service: WorldService,
    ):
        """Should build shelter with walls and door."""
        action = BuildShelterAction()
        result = await action_engine.execute(saved_agent_with_wood, action, tick=1)

        assert result.success
        assert len(result.events) == 5  # 4 walls + 1 door

        # Check walls exist on all sides
        cell = await world_service.get_cell(Position(50, 50))
        assert len(cell.walls) == 4
        assert Direction.SOUTH in cell.doors

    async def test_build_shelter_insufficient_materials(
        self, action_engine: ActionEngine, saved_agent: Agent
    ):
        """Should fail when not enough materials."""
        action = BuildShelterAction()
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert not result.success
        assert "wood" in result.message.lower()


# -----------------------------------------------------------------------------
# Expression Action Tests
# -----------------------------------------------------------------------------


class TestWriteSignAction:
    """Test write_sign action execution."""

    async def test_write_sign_success(
        self,
        action_engine: ActionEngine,
        saved_agent: Agent,
        world_service: WorldService,
    ):
        """Should create a sign at agent position."""
        action = WriteSignAction(text="Hello World")
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert result.success
        assert len(result.events) == 1

        # Check sign exists
        objects = await world_service.get_objects_at(Position(50, 50))
        assert len(objects) == 1
        assert isinstance(objects[0], Sign)
        assert objects[0].text == "Hello World"


class TestReadSignAction:
    """Test read_sign action execution."""

    async def test_read_sign_down(
        self,
        action_engine: ActionEngine,
        saved_agent: Agent,
        world_service: WorldService,
    ):
        """Should read sign content at current position."""
        sign = Sign(
            id=ObjectId("test-sign"),
            position=Position(50, 50),  # Same as agent position
            text="Test message",
            created_by=AgentName("Someone"),
            created_tick=0,
        )
        await world_service.place_object(sign)

        action = ReadSignAction(direction="down")
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert result.success
        assert result.data["text"] == "Test message"

    async def test_read_sign_north(
        self,
        action_engine: ActionEngine,
        saved_agent: Agent,
        world_service: WorldService,
    ):
        """Should read sign content to the north."""
        sign = Sign(
            id=ObjectId("north-sign"),
            position=Position(50, 51),  # One cell north of agent at (50, 50)
            text="North message",
            created_by=AgentName("Someone"),
            created_tick=0,
        )
        await world_service.place_object(sign)

        action = ReadSignAction(direction="north")
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert result.success
        assert result.data["text"] == "North message"

    async def test_read_sign_no_sign_at_direction(
        self,
        action_engine: ActionEngine,
        saved_agent: Agent,
    ):
        """Should fail when no sign at direction."""
        action = ReadSignAction(direction="west")
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert not result.success


class TestNamePlaceAction:
    """Test name_place action execution."""

    async def test_name_place_success(
        self,
        action_engine: ActionEngine,
        saved_agent: Agent,
        world_service: WorldService,
    ):
        """Should name current location."""
        action = NamePlaceAction(name="My Spot")
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert result.success
        assert len(result.events) == 1

        # Verify name saved
        pos = await world_service.get_place_position("My Spot")
        assert pos == Position(50, 50)


# -----------------------------------------------------------------------------
# State Action Tests
# -----------------------------------------------------------------------------


class TestSleepAction:
    """Test sleep action execution."""

    async def test_sleep_success(
        self,
        action_engine: ActionEngine,
        saved_agent: Agent,
        agent_service: AgentService,
    ):
        """Should set agent to sleeping."""
        action = SleepAction()
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert result.success
        assert len(result.events) == 1

        # Verify agent is sleeping
        updated = await agent_service.get_agent(saved_agent.name)
        assert updated.is_sleeping


# -----------------------------------------------------------------------------
# Stub Action Tests
# -----------------------------------------------------------------------------


class TestSocialActionsWithoutService:
    """Test that social actions fail gracefully without ConversationService."""

    async def test_speak_without_service(
        self, action_engine: ActionEngine, saved_agent: Agent
    ):
        """Speak should fail when ConversationService not initialized."""
        action = SpeakAction(message="Hello")
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert not result.success
        assert "not initialized" in result.message

    async def test_invite_without_service(
        self, action_engine: ActionEngine, saved_agent: Agent
    ):
        """Invite should fail when ConversationService not initialized."""
        action = InviteAction(agent=AgentName("Someone"))
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert not result.success
        assert "not initialized" in result.message

    async def test_accept_invite_without_service(
        self, action_engine: ActionEngine, saved_agent: Agent
    ):
        """AcceptInvite should fail when ConversationService not initialized."""
        action = AcceptInviteAction()
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert not result.success
        assert "not initialized" in result.message

    async def test_decline_invite_without_service(
        self, action_engine: ActionEngine, saved_agent: Agent
    ):
        """DeclineInvite should fail when ConversationService not initialized."""
        action = DeclineInviteAction()
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert not result.success
        assert "not initialized" in result.message

    async def test_join_conversation_without_service(
        self, action_engine: ActionEngine, saved_agent: Agent
    ):
        """JoinConversation should fail when ConversationService not initialized."""
        action = JoinConversationAction(participant=AgentName("Someone"))
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert not result.success
        assert "not initialized" in result.message

    async def test_leave_conversation_without_service(
        self, action_engine: ActionEngine, saved_agent: Agent
    ):
        """LeaveConversation should fail when ConversationService not initialized."""
        action = LeaveConversationAction()
        result = await action_engine.execute(saved_agent, action, tick=1)

        assert not result.success
        assert "not initialized" in result.message


# -----------------------------------------------------------------------------
# ActionResult Tests
# -----------------------------------------------------------------------------


class TestActionResult:
    """Test ActionResult helper methods."""

    def test_ok_result(self):
        """Should create successful result."""
        result = ActionResult.ok("Success!", data={"key": "value"})

        assert result.success
        assert result.message == "Success!"
        assert result.events == ()
        assert result.data == {"key": "value"}

    def test_fail_result(self):
        """Should create failure result."""
        result = ActionResult.fail("Something went wrong")

        assert not result.success
        assert result.message == "Something went wrong"
        assert result.events == ()
        assert result.data is None

    def test_not_implemented_result(self):
        """Should create not implemented result."""
        result = ActionResult.not_implemented("test_action")

        assert not result.success
        assert "test_action" in result.message
        assert "not yet available" in result.message


# -----------------------------------------------------------------------------
# Crafting Action Tests
# -----------------------------------------------------------------------------


class TestCombineAction:
    """Test combine action for crafting."""

    async def test_combine_success(
        self, action_engine_with_crafting: ActionEngine, agent_service: AgentService
    ):
        """Should combine items into new item."""
        # Create agent with fiber
        agent = Agent(
            name=AgentName("CraftAgent"),
            model=AgentModel(id="test-model", display_name="Test"),
            position=Position(50, 50),
            inventory=Inventory().add_resource("fiber", 2),
        )
        await agent_service.save_agent(agent)

        action = CombineAction(items=("fiber", "fiber"))
        result = await action_engine_with_crafting.execute(agent, action, tick=1)

        assert result.success
        assert "rope" in result.message.lower()
        assert result.data["output"] == "rope"

        # Verify inventory updated
        updated = await agent_service.get_agent(agent.name)
        assert not updated.inventory.has_resource("fiber", 1)  # Consumed
        assert updated.inventory.has_resource("rope", 1)  # Created

    async def test_combine_missing_item(
        self, action_engine_with_crafting: ActionEngine, agent_service: AgentService
    ):
        """Should fail if agent doesn't have enough items."""
        agent = Agent(
            name=AgentName("CraftAgent"),
            model=AgentModel(id="test-model", display_name="Test"),
            position=Position(50, 50),
            inventory=Inventory().add_resource("fiber", 1),  # Only 1 fiber, need 2
        )
        await agent_service.save_agent(agent)

        action = CombineAction(items=("fiber", "fiber"))
        result = await action_engine_with_crafting.execute(agent, action, tick=1)

        assert not result.success
        assert "need at least 2" in result.message.lower()

    async def test_combine_unknown_recipe(
        self, action_engine_with_crafting: ActionEngine, agent_service: AgentService
    ):
        """Should fail with hint for unknown combination."""
        agent = Agent(
            name=AgentName("CraftAgent"),
            model=AgentModel(id="test-model", display_name="Test"),
            position=Position(50, 50),
            inventory=Inventory().add_resource("banana", 1).add_resource("pineapple", 1),
        )
        await agent_service.save_agent(agent)

        action = CombineAction(items=("banana", "pineapple"))
        result = await action_engine_with_crafting.execute(agent, action, tick=1)

        assert not result.success
        assert "don't combine" in result.message.lower()

    async def test_combine_without_crafting_service(
        self, action_engine: ActionEngine, agent_service: AgentService
    ):
        """Should fail if crafting service not available."""
        agent = Agent(
            name=AgentName("CraftAgent"),
            model=AgentModel(id="test-model", display_name="Test"),
            position=Position(50, 50),
            inventory=Inventory().add_resource("fiber", 2),
        )
        await agent_service.save_agent(agent)

        action = CombineAction(items=("fiber", "fiber"))
        result = await action_engine.execute(agent, action, tick=1)

        assert not result.success
        assert "not available" in result.message.lower()


class TestWorkAction:
    """Test work action for crafting."""

    async def test_work_success(
        self, action_engine_with_crafting: ActionEngine, agent_service: AgentService
    ):
        """Should work material with technique."""
        agent = Agent(
            name=AgentName("CraftAgent"),
            model=AgentModel(id="test-model", display_name="Test"),
            position=Position(50, 50),
            inventory=Inventory().add_resource("wood", 1),
        )
        await agent_service.save_agent(agent)

        action = WorkAction(material="wood", technique="split")
        result = await action_engine_with_crafting.execute(agent, action, tick=1)

        assert result.success
        assert "planks" in result.message.lower()
        assert result.data["output"] == "planks"
        assert result.data["quantity"] == 4  # Recipe gives 4 planks

        # Verify inventory updated
        updated = await agent_service.get_agent(agent.name)
        assert not updated.inventory.has_resource("wood", 1)  # Consumed
        assert updated.inventory.has_resource("planks", 4)  # Created

    async def test_work_wrong_technique(
        self, action_engine_with_crafting: ActionEngine, agent_service: AgentService
    ):
        """Should fail with wrong technique."""
        agent = Agent(
            name=AgentName("CraftAgent"),
            model=AgentModel(id="test-model", display_name="Test"),
            position=Position(50, 50),
            inventory=Inventory().add_resource("wood", 1),
        )
        await agent_service.save_agent(agent)

        action = WorkAction(material="wood", technique="smash")  # Wrong technique
        result = await action_engine_with_crafting.execute(agent, action, tick=1)

        assert not result.success
        assert "technique" in result.message.lower()

        # Inventory should be unchanged
        updated = await agent_service.get_agent(agent.name)
        assert updated.inventory.has_resource("wood", 1)

    async def test_work_creates_unique_item(
        self, action_engine_with_crafting: ActionEngine, agent_service: AgentService
    ):
        """Should create unique item with ID for non-stackable recipes."""
        agent = Agent(
            name=AgentName("CraftAgent"),
            model=AgentModel(id="test-model", display_name="Test"),
            position=Position(50, 50),
            inventory=Inventory().add_resource("wood", 1),
        )
        await agent_service.save_agent(agent)

        action = WorkAction(material="wood", technique="hollow")  # Creates wooden_bowl
        result = await action_engine_with_crafting.execute(agent, action, tick=1)

        assert result.success
        assert result.data["output"] == "wooden_bowl"

        # Verify unique item in inventory
        updated = await agent_service.get_agent(agent.name)
        assert len(updated.inventory.items) == 1
        bowl = updated.inventory.items[0]
        assert bowl.item_type == "wooden_bowl"
        assert bowl.is_unique
        assert bowl.id is not None


class TestApplyAction:
    """Test apply action for crafting."""

    async def test_apply_success(
        self, action_engine_with_crafting: ActionEngine, agent_service: AgentService
    ):
        """Should apply heat source to target."""
        # Create agent with heat source (campfire) and target
        campfire = Item.unique("campfire", properties=("light", "heat", "stationary"))
        agent = Agent(
            name=AgentName("CraftAgent"),
            model=AgentModel(id="test-model", display_name="Test"),
            position=Position(50, 50),
            inventory=Inventory().add_item(campfire),
        )
        # Add clay_vessel
        vessel = Item.unique("clay_vessel", properties=("fragile", "container"))
        agent = agent.add_item(vessel)
        await agent_service.save_agent(agent)

        action = ApplyAction(tool="campfire", target="clay_vessel")
        result = await action_engine_with_crafting.execute(agent, action, tick=1)

        assert result.success
        assert "fired_vessel" in result.message.lower()
        assert result.data["output"] == "fired_vessel"

        # Verify: heat source preserved, target consumed, output created
        updated = await agent_service.get_agent(agent.name)
        # Should still have campfire
        fire = [i for i in updated.inventory.items if i.item_type == "campfire"]
        assert len(fire) == 1
        # Should not have clay_vessel
        vessel = [i for i in updated.inventory.items if i.item_type == "clay_vessel"]
        assert len(vessel) == 0
        # Should have fired_vessel
        fired = [i for i in updated.inventory.items if i.item_type == "fired_vessel"]
        assert len(fired) == 1

    async def test_apply_non_tool_fails(
        self, action_engine_with_crafting: ActionEngine, agent_service: AgentService
    ):
        """Should fail if item doesn't have 'tool' or 'heat' property."""
        # Create agent with item that has neither tool nor heat property
        rock = Item.unique("rock", properties=("heavy",))  # Not a tool or heat source
        agent = Agent(
            name=AgentName("CraftAgent"),
            model=AgentModel(id="test-model", display_name="Test"),
            position=Position(50, 50),
            inventory=Inventory().add_item(rock).add_resource("wood", 1),
        )
        await agent_service.save_agent(agent)

        action = ApplyAction(tool="rock", target="wood")
        result = await action_engine_with_crafting.execute(agent, action, tick=1)

        assert not result.success
        assert "cannot be used this way" in result.message.lower()

    async def test_apply_unknown_combination(
        self, action_engine_with_crafting: ActionEngine, agent_service: AgentService
    ):
        """Should fail for unknown tool+target combination."""
        tool = Item.unique("stone_axe", properties=("tool", "sharp", "chopping"))
        agent = Agent(
            name=AgentName("CraftAgent"),
            model=AgentModel(id="test-model", display_name="Test"),
            position=Position(50, 50),
            inventory=Inventory().add_item(tool).add_resource("banana", 1),
        )
        await agent_service.save_agent(agent)

        action = ApplyAction(tool="stone_axe", target="banana")
        result = await action_engine_with_crafting.execute(agent, action, tick=1)

        assert not result.success
        assert "doesn't do anything" in result.message.lower()


class TestCraftingEvents:
    """Test that crafting generates proper events."""

    async def test_combine_generates_event(
        self, action_engine_with_crafting: ActionEngine, agent_service: AgentService
    ):
        """Combine should generate ItemCraftedEvent."""
        agent = Agent(
            name=AgentName("CraftAgent"),
            model=AgentModel(id="test-model", display_name="Test"),
            position=Position(50, 50),
            inventory=Inventory().add_resource("fiber", 2),
        )
        await agent_service.save_agent(agent)

        action = CombineAction(items=("fiber", "fiber"))
        result = await action_engine_with_crafting.execute(agent, action, tick=1)

        assert result.success
        assert len(result.events) == 1
        event = result.events[0]
        assert event.type == "item_crafted"
        assert event.agent == agent.name
        assert event.output == "rope"
        assert event.technique is None  # combine doesn't use technique

    async def test_work_generates_event(
        self, action_engine_with_crafting: ActionEngine, agent_service: AgentService
    ):
        """Work should generate ItemCraftedEvent with technique."""
        agent = Agent(
            name=AgentName("CraftAgent"),
            model=AgentModel(id="test-model", display_name="Test"),
            position=Position(50, 50),
            inventory=Inventory().add_resource("wood", 1),
        )
        await agent_service.save_agent(agent)

        action = WorkAction(material="wood", technique="split")
        result = await action_engine_with_crafting.execute(agent, action, tick=1)

        assert result.success
        assert len(result.events) == 1
        event = result.events[0]
        assert event.type == "item_crafted"
        assert event.technique == "split"
