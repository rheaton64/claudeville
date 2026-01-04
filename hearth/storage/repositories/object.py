"""Object repository for Hearth.

Handles persistence of world objects: signs, placed items, etc.
Uses single-table inheritance with a discriminator column.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.types import Position, Rect, ObjectId, AgentName
from core.objects import WorldObject, Sign, PlacedItem, AnyWorldObject

from .base import BaseRepository

if TYPE_CHECKING:
    pass


class ObjectRepository(BaseRepository):
    """Repository for world objects.

    Handles:
    - Object CRUD (polymorphic via object_type discriminator)
    - Position queries
    - Type-specific queries
    """

    # --- Object CRUD ---

    async def get_object(self, object_id: ObjectId) -> AnyWorldObject | None:
        """Get an object by ID.

        Args:
            object_id: Object ID to get

        Returns:
            Object if found, None otherwise
        """
        row = await self.db.fetch_one(
            "SELECT * FROM objects WHERE id = ?",
            (str(object_id),),
        )
        if row is None:
            return None
        return self._row_to_object(row)

    async def save_object(self, obj: AnyWorldObject) -> None:
        """Save or update an object.

        Args:
            obj: Object to save
        """
        data = self._object_to_data(obj)
        quantity = obj.quantity if isinstance(obj, PlacedItem) else 1

        await self.db.execute(
            """
            INSERT INTO objects (id, object_type, x, y, created_by, created_tick, passable, quantity, data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                object_type = excluded.object_type,
                x = excluded.x,
                y = excluded.y,
                created_by = excluded.created_by,
                created_tick = excluded.created_tick,
                passable = excluded.passable,
                quantity = excluded.quantity,
                data = excluded.data
            """,
            (
                str(obj.id),
                self._get_object_type(obj),
                obj.position.x,
                obj.position.y,
                str(obj.created_by) if obj.created_by else None,
                obj.created_tick,
                int(obj.passable),
                quantity,
                self._encode_json(data),
            ),
        )
        await self.db.commit()

    async def delete_object(self, object_id: ObjectId) -> None:
        """Delete an object.

        Args:
            object_id: ID of object to delete
        """
        await self.db.execute(
            "DELETE FROM objects WHERE id = ?",
            (str(object_id),),
        )
        await self.db.commit()

    # --- Position Queries ---

    async def get_objects_at(self, pos: Position) -> list[AnyWorldObject]:
        """Get all objects at a position.

        Args:
            pos: Position to query

        Returns:
            List of objects at that position
        """
        rows = await self.db.fetch_all(
            "SELECT * FROM objects WHERE x = ? AND y = ?",
            (pos.x, pos.y),
        )
        return [self._row_to_object(row) for row in rows]

    async def get_objects_in_rect(self, rect: Rect) -> list[AnyWorldObject]:
        """Get all objects in a rectangle.

        Args:
            rect: Rectangle to query

        Returns:
            List of objects in the rect
        """
        rows = await self.db.fetch_all(
            """
            SELECT * FROM objects
            WHERE x >= ? AND x <= ? AND y >= ? AND y <= ?
            """,
            (rect.min_x, rect.max_x, rect.min_y, rect.max_y),
        )
        return [self._row_to_object(row) for row in rows]

    # --- Type Queries ---

    async def get_objects_by_type(self, obj_type: str) -> list[AnyWorldObject]:
        """Get all objects of a specific type.

        Args:
            obj_type: Object type ('sign', 'placed_item', etc.)

        Returns:
            List of objects of that type
        """
        rows = await self.db.fetch_all(
            "SELECT * FROM objects WHERE object_type = ?",
            (obj_type,),
        )
        return [self._row_to_object(row) for row in rows]

    async def get_objects_by_creator(self, agent: AgentName) -> list[AnyWorldObject]:
        """Get all objects created by an agent.

        Args:
            agent: Agent name

        Returns:
            List of objects created by that agent
        """
        rows = await self.db.fetch_all(
            "SELECT * FROM objects WHERE created_by = ?",
            (str(agent),),
        )
        return [self._row_to_object(row) for row in rows]

    # --- Type-Specific Methods ---

    async def get_sign(self, object_id: ObjectId) -> Sign | None:
        """Get a sign by ID.

        Args:
            object_id: Sign ID

        Returns:
            Sign if found and is a sign, None otherwise
        """
        obj = await self.get_object(object_id)
        if isinstance(obj, Sign):
            return obj
        return None

    async def get_signs_at(self, pos: Position) -> list[Sign]:
        """Get all signs at a position.

        Args:
            pos: Position to query

        Returns:
            List of signs at that position
        """
        rows = await self.db.fetch_all(
            "SELECT * FROM objects WHERE x = ? AND y = ? AND object_type = 'sign'",
            (pos.x, pos.y),
        )
        result = []
        for row in rows:
            obj = self._row_to_object(row)
            if isinstance(obj, Sign):
                result.append(obj)
        return result

    async def get_all_signs(self) -> list[Sign]:
        """Get all signs in the world.

        Returns:
            List of all signs
        """
        rows = await self.db.fetch_all(
            "SELECT * FROM objects WHERE object_type = 'sign'"
        )
        result = []
        for row in rows:
            obj = self._row_to_object(row)
            if isinstance(obj, Sign):
                result.append(obj)
        return result

    async def get_placed_items_at(self, pos: Position) -> list[PlacedItem]:
        """Get all placed items at a position.

        Args:
            pos: Position to query

        Returns:
            List of placed items at that position
        """
        rows = await self.db.fetch_all(
            "SELECT * FROM objects WHERE x = ? AND y = ? AND object_type = 'placed_item'",
            (pos.x, pos.y),
        )
        result = []
        for row in rows:
            obj = self._row_to_object(row)
            if isinstance(obj, PlacedItem):
                result.append(obj)
        return result

    # --- Conversion Helpers ---

    def _get_object_type(self, obj: AnyWorldObject) -> str:
        """Get the discriminator string for an object type.

        Args:
            obj: Object to get type for

        Returns:
            Type string for storage
        """
        if isinstance(obj, Sign):
            return "sign"
        if isinstance(obj, PlacedItem):
            return "placed_item"
        return "unknown"

    def _object_to_data(self, obj: AnyWorldObject) -> dict:
        """Extract type-specific data from an object.

        Args:
            obj: Object to extract data from

        Returns:
            Dict of type-specific fields
        """
        if isinstance(obj, Sign):
            return {"text": obj.text}
        if isinstance(obj, PlacedItem):
            return {
                "item_type": obj.item_type,
                "properties": list(obj.properties),
            }
        return {}

    def _row_to_object(self, row) -> AnyWorldObject:
        """Convert a database row to an object.

        Args:
            row: Database row

        Returns:
            Object instance
        """
        pos = Position(row["x"], row["y"])
        object_id = ObjectId(row["id"])
        created_by = AgentName(row["created_by"]) if row["created_by"] else None
        passable = bool(row["passable"])
        data = self._decode_json(row["data"]) or {}

        object_type = row["object_type"]

        if object_type == "sign":
            return Sign(
                id=object_id,
                position=pos,
                created_by=created_by,
                created_tick=row["created_tick"],
                passable=passable,
                text=data.get("text", ""),
            )
        if object_type == "placed_item":
            return PlacedItem(
                id=object_id,
                position=pos,
                created_by=created_by,
                created_tick=row["created_tick"],
                passable=passable,
                item_type=data.get("item_type", "unknown"),
                properties=tuple(data.get("properties", [])),
                quantity=row["quantity"],
            )

        # Fallback to generic WorldObject (shouldn't happen)
        raise ValueError(f"Unknown object type: {object_type}")
