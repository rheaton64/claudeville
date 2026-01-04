"""Fixtures for observe tests."""

from pathlib import Path
from typing import AsyncGenerator

import pytest_asyncio

from storage import Storage
from services import WorldService, AgentService
from observe import ObserverAPI


@pytest_asyncio.fixture
async def storage(temp_data_dir: Path) -> AsyncGenerator[Storage, None]:
    """Create a fully initialized Storage instance."""
    store = Storage(temp_data_dir)
    await store.connect()
    yield store
    await store.close()


@pytest_asyncio.fixture
async def world_service(storage: Storage) -> WorldService:
    """Create WorldService with connected storage."""
    return WorldService(storage)


@pytest_asyncio.fixture
async def agent_service(storage: Storage) -> AgentService:
    """Create AgentService with connected storage."""
    return AgentService(storage)


@pytest_asyncio.fixture
async def observer_api(
    storage: Storage, world_service: WorldService, agent_service: AgentService
) -> ObserverAPI:
    """Create ObserverAPI with all dependencies."""
    return ObserverAPI(storage, world_service, agent_service)
