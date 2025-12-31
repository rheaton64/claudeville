"""
Smoke tests to verify SDK token tracking behavior.

These tests make actual API calls to verify our assumptions about:
1. SDK usage is cumulative within a session (across multiple query() calls)
2. New client/session resets token counts
3. What happens with session resume

Run with: uv run python tests/smoke_test_sdk_tokens.py
"""

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path

# Load .env file
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Ensure we have API key
if not os.environ.get("ANTHROPIC_API_KEY"):
    print("ERROR: ANTHROPIC_API_KEY not set")
    print(f"Checked .env at: {env_path}")
    exit(1)

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
)


@dataclass
class TurnUsage:
    """Token usage from a single turn."""
    input_tokens: int
    output_tokens: int
    total: int
    session_id: str | None = None


async def get_usage_from_response(client: ClaudeSDKClient) -> TurnUsage | None:
    """Extract usage from the ResultMessage after a query."""
    async for message in client.receive_response():
        if isinstance(message, ResultMessage):
            usage = getattr(message, 'usage', None)
            session_id = getattr(message, 'session_id', None)
            if usage:
                input_tokens = usage.get('input_tokens', 0)
                output_tokens = usage.get('output_tokens', 0)
                return TurnUsage(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total=input_tokens + output_tokens,
                    session_id=session_id,
                )
    return None


async def test_cumulative_within_session():
    """
    Test that SDK usage is cumulative within a session.

    Using ClaudeSDKClient with multiple query() calls on the same client.
    This is how ClaudeVille uses the SDK.
    """
    print("\n" + "=" * 60)
    print("TEST 1: Cumulative usage within session (same client)")
    print("=" * 60)

    async with ClaudeSDKClient(
        options=ClaudeAgentOptions(
            model="claude-haiku-4-5-20251001",
            max_turns=1,
        ),
    ) as client:
        # Turn 1
        print("\n--- Turn 1 ---")
        await client.query("Say 'hello' and nothing else.")
        usage1 = await get_usage_from_response(client)
        print(f"Usage after turn 1: {usage1}")

        # Turn 2 (same session)
        print("\n--- Turn 2 ---")
        await client.query("Say 'world' and nothing else.")
        usage2 = await get_usage_from_response(client)
        print(f"Usage after turn 2: {usage2}")

        # Turn 3 (same session)
        print("\n--- Turn 3 ---")
        await client.query("Say 'done' and nothing else.")
        usage3 = await get_usage_from_response(client)
        print(f"Usage after turn 3: {usage3}")

    # Analysis
    print("\n--- Analysis ---")
    if usage1 and usage2 and usage3:
        print(f"Turn 1 total: {usage1.total}")
        print(f"Turn 2 total: {usage2.total}")
        print(f"Turn 3 total: {usage3.total}")

        is_cumulative = usage2.total > usage1.total and usage3.total > usage2.total
        print(f"Is cumulative? {is_cumulative}")

        if is_cumulative:
            print("✓ CONFIRMED: SDK usage IS cumulative within a session")
            delta_2 = usage2.total - usage1.total
            delta_3 = usage3.total - usage2.total
            print(f"  Turn 2 delta: {delta_2}")
            print(f"  Turn 3 delta: {delta_3}")
        else:
            # Check if usage is per-turn instead
            is_per_turn = abs(usage1.total - usage2.total) < usage1.total * 0.5
            if is_per_turn:
                print("✗ UNEXPECTED: SDK usage appears to be PER-TURN, not cumulative")
            else:
                print("? UNCLEAR: Need more investigation")
    else:
        print("✗ Could not get usage from all turns")


async def test_new_client_resets():
    """Test that creating a new client resets token counts."""
    print("\n" + "=" * 60)
    print("TEST 2: New client resets token counts")
    print("=" * 60)

    # Client 1
    print("\n--- Client 1 ---")
    async with ClaudeSDKClient(
        options=ClaudeAgentOptions(model="claude-haiku-4-5-20251001", max_turns=1),
    ) as client1:
        await client1.query("Say 'client one' and nothing else.")
        usage1 = await get_usage_from_response(client1)
        print(f"Client 1 usage: {usage1}")

    # Client 2 (new client, new session)
    print("\n--- Client 2 (new client) ---")
    async with ClaudeSDKClient(
        options=ClaudeAgentOptions(model="claude-haiku-4-5-20251001", max_turns=1),
    ) as client2:
        await client2.query("Say 'client two' and nothing else.")
        usage2 = await get_usage_from_response(client2)
        print(f"Client 2 usage: {usage2}")

    # Analysis
    print("\n--- Analysis ---")
    if usage1 and usage2:
        print(f"Client 1 total: {usage1.total}")
        print(f"Client 2 total: {usage2.total}")
        print(f"Client 1 session: {usage1.session_id}")
        print(f"Client 2 session: {usage2.session_id}")

        # They should be similar (not cumulative across clients)
        ratio = usage2.total / usage1.total if usage1.total > 0 else 0
        if 0.5 < ratio < 2.0:
            print("✓ CONFIRMED: New client starts with fresh token counts")
        else:
            print(f"? UNCLEAR: Ratio of {ratio:.2f} - may need investigation")
    else:
        print("✗ Could not get usage from both clients")


async def test_session_resume():
    """Test what happens to token counts when resuming a session."""
    print("\n" + "=" * 60)
    print("TEST 3: Session resume behavior")
    print("=" * 60)

    # First session - capture session_id
    print("\n--- Initial session ---")
    session_id = None
    usage_before = None

    async with ClaudeSDKClient(
        options=ClaudeAgentOptions(model="claude-haiku-4-5-20251001", max_turns=1),
    ) as client1:
        await client1.query("Say 'first message' and nothing else.")
        usage_before = await get_usage_from_response(client1)
        session_id = usage_before.session_id if usage_before else None
        print(f"Session ID: {session_id}")
        print(f"Usage before disconnect: {usage_before}")

    if not session_id:
        print("✗ Could not get session_id, skipping resume test")
        return

    # Resume session
    print("\n--- Resumed session ---")
    async with ClaudeSDKClient(
        options=ClaudeAgentOptions(
            model="claude-haiku-4-5-20251001",
            max_turns=1,
            resume=session_id,
        ),
    ) as client2:
        await client2.query("Say 'second message' and nothing else.")
        usage_after = await get_usage_from_response(client2)
        print(f"Usage after resume: {usage_after}")
        print(f"New session ID: {usage_after.session_id if usage_after else None}")

    # Analysis
    print("\n--- Analysis ---")
    if usage_before and usage_after:
        print(f"Before disconnect: {usage_before.total}")
        print(f"After resume: {usage_after.total}")

        if usage_after.total > usage_before.total:
            print("✓ CONFIRMED: Resume continues cumulative counting")
            delta = usage_after.total - usage_before.total
            print(f"  Delta from resumed turn: {delta}")
        else:
            print("? Session resume may reset or use different tracking")
    else:
        print("✗ Could not get usage from both parts")


async def test_usage_structure():
    """Test the structure of the usage dict."""
    print("\n" + "=" * 60)
    print("TEST 4: Usage dict structure")
    print("=" * 60)

    async with ClaudeSDKClient(
        options=ClaudeAgentOptions(model="claude-haiku-4-5-20251001", max_turns=1),
    ) as client:
        await client.query("Say 'test' and nothing else.")

        async for message in client.receive_response():
            if isinstance(message, ResultMessage):
                usage = getattr(message, 'usage', None)
                print(f"\nResultMessage attributes:")
                print(f"  session_id: {getattr(message, 'session_id', None)}")
                print(f"  duration_ms: {getattr(message, 'duration_ms', None)}")
                print(f"  total_cost_usd: {getattr(message, 'total_cost_usd', None)}")
                print(f"  num_turns: {getattr(message, 'num_turns', None)}")
                print(f"\nUsage dict keys: {list(usage.keys()) if usage else None}")
                if usage:
                    for key, value in usage.items():
                        print(f"  {key}: {value}")
                break


async def main():
    """Run all smoke tests."""
    print("=" * 60)
    print("SDK Token Tracking Smoke Tests")
    print("=" * 60)
    print("These tests verify our assumptions about SDK token behavior.")
    print("Using model: claude-haiku-4-5-20251001")

    await test_cumulative_within_session()
    await test_new_client_resets()
    await test_session_resume()
    await test_usage_structure()

    print("\n" + "=" * 60)
    print("All tests complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
