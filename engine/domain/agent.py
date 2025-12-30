from pydantic import BaseModel, ConfigDict
from .types import AgentName, LocationId
from .time import TimePeriod

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
    
