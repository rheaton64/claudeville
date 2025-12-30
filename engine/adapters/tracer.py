"""
VillageTracer - traces agent activity to JSONL files and streams to callbacks.

This enables:
- Real-time streaming to TUI for live agent monitoring
- Persistent trace files for history loading and debugging
- Thread-safe operation for concurrent agent turns

Events follow the engine format:
- turn_start: Beginning of agent turn with context
- text: Streaming text output from agent
- tool_use: Agent calling a tool
- tool_result: Tool execution result
- turn_end: End of turn with narrative (before interpretation)
- interpret_complete: Interpreted observations (after InterpretPhase)
"""

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from engine.runtime.interpreter import AgentTurnResult


class VillageTracer:
    """
    Thread-safe tracer for agent activity.

    Writes events to per-agent JSONL files and notifies registered callbacks
    in real-time. Designed for concurrent agent turns with proper locking.

    Events:
    - turn_start: Beginning of agent turn
    - text: Streaming text output
    - tool_use: Tool invocation
    - tool_result: Tool response
    - turn_end: End of turn (before interpretation)
    - interpret_complete: Interpreted observations (after InterpretPhase)
    """

    def __init__(self, trace_dir: Path):
        """
        Initialize tracer.

        Args:
            trace_dir: Directory for trace files (e.g., village/traces)
        """
        self.trace_dir = trace_dir
        self.trace_dir.mkdir(parents=True, exist_ok=True)

        # Thread-safe callback management
        self._callbacks: list[Callable[[str, dict], None]] = []
        self._callbacks_lock = threading.Lock()

        # Per-agent turn IDs (agent_name -> current_turn_id)
        self._turn_ids: dict[str, str | None] = {}
        self._turn_ids_lock = threading.Lock()

    def register_callback(self, callback: Callable[[str, dict], None]) -> None:
        """
        Register a callback for real-time streaming.

        Callbacks receive (event_type, event_dict) for each trace event.
        Thread-safe: can be called from any thread.

        Args:
            callback: Function(event_type: str, data: dict) -> None
        """
        with self._callbacks_lock:
            self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[str, dict], None]) -> None:
        """Remove a previously registered callback."""
        with self._callbacks_lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def _get_trace_file(self, agent_name: str) -> Path:
        """Get the trace file path for an agent."""
        return self.trace_dir / f"{agent_name}.jsonl"

    def _generate_turn_id(self) -> str:
        """Generate an 8-character turn ID."""
        return str(uuid.uuid4())[:8]

    def _write_event(self, agent_name: str, event_type: str, data: dict[str, Any]) -> None:
        """
        Write event to file and notify callbacks.

        Thread-safe for concurrent agent turns.

        Args:
            agent_name: Which agent this event is for
            event_type: Type of event (turn_start, text, etc.)
            data: Event-specific data
        """
        with self._turn_ids_lock:
            turn_id = self._turn_ids.get(agent_name)

        entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": agent_name,
            "turn_id": turn_id,
            "event": event_type,
            **data
        }

        # Write to file (per-agent file minimizes contention)
        trace_file = self._get_trace_file(agent_name)
        with open(trace_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

        # Notify callbacks (copy list under lock, invoke outside)
        with self._callbacks_lock:
            callbacks = list(self._callbacks)

        for callback in callbacks:
            try:
                callback(event_type, entry)
            except Exception:
                pass  # Don't let callback errors break tracing

    # =========================================================================
    # Turn Lifecycle Events
    # =========================================================================

    def start_turn(
        self,
        agent_name: str,
        tick: int,
        location: str,
        model: str,
        context: str,
        session_id: str | None = None,
    ) -> str:
        """
        Log the start of a new turn.

        Args:
            agent_name: Which agent is taking a turn
            tick: Current simulation tick
            location: Agent's current location
            model: LLM model being used
            context: The full context prompt sent to the agent
            session_id: Optional SDK session ID

        Returns:
            The generated turn_id
        """
        turn_id = self._generate_turn_id()

        with self._turn_ids_lock:
            self._turn_ids[agent_name] = turn_id

        self._write_event(agent_name, "turn_start", {
            "tick": tick,
            "session_id": session_id,
            "location": location,
            "model": model,
            "context": context,
        })

        return turn_id

    def log_text(self, agent_name: str, content: str) -> None:
        """
        Log text output from the agent.

        Called for each TextBlock in the response stream.

        Args:
            agent_name: Which agent produced this text
            content: The text content
        """
        self._write_event(agent_name, "text", {"content": content})

    def log_tool_use(
        self,
        agent_name: str,
        tool_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> None:
        """
        Log the agent calling a tool.

        Args:
            agent_name: Which agent called the tool
            tool_id: SDK tool use ID (for linking with result)
            tool_name: Name of the tool being called
            tool_input: Arguments passed to the tool
        """
        self._write_event(agent_name, "tool_use", {
            "tool_id": tool_id,
            "tool": tool_name,
            "input": tool_input,
        })

    def log_tool_result(
        self,
        agent_name: str,
        tool_use_id: str,
        content: str | None,
        is_error: bool = False,
    ) -> None:
        """
        Log the result of a tool call.

        Args:
            agent_name: Which agent's tool call this is for
            tool_use_id: SDK tool use ID (links to tool_use event)
            content: Tool result content (truncated to 500 chars)
            is_error: Whether the tool call failed
        """
        self._write_event(agent_name, "tool_result", {
            "tool_id": tool_use_id,
            "result": content[:500] if content else None,  # Truncate long results
            "is_error": is_error,
        })

    def end_turn(
        self,
        agent_name: str,
        narrative: str,
        session_id: str | None = None,
        duration_ms: int = 0,
        cost_usd: float | None = None,
        num_turns: int = 0,
    ) -> None:
        """
        Log the end of a turn (before interpretation).

        This captures the raw narrative and SDK metadata.
        Interpretation results come later via log_interpret_complete().

        Args:
            agent_name: Which agent's turn ended
            narrative: The complete narrative text
            session_id: SDK session ID for resumption
            duration_ms: How long the SDK call took
            cost_usd: API cost for this turn
            num_turns: Number of SDK turns (agentic loops)
        """
        self._write_event(agent_name, "turn_end", {
            "session_id": session_id,
            "narrative": narrative,
            "duration_ms": duration_ms,
            "cost_usd": cost_usd,
            "sdk_turns": num_turns,
        })

        with self._turn_ids_lock:
            self._turn_ids[agent_name] = None

    def log_interpret_complete(
        self,
        agent_name: str,
        result: "AgentTurnResult",
        tick: int,
    ) -> None:
        """
        Log interpretation results (after InterpretPhase).

        This is called separately from end_turn because interpretation
        happens in a later phase of the tick pipeline.

        Args:
            agent_name: Which agent's turn was interpreted
            result: The interpreted observations
            tick: Current simulation tick (links to turn)
        """
        self._write_event(agent_name, "interpret_complete", {
            "tick": tick,
            "mood": result.mood_expressed,
            "movement": result.movement,
            "proposes_moving_together": result.proposes_moving_together,
            "actions": list(result.actions_described),
            "wants_to_rest": result.wants_to_rest,
            "wants_to_sleep": result.wants_to_sleep,
            "suggested_next_speaker": result.suggested_next_speaker,
        })

    # =========================================================================
    # Compaction Events
    # =========================================================================

    def log_token_update(
        self,
        agent_name: str,
        token_count: int,
        threshold: int = 150_000,
    ) -> None:
        """
        Log token count update (for TUI display).

        Called after each turn to update the token display.

        Args:
            agent_name: Which agent's tokens were updated
            token_count: Current cumulative token count
            threshold: Compaction threshold (default 150K)
        """
        percent = min(100, int(token_count / threshold * 100))
        self._write_event(agent_name, "token_update", {
            "tokens": token_count,
            "threshold": threshold,
            "percent": percent,
        })

    def log_compaction_start(
        self,
        agent_name: str,
        critical: bool,
        pre_tokens: int,
    ) -> None:
        """
        Log the start of a compaction operation.

        Args:
            agent_name: Which agent is being compacted
            critical: True if critical threshold (150K), False if pre-sleep (100K)
            pre_tokens: Token count before compaction
        """
        self._write_event(agent_name, "compaction_start", {
            "critical": critical,
            "pre_tokens": pre_tokens,
        })

    def log_compaction_end(
        self,
        agent_name: str,
        pre_tokens: int,
        post_tokens: int,
    ) -> None:
        """
        Log completion of compaction.

        Args:
            agent_name: Which agent was compacted
            pre_tokens: Token count before compaction
            post_tokens: Token count after compaction
        """
        self._write_event(agent_name, "compaction_end", {
            "pre_tokens": pre_tokens,
            "post_tokens": post_tokens,
            "tokens_saved": pre_tokens - post_tokens,
        })
