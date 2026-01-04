"""Hearth - A grid-based world for Claude agents."""

import argparse
import asyncio
import logging
import random
import sys
from collections import deque
from pathlib import Path

from dotenv import load_dotenv

from logging_config import setup_logging
from core.types import Position
from core.terrain import Terrain


def find_agent_positions(
    terrain_map: dict[Position, Terrain],
    world_width: int,
    world_height: int,
    num_agents: int = 3,
    min_distance: int = 30,
    max_distance: int = 60,
    max_attempts: int = 100,
) -> list[Position]:
    """Find valid starting positions for agents.

    Positions must be:
    1. On grass terrain (not in terrain_map means grass)
    2. Between min_distance and max_distance L1 (Manhattan) distance of each other
    3. Connected via passable paths

    Args:
        terrain_map: Dict of non-grass terrain positions
        world_width: World width
        world_height: World height
        num_agents: Number of positions to find
        min_distance: Minimum L1 distance between any two agents
        max_distance: Maximum L1 distance between any two agents
        max_attempts: How many random starting points to try

    Returns:
        List of positions, one per agent

    Raises:
        RuntimeError: If valid positions cannot be found
    """
    def is_passable(pos: Position) -> bool:
        """Check if position is passable (grass or other passable terrain)."""
        if pos.x < 0 or pos.x >= world_width or pos.y < 0 or pos.y >= world_height:
            return False
        terrain = terrain_map.get(pos, Terrain.GRASS)
        return terrain != Terrain.WATER

    def is_grass(pos: Position) -> bool:
        """Check if position is grass (not in terrain_map)."""
        if pos.x < 0 or pos.x >= world_width or pos.y < 0 or pos.y >= world_height:
            return False
        return pos not in terrain_map

    def l1_distance(p1: Position, p2: Position) -> int:
        """Manhattan distance between two positions."""
        return abs(p1.x - p2.x) + abs(p1.y - p2.y)

    def has_path(start: Position, end: Position) -> bool:
        """BFS to check if path exists between two positions."""
        if start == end:
            return True
        visited = {start}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                neighbor = Position(current.x + dx, current.y + dy)
                if neighbor == end:
                    return True
                if neighbor not in visited and is_passable(neighbor):
                    visited.add(neighbor)
                    queue.append(neighbor)
        return False

    def find_nearby_grass(center: Position, radius: int) -> list[Position]:
        """Find all grass positions within radius of center."""
        positions = []
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if abs(dx) + abs(dy) <= radius:
                    pos = Position(center.x + dx, center.y + dy)
                    if is_grass(pos):
                        positions.append(pos)
        return positions

    # Try random starting points near the center
    center_x = world_width // 2
    center_y = world_height // 2

    for attempt in range(max_attempts):
        # Pick a random center point within central region
        base_x = center_x + random.randint(-100, 100)
        base_y = center_y + random.randint(-100, 100)
        base = Position(base_x, base_y)

        # Find grass positions nearby (search radius covers max_distance)
        search_radius = max_distance
        candidates = find_nearby_grass(base, search_radius)

        if len(candidates) < num_agents:
            continue

        # Try to find num_agents positions that are all connected
        random.shuffle(candidates)

        # Start with first candidate
        selected = [candidates[0]]

        for candidate in candidates[1:]:
            if len(selected) >= num_agents:
                break

            # Check L1 distance constraint with all selected (min and max)
            distances = [l1_distance(candidate, s) for s in selected]
            if all(min_distance <= d <= max_distance for d in distances):
                # Check path connectivity with all selected
                if all(has_path(candidate, s) for s in selected):
                    selected.append(candidate)

        if len(selected) >= num_agents:
            return selected[:num_agents]

    raise RuntimeError(
        f"Could not find {num_agents} valid starting positions after {max_attempts} attempts. "
        "Try adjusting terrain generation parameters."
    )


async def init_world(data_dir: Path) -> int:
    """Initialize a new world with terrain and agents.

    Args:
        data_dir: Data directory for world.db and traces

    Returns:
        Exit code
    """
    from core.types import AgentName
    from core.agent import Agent, AgentModel, Inventory
    from core.world import Cell
    from core.terrain import Weather
    from generation import generate_terrain
    from storage import Storage
    from services import WorldService, AgentService
    from adapters.prompt_builder import DEFAULT_AGENTS

    # Create directories
    data_dir.mkdir(parents=True, exist_ok=True)
    agents_dir = data_dir.parent / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    db_path = data_dir / "world.db"
    if db_path.exists():
        print(f"Warning: Overwriting existing world at {db_path}")
        db_path.unlink()

    print("Initializing new world...")

    async with Storage(data_dir) as storage:
        world_service = WorldService(storage)
        agent_service = AgentService(storage)

        # Set world dimensions and initial state
        print("  Setting world state (500x500, tick=0, weather=CLEAR)...")
        await storage.world.set_dimensions(500, 500)
        await storage.world.set_tick(0)
        await storage.world.set_weather(Weather.CLEAR)

        # Generate terrain using WFC
        # For 500x500 grid (250k cells):
        # - batch_size=2000: collapse many cells per step
        # - min_batch_distance=4: standard spacing
        from tqdm import tqdm
        pbar = tqdm(total=500*500, desc="  Generating terrain", unit="cells")
        last_progress = [0]

        def update_progress(current: int, total: int) -> None:
            delta = current - last_progress[0]
            if delta > 0:
                pbar.update(delta)
                last_progress[0] = current

        terrain_map = generate_terrain(
            width=500,
            height=500,
            batch_size=2000,
            min_batch_distance=4,
            progress_callback=update_progress,
        )
        pbar.close()
        print(f"  Generated {len(terrain_map)} non-grass cells")

        # Insert terrain cells (bulk insert for speed)
        print("  Saving terrain to database...")
        cells = [Cell(position=pos, terrain=terrain_type) for pos, terrain_type in terrain_map.items()]
        await storage.world.set_cells_bulk(cells)

        # Find valid starting positions for agents
        # Agents spawn 30-60 cells apart on grass with passable paths between them
        print("  Finding agent starting positions...")
        agent_names = list(DEFAULT_AGENTS.keys())
        positions = find_agent_positions(
            terrain_map,
            world_width=500,
            world_height=500,
            num_agents=len(agent_names),
        )
        agent_positions = dict(zip(agent_names, positions))

        # Create agents
        print("  Creating agents...")
        for agent_name, config in DEFAULT_AGENTS.items():
            # Extract model display name from model_id
            model_id = config["model_id"]
            if "opus" in model_id:
                display_name = "Opus 4.5"
            else:
                display_name = "Sonnet 4.5"

            agent = Agent(
                name=AgentName(agent_name),
                model=AgentModel(id=model_id, display_name=display_name),
                personality=config["personality"],
                position=agent_positions[agent_name],
            )
            await storage.agents.save_agent(agent)
            print(f"    {agent_name} at ({agent.position.x}, {agent.position.y}) [{display_name}]")

            # Create home directory
            agent_service.ensure_home_directory(AgentName(agent_name), agents_dir)

    print()
    print("World initialized successfully!")
    print(f"  Database: {db_path}")
    print(f"  Agent homes: {agents_dir}")
    print()
    print("Run 'hearth --status' to see world state")
    print("Run 'hearth --run N' to execute N ticks")
    return 0


async def run_batch(data_dir: Path, num_ticks: int) -> int:
    """Run N ticks without TUI.

    Args:
        data_dir: Data directory containing world.db
        num_ticks: Number of ticks to execute

    Returns:
        Exit code
    """
    from storage import Storage
    from engine import HearthEngine

    db_path = data_dir / "world.db"
    if not db_path.exists():
        print(f"Error: No world found at {db_path}")
        print("Run with --init to create a new world first.")
        return 1

    agents_dir = data_dir.parent / "agents"

    print(f"Running {num_ticks} tick(s)...")
    print()

    async with Storage(data_dir) as storage:
        # Create engine
        engine = HearthEngine(
            storage,
            agents_root=agents_dir,
            enable_llm=True,
        )
        await engine.initialize()

        try:
            for i in range(num_ticks):
                print(f"--- Tick {i + 1}/{num_ticks} ---")
                ctx = await engine.tick_once()

                # Print summary
                print(f"  Time: {ctx.time_of_day}, Weather: {ctx.weather.value}")
                print(f"  Agents acted: {len(ctx.agents_to_act)}")
                if ctx.agents_to_act:
                    for agent_name in ctx.agents_to_act:
                        print(f"    - {agent_name}")
                print(f"  Events: {len(ctx.events)}")
                for event in ctx.events:
                    print(f"    - {type(event).__name__}")
                print()

        finally:
            await engine.shutdown()

    print("Batch run complete!")
    return 0


async def run_tui_mode(data_dir: Path) -> int:
    """Run the TUI observer.

    Args:
        data_dir: Data directory containing world.db

    Returns:
        Exit code
    """
    from storage import Storage
    from engine import HearthEngine, EngineRunner
    from observe.tui import run_tui

    db_path = data_dir / "world.db"
    if not db_path.exists():
        print(f"Error: No world found at {db_path}")
        print("Run with --init to create a new world first.")
        return 1

    agents_dir = data_dir.parent / "agents"

    async with Storage(data_dir) as storage:
        # Create engine with LLM enabled
        engine = HearthEngine(
            storage,
            agents_root=agents_dir,
            enable_llm=True,
        )

        # Create runner
        runner = EngineRunner(engine)

        try:
            # Run TUI (engine initialization happens inside runner.start())
            await run_tui(runner)
        finally:
            # Clean shutdown
            await engine.shutdown()

    return 0


async def show_status(data_dir: Path) -> int:
    """Show world status.

    Args:
        data_dir: Data directory containing world.db

    Returns:
        Exit code
    """
    from storage import Storage
    from services import WorldService, AgentService

    db_path = data_dir / "world.db"
    if not db_path.exists():
        print(f"No world found at {db_path}")
        return 1

    async with Storage(data_dir) as storage:
        world_service = WorldService(storage)
        agent_service = AgentService(storage)

        # Get world state
        world_state = await world_service.get_world_state()
        width, height = await world_service.get_world_dimensions()

        print(f"World: {width}x{height}")
        print(f"Tick: {world_state.current_tick}")
        print(f"Weather: {world_state.weather.value}")
        print()

        # Get agents
        agents = await agent_service.get_all_agents()
        print(f"Agents ({len(agents)}):")
        for agent in agents:
            status = "sleeping" if agent.is_sleeping else "awake"
            journey = ""
            if agent.is_journeying and agent.journey:
                dest = agent.journey.destination
                if dest.landmark:
                    journey = f" -> {dest.landmark}"
                elif dest.position:
                    journey = f" -> ({dest.position.x}, {dest.position.y})"
            print(f"  {agent.name}: ({agent.position.x}, {agent.position.y}) [{status}]{journey}")

        # Get named places
        named_places = await world_service.get_all_named_places()
        if named_places:
            print()
            print(f"Named places ({len(named_places)}):")
            for name, pos in named_places.items():
                print(f"  {name}: ({pos.x}, {pos.y})")

    return 0


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
        return asyncio.run(init_world(args.data))

    if args.status:
        return asyncio.run(show_status(args.data))

    if args.run is not None:
        return asyncio.run(run_batch(args.data, args.run))

    # Default: TUI mode
    return asyncio.run(run_tui_mode(args.data))


if __name__ == "__main__":
    sys.exit(main())
