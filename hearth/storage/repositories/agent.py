"""Agent repository for Hearth.

Handles persistence of agents, their inventory, and journey state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.types import Position, Rect, AgentName, ObjectId
from core.agent import (
    Agent,
    AgentModel,
    Inventory,
    InventoryStack,
    Journey,
    JourneyDestination,
)
from core.objects import Item

from .base import BaseRepository

if TYPE_CHECKING:
    pass


class AgentRepository(BaseRepository):
    """Repository for agents and their inventory.

    Handles:
    - Agent CRUD (position, state, session)
    - Inventory (stacks for resources, items for unique objects)
    - Journey state
    """

    # --- Agent CRUD ---

    async def get_agent(self, name: AgentName) -> Agent | None:
        """Get an agent by name.

        Args:
            name: Agent name

        Returns:
            Agent if found, None otherwise
        """
        row = await self.db.fetch_one(
            "SELECT * FROM agents WHERE name = ?",
            (str(name),),
        )
        if row is None:
            return None

        # Load inventory separately
        inventory = await self.get_inventory(name)

        # Parse journey if present
        journey = None
        if row["journey"]:
            journey = self._parse_journey(row["journey"])

        return Agent(
            name=name,
            model=AgentModel(
                id=row["model_id"],
                display_name=row["model_display_name"],
            ),
            personality=row["personality"],
            position=Position(row["x"], row["y"]),
            journey=journey,
            inventory=inventory,
            is_sleeping=bool(row["is_sleeping"]),
            known_agents=self._json_to_agent_names(row["known_agents"]),
            session_id=row["session_id"],
            last_active_tick=row["last_active_tick"],
        )

    async def get_all_agents(self) -> list[Agent]:
        """Get all agents.

        Returns:
            List of all agents
        """
        rows = await self.db.fetch_all("SELECT name FROM agents")
        agents = []
        for row in rows:
            agent = await self.get_agent(AgentName(row["name"]))
            if agent is not None:
                agents.append(agent)
        return agents

    async def save_agent(self, agent: Agent) -> None:
        """Save or update an agent.

        Args:
            agent: Agent to save
        """
        # Serialize journey if present
        journey_json = None
        if agent.journey:
            journey_json = self._serialize_journey(agent.journey)

        await self.db.execute(
            """
            INSERT INTO agents (
                name, model_id, model_display_name, personality,
                x, y, is_sleeping, session_id, last_active_tick,
                known_agents, journey
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                model_id = excluded.model_id,
                model_display_name = excluded.model_display_name,
                personality = excluded.personality,
                x = excluded.x,
                y = excluded.y,
                is_sleeping = excluded.is_sleeping,
                session_id = excluded.session_id,
                last_active_tick = excluded.last_active_tick,
                known_agents = excluded.known_agents,
                journey = excluded.journey
            """,
            (
                str(agent.name),
                agent.model.id,
                agent.model.display_name,
                agent.personality,
                agent.position.x,
                agent.position.y,
                int(agent.is_sleeping),
                agent.session_id,
                agent.last_active_tick,
                self._agent_names_to_json(agent.known_agents),
                journey_json,
            ),
        )

        # Save inventory
        await self.save_inventory(agent.name, agent.inventory)

        await self.db.commit()

    async def delete_agent(self, name: AgentName) -> None:
        """Delete an agent and their inventory.

        Args:
            name: Agent name to delete
        """
        # Inventory tables have CASCADE delete, so just delete agent
        await self.db.execute(
            "DELETE FROM agents WHERE name = ?",
            (str(name),),
        )
        await self.db.commit()

    # --- Position Queries ---

    async def get_agents_in_rect(self, rect: Rect) -> list[Agent]:
        """Get all agents with positions in a rectangle.

        Args:
            rect: Rectangle to query

        Returns:
            List of agents in the rect
        """
        rows = await self.db.fetch_all(
            """
            SELECT name FROM agents
            WHERE x >= ? AND x <= ? AND y >= ? AND y <= ?
            """,
            (rect.min_x, rect.max_x, rect.min_y, rect.max_y),
        )

        agents = []
        for row in rows:
            agent = await self.get_agent(AgentName(row["name"]))
            if agent is not None:
                agents.append(agent)
        return agents

    async def get_agent_at(self, pos: Position) -> Agent | None:
        """Get agent at exact position.

        Args:
            pos: Position to query

        Returns:
            Agent at position, or None
        """
        row = await self.db.fetch_one(
            "SELECT name FROM agents WHERE x = ? AND y = ?",
            (pos.x, pos.y),
        )
        if row is None:
            return None
        return await self.get_agent(AgentName(row["name"]))

    # --- Inventory ---

    async def get_inventory(self, agent: AgentName) -> Inventory:
        """Get agent's inventory.

        Args:
            agent: Agent name

        Returns:
            Inventory with stacks and items
        """
        stacks = await self._load_stacks(agent)
        items = await self._load_items(agent)
        return Inventory(stacks=stacks, items=items)

    async def save_inventory(self, agent: AgentName, inventory: Inventory) -> None:
        """Save agent's full inventory (replaces existing).

        Args:
            agent: Agent name
            inventory: Inventory to save
        """
        await self._save_stacks(agent, inventory.stacks)
        await self._save_items(agent, inventory.items)

    async def _load_stacks(self, agent: AgentName) -> tuple[InventoryStack, ...]:
        """Load inventory stacks for an agent.

        Args:
            agent: Agent name

        Returns:
            Tuple of inventory stacks
        """
        rows = await self.db.fetch_all(
            "SELECT item_type, quantity FROM inventory_stacks WHERE agent = ?",
            (str(agent),),
        )
        return tuple(
            InventoryStack(item_type=row["item_type"], quantity=row["quantity"])
            for row in rows
        )

    async def _load_items(self, agent: AgentName) -> tuple[Item, ...]:
        """Load unique inventory items for an agent.

        Args:
            agent: Agent name

        Returns:
            Tuple of unique items
        """
        rows = await self.db.fetch_all(
            "SELECT id, item_type, properties FROM inventory_items WHERE agent = ?",
            (str(agent),),
        )
        return tuple(
            Item(
                id=ObjectId(row["id"]),
                item_type=row["item_type"],
                properties=tuple(self._decode_json(row["properties"]) or []),
                quantity=1,
            )
            for row in rows
        )

    async def _save_stacks(
        self, agent: AgentName, stacks: tuple[InventoryStack, ...]
    ) -> None:
        """Save inventory stacks, replacing existing.

        Args:
            agent: Agent name
            stacks: Stacks to save
        """
        # Delete existing stacks
        await self.db.execute(
            "DELETE FROM inventory_stacks WHERE agent = ?",
            (str(agent),),
        )

        # Insert new stacks
        if stacks:
            await self.db.executemany(
                "INSERT INTO inventory_stacks (agent, item_type, quantity) VALUES (?, ?, ?)",
                [(str(agent), s.item_type, s.quantity) for s in stacks],
            )

    async def _save_items(
        self, agent: AgentName, items: tuple[Item, ...]
    ) -> None:
        """Save unique inventory items, replacing existing.

        Args:
            agent: Agent name
            items: Items to save
        """
        # Delete existing items
        await self.db.execute(
            "DELETE FROM inventory_items WHERE agent = ?",
            (str(agent),),
        )

        # Insert new items
        if items:
            await self.db.executemany(
                "INSERT INTO inventory_items (id, agent, item_type, properties) VALUES (?, ?, ?, ?)",
                [
                    (
                        str(item.id),
                        str(agent),
                        item.item_type,
                        self._encode_json(list(item.properties)),
                    )
                    for item in items
                ],
            )

    # --- Journey Helpers ---

    def _serialize_journey(self, journey: Journey) -> str:
        """Serialize journey to JSON.

        Args:
            journey: Journey to serialize

        Returns:
            JSON string
        """
        data = {
            "destination": {
                "position": [journey.destination.position.x, journey.destination.position.y]
                if journey.destination.position
                else None,
                "landmark": str(journey.destination.landmark)
                if journey.destination.landmark
                else None,
            },
            "path": [[p.x, p.y] for p in journey.path],
            "progress": journey.progress,
        }
        return self._encode_json(data)

    def _parse_journey(self, json_str: str) -> Journey:
        """Parse journey from JSON.

        Args:
            json_str: JSON string

        Returns:
            Journey instance
        """
        data = self._decode_json(json_str)

        dest_data = data["destination"]
        destination = JourneyDestination(
            position=Position(dest_data["position"][0], dest_data["position"][1])
            if dest_data.get("position")
            else None,
            landmark=dest_data.get("landmark"),
        )

        path = tuple(Position(p[0], p[1]) for p in data["path"])

        return Journey(
            destination=destination,
            path=path,
            progress=data["progress"],
        )

    # --- Convenience Methods ---

    async def update_position(self, name: AgentName, pos: Position) -> None:
        """Update just the agent's position.

        Args:
            name: Agent name
            pos: New position
        """
        await self.db.execute(
            "UPDATE agents SET x = ?, y = ? WHERE name = ?",
            (pos.x, pos.y, str(name)),
        )
        await self.db.commit()

    async def update_session(
        self, name: AgentName, session_id: str | None, tick: int
    ) -> None:
        """Update agent's session info.

        Args:
            name: Agent name
            session_id: New session ID (or None)
            tick: Current tick
        """
        await self.db.execute(
            "UPDATE agents SET session_id = ?, last_active_tick = ? WHERE name = ?",
            (session_id, tick, str(name)),
        )
        await self.db.commit()

    async def update_sleeping(self, name: AgentName, is_sleeping: bool) -> None:
        """Update agent's sleep state.

        Args:
            name: Agent name
            is_sleeping: New sleep state
        """
        await self.db.execute(
            "UPDATE agents SET is_sleeping = ? WHERE name = ?",
            (int(is_sleeping), str(name)),
        )
        await self.db.commit()
