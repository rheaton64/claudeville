"""Shared test fixtures for Hearth."""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_data_dir() -> Path:
    """Create a temporary data directory for tests."""
    with tempfile.TemporaryDirectory(prefix="hearth_test_") as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_world_dir(temp_data_dir: Path) -> Path:
    """Create a temporary world directory with standard structure."""
    # Create standard subdirectories
    (temp_data_dir / "snapshots").mkdir()
    return temp_data_dir
