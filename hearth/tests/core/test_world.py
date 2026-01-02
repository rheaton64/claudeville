"""Tests for Cell and Grid models."""

import pytest

from hearth.core import (
    Cell,
    Grid,
    Position,
    Direction,
    Rect,
    Terrain,
    ObjectId,
)


class TestCell:
    """Tests for Cell model."""

    def test_create_default_cell(self):
        """Can create a cell with just position."""
        cell = Cell(position=Position(5, 5))
        assert cell.position == Position(5, 5)
        assert cell.terrain == Terrain.GRASS
        assert cell.walls == frozenset()
        assert cell.doors == frozenset()
        assert cell.place_name is None
        assert cell.structure_id is None

    def test_create_cell_with_terrain(self):
        """Can create a cell with specific terrain."""
        cell = Cell(position=Position(5, 5), terrain=Terrain.WATER)
        assert cell.terrain == Terrain.WATER

    def test_cell_is_frozen(self):
        """Cell is immutable."""
        cell = Cell(position=Position(5, 5))
        with pytest.raises(Exception):  # Pydantic ValidationError
            cell.terrain = Terrain.WATER

    def test_has_wall(self):
        """Check for wall on edge."""
        cell = Cell(position=Position(5, 5), walls=frozenset({Direction.NORTH}))
        assert cell.has_wall(Direction.NORTH)
        assert not cell.has_wall(Direction.SOUTH)

    def test_has_door(self):
        """Check for door on edge."""
        cell = Cell(
            position=Position(5, 5),
            walls=frozenset({Direction.NORTH}),
            doors=frozenset({Direction.NORTH}),
        )
        assert cell.has_door(Direction.NORTH)
        assert not cell.has_door(Direction.SOUTH)

    def test_can_exit_no_wall(self):
        """Can exit where there's no wall."""
        cell = Cell(position=Position(5, 5))
        assert cell.can_exit(Direction.NORTH)
        assert cell.can_exit(Direction.SOUTH)

    def test_can_exit_with_wall(self):
        """Cannot exit through wall."""
        cell = Cell(position=Position(5, 5), walls=frozenset({Direction.NORTH}))
        assert not cell.can_exit(Direction.NORTH)
        assert cell.can_exit(Direction.SOUTH)

    def test_can_exit_with_door(self):
        """Can exit through door in wall."""
        cell = Cell(
            position=Position(5, 5),
            walls=frozenset({Direction.NORTH}),
            doors=frozenset({Direction.NORTH}),
        )
        assert cell.can_exit(Direction.NORTH)

    def test_with_wall(self):
        """Add wall returns new cell."""
        cell = Cell(position=Position(5, 5))
        new_cell = cell.with_wall(Direction.NORTH)

        assert not cell.has_wall(Direction.NORTH)  # Original unchanged
        assert new_cell.has_wall(Direction.NORTH)

    def test_without_wall(self):
        """Remove wall returns new cell."""
        cell = Cell(position=Position(5, 5), walls=frozenset({Direction.NORTH}))
        new_cell = cell.without_wall(Direction.NORTH)

        assert cell.has_wall(Direction.NORTH)  # Original unchanged
        assert not new_cell.has_wall(Direction.NORTH)

    def test_without_wall_removes_door(self):
        """Removing wall also removes door."""
        cell = Cell(
            position=Position(5, 5),
            walls=frozenset({Direction.NORTH}),
            doors=frozenset({Direction.NORTH}),
        )
        new_cell = cell.without_wall(Direction.NORTH)

        assert not new_cell.has_wall(Direction.NORTH)
        assert not new_cell.has_door(Direction.NORTH)

    def test_with_door_adds_wall(self):
        """Adding door also adds wall if needed."""
        cell = Cell(position=Position(5, 5))
        new_cell = cell.with_door(Direction.NORTH)

        assert new_cell.has_wall(Direction.NORTH)
        assert new_cell.has_door(Direction.NORTH)

    def test_without_door_keeps_wall(self):
        """Removing door keeps wall."""
        cell = Cell(
            position=Position(5, 5),
            walls=frozenset({Direction.NORTH}),
            doors=frozenset({Direction.NORTH}),
        )
        new_cell = cell.without_door(Direction.NORTH)

        assert new_cell.has_wall(Direction.NORTH)
        assert not new_cell.has_door(Direction.NORTH)

    def test_with_terrain(self):
        """Change terrain returns new cell."""
        cell = Cell(position=Position(5, 5))
        new_cell = cell.with_terrain(Terrain.WATER)

        assert cell.terrain == Terrain.GRASS
        assert new_cell.terrain == Terrain.WATER

    def test_with_place_name(self):
        """Set place name returns new cell."""
        cell = Cell(position=Position(5, 5))
        new_cell = cell.with_place_name("The Old Oak")

        assert cell.place_name is None
        assert new_cell.place_name == "The Old Oak"

    def test_with_structure_id(self):
        """Set structure ID returns new cell."""
        cell = Cell(position=Position(5, 5))
        structure_id = ObjectId("test-structure-id")
        new_cell = cell.with_structure_id(structure_id)

        assert cell.structure_id is None
        assert new_cell.structure_id == structure_id


class TestGrid:
    """Tests for Grid model."""

    def test_create_default_grid(self):
        """Can create a grid with default size."""
        grid = Grid()
        assert grid.width == 100
        assert grid.height == 100
        assert len(grid.cells) == 0

    def test_create_grid_with_dimensions(self):
        """Can create a grid with custom dimensions."""
        grid = Grid(width=50, height=50)
        assert grid.width == 50
        assert grid.height == 50

    def test_get_cell_returns_default(self):
        """Getting unset cell returns default grass cell."""
        grid = Grid()
        cell = grid.get_cell(Position(10, 10))

        assert cell.position == Position(10, 10)
        assert cell.terrain == Terrain.GRASS
        assert cell.walls == frozenset()

    def test_set_cell(self):
        """Setting a cell returns new grid."""
        grid = Grid()
        cell = Cell(position=Position(10, 10), terrain=Terrain.WATER)
        new_grid = grid.set_cell(cell)

        assert Position(10, 10) not in grid.cells
        assert Position(10, 10) in new_grid.cells
        assert new_grid.get_cell(Position(10, 10)).terrain == Terrain.WATER

    def test_set_default_cell_removes_from_storage(self):
        """Setting a default cell removes it from storage."""
        grid = Grid()
        water_cell = Cell(position=Position(10, 10), terrain=Terrain.WATER)
        grid = grid.set_cell(water_cell)
        assert Position(10, 10) in grid.cells

        grass_cell = Cell(position=Position(10, 10))  # Default
        grid = grid.set_cell(grass_cell)
        assert Position(10, 10) not in grid.cells

    def test_update_cell(self):
        """Update cell with kwargs."""
        grid = Grid()
        cell = Cell(position=Position(10, 10), terrain=Terrain.WATER)
        grid = grid.set_cell(cell)

        new_grid = grid.update_cell(Position(10, 10), place_name="Lake")
        assert new_grid.get_cell(Position(10, 10)).place_name == "Lake"
        assert new_grid.get_cell(Position(10, 10)).terrain == Terrain.WATER

    def test_cells_in_rect(self):
        """Get all cells in rectangle."""
        grid = Grid(width=10, height=10)
        rect = Rect(2, 2, 4, 4)
        cells = grid.cells_in_rect(rect)

        assert len(cells) == 9  # 3x3
        positions = {c.position for c in cells}
        assert Position(2, 2) in positions
        assert Position(4, 4) in positions

    def test_cells_in_rect_clamped(self):
        """Rectangle is clamped to grid bounds."""
        grid = Grid(width=10, height=10)
        rect = Rect(-5, -5, 5, 5)
        cells = grid.cells_in_rect(rect)

        # Should be clamped to 0,0 -> 5,5 = 6x6 = 36 cells
        assert len(cells) == 36
        positions = {c.position for c in cells}
        assert Position(0, 0) in positions
        assert Position(-1, 0) not in positions

    def test_stored_cells_in_rect(self):
        """Get only stored cells in rectangle."""
        grid = Grid()
        water_cell = Cell(position=Position(3, 3), terrain=Terrain.WATER)
        grid = grid.set_cell(water_cell)

        rect = Rect(0, 0, 10, 10)
        stored = grid.stored_cells_in_rect(rect)

        assert len(stored) == 1
        assert stored[0].position == Position(3, 3)

    def test_is_valid_position(self):
        """Check position validity."""
        grid = Grid(width=10, height=10)

        assert grid.is_valid_position(Position(0, 0))
        assert grid.is_valid_position(Position(9, 9))
        assert not grid.is_valid_position(Position(10, 0))
        assert not grid.is_valid_position(Position(0, 10))
        assert not grid.is_valid_position(Position(-1, 0))

    def test_is_passable(self):
        """Check terrain passability."""
        grid = Grid()
        water_cell = Cell(position=Position(5, 5), terrain=Terrain.WATER)
        grid = grid.set_cell(water_cell)

        assert grid.is_passable(Position(3, 3))  # Default grass
        assert not grid.is_passable(Position(5, 5))  # Water
        assert not grid.is_passable(Position(100, 100))  # Out of bounds

    def test_can_move_simple(self):
        """Can move between adjacent grass cells."""
        grid = Grid()

        assert grid.can_move(Position(5, 5), Direction.NORTH)
        assert grid.can_move(Position(5, 5), Direction.SOUTH)
        assert grid.can_move(Position(5, 5), Direction.EAST)
        assert grid.can_move(Position(5, 5), Direction.WEST)

    def test_can_move_blocked_by_terrain(self):
        """Cannot move into impassable terrain."""
        grid = Grid()
        water_cell = Cell(position=Position(5, 6), terrain=Terrain.WATER)
        grid = grid.set_cell(water_cell)

        assert not grid.can_move(Position(5, 5), Direction.NORTH)

    def test_can_move_blocked_by_bounds(self):
        """Cannot move out of bounds."""
        grid = Grid(width=10, height=10)

        assert not grid.can_move(Position(0, 5), Direction.WEST)
        assert not grid.can_move(Position(9, 5), Direction.EAST)
        assert not grid.can_move(Position(5, 0), Direction.SOUTH)
        assert not grid.can_move(Position(5, 9), Direction.NORTH)

    def test_can_move_blocked_by_wall_source(self):
        """Cannot move through wall on source cell."""
        grid = Grid()
        walled_cell = Cell(position=Position(5, 5), walls=frozenset({Direction.NORTH}))
        grid = grid.set_cell(walled_cell)

        assert not grid.can_move(Position(5, 5), Direction.NORTH)
        assert grid.can_move(Position(5, 5), Direction.SOUTH)

    def test_can_move_blocked_by_wall_destination(self):
        """Cannot move through wall on destination cell."""
        grid = Grid()
        walled_cell = Cell(position=Position(5, 6), walls=frozenset({Direction.SOUTH}))
        grid = grid.set_cell(walled_cell)

        assert not grid.can_move(Position(5, 5), Direction.NORTH)

    def test_can_move_through_door(self):
        """Can move through door in wall."""
        grid = Grid()
        doored_cell = Cell(
            position=Position(5, 5),
            walls=frozenset({Direction.NORTH}),
            doors=frozenset({Direction.NORTH}),
        )
        grid = grid.set_cell(doored_cell)

        assert grid.can_move(Position(5, 5), Direction.NORTH)

    def test_with_dimensions(self):
        """Resize grid removes out-of-bounds cells."""
        grid = Grid(width=20, height=20)
        cell1 = Cell(position=Position(5, 5), terrain=Terrain.WATER)
        cell2 = Cell(position=Position(15, 15), terrain=Terrain.WATER)
        grid = grid.set_cell(cell1)
        grid = grid.set_cell(cell2)

        smaller_grid = grid.with_dimensions(10, 10)

        assert smaller_grid.width == 10
        assert smaller_grid.height == 10
        assert Position(5, 5) in smaller_grid.cells
        assert Position(15, 15) not in smaller_grid.cells
