"""
ObserverAPI - Clean interface for human interactions with the village.

All methods are either:
- Queries (get_*): Read-only, safe to call any number of times
- Commands (do_*): Produce effects, may raise ObserverError on failure

This module provides a strict separation between reads and writes,
ensuring the TUI can safely query state for display without side effects.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from engine.domain import (
    AgentName,
    AgentSnapshot,
    Conversation,
    ConversationId,
    DomainEvent,
    Effect,
    Invitation,
    LocationId,
    MoveAgentEffect,
    UpdateMoodEffect,
    UpdateEnergyEffect,
    AgentSleepEffect,
    AgentWakeEffect,
    SetNextSpeakerEffect,
    WorldEventOccurred,
    WeatherChangedEvent,
    AgentActionEvent,
)
from .snapshots import (
    AgentDisplaySnapshot,
    ConversationDisplaySnapshot,
    InviteDisplaySnapshot,
    ScheduleDisplaySnapshot,
    ScheduledEventDisplay,
    TimeDisplaySnapshot,
    VillageDisplaySnapshot,
)

if TYPE_CHECKING:
    from engine.engine import VillageEngine

logger = logging.getLogger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class ObserverError(Exception):
    """Base exception for Observer API errors."""

    pass


class AgentNotFoundError(ObserverError):
    """Raised when an agent doesn't exist."""

    pass


class InvalidLocationError(ObserverError):
    """Raised when a location is invalid or unreachable."""

    pass


class ConversationError(ObserverError):
    """Raised when a conversation operation fails."""

    pass


# =============================================================================
# Observer API
# =============================================================================


class ObserverAPI:
    """
    Clean interface for Observer (human) interactions with the village.

    All methods are either:
    - Queries (get_*): Read-only, safe to call freely for display
    - Commands (do_*): Produce effects or events, raise ObserverError on failure
    """

    def __init__(self, engine: "VillageEngine"):
        self._engine = engine

    # =========================================================================
    # QUERIES (Read-Only)
    # =========================================================================

    # --- Village State ---

    def get_village_snapshot(self) -> VillageDisplaySnapshot:
        """Get complete village state for display."""
        return VillageDisplaySnapshot(
            tick=self._engine.tick,
            time=self.get_time_snapshot(),
            weather=self._engine.world.weather.value,
            agents=self.get_all_agents_snapshot(),
            conversations=self.get_conversations(),
            pending_invites=self.get_pending_invites(),
            schedule=self.get_schedule_snapshot(),
        )

    def get_time_snapshot(self) -> TimeDisplaySnapshot:
        """Get current time information."""
        return TimeDisplaySnapshot.from_domain(
            tick=self._engine.tick,
            time_snapshot=self._engine.time_snapshot,
        )

    def get_weather(self) -> str:
        """Get current weather."""
        return self._engine.world.weather.value

    # --- Agent State ---

    def get_agent_snapshot(self, name: AgentName) -> AgentDisplaySnapshot | None:
        """Get a single agent's state for display."""
        agent = self._engine.agents.get(name)
        if not agent:
            return None

        in_conversation = self._is_in_conversation(name)
        has_pending_invite = self._has_pending_invite(name)

        return AgentDisplaySnapshot.from_domain(
            agent=agent,
            in_conversation=in_conversation,
            has_pending_invite=has_pending_invite,
        )

    def get_all_agents_snapshot(self) -> dict[str, AgentDisplaySnapshot]:
        """Get all agents' states for display."""
        result = {}
        for name, agent in self._engine.agents.items():
            in_conversation = self._is_in_conversation(name)
            has_pending_invite = self._has_pending_invite(name)
            result[name] = AgentDisplaySnapshot.from_domain(
                agent=agent,
                in_conversation=in_conversation,
                has_pending_invite=has_pending_invite,
            )
        return result

    def get_agent_location(self, name: AgentName) -> LocationId | None:
        """Get where an agent currently is."""
        agent = self._engine.agents.get(name)
        return agent.location if agent else None

    def get_agents_at_location(self, location: LocationId) -> list[AgentName]:
        """Get who is at a location."""
        return [
            name for name, agent in self._engine.agents.items()
            if agent.location == location
        ]

    # --- Conversation State ---

    def get_conversations(self) -> list[ConversationDisplaySnapshot]:
        """Get all active conversations for display."""
        return [
            ConversationDisplaySnapshot.from_domain(conv)
            for conv in self._engine.conversations.values()
        ]

    def get_conversation_for_agent(
        self, name: AgentName
    ) -> ConversationDisplaySnapshot | None:
        """Get the conversation an agent is in, if any."""
        for conv in self._engine.conversations.values():
            if name in conv.participants:
                return ConversationDisplaySnapshot.from_domain(conv)
        return None

    def has_active_conversation(self) -> bool:
        """Check if any conversation is active."""
        return len(self._engine.conversations) > 0

    def get_conversation_participants(self) -> list[AgentName]:
        """Get all agents currently in any conversation."""
        participants: set[AgentName] = set()
        for conv in self._engine.conversations.values():
            participants.update(conv.participants)
        return list(participants)

    # --- Invitation State ---

    def get_pending_invites(self) -> list[InviteDisplaySnapshot]:
        """Get all pending invitations for display."""
        return [
            InviteDisplaySnapshot.from_domain(invite)
            for invite in self._engine.pending_invites.values()
        ]

    def get_invites_for_agent(self, name: AgentName) -> list[InviteDisplaySnapshot]:
        """Get pending invitations for a specific agent."""
        invite = self._engine.pending_invites.get(name)
        if invite:
            return [InviteDisplaySnapshot.from_domain(invite)]
        return []

    # --- Scheduling State ---

    def get_schedule_snapshot(self) -> ScheduleDisplaySnapshot:
        """Get current scheduling state for display."""
        scheduler = self._engine.scheduler

        # Convert pending events
        pending_events = tuple(
            ScheduledEventDisplay.from_domain(e)
            for e in scheduler._queue[:10]  # Show first 10
        )

        return ScheduleDisplaySnapshot(
            pending_events=pending_events,
            forced_next=scheduler.get_forced_next(),
            skip_counts=dict(scheduler._skip_counts),
            turn_counts=dict(scheduler._turn_counts),
        )

    # --- Events ---

    def get_recent_events(self, since_tick: int = 0) -> list[DomainEvent]:
        """Get domain events since a given tick."""
        return self._engine.event_store.get_events_since(since_tick)

    # =========================================================================
    # COMMANDS (State-Mutating)
    # =========================================================================

    # --- World Events ---

    def do_trigger_event(self, description: str) -> WorldEventOccurred:
        """
        Trigger a world event that all agents will perceive.

        Args:
            description: What happens in the world

        Returns:
            The created event
        """
        logger.info(f"OBSERVER_CMD | trigger_event | desc={description[:50]}...")

        event = WorldEventOccurred(
            tick=self._engine.tick,
            timestamp=self._engine.time_snapshot.timestamp,
            description=description,
        )
        self._engine.commit_event(event)
        return event

    def do_set_weather(self, weather: str) -> WeatherChangedEvent:
        """
        Change the weather.

        Args:
            weather: New weather value (sunny, cloudy, rainy, etc.)

        Returns:
            Event describing the change
        """
        old_weather = self._engine.world.weather.value
        logger.info(f"OBSERVER_CMD | set_weather | {old_weather} -> {weather}")

        event = WeatherChangedEvent(
            tick=self._engine.tick,
            timestamp=self._engine.time_snapshot.timestamp,
            old_weather=old_weather,
            new_weather=weather,
        )
        self._engine.commit_event(event)
        return event

    def do_send_dream(self, agent_name: AgentName, content: str) -> WorldEventOccurred:
        """
        Send a dream/inspiration to an agent.

        Args:
            agent_name: Who receives the dream
            content: The dream content

        Returns:
            Event for the dream

        Raises:
            AgentNotFoundError: If agent doesn't exist
        """
        if agent_name not in self._engine.agents:
            raise AgentNotFoundError(f"Unknown agent: {agent_name}")

        logger.info(f"OBSERVER_CMD | send_dream | to={agent_name} | len={len(content)}")

        # Write to agent's dreams directory
        self._engine.write_to_agent_dreams(agent_name, content)

        event = WorldEventOccurred(
            tick=self._engine.tick,
            timestamp=self._engine.time_snapshot.timestamp,
            description=f"A dream drifts to {agent_name}...",
            agents_involved=(agent_name,),
        )
        self._engine.commit_event(event)
        return event

    # --- Scheduling Control ---

    def do_force_turn(self, agent_name: AgentName) -> None:
        """
        Force an agent to act on the next tick.

        Args:
            agent_name: Who should act next

        Raises:
            AgentNotFoundError: If agent doesn't exist
        """
        if agent_name not in self._engine.agents:
            raise AgentNotFoundError(f"Unknown agent: {agent_name}")

        logger.info(f"OBSERVER_CMD | force_turn | agent={agent_name}")
        self._engine.scheduler.force_next_turn(agent_name)

    def do_skip_turns(self, agent_name: AgentName, count: int) -> None:
        """
        Skip an agent for N turns.

        Args:
            agent_name: Who to skip
            count: Number of turns to skip

        Raises:
            AgentNotFoundError: If agent doesn't exist
        """
        if agent_name not in self._engine.agents:
            raise AgentNotFoundError(f"Unknown agent: {agent_name}")

        logger.info(f"OBSERVER_CMD | skip_turns | agent={agent_name} | count={count}")
        self._engine.scheduler.skip_turns(agent_name, count)

    def do_clear_all_modifiers(self) -> None:
        """Clear all scheduling modifiers."""
        logger.info("OBSERVER_CMD | clear_all_modifiers")
        self._engine.scheduler.clear_forced_next()
        self._engine.scheduler._skip_counts.clear()

    # --- Agent Manipulation ---

    def do_move_agent(self, agent_name: AgentName, destination: LocationId) -> Effect:
        """
        Manually move an agent to a location.

        Args:
            agent_name: Who to move
            destination: Where to move them

        Returns:
            MoveAgentEffect to be applied

        Raises:
            AgentNotFoundError: If agent doesn't exist
            InvalidLocationError: If destination is invalid
        """
        agent = self._engine.agents.get(agent_name)
        if not agent:
            raise AgentNotFoundError(f"Unknown agent: {agent_name}")

        # Validate destination
        if destination not in self._engine.world.locations:
            raise InvalidLocationError(f"Invalid location: {destination}")

        logger.info(
            f"OBSERVER_CMD | move_agent | agent={agent_name} | "
            f"{agent.location} -> {destination}"
        )

        effect = MoveAgentEffect(
            agent=agent_name,
            from_location=agent.location,
            to_location=destination,
        )
        self._engine.apply_effect(effect)
        return effect

    def do_set_mood(self, agent_name: AgentName, mood: str) -> Effect:
        """
        Manually set an agent's mood.

        Args:
            agent_name: Whose mood to set
            mood: New mood value

        Returns:
            UpdateMoodEffect to be applied

        Raises:
            AgentNotFoundError: If agent doesn't exist
        """
        agent = self._engine.agents.get(agent_name)
        if not agent:
            raise AgentNotFoundError(f"Unknown agent: {agent_name}")

        logger.info(f"OBSERVER_CMD | set_mood | agent={agent_name} | mood={mood}")

        effect = UpdateMoodEffect(agent=agent_name, mood=mood)
        self._engine.apply_effect(effect)
        return effect

    def do_set_sleeping(self, agent_name: AgentName, sleeping: bool) -> Effect:
        """
        Manually put agent to sleep or wake them.

        Args:
            agent_name: Who to sleep/wake
            sleeping: True to put to sleep, False to wake

        Returns:
            AgentSleepEffect or AgentWakeEffect

        Raises:
            AgentNotFoundError: If agent doesn't exist
        """
        agent = self._engine.agents.get(agent_name)
        if not agent:
            raise AgentNotFoundError(f"Unknown agent: {agent_name}")

        if agent.is_sleeping == sleeping:
            return None  # No change needed

        logger.info(
            f"OBSERVER_CMD | set_sleeping | agent={agent_name} | sleeping={sleeping}"
        )

        if sleeping:
            effect = AgentSleepEffect(agent=agent_name)
        else:
            effect = AgentWakeEffect(agent=agent_name, reason="observer_intervention")

        self._engine.apply_effect(effect)
        return effect

    def do_boost_energy(self, agent_name: AgentName, amount: int = 20) -> Effect:
        """
        Give an agent an energy boost.

        Args:
            agent_name: Who gets the boost
            amount: Energy to add (default 20)

        Returns:
            UpdateEnergyEffect

        Raises:
            AgentNotFoundError: If agent doesn't exist
        """
        agent = self._engine.agents.get(agent_name)
        if not agent:
            raise AgentNotFoundError(f"Unknown agent: {agent_name}")

        logger.info(
            f"OBSERVER_CMD | boost_energy | agent={agent_name} | amount={amount}"
        )

        new_energy = min(100, agent.energy + amount)
        effect = UpdateEnergyEffect(agent=agent_name, energy=new_energy)
        self._engine.apply_effect(effect)
        return effect

    def do_record_action(self, agent_name: AgentName, description: str) -> DomainEvent:
        """
        Manually record an action performed by an agent.

        Args:
            agent_name: Who performed the action
            description: What they did

        Returns:
            AgentActionEvent

        Raises:
            AgentNotFoundError: If agent doesn't exist
        """
        agent = self._engine.agents.get(agent_name)
        if not agent:
            raise AgentNotFoundError(f"Unknown agent: {agent_name}")

        logger.info(
            f"OBSERVER_CMD | record_action | agent={agent_name} | desc={description[:50]}"
        )

        event = AgentActionEvent(
            tick=self._engine.tick,
            timestamp=self._engine.time_snapshot.timestamp,
            agent=agent_name,
            location=agent.location,
            description=description,
        )
        self._engine.commit_event(event)
        return event

    # --- Conversation Control ---

    def do_end_conversation(
        self, conversation_id: ConversationId | None = None
    ) -> DomainEvent | None:
        """
        Force end a conversation.

        Args:
            conversation_id: Specific conversation to end, or None for first active

        Returns:
            ConversationEndedEvent, or None if no conversation

        Raises:
            ConversationError: If specified conversation not found
        """
        if conversation_id:
            if conversation_id not in self._engine.conversations:
                raise ConversationError(f"Conversation not found: {conversation_id}")
            conv_id = conversation_id
        else:
            if not self._engine.conversations:
                return None
            conv_id = next(iter(self._engine.conversations.keys()))

        logger.info(f"OBSERVER_CMD | end_conversation | id={conv_id}")
        return self._engine.end_conversation(conv_id, reason="observer_ended")

    def do_set_next_speaker(
        self, agent_name: AgentName, next_speaker: AgentName
    ) -> Effect | None:
        """
        Set the next speaker for a conversation that an agent is in.

        This is used for manual observation when the interpreter missed
        a next-speaker suggestion in the narrative.

        Args:
            agent_name: The agent who "suggested" the next speaker (must be in a conversation)
            next_speaker: Who should speak next

        Returns:
            SetNextSpeakerEffect, or None if agent is not in a conversation

        Raises:
            AgentNotFoundError: If agent doesn't exist
            ConversationError: If next_speaker is not in the conversation
        """
        if agent_name not in self._engine.agents:
            raise AgentNotFoundError(f"Unknown agent: {agent_name}")

        if next_speaker not in self._engine.agents:
            raise AgentNotFoundError(f"Unknown next speaker: {next_speaker}")

        # Find the conversation that agent_name is in
        conv_id = None
        conv = None
        for cid, c in self._engine.conversations.items():
            if agent_name in c.participants:
                conv_id = cid
                conv = c
                break

        if not conv_id or not conv:
            logger.warning(
                f"OBSERVER_CMD | set_next_speaker | agent={agent_name} not in conversation"
            )
            return None

        # Validate next_speaker is in the conversation
        if next_speaker not in conv.participants:
            raise ConversationError(
                f"{next_speaker} is not in the conversation with {agent_name}"
            )

        logger.info(
            f"OBSERVER_CMD | set_next_speaker | conv={conv_id} | next={next_speaker}"
        )

        effect = SetNextSpeakerEffect(
            conversation_id=conv_id,
            speaker=next_speaker,
        )
        self._engine.apply_effect(effect)
        return effect

    # --- Compaction Control ---

    def get_agent_compaction_state(self, agent_name: AgentName) -> dict | None:
        """
        Get compaction state for an agent.

        Args:
            agent_name: Which agent to check

        Returns:
            Dict with {tokens, threshold, percent, is_compacting}, or None if no service
        """
        service = self._engine.compaction_service
        if not service:
            return None

        from engine.services import CRITICAL_THRESHOLD

        tokens = service.get_token_count(agent_name)
        threshold = CRITICAL_THRESHOLD
        percent = int((tokens / threshold) * 100) if threshold > 0 else 0
        is_compacting = agent_name in service._compacting

        return {
            "tokens": tokens,
            "threshold": threshold,
            "percent": percent,
            "is_compacting": is_compacting,
        }

    def get_all_agents_compaction_state(self) -> dict[str, dict]:
        """
        Get compaction state for all agents.

        Returns:
            Dict mapping agent names to compaction state dicts
        """
        result = {}
        for name in self._engine.agents:
            state = self.get_agent_compaction_state(name)
            if state:
                result[name] = state
        return result

    async def do_force_compact(self, agent_name: AgentName) -> dict | None:
        """
        Force compaction for an agent (manual trigger).

        Args:
            agent_name: Which agent to compact

        Returns:
            Dict with {pre_tokens, post_tokens, saved}, or None if no service

        Raises:
            AgentNotFoundError: If agent doesn't exist
        """
        if agent_name not in self._engine.agents:
            raise AgentNotFoundError(f"Unknown agent: {agent_name}")

        service = self._engine.compaction_service
        if not service:
            logger.warning(f"No compaction service available for force_compact")
            return None

        logger.info(f"OBSERVER_CMD | force_compact | agent={agent_name}")

        pre_tokens = service.get_token_count(agent_name)
        post_tokens = await service.execute_compact(agent_name, critical=False)

        return {
            "pre_tokens": pre_tokens,
            "post_tokens": post_tokens,
            "saved": pre_tokens - post_tokens,
        }

    # --- Token Usage Queries ---

    def get_agent_token_usage(self, agent_name: AgentName) -> dict | None:
        """
        Get cumulative token usage for an agent.

        Args:
            agent_name: Which agent to query

        Returns:
            Dict with token usage breakdown, or None if agent not found.
            Includes session tokens (reset on compaction) and all-time totals.
        """
        agent = self._engine.agents.get(agent_name)
        if not agent:
            return None

        u = agent.token_usage
        return {
            "session_tokens": u.session_input_tokens + u.session_output_tokens,
            "total_tokens": u.total_input_tokens + u.total_output_tokens,
            "turn_count": u.turn_count,
            # Breakdown
            "session_input": u.session_input_tokens,
            "session_output": u.session_output_tokens,
            "total_input": u.total_input_tokens,
            "total_output": u.total_output_tokens,
            "cache_creation": u.cache_creation_input_tokens,
            "cache_read": u.cache_read_input_tokens,
        }

    def get_all_agent_token_usage(self) -> dict[str, dict]:
        """
        Get token usage for all agents.

        Returns:
            Dict mapping agent names to token usage dicts
        """
        result = {}
        for name in self._engine.agents:
            usage = self.get_agent_token_usage(name)
            if usage:
                result[str(name)] = usage
        return result

    def get_interpreter_usage(self) -> dict:
        """
        Get interpreter (Haiku) token usage - system overhead.

        Returns:
            Dict with total input/output tokens and call count
        """
        u = self._engine.world.interpreter_usage
        return {
            "total_tokens": u.total_input_tokens + u.total_output_tokens,
            "total_input": u.total_input_tokens,
            "total_output": u.total_output_tokens,
            "call_count": u.call_count,
        }

    def get_total_token_usage(self) -> dict:
        """
        Get combined token usage across all agents and interpreter.

        Returns:
            Dict with village-wide token totals
        """
        total_input = 0
        total_output = 0
        total_cache_creation = 0
        total_cache_read = 0
        total_turn_count = 0

        for agent in self._engine.agents.values():
            u = agent.token_usage
            total_input += u.total_input_tokens
            total_output += u.total_output_tokens
            total_cache_creation += u.cache_creation_input_tokens
            total_cache_read += u.cache_read_input_tokens
            total_turn_count += u.turn_count

        # Add interpreter usage
        interp = self._engine.world.interpreter_usage
        interpreter_total = interp.total_input_tokens + interp.total_output_tokens

        return {
            "agent_input_tokens": total_input,
            "agent_output_tokens": total_output,
            "agent_total_tokens": total_input + total_output,
            "agent_turn_count": total_turn_count,
            "cache_creation_tokens": total_cache_creation,
            "cache_read_tokens": total_cache_read,
            "interpreter_total_tokens": interpreter_total,
            "interpreter_call_count": interp.call_count,
            "grand_total_tokens": total_input + total_output + interpreter_total,
        }

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _is_in_conversation(self, agent_name: AgentName) -> bool:
        """Check if agent is in any conversation."""
        for conv in self._engine.conversations.values():
            if agent_name in conv.participants:
                return True
        return False

    def _has_pending_invite(self, agent_name: AgentName) -> bool:
        """Check if agent has a pending invitation."""
        return agent_name in self._engine.pending_invites
