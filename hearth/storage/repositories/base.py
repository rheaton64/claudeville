"""Base repository with common patterns.

Provides JSON serialization helpers and position utilities used by
all domain-specific repositories.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from core.types import Position, Direction, AgentName

if TYPE_CHECKING:
    from ..database import Database


class BaseRepository:
    """Base class for all repositories.

    Provides:
    - Database reference
    - JSON encoding/decoding helpers
    - Position conversion utilities
    - Direction serialization
    """

    def __init__(self, db: Database):
        """Initialize repository with database connection.

        Args:
            db: Connected database instance
        """
        self.db = db

    # --- JSON Helpers ---

    def _encode_json(self, obj: Any) -> str:
        """Encode Python object to JSON string.

        Args:
            obj: Object to encode (must be JSON-serializable)

        Returns:
            JSON string
        """
        return json.dumps(obj, separators=(",", ":"))

    def _decode_json(self, s: str | None) -> Any:
        """Decode JSON string to Python object.

        Args:
            s: JSON string, or None

        Returns:
            Decoded object, or None if input was None
        """
        if s is None:
            return None
        return json.loads(s)

    # --- Position Helpers ---

    def _pos_to_tuple(self, pos: Position) -> tuple[int, int]:
        """Convert Position to tuple for SQL binding.

        Args:
            pos: Position instance

        Returns:
            (x, y) tuple
        """
        return (pos.x, pos.y)

    def _tuple_to_pos(self, x: int, y: int) -> Position:
        """Convert x, y coordinates to Position.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            Position instance
        """
        return Position(x, y)

    # --- Direction Helpers ---

    def _directions_to_json(self, directions: frozenset[Direction]) -> str:
        """Encode a frozenset of Directions to JSON array.

        Args:
            directions: Frozenset of Direction enums

        Returns:
            JSON array string like '["north", "east"]'
        """
        return self._encode_json([d.value for d in directions])

    def _json_to_directions(self, s: str) -> frozenset[Direction]:
        """Decode JSON array to frozenset of Directions.

        Args:
            s: JSON array string like '["north", "east"]'

        Returns:
            Frozenset of Direction enums
        """
        values = self._decode_json(s) or []
        return frozenset(Direction(v) for v in values)

    # --- Agent Name Helpers ---

    def _agent_names_to_json(self, names: frozenset[AgentName]) -> str:
        """Encode a frozenset of agent names to JSON array.

        Args:
            names: Frozenset of AgentName values

        Returns:
            JSON array string
        """
        return self._encode_json(list(names))

    def _json_to_agent_names(self, s: str) -> frozenset[AgentName]:
        """Decode JSON array to frozenset of agent names.

        Args:
            s: JSON array string

        Returns:
            Frozenset of AgentName values
        """
        values = self._decode_json(s) or []
        return frozenset(AgentName(v) for v in values)

    # --- Position List Helpers ---

    def _positions_to_json(self, positions: tuple[Position, ...]) -> str:
        """Encode a tuple of Positions to JSON array of [x,y] pairs.

        Args:
            positions: Tuple of Position instances

        Returns:
            JSON array string like '[[1,2],[3,4]]'
        """
        return self._encode_json([[p.x, p.y] for p in positions])

    def _json_to_positions(self, s: str) -> tuple[Position, ...]:
        """Decode JSON array of [x,y] pairs to tuple of Positions.

        Args:
            s: JSON array string like '[[1,2],[3,4]]'

        Returns:
            Tuple of Position instances
        """
        pairs = self._decode_json(s) or []
        return tuple(Position(p[0], p[1]) for p in pairs)
