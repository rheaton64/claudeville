"""Repository layer for Hearth storage.

Repositories provide domain-specific data access patterns on top of the
raw database. Each repository handles one domain area:
- WorldRepository: Grid cells, world state, named places, structures
- AgentRepository: Agents, inventory (stacks and items)
- ObjectRepository: World objects (signs, placed items)
- ConversationRepository: Conversations, turns, invitations
"""

from .base import BaseRepository
from .world import WorldRepository
from .agent import AgentRepository
from .object import ObjectRepository
from .conversation import ConversationRepository

__all__ = [
    "BaseRepository",
    "WorldRepository",
    "AgentRepository",
    "ObjectRepository",
    "ConversationRepository",
]
