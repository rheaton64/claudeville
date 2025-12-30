"""
Centralized logging configuration for engine.

Provides comprehensive debug logging to file for all engine operations.
Log file: village/debug.log (with rotation)

Usage:
    from engine.logging_config import setup_logging
    setup_logging(village_root)  # Call once at startup

All engine.* loggers will write DEBUG to file, WARNING+ to console.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime


# Global configuration
LOG_FILE_NAME = "debug.log"
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB per file
BACKUP_COUNT = 5  # Keep 5 backup files

_logging_initialized = False


def setup_logging(
    village_root: Path | str,
    log_level: int = logging.DEBUG,
    console_level: int = logging.WARNING,
) -> Path:
    """
    Configure the logging system for engine.

    Args:
        village_root: Path to village directory (log file goes here)
        log_level: Level for file logging (default: DEBUG)
        console_level: Level for console output (default: WARNING)

    Returns:
        Path to the log file
    """
    global _logging_initialized

    village_path = Path(village_root)
    village_path.mkdir(parents=True, exist_ok=True)
    log_path = village_path / LOG_FILE_NAME

    # Create root logger for engine
    root_logger = logging.getLogger("engine")
    root_logger.setLevel(logging.DEBUG)  # Capture all levels

    # Clear any existing handlers (for re-initialization)
    root_logger.handlers.clear()

    # File handler with rotation
    file_formatter = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)-35s | %(funcName)-25s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=MAX_LOG_SIZE,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Console handler (less verbose)
    console_formatter = logging.Formatter(
        fmt="%(levelname)-8s | %(name)-25s | %(message)s"
    )
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # Log startup
    if not _logging_initialized:
        root_logger.info("=" * 80)
        root_logger.info(f"ClaudeVille engine logging initialized at {datetime.now().isoformat()}")
        root_logger.info(f"Log file: {log_path.absolute()}")
        root_logger.info("=" * 80)
        _logging_initialized = True

    return log_path


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a module.

    Args:
        name: Module name (typically __name__)

    Returns:
        Logger configured as child of engine logger
    """
    # Create child logger under engine namespace
    if name.startswith("engine."):
        return logging.getLogger(name)
    else:
        return logging.getLogger(f"engine.{name}")


# =============================================================================
# Structured Logging Helpers
# =============================================================================


def log_tick(
    logger: logging.Logger,
    tick: int,
    phase: str,
    details: str | None = None,
) -> None:
    """Log tick-related activity."""
    details_str = f" | {details}" if details else ""
    logger.debug(f"TICK {tick:05d} | {phase}{details_str}")


def log_phase(
    logger: logging.Logger,
    tick: int,
    phase_name: str,
    status: str,
    duration_ms: int | None = None,
    details: str | None = None,
) -> None:
    """Log pipeline phase execution."""
    duration_str = f" | {duration_ms}ms" if duration_ms else ""
    details_str = f" | {details}" if details else ""
    logger.debug(f"TICK {tick:05d} | PHASE | {phase_name} | {status}{duration_str}{details_str}")


def log_effect(
    logger: logging.Logger,
    tick: int,
    effect_type: str,
    agent: str | None = None,
    details: str | None = None,
) -> None:
    """Log an effect being produced."""
    agent_str = f" | agent={agent}" if agent else ""
    details_str = f" | {details}" if details else ""
    logger.debug(f"TICK {tick:05d} | EFFECT | {effect_type}{agent_str}{details_str}")


def log_event(
    logger: logging.Logger,
    tick: int,
    event_type: str,
    details: str | None = None,
) -> None:
    """Log a domain event being committed."""
    details_str = f" | {details}" if details else ""
    logger.info(f"TICK {tick:05d} | EVENT | {event_type}{details_str}")


def log_agent_turn(
    logger: logging.Logger,
    tick: int,
    agent: str,
    status: str,
    model: str | None = None,
    duration_ms: int | None = None,
    details: str | None = None,
) -> None:
    """Log agent turn activity."""
    model_str = f" | model={model}" if model else ""
    duration_str = f" | {duration_ms}ms" if duration_ms else ""
    details_str = f" | {details}" if details else ""
    logger.info(f"TICK {tick:05d} | AGENT_TURN | {agent} | {status}{model_str}{duration_str}{details_str}")


def log_conversation(
    logger: logging.Logger,
    tick: int,
    conv_id: str,
    action: str,
    participants: list[str] | None = None,
    details: str | None = None,
) -> None:
    """Log conversation-related activity."""
    p_str = f" | participants={participants}" if participants else ""
    details_str = f" | {details}" if details else ""
    logger.info(f"TICK {tick:05d} | CONVERSATION | {conv_id} | {action}{p_str}{details_str}")


def log_scheduler(
    logger: logging.Logger,
    tick: int,
    action: str,
    details: str | None = None,
) -> None:
    """Log scheduler activity."""
    details_str = f" | {details}" if details else ""
    logger.debug(f"TICK {tick:05d} | SCHEDULER | {action}{details_str}")


def log_storage(
    logger: logging.Logger,
    operation: str,
    path: Path | str | None = None,
    success: bool = True,
    details: str | None = None,
) -> None:
    """Log storage operations (event store, snapshots)."""
    status = "OK" if success else "FAILED"
    path_str = f" | {path}" if path else ""
    details_str = f" | {details}" if details else ""
    logger.debug(f"STORAGE | {operation}{path_str} | {status}{details_str}")


def log_observer_cmd(
    logger: logging.Logger,
    command: str,
    details: str | None = None,
) -> None:
    """Log observer commands."""
    details_str = f" | {details}" if details else ""
    logger.info(f"OBSERVER_CMD | {command}{details_str}")
