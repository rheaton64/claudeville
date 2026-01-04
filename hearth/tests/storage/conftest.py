"""Fixtures for storage layer tests."""

from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio

from storage.database import Database
from storage import Storage


@pytest_asyncio.fixture
async def db(temp_data_dir: Path) -> AsyncGenerator[Database, None]:
    """Create an in-memory database for testing."""
    database = Database(Path(":memory:"))
    await database.connect()
    yield database
    await database.close()


@pytest_asyncio.fixture
async def db_with_schema(temp_data_dir: Path) -> AsyncGenerator[Database, None]:
    """Create a database with schema applied."""
    database = Database(Path(":memory:"))
    await database.connect()

    # Apply schema manually
    from storage.schema import SCHEMA_V1
    await database.executescript(SCHEMA_V1)
    await database.commit()

    yield database
    await database.close()


@pytest_asyncio.fixture
async def storage(temp_data_dir: Path) -> AsyncGenerator[Storage, None]:
    """Create a fully initialized Storage instance."""
    store = Storage(temp_data_dir)
    await store.connect()
    yield store
    await store.close()
