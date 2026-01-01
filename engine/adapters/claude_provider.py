"""
ClaudeProvider - Claude Agent SDK integration for ClaudeVille.

Uses the Claude Agent SDK with:
- Persistent ClaudeSDKClient per agent (maintains conversation)
- Per-agent MCP server with closures capturing agent-specific state
- Streaming input (required for MCP tools)
- LangSmith tracing via manual trace context manager

NOTE: We create a separate MCP server per agent because:
1. Tool handlers run in a background async context spawned by the SDK
2. Contextvars don't propagate to that context
3. Each agent needs their own state (tool_context, effects, tools)
4. With parallel agent execution, a shared state would cause collisions

The MCP tools are generated dynamically from CONVERSATION_TOOL_REGISTRY,
so tool definitions only need to be maintained in one place.
"""

import asyncio
import dataclasses
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable

from langsmith import trace as langsmith_trace

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    tool,
    create_sdk_mcp_server,
    AssistantMessage,
    TextBlock,
    ResultMessage,
    SystemMessage,
    ToolUseBlock,
    ToolResultBlock,
    UserMessage,
)

from engine.domain import (
    AgentName,
    Effect,
    UpdateSessionIdEffect,
    AcceptInviteEffect,
    JoinConversationEffect,
    LeaveConversationEffect,
    AgentSnapshot,
)
from engine.runtime.phases.agent_turn import (
    AgentContext,
    ToolContext,
    TurnResult,
    TurnTokenUsage,
    ConversationTool,
    CONVERSATION_TOOL_REGISTRY,
)
from .prompt_builder import PromptBuilder
from .tracer import VillageTracer


logger = logging.getLogger(__name__)


def _format_tool_call(name: str, input_dict: dict[str, Any]) -> str:
    """Format a tool call for display in conversation narrative.

    Produces: [tool_name(arg1=val1, arg2=val2)]
    """
    # Strip MCP prefix if present
    display_name = name.replace("mcp__village__", "")

    if not input_dict:
        return f"[{display_name}]"

    # Format args, truncating long values
    args = []
    for k, v in input_dict.items():
        if v is None:
            continue
        v_str = str(v)
        if len(v_str) > 50:
            v_str = v_str[:47] + "..."
        args.append(f"{k}={v_str}")

    if args:
        return f"[{display_name}({', '.join(args)})]"
    return f"[{display_name}]"


# =============================================================================
# Per-Agent Tool State
# =============================================================================

@dataclass
class AgentToolState:
    """
    Mutable state for an agent's MCP tool handlers.

    Each agent gets their own instance, which is captured by closures
    in their MCP tool handlers. The state is updated each turn before
    the LLM call, so tools see the current context.

    Uses asyncio.Lock for thread safety since MCP tool handlers run in
    background async contexts that could interleave with the message loop.
    """
    tool_context: ToolContext | None = None
    effects: list[Effect] = field(default_factory=list)
    tools: dict[str, ConversationTool] = field(default_factory=dict)

    # Track conversation entry/exit messages
    narrative_parts: list[str] = field(default_factory=list)
    capturing_first_message: bool = False
    first_message_parts: list[str] = field(default_factory=list)
    pre_leave_narrative: str | None = None

    # Lock for async thread safety
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def update_for_turn(
        self,
        tool_context: ToolContext,
        effects: list[Effect],
        tools: dict[str, ConversationTool],
    ) -> None:
        """Update state for a new turn."""
        self.tool_context = tool_context
        self.effects = effects
        self.tools = tools
        # Reset message capture state
        self.narrative_parts = []
        self.capturing_first_message = False
        self.first_message_parts = []
        self.pre_leave_narrative = None


class PersistentInputStream:
    """
    A persistent input stream for streaming input mode.

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
        logger.debug(f"[STREAM:{self._name}] push() #{self._push_count}, queue_size_before={self._queue.qsize()}")
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
        logger.debug(f"[STREAM:{self._name}] __anext__() #{self._next_count} called, queue_size={self._queue.qsize()}")
        msg = await self._queue.get()
        got_msg = msg is not None and not self._closed
        logger.debug(f"[STREAM:{self._name}] __anext__() #{self._next_count} got message: {got_msg}")
        if msg is None or self._closed:
            raise StopAsyncIteration
        return msg


def _create_mcp_tool_handler(
    tool_name: str,
    tool_def: ConversationTool,
    state: AgentToolState,
) -> Callable:
    """
    Create an MCP tool handler that captures the agent's state.

    The handler is a closure that references the agent's AgentToolState,
    allowing it to access the current turn's context even though MCP
    tools run in a different async context.
    """
    # Convert JSON Schema input_schema to SDK format
    # The SDK @tool decorator expects {param_name: type} dict
    sdk_params = {}
    if "properties" in tool_def.input_schema:
        for param_name, param_def in tool_def.input_schema["properties"].items():
            # Map JSON Schema types to Python types
            type_map = {"string": str, "integer": int, "boolean": bool, "number": float}
            param_type = type_map.get(param_def.get("type", "string"), str)
            sdk_params[param_name] = param_type

    @tool(tool_name, tool_def.description, sdk_params)
    async def handler(args: dict[str, Any]) -> dict[str, Any]:
        if state.tool_context is None:
            return {"content": [{"type": "text", "text": "Tool called outside of turn context."}]}

        processor = state.tools.get(tool_name)
        if not processor:
            return {"content": [{"type": "text", "text": "Tool not configured."}]}

        # Process tool under lock for thread safety
        async with state._lock:
            # For leave_conversation: capture narrative BEFORE processing
            if tool_name == "leave_conversation":
                state.pre_leave_narrative = "\n".join(state.narrative_parts).strip() or None

            new_effects = processor.processor(args, state.tool_context)
            state.effects.extend(new_effects)

            # For accept/join: start capturing text AFTER the tool call
            if tool_name in ("accept_invite", "join_conversation") and new_effects:
                state.capturing_first_message = True

            had_effects = bool(new_effects)

        # Return response message based on whether effects were produced
        if had_effects:
            # Success messages vary by tool
            if tool_name == "invite_to_conversation":
                return {"content": [{"type": "text", "text": f"Invitation sent to {args.get('invitee')}."}]}
            elif tool_name == "accept_invite":
                return {"content": [{"type": "text", "text": "You accepted the invitation."}]}
            elif tool_name == "decline_invite":
                return {"content": [{"type": "text", "text": "You declined the invitation."}]}
            elif tool_name == "join_conversation":
                return {"content": [{"type": "text", "text": "You joined the conversation."}]}
            elif tool_name == "leave_conversation":
                return {"content": [{"type": "text", "text": "You left the conversation."}]}
            elif tool_name == "move_conversation":
                return {"content": [{"type": "text", "text": f"Everyone will move to {args.get('destination')} once you finish speaking."}]}
            else:
                return {"content": [{"type": "text", "text": "Action completed."}]}
        else:
            # Failure messages vary by tool
            if tool_name == "invite_to_conversation":
                return {"content": [{"type": "text", "text": f"Could not invite {args.get('invitee')} - they may not be at your location."}]}
            elif tool_name in ("accept_invite", "decline_invite"):
                return {"content": [{"type": "text", "text": "No matching invitation found."}]}
            elif tool_name == "join_conversation":
                return {"content": [{"type": "text", "text": "Could not join - conversation may not be public or not at your location."}]}
            elif tool_name == "leave_conversation":
                return {"content": [{"type": "text", "text": "You're not in that conversation."}]}
            elif tool_name == "move_conversation":
                return {"content": [{"type": "text", "text": f"Cannot move to {args.get('destination')} - it may not be connected to your current location, or you may not be in a conversation."}]}
            else:
                return {"content": [{"type": "text", "text": "Action failed."}]}

    return handler


def _create_agent_mcp_server(agent_name: AgentName, state: AgentToolState):
    """
    Create an MCP server for a specific agent with tools generated from the registry.

    Each agent gets their own MCP server with closures that reference their
    AgentToolState. This ensures parallel execution is safe - each agent's
    tools only access their own state.
    """
    # Generate tool handlers from the registry
    tool_handlers = []
    for tool_name, tool_def in CONVERSATION_TOOL_REGISTRY.items():
        handler = _create_mcp_tool_handler(tool_name, tool_def, state)
        tool_handlers.append(handler)

    # Create the MCP server with the agent-specific tool handlers
    return create_sdk_mcp_server(
        name="village",
        version="1.0.0",
        tools=tool_handlers,
    )


# Tool names as they appear to Claude (with MCP prefix)
# Generated from the registry
VILLAGE_TOOL_NAMES = [
    f"mcp__village__{name}" for name in CONVERSATION_TOOL_REGISTRY.keys()
]


# =============================================================================
# Claude Provider
# =============================================================================

class ClaudeProvider:
    """
    LLM provider using Claude Agent SDK.

    Maintains a persistent ClaudeSDKClient per agent, which keeps
    conversation context across turns automatically.

    Each agent gets their own MCP server with closures that capture
    agent-specific state. This ensures parallel execution is safe.
    """

    def __init__(
        self,
        system_prompt_preset: bool = False,
        tracer: VillageTracer | None = None,
    ):
        """
        Initialize the provider.

        Args:
            system_prompt_preset: Whether to use Claude Code's system prompt preset
            tracer: Optional tracer for real-time event streaming
        """
        self._system_prompt_preset = system_prompt_preset
        self._clients: dict[AgentName, ClaudeSDKClient] = {}
        self._input_streams: dict[AgentName, PersistentInputStream] = {}
        self._query_tasks: dict[AgentName, asyncio.Task] = {}  # Track background tasks
        self._agent_states: dict[AgentName, AgentToolState] = {}
        self._prompt_builder = PromptBuilder()
        self._tracer = tracer
        # Context window size for compaction threshold
        # Uses cache_read_input_tokens + input_tokens from SDK usage
        # SDK tracks this server-side and persists across session resumes
        self._token_counts: dict[AgentName, int] = {}

    async def execute_turn(
        self,
        agent_context: AgentContext,
        tool_context: ToolContext,
        tools: dict[str, ConversationTool],
        agent_dir: str | None = None,
    ) -> TurnResult:
        """
        Execute an agent's turn.

        Args:
            agent_context: Context for building the prompt
            tool_context: Context passed to tool processors
            tools: Tool registry with processors

        Returns:
            TurnResult with narrative and effects from tool calls
        """
        agent_name = agent_context.agent.name
        effects: list[Effect] = []

        # Get or create the agent's tool state and update it for this turn
        if agent_name not in self._agent_states:
            self._agent_states[agent_name] = AgentToolState()
        self._agent_states[agent_name].update_for_turn(tool_context, effects, tools)

        # Check if LangSmith tracing is enabled
        langsmith_enabled = os.environ.get("LANGSMITH_TRACING", "").lower() == "true"

        # Get or create client for this agent
        client = await self._get_or_create_client(agent_name, agent_context, agent_dir)

        # Build prompts
        system_prompt = self._prompt_builder.build_system_prompt(agent_context)
        user_prompt = self._prompt_builder.build_user_prompt(agent_context)

        # Execute with LangSmith tracing if enabled
        if langsmith_enabled:
            return await self._execute_turn_with_langsmith(
                client, agent_name, agent_context, tool_context,
                user_prompt, effects
            )
        else:
            return await self._execute_turn_internal(
                client, agent_name, agent_context, tool_context,
                user_prompt, effects, langsmith_run=None
            )

    async def _execute_turn_with_langsmith(
        self,
        client: ClaudeSDKClient,
        agent_name: AgentName,
        agent_context: AgentContext,
        tool_context: ToolContext,
        user_prompt: str,
        effects: list[Effect],
    ) -> TurnResult:
        """Execute turn wrapped in LangSmith trace context."""
        model_id = agent_context.agent.model.id
        async with langsmith_trace(
            name=f"agent_turn:{agent_name}",
            run_type="chain",
            inputs={
                "agent": str(agent_name),
                "tick": tool_context.tick_context.tick,
                "location": str(agent_context.agent.location),
                "prompt": user_prompt,
            },
            metadata={
                "model": model_id,
                "agent_job": agent_context.agent.job,
                "agent_mood": agent_context.agent.mood,
                "agent_energy": agent_context.agent.energy,
                "in_conversation": agent_context.conversation is not None,
            },
            tags=["agent_turn", str(agent_name), model_id],
        ) as run:
            result = await self._execute_turn_internal(
                client, agent_name, agent_context, tool_context,
                user_prompt, effects, langsmith_run=run
            )

            # End LangSmith run with outputs
            run.end(outputs={
                "narrative": result.narrative,
                "effects_count": len(result.effects),
                "effects": [type(e).__name__ for e in result.effects],
            })

            return result

    async def _execute_turn_internal(
        self,
        client: ClaudeSDKClient,
        agent_name: AgentName,
        agent_context: AgentContext,
        tool_context: ToolContext,
        user_prompt: str,
        effects: list[Effect],
        langsmith_run: Any | None,
    ) -> TurnResult:
        """Internal turn execution logic."""
        model_id = agent_context.agent.model.id

        # Check background task status
        task = self._query_tasks.get(agent_name)
        if task:
            task_done = task.done()
            task_cancelled = task.cancelled()
            task_exception = None
            if task_done and not task_cancelled:
                try:
                    task_exception = task.exception()
                except Exception:
                    pass
            logger.debug(
                f"[{agent_name}] Background task status: done={task_done}, "
                f"cancelled={task_cancelled}, exception={task_exception}"
            )
            if task_done:
                logger.error(f"[{agent_name}] Background query task has ENDED! This is the bug.")
        else:
            logger.warning(f"[{agent_name}] No background task found!")

        # Start VillageTracer tracing
        if self._tracer:
            self._tracer.start_turn(
                agent_name=str(agent_name),
                tick=tool_context.tick_context.tick,
                location=str(agent_context.agent.location),
                model=model_id,
                context=user_prompt,
            )

        # Get the persistent input stream for this agent (created with client)
        input_stream = self._input_streams[agent_name]

        # Push this turn's message to the stream
        # The SDK is already iterating over the stream (query() called at client creation)
        logger.debug(f"[{agent_name}] Pushing message to stream (len={len(user_prompt)})")
        await input_stream.push({
            "type": "user",
            "message": {
                "role": "user",
                "content": user_prompt,
            }
        })
        # Yield to event loop so the background query() task can receive the message
        # Without this, receive_response() may return empty because the SDK hasn't
        # had a chance to process the pushed message yet
        await asyncio.sleep(0)
        logger.debug(f"[{agent_name}] Message pushed, calling receive_response()")

        # Collect narrative and metadata from response
        narrative_parts: list[str] = []
        narrative_with_tools_parts: list[str] = []  # Interleaved text + tool calls
        message_count = 0
        session_id: str | None = None
        duration_ms: int = 0
        cost_usd: float | None = None
        num_turns: int = 0
        tool_calls_count: int = 0
        turn_token_usage: TurnTokenUsage | None = None

        async for message in client.receive_response():
            message_count += 1
            logger.debug(f"[{agent_name}] receive_response() yielded message #{message_count}: {type(message).__name__}")
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        narrative_parts.append(block.text)
                        narrative_with_tools_parts.append(block.text)
                        # Track on state for MCP tool handlers (under lock for thread safety)
                        state = self._agent_states[agent_name]
                        async with state._lock:
                            state.narrative_parts.append(block.text)
                            # Capture first message parts if we're after accept/join
                            if state.capturing_first_message:
                                state.first_message_parts.append(block.text)
                        if self._tracer:
                            self._tracer.log_text(str(agent_name), block.text)
                        # Add LangSmith event for text streaming
                        if langsmith_run:
                            langsmith_run.add_event({
                                "name": "text_block",
                                "text_preview": block.text[:500] if len(block.text) > 500 else block.text,
                            })

                    elif isinstance(block, ToolUseBlock):
                        tool_calls_count += 1
                        # Add formatted tool call to interleaved narrative
                        narrative_with_tools_parts.append(
                            _format_tool_call(block.name, block.input)
                        )
                        if self._tracer:
                            self._tracer.log_tool_use(
                                str(agent_name), block.id, block.name, block.input
                            )
                        # Add LangSmith event for tool use
                        if langsmith_run:
                            langsmith_run.add_event({
                                "name": "tool_use",
                                "tool": block.name,
                                "tool_id": block.id,
                                "input": block.input,
                            })

            elif isinstance(message, UserMessage):
                # Tool results come wrapped in UserMessage
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
                        # Add LangSmith event for tool result
                        if langsmith_run:
                            langsmith_run.add_event({
                                "name": "tool_result",
                                "tool_id": block.tool_use_id,
                                "is_error": block.is_error or False,
                                "result_preview": content[:500] if content and len(content) > 500 else content,
                            })

            elif isinstance(message, ToolResultBlock):
                # Tool results can also come directly in stream
                content = message.content
                if isinstance(content, list):
                    content = str(content)
                if self._tracer:
                    self._tracer.log_tool_result(
                        str(agent_name), message.tool_use_id, content,
                        is_error=message.is_error or False
                    )
                if langsmith_run:
                    langsmith_run.add_event({
                        "name": "tool_result",
                        "tool_id": message.tool_use_id,
                        "is_error": message.is_error or False,
                    })

            elif isinstance(message, ResultMessage):
                if message.is_error:
                    logger.error(
                        f"Turn error for {agent_name}: {message.result}"
                    )
                # Capture metadata
                session_id = getattr(message, 'session_id', None)
                duration_ms = getattr(message, 'duration_ms', 0)
                cost_usd = getattr(message, 'total_cost_usd', None)
                num_turns = getattr(message, 'num_turns', 0)

                # Extract token usage from SDK
                # See docs/sdk-token-tracking-behavior.md for detailed analysis
                usage = getattr(message, 'usage', None)
                if usage:
                    # Per-turn tokens (for billing/usage tracking)
                    # These are fresh values each turn, NOT cumulative
                    input_tokens = usage.get('input_tokens', 0)
                    output_tokens = usage.get('output_tokens', 0)
                    cache_creation = usage.get('cache_creation_input_tokens', 0)
                    cache_read = usage.get('cache_read_input_tokens', 0)

                    # Context window size (for compaction threshold)
                    # Includes all tokens being processed this turn:
                    # - cache_read: tokens from previous turns (cumulative)
                    # - input: new user input tokens (per-turn)
                    # - cache_creation: new tokens being cached (per-turn)
                    context_window_size = cache_read + input_tokens + cache_creation
                    self._token_counts[agent_name] = context_window_size

                    logger.debug(
                        f"[{agent_name}] Context window: {context_window_size} | "
                        f"Per-turn: in={input_tokens}, out={output_tokens}, "
                        f"cache_read={cache_read}, cache_create={cache_creation}"
                    )

                    # Create token usage for this turn
                    # These are per-turn values that get ADDED to cumulative totals
                    # by the effect/event system
                    turn_token_usage = TurnTokenUsage(
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cache_creation_input_tokens=cache_creation,
                        cache_read_input_tokens=cache_read,
                        model_id=model_id,
                    )

                    # Emit token update event for TUI display
                    if self._tracer:
                        from engine.services import CRITICAL_THRESHOLD
                        self._tracer.log_token_update(
                            str(agent_name), context_window_size, CRITICAL_THRESHOLD
                        )

                # Update LangSmith metadata with SDK metrics
                if langsmith_run:
                    langsmith_run.metadata["session_id"] = session_id
                    langsmith_run.metadata["duration_ms"] = duration_ms
                    langsmith_run.metadata["cost_usd"] = cost_usd
                    langsmith_run.metadata["sdk_turns"] = num_turns
                    langsmith_run.metadata["tool_calls_count"] = tool_calls_count

        narrative = "\n".join(narrative_parts)
        narrative_with_tools = "\n\n".join(narrative_with_tools_parts)
        logger.debug(f"[{agent_name}] receive_response() loop ended, got {message_count} messages, narrative_len={len(narrative)}")

        # End VillageTracer tracing (before interpretation)
        if self._tracer:
            self._tracer.end_turn(
                str(agent_name), narrative, session_id,
                duration_ms, cost_usd, num_turns
            )

        # Save session ID for future resumption (only on first turn)
        if session_id and agent_context.agent.session_id is None:
            effects.append(UpdateSessionIdEffect(
                agent=agent_name,
                session_id=session_id,
            ))

        # Attach captured messages to conversation effects
        state = self._agent_states[agent_name]

        # Attach first_message to accept/join effects
        if state.first_message_parts:
            first_message = "\n".join(state.first_message_parts).strip()
            if first_message:
                for i, effect in enumerate(effects):
                    if isinstance(effect, AcceptInviteEffect):
                        effects[i] = effect.model_copy(update={"first_message": first_message})
                        break
                    elif isinstance(effect, JoinConversationEffect):
                        effects[i] = effect.model_copy(update={"first_message": first_message})
                        break

        # Attach last_message to leave effect
        if state.pre_leave_narrative:
            for i, effect in enumerate(effects):
                if isinstance(effect, LeaveConversationEffect):
                    effects[i] = effect.model_copy(update={"last_message": state.pre_leave_narrative})
                    break

        logger.debug(
            f"Turn complete for {agent_name} | "
            f"narrative_len={len(narrative)} | "
            f"effects={len(effects)}"
        )

        return TurnResult(
            narrative=narrative,
            effects=list(effects),
            narrative_with_tools=narrative_with_tools,
            token_usage=turn_token_usage,
        )

    async def _get_or_create_client(
        self,
        agent_name: AgentName,
        agent_context: AgentContext,
        agent_dir: str | None,
    ) -> ClaudeSDKClient:
        """Get existing client or create a new one for an agent."""
        if agent_name not in self._clients:
            model_id = agent_context.agent.model.id
            logger.info(f"Creating new client for {agent_name} with model {model_id}")

            # Ensure agent has a tool state (for MCP server closures)
            if agent_name not in self._agent_states:
                self._agent_states[agent_name] = AgentToolState()

            # Create per-agent MCP server with closures capturing their state
            agent_mcp_server = _create_agent_mcp_server(
                agent_name, self._agent_states[agent_name]
            )

            system_prompt = self._prompt_builder.build_system_prompt(agent_context)

            # Resume from previous session if available
            session_id = agent_context.agent.session_id

            options = ClaudeAgentOptions(
                model=model_id,
                system_prompt=system_prompt,
                mcp_servers={"village": agent_mcp_server},
                allowed_tools=["Read", "Write", "Task", "Bash", "Grep", "Glob", "Edit", "TodoWrite", *VILLAGE_TOOL_NAMES],
                permission_mode="acceptEdits",
                cwd=agent_dir,
                max_turns=100,  # Limit agentic loops per turn
            )
            if session_id:
                options = dataclasses.replace(options, resume=session_id)
            client = ClaudeSDKClient(options=options)
            await client.connect()
            self._clients[agent_name] = client

            # Create persistent input stream and start the query session
            # The SDK will iterate over the stream for the lifetime of the session
            # NOTE: We use create_task() instead of await because query() blocks
            # waiting for the first message. The task runs in background and
            # processes messages as they are pushed to the stream.
            input_stream = PersistentInputStream(name=str(agent_name))
            self._input_streams[agent_name] = input_stream
            task = asyncio.create_task(client.query(input_stream))
            self._query_tasks[agent_name] = task
            logger.debug(f"Started streaming session for {agent_name}, task={task}")

        return self._clients[agent_name]

    async def disconnect_agent(self, agent_name: AgentName) -> None:
        """Disconnect a specific agent's client."""
        # Close the input stream first to signal end of session
        if agent_name in self._input_streams:
            self._input_streams[agent_name].close()
            del self._input_streams[agent_name]

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
        """Get cumulative token count for an agent.

        Returns the total input + output tokens from the most recent turn.
        This is the SDK's cumulative usage tracking.
        """
        return self._token_counts.get(agent_name, 0)

    def restore_token_counts(self, agents: dict[AgentName, "AgentSnapshot"]) -> None:
        """Called on startup - but context window tracking is handled by SDK.

        The SDK tracks context window size (cache_read_input_tokens) server-side
        and this persists across session resumes. The first turn after restart
        will automatically report the correct context window size.

        This method is kept for compatibility but doesn't need to do much.
        The actual context window size will be populated on the first turn.

        Args:
            agents: Dictionary of agent snapshots (unused for compaction)
        """
        # Context window tracking is handled by SDK server-side via session resume
        # The first turn will populate _token_counts with the correct value
        # We just log for visibility
        for name in agents:
            logger.info(f"Agent {name} ready - context window will be tracked by SDK")

    def reset_session_after_compaction(
        self, agent_name: AgentName, post_compaction_tokens: int
    ) -> None:
        """Update local tracking after compaction.

        After compaction, the SDK's context window shrinks. We update our local
        tracking to reflect the new post-compaction context size.

        Args:
            agent_name: Which agent was compacted
            post_compaction_tokens: New context window size after compaction
        """
        self._token_counts[agent_name] = post_compaction_tokens
        logger.info(
            f"Updated context window for {agent_name} after compaction: {post_compaction_tokens}"
        )
