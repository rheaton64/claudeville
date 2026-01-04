"""Database migration system for Hearth.

Hand-rolled migration system that tracks versions in schema_version table
and applies SQL migrations in order.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..schema import CURRENT_VERSION, get_migration_sql, get_pending_versions

if TYPE_CHECKING:
    from ..database import Database

logger = logging.getLogger(__name__)


async def ensure_schema(db: Database) -> int:
    """Ensure database schema is up to date.

    Creates tables if needed and applies any pending migrations.

    Args:
        db: Connected database instance

    Returns:
        Final schema version after migrations

    Raises:
        RuntimeError: If a migration fails
    """
    current_version = await db.get_schema_version()
    logger.info(f"Current schema version: {current_version}, target: {CURRENT_VERSION}")

    pending = get_pending_versions(current_version)
    if not pending:
        logger.debug("Schema is up to date")
        return current_version

    logger.info(f"Applying {len(pending)} migration(s): {pending}")

    for version in pending:
        sql = get_migration_sql(version)
        if sql is None:
            raise RuntimeError(f"No migration SQL for version {version}")

        logger.info(f"Applying migration v{version}...")
        try:
            await db.executescript(sql)
            await db.set_schema_version(version)
            logger.info(f"Migration v{version} applied successfully")
        except Exception as e:
            logger.error(f"Migration v{version} failed: {e}")
            raise RuntimeError(f"Migration v{version} failed: {e}") from e

    final_version = await db.get_schema_version()
    logger.info(f"Schema migration complete. Version: {final_version}")
    return final_version


async def reset_schema(db: Database) -> None:
    """Drop all tables and recreate schema from scratch.

    WARNING: This destroys all data! Use only in tests or dev.

    Args:
        db: Connected database instance
    """
    logger.warning("Resetting database schema - all data will be lost!")

    # Drop all tables in reverse dependency order
    drop_sql = """
    DROP TABLE IF EXISTS inventory_items;
    DROP TABLE IF EXISTS inventory_stacks;
    DROP TABLE IF EXISTS structures;
    DROP TABLE IF EXISTS named_places;
    DROP TABLE IF EXISTS objects;
    DROP TABLE IF EXISTS cells;
    DROP TABLE IF EXISTS agents;
    DROP TABLE IF EXISTS world_state;
    DROP TABLE IF EXISTS schema_version;
    """
    await db.executescript(drop_sql)
    await db.commit()

    # Reapply schema
    await ensure_schema(db)
