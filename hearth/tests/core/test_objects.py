"""Tests for world objects: Sign, PlacedItem, Item."""

import pytest

from hearth.core import (
    WorldObject,
    Sign,
    PlacedItem,
    Item,
    Position,
    ObjectId,
    AgentName,
    generate_object_id,
)


class TestGenerateObjectId:
    """Tests for object ID generation."""

    def test_generates_string(self):
        """Generated ID is a string."""
        id1 = generate_object_id()
        assert isinstance(id1, str)

    def test_generates_unique_ids(self):
        """Each call generates a unique ID."""
        ids = {generate_object_id() for _ in range(100)}
        assert len(ids) == 100


class TestSign:
    """Tests for Sign model."""

    def test_create_sign(self):
        """Can create a sign."""
        sign = Sign(
            id=ObjectId("sign-1"),
            position=Position(5, 5),
            text="Hello, world!",
        )
        assert sign.id == "sign-1"
        assert sign.position == Position(5, 5)
        assert sign.text == "Hello, world!"
        assert sign.object_type == "sign"

    def test_create_sign_with_creator(self):
        """Sign can have a creator."""
        sign = Sign(
            id=ObjectId("sign-1"),
            position=Position(5, 5),
            text="Hello",
            created_by=AgentName("Ember"),
            created_tick=10,
        )
        assert sign.created_by == "Ember"
        assert sign.created_tick == 10

    def test_sign_is_frozen(self):
        """Sign is immutable."""
        sign = Sign(
            id=ObjectId("sign-1"),
            position=Position(5, 5),
            text="Hello",
        )
        with pytest.raises(Exception):
            sign.text = "Changed"

    def test_with_text(self):
        """Update sign text returns new sign."""
        sign = Sign(
            id=ObjectId("sign-1"),
            position=Position(5, 5),
            text="Hello",
        )
        new_sign = sign.with_text("Goodbye")

        assert sign.text == "Hello"
        assert new_sign.text == "Goodbye"
        assert new_sign.id == sign.id


class TestPlacedItem:
    """Tests for PlacedItem model."""

    def test_create_placed_item(self):
        """Can create a placed item."""
        item = PlacedItem(
            id=ObjectId("item-1"),
            position=Position(5, 5),
            item_type="table",
        )
        assert item.id == "item-1"
        assert item.position == Position(5, 5)
        assert item.item_type == "table"
        assert item.object_type == "placed_item"
        assert item.properties == ()

    def test_create_placed_item_with_properties(self):
        """Placed item can have properties."""
        item = PlacedItem(
            id=ObjectId("item-1"),
            position=Position(5, 5),
            item_type="table",
            properties=("wooden", "sturdy"),
        )
        assert item.properties == ("wooden", "sturdy")

    def test_with_properties(self):
        """Update properties returns new item."""
        item = PlacedItem(
            id=ObjectId("item-1"),
            position=Position(5, 5),
            item_type="table",
        )
        new_item = item.with_properties("polished", "large")

        assert item.properties == ()
        assert new_item.properties == ("polished", "large")


class TestItem:
    """Tests for Item model."""

    def test_create_stackable_item(self):
        """Can create a stackable resource item."""
        item = Item(item_type="wood", quantity=5)

        assert item.item_type == "wood"
        assert item.quantity == 5
        assert item.id is None
        assert item.is_stackable
        assert not item.is_unique

    def test_create_unique_item(self):
        """Can create a unique item with ID."""
        item = Item(
            id=ObjectId("item-1"),
            item_type="crafted_bowl",
            properties=("clay", "fragile"),
        )

        assert item.id == "item-1"
        assert item.item_type == "crafted_bowl"
        assert item.is_unique
        assert not item.is_stackable

    def test_stackable_factory(self):
        """Create stackable item via factory."""
        item = Item.stackable("stone", 10)

        assert item.item_type == "stone"
        assert item.quantity == 10
        assert item.is_stackable

    def test_unique_factory(self):
        """Create unique item via factory."""
        item = Item.unique("crystal", ("glowing", "blue"))

        assert item.item_type == "crystal"
        assert item.is_unique
        assert item.id is not None
        assert "glowing" in item.properties

    def test_with_quantity(self):
        """Update quantity returns new item."""
        item = Item.stackable("wood", 5)
        new_item = item.with_quantity(10)

        assert item.quantity == 5
        assert new_item.quantity == 10

    def test_with_properties(self):
        """Update properties returns new item."""
        item = Item.unique("bowl")
        new_item = item.with_properties("polished", "fired")

        assert item.properties == ()
        assert new_item.properties == ("polished", "fired")

    def test_add_property(self):
        """Add single property."""
        item = Item.unique("bowl", ("clay",))
        new_item = item.add_property("fired")

        assert item.properties == ("clay",)
        assert new_item.properties == ("clay", "fired")

    def test_add_property_idempotent(self):
        """Adding existing property does nothing."""
        item = Item.unique("bowl", ("clay",))
        new_item = item.add_property("clay")

        assert new_item is item  # Same object

    def test_remove_property(self):
        """Remove single property."""
        item = Item.unique("bowl", ("clay", "fired"))
        new_item = item.remove_property("clay")

        assert item.properties == ("clay", "fired")
        assert new_item.properties == ("fired",)

    def test_to_placed_item(self):
        """Convert item to placed world object."""
        item = Item.unique("table", ("wooden",))
        placed = item.to_placed_item(
            position=Position(5, 5),
            created_by=AgentName("Ember"),
            created_tick=10,
        )

        assert placed.position == Position(5, 5)
        assert placed.item_type == "table"
        assert placed.properties == ("wooden",)
        assert placed.created_by == "Ember"
        assert placed.created_tick == 10
        # Uses existing ID if present
        assert placed.id == item.id

    def test_to_placed_item_stackable(self):
        """Converting stackable item generates new ID."""
        item = Item.stackable("wood", 1)
        placed = item.to_placed_item(position=Position(5, 5))

        assert placed.id is not None  # Generated
        assert placed.item_type == "wood"
