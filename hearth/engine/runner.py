"""EngineRunner - Persistent thread for TUI integration.

Runs the engine in a dedicated thread with its own event loop, allowing
the TUI to remain responsive while ticks execute.
"""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from engine.engine import HearthEngine
    from engine.context import TickContext

logger = logging.getLogger(__name__)


class EngineRunner:
    """Runs engine in a persistent thread with its own event loop.

    The TUI runs in the main thread with Textual. This runner creates a
    dedicated background thread with its own asyncio event loop for the
    engine. Commands are sent via a thread-safe queue.

    This architecture ensures:
    - TUI remains responsive during tick execution
    - Background tasks survive across ticks
    - Clean shutdown when TUI exits

    Usage:
        runner = EngineRunner(engine)
        runner.start()  # Starts background thread

        # From TUI:
        runner.request_tick()  # Run single tick
        runner.request_run()   # Run continuously
        runner.request_pause() # Pause continuous running
        runner.stop()          # Clean shutdown
    """

    def __init__(self, engine: "HearthEngine"):
        """Initialize EngineRunner.

        Args:
            engine: HearthEngine instance to run
        """
        self._engine = engine
        self._command_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._running = False
        self._paused = False
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

        # Callbacks for TUI updates (called from engine thread)
        self._tick_callbacks: list[Callable[["TickContext"], None]] = []

    def start(self) -> None:
        """Start the engine thread.

        Creates a background thread with its own event loop and begins
        processing commands from the queue.
        """
        if self._running:
            logger.warning("EngineRunner already running")
            return

        self._running = True
        self._paused = False
        self._thread = threading.Thread(target=self._thread_main, daemon=True)
        self._thread.start()
        logger.info("EngineRunner started")

    def stop(self) -> None:
        """Stop the engine thread.

        Sends stop command and waits for thread to finish.
        """
        if not self._running:
            return

        self._running = False
        self._command_queue.put(("stop", None))

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

        logger.info("EngineRunner stopped")

    def request_tick(self) -> None:
        """Request a single tick (thread-safe).

        The tick will execute asynchronously in the engine thread.
        """
        self._command_queue.put(("tick", None))

    def request_run(self, count: int | None = None) -> None:
        """Request continuous running (thread-safe).

        Args:
            count: Number of ticks to run, or None for unlimited
        """
        self._command_queue.put(("run", count))

    def request_pause(self) -> None:
        """Pause continuous running (thread-safe).

        Takes effect after the current tick completes.
        """
        self._command_queue.put(("pause", None))

    def on_tick(self, callback: Callable[["TickContext"], None]) -> None:
        """Register a tick completion callback.

        Callbacks are called from the engine thread after each tick.
        Use these for TUI updates.

        Args:
            callback: Function to call after each tick
        """
        self._tick_callbacks.append(callback)

    @property
    def is_running(self) -> bool:
        """Check if the engine thread is running."""
        return self._running

    @property
    def is_paused(self) -> bool:
        """Check if continuous running is paused."""
        return self._paused

    # -------------------------------------------------------------------------
    # Thread Implementation
    # -------------------------------------------------------------------------

    def _thread_main(self) -> None:
        """Main function for engine thread.

        Creates an event loop and runs the command processing loop.
        """
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._command_loop())
        except Exception as e:
            logger.error(f"Engine thread error: {e}")
        finally:
            self._loop.close()
            self._loop = None

    async def _command_loop(self) -> None:
        """Process commands from the queue.

        Runs until a stop command is received.
        """
        # Initialize engine from storage
        await self._engine.initialize()

        while self._running:
            try:
                # Non-blocking check with timeout
                cmd, arg = self._command_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if cmd == "stop":
                break
            elif cmd == "tick":
                await self._execute_single_tick()
            elif cmd == "run":
                await self._run_continuous(arg)
            elif cmd == "pause":
                self._paused = True

    async def _execute_single_tick(self) -> None:
        """Execute a single tick and notify callbacks."""
        try:
            ctx = await self._engine.tick_once()
            self._notify_callbacks(ctx)
        except Exception as e:
            logger.error(f"Tick error: {e}")
            raise

    async def _run_continuous(self, count: int | None) -> None:
        """Run ticks continuously.

        Args:
            count: Number of ticks to run, or None for unlimited
        """
        self._paused = False
        ticks_run = 0

        while not self._paused and self._running:
            await self._execute_single_tick()
            ticks_run += 1

            if count is not None and ticks_run >= count:
                break

            # Check for commands between ticks
            try:
                cmd, _ = self._command_queue.get_nowait()
                if cmd == "pause":
                    self._paused = True
                elif cmd == "stop":
                    self._running = False
                    break
            except queue.Empty:
                pass

            # Small delay to prevent tight loop and allow responsiveness
            await asyncio.sleep(0.1)

    def _notify_callbacks(self, ctx: "TickContext") -> None:
        """Notify all registered callbacks after a tick.

        Args:
            ctx: The completed tick context
        """
        for callback in self._tick_callbacks:
            try:
                callback(ctx)
            except Exception as e:
                logger.error(f"Callback error: {e}")
