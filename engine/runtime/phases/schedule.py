"""
SchedulePhase - determines which agents act this tick.

This phase processes scheduled events and determines:
1. Which agents should take turns
2. For conversation turns, who is the next speaker
3. Respects observer modifiers (forced next, skip counts)
"""

import logging
import random

from engine.domain import AgentName, ConversationId, LocationId
from engine.services import Scheduler
from engine.runtime.context import TickContext
from engine.runtime.pipeline import BasePhase


logger = logging.getLogger(__name__)


class SchedulePhase(BasePhase):
    """
    Determine which agents act this tick.

    Processes scheduled events to determine:
    - Solo agent turns
    - Conversation turns (picks speaker)
    - Invite responses

    Also applies observer modifiers:
    - Forced next turn
    - Skip counts
    """

    def __init__(self, scheduler: Scheduler):
        """
        Initialize the phase.

        Args:
            scheduler: The scheduler service for modifier checks
        """
        self._scheduler = scheduler

    async def _execute(self, ctx: TickContext) -> TickContext:
        """Determine which agents should act this tick."""
        agents_to_act: set[AgentName] = set()
        conversation_speakers: dict[ConversationId, AgentName] = {}

        for event in ctx.scheduled_events:
            if event.event_type == "agent_turn":
                agent_name = AgentName(event.target_id)
                agent = ctx.agents.get(agent_name)

                # Skip if agent doesn't exist or is sleeping
                if agent is None or agent.is_sleeping:
                    continue

                # Check skip count
                if self._scheduler.get_skip_count(agent_name) > 0:
                    self._scheduler.decrement_skip(agent_name)
                    logger.debug(f"Skipping turn for {agent_name}")
                    continue

                agents_to_act.add(agent_name)

            elif event.event_type == "conversation_turn":
                conv_id = ConversationId(event.target_id)
                conv = ctx.conversations.get(conv_id)

                if conv is None:
                    continue

                # Determine next speaker
                speaker = self._get_conversation_speaker(conv_id, ctx)
                if speaker:
                    agents_to_act.add(speaker)
                    conversation_speakers[conv_id] = speaker

            elif event.event_type == "invite_response":
                agent_name = AgentName(event.target_id)
                agent = ctx.agents.get(agent_name)

                # Invite response turns happen even if agent would normally skip
                if agent is not None and not agent.is_sleeping:
                    agents_to_act.add(agent_name)

        # Apply forced next turn (observer override)
        forced = self._scheduler.get_forced_next()
        if forced and forced in ctx.agents:
            agent = ctx.agents[forced]
            if not agent.is_sleeping:
                agents_to_act.add(forced)
                logger.info(f"Forcing turn for {forced}")

        # Filter to one agent per location (random-not-last selection)
        agents_to_act = self._filter_one_per_location(agents_to_act, ctx, forced)

        logger.debug(
            f"Scheduled {len(agents_to_act)} agents to act | "
            f"conversation_speakers={len(conversation_speakers)}"
        )

        return ctx.with_agents_to_act(frozenset(agents_to_act))

    def _get_conversation_speaker(
        self,
        conv_id: ConversationId,
        ctx: TickContext,
    ) -> AgentName | None:
        """
        Determine who should speak next in a conversation.

        Priority:
        1. next_speaker field on conversation (set by interpreter)
        2. Random participant (excluding last speaker)
        """
        conv = ctx.conversations.get(conv_id)
        if conv is None or not conv.participants:
            return None

        # Check for explicitly set next speaker
        if conv.next_speaker and conv.next_speaker in conv.participants:
            agent = ctx.agents.get(conv.next_speaker)
            if agent and not agent.is_sleeping:
                return conv.next_speaker

        # Determine last speaker from history
        last_speaker: AgentName | None = None
        if conv.history:
            last_speaker = conv.history[-1].speaker

        # Pick randomly, excluding last speaker and sleeping agents
        candidates = [
            p for p in conv.participants
            if p != last_speaker
            and (agent := ctx.agents.get(p)) is not None
            and not agent.is_sleeping
        ]

        if not candidates:
            # Fall back to anyone except last speaker
            candidates = [p for p in conv.participants if p != last_speaker]

        if not candidates:
            # Everyone is the same person or all sleeping
            candidates = list(conv.participants)

        return random.choice(candidates) if candidates else None

    def _filter_one_per_location(
        self,
        agents_to_act: set[AgentName],
        ctx: TickContext,
        forced: AgentName | None,
    ) -> set[AgentName]:
        """
        Filter agents to one per location using random-not-last selection.

        When multiple agents at the same location would act, select only one.
        Prioritizes forced agents, then uses random selection excluding the
        last speaker at that location.
        """
        if len(agents_to_act) <= 1:
            return agents_to_act

        # Group candidates by location
        location_candidates: dict[LocationId, list[AgentName]] = {}
        for agent_name in agents_to_act:
            agent = ctx.agents.get(agent_name)
            if agent:
                loc = agent.location
                if loc not in location_candidates:
                    location_candidates[loc] = []
                location_candidates[loc].append(agent_name)

        # Filter to one per location
        final_agents: set[AgentName] = set()
        for location, candidates in location_candidates.items():
            if len(candidates) == 1:
                final_agents.add(candidates[0])
            else:
                # If forced agent is at this location, always select them
                if forced and forced in candidates:
                    final_agents.add(forced)
                    logger.debug(f"Forced agent {forced} selected at {location}")
                    continue

                # Random selection excluding last speaker at this location
                last_speaker = self._scheduler.get_last_location_speaker(location)
                choices = [c for c in candidates if c != last_speaker]
                if not choices:
                    choices = candidates  # Fall back if all excluded
                selected = random.choice(choices)
                final_agents.add(selected)
                logger.debug(
                    f"Selected {selected} at {location} "
                    f"(candidates={candidates}, last={last_speaker})"
                )

        return final_agents
