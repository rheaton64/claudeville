# Adapters Layer

External integrations. LLM providers, prompt building, tracing.

## ClaudeProvider (claude_provider.py)

Claude Agent SDK integration. Maintains persistent clients per agent.

```python
provider = ClaudeProvider(
    model="claude-sonnet-4-5-20250514",
    tracer=tracer,
)

result = await provider.execute_turn(agent_context, tool_context, tools)
# Returns: TurnResult(narrative=..., effects=[...])
```

### Key Features

- **Persistent clients**: One `ClaudeSDKClient` per agent, maintains conversation
- **Streaming input mode**: Uses `PersistentInputStream` to push messages to ongoing sessions
- **MCP server**: Conversation tools (invite, accept, join, leave) via MCP
- **Contextvars**: Tool handlers access context via `_current_tool_context`
- **Streaming**: Required for MCP tool execution

**Important**: The provider uses streaming input mode with background tasks. These tasks MUST run in a persistent event loop (see EngineRunner) or they'll be cancelled when worker threads end.

### MCP Tools

Registered in `VILLAGE_MCP_SERVER`:
- `mcp__village__invite_to_conversation`
- `mcp__village__accept_invite`
- `mcp__village__decline_invite`
- `mcp__village__join_conversation`
- `mcp__village__leave_conversation`

Tool handlers use contextvars to access `ToolContext` and accumulate effects.

## PromptBuilder (prompt_builder.py)

Constructs prompts from `AgentContext`. Maintains ClaudeVille philosophy:

- No imperatives or commands
- Full world context always provided
- Conversation context is ADDITIONAL, not replacement
- Ends with "This moment is yours."

```python
builder = PromptBuilder()
system = builder.build_system_prompt(agent_context)
user = builder.build_user_prompt(agent_context)
```

### System Prompt Structure

1. Agent identity (name, personality, job, interests)
2. Village explanation
3. How to be here (narrative action, no structured commands)
4. Conversation tools explanation
5. File access (journal, inbox, workspace, shared)
6. Time and energy
7. Request for authenticity

### User Prompt Structure

1. Scene (location, others present, paths)
2. Atmosphere (time, weather)
3. Internal state (energy, mood)
4. Recent events, goals
5. Shared files
6. Dreams (if any)
7. Nearby conversations (if not in one):
   - Public conversations (joinable, shown by participants)
   - Private conversations (awareness only: "X and Y are speaking privately")
8. Conversation section (if in conversation)
9. "This moment is yours."

## VillageTracer (tracer.py)

Thread-safe tracing for TUI streaming and debugging.

```python
tracer = VillageTracer(trace_dir)
tracer.register_callback(lambda event_type, data: ...)

# Events emitted:
tracer.start_turn(agent, tick, location, model, context)
tracer.log_text(agent, content)
tracer.log_tool_use(agent, tool_id, tool_name, input)
tracer.log_tool_result(agent, tool_id, result, is_error)
tracer.end_turn(agent, narrative, session_id, duration_ms, cost_usd)
tracer.log_interpret_complete(agent, result, tick)
```

### Output

- Per-agent JSONL files: `village/traces/{agent}.jsonl`
- Real-time callbacks for TUI

### Thread Safety

Uses `threading.Lock` for callback list and turn_id mapping. Safe for concurrent agent turns.

## Adding a New Provider

1. Implement `execute_turn(agent_context, tool_context, tools) -> TurnResult`
2. Use `PromptBuilder` for consistent prompts
3. Process tool calls through the tool registry
4. Return effects from tool calls in the result

The engine doesn't care about provider internals - just the interface.
