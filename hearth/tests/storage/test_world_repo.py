"""Tests for WorldRepository."""

import pytest

from core.types import Position, Rect, ObjectId, AgentName
from core.terrain import Terrain, Weather
from core.world import Cell, Direction, WorldState
from core.structures import Structure

from storage import Storage
from storage.repositories.world import WorldRepository


class TestWorldState:
    """Test world state operations."""

    async def test_get_default_world_state(self, storage: Storage):
        """Should return default world state."""
        state = await storage.world.get_world_state()
        assert state.current_tick == 0
        assert state.weather == Weather.CLEAR
        assert state.width > 0
        assert state.height > 0

    async def test_set_tick(self, storage: Storage):
        """Should update tick."""
        await storage.world.set_tick(42)
        state = await storage.world.get_world_state()
        assert state.current_tick == 42

    async def test_set_weather(self, storage: Storage):
        """Should update weather."""
        await storage.world.set_weather(Weather.RAINY)
        state = await storage.world.get_world_state()
        assert state.weather == Weather.RAINY

    async def test_set_dimensions(self, storage: Storage):
        """Should update dimensions."""
        await storage.world.set_dimensions(200, 150)
        state = await storage.world.get_world_state()
        assert state.width == 200
        assert state.height == 150


class TestCells:
    """Test cell operations."""

    async def test_get_default_cell(self, storage: Storage):
        """Should return default grass cell for unstored position."""
        cell = await storage.world.get_cell(Position(50, 50))
        assert cell.position == Position(50, 50)
        assert cell.terrain == Terrain.GRASS
        assert cell.walls == frozenset()
        assert cell.doors == frozenset()
        assert cell.place_name is None

    async def test_set_and_get_cell(self, storage: Storage):
        """Should store and retrieve cell."""
        cell = Cell(
            position=Position(10, 20),
            terrain=Terrain.WATER,
            walls=frozenset({Direction.NORTH, Direction.EAST}),
            doors=frozenset({Direction.NORTH}),
            place_name="Test Place",
        )
        await storage.world.set_cell(cell)

        retrieved = await storage.world.get_cell(Position(10, 20))
        assert retrieved.terrain == Terrain.WATER
        assert retrieved.walls == frozenset({Direction.NORTH, Direction.EAST})
        assert retrieved.doors == frozenset({Direction.NORTH})
        assert retrieved.place_name == "Test Place"

    async def test_set_default_cell_removes_from_storage(self, storage: Storage):
        """Setting a default cell should remove it from storage."""
        # First set a non-default cell
        cell = Cell(position=Position(10, 20), terrain=Terrain.FOREST)
        await storage.world.set_cell(cell)

        # Now set it back to default
        default_cell = Cell(position=Position(10, 20))
        await storage.world.set_cell(default_cell)

        # Should return default
        retrieved = await storage.world.get_cell(Position(10, 20))
        assert retrieved.terrain == Terrain.GRASS

    async def test_get_cells_in_rect(self, storage: Storage):
        """Should return all cells in rectangle."""
        # Set some cells
        await storage.world.set_cell(
            Cell(position=Position(5, 5), terrain=Terrain.WATER)
        )
        await storage.world.set_cell(
            Cell(position=Position(6, 6), terrain=Terrain.STONE)
        )

        rect = Rect(5, 5, 7, 7)
        cells = await storage.world.get_cells_in_rect(rect)

        # Should have 9 cells (3x3 grid)
        assert len(cells) == 9

        # Find our special cells
        water_cells = [c for c in cells if c.terrain == Terrain.WATER]
        stone_cells = [c for c in cells if c.terrain == Terrain.STONE]
        grass_cells = [c for c in cells if c.terrain == Terrain.GRASS]

        assert len(water_cells) == 1
        assert len(stone_cells) == 1
        assert len(grass_cells) == 7

    async def test_get_stored_cells_in_rect(self, storage: Storage):
        """Should return only stored cells."""
        await storage.world.set_cell(
            Cell(position=Position(5, 5), terrain=Terrain.WATER)
        )

        rect = Rect(4, 4, 6, 6)
        cells = await storage.world.get_stored_cells_in_rect(rect)

        # Should only have the one stored cell
        assert len(cells) == 1
        assert cells[0].position == Position(5, 5)


class TestNamedPlaces:
    """Test named places operations."""

    async def test_set_and_get_named_place(self, storage: Storage):
        """Should store and retrieve named places."""
        await storage.world.set_named_place("The Grove", Position(25, 30))

        pos = await storage.world.get_named_place("The Grove")
        assert pos == Position(25, 30)

    async def test_get_nonexistent_place(self, storage: Storage):
        """Should return None for unknown place."""
        pos = await storage.world.get_named_place("Unknown")
        assert pos is None

    async def test_update_named_place(self, storage: Storage):
        """Should update existing place."""
        await storage.world.set_named_place("Moving Place", Position(10, 10))
        await storage.world.set_named_place("Moving Place", Position(20, 20))

        pos = await storage.world.get_named_place("Moving Place")
        assert pos == Position(20, 20)

    async def test_get_all_named_places(self, storage: Storage):
        """Should return all named places."""
        await storage.world.set_named_place("Place A", Position(1, 1))
        await storage.world.set_named_place("Place B", Position(2, 2))
        await storage.world.set_named_place("Place C", Position(3, 3))

        places = await storage.world.get_all_named_places()
        assert len(places) == 3
        assert places["Place A"] == Position(1, 1)
        assert places["Place B"] == Position(2, 2)
        assert places["Place C"] == Position(3, 3)


class TestStructures:
    """Test structure operations."""

    async def test_save_and_get_structure(self, storage: Storage):
        """Should store and retrieve structures."""
        structure = Structure(
            id=ObjectId("struct-1"),
            name="My House",
            interior_cells=frozenset({Position(10, 10), Position(10, 11), Position(11, 10)}),
            created_by=AgentName("Ember"),
        )
        await storage.world.save_structure(structure)

        retrieved = await storage.world.get_structure(ObjectId("struct-1"))
        assert retrieved is not None
        assert retrieved.name == "My House"
        assert len(retrieved.interior_cells) == 3
        assert retrieved.created_by == AgentName("Ember")

    async def test_get_nonexistent_structure(self, storage: Storage):
        """Should return None for unknown structure."""
        retrieved = await storage.world.get_structure(ObjectId("unknown"))
        assert retrieved is None

    async def test_structure_updates_cells(self, storage: Storage):
        """Saving structure should update cell structure_id."""
        structure = Structure(
            id=ObjectId("struct-1"),
            interior_cells=frozenset({Position(10, 10)}),
        )
        await storage.world.save_structure(structure)

        cell = await storage.world.get_cell(Position(10, 10))
        assert cell.structure_id == ObjectId("struct-1")

    async def test_delete_structure(self, storage: Storage):
        """Should delete structure and clear cell references."""
        structure = Structure(
            id=ObjectId("struct-1"),
            interior_cells=frozenset({Position(10, 10)}),
        )
        await storage.world.save_structure(structure)

        await storage.world.delete_structure(ObjectId("struct-1"))

        # Structure should be gone
        retrieved = await storage.world.get_structure(ObjectId("struct-1"))
        assert retrieved is None

        # Cell should have structure_id cleared
        cell = await storage.world.get_cell(Position(10, 10))
        assert cell.structure_id is None

    async def test_structure_is_private(self, storage: Storage):
        """Should store and retrieve is_private flag."""
        # Test default (False)
        public_structure = Structure(
            id=ObjectId("public-1"),
            interior_cells=frozenset({Position(5, 5)}),
        )
        await storage.world.save_structure(public_structure)

        retrieved = await storage.world.get_structure(ObjectId("public-1"))
        assert retrieved is not None
        assert retrieved.is_private is False

        # Test explicit True
        private_structure = Structure(
            id=ObjectId("private-1"),
            interior_cells=frozenset({Position(6, 6)}),
            is_private=True,
        )
        await storage.world.save_structure(private_structure)

        retrieved = await storage.world.get_structure(ObjectId("private-1"))
        assert retrieved is not None
        assert retrieved.is_private is True
