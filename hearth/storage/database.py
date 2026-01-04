"""Database connection and operations for Hearth.

Provides async SQLite access via aiosqlite with connection management,
transaction support, and schema migration handling.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterator

import aiosqlite

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

# Type alias for row data
Row = aiosqlite.Row


class Database:
    """Async SQLite database connection manager.

    Usage:
        db = Database(Path("data/world.db"))
        await db.connect()
        try:
            row = await db.fetch_one("SELECT * FROM agents WHERE name = ?", ("Ember",))
        finally:
            await db.close()

    Or with async context manager:
        async with Database(Path("data/world.db")) as db:
            row = await db.fetch_one("SELECT * FROM agents WHERE name = ?", ("Ember",))
    """

    def __init__(self, path: Path):
        """Initialize database with path.

        Args:
            path: Path to SQLite database file. Use ":memory:" for in-memory DB.
        """
        self.path = path
        self._conn: aiosqlite.Connection | None = None
        self._in_transaction: bool = False

    async def connect(self) -> None:
        """Open database connection.

        Enables WAL mode for crash safety and row factory for dict-like access.
        """
        if self._conn is not None:
            return

        # Ensure parent directory exists
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row

        # Enable WAL mode for crash safety and better concurrency
        await self._conn.execute("PRAGMA journal_mode=WAL")
        # Enable foreign key constraints
        await self._conn.execute("PRAGMA foreign_keys=ON")

        logger.debug(f"Connected to database: {self.path}")

    async def close(self) -> None:
        """Close database connection."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
            logger.debug(f"Closed database: {self.path}")

    async def __aenter__(self) -> Database:
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    @property
    def connection(self) -> aiosqlite.Connection:
        """Get the underlying connection, raising if not connected."""
        if self._conn is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._conn

    async def execute(
        self, sql: str, params: Sequence[Any] = ()
    ) -> aiosqlite.Cursor:
        """Execute SQL statement.

        Args:
            sql: SQL statement to execute
            params: Parameters to bind to the statement

        Returns:
            Cursor for the executed statement
        """
        return await self.connection.execute(sql, params)

    async def executemany(
        self, sql: str, params_seq: Sequence[Sequence[Any]]
    ) -> aiosqlite.Cursor:
        """Execute SQL statement with multiple parameter sets.

        Args:
            sql: SQL statement to execute
            params_seq: Sequence of parameter tuples

        Returns:
            Cursor for the executed statement
        """
        return await self.connection.executemany(sql, params_seq)

    async def executescript(self, sql: str) -> aiosqlite.Cursor:
        """Execute multiple SQL statements as a script.

        Args:
            sql: SQL script to execute

        Returns:
            Cursor for the executed script
        """
        return await self.connection.executescript(sql)

    async def fetch_one(
        self, sql: str, params: Sequence[Any] = ()
    ) -> Row | None:
        """Execute query and fetch single row.

        Args:
            sql: SQL query
            params: Parameters to bind

        Returns:
            Single row or None if no results
        """
        cursor = await self.execute(sql, params)
        return await cursor.fetchone()

    async def fetch_all(
        self, sql: str, params: Sequence[Any] = ()
    ) -> list[Row]:
        """Execute query and fetch all rows.

        Args:
            sql: SQL query
            params: Parameters to bind

        Returns:
            List of rows
        """
        cursor = await self.execute(sql, params)
        return await cursor.fetchall()

    async def commit(self) -> None:
        """Commit current transaction.

        If inside an explicit transaction block, this is a no-op.
        The transaction context manager handles the commit.
        """
        if not self._in_transaction:
            await self.connection.commit()

    async def rollback(self) -> None:
        """Rollback current transaction."""
        await self.connection.rollback()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        """Context manager for ACID transactions.

        Provides true transactional semantics - all operations within the
        block either commit together or rollback together on exception.

        Inner calls to commit() are ignored while inside this block.

        Usage:
            async with db.transaction():
                await db.execute("INSERT ...")
                await db.execute("UPDATE ...")
            # Auto-commits on success, auto-rollbacks on exception

        Yields:
            None

        Raises:
            RuntimeError: If transactions are nested (not supported)
        """
        if self._in_transaction:
            raise RuntimeError("Nested transactions are not supported")

        self._in_transaction = True
        await self.execute("BEGIN TRANSACTION")
        try:
            yield
            await self.execute("COMMIT")
        except Exception:
            await self.execute("ROLLBACK")
            raise
        finally:
            self._in_transaction = False

    @property
    def in_transaction(self) -> bool:
        """Check if currently inside a transaction block."""
        return self._in_transaction

    async def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database.

        Args:
            table_name: Name of the table to check

        Returns:
            True if table exists
        """
        row = await self.fetch_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return row is not None

    async def get_schema_version(self) -> int:
        """Get current schema version from database.

        Returns:
            Current schema version, or 0 if no schema_version table exists
        """
        if not await self.table_exists("schema_version"):
            return 0

        row = await self.fetch_one(
            "SELECT MAX(version) as version FROM schema_version"
        )
        if row is None or row["version"] is None:
            return 0
        return int(row["version"])

    async def set_schema_version(self, version: int) -> None:
        """Record a schema version as applied.

        Args:
            version: The version number that was applied
        """
        from datetime import datetime, timezone

        await self.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (version, datetime.now(timezone.utc).isoformat()),
        )
        await self.commit()
