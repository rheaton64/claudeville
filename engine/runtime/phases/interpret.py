"""
InterpretPhase - runs the Haiku interpreter on agent narratives.

This phase:
1. Takes narratives from AgentTurnPhase
2. Runs NarrativeInterpreter on each
3. Updates turn_results with observation data
4. Produces effects from observations (movement, mood, sleep, etc.)
"""

import asyncio
import logging

from engine.domain import (
    AgentName,
    LocationId,
    Effect,
    MoveAgentEffect,
    UpdateMoodEffect,
    AgentSleepEffect,
    RecordActionEffect,
    AddConversationTurnEffect,
    SetNextSpeakerEffect,
    LeaveConversationEffect,
    RecordInterpreterTokenUsageEffect,
)
from engine.runtime.context import TickContext
from engine.runtime.pipeline import BasePhase
from engine.runtime.interpreter import NarrativeInterpreter, AgentTurnResult, InterpreterTokenUsage

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.adapters import VillageTracer


logger = logging.getLogger(__name__)


class InterpretPhase(BasePhase):
    """
    Interpret agent narratives using Claude Haiku.

    The interpreter extracts observations from narratives:
    - Movement (where they went)
    - Mood (emotional state)
    - Actions (what they did)
    - Sleep/rest intent
    - Group conversation flow suggestions

    These observations are stored in turn_results and converted to effects.
    """

    def __init__(self) -> None:
        super().__init__()
        self._tracer: "VillageTracer | None" = None

    def set_tracer(self, tracer: "VillageTracer") -> None:
        """Set the tracer for emitting interpret_complete events."""
        self._tracer = tracer

    async def _execute(self, ctx: TickContext) -> TickContext:
        """Run interpreter on all turn narratives."""
        if not ctx.turn_results:
            return ctx

        # Run interpretation in parallel
        tasks = []
        for agent_name, turn_result in ctx.turn_results.items():
            agent = ctx.agents.get(agent_name)
            if agent is None:
                continue

            task = self._interpret_turn(
                agent_name,
                turn_result.narrative,
                turn_result.narrative_with_tools,
                ctx,
            )
            tasks.append((agent_name, task))

        # Gather results
        results = await asyncio.gather(
            *[t for _, t in tasks],
            return_exceptions=True,
        )

        # Process results
        new_ctx = ctx
        for (agent_name, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                logger.error(f"Interpretation failed for {agent_name}: {result}")
                continue

            interpreted_result, effects, token_usage = result

            # Update turn result with interpreted data
            new_ctx = new_ctx.with_turn_result(agent_name, interpreted_result)
            new_ctx = new_ctx.with_effects(effects)

            # Emit interpreter token usage effect (system overhead)
            if token_usage:
                new_ctx = new_ctx.with_effect(RecordInterpreterTokenUsageEffect(
                    input_tokens=token_usage.input_tokens,
                    output_tokens=token_usage.output_tokens,
                ))

            # Emit interpret_complete event for TUI streaming
            if self._tracer:
                self._tracer.log_interpret_complete(
                    str(agent_name), interpreted_result, ctx.tick
                )

        logger.debug(f"Interpreted {len(ctx.turn_results)} narratives")
        return new_ctx

    async def _interpret_turn(
        self,
        agent_name: AgentName,
        narrative: str,
        narrative_with_tools: str,
        ctx: TickContext,
    ) -> tuple[AgentTurnResult, list[Effect], InterpreterTokenUsage | None]:
        """
        Interpret a single turn.

        Returns:
            (interpreted_result, effects, token_usage) tuple
        """
        agent = ctx.agents[agent_name]

        # Get location info for interpreter context
        location = ctx.world.locations.get(agent.location)
        available_paths = list(location.connections) if location else []

        # Get others present
        present_agents = [
            a.name for a in ctx.agents.values()
            if a.location == agent.location
            and a.name != agent_name
            and not a.is_sleeping
        ]

        # Create interpreter
        interpreter = NarrativeInterpreter(
            current_location=agent.location,
            available_paths=available_paths,
            present_agents=present_agents,
        )

        # Run interpretation
        result, token_usage = await interpreter.interpret(narrative)

        # Log any interpreter errors (but don't fail)
        if interpreter.has_error():
            error = interpreter.get_error()
            logger.warning(
                f"Interpreter warning for {agent_name}: {error.message}"
            )

        # Convert observations to effects
        effects = self._observations_to_effects(
            agent_name, result, narrative_with_tools, ctx
        )

        return result, effects, token_usage

    def _observations_to_effects(
        self,
        agent_name: AgentName,
        result: AgentTurnResult,
        narrative_with_tools: str,
        ctx: TickContext,
    ) -> list[Effect]:
        """Convert interpreted observations to effects."""
        effects: list[Effect] = []
        agent = ctx.agents[agent_name]

        # Movement
        if result.movement:
            effects.append(MoveAgentEffect(
                agent=agent_name,
                from_location=agent.location,
                to_location=LocationId(result.movement),
            ))

        # Mood
        if result.mood_expressed and result.mood_expressed != agent.mood:
            effects.append(UpdateMoodEffect(
                agent=agent_name,
                mood=result.mood_expressed,
            ))

        # Sleep
        if result.wants_to_sleep:
            effects.append(AgentSleepEffect(agent=agent_name))

        # Actions
        for action in result.actions_described:
            effects.append(RecordActionEffect(
                agent=agent_name,
                description=action,
            ))

        # If in conversation, add the narrative as a conversation turn
        # But skip if leaving with a last_message (turn already captured there)
        has_leave_with_last_message = any(
            isinstance(e, LeaveConversationEffect)
            and e.agent == agent_name
            and e.last_message
            for e in ctx.effects
        )

        conversations = ctx.get_conversations_for_agent(agent_name)
        if conversations and not has_leave_with_last_message:
            # Use the first conversation (agents typically in one at a time)
            conv = conversations[0]
            effects.append(AddConversationTurnEffect(
                conversation_id=conv.id,
                speaker=agent_name,
                narrative=result.narrative,
                narrative_with_tools=narrative_with_tools,
            ))

            if result.suggested_next_speaker and result.suggested_next_speaker in conv.participants:
                effects.append(SetNextSpeakerEffect(
                    conversation_id=conv.id,
                    speaker=AgentName(result.suggested_next_speaker),
                ))

        return effects
