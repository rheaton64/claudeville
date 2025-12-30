# Streaming Input Mode

Understanding the two input modes for Claude Agent SDK and when to use each.

## Overview

The Claude Agent SDK supports two distinct input modes for interacting with agents:

- **Streaming Input Mode** (Default & Recommended) - A persistent, interactive session
- **Single Message Input** - One-shot queries that use session state and resuming

## Streaming Input Mode (Recommended)

Streaming input mode is the **preferred** way to use the Claude Agent SDK. It provides full access to the agent's capabilities and enables rich, interactive experiences.

It allows the agent to operate as a long lived process that takes in user input, handles interruptions, surfaces permission requests, and handles session management.

### How It Works

```
App -> Agent: Initialize with AsyncGenerator
App -> Agent: Yield Message 1
Agent -> Tools: Execute tools
Agent -> App: Stream response
Agent -> App: Complete Message 1

App -> Agent: Yield Message 2
Agent -> App: Stream response 2

Note: Session stays alive across messages
```

### Benefits

- **Image Uploads**: Attach images directly to messages for visual analysis
- **Queued Messages**: Send multiple messages that process sequentially, with ability to interrupt
- **Tool Integration**: Full access to all tools and custom MCP servers during the session
- **Hooks Support**: Use lifecycle hooks to customize behavior at various points
- **Real-time Feedback**: See responses as they're generated, not just final results
- **Context Persistence**: Maintain conversation context across multiple turns naturally

### Message Format

Messages yielded by the async generator should have this format:

```python
{
    "type": "user",
    "message": {
        "role": "user",
        "content": "Your message here"
    }
}
```

For messages with images:

```python
{
    "type": "user",
    "message": {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": "Review this image"
            },
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": "<base64_encoded_image>"
                }
            }
        ]
    }
}
```

### Implementation Example

```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, TextBlock
import asyncio

async def streaming_analysis():
    async def message_generator():
        # First message
        yield {
            "type": "user",
            "message": {
                "role": "user",
                "content": "Analyze this codebase for security issues"
            }
        }

        # Wait for conditions (e.g., user input)
        await asyncio.sleep(2)

        # Follow-up message
        yield {
            "type": "user",
            "message": {
                "role": "user",
                "content": "Now focus on authentication"
            }
        }

    options = ClaudeAgentOptions(
        max_turns=10,
        allowed_tools=["Read", "Grep"]
    )

    async with ClaudeSDKClient(options) as client:
        # Send streaming input
        await client.query(message_generator())

        # Process responses
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text)

asyncio.run(streaming_analysis())
```

## Single Message Input

Single message input is simpler but more limited.

### When to Use Single Message Input

Use single message input when:

- You need a one-shot response
- You do not need image attachments, hooks, etc.
- You need to operate in a stateless environment, such as a lambda function

### Limitations

Single message input mode does **not** support:
- Direct image attachments in messages
- Dynamic message queueing
- Real-time interruption
- Hook integration
- Natural multi-turn conversations

### Implementation Example

```python
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage
import asyncio

async def single_message_example():
    # Simple one-shot query using query() function
    async for message in query(
        prompt="Explain the authentication flow",
        options=ClaudeAgentOptions(
            max_turns=1,
            allowed_tools=["Read", "Grep"]
        )
    ):
        if isinstance(message, ResultMessage):
            print(message.result)

    # Continue conversation with session management
    async for message in query(
        prompt="Now explain the authorization process",
        options=ClaudeAgentOptions(
            continue_conversation=True,
            max_turns=1
        )
    ):
        if isinstance(message, ResultMessage):
            print(message.result)

asyncio.run(single_message_example())
```

## ClaudeVille's PersistentInputStream

ClaudeVille uses a custom `PersistentInputStream` class to enable reusable streaming input across multiple turns and run() calls:

```python
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

    def __init__(self):
        self._queue: asyncio.Queue[dict | None] = asyncio.Queue()
        self._closed = False

    async def push(self, message: dict) -> None:
        """Push a message to be yielded to the SDK."""
        if self._closed:
            raise RuntimeError("Stream is closed")
        await self._queue.put(message)

    def close(self) -> None:
        """Close the stream, causing StopAsyncIteration on next read."""
        self._closed = True
        self._queue.put_nowait(None)

    def __aiter__(self):
        return self

    async def __anext__(self) -> dict:
        msg = await self._queue.get()
        if msg is None or self._closed:
            raise StopAsyncIteration
        return msg
```

### Usage Pattern

```python
# When creating the client:
input_stream = PersistentInputStream()
client = ClaudeSDKClient(options=options)
await client.connect()

# Start the streaming session in the background
# NOTE: We use create_task() because query() blocks waiting for the first message.
# The task runs in background and processes messages as they are pushed.
asyncio.create_task(client.query(input_stream))

# Each turn:
await input_stream.push({"type": "user", "message": {...}})
async for msg in client.receive_response():
    # process response until ResultMessage

# When disconnecting:
input_stream.close()
await client.disconnect()
```

The key insight is that `query()` is called **once** when creating the client, but in the background via `create_task()`. The SDK blocks waiting for messages from the stream. When we push a message, the SDK processes it and we can iterate `receive_response()` to get the response.
