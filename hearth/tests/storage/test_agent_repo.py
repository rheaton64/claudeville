"""Tests for AgentRepository."""

import pytest

from core.types import Position, Rect, AgentName, ObjectId
from core.agent import Agent, AgentModel, Inventory, Journey, JourneyDestination
from core.objects import Item

from storage import Storage


class TestAgentCRUD:
    """Test agent CRUD operations."""

    async def test_save_and_get_agent(self, storage: Storage):
        """Should store and retrieve agent."""
        agent = Agent(
            name=AgentName("Ember"),
            model=AgentModel(id="claude-sonnet", display_name="Sonnet"),
            personality="Creative and curious",
            position=Position(50, 50),
        )
        await storage.agents.save_agent(agent)

        retrieved = await storage.agents.get_agent(AgentName("Ember"))
        assert retrieved is not None
        assert retrieved.name == AgentName("Ember")
        assert retrieved.model.id == "claude-sonnet"
        assert retrieved.personality == "Creative and curious"
        assert retrieved.position == Position(50, 50)

    async def test_get_nonexistent_agent(self, storage: Storage):
        """Should return None for unknown agent."""
        agent = await storage.agents.get_agent(AgentName("Unknown"))
        assert agent is None

    async def test_get_all_agents(self, storage: Storage):
        """Should return all agents."""
        ember = Agent(
            name=AgentName("Ember"),
            model=AgentModel(id="claude-sonnet", display_name="Sonnet"),
            position=Position(10, 10),
        )
        sage = Agent(
            name=AgentName("Sage"),
            model=AgentModel(id="claude-opus", display_name="Opus"),
            position=Position(20, 20),
        )
        await storage.agents.save_agent(ember)
        await storage.agents.save_agent(sage)

        agents = await storage.agents.get_all_agents()
        assert len(agents) == 2
        names = {a.name for a in agents}
        assert AgentName("Ember") in names
        assert AgentName("Sage") in names

    async def test_update_agent(self, storage: Storage):
        """Should update existing agent."""
        agent = Agent(
            name=AgentName("Ember"),
            model=AgentModel(id="claude-sonnet", display_name="Sonnet"),
            position=Position(10, 10),
        )
        await storage.agents.save_agent(agent)

        # Update position
        updated = agent.with_position(Position(20, 20))
        await storage.agents.save_agent(updated)

        retrieved = await storage.agents.get_agent(AgentName("Ember"))
        assert retrieved.position == Position(20, 20)

    async def test_delete_agent(self, storage: Storage):
        """Should delete agent."""
        agent = Agent(
            name=AgentName("Ember"),
            model=AgentModel(id="claude-sonnet", display_name="Sonnet"),
            position=Position(10, 10),
        )
        await storage.agents.save_agent(agent)

        await storage.agents.delete_agent(AgentName("Ember"))

        retrieved = await storage.agents.get_agent(AgentName("Ember"))
        assert retrieved is None


class TestAgentPositionQueries:
    """Test agent position queries."""

    async def test_get_agents_in_rect(self, storage: Storage):
        """Should find agents in rectangle."""
        ember = Agent(
            name=AgentName("Ember"),
            model=AgentModel(id="claude-sonnet", display_name="Sonnet"),
            position=Position(5, 5),
        )
        sage = Agent(
            name=AgentName("Sage"),
            model=AgentModel(id="claude-opus", display_name="Opus"),
            position=Position(50, 50),  # Outside rect
        )
        await storage.agents.save_agent(ember)
        await storage.agents.save_agent(sage)

        rect = Rect(0, 0, 10, 10)
        agents = await storage.agents.get_agents_in_rect(rect)

        assert len(agents) == 1
        assert agents[0].name == AgentName("Ember")

    async def test_get_agent_at(self, storage: Storage):
        """Should find agent at exact position."""
        agent = Agent(
            name=AgentName("Ember"),
            model=AgentModel(id="claude-sonnet", display_name="Sonnet"),
            position=Position(25, 30),
        )
        await storage.agents.save_agent(agent)

        found = await storage.agents.get_agent_at(Position(25, 30))
        assert found is not None
        assert found.name == AgentName("Ember")

        not_found = await storage.agents.get_agent_at(Position(25, 31))
        assert not_found is None


class TestAgentInventory:
    """Test inventory operations."""

    async def test_save_agent_with_stacks(self, storage: Storage):
        """Should persist inventory stacks."""
        inventory = Inventory().add_resource("wood", 5).add_resource("stone", 3)
        agent = Agent(
            name=AgentName("Ember"),
            model=AgentModel(id="claude-sonnet", display_name="Sonnet"),
            position=Position(10, 10),
            inventory=inventory,
        )
        await storage.agents.save_agent(agent)

        retrieved = await storage.agents.get_agent(AgentName("Ember"))
        assert retrieved.inventory.get_resource_quantity("wood") == 5
        assert retrieved.inventory.get_resource_quantity("stone") == 3

    async def test_save_agent_with_unique_items(self, storage: Storage):
        """Should persist unique inventory items."""
        item = Item.unique("crystal_orb", ("glowing", "fragile"))
        inventory = Inventory(items=(item,))
        agent = Agent(
            name=AgentName("Ember"),
            model=AgentModel(id="claude-sonnet", display_name="Sonnet"),
            position=Position(10, 10),
            inventory=inventory,
        )
        await storage.agents.save_agent(agent)

        retrieved = await storage.agents.get_agent(AgentName("Ember"))
        assert len(retrieved.inventory.items) == 1
        assert retrieved.inventory.items[0].item_type == "crystal_orb"
        assert "glowing" in retrieved.inventory.items[0].properties

    async def test_update_inventory(self, storage: Storage):
        """Should update inventory correctly."""
        agent = Agent(
            name=AgentName("Ember"),
            model=AgentModel(id="claude-sonnet", display_name="Sonnet"),
            position=Position(10, 10),
            inventory=Inventory().add_resource("wood", 5),
        )
        await storage.agents.save_agent(agent)

        # Update inventory
        new_inventory = Inventory().add_resource("stone", 10)
        updated = agent.with_inventory(new_inventory)
        await storage.agents.save_agent(updated)

        retrieved = await storage.agents.get_agent(AgentName("Ember"))
        assert retrieved.inventory.get_resource_quantity("wood") == 0
        assert retrieved.inventory.get_resource_quantity("stone") == 10


class TestAgentJourney:
    """Test journey state persistence."""

    async def test_save_agent_with_journey(self, storage: Storage):
        """Should persist journey state."""
        journey = Journey(
            destination=JourneyDestination(position=Position(100, 100)),
            path=(Position(10, 10), Position(20, 20), Position(30, 30), Position(100, 100)),
            progress=1,
        )
        agent = Agent(
            name=AgentName("Ember"),
            model=AgentModel(id="claude-sonnet", display_name="Sonnet"),
            position=Position(20, 20),
            journey=journey,
        )
        await storage.agents.save_agent(agent)

        retrieved = await storage.agents.get_agent(AgentName("Ember"))
        assert retrieved.journey is not None
        assert retrieved.journey.destination.position == Position(100, 100)
        assert len(retrieved.journey.path) == 4
        assert retrieved.journey.progress == 1

    async def test_save_agent_without_journey(self, storage: Storage):
        """Should handle agent with no journey."""
        agent = Agent(
            name=AgentName("Ember"),
            model=AgentModel(id="claude-sonnet", display_name="Sonnet"),
            position=Position(10, 10),
            journey=None,
        )
        await storage.agents.save_agent(agent)

        retrieved = await storage.agents.get_agent(AgentName("Ember"))
        assert retrieved.journey is None


class TestAgentState:
    """Test agent state fields."""

    async def test_known_agents(self, storage: Storage):
        """Should persist known agents."""
        agent = Agent(
            name=AgentName("Ember"),
            model=AgentModel(id="claude-sonnet", display_name="Sonnet"),
            position=Position(10, 10),
            known_agents=frozenset({AgentName("Sage"), AgentName("River")}),
        )
        await storage.agents.save_agent(agent)

        retrieved = await storage.agents.get_agent(AgentName("Ember"))
        assert AgentName("Sage") in retrieved.known_agents
        assert AgentName("River") in retrieved.known_agents

    async def test_sleeping_state(self, storage: Storage):
        """Should persist sleeping state."""
        agent = Agent(
            name=AgentName("Ember"),
            model=AgentModel(id="claude-sonnet", display_name="Sonnet"),
            position=Position(10, 10),
            is_sleeping=True,
        )
        await storage.agents.save_agent(agent)

        retrieved = await storage.agents.get_agent(AgentName("Ember"))
        assert retrieved.is_sleeping is True

    async def test_session_id(self, storage: Storage):
        """Should persist session ID."""
        agent = Agent(
            name=AgentName("Ember"),
            model=AgentModel(id="claude-sonnet", display_name="Sonnet"),
            position=Position(10, 10),
            session_id="session-12345",
            last_active_tick=42,
        )
        await storage.agents.save_agent(agent)

        retrieved = await storage.agents.get_agent(AgentName("Ember"))
        assert retrieved.session_id == "session-12345"
        assert retrieved.last_active_tick == 42
