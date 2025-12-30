from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from .types import AgentName, LocationId


class Weather(Enum):
    CLEAR = "clear"
    CLOUDY = "cloudy"
    RAINY = "rainy"
    STORMY = "stormy"
    FOGGY = "foggy"
    SNOWY = "snowy"

class Location(BaseModel):
    """A place in the world."""
    model_config = ConfigDict(frozen=True)

    id: LocationId
    name: str
    description: str
    features: tuple[str, ...] = Field(default_factory=tuple)
    connections: tuple[LocationId, ...] = Field(default_factory=tuple)
    
class WorldSnapshot(BaseModel):
    """Immutable representation of the world's state at a moment in time."""
    model_config = ConfigDict(frozen=True)

    tick: int
    world_time: datetime
    start_date: datetime
    weather: Weather
    locations: dict[LocationId, Location]
    agent_locations: dict[AgentName, LocationId]