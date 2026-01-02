"""World objects for Hearth.

Objects are persistent entities in the world that agents can interact with.
Signs, placed items, and items that can be carried or dropped.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .types import Position, ObjectId, AgentName


def generate_object_id() -> ObjectId:
    """Generate a new unique object ID."""
    return ObjectId(str(uuid.uuid4()))


class WorldObject(BaseModel):
    """Base for all persistent objects in the world.

    World objects have a position and track their creator.
    Some objects block movement (passable=False), others can be walked through.
    """

    model_config = ConfigDict(frozen=True)

    id: ObjectId
    position: Position
    created_by: AgentName | None = None
    created_tick: int = 0
    passable: bool = True  # Can agents walk through this object's cell?


class Sign(WorldObject):
    """A readable marker at a location.

    Signs display text that agents can read when they're nearby.
    """

    object_type: Literal["sign"] = "sign"
    text: str

    def with_text(self, text: str) -> Sign:
        """Return a new sign with updated text."""
        return self.model_copy(update={"text": text})


class PlacedItem(WorldObject):
    """An item placed in the world (furniture, decoration, etc.).

    Unlike items in inventory, placed items occupy a world position
    and can be interacted with by any agent.
    """

    object_type: Literal["placed_item"] = "placed_item"
    item_type: str
    properties: tuple[str, ...] = ()

    def with_properties(self, *props: str) -> PlacedItem:
        """Return a new placed item with updated properties."""
        return self.model_copy(update={"properties": props})


class Item(BaseModel):
    """An item that can be in inventory or converted to a world object.

    Items can be:
    - Stackable resources (wood, stone, clay) - no ID, quantity > 1
    - Unique items (crafted objects, rare finds) - have ID, quantity = 1
    """

    model_config = ConfigDict(frozen=True)

    # None for stackable resources, set for unique items
    id: ObjectId | None = None
    item_type: str
    properties: tuple[str, ...] = ()
    quantity: int = 1

    @property
    def is_stackable(self) -> bool:
        """Check if this is a stackable resource (no unique ID)."""
        return self.id is None

    @property
    def is_unique(self) -> bool:
        """Check if this is a unique item (has an ID)."""
        return self.id is not None

    def with_quantity(self, quantity: int) -> Item:
        """Return a new item with updated quantity."""
        return self.model_copy(update={"quantity": quantity})

    def with_properties(self, *props: str) -> Item:
        """Return a new item with updated properties."""
        return self.model_copy(update={"properties": props})

    def add_property(self, prop: str) -> Item:
        """Return a new item with an additional property."""
        if prop in self.properties:
            return self
        return self.model_copy(update={"properties": self.properties + (prop,)})

    def remove_property(self, prop: str) -> Item:
        """Return a new item with a property removed."""
        new_props = tuple(p for p in self.properties if p != prop)
        return self.model_copy(update={"properties": new_props})

    @classmethod
    def stackable(cls, item_type: str, quantity: int = 1) -> Item:
        """Create a stackable resource item."""
        return cls(item_type=item_type, quantity=quantity)

    @classmethod
    def unique(cls, item_type: str, properties: tuple[str, ...] = ()) -> Item:
        """Create a unique item with an ID."""
        return cls(
            id=generate_object_id(),
            item_type=item_type,
            properties=properties,
            quantity=1,
        )

    def to_placed_item(
        self,
        position: Position,
        created_by: AgentName | None = None,
        created_tick: int = 0,
        passable: bool = True,
    ) -> PlacedItem:
        """Convert this item to a placed item in the world."""
        return PlacedItem(
            id=self.id or generate_object_id(),
            position=position,
            created_by=created_by,
            created_tick=created_tick,
            item_type=self.item_type,
            properties=self.properties,
            passable=passable,
        )


# Type alias for any world object
AnyWorldObject = Sign | PlacedItem
