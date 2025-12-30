"""
AgentTurnResult - structured result of narrative interpretation.

This contains OBSERVATIONS extracted from the narrative, not conversation
actions (those are handled by agent tool calls in the new architecture).
"""

from pydantic import BaseModel, ConfigDict, Field


class AgentTurnResult(BaseModel):
    """
    Result of interpreting an agent's turn narrative.

    The interpreter extracts observations about what happened in the narrative.
    Conversation lifecycle actions (invite, accept, join, leave) are NOT here -
    they come from agent tool calls.
    """

    model_config = ConfigDict(frozen=True)

    # The full narrative response from the agent
    narrative: str

    # --- Movement ---
    # Where they moved (solo movement)
    movement: str | None = None
    # First words of arrival narrative (to show others at destination)
    movement_narrative_start: str | None = None
    # Destination for group move proposal (wants to go together)
    proposes_moving_together: str | None = None

    # --- State observations ---
    # Emotional state observed
    mood_expressed: str | None = None
    # Agent is winding down / settling in
    wants_to_rest: bool = False
    # Agent is going to sleep
    wants_to_sleep: bool = False

    # --- Actions ---
    # Activities performed (can be multiple)
    actions_described: tuple[str, ...] = Field(default_factory=tuple)

    # --- Group conversation flow ---
    # Who should speak next (interpreter suggestion for 3+ participant convos)
    suggested_next_speaker: str | None = None

    def get_arrival_narrative(self) -> str:
        """
        Get the portion of narrative that happens at the destination.

        If movement_narrative_start is set, returns narrative from that point.
        Otherwise returns the full narrative.
        """
        if self.movement_narrative_start:
            idx = self.narrative.find(self.movement_narrative_start)
            if idx >= 0:
                return self.narrative[idx:]
        return self.narrative


class MutableTurnResult:
    """
    Mutable version of AgentTurnResult for building during interpretation.

    The interpreter populates this, then we convert to frozen AgentTurnResult.
    """

    def __init__(self, narrative: str):
        self.narrative = narrative
        self.movement: str | None = None
        self.movement_narrative_start: str | None = None
        self.proposes_moving_together: str | None = None
        self.mood_expressed: str | None = None
        self.wants_to_rest: bool = False
        self.wants_to_sleep: bool = False
        self.actions_described: list[str] = []
        self.suggested_next_speaker: str | None = None

    def to_result(self) -> AgentTurnResult:
        """Convert to frozen AgentTurnResult."""
        return AgentTurnResult(
            narrative=self.narrative,
            movement=self.movement,
            movement_narrative_start=self.movement_narrative_start,
            proposes_moving_together=self.proposes_moving_together,
            mood_expressed=self.mood_expressed,
            wants_to_rest=self.wants_to_rest,
            wants_to_sleep=self.wants_to_sleep,
            actions_described=tuple(self.actions_described),
            suggested_next_speaker=self.suggested_next_speaker,
        )
