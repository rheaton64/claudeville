"""
Observer layer - Human interface for the village.

Provides:
- ObserverAPI: Query/command interface for TUI and CLI
- Display snapshots: Read-only views of village state
"""

from .snapshots import (
    AgentDisplaySnapshot,
    ConversationDisplaySnapshot,
    InviteDisplaySnapshot,
    ScheduleDisplaySnapshot,
    TimeDisplaySnapshot,
    VillageDisplaySnapshot,
)
from .api import ObserverAPI, ObserverError

__all__ = [
    "ObserverAPI",
    "ObserverError",
    "AgentDisplaySnapshot",
    "ConversationDisplaySnapshot",
    "InviteDisplaySnapshot",
    "ScheduleDisplaySnapshot",
    "TimeDisplaySnapshot",
    "VillageDisplaySnapshot",
]
