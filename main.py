#!/usr/bin/env python3
"""
ClaudeVille - A multi-agent village simulation (engine).

Run this to start the simulation and enter the Observer interface.
"""

import argparse
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from engine.engine import VillageEngine
from engine.runner import EngineRunner
from engine.adapters import ClaudeProvider
from engine.logging_config import setup_logging
from observer import ClaudeVilleTUI


def main():
    parser = argparse.ArgumentParser(
        description="ClaudeVille - A multi-agent village simulation (engine)"
    )
    parser.add_argument(
        "--village",
        type=Path,
        default=Path("village"),
        help="Path to village data directory (default: ./village)",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Initialize a new village (will overwrite existing)",
    )
    parser.add_argument(
        "--run",
        type=int,
        metavar="N",
        help="Run N ticks automatically instead of entering TUI",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Just show village status and exit",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    # Configure logging - always log DEBUG to file, console level depends on --debug
    console_level = logging.DEBUG if args.debug else logging.WARNING
    log_path = setup_logging(args.village, console_level=console_level)
    print(f"Logging to: {log_path}")

    # Create LLM provider (uses per-agent models from bootstrap)
    provider = ClaudeProvider()

    # Create engine
    engine = VillageEngine(
        village_root=args.village,
        llm_provider=provider,
    )

    # Initialize or recover village state
    if args.init:
        print("Initializing new village...")
        engine.initialize_default()
        print(f"Village created at {args.village}")
        print(f"Agents: {', '.join(engine.agents.keys())}")
    else:
        # Try to recover existing village
        recovered = engine.recover()
        if not recovered:
            print("No village found. Creating new village...")
            engine.initialize_default()
            print(f"Village created at {args.village}")

    # Status mode
    if args.status:
        print("\nClaudeVille Status (engine)")
        print("==============================")
        time_snap = engine.observer.get_time_snapshot()
        print(f"Tick: {engine.tick}")
        print(f"Day: {time_snap.day_number} ({time_snap.time_of_day})")
        print(f"Time: {time_snap.clock_time}")
        print(f"Weather: {engine.world.weather.value}")
        print("\nAgents:")
        for name, agent in engine.agents.items():
            status = "sleeping" if agent.is_sleeping else "awake"
            print(f"  {name}: {agent.location} (mood: {agent.mood}, energy: {agent.energy}, {status})")
        return

    # Run mode (automated)
    if args.run:
        async def run_auto():
            print(f"\nRunning {args.run} ticks...")
            print("-" * 40)
            for _ in range(args.run):
                result = await engine.tick_once()
                summary = ", ".join(result.agents_acted) if result.agents_acted else "No agents acted"
                print(f"[{result.tick}] {summary} | {len(result.events)} events")
            print("-" * 40)
            print("Done.")

        asyncio.run(run_auto())
        return

    # Interactive mode - TUI
    print(f"\nLoaded village with {len(engine.agents)} agents:")
    for name, agent in engine.agents.items():
        print(f"  - {name} at {agent.location}")

    # Create EngineRunner - runs engine in dedicated thread with persistent event loop
    # This ensures background asyncio tasks (like streaming sessions) survive across ticks
    runner = EngineRunner(engine)
    app = ClaudeVilleTUI(runner)
    app.run()


if __name__ == "__main__":
    main()
