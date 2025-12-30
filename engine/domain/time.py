from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict, computed_field

class TimePeriod(Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NIGHT = "night"

class TimeSnapshot(BaseModel):
    """Immutable representation of a moment in time."""
    model_config = ConfigDict(frozen=True)

    world_time: datetime
    tick: int
    start_date: datetime

    @computed_field
    @property
    def period(self) -> TimePeriod:
        """Get the current time period."""
        hour = self.world_time.hour
        if 6 <= hour < 12:
            return TimePeriod.MORNING
        elif 12 <= hour < 18:
            return TimePeriod.AFTERNOON
        elif 18 <= hour < 22:
            return TimePeriod.EVENING
        else:
            return TimePeriod.NIGHT

    @computed_field
    @property
    def day_number(self) -> int:
        """Get the current day number relative to the start date."""
        days_elapsed = (self.world_time.date() - self.start_date.date()).days
        return days_elapsed + 1

    @computed_field
    @property
    def timestamp(self) -> datetime:
        """Alias for world_time used by display/observer code."""
        return self.world_time
