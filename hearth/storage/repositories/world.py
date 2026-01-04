"""World repository for Hearth.

Handles persistence of grid cells, world state, named places, and structures.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.types import Position, Rect, ObjectId, AgentName
from core.terrain import Terrain, Weather
from core.world import Cell, WorldState
from core.structures import Structure

from .base import BaseRepository

if TYPE_CHECKING:
    pass


class WorldRepository(BaseRepository):
    """Repository for world grid and global state.

    Handles:
    - World state (tick, weather, dimensions)
    - Grid cells (sparse storage)
    - Named places
    - Structures
    """

    # --- World State ---

    async def get_world_state(self) -> WorldState:
        """Get current world state.

        Returns:
            WorldState with tick, weather, dimensions
        """
        row = await self.db.fetch_one("SELECT * FROM world_state WHERE id = 1")
        if row is None:
            # Return defaults if not initialized
            return WorldState(
                current_tick=0,
                weather=Weather.CLEAR,
                width=500,
                height=500,
            )
        return WorldState(
            current_tick=row["current_tick"],
            weather=Weather(row["weather"]),
            width=row["width"],
            height=row["height"],
        )

    async def set_tick(self, tick: int) -> None:
        """Update current tick.

        Args:
            tick: New tick value
        """
        await self.db.execute(
            "UPDATE world_state SET current_tick = ? WHERE id = 1",
            (tick,),
        )
        await self.db.commit()

    async def set_weather(self, weather: Weather) -> None:
        """Update weather.

        Args:
            weather: New weather value
        """
        await self.db.execute(
            "UPDATE world_state SET weather = ? WHERE id = 1",
            (weather.value,),
        )
        await self.db.commit()

    async def set_dimensions(self, width: int, height: int) -> None:
        """Update world dimensions.

        Args:
            width: New width
            height: New height
        """
        await self.db.execute(
            "UPDATE world_state SET width = ?, height = ? WHERE id = 1",
            (width, height),
        )
        await self.db.commit()

    # --- Cells ---

    async def get_cell(self, pos: Position) -> Cell:
        """Get cell at position.

        Returns default grass cell if position not in database.

        Args:
            pos: Position to query

        Returns:
            Cell at that position
        """
        row = await self.db.fetch_one(
            "SELECT * FROM cells WHERE x = ? AND y = ?",
            (pos.x, pos.y),
        )
        if row is None:
            return Cell(position=pos)

        return Cell(
            position=pos,
            terrain=Terrain(row["terrain"]),
            walls=self._json_to_directions(row["walls"]),
            doors=self._json_to_directions(row["doors"]),
            place_name=row["place_name"],
            structure_id=ObjectId(row["structure_id"]) if row["structure_id"] else None,
        )

    async def set_cell(self, cell: Cell) -> None:
        """Save cell to database.

        If cell is default (grass, no walls, etc.), removes from database.
        Otherwise inserts or updates.

        Args:
            cell: Cell to save
        """
        default = Cell(position=cell.position)

        if cell == default:
            # Remove default cells from storage
            await self.db.execute(
                "DELETE FROM cells WHERE x = ? AND y = ?",
                (cell.position.x, cell.position.y),
            )
        else:
            # Upsert non-default cell
            await self.db.execute(
                """
                INSERT INTO cells (x, y, terrain, walls, doors, place_name, structure_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(x, y) DO UPDATE SET
                    terrain = excluded.terrain,
                    walls = excluded.walls,
                    doors = excluded.doors,
                    place_name = excluded.place_name,
                    structure_id = excluded.structure_id
                """,
                (
                    cell.position.x,
                    cell.position.y,
                    cell.terrain.value,
                    self._directions_to_json(cell.walls),
                    self._directions_to_json(cell.doors),
                    cell.place_name,
                    str(cell.structure_id) if cell.structure_id else None,
                ),
            )
        await self.db.commit()

    async def set_cells_bulk(self, cells: list[Cell]) -> None:
        """Bulk insert/update cells in a single transaction.

        Much faster than calling set_cell() repeatedly.
        Only handles non-default cells (doesn't delete defaults).

        Args:
            cells: List of cells to save
        """
        if not cells:
            return

        # Prepare all rows
        rows = [
            (
                cell.position.x,
                cell.position.y,
                cell.terrain.value,
                self._directions_to_json(cell.walls),
                self._directions_to_json(cell.doors),
                cell.place_name,
                str(cell.structure_id) if cell.structure_id else None,
            )
            for cell in cells
        ]

        # Bulk insert with executemany
        await self.db.executemany(
            """
            INSERT INTO cells (x, y, terrain, walls, doors, place_name, structure_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(x, y) DO UPDATE SET
                terrain = excluded.terrain,
                walls = excluded.walls,
                doors = excluded.doors,
                place_name = excluded.place_name,
                structure_id = excluded.structure_id
            """,
            rows,
        )
        await self.db.commit()

    async def get_cells_in_rect(self, rect: Rect) -> list[Cell]:
        """Get all cells in a rectangle.

        Returns cells for all positions, creating default cells for
        positions not in database.

        Args:
            rect: Rectangle to query

        Returns:
            List of cells (one per position in rect)
        """
        # Get stored cells
        rows = await self.db.fetch_all(
            """
            SELECT * FROM cells
            WHERE x >= ? AND x <= ? AND y >= ? AND y <= ?
            """,
            (rect.min_x, rect.max_x, rect.min_y, rect.max_y),
        )

        # Build dict of stored cells
        stored: dict[Position, Cell] = {}
        for row in rows:
            pos = Position(row["x"], row["y"])
            stored[pos] = Cell(
                position=pos,
                terrain=Terrain(row["terrain"]),
                walls=self._json_to_directions(row["walls"]),
                doors=self._json_to_directions(row["doors"]),
                place_name=row["place_name"],
                structure_id=ObjectId(row["structure_id"]) if row["structure_id"] else None,
            )

        # Return all positions, using stored or default
        result = []
        for pos in rect.positions():
            if pos in stored:
                result.append(stored[pos])
            else:
                result.append(Cell(position=pos))
        return result

    async def get_stored_cells_in_rect(self, rect: Rect) -> list[Cell]:
        """Get only explicitly stored cells in a rectangle.

        More efficient when you only need non-default cells.

        Args:
            rect: Rectangle to query

        Returns:
            List of non-default cells in rect
        """
        rows = await self.db.fetch_all(
            """
            SELECT * FROM cells
            WHERE x >= ? AND x <= ? AND y >= ? AND y <= ?
            """,
            (rect.min_x, rect.max_x, rect.min_y, rect.max_y),
        )

        return [
            Cell(
                position=Position(row["x"], row["y"]),
                terrain=Terrain(row["terrain"]),
                walls=self._json_to_directions(row["walls"]),
                doors=self._json_to_directions(row["doors"]),
                place_name=row["place_name"],
                structure_id=ObjectId(row["structure_id"]) if row["structure_id"] else None,
            )
            for row in rows
        ]

    # --- Named Places ---

    async def get_named_place(self, name: str) -> Position | None:
        """Get position of a named place.

        Args:
            name: Place name to look up

        Returns:
            Position if found, None otherwise
        """
        row = await self.db.fetch_one(
            "SELECT x, y FROM named_places WHERE name = ?",
            (name,),
        )
        if row is None:
            return None
        return Position(row["x"], row["y"])

    async def set_named_place(self, name: str, pos: Position) -> None:
        """Set or update a named place.

        Also updates the cell's place_name field. If the name previously
        existed at a different position, clears the old cell's place_name.

        Args:
            name: Name for the place
            pos: Position of the place
        """
        # Check if this name already exists at a different position
        old_pos = await self.get_named_place(name)
        if old_pos is not None and old_pos != pos:
            # Clear the old cell's place_name
            old_cell = await self.get_cell(old_pos)
            if old_cell.place_name == name:
                await self.set_cell(old_cell.with_place_name(None))

        # Update named_places table
        await self.db.execute(
            """
            INSERT INTO named_places (name, x, y)
            VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET x = excluded.x, y = excluded.y
            """,
            (name, pos.x, pos.y),
        )

        # Update new cell's place_name
        cell = await self.get_cell(pos)
        await self.set_cell(cell.with_place_name(name))

    async def remove_named_place(self, name: str) -> None:
        """Remove a named place.

        Args:
            name: Name of place to remove
        """
        # Get position first
        pos = await self.get_named_place(name)
        if pos is None:
            return

        # Remove from named_places
        await self.db.execute(
            "DELETE FROM named_places WHERE name = ?",
            (name,),
        )

        # Clear cell's place_name
        cell = await self.get_cell(pos)
        if cell.place_name == name:
            await self.set_cell(cell.with_place_name(None))

        await self.db.commit()

    async def get_all_named_places(self) -> dict[str, Position]:
        """Get all named places.

        Returns:
            Dict mapping name to position
        """
        rows = await self.db.fetch_all("SELECT name, x, y FROM named_places")
        return {row["name"]: Position(row["x"], row["y"]) for row in rows}

    # --- Structures ---

    async def get_structure(self, structure_id: ObjectId) -> Structure | None:
        """Get a structure by ID.

        Args:
            structure_id: ID of structure to get

        Returns:
            Structure if found, None otherwise
        """
        row = await self.db.fetch_one(
            "SELECT * FROM structures WHERE id = ?",
            (str(structure_id),),
        )
        if row is None:
            return None

        # Parse interior_cells from JSON
        interior_cells = frozenset(self._json_to_positions(row["interior_cells"]))

        return Structure(
            id=ObjectId(row["id"]),
            name=row["name"],
            interior_cells=interior_cells,
            created_by=AgentName(row["creator"]) if row["creator"] else None,
            is_private=bool(row["is_private"]),
        )

    async def save_structure(self, structure: Structure) -> None:
        """Save or update a structure.

        Also updates cells to reference this structure.

        Args:
            structure: Structure to save
        """
        # Convert interior_cells to JSON
        interior_json = self._positions_to_json(tuple(structure.interior_cells))

        await self.db.execute(
            """
            INSERT INTO structures (id, interior_cells, creator, name, is_private)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                interior_cells = excluded.interior_cells,
                creator = excluded.creator,
                name = excluded.name,
                is_private = excluded.is_private
            """,
            (
                str(structure.id),
                interior_json,
                str(structure.created_by) if structure.created_by else None,
                structure.name,
                int(structure.is_private),
            ),
        )

        # Update cells to reference this structure
        for pos in structure.interior_cells:
            cell = await self.get_cell(pos)
            await self.set_cell(cell.with_structure_id(structure.id))

        await self.db.commit()

    async def delete_structure(self, structure_id: ObjectId) -> None:
        """Delete a structure.

        Clears structure_id from all cells that referenced it.

        Args:
            structure_id: ID of structure to delete
        """
        # Get structure first to find cells
        structure = await self.get_structure(structure_id)
        if structure is None:
            return

        # Clear cells
        for pos in structure.interior_cells:
            cell = await self.get_cell(pos)
            if cell.structure_id == structure_id:
                await self.set_cell(cell.with_structure_id(None))

        # Delete structure
        await self.db.execute(
            "DELETE FROM structures WHERE id = ?",
            (str(structure_id),),
        )
        await self.db.commit()

    async def get_structures_in_rect(self, rect: Rect) -> list[Structure]:
        """Get all structures with interior cells in a rectangle.

        Args:
            rect: Rectangle to query

        Returns:
            List of structures overlapping the rect
        """
        # Find structure IDs from cells in rect
        rows = await self.db.fetch_all(
            """
            SELECT DISTINCT structure_id FROM cells
            WHERE x >= ? AND x <= ? AND y >= ? AND y <= ?
            AND structure_id IS NOT NULL
            """,
            (rect.min_x, rect.max_x, rect.min_y, rect.max_y),
        )

        # Load each structure
        structures = []
        for row in rows:
            structure = await self.get_structure(ObjectId(row["structure_id"]))
            if structure is not None:
                structures.append(structure)
        return structures
