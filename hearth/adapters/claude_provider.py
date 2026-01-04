"""HearthProvider - Claude Agent SDK integration for Hearth.

Uses the Claude Agent SDK with:
- Persistent ClaudeSDKClient per agent (maintains conversation)
- Per-agent MCP server with closures capturing agent-specific state
- Streaming input (required for MCP tools)

Each agent gets their own MCP server because:
1. Tool handlers run in a background async context spawned by the SDK
2. Contextvars don't propagate to that context
3. Each agent needs their own state (tool_context, events, actions)
4. With parallel agent execution, a shared state would cause collisions
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from langsmith import trace as langsmith_trace

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    ResultMessage,
    ToolUseBlock,
    ToolResultBlock,
    UserMessage,
)

from core.types import AgentName, Position, TurnTokenUsage
from core.terrain import Weather
from core.events import DomainEvent
from .tools import (
    AgentToolState,
    HearthToolContext,
    HEARTH_TOOL_NAMES,
    create_hearth_mcp_server,
)
from .prompt_builder import PromptBuilder
from .tracer import HearthTracer

if TYPE_CHECKING:
    from core.agent import Agent
    from core.actions import Action
    from services import WorldService, AgentService, ActionEngine, Narrator
    from .perception import AgentPerception


logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Turn Result
# -----------------------------------------------------------------------------


@dataclass
class ProviderTurnResult:
    """Result from HearthProvider.execute_turn().

    Contains all information about what happened during an agent's turn.
    """

    # Agent's narrative output (combined text blocks)
    narrative: str

    # Actions taken and events produced
    actions_taken: list["Action"] = field(default_factory=list)
    events: list[DomainEvent] = field(default_factory=list)

    # Session info
    session_id: str | None = None

    # Token usage
    token_usage: TurnTokenUsage | None = None


# -----------------------------------------------------------------------------
# Persistent Input Stream
# -----------------------------------------------------------------------------


class PersistentInputStream:
    """A persistent input stream for streaming input mode.

    The SDK iterates over this stream for the lifetime of the agent session.
    Each turn pushes a message, which is yielded to the SDK. The SDK processes
    the message and responds, then waits for the next message.

    IMPORTANT: We do NOT raise StopAsyncIteration between turns - the iterator
    blocks waiting for the next message. StopAsyncIteration is only raised when
    the session should end (via close()).
    """

    def __init__(self, name: str = ""):
        self._queue: asyncio.Queue[dict | None] = asyncio.Queue()
        self._closed = False
        self._name = name
        self._push_count = 0
        self._next_count = 0

    async def push(self, message: dict) -> None:
        """Push a message to be yielded to the SDK."""
        if self._closed:
            raise RuntimeError("Stream is closed")
        self._push_count += 1
        logger.debug(
            f"[STREAM:{self._name}] push() #{self._push_count}, "
            f"queue_size_before={self._queue.qsize()}"
        )
        await self._queue.put(message)

    def close(self) -> None:
        """Close the stream, causing StopAsyncIteration on next read."""
        logger.debug(f"[STREAM:{self._name}] close() called")
        self._closed = True
        # Put None to unblock any waiting __anext__
        self._queue.put_nowait(None)

    def __aiter__(self):
        return self

    async def __anext__(self) -> dict:
        self._next_count += 1
        logger.debug(
            f"[STREAM:{self._name}] __anext__() #{self._next_count} called, "
            f"queue_size={self._queue.qsize()}"
        )
        msg = await self._queue.get()
        got_msg = msg is not None and not self._closed
        logger.debug(
            f"[STREAM:{self._name}] __anext__() #{self._next_count} got message: {got_msg}"
        )
        if msg is None or self._closed:
            raise StopAsyncIteration
        return msg


# -----------------------------------------------------------------------------
# Hearth Provider
# -----------------------------------------------------------------------------


class HearthProvider:
    """LLM provider using Claude Agent SDK.

    Maintains a persistent ClaudeSDKClient per agent, which keeps
    conversation context across turns automatically.

    Each agent gets their own MCP server with closures that capture
    agent-specific state. This ensures parallel execution is safe.
    """

    def __init__(
        self,
        world_service: "WorldService",
        agent_service: "AgentService",
        action_engine: "ActionEngine",
        narrator: "Narrator",
        tracer: HearthTracer | None = None,
        agents_root: Path | None = None,
    ):
        """Initialize the provider.

        Args:
            world_service: For spatial queries
            agent_service: For agent queries
            action_engine: For executing actions
            narrator: For narrating results
            tracer: Optional tracer for real-time event streaming
            agents_root: Root directory for agent home directories
        """
        self._world_service = world_service
        self._agent_service = agent_service
        self._action_engine = action_engine
        self._narrator = narrator
        self._tracer = tracer
        self._agents_root = agents_root or Path("agents")

        # Per-agent state
        self._clients: dict[AgentName, ClaudeSDKClient] = {}
        self._input_streams: dict[AgentName, PersistentInputStream] = {}
        self._query_tasks: dict[AgentName, asyncio.Task] = {}
        self._agent_states: dict[AgentName, AgentToolState] = {}

        # Prompt builder
        self._prompt_builder = PromptBuilder()

        # Token tracking for compaction
        self._token_counts: dict[AgentName, int] = {}

    async def execute_turn(
        self,
        agent: "Agent",
        perception: "AgentPerception",
        tick: int,
    ) -> ProviderTurnResult:
        """Execute an agent's turn.

        Args:
            agent: The agent taking a turn
            perception: Their perception context
            tick: Current simulation tick

        Returns:
            ProviderTurnResult with narrative, actions, and events
        """
        agent_name = agent.name

        # Ensure agent has a tool state
        if agent_name not in self._agent_states:
            self._agent_states[agent_name] = AgentToolState()

        # Create tool context for this turn
        tool_context = HearthToolContext(
            agent_name=agent_name,
            agent=agent,
            tick=tick,
            time_of_day=perception.time_of_day,
            weather=perception.weather,
            world_service=self._world_service,
            agent_service=self._agent_service,
            action_engine=self._action_engine,
            narrator=self._narrator,
        )

        # Update state for this turn
        self._agent_states[agent_name].update_for_turn(tool_context)

        # Check if LangSmith tracing is enabled
        langsmith_enabled = os.environ.get("LANGSMITH_TRACING", "").lower() == "true"

        # Get or create client
        client = await self._get_or_create_client(agent)

        # Build prompts
        user_prompt = self._prompt_builder.build_user_prompt(agent, perception)

        # Execute with or without LangSmith
        if langsmith_enabled:
            return await self._execute_turn_with_langsmith(
                client, agent, perception, tick, user_prompt, tool_context
            )
        else:
            return await self._execute_turn_internal(
                client, agent, perception, tick, user_prompt, tool_context, None
            )

    async def _execute_turn_with_langsmith(
        self,
        client: ClaudeSDKClient,
        agent: "Agent",
        perception: "AgentPerception",
        tick: int,
        user_prompt: str,
        tool_context: HearthToolContext,
    ) -> ProviderTurnResult:
        """Execute turn wrapped in LangSmith trace context."""
        model_id = self._prompt_builder.get_model_id(str(agent.name))

        async with langsmith_trace(
            name=f"agent_turn:{agent.name}",
            run_type="chain",
            inputs={
                "agent": str(agent.name),
                "tick": tick,
                "position": f"({agent.position.x}, {agent.position.y})",
                "prompt": user_prompt,
            },
            metadata={
                "model": model_id,
                "time_of_day": perception.time_of_day,
                "weather": str(perception.weather),
            },
            tags=["agent_turn", str(agent.name), model_id],
        ) as run:
            result = await self._execute_turn_internal(
                client, agent, perception, tick, user_prompt, tool_context, run
            )

            run.end(outputs={
                "narrative": result.narrative,
                "actions_count": len(result.actions_taken),
                "events_count": len(result.events),
            })

            return result

    async def _execute_turn_internal(
        self,
        client: ClaudeSDKClient,
        agent: "Agent",
        perception: "AgentPerception",
        tick: int,
        user_prompt: str,
        tool_context: HearthToolContext,
        langsmith_run: Any | None,
    ) -> ProviderTurnResult:
        """Internal turn execution logic."""
        agent_name = agent.name
        model_id = self._prompt_builder.get_model_id(str(agent_name))

        # Start tracing
        if self._tracer:
            self._tracer.start_turn(
                agent_name=str(agent_name),
                tick=tick,
                position=agent.position,
                model=model_id,
                context=user_prompt,
            )

        # Get input stream
        input_stream = self._input_streams[agent_name]

        # Push message to stream
        logger.debug(f"[{agent_name}] Pushing message to stream (len={len(user_prompt)})")
        await input_stream.push({
            "type": "user",
            "message": {
                "role": "user",
                "content": user_prompt,
            }
        })

        # Yield to event loop
        await asyncio.sleep(0)
        logger.debug(f"[{agent_name}] Message pushed, calling receive_response()")

        # Collect response
        narrative_parts: list[str] = []
        message_count = 0
        session_id: str | None = None
        duration_ms: int = 0
        cost_usd: float | None = None
        num_turns: int = 0
        turn_token_usage: TurnTokenUsage | None = None

        async for message in client.receive_response():
            message_count += 1
            logger.debug(
                f"[{agent_name}] receive_response() yielded message #{message_count}: "
                f"{type(message).__name__}"
            )

            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        narrative_parts.append(block.text)
                        if self._tracer:
                            self._tracer.log_text(str(agent_name), block.text)
                        if langsmith_run:
                            langsmith_run.add_event({
                                "name": "text_block",
                                "text_preview": block.text[:500] if len(block.text) > 500 else block.text,
                            })

                    elif isinstance(block, ToolUseBlock):
                        if self._tracer:
                            self._tracer.log_tool_use(
                                str(agent_name), block.id, block.name, block.input
                            )
                        if langsmith_run:
                            langsmith_run.add_event({
                                "name": "tool_use",
                                "tool": block.name,
                                "tool_id": block.id,
                                "input": block.input,
                            })

            elif isinstance(message, UserMessage):
                for block in message.content:
                    if isinstance(block, ToolResultBlock):
                        content = block.content
                        if isinstance(content, list):
                            content = str(content)
                        if self._tracer:
                            self._tracer.log_tool_result(
                                str(agent_name), block.tool_use_id, content,
                                is_error=block.is_error or False
                            )
                        if langsmith_run:
                            langsmith_run.add_event({
                                "name": "tool_result",
                                "tool_id": block.tool_use_id,
                                "is_error": block.is_error or False,
                            })

            elif isinstance(message, ToolResultBlock):
                content = message.content
                if isinstance(content, list):
                    content = str(content)
                if self._tracer:
                    self._tracer.log_tool_result(
                        str(agent_name), message.tool_use_id, content,
                        is_error=message.is_error or False
                    )

            elif isinstance(message, ResultMessage):
                if message.is_error:
                    logger.error(f"Turn error for {agent_name}: {message.result}")

                session_id = getattr(message, 'session_id', None)
                duration_ms = getattr(message, 'duration_ms', 0)
                cost_usd = getattr(message, 'total_cost_usd', None)
                num_turns = getattr(message, 'num_turns', 0)

                # Extract token usage
                usage = getattr(message, 'usage', None)
                if usage:
                    input_tokens = usage.get('input_tokens', 0)
                    output_tokens = usage.get('output_tokens', 0)
                    cache_creation = usage.get('cache_creation_input_tokens', 0)
                    cache_read = usage.get('cache_read_input_tokens', 0)

                    context_window_size = cache_read + input_tokens
                    self._token_counts[agent_name] = context_window_size

                    logger.debug(
                        f"[{agent_name}] Context window: {context_window_size} | "
                        f"Per-turn: in={input_tokens}, out={output_tokens}"
                    )

                    turn_token_usage = TurnTokenUsage(
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cache_creation_input_tokens=cache_creation,
                        cache_read_input_tokens=cache_read,
                        model_id=model_id,
                    )

                    if self._tracer:
                        self._tracer.log_token_update(
                            str(agent_name), context_window_size
                        )

                if langsmith_run:
                    langsmith_run.metadata["session_id"] = session_id
                    langsmith_run.metadata["duration_ms"] = duration_ms
                    langsmith_run.metadata["cost_usd"] = cost_usd
                    langsmith_run.metadata["sdk_turns"] = num_turns

        narrative = "\n".join(narrative_parts)
        logger.debug(
            f"[{agent_name}] receive_response() loop ended, "
            f"got {message_count} messages, narrative_len={len(narrative)}"
        )

        # End tracing
        if self._tracer:
            self._tracer.end_turn(
                str(agent_name), narrative, session_id,
                duration_ms, cost_usd, num_turns
            )

        # Get accumulated actions and events from tool context
        actions_taken = list(tool_context.actions_taken)
        events = list(tool_context.accumulated_events)

        logger.debug(
            f"Turn complete for {agent_name} | "
            f"narrative_len={len(narrative)} | "
            f"actions={len(actions_taken)} | "
            f"events={len(events)}"
        )

        return ProviderTurnResult(
            narrative=narrative,
            actions_taken=actions_taken,
            events=events,
            session_id=session_id,
            token_usage=turn_token_usage,
        )

    async def _get_or_create_client(self, agent: "Agent") -> ClaudeSDKClient:
        """Get existing client or create a new one for an agent."""
        agent_name = agent.name

        if agent_name not in self._clients:
            model_id = self._prompt_builder.get_model_id(str(agent_name))
            logger.info(f"Creating new client for {agent_name} with model {model_id}")

            # Ensure agent home directory exists
            agent_dir = self._agents_root / str(agent_name)
            agent_dir.mkdir(parents=True, exist_ok=True)

            # Create initial files if they don't exist
            self._ensure_agent_files(agent_dir)

            # Ensure agent has a tool state
            if agent_name not in self._agent_states:
                self._agent_states[agent_name] = AgentToolState()

            # Create per-agent MCP server
            agent_mcp_server = create_hearth_mcp_server(
                agent_name, self._agent_states[agent_name]
            )

            system_prompt = self._prompt_builder.build_system_prompt(agent)

            # Resume from previous session if available
            session_id = agent.session_id

            options = ClaudeAgentOptions(
                model=model_id,
                system_prompt=system_prompt,
                mcp_servers={"hearth": agent_mcp_server},
                allowed_tools=[
                    "Read", "Write", "Edit", "Glob", "Grep",
                    *HEARTH_TOOL_NAMES
                ],
                permission_mode="acceptEdits",
                cwd=str(agent_dir),
                max_turns=50,
            )

            if session_id:
                options = dataclasses.replace(options, resume=session_id)

            client = ClaudeSDKClient(options=options)
            await client.connect()
            self._clients[agent_name] = client

            # Create persistent input stream and start query
            input_stream = PersistentInputStream(name=str(agent_name))
            self._input_streams[agent_name] = input_stream
            task = asyncio.create_task(client.query(input_stream))
            self._query_tasks[agent_name] = task
            logger.debug(f"Started streaming session for {agent_name}, task={task}")

        return self._clients[agent_name]

    def _ensure_agent_files(self, agent_dir: Path) -> None:
        """Ensure agent's home directory has required files."""
        # journal.md
        journal = agent_dir / "journal.md"
        if not journal.exists():
            journal.write_text("# Journal\n\nYour personal journal. Write anything here.\n")

        # notes.md
        notes = agent_dir / "notes.md"
        if not notes.exists():
            notes.write_text("# Notes\n\nWorking notes and observations.\n")

        # discoveries.md
        discoveries = agent_dir / "discoveries.md"
        if not discoveries.exists():
            discoveries.write_text("# Discoveries\n\nThings you've learned about the world.\n")

    async def disconnect_agent(self, agent_name: AgentName) -> None:
        """Disconnect a specific agent's client."""
        if agent_name in self._input_streams:
            self._input_streams[agent_name].close()
            del self._input_streams[agent_name]

        if agent_name in self._query_tasks:
            task = self._query_tasks.pop(agent_name)
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        if agent_name in self._clients:
            client = self._clients.pop(agent_name)
            await client.disconnect()
            logger.info(f"Disconnected client for {agent_name}")

    async def disconnect_all(self) -> None:
        """Disconnect all agent clients."""
        for agent_name in list(self._clients.keys()):
            await self.disconnect_agent(agent_name)
        logger.info("All clients disconnected")

    def get_connected_agents(self) -> list[AgentName]:
        """Get list of agents with active clients."""
        return list(self._clients.keys())

    def get_token_count(self, agent_name: AgentName) -> int:
        """Get current context window size for an agent."""
        return self._token_counts.get(agent_name, 0)

    def reset_session_after_compaction(
        self,
        agent_name: AgentName,
        post_compaction_tokens: int,
    ) -> None:
        """Update local tracking after compaction."""
        self._token_counts[agent_name] = post_compaction_tokens
        logger.info(
            f"Updated context window for {agent_name} after compaction: "
            f"{post_compaction_tokens}"
        )
