"""Tests for core types: Position, Direction, Rect."""

import pytest

from hearth.core import Position, Direction, Rect


class TestDirection:
    """Tests for Direction enum."""

    def test_all_directions_exist(self):
        """All four cardinal directions exist."""
        assert Direction.NORTH
        assert Direction.SOUTH
        assert Direction.EAST
        assert Direction.WEST

    def test_offset_north(self):
        """North goes up (positive y)."""
        assert Direction.NORTH.offset == (0, 1)

    def test_offset_south(self):
        """South goes down (negative y)."""
        assert Direction.SOUTH.offset == (0, -1)

    def test_offset_east(self):
        """East goes right (positive x)."""
        assert Direction.EAST.offset == (1, 0)

    def test_offset_west(self):
        """West goes left (negative x)."""
        assert Direction.WEST.offset == (-1, 0)

    def test_opposites(self):
        """Each direction has its opposite."""
        assert Direction.NORTH.opposite == Direction.SOUTH
        assert Direction.SOUTH.opposite == Direction.NORTH
        assert Direction.EAST.opposite == Direction.WEST
        assert Direction.WEST.opposite == Direction.EAST


class TestPosition:
    """Tests for Position NamedTuple."""

    def test_create_position(self):
        """Can create a position with x and y."""
        pos = Position(5, 10)
        assert pos.x == 5
        assert pos.y == 10

    def test_position_is_hashable(self):
        """Positions can be used as dict keys."""
        pos1 = Position(1, 2)
        pos2 = Position(1, 2)
        pos3 = Position(3, 4)

        d = {pos1: "a", pos3: "b"}
        assert d[pos2] == "a"  # pos2 equals pos1

    def test_add_direction(self):
        """Can add a direction to get adjacent position."""
        pos = Position(5, 5)

        assert pos + Direction.NORTH == Position(5, 6)
        assert pos + Direction.SOUTH == Position(5, 4)
        assert pos + Direction.EAST == Position(6, 5)
        assert pos + Direction.WEST == Position(4, 5)

    def test_add_tuple(self):
        """Can add a tuple offset."""
        pos = Position(5, 5)
        assert pos + (2, 3) == Position(7, 8)
        assert pos + (-1, -1) == Position(4, 4)

    def test_subtract_direction(self):
        """Can subtract a direction."""
        pos = Position(5, 5)

        assert pos - Direction.NORTH == Position(5, 4)
        assert pos - Direction.SOUTH == Position(5, 6)

    def test_subtract_tuple(self):
        """Can subtract a tuple offset."""
        pos = Position(5, 5)
        assert pos - (2, 3) == Position(3, 2)

    def test_distance_to(self):
        """Manhattan distance calculation."""
        pos1 = Position(0, 0)
        pos2 = Position(3, 4)
        assert pos1.distance_to(pos2) == 7

        # Same position
        assert pos1.distance_to(pos1) == 0

        # Negative coordinates
        pos3 = Position(-2, -3)
        assert pos1.distance_to(pos3) == 5

    def test_direction_to_same_position(self):
        """Direction to self is None."""
        pos = Position(5, 5)
        assert pos.direction_to(pos) is None

    def test_direction_to_cardinal(self):
        """Direction to cardinal neighbors."""
        pos = Position(5, 5)

        assert pos.direction_to(Position(5, 10)) == Direction.NORTH
        assert pos.direction_to(Position(5, 0)) == Direction.SOUTH
        assert pos.direction_to(Position(10, 5)) == Direction.EAST
        assert pos.direction_to(Position(0, 5)) == Direction.WEST

    def test_direction_to_diagonal_favors_x(self):
        """Diagonal direction favors x-axis on ties."""
        pos = Position(5, 5)

        # Equal distance: favor x-axis
        assert pos.direction_to(Position(6, 6)) == Direction.EAST
        assert pos.direction_to(Position(4, 4)) == Direction.WEST

        # Greater y difference: go vertical
        assert pos.direction_to(Position(6, 8)) == Direction.NORTH
        assert pos.direction_to(Position(4, 2)) == Direction.SOUTH

    def test_neighbors(self):
        """Get all adjacent positions."""
        pos = Position(5, 5)
        neighbors = pos.neighbors()

        assert neighbors[Direction.NORTH] == Position(5, 6)
        assert neighbors[Direction.SOUTH] == Position(5, 4)
        assert neighbors[Direction.EAST] == Position(6, 5)
        assert neighbors[Direction.WEST] == Position(4, 5)
        assert len(neighbors) == 4

    def test_in_bounds(self):
        """Boundary checking."""
        assert Position(0, 0).in_bounds(10, 10)
        assert Position(9, 9).in_bounds(10, 10)
        assert not Position(10, 10).in_bounds(10, 10)
        assert not Position(-1, 5).in_bounds(10, 10)
        assert not Position(5, -1).in_bounds(10, 10)


class TestRect:
    """Tests for Rect NamedTuple."""

    def test_create_rect(self):
        """Can create a rectangle."""
        rect = Rect(0, 0, 10, 10)
        assert rect.min_x == 0
        assert rect.min_y == 0
        assert rect.max_x == 10
        assert rect.max_y == 10

    def test_contains(self):
        """Position containment check."""
        rect = Rect(5, 5, 15, 15)

        # Inside
        assert rect.contains(Position(10, 10))
        assert rect.contains(Position(5, 5))
        assert rect.contains(Position(15, 15))

        # Outside
        assert not rect.contains(Position(4, 10))
        assert not rect.contains(Position(10, 4))
        assert not rect.contains(Position(16, 10))
        assert not rect.contains(Position(10, 16))

    def test_expand(self):
        """Expand rectangle by radius."""
        rect = Rect(5, 5, 10, 10)
        expanded = rect.expand(2)

        assert expanded.min_x == 3
        assert expanded.min_y == 3
        assert expanded.max_x == 12
        assert expanded.max_y == 12

    def test_clamp(self):
        """Clamp rectangle to grid bounds."""
        rect = Rect(-5, -5, 15, 15)
        clamped = rect.clamp(10, 10)

        assert clamped.min_x == 0
        assert clamped.min_y == 0
        assert clamped.max_x == 9
        assert clamped.max_y == 9

    def test_around(self):
        """Create rectangle centered on position."""
        rect = Rect.around(Position(10, 10), 3)

        assert rect.min_x == 7
        assert rect.min_y == 7
        assert rect.max_x == 13
        assert rect.max_y == 13

    def test_positions(self):
        """Get all positions in rectangle."""
        rect = Rect(0, 0, 2, 1)
        positions = rect.positions()

        assert len(positions) == 6  # 3 x 2
        assert Position(0, 0) in positions
        assert Position(2, 1) in positions
        assert Position(1, 0) in positions

    def test_dimensions(self):
        """Width and height properties."""
        rect = Rect(5, 5, 10, 15)
        assert rect.width == 6  # 10 - 5 + 1
        assert rect.height == 11  # 15 - 5 + 1
