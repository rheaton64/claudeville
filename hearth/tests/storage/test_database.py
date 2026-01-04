"""Tests for Database class."""

from pathlib import Path

import pytest

from storage.database import Database


class TestDatabaseConnection:
    """Test database connection management."""

    async def test_connect_creates_file(self, temp_data_dir: Path):
        """Database file should be created on connect."""
        db_path = temp_data_dir / "test.db"
        db = Database(db_path)

        assert not db_path.exists()
        await db.connect()
        assert db_path.exists()
        await db.close()

    async def test_connect_in_memory(self):
        """In-memory database should work."""
        db = Database(Path(":memory:"))
        await db.connect()
        await db.execute("CREATE TABLE test (id INTEGER)")
        await db.close()

    async def test_context_manager(self, temp_data_dir: Path):
        """Async context manager should work."""
        db_path = temp_data_dir / "test.db"
        async with Database(db_path) as db:
            await db.execute("CREATE TABLE test (id INTEGER)")
        # Should be closed after context

    async def test_double_connect_is_safe(self, temp_data_dir: Path):
        """Connecting twice should not error."""
        db = Database(temp_data_dir / "test.db")
        await db.connect()
        await db.connect()  # Should not error
        await db.close()


class TestDatabaseOperations:
    """Test database CRUD operations."""

    async def test_execute_and_fetch(self, db: Database):
        """Basic execute and fetch should work."""
        await db.execute("CREATE TABLE test (id INTEGER, name TEXT)")
        await db.execute("INSERT INTO test VALUES (1, 'foo')")
        await db.execute("INSERT INTO test VALUES (2, 'bar')")
        await db.commit()

        row = await db.fetch_one("SELECT * FROM test WHERE id = ?", (1,))
        assert row is not None
        assert row["id"] == 1
        assert row["name"] == "foo"

        rows = await db.fetch_all("SELECT * FROM test ORDER BY id")
        assert len(rows) == 2
        assert rows[0]["name"] == "foo"
        assert rows[1]["name"] == "bar"

    async def test_fetch_one_returns_none(self, db: Database):
        """Fetch one should return None for no results."""
        await db.execute("CREATE TABLE test (id INTEGER)")
        row = await db.fetch_one("SELECT * FROM test WHERE id = 999")
        assert row is None

    async def test_executemany(self, db: Database):
        """Executemany should insert multiple rows."""
        await db.execute("CREATE TABLE test (id INTEGER, name TEXT)")
        await db.executemany(
            "INSERT INTO test VALUES (?, ?)",
            [(1, "a"), (2, "b"), (3, "c")],
        )
        await db.commit()

        rows = await db.fetch_all("SELECT * FROM test")
        assert len(rows) == 3


class TestDatabaseTransactions:
    """Test transaction support."""

    async def test_transaction_commits(self, db: Database):
        """Transaction should commit on success."""
        await db.execute("CREATE TABLE test (id INTEGER)")

        async with db.transaction():
            await db.execute("INSERT INTO test VALUES (1)")
            await db.execute("INSERT INTO test VALUES (2)")

        rows = await db.fetch_all("SELECT * FROM test")
        assert len(rows) == 2

    async def test_transaction_rollback_on_error(self, db: Database):
        """Transaction should rollback on error."""
        await db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
        await db.execute("INSERT INTO test VALUES (1)")
        await db.commit()

        with pytest.raises(Exception):
            async with db.transaction():
                await db.execute("INSERT INTO test VALUES (2)")
                # Force an error
                await db.execute("INSERT INTO test VALUES (1)")  # Duplicate PK

        # Only original row should exist
        rows = await db.fetch_all("SELECT * FROM test")
        assert len(rows) == 1


class TestSchemaVersion:
    """Test schema version tracking."""

    async def test_get_version_no_table(self, db: Database):
        """Should return 0 if no schema_version table."""
        version = await db.get_schema_version()
        assert version == 0

    async def test_set_and_get_version(self, db: Database):
        """Should track schema version."""
        await db.execute(
            "CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT)"
        )
        await db.commit()

        assert await db.get_schema_version() == 0

        await db.set_schema_version(1)
        assert await db.get_schema_version() == 1

        await db.set_schema_version(2)
        assert await db.get_schema_version() == 2

    async def test_table_exists(self, db: Database):
        """Should detect table existence."""
        assert not await db.table_exists("test")
        await db.execute("CREATE TABLE test (id INTEGER)")
        assert await db.table_exists("test")
