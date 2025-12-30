"""
EngineRunner - Runs VillageEngine in a dedicated thread with persistent event loop.

This solves the problem of background asyncio tasks (like streaming sessions) getting
cancelled when Textual worker threads end. By running the engine in a single persistent
thread, all asyncio.create_task() calls persist for the entire TUI session.

Architecture:
- TUI (main thread): Sends commands via queue, receives updates via callbacks
- Engine thread: Own event loop, processes commands, runs engine operations
- Callbacks: Already thread-safe (TUI uses call_from_thread())
"""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from engine.engine import VillageEngine

logger = logging.getLogger(__name__)


class Command(Enum):
    """Commands that can be sent to the engine thread."""
    TICK_ONCE = auto()
    RUN = auto()
    PAUSE = auto()
    RESUME = auto()
    STOP = auto()
    SHUTDOWN = auto()


class EngineRunner:
    """
    Runs VillageEngine in a dedicated thread with persistent event loop.

    This ensures that background asyncio tasks (like persistent streaming sessions)
    survive across multiple tick commands, because the event loop never dies.

    Usage:
        runner = EngineRunner(engine)
        runner.start()  # Call once on TUI mount

        # These are thread-safe, non-blocking
        runner.tick_once()
        runner.run_continuous()
        runner.pause()
        runner.stop()

        runner.shutdown()  # Call on TUI unmount
    """

    def __init__(self, engine: "VillageEngine"):
        self._engine = engine
        self._command_queue: queue.Queue[tuple[Command, dict[str, Any]]] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._is_continuous_running = False  # Is continuous run active?
        self._shutdown_event = threading.Event()

    @property
    def engine(self) -> "VillageEngine":
        """Access the underlying engine (for callbacks and state queries)."""
        return self._engine

    @property
    def is_running(self) -> bool:
        """Whether continuous simulation is active."""
        return self._is_continuous_running

    def start(self) -> None:
        """
        Start the engine thread.

        Call once on TUI mount. The thread will run until shutdown() is called.
        """
        if self._thread is not None and self._thread.is_alive():
            logger.warning("Engine thread already running")
            return

        self._shutdown_event.clear()
        self._thread = threading.Thread(target=self._thread_main, daemon=True, name="EngineRunner")
        self._thread.start()
        logger.info("Engine thread started")

    def shutdown(self) -> None:
        """
        Shutdown the engine thread.

        Call on TUI unmount. Blocks until the thread exits (with timeout).
        """
        if self._thread is None:
            return

        logger.info("Requesting engine thread shutdown")
        self._command_queue.put((Command.SHUTDOWN, {}))
        self._shutdown_event.set()

        # Wait for thread to exit
        self._thread.join(timeout=5.0)
        if self._thread.is_alive():
            logger.warning("Engine thread did not exit cleanly")
        else:
            logger.info("Engine thread shut down")
        self._thread = None

    def _thread_main(self) -> None:
        """Entry point for engine thread - creates and runs event loop."""
        logger.debug("Engine thread starting event loop")
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._command_loop())
        except Exception as e:
            logger.error(f"Engine thread error: {e}", exc_info=True)
        finally:
            # Clean up pending tasks
            pending = asyncio.all_tasks(self._loop)
            for task in pending:
                task.cancel()
            if pending:
                self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            self._loop.close()
            logger.debug("Engine thread event loop closed")

    async def _command_loop(self) -> None:
        """Main loop: process commands forever until shutdown."""
        logger.debug("Command loop started")

        while True:
            # Non-blocking check for commands
            try:
                cmd, data = self._command_queue.get_nowait()
            except queue.Empty:
                # No command, yield to event loop for other tasks
                await asyncio.sleep(0.01)
                continue

            logger.debug(f"Processing command: {cmd.name}")

            if cmd == Command.SHUTDOWN:
                # Stop any running simulation first
                self._engine.stop()
                self._is_continuous_running = False
                # Shutdown the LLM provider
                if hasattr(self._engine, '_llm_provider') and self._engine._llm_provider:
                    await self._engine.shutdown()
                logger.debug("Command loop exiting")
                break

            elif cmd == Command.TICK_ONCE:
                if not self._is_continuous_running:
                    try:
                        await self._engine.run(max_ticks=1)
                    except Exception as e:
                        logger.error(f"Tick error: {e}", exc_info=True)

            elif cmd == Command.RUN:
                if not self._is_continuous_running:
                    self._is_continuous_running = True
                    # Start continuous run as a background task
                    asyncio.create_task(self._run_continuous())

            elif cmd == Command.PAUSE:
                self._engine.pause()

            elif cmd == Command.RESUME:
                self._engine.resume()

            elif cmd == Command.STOP:
                self._engine.stop()
                self._is_continuous_running = False

    async def _run_continuous(self) -> None:
        """Run engine continuously until stopped."""
        logger.debug("Starting continuous run")
        try:
            await self._engine.run()
        except Exception as e:
            logger.error(f"Continuous run error: {e}", exc_info=True)
        finally:
            self._is_continuous_running = False
            logger.debug("Continuous run ended")

    # =========================================================================
    # Public API (called from TUI thread, thread-safe via queue)
    # =========================================================================

    def tick_once(self) -> None:
        """
        Execute a single tick.

        Thread-safe. Non-blocking - returns immediately.
        Results come via engine callbacks (on_tick, on_event, on_agent_stream).
        """
        if self._is_continuous_running:
            logger.debug("tick_once ignored - continuous run active")
            return
        self._command_queue.put((Command.TICK_ONCE, {}))

    def run_continuous(self) -> None:
        """
        Start continuous simulation.

        Thread-safe. Non-blocking.
        Use stop() to end the simulation.
        """
        if self._is_continuous_running:
            logger.debug("run_continuous ignored - already running")
            return
        self._command_queue.put((Command.RUN, {}))

    def pause(self) -> None:
        """
        Pause the simulation (graceful - after current tick).

        Thread-safe. Non-blocking.
        Use resume() to continue.
        """
        self._command_queue.put((Command.PAUSE, {}))

    def resume(self) -> None:
        """
        Resume a paused simulation.

        Thread-safe. Non-blocking.
        """
        self._command_queue.put((Command.RESUME, {}))

    def stop(self) -> None:
        """
        Stop the simulation.

        Thread-safe. Non-blocking.
        """
        self._command_queue.put((Command.STOP, {}))

    def run_in_engine_loop(self, coro) -> None:
        """
        Run a coroutine in the engine's event loop.

        Thread-safe. Non-blocking - the coroutine runs asynchronously.
        Useful for running async operations like compaction from the TUI thread.

        Args:
            coro: A coroutine to run in the engine's event loop
        """
        if self._loop is None:
            logger.warning("Cannot run_in_engine_loop - engine thread not started")
            return

        # Schedule the coroutine to run in the engine's event loop
        # This is thread-safe because call_soon_threadsafe is
        def schedule():
            asyncio.create_task(coro)

        self._loop.call_soon_threadsafe(schedule)
