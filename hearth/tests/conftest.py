"""Shared test fixtures for Hearth."""

import tempfile
from pathlib import Path

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (skipped by default, run with --run-slow)")


def pytest_addoption(parser):
    """Add --run-slow option to pytest."""
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="Run slow tests (skipped by default)",
    )


def pytest_collection_modifyitems(config, items):
    """Skip slow tests unless --run-slow is passed."""
    if config.getoption("--run-slow"):
        # --run-slow given: don't skip slow tests
        return

    skip_slow = pytest.mark.skip(reason="Slow test (use --run-slow to run)")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)


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
