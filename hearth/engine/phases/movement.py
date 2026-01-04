"""Movement phase for Hearth engine.

Advances journeys and checks for interrupts (encountering other agents).
"""

from __future__ import annotations

from datetime import datetime

from core.types import AgentName
from core.constants import HEARTH_TZ, NIGHT_VISION_MODIFIER
from core.events import JourneyInterruptedEvent, JourneyCompletedEvent, DomainEvent
from ..context import TickContext
from services.agent_service import AgentService


class MovementPhase:
    """Advance journeys, check for interrupts.

    For each journeying agent:
    1. Check if another agent is within vision range (interrupt journey)
    2. If not interrupted, advance one step along the path
    3. If arrived at destination, complete the journey
    """

    def __init__(self, agent_service: AgentService, vision_radius: int):
        """Initialize MovementPhase.

        Args:
            agent_service: AgentService for journey management
            vision_radius: Base vision radius (from PerceptionBuilder via Scheduler)
        """
        self._agent_service = agent_service
        self._vision_radius = vision_radius
        self._night_vision_radius = max(1, int(vision_radius * NIGHT_VISION_MODIFIER))

    def _get_vision_radius(self, time_of_day: str) -> int:
        """Get effective vision radius based on time of day.

        Args:
            time_of_day: Current time period

        Returns:
            Vision radius (reduced at night)
        """
        return self._night_vision_radius if time_of_day == "night" else self._vision_radius

    async def execute(self, ctx: TickContext) -> TickContext:
        """Execute movement phase.

        Processes all journeying agents, checking for interrupts and
        advancing their journeys.

        Args:
            ctx: Current tick context

        Returns:
            Updated context with journey events appended
        """
        events: list[DomainEvent] = []
        updated_agents = dict(ctx.agents)
        radius = self._get_vision_radius(ctx.time_of_day)

        for name, agent in ctx.agents.items():
            if not agent.is_journeying:
                continue

            # Check for interrupt (another agent in vision)
            nearby = await self._agent_service.get_nearby_agents(agent.position, radius)
            others = [a for a in nearby if a.name != name]

            if others:
                # Interrupt journey - encountered another agent
                updated = await self._agent_service.interrupt_journey(
                    name, "encountered_agent"
                )
                updated_agents[name] = updated
                events.append(
                    JourneyInterruptedEvent(
                        tick=ctx.tick,
                        timestamp=datetime.now(HEARTH_TZ),
                        agent=name,
                        reason="encountered_agent",
                        at_position=agent.position,
                    )
                )
            else:
                # Capture destination before advancing (journey is cleared on arrival)
                destination = (
                    agent.journey.destination.position
                    if agent.journey
                    else agent.position
                )

                # Advance one step along the path
                updated, arrived = await self._agent_service.advance_journey(name)
                updated_agents[name] = updated
                if arrived:
                    # Journey complete
                    events.append(
                        JourneyCompletedEvent(
                            tick=ctx.tick,
                            timestamp=datetime.now(HEARTH_TZ),
                            agent=name,
                            destination=destination,
                        )
                    )

        return ctx.with_agents(updated_agents).append_events(events)
