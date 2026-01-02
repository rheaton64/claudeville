"""Tests for Agent, Journey, and Inventory models."""

import pytest

from hearth.core import (
    Agent,
    AgentModel,
    Inventory,
    InventoryStack,
    Journey,
    JourneyDestination,
    Item,
    Position,
    AgentName,
    LandmarkName,
    ObjectId,
)


class TestJourneyDestination:
    """Tests for JourneyDestination model."""

    def test_to_position(self):
        """Create destination targeting coordinates."""
        dest = JourneyDestination.to_position(Position(10, 20))

        assert dest.position == Position(10, 20)
        assert dest.landmark is None
        assert dest.is_resolved()

    def test_to_landmark(self):
        """Create destination targeting named landmark."""
        dest = JourneyDestination.to_landmark(LandmarkName("Crystal Cave"))

        assert dest.position is None
        assert dest.landmark == "Crystal Cave"
        assert not dest.is_resolved()


class TestJourney:
    """Tests for Journey model."""

    def test_create_journey(self):
        """Create a journey with path."""
        path = (Position(0, 0), Position(0, 1), Position(0, 2))
        dest = JourneyDestination.to_position(Position(0, 2))
        journey = Journey.create(dest, path)

        assert journey.destination == dest
        assert journey.path == path
        assert journey.progress == 0

    def test_current_position(self):
        """Get current position along path."""
        path = (Position(0, 0), Position(0, 1), Position(0, 2))
        dest = JourneyDestination.to_position(Position(0, 2))
        journey = Journey.create(dest, path)

        assert journey.current_position == Position(0, 0)

    def test_next_position(self):
        """Get next position along path."""
        path = (Position(0, 0), Position(0, 1), Position(0, 2))
        dest = JourneyDestination.to_position(Position(0, 2))
        journey = Journey.create(dest, path)

        assert journey.next_position == Position(0, 1)

    def test_is_complete(self):
        """Journey completion check."""
        path = (Position(0, 0), Position(0, 1))
        dest = JourneyDestination.to_position(Position(0, 1))
        journey = Journey.create(dest, path)

        assert not journey.is_complete
        journey = journey.advance()
        assert journey.is_complete

    def test_remaining_steps(self):
        """Count remaining steps."""
        path = (Position(0, 0), Position(0, 1), Position(0, 2))
        dest = JourneyDestination.to_position(Position(0, 2))
        journey = Journey.create(dest, path)

        assert journey.remaining_steps == 2
        journey = journey.advance()
        assert journey.remaining_steps == 1
        journey = journey.advance()
        assert journey.remaining_steps == 0

    def test_advance(self):
        """Advance journey by one step."""
        path = (Position(0, 0), Position(0, 1), Position(0, 2))
        dest = JourneyDestination.to_position(Position(0, 2))
        journey = Journey.create(dest, path)

        advanced = journey.advance()
        assert journey.progress == 0  # Original unchanged
        assert advanced.progress == 1
        assert advanced.current_position == Position(0, 1)


class TestInventoryStack:
    """Tests for InventoryStack model."""

    def test_create_stack(self):
        """Create a resource stack."""
        stack = InventoryStack(item_type="wood", quantity=10)

        assert stack.item_type == "wood"
        assert stack.quantity == 10

    def test_add_to_stack(self):
        """Add quantity to stack."""
        stack = InventoryStack(item_type="wood", quantity=10)
        new_stack = stack.add(5)

        assert stack.quantity == 10  # Original unchanged
        assert new_stack.quantity == 15

    def test_remove_from_stack(self):
        """Remove quantity from stack."""
        stack = InventoryStack(item_type="wood", quantity=10)
        new_stack = stack.remove(3)

        assert stack.quantity == 10
        assert new_stack.quantity == 7

    def test_remove_too_much_raises(self):
        """Cannot remove more than available."""
        stack = InventoryStack(item_type="wood", quantity=5)

        with pytest.raises(ValueError):
            stack.remove(10)


class TestInventory:
    """Tests for Inventory model."""

    def test_empty_inventory(self):
        """Create empty inventory."""
        inv = Inventory()

        assert inv.stacks == ()
        assert inv.items == ()
        assert inv.is_empty

    def test_add_resource(self):
        """Add stackable resource."""
        inv = Inventory()
        new_inv = inv.add_resource("wood", 5)

        assert inv.is_empty
        assert new_inv.get_resource_quantity("wood") == 5

    def test_add_resource_stacks(self):
        """Adding same resource increases stack."""
        inv = Inventory()
        inv = inv.add_resource("wood", 5)
        inv = inv.add_resource("wood", 3)

        assert inv.get_resource_quantity("wood") == 8

    def test_has_resource(self):
        """Check resource availability."""
        inv = Inventory().add_resource("wood", 5)

        assert inv.has_resource("wood", 5)
        assert inv.has_resource("wood", 1)
        assert not inv.has_resource("wood", 10)
        assert not inv.has_resource("stone", 1)

    def test_remove_resource(self):
        """Remove stackable resource."""
        inv = Inventory().add_resource("wood", 10)
        new_inv = inv.remove_resource("wood", 3)

        assert inv.get_resource_quantity("wood") == 10
        assert new_inv.get_resource_quantity("wood") == 7

    def test_remove_all_resource(self):
        """Removing all of a resource removes the stack."""
        inv = Inventory().add_resource("wood", 5)
        new_inv = inv.remove_resource("wood", 5)

        assert new_inv.get_resource_quantity("wood") == 0
        assert len(new_inv.stacks) == 0

    def test_remove_nonexistent_raises(self):
        """Cannot remove resource not in inventory."""
        inv = Inventory()

        with pytest.raises(ValueError):
            inv.remove_resource("wood", 1)

    def test_remove_too_much_raises(self):
        """Cannot remove more than available."""
        inv = Inventory().add_resource("wood", 5)

        with pytest.raises(ValueError):
            inv.remove_resource("wood", 10)

    def test_add_unique_item(self):
        """Add unique item to inventory."""
        inv = Inventory()
        item = Item.unique("crystal", ("blue", "glowing"))
        new_inv = inv.add_item(item)

        assert inv.items == ()
        assert len(new_inv.items) == 1
        assert new_inv.has_item(item.id)

    def test_add_stackable_item_goes_to_stacks(self):
        """Adding stackable item via add_item goes to stacks."""
        inv = Inventory()
        item = Item.stackable("wood", 5)
        new_inv = inv.add_item(item)

        assert len(new_inv.stacks) == 1
        assert new_inv.get_resource_quantity("wood") == 5

    def test_get_item(self):
        """Get unique item by ID."""
        inv = Inventory()
        item = Item.unique("crystal")
        inv = inv.add_item(item)

        found = inv.get_item(item.id)
        assert found == item

    def test_get_item_not_found(self):
        """Get nonexistent item returns None."""
        inv = Inventory()

        assert inv.get_item(ObjectId("nonexistent")) is None

    def test_remove_item(self):
        """Remove unique item from inventory."""
        inv = Inventory()
        item = Item.unique("crystal")
        inv = inv.add_item(item)
        new_inv = inv.remove_item(item.id)

        assert inv.has_item(item.id)
        assert not new_inv.has_item(item.id)

    def test_remove_nonexistent_item_raises(self):
        """Cannot remove item not in inventory."""
        inv = Inventory()

        with pytest.raises(ValueError):
            inv.remove_item(ObjectId("nonexistent"))

    def test_all_items(self):
        """Get all items as list."""
        inv = Inventory()
        inv = inv.add_resource("wood", 5)
        inv = inv.add_resource("stone", 3)
        item = Item.unique("crystal")
        inv = inv.add_item(item)

        all_items = inv.all_items()
        assert len(all_items) == 3

        types = {i.item_type for i in all_items}
        assert types == {"wood", "stone", "crystal"}


class TestAgent:
    """Tests for Agent model."""

    @pytest.fixture
    def agent(self):
        """Create a test agent."""
        return Agent(
            name=AgentName("Ember"),
            model=AgentModel(id="sonnet", display_name="Sonnet"),
            position=Position(10, 10),
        )

    def test_create_agent(self, agent):
        """Can create an agent."""
        assert agent.name == "Ember"
        assert agent.position == Position(10, 10)
        assert agent.inventory.is_empty
        assert not agent.is_sleeping
        assert agent.journey is None

    def test_agent_is_frozen(self, agent):
        """Agent is immutable."""
        with pytest.raises(Exception):
            agent.position = Position(0, 0)

    def test_with_position(self, agent):
        """Move agent to new position."""
        new_agent = agent.with_position(Position(20, 20))

        assert agent.position == Position(10, 10)
        assert new_agent.position == Position(20, 20)

    def test_is_journeying(self, agent):
        """Check if agent is on a journey."""
        assert not agent.is_journeying

        path = (Position(10, 10), Position(10, 11))
        dest = JourneyDestination.to_position(Position(10, 11))
        journey = Journey.create(dest, path)
        traveling = agent.with_journey(journey)

        assert traveling.is_journeying

        # Completed journey
        completed = traveling.with_journey(journey.advance())
        assert not completed.is_journeying

    def test_with_sleeping(self, agent):
        """Set sleep state."""
        sleeping = agent.with_sleeping(True)

        assert not agent.is_sleeping
        assert sleeping.is_sleeping

    def test_with_known_agent(self, agent):
        """Add known agent."""
        new_agent = agent.with_known_agent(AgentName("Sage"))

        assert "Sage" not in agent.known_agents
        assert "Sage" in new_agent.known_agents

    def test_with_known_agent_idempotent(self, agent):
        """Adding already known agent is no-op."""
        agent = agent.with_known_agent(AgentName("Sage"))
        same_agent = agent.with_known_agent(AgentName("Sage"))

        assert same_agent is agent

    def test_knows(self, agent):
        """Check if agent knows another."""
        assert not agent.knows(AgentName("Sage"))

        agent = agent.with_known_agent(AgentName("Sage"))
        assert agent.knows(AgentName("Sage"))

    def test_add_resource(self, agent):
        """Add resource to inventory."""
        new_agent = agent.add_resource("wood", 5)

        assert agent.inventory.is_empty
        assert new_agent.inventory.get_resource_quantity("wood") == 5

    def test_remove_resource(self, agent):
        """Remove resource from inventory."""
        agent = agent.add_resource("wood", 10)
        new_agent = agent.remove_resource("wood", 3)

        assert agent.inventory.get_resource_quantity("wood") == 10
        assert new_agent.inventory.get_resource_quantity("wood") == 7

    def test_add_item(self, agent):
        """Add unique item to inventory."""
        item = Item.unique("crystal")
        new_agent = agent.add_item(item)

        assert not agent.inventory.has_item(item.id)
        assert new_agent.inventory.has_item(item.id)

    def test_remove_item(self, agent):
        """Remove unique item from inventory."""
        item = Item.unique("crystal")
        agent = agent.add_item(item)
        new_agent = agent.remove_item(item.id)

        assert agent.inventory.has_item(item.id)
        assert not new_agent.inventory.has_item(item.id)
