"""Structure model for Hearth.

Structures are detected when walls form enclosed areas. They provide
social boundaries (privacy) and may have other effects in the future.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .types import Position, ObjectId, AgentName
from .objects import generate_object_id


class Structure(BaseModel):
    """A detected enclosed structure formed by walls.

    Structures are automatically detected when walls form an enclosure.
    Interior cells can be marked as private (social boundary) and
    the structure can be named.
    """

    model_config = ConfigDict(frozen=True)

    id: ObjectId
    name: str | None = None
    interior_cells: frozenset[Position]
    created_by: AgentName | None = None
    is_private: bool = False

    @property
    def size(self) -> int:
        """Number of cells inside the structure."""
        return len(self.interior_cells)

    def contains(self, pos: Position) -> bool:
        """Check if a position is inside this structure."""
        return pos in self.interior_cells

    def with_name(self, name: str | None) -> Structure:
        """Return a new structure with the given name."""
        return self.model_copy(update={"name": name})

    def with_privacy(self, is_private: bool) -> Structure:
        """Return a new structure with updated privacy setting."""
        return self.model_copy(update={"is_private": is_private})

    @classmethod
    def create(
        cls,
        interior_cells: frozenset[Position],
        created_by: AgentName | None = None,
        name: str | None = None,
        is_private: bool = False,
    ) -> Structure:
        """Create a new structure with a generated ID."""
        return cls(
            id=generate_object_id(),
            name=name,
            interior_cells=interior_cells,
            created_by=created_by,
            is_private=is_private,
        )
