"""Database schema definitions for Hearth.

Contains the SQL schema and version tracking for migrations.
SQLite is the single source of truth for world state.
"""

from __future__ import annotations

# Current schema version - increment when adding migrations
CURRENT_VERSION = 3

# Initial schema creation SQL (version 1)
SCHEMA_V1 = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

-- World-level state (single row)
CREATE TABLE IF NOT EXISTS world_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    current_tick INTEGER NOT NULL DEFAULT 0,
    weather TEXT NOT NULL DEFAULT 'clear',
    width INTEGER NOT NULL DEFAULT 500,
    height INTEGER NOT NULL DEFAULT 500
);

-- Initialize world_state with single row
INSERT OR IGNORE INTO world_state (id) VALUES (1);

-- Grid cells (sparse - only non-default cells stored)
CREATE TABLE IF NOT EXISTS cells (
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    terrain TEXT NOT NULL DEFAULT 'grass',
    walls TEXT NOT NULL DEFAULT '[]',
    doors TEXT NOT NULL DEFAULT '[]',
    place_name TEXT,
    structure_id TEXT,
    PRIMARY KEY (x, y)
);

CREATE INDEX IF NOT EXISTS idx_cells_structure ON cells(structure_id);

-- World objects (polymorphic with discriminator)
CREATE TABLE IF NOT EXISTS objects (
    id TEXT PRIMARY KEY,
    object_type TEXT NOT NULL,
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    created_by TEXT,
    created_tick INTEGER NOT NULL DEFAULT 0,
    passable INTEGER NOT NULL DEFAULT 1,
    data TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_objects_position ON objects(x, y);
CREATE INDEX IF NOT EXISTS idx_objects_type ON objects(object_type);
CREATE INDEX IF NOT EXISTS idx_objects_creator ON objects(created_by);

-- Agents
CREATE TABLE IF NOT EXISTS agents (
    name TEXT PRIMARY KEY,
    model_id TEXT NOT NULL,
    model_display_name TEXT NOT NULL,
    personality TEXT NOT NULL DEFAULT '',
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    is_sleeping INTEGER NOT NULL DEFAULT 0,
    session_id TEXT,
    last_active_tick INTEGER NOT NULL DEFAULT 0,
    known_agents TEXT NOT NULL DEFAULT '[]',
    journey TEXT
);

-- Inventory: stackable resources
CREATE TABLE IF NOT EXISTS inventory_stacks (
    agent TEXT NOT NULL,
    item_type TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (agent, item_type),
    FOREIGN KEY (agent) REFERENCES agents(name) ON DELETE CASCADE
);

-- Inventory: unique items
CREATE TABLE IF NOT EXISTS inventory_items (
    id TEXT PRIMARY KEY,
    agent TEXT NOT NULL,
    item_type TEXT NOT NULL,
    properties TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY (agent) REFERENCES agents(name) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_inventory_items_agent ON inventory_items(agent);

-- Named places (denormalized from cells for quick lookup)
CREATE TABLE IF NOT EXISTS named_places (
    name TEXT PRIMARY KEY,
    x INTEGER NOT NULL,
    y INTEGER NOT NULL
);

-- Structures (detected enclosed areas)
CREATE TABLE IF NOT EXISTS structures (
    id TEXT PRIMARY KEY,
    interior_cells TEXT NOT NULL,
    creator TEXT,
    name TEXT,
    is_private INTEGER NOT NULL DEFAULT 0
);
"""

# Migration v2: Add quantity column to objects for PlacedItem stacks
SCHEMA_V2 = """
-- Add quantity column to objects table for stackable placed items
ALTER TABLE objects ADD COLUMN quantity INTEGER NOT NULL DEFAULT 1;
"""

# Migration v3: Add conversation system tables
SCHEMA_V3 = """
-- Conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    privacy TEXT NOT NULL DEFAULT 'public',
    started_at_tick INTEGER NOT NULL,
    created_by TEXT NOT NULL,
    ended_at_tick INTEGER,
    FOREIGN KEY (created_by) REFERENCES agents(name)
);

-- Conversation participants (many-to-many)
CREATE TABLE IF NOT EXISTS conversation_participants (
    conversation_id TEXT NOT NULL,
    agent TEXT NOT NULL,
    joined_at_tick INTEGER NOT NULL,
    left_at_tick INTEGER,
    last_turn_tick INTEGER,
    PRIMARY KEY (conversation_id, agent),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id),
    FOREIGN KEY (agent) REFERENCES agents(name)
);

-- Conversation turns (history)
CREATE TABLE IF NOT EXISTS conversation_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    speaker TEXT NOT NULL,
    message TEXT NOT NULL,
    tick INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id),
    FOREIGN KEY (speaker) REFERENCES agents(name)
);

-- Pending invitations
CREATE TABLE IF NOT EXISTS conversation_invitations (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    inviter TEXT NOT NULL,
    invitee TEXT NOT NULL,
    privacy TEXT NOT NULL DEFAULT 'public',
    created_at_tick INTEGER NOT NULL,
    expires_at_tick INTEGER NOT NULL,
    FOREIGN KEY (inviter) REFERENCES agents(name),
    FOREIGN KEY (invitee) REFERENCES agents(name)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_conv_participants_agent ON conversation_participants(agent);
CREATE INDEX IF NOT EXISTS idx_conv_turns_conv ON conversation_turns(conversation_id);
CREATE INDEX IF NOT EXISTS idx_conv_invitations_invitee ON conversation_invitations(invitee);
"""

# Map of version -> SQL to apply
MIGRATIONS: dict[int, str] = {
    1: SCHEMA_V1,
    2: SCHEMA_V2,
    3: SCHEMA_V3,
}


def get_migration_sql(version: int) -> str | None:
    """Get the SQL for a specific migration version.

    Args:
        version: The version number to get SQL for

    Returns:
        SQL string for the migration, or None if version doesn't exist
    """
    return MIGRATIONS.get(version)


def get_pending_versions(current: int) -> list[int]:
    """Get list of migration versions that need to be applied.

    Args:
        current: Current schema version in database

    Returns:
        List of version numbers to apply, in order
    """
    return [v for v in sorted(MIGRATIONS.keys()) if v > current]
