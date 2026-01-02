"""Hearth - A grid-based world for Claude agents."""

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from logging_config import setup_logging


def main() -> int:
    """Main entry point for Hearth."""
    # Load environment variables first
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Hearth - A grid-based world for Claude agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  hearth                    # Run with TUI observer
  hearth --init             # Initialize new world
  hearth --run 10           # Run 10 ticks without TUI
  hearth --status           # Show current status
        """,
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("data"),
        help="Data directory (default: data/)",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Initialize a new world (caution: overwrites existing)",
    )
    parser.add_argument(
        "--run",
        type=int,
        metavar="N",
        help="Run N ticks without TUI",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show world status and exit",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging to console",
    )

    args = parser.parse_args()

    # Setup logging
    console_level = logging.DEBUG if args.debug else logging.WARNING
    log_path = setup_logging(args.data, console_level=console_level)

    # Show version
    try:
        from hearth import __version__
    except ImportError:
        __version__ = "0.1.0"  # Fallback when running directly
    print(f"Hearth v{__version__}")
    print(f"Data directory: {args.data.absolute()}")
    print(f"Log file: {log_path}")
    print()

    # Handle different run modes
    if args.init:
        print("World initialization not yet implemented (Phase 14)")
        return 0

    if args.status:
        print("Status display not yet implemented")
        return 0

    if args.run is not None:
        print(f"Batch mode ({args.run} ticks) not yet implemented")
        return 0

    # Default: TUI mode
    print("TUI observer not yet implemented (Phase 17)")
    print("Use --help to see available options")
    return 0


if __name__ == "__main__":
    sys.exit(main())
