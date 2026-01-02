"""Basic package tests for Hearth."""

import pytest


def test_package_imports():
    """Test that the package can be imported."""
    import hearth
    assert hearth.__version__ == "0.1.0"


def test_core_imports():
    """Test that core subpackage can be imported."""
    import hearth.core


def test_engine_imports():
    """Test that engine subpackage can be imported."""
    import hearth.engine


def test_services_imports():
    """Test that services subpackage can be imported."""
    import hearth.services


def test_storage_imports():
    """Test that storage subpackage can be imported."""
    import hearth.storage


def test_adapters_imports():
    """Test that adapters subpackage can be imported."""
    import hearth.adapters


def test_generation_imports():
    """Test that generation subpackage can be imported."""
    import hearth.generation


def test_observer_imports():
    """Test that observer subpackage can be imported."""
    import hearth.observer
    import hearth.observer.tui


def test_logging_config_imports():
    """Test that logging_config can be imported."""
    from hearth.logging_config import setup_logging, get_logger


def test_logging_setup(temp_data_dir):
    """Test that logging can be set up."""
    from hearth.logging_config import setup_logging

    log_path = setup_logging(temp_data_dir)
    assert log_path.exists()
    assert log_path.name == "debug.log"


def test_get_logger():
    """Test logger creation."""
    from hearth.logging_config import get_logger

    logger = get_logger("test_module")
    assert logger.name == "hearth.test_module"

    # Already prefixed should stay as-is
    logger2 = get_logger("hearth.something")
    assert logger2.name == "hearth.something"
