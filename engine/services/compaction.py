"""
CompactionService - Handles context compaction for agent SDK sessions.

Compaction is triggered when an agent's context exceeds token thresholds:
- 150K tokens (critical): Always compact, context is in danger of overflow
- 100K tokens (pre-sleep): Only compact if agent is going to sleep

The service sends a `/compact` user message to the SDK session, which
triggers server-side context summarization.
"""

import asyncio
import logging
from typing import TYPE_CHECKING

from engine.domain import AgentName

if TYPE_CHECKING:
    from engine.adapters.claude_provider import ClaudeProvider
    from engine.adapters.tracer import VillageTracer

logger = logging.getLogger(__name__)

# Thresholds (in tokens)
CRITICAL_THRESHOLD = 150_000  # Must compact - critical levels
PRE_SLEEP_THRESHOLD = 100_000  # Opportunistic compaction before sleep


class CompactionService:
    """
    Executes compaction via SDK /compact command.

    This service is called by ApplyEffectsPhase when handling ShouldCompactEffect.
    It pushes the /compact message to the agent's input stream and waits for
    the ResultMessage to confirm completion.
    """

    def __init__(
        self,
        provider: "ClaudeProvider",
        tracer: "VillageTracer | None" = None,
    ):
        """
        Initialize the compaction service.

        Args:
            provider: Claude provider with persistent clients
            tracer: Optional tracer for real-time TUI updates
        """
        self._provider = provider
        self._tracer = tracer
        self._compacting: set[AgentName] = set()

    @property
    def is_compacting(self) -> bool:
        """True if any agent is currently compacting."""
        return len(self._compacting) > 0

    def get_token_count(self, agent_name: AgentName) -> int:
        """Get cumulative token count for an agent."""
        return self._provider.get_token_count(agent_name)

    async def execute_compact(self, agent_name: AgentName, critical: bool) -> int:
        """
        Execute compaction for an agent.

        Sends /compact to the agent's SDK session and waits for completion.
        The SDK handles server-side context summarization.

        Args:
            agent_name: Which agent to compact
            critical: True if critical threshold (150K), False if pre-sleep (100K)

        Returns:
            Post-compaction token count
        """
        if agent_name in self._compacting:
            logger.warning(f"Agent {agent_name} is already compacting, skipping")
            return self.get_token_count(agent_name)

        self._compacting.add(agent_name)
        pre_tokens = self.get_token_count(agent_name)

        threshold_desc = "critical" if critical else "pre-sleep"
        logger.info(
            f"COMPACTION_START | {agent_name} | {threshold_desc} | "
            f"tokens={pre_tokens}"
        )

        # Emit tracer event for TUI
        if self._tracer:
            self._tracer.log_compaction_start(
                str(agent_name), critical, pre_tokens
            )

        try:
            # Get the agent's input stream and client
            input_stream = self._provider._input_streams.get(agent_name)
            client = self._provider._clients.get(agent_name)

            if not input_stream or not client:
                logger.error(
                    f"COMPACTION_FAILED | {agent_name} | "
                    "no active input stream or client"
                )
                return pre_tokens

            # Push /compact as a user message
            await input_stream.push({
                "type": "user",
                "message": {
                    "role": "user",
                    "content": "/compact",
                }
            })

            # Wait for the response (compaction happens server-side)
            # Extract the post-compaction token count from ResultMessage
            from claude_agent_sdk import ResultMessage
            post_tokens = pre_tokens  # Default to pre-tokens if extraction fails
            async for message in client.receive_response():
                if isinstance(message, ResultMessage):
                    # Extract token count from the compaction ResultMessage
                    usage = getattr(message, 'usage', None)
                    if usage:
                        input_tokens = usage.get('input_tokens', 0)
                        output_tokens = usage.get('output_tokens', 0)
                        post_tokens = input_tokens + output_tokens
                    break

            # Reset provider's session tracking after compaction
            # This ensures delta computation works correctly for subsequent turns
            self._provider.reset_session_after_compaction(agent_name, post_tokens)

            logger.info(
                f"COMPACTION_COMPLETE | {agent_name} | "
                f"tokens: {pre_tokens} -> {post_tokens} | "
                f"saved: {pre_tokens - post_tokens}"
            )

            # Emit tracer event for TUI
            if self._tracer:
                self._tracer.log_compaction_end(
                    str(agent_name), pre_tokens, post_tokens
                )

            return post_tokens

        except Exception as e:
            logger.error(
                f"COMPACTION_ERROR | {agent_name} | {e}",
                exc_info=True
            )
            return pre_tokens

        finally:
            self._compacting.discard(agent_name)
