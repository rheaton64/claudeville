"""Tests for WorldService."""

import pytest

from core.types import Position, Direction, Rect, ObjectId, AgentName
from core.terrain import Terrain
from core.world import Cell
from core.objects import Sign, PlacedItem, Item
from core.structures import Structure

from services import (
    WorldService,
    InvalidPositionError,
    ObjectNotFoundError,
)


class TestSpatialQueries:
    """Test cell and object queries."""

    async def test_get_cell_returns_default_for_unstored(
        self, world_service: WorldService
    ):
        """Should return default grass cell for unstored position."""
        cell = await world_service.get_cell(Position(50, 50))
        assert cell.position == Position(50, 50)
        assert cell.terrain == Terrain.GRASS
        assert cell.walls == frozenset()

    async def test_get_cell_returns_stored_cell(self, world_service: WorldService):
        """Should return stored cell when set."""
        # Set a cell with custom terrain
        cell = Cell(position=Position(10, 10), terrain=Terrain.WATER)
        await world_service._world_repo.set_cell(cell)

        retrieved = await world_service.get_cell(Position(10, 10))
        assert retrieved.terrain == Terrain.WATER

    async def test_get_cells_in_rect(self, world_service: WorldService):
        """Should return all cells in rectangle (including defaults)."""
        # Set one cell
        cell = Cell(position=Position(5, 5), terrain=Terrain.FOREST)
        await world_service._world_repo.set_cell(cell)

        rect = Rect(5, 5, 7, 7)
        cells = await world_service.get_cells_in_rect(rect)

        # Should have 9 cells (3x3)
        assert len(cells) == 9

        # One should be forest
        forest_cells = [c for c in cells if c.terrain == Terrain.FOREST]
        assert len(forest_cells) == 1
        assert forest_cells[0].position == Position(5, 5)

    async def test_get_objects_at_position(self, world_service: WorldService):
        """Should return objects at position."""
        sign = Sign(
            id=ObjectId("sign-1"),
            position=Position(10, 10),
            text="Hello",
            created_tick=0,
        )
        await world_service.place_object(sign)

        objects = await world_service.get_objects_at(Position(10, 10))
        assert len(objects) == 1
        assert objects[0].id == ObjectId("sign-1")

    async def test_get_objects_in_rect(self, world_service: WorldService):
        """Should return objects in rectangle."""
        sign1 = Sign(
            id=ObjectId("sign-1"),
            position=Position(5, 5),
            text="First",
            created_tick=0,
        )
        sign2 = Sign(
            id=ObjectId("sign-2"),
            position=Position(50, 50),
            text="Second",
            created_tick=0,
        )
        await world_service.place_object(sign1)
        await world_service.place_object(sign2)

        rect = Rect(0, 0, 10, 10)
        objects = await world_service.get_objects_in_rect(rect)

        assert len(objects) == 1
        assert objects[0].id == ObjectId("sign-1")

    async def test_get_world_dimensions(self, world_service: WorldService):
        """Should return world dimensions."""
        width, height = await world_service.get_world_dimensions()
        assert width == 500
        assert height == 500


class TestTerrainProperties:
    """Test terrain property lookups."""

    def test_get_terrain_properties(self, world_service: WorldService):
        """Should return terrain properties dict."""
        props = world_service.get_terrain_properties(Terrain.FOREST)
        assert props["passable"] is True
        assert props["symbol"] == "♣"
        assert props["gather_resource"] == "wood"

    def test_is_terrain_passable_true(self, world_service: WorldService):
        """Should return True for passable terrain."""
        assert world_service.is_terrain_passable(Terrain.GRASS) is True
        assert world_service.is_terrain_passable(Terrain.FOREST) is True
        assert world_service.is_terrain_passable(Terrain.STONE) is True

    def test_is_terrain_passable_false(self, world_service: WorldService):
        """Should return False for impassable terrain."""
        assert world_service.is_terrain_passable(Terrain.WATER) is False

    def test_get_terrain_symbol(self, world_service: WorldService):
        """Should return terrain symbol."""
        assert world_service.get_terrain_symbol(Terrain.GRASS) == "."
        assert world_service.get_terrain_symbol(Terrain.WATER) == "≈"
        assert world_service.get_terrain_symbol(Terrain.FOREST) == "♣"

    def test_get_gather_resource(self, world_service: WorldService):
        """Should return gatherable resource for each terrain type."""
        assert world_service.get_gather_resource(Terrain.FOREST) == "wood"
        assert world_service.get_gather_resource(Terrain.WATER) is None  # Needs vessel
        assert world_service.get_gather_resource(Terrain.GRASS) == "grass"
        assert world_service.get_gather_resource(Terrain.STONE) == "stone"
        assert world_service.get_gather_resource(Terrain.SAND) == "clay"


class TestObjectManagement:
    """Test object placement and removal."""

    async def test_place_object(self, world_service: WorldService):
        """Should place object in world."""
        sign = Sign(
            id=ObjectId("sign-1"),
            position=Position(25, 25),
            text="Test",
            created_tick=0,
        )
        await world_service.place_object(sign)

        retrieved = await world_service._object_repo.get_object(ObjectId("sign-1"))
        assert retrieved is not None
        assert retrieved.position == Position(25, 25)

    async def test_place_object_out_of_bounds(self, world_service: WorldService):
        """Should raise error for out of bounds position."""
        sign = Sign(
            id=ObjectId("sign-1"),
            position=Position(600, 600),  # Out of bounds (world is 500x500)
            text="Test",
            created_tick=0,
        )
        with pytest.raises(InvalidPositionError):
            await world_service.place_object(sign)

    async def test_remove_object(self, world_service: WorldService):
        """Should remove object from world."""
        sign = Sign(
            id=ObjectId("sign-1"),
            position=Position(25, 25),
            text="Test",
            created_tick=0,
        )
        await world_service.place_object(sign)
        await world_service.remove_object(ObjectId("sign-1"))

        retrieved = await world_service._object_repo.get_object(ObjectId("sign-1"))
        assert retrieved is None

    async def test_remove_nonexistent_object(self, world_service: WorldService):
        """Should raise error for nonexistent object."""
        with pytest.raises(ObjectNotFoundError):
            await world_service.remove_object(ObjectId("nonexistent"))

    async def test_move_object(self, world_service: WorldService):
        """Should move object to new position."""
        sign = Sign(
            id=ObjectId("sign-1"),
            position=Position(25, 25),
            text="Test",
            created_tick=0,
        )
        await world_service.place_object(sign)
        await world_service.move_object(ObjectId("sign-1"), Position(30, 30))

        retrieved = await world_service._object_repo.get_object(ObjectId("sign-1"))
        assert retrieved.position == Position(30, 30)

    async def test_move_object_out_of_bounds(self, world_service: WorldService):
        """Should raise error for moving out of bounds."""
        sign = Sign(
            id=ObjectId("sign-1"),
            position=Position(25, 25),
            text="Test",
            created_tick=0,
        )
        await world_service.place_object(sign)

        with pytest.raises(InvalidPositionError):
            await world_service.move_object(ObjectId("sign-1"), Position(600, 600))


class TestWallPlacement:
    """Test wall symmetry and transactions."""

    async def test_place_wall_updates_both_cells(self, world_service: WorldService):
        """Should place wall on both adjacent cells."""
        await world_service.place_wall(Position(10, 10), Direction.NORTH)

        cell = await world_service.get_cell(Position(10, 10))
        adjacent = await world_service.get_cell(Position(10, 11))

        assert Direction.NORTH in cell.walls
        assert Direction.SOUTH in adjacent.walls

    async def test_place_wall_at_world_edge(self, world_service: WorldService):
        """Should only update one cell at world edge."""
        # Place wall on north edge of world (y=99)
        await world_service.place_wall(Position(10, 99), Direction.NORTH)

        cell = await world_service.get_cell(Position(10, 99))
        assert Direction.NORTH in cell.walls

        # Adjacent cell doesn't exist (out of bounds)

    async def test_place_wall_invalid_position(self, world_service: WorldService):
        """Should raise error for invalid position."""
        with pytest.raises(InvalidPositionError):
            await world_service.place_wall(Position(600, 600), Direction.NORTH)

    async def test_remove_wall_updates_both_cells(self, world_service: WorldService):
        """Should remove wall from both adjacent cells."""
        # First place wall
        await world_service.place_wall(Position(10, 10), Direction.NORTH)

        # Then remove it
        await world_service.remove_wall(Position(10, 10), Direction.NORTH)

        cell = await world_service.get_cell(Position(10, 10))
        adjacent = await world_service.get_cell(Position(10, 11))

        assert Direction.NORTH not in cell.walls
        assert Direction.SOUTH not in adjacent.walls

    async def test_place_door_adds_wall_and_door(self, world_service: WorldService):
        """Should add both wall and door on both cells."""
        await world_service.place_door(Position(10, 10), Direction.EAST)

        cell = await world_service.get_cell(Position(10, 10))
        adjacent = await world_service.get_cell(Position(11, 10))

        assert Direction.EAST in cell.walls
        assert Direction.EAST in cell.doors
        assert Direction.WEST in adjacent.walls
        assert Direction.WEST in adjacent.doors

    async def test_remove_door_leaves_wall(self, world_service: WorldService):
        """Should remove door but leave wall."""
        # First place door (which adds wall)
        await world_service.place_door(Position(10, 10), Direction.EAST)

        # Then remove door
        await world_service.remove_door(Position(10, 10), Direction.EAST)

        cell = await world_service.get_cell(Position(10, 10))
        adjacent = await world_service.get_cell(Position(11, 10))

        # Wall should remain
        assert Direction.EAST in cell.walls
        assert Direction.WEST in adjacent.walls

        # Door should be gone
        assert Direction.EAST not in cell.doors
        assert Direction.WEST not in adjacent.doors


class TestStructureDetection:
    """Test flood-fill structure detection."""

    async def test_detect_simple_rectangle(self, world_service: WorldService):
        """Should detect a simple 2x2 enclosed structure."""
        # Create a 2x2 box with walls around it
        # The interior cells are (5,5), (5,6), (6,5), (6,6)
        # We need walls on all exterior edges

        # Bottom row: walls on south
        await world_service.place_wall(Position(5, 5), Direction.SOUTH)
        await world_service.place_wall(Position(6, 5), Direction.SOUTH)

        # Top row: walls on north
        await world_service.place_wall(Position(5, 6), Direction.NORTH)
        await world_service.place_wall(Position(6, 6), Direction.NORTH)

        # Left column: walls on west
        await world_service.place_wall(Position(5, 5), Direction.WEST)
        await world_service.place_wall(Position(5, 6), Direction.WEST)

        # Right column: walls on east
        await world_service.place_wall(Position(6, 5), Direction.EAST)
        await world_service.place_wall(Position(6, 6), Direction.EAST)

        # Detect structure starting from inside
        structure = await world_service.detect_structure_at(Position(5, 5))

        assert structure is not None
        assert structure.size == 4
        assert Position(5, 5) in structure.interior_cells
        assert Position(5, 6) in structure.interior_cells
        assert Position(6, 5) in structure.interior_cells
        assert Position(6, 6) in structure.interior_cells

    async def test_detect_single_cell_enclosure(self, world_service: WorldService):
        """Should detect a single-cell enclosure."""
        # Create walls on all four sides of one cell
        await world_service.place_wall(Position(10, 10), Direction.NORTH)
        await world_service.place_wall(Position(10, 10), Direction.SOUTH)
        await world_service.place_wall(Position(10, 10), Direction.EAST)
        await world_service.place_wall(Position(10, 10), Direction.WEST)

        structure = await world_service.detect_structure_at(Position(10, 10))

        assert structure is not None
        assert structure.size == 1
        assert Position(10, 10) in structure.interior_cells

    async def test_not_enclosed_returns_none(self, world_service: WorldService):
        """Should return None if area is not enclosed."""
        # Place only 3 walls (missing one side)
        await world_service.place_wall(Position(10, 10), Direction.NORTH)
        await world_service.place_wall(Position(10, 10), Direction.SOUTH)
        await world_service.place_wall(Position(10, 10), Direction.EAST)
        # Missing WEST wall

        structure = await world_service.detect_structure_at(Position(10, 10))
        assert structure is None

    async def test_door_allows_escape(self, world_service: WorldService):
        """Structure detection with door should not be enclosed (door allows passage)."""
        # Create walls on all four sides
        await world_service.place_wall(Position(10, 10), Direction.NORTH)
        await world_service.place_wall(Position(10, 10), Direction.SOUTH)
        await world_service.place_wall(Position(10, 10), Direction.EAST)
        # Place door instead of wall on west
        await world_service.place_door(Position(10, 10), Direction.WEST)

        # With a door, we can "escape" so it's not enclosed
        structure = await world_service.detect_structure_at(Position(10, 10))
        assert structure is None

    async def test_max_cells_limit(self, world_service: WorldService):
        """Should return None if search exceeds max_cells."""
        # An unenclosed area will keep expanding until hitting world boundary or max_cells
        structure = await world_service.detect_structure_at(
            Position(50, 50), max_cells=5
        )
        assert structure is None

    async def test_detect_l_shaped_structure(self, world_service: WorldService):
        """Should detect an L-shaped enclosed structure."""
        # L-shape:
        # (5,6) (6,6)
        # (5,5)
        #
        # Walls needed:
        # Around (5,5): SOUTH, WEST
        # Around (5,6): NORTH, WEST
        # Around (6,6): NORTH, EAST, SOUTH

        # Left column
        await world_service.place_wall(Position(5, 5), Direction.SOUTH)
        await world_service.place_wall(Position(5, 5), Direction.WEST)
        await world_service.place_wall(Position(5, 6), Direction.NORTH)
        await world_service.place_wall(Position(5, 6), Direction.WEST)

        # Right cell of top row
        await world_service.place_wall(Position(6, 6), Direction.NORTH)
        await world_service.place_wall(Position(6, 6), Direction.EAST)
        await world_service.place_wall(Position(6, 6), Direction.SOUTH)

        # Wall between (5,5) and (6,5) to close the L
        await world_service.place_wall(Position(5, 5), Direction.EAST)

        structure = await world_service.detect_structure_at(Position(5, 5))

        assert structure is not None
        assert structure.size == 3
        assert Position(5, 5) in structure.interior_cells
        assert Position(5, 6) in structure.interior_cells
        assert Position(6, 6) in structure.interior_cells

    async def test_save_and_get_structure(self, world_service: WorldService):
        """Should save structure and update interior cells."""
        # Create a simple 1-cell enclosure
        await world_service.place_wall(Position(10, 10), Direction.NORTH)
        await world_service.place_wall(Position(10, 10), Direction.SOUTH)
        await world_service.place_wall(Position(10, 10), Direction.EAST)
        await world_service.place_wall(Position(10, 10), Direction.WEST)

        structure = await world_service.detect_structure_at(Position(10, 10))
        assert structure is not None

        # Save it
        await world_service.save_structure(structure)

        # Interior cell should reference structure
        cell = await world_service.get_cell(Position(10, 10))
        assert cell.structure_id == structure.id

        # Get structure at position
        retrieved = await world_service.get_structure_at(Position(10, 10))
        assert retrieved is not None
        assert retrieved.id == structure.id

    async def test_delete_structure_clears_cell_references(
        self, world_service: WorldService
    ):
        """Should clear structure_id from interior cells on delete."""
        # Create and save a structure
        await world_service.place_wall(Position(10, 10), Direction.NORTH)
        await world_service.place_wall(Position(10, 10), Direction.SOUTH)
        await world_service.place_wall(Position(10, 10), Direction.EAST)
        await world_service.place_wall(Position(10, 10), Direction.WEST)

        structure = await world_service.detect_structure_at(Position(10, 10))
        await world_service.save_structure(structure)

        # Delete it
        await world_service.delete_structure(structure.id)

        # Cell should no longer reference structure
        cell = await world_service.get_cell(Position(10, 10))
        assert cell.structure_id is None


class TestNamedPlaces:
    """Test place naming."""

    async def test_name_place(self, world_service: WorldService):
        """Should name a location."""
        await world_service.name_place("The Grove", Position(25, 30))

        pos = await world_service.get_place_position("The Grove")
        assert pos == Position(25, 30)

    async def test_name_place_updates_cell(self, world_service: WorldService):
        """Should update cell's place_name."""
        await world_service.name_place("The Grove", Position(25, 30))

        cell = await world_service.get_cell(Position(25, 30))
        assert cell.place_name == "The Grove"

    async def test_get_place_position_not_found(self, world_service: WorldService):
        """Should return None for unknown place."""
        pos = await world_service.get_place_position("Unknown")
        assert pos is None

    async def test_get_all_named_places(self, world_service: WorldService):
        """Should return all named places."""
        await world_service.name_place("Place A", Position(1, 1))
        await world_service.name_place("Place B", Position(2, 2))

        places = await world_service.get_all_named_places()
        assert len(places) == 2
        assert places["Place A"] == Position(1, 1)
        assert places["Place B"] == Position(2, 2)

    async def test_remove_place_name(self, world_service: WorldService):
        """Should remove named place."""
        await world_service.name_place("The Grove", Position(25, 30))
        await world_service.remove_place_name("The Grove")

        pos = await world_service.get_place_position("The Grove")
        assert pos is None

    async def test_name_place_invalid_position(self, world_service: WorldService):
        """Should raise error for invalid position."""
        with pytest.raises(InvalidPositionError):
            await world_service.name_place("Bad Place", Position(600, 600))


class TestMovement:
    """Test movement validation."""

    async def test_is_position_valid(self, world_service: WorldService):
        """Should check if position is in bounds."""
        assert await world_service.is_position_valid(Position(50, 50)) is True
        assert await world_service.is_position_valid(Position(0, 0)) is True
        assert await world_service.is_position_valid(Position(499, 499)) is True
        assert await world_service.is_position_valid(Position(500, 500)) is False
        assert await world_service.is_position_valid(Position(-1, 0)) is False

    async def test_is_position_passable_grass(self, world_service: WorldService):
        """Should return True for passable terrain."""
        assert await world_service.is_position_passable(Position(50, 50)) is True

    async def test_is_position_passable_water(self, world_service: WorldService):
        """Should return False for impassable terrain."""
        cell = Cell(position=Position(10, 10), terrain=Terrain.WATER)
        await world_service._world_repo.set_cell(cell)

        assert await world_service.is_position_passable(Position(10, 10)) is False

    async def test_is_position_passable_with_blocking_object(
        self, world_service: WorldService
    ):
        """Should return False if blocking object present."""
        # Place an impassable object
        item = PlacedItem(
            id=ObjectId("block-1"),
            position=Position(10, 10),
            item_type="boulder",
            passable=False,
            created_tick=0,
        )
        await world_service.place_object(item)

        assert await world_service.is_position_passable(Position(10, 10)) is False

    async def test_can_move_blocked_by_wall(self, world_service: WorldService):
        """Should return False when blocked by wall."""
        await world_service.place_wall(Position(10, 10), Direction.NORTH)

        assert await world_service.can_move(Position(10, 10), Direction.NORTH) is False

    async def test_can_move_allowed_through_door(self, world_service: WorldService):
        """Should return True when door allows passage."""
        await world_service.place_door(Position(10, 10), Direction.NORTH)

        assert await world_service.can_move(Position(10, 10), Direction.NORTH) is True

    async def test_can_move_blocked_by_terrain(self, world_service: WorldService):
        """Should return False when destination terrain is impassable."""
        cell = Cell(position=Position(10, 11), terrain=Terrain.WATER)
        await world_service._world_repo.set_cell(cell)

        assert await world_service.can_move(Position(10, 10), Direction.NORTH) is False

    async def test_can_move_blocked_by_bounds(self, world_service: WorldService):
        """Should return False when moving out of bounds."""
        assert await world_service.can_move(Position(0, 0), Direction.SOUTH) is False
        assert await world_service.can_move(Position(499, 499), Direction.NORTH) is False

    async def test_can_move_success(self, world_service: WorldService):
        """Should return True when movement is valid."""
        assert await world_service.can_move(Position(50, 50), Direction.NORTH) is True
        assert await world_service.can_move(Position(50, 50), Direction.SOUTH) is True
        assert await world_service.can_move(Position(50, 50), Direction.EAST) is True
        assert await world_service.can_move(Position(50, 50), Direction.WEST) is True
