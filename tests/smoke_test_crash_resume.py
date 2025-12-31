"""
Test simulating crash/restart to see how token counts behave.

Run this twice:
1. First run: creates session, does 3 turns, prints session_id
2. Second run: pass session_id as argument to resume and see token behavior

Usage:
  uv run python tests/smoke_test_crash_resume.py              # First run
  uv run python tests/smoke_test_crash_resume.py <session_id>  # Resume
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

if not os.environ.get("ANTHROPIC_API_KEY"):
    print("ERROR: ANTHROPIC_API_KEY not set")
    exit(1)

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    ResultMessage,
)


async def run_turns(client: ClaudeSDKClient, num_turns: int, start_num: int = 1):
    """Run N turns and print usage after each."""
    for i in range(num_turns):
        turn_num = start_num + i
        print(f"\n--- Turn {turn_num} ---")
        await client.query(f"Say 'turn {turn_num}' and nothing else.")

        async for message in client.receive_response():
            if isinstance(message, ResultMessage):
                usage = getattr(message, 'usage', None)
                session_id = getattr(message, 'session_id', None)
                if usage:
                    input_t = usage.get('input_tokens', 0)
                    output_t = usage.get('output_tokens', 0)
                    cache_read = usage.get('cache_read_input_tokens', 0)
                    cache_create = usage.get('cache_creation_input_tokens', 0)
                    print(f"  input_tokens: {input_t}")
                    print(f"  output_tokens: {output_t}")
                    print(f"  cache_read_input_tokens: {cache_read}")
                    print(f"  cache_creation_input_tokens: {cache_create}")
                    print(f"  raw_total (in+out): {input_t + output_t}")
                    print(f"  context_size (cache_read + in): {cache_read + input_t}")
                    print(f"  session_id: {session_id}")
                break

    return session_id


async def first_run():
    """First run: create fresh session, do 3 turns."""
    print("=" * 60)
    print("FIRST RUN: Fresh session")
    print("=" * 60)

    async with ClaudeSDKClient(
        options=ClaudeAgentOptions(
            model="claude-haiku-4-5-20251001",
            max_turns=1,
        ),
    ) as client:
        session_id = await run_turns(client, 3)

    print("\n" + "=" * 60)
    print("SESSION COMPLETE")
    print(f"Session ID: {session_id}")
    print("=" * 60)
    print(f"\nTo simulate restart, run:")
    print(f"  uv run python tests/smoke_test_crash_resume.py {session_id}")

    return session_id


async def resume_run(session_id: str):
    """Resume from session_id (simulating restart)."""
    print("=" * 60)
    print(f"RESUMED RUN: Continuing session {session_id[:20]}...")
    print("=" * 60)

    async with ClaudeSDKClient(
        options=ClaudeAgentOptions(
            model="claude-haiku-4-5-20251001",
            max_turns=1,
            resume=session_id,
        ),
    ) as client:
        # Continue with turns 4, 5, 6
        await run_turns(client, 3, start_num=4)

    print("\n" + "=" * 60)
    print("ANALYSIS")
    print("=" * 60)
    print("Compare the 'context_size' values above.")
    print("If they increased from first run, token tracking continues.")
    print("If they reset to ~same as turn 1, tracking resets on resume.")


async def main():
    if len(sys.argv) > 1:
        session_id = sys.argv[1]
        await resume_run(session_id)
    else:
        await first_run()


if __name__ == "__main__":
    asyncio.run(main())
