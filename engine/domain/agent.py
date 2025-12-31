from pydantic import BaseModel, ConfigDict, Field
from .types import AgentName, LocationId
from .time import TimePeriod


class TokenUsage(BaseModel):
    """Cumulative token usage for an agent.

    Tracks context window size (for compaction threshold decisions) and
    all-time totals (for billing/stats, never reset).
    """

    model_config = ConfigDict(frozen=True)

    # Context window size - the current size of the agent's context
    # Set to cache_read_input_tokens + input_tokens from SDK each turn
    # Used for compaction threshold decisions (100K/150K)
    session_tokens: int = 0

    # All-time cumulative tokens (never reset)
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    # Cache tokens (all-time only)
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    # Turn counter (for averages)
    turn_count: int = 0


class AgentLLMModel(BaseModel):
    """The model of an agent's LLM."""
    model_config = ConfigDict(frozen=True)

    id: str
    display_name: str
    provider: str

class AgentSnapshot(BaseModel):
    """Immutable representation of an agent's state at a moment in time."""
    model_config = ConfigDict(frozen=True)

    # Identity
    name: AgentName
    model: AgentLLMModel
    personality: str
    job: str
    interests: tuple[str, ...]
    note_to_self: str

    # Dynamic
    location: LocationId
    mood: str
    energy: int
    goals: tuple[str, ...]
    relationships: dict[AgentName, str]

    # Sleep
    is_sleeping: bool = False
    sleep_started_tick: int | None = None
    sleep_started_time_period: TimePeriod | None = None

    # Session
    session_id: str | None = None

    # Turn tracking
    last_active_tick: int = 0

    # Token usage tracking
    token_usage: TokenUsage = Field(default_factory=TokenUsage)

