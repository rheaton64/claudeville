"""Shared constants for Hearth.

Centralizes values used across multiple modules to ensure consistency.
"""

from zoneinfo import ZoneInfo

# Timezone for all timestamps
HEARTH_TZ = ZoneInfo("America/New_York")

# Vision settings
DEFAULT_VISION_RADIUS = 3  # 7x7 grid (radius 3 = 3 cells in each direction)
NIGHT_VISION_MODIFIER = 0.6  # Night vision is 60% of day vision
