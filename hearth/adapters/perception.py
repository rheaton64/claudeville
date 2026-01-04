"""Perception builder for Hearth.

Builds the perception context that agents receive at the start of their turn.
This is the "eyes" of the agent - what they see and know about their surroundings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import anthropic
from dotenv import load_dotenv

load_dotenv()

from core.terrain import (
    Weather,
    Terrain,
    TERRAIN_EMOJI,
    OBJECT_EMOJI,
    AGENT_EMOJI,
    SELF_EMOJI,
    is_passable,
)
from core.types import Position, Direction, Rect, AgentName
from core.constants import NIGHT_VISION_MODIFIER
from core.world import Cell
from core.agent import Agent, Inventory
from core.objects import Sign, PlacedItem, AnyWorldObject
from core.conversation import Invitation, ConversationContext

if TYPE_CHECKING:
    from services.world_service import WorldService
    from services.agent_service import AgentService
    from services.conversation import ConversationService
    from storage import Storage


# -----------------------------------------------------------------------------
# Direction Phrases for Immediate Surroundings
# -----------------------------------------------------------------------------

DIRECTION_PHRASES: dict[Direction, str] = {
    Direction.NORTH: "One step north",
    Direction.SOUTH: "One step south",
    Direction.EAST: "One step east",
    Direction.WEST: "One step west",
}

HERE_PHRASE = "Beneath you"


# -----------------------------------------------------------------------------
# Time of Day
# -----------------------------------------------------------------------------


def get_time_of_day(tick: int, ticks_per_day: int = 24) -> str:
    """Derive time of day from tick.

    Divides day into 4 equal periods:
    - morning: first quarter
    - afternoon: second quarter
    - evening: third quarter
    - night: fourth quarter

    Args:
        tick: Current world tick
        ticks_per_day: Ticks per full day cycle (default 24)

    Returns:
        Time period string
    """
    hour = tick % ticks_per_day
    quarter = ticks_per_day // 4

    if hour < quarter:
        return "morning"
    elif hour < quarter * 2:
        return "afternoon"
    elif hour < quarter * 3:
        return "evening"
    else:
        return "night"


# -----------------------------------------------------------------------------
# AgentPerception
# -----------------------------------------------------------------------------


@dataclass
class AgentPerception:
    """Complete perception context for an agent's turn."""

    # Grid view
    grid_view: str  # Emoji grid with walls (7x7 cells, double-res)

    # Immediate surroundings (explicit N/S/E/W + here)
    immediate_surroundings_text: str  # "One step north: grass. One step south: forest..."

    # Narrative description
    narrative: str  # Haiku-generated atmospheric prose

    # Agent state
    inventory_text: str  # "You carry: wood (3), stone (2), clay_vessel"
    journey_text: str | None  # "Traveling to X (N steps remaining)"

    # Social awareness (visible only - sense_others is an action)
    visible_agents_text: str  # "Sage is to the north. An unfamiliar figure to the west."

    # World state
    time_of_day: str  # "morning", "afternoon", "evening", "night"
    weather: Weather
    position: Position

    # Conversation context (optional)
    conversation_text: str | None = None  # Active conversation history (unseen turns)
    pending_invitation_text: str | None = None  # "Sage has invited you to talk."


# -----------------------------------------------------------------------------
# Box-Drawing Wall Characters
# -----------------------------------------------------------------------------

# Map of (north, south, east, west) wall connections to box-drawing character
# True = wall connects in that direction
_WALL_CHARS: dict[tuple[bool, bool, bool, bool], str] = {
    # Single lines
    (True, True, False, False): "│",  # Vertical
    (False, False, True, True): "─",  # Horizontal
    # Corners
    (False, True, True, False): "┌",  # Top-left
    (False, True, False, True): "┐",  # Top-right
    (True, False, True, False): "└",  # Bottom-left
    (True, False, False, True): "┘",  # Bottom-right
    # T-junctions
    (True, True, True, False): "├",  # T facing east
    (True, True, False, True): "┤",  # T facing west
    (False, True, True, True): "┬",  # T facing south
    (True, False, True, True): "┴",  # T facing north
    # Cross
    (True, True, True, True): "┼",  # Four-way
    # Edge cases (only one connection - treat as line segment)
    (True, False, False, False): "│",
    (False, True, False, False): "│",
    (False, False, True, False): "─",
    (False, False, False, True): "─",
    # No connections (shouldn't happen, but handle gracefully)
    (False, False, False, False): " ",
}

# Door characters (gaps in walls)
DOOR_HORIZONTAL = " "  # Gap for horizontal door
DOOR_VERTICAL = " "  # Gap for vertical door


def _get_wall_char(
    has_north: bool,
    has_south: bool,
    has_east: bool,
    has_west: bool,
) -> str:
    """Get appropriate box-drawing character for wall intersection.

    Args:
        has_north: Wall extends north
        has_south: Wall extends south
        has_east: Wall extends east
        has_west: Wall extends west

    Returns:
        Appropriate box-drawing character
    """
    key = (has_north, has_south, has_east, has_west)
    return _WALL_CHARS.get(key, " ")


# -----------------------------------------------------------------------------
# Haiku Narrative Prompts
# -----------------------------------------------------------------------------

PERCEPTION_SYSTEM_PROMPT = """You are describing what an agent perceives in Hearth, a peaceful grid world. Generate an atmospheric description of their surroundings.

Guidelines:
- Describe what they can see based on the feature list provided
- Add atmosphere based on time of day and weather
- Mention named places naturally if standing on one
- Keep it concise: 2-4 sentences
- Use second person ("You see...", "To the north...")
- Never break immersion or reference "game mechanics"

Weather: {weather}
Time of day: {time_of_day}"""


def _build_narrative_user_prompt(features: dict) -> str:
    """Build user prompt for Haiku narrative generation."""
    parts = []

    if features.get("standing_on"):
        parts.append(f"Standing at: {features['standing_on']}")

    if features.get("terrain"):
        parts.append(f"Terrain: {', '.join(features['terrain'])}")

    if features.get("objects"):
        parts.append(f"Objects: {', '.join(features['objects'])}")

    if features.get("agents"):
        parts.append(f"Others: {', '.join(features['agents'])}")

    if not parts:
        parts.append("Open grassland, nothing remarkable nearby.")

    return "\n".join(parts) + "\n\nDescribe this scene atmospherically."


# -----------------------------------------------------------------------------
# PerceptionBuilder
# -----------------------------------------------------------------------------


class PerceptionBuilder:
    """Builds perception context for agents.

    Assembles the grid view, narrative description, and state information
    that an agent receives at the start of their turn.
    """

    def __init__(
        self,
        world_service: "WorldService",
        agent_service: "AgentService",
        conversation_service: "ConversationService | None" = None,
        haiku_client: anthropic.AsyncAnthropic | None = None,
        haiku_model: str = "claude-haiku-4-5-20251001",
        vision_radius: int = 3,
    ):
        """Initialize PerceptionBuilder.

        Args:
            world_service: WorldService for spatial queries
            agent_service: AgentService for agent queries
            conversation_service: ConversationService for conversation context
            haiku_client: Anthropic client (lazy-initialized if None)
            haiku_model: Model to use for narrative generation
            vision_radius: How far agent can see (default 3 = 7x7 grid)
        """
        self._world_service = world_service
        self._agent_service = agent_service
        self._conversation_service = conversation_service
        self._haiku_client = haiku_client
        self._haiku_model = haiku_model
        self._vision_radius = vision_radius

    async def build(self, agent_name: AgentName, tick: int) -> AgentPerception:
        """Build complete perception for an agent.

        Args:
            agent_name: Name of the agent to build perception for
            tick: Current world tick

        Returns:
            AgentPerception with all context for the agent's turn
        """
        # 1. Get agent and world state
        agent = await self._agent_service.get_agent_or_raise(agent_name)
        world_state = await self._world_service.get_world_state()

        # 2. Derive time of day
        time_of_day = get_time_of_day(tick)

        # 3. Calculate effective vision radius (reduced at night)
        effective_radius = self._vision_radius
        if time_of_day == "night":
            effective_radius = max(1, int(self._vision_radius * NIGHT_VISION_MODIFIER))

        # 4. Get visible cells (clamped to world bounds)
        width, height = await self._world_service.get_world_dimensions()
        rect = Rect(
            agent.position.x - effective_radius,
            agent.position.y - effective_radius,
            agent.position.x + effective_radius,
            agent.position.y + effective_radius,
        ).clamp(width, height)

        cells = await self._world_service.get_cells_in_rect(rect)
        objects = await self._world_service.get_objects_in_rect(rect)

        # 5. Get agents in vision
        other_agents = await self._agent_service.get_nearby_agents(
            agent.position, radius=effective_radius
        )
        other_agents = [a for a in other_agents if a.name != agent_name]

        # Record meetings with visible agents (enables sense_others)
        for other in other_agents:
            await self._agent_service.record_meeting(agent_name, other.name)

        # 6. Build grid view
        grid_view = self._build_grid_view(agent, cells, objects, other_agents, rect)

        # 6b. Build immediate surroundings (explicit N/S/E/W + here)
        immediate_surroundings_text = self._build_immediate_surroundings(
            agent, cells, objects, other_agents, width, height
        )

        # 7. Extract features for narrative
        features = await self._extract_features(
            agent.position, cells, objects, other_agents
        )

        # 8. Generate narrative
        narrative = await self._generate_narrative(
            features, time_of_day, world_state.weather
        )

        # 9. Format state information
        inventory_text = self._format_inventory(agent.inventory)
        journey_text = self._format_journey(agent)
        visible_agents_text = self._format_visible_agents(agent, other_agents)

        # 10. Get conversation context (if service available)
        conversation_text = None
        pending_invitation_text = None
        if self._conversation_service is not None:
            # Check for pending invitation
            pending_invite = await self._conversation_service.get_pending_invitation(
                agent_name
            )
            if pending_invite is not None:
                pending_invitation_text = self._format_invitation(pending_invite)

            # Check for active conversation
            conv_context = await self._conversation_service.get_conversation_context(
                agent_name
            )
            if conv_context is not None:
                conversation_text = self._format_conversation(conv_context)

        return AgentPerception(
            grid_view=grid_view,
            immediate_surroundings_text=immediate_surroundings_text,
            narrative=narrative,
            inventory_text=inventory_text,
            journey_text=journey_text,
            visible_agents_text=visible_agents_text,
            time_of_day=time_of_day,
            weather=world_state.weather,
            position=agent.position,
            conversation_text=conversation_text,
            pending_invitation_text=pending_invitation_text,
        )

    # -------------------------------------------------------------------------
    # Grid View Generation
    # -------------------------------------------------------------------------

    def _build_grid_view(
        self,
        agent: Agent,
        cells: list[Cell],
        objects: list[AnyWorldObject],
        other_agents: list[Agent],
        visible_rect: Rect,
    ) -> str:
        """Build emoji grid view with box-drawing walls.

        Uses double resolution to show walls between cells:
        - Cell content at even coordinates
        - Wall characters at odd coordinates

        Args:
            agent: The perceiving agent
            cells: Visible cells
            objects: Visible objects
            other_agents: Visible agents
            visible_rect: The visible rectangle (clamped to world bounds)

        Returns:
            Multi-line string grid view
        """
        # Build lookups
        cell_lookup = {cell.position: cell for cell in cells}
        object_lookup: dict[Position, list[AnyWorldObject]] = {}
        for obj in objects:
            if obj.position not in object_lookup:
                object_lookup[obj.position] = []
            object_lookup[obj.position].append(obj)

        agent_lookup: dict[Position, list[Agent]] = {}
        for a in other_agents:
            if a.position not in agent_lookup:
                agent_lookup[a.position] = []
            agent_lookup[a.position].append(a)

        # Grid dimensions in double-resolution
        # Each cell becomes a 2x2 block: content + walls
        grid_width = (visible_rect.width + 1) * 2 - 1
        grid_height = (visible_rect.height + 1) * 2 - 1

        # Initialize grid with spaces
        grid: list[list[str]] = [[" " for _ in range(grid_width)] for _ in range(grid_height)]

        # Fill in cell content and walls
        for gy, world_y in enumerate(range(visible_rect.max_y, visible_rect.min_y - 1, -1)):
            for gx, world_x in enumerate(range(visible_rect.min_x, visible_rect.max_x + 1)):
                pos = Position(world_x, world_y)
                cell = cell_lookup.get(pos, Cell(position=pos))

                # Double-resolution coordinates
                dx = gx * 2
                dy = gy * 2

                # Cell content (priority: agent > object > terrain)
                symbol = self._get_cell_symbol(
                    pos, agent, cell, object_lookup.get(pos, []), agent_lookup.get(pos, [])
                )
                if dy < grid_height and dx < grid_width:
                    grid[dy][dx] = symbol

                # East wall (between this cell and the one to the east)
                if gx < visible_rect.width:
                    east_pos = Position(world_x + 1, world_y)
                    east_cell = cell_lookup.get(east_pos, Cell(position=east_pos))
                    wall_x = dx + 1
                    if wall_x < grid_width and dy < grid_height:
                        wall_char = self._get_vertical_wall(cell, east_cell, Direction.EAST)
                        if wall_char:
                            grid[dy][wall_x] = wall_char

                # South wall (between this cell and the one to the south)
                if gy < visible_rect.height:
                    south_pos = Position(world_x, world_y - 1)
                    south_cell = cell_lookup.get(south_pos, Cell(position=south_pos))
                    wall_y = dy + 1
                    if wall_y < grid_height and dx < grid_width:
                        wall_char = self._get_horizontal_wall(cell, south_cell, Direction.SOUTH)
                        if wall_char:
                            grid[wall_y][dx] = wall_char

                # Corner (intersection of walls)
                if gx < visible_rect.width and gy < visible_rect.height:
                    corner_x = dx + 1
                    corner_y = dy + 1
                    if corner_x < grid_width and corner_y < grid_height:
                        corner_char = self._get_corner_char(
                            pos, cell_lookup, visible_rect
                        )
                        if corner_char and corner_char != " ":
                            grid[corner_y][corner_x] = corner_char

        # Convert to string
        return "\n".join("".join(row) for row in grid)

    def _get_cell_symbol(
        self,
        pos: Position,
        viewer: Agent,
        cell: Cell,
        objects_here: list[AnyWorldObject],
        agents_here: list[Agent],
    ) -> str:
        """Get the symbol for a cell (priority: viewer > agents > objects > terrain).

        Args:
            pos: Position being rendered
            viewer: The perceiving agent
            cell: The cell at this position
            objects_here: Objects at this position
            agents_here: Other agents at this position

        Returns:
            Single character/emoji for the cell
        """
        # Highest priority: self
        if pos == viewer.position:
            return SELF_EMOJI

        # Second priority: other agents
        if agents_here:
            return AGENT_EMOJI

        # Third priority: objects
        if objects_here:
            obj = objects_here[0]
            if isinstance(obj, Sign):
                return OBJECT_EMOJI.get("sign", "📜")
            elif isinstance(obj, PlacedItem):
                return OBJECT_EMOJI.get("placed_item", "✨")
            return "?"

        # Lowest priority: terrain
        return TERRAIN_EMOJI.get(cell.terrain, "?")

    def _get_vertical_wall(
        self,
        west_cell: Cell,
        east_cell: Cell,
        direction: Direction,
    ) -> str | None:
        """Get vertical wall character between two horizontally adjacent cells.

        Args:
            west_cell: Cell to the west
            east_cell: Cell to the east
            direction: Direction from west_cell (should be EAST)

        Returns:
            Wall character or None
        """
        has_wall = direction in west_cell.walls or direction.opposite in east_cell.walls
        if not has_wall:
            return None

        # Check for door
        has_door = direction in west_cell.doors or direction.opposite in east_cell.doors
        if has_door:
            return DOOR_VERTICAL

        return "│"

    def _get_horizontal_wall(
        self,
        north_cell: Cell,
        south_cell: Cell,
        direction: Direction,
    ) -> str | None:
        """Get horizontal wall character between two vertically adjacent cells.

        Args:
            north_cell: Cell to the north
            south_cell: Cell to the south
            direction: Direction from north_cell (should be SOUTH)

        Returns:
            Wall character or None
        """
        has_wall = direction in north_cell.walls or direction.opposite in south_cell.walls
        if not has_wall:
            return None

        # Check for door
        has_door = direction in north_cell.doors or direction.opposite in south_cell.doors
        if has_door:
            return DOOR_HORIZONTAL

        return "─"

    def _get_corner_char(
        self,
        pos: Position,
        cell_lookup: dict[Position, Cell],
        visible_rect: Rect,
    ) -> str | None:
        """Get corner character at the intersection of four cells.

        The corner is at the southeast corner of the cell at `pos`.

        Wall Corner Diagram:
        ====================

        The corner point (*) lies at the meeting of four cells:

                    │
                    │ has_north (wall extends up from corner)
                    │
            ┌───────┼───────┐
            │  NW   │  NE   │
            │ cell  │ cell  │
        ────┼───────*───────┼────  has_east/west (wall extends horizontally)
            │  SW   │  SE   │
            │ cell  │ cell  │
            └───────┼───────┘
                    │
                    │ has_south (wall extends down from corner)
                    │

        To determine which directions have walls extending from the corner:

        - has_north: A vertical wall extends NORTH from corner (*)
          → Check: NW cell has EAST wall OR NE cell has WEST wall
          (Either side of the vertical line between NW and NE)

        - has_south: A vertical wall extends SOUTH from corner (*)
          → Check: SW cell has EAST wall OR SE cell has WEST wall
          (Either side of the vertical line between SW and SE)

        - has_east: A horizontal wall extends EAST from corner (*)
          → Check: NE cell has SOUTH wall OR SE cell has NORTH wall
          (Either side of the horizontal line between NE and SE)

        - has_west: A horizontal wall extends WEST from corner (*)
          → Check: NW cell has SOUTH wall OR SW cell has NORTH wall
          (Either side of the horizontal line between NW and SW)

        The resulting (has_north, has_south, has_east, has_west) tuple maps to
        a box-drawing character via _WALL_CHARS.

        Args:
            pos: Position of the northwest cell of the four
            cell_lookup: Lookup of all cells
            visible_rect: Visible rectangle

        Returns:
            Corner character or None
        """
        # Four cells meeting at this corner
        nw = cell_lookup.get(pos, Cell(position=pos))
        ne = cell_lookup.get(Position(pos.x + 1, pos.y), Cell(position=Position(pos.x + 1, pos.y)))
        sw = cell_lookup.get(Position(pos.x, pos.y - 1), Cell(position=Position(pos.x, pos.y - 1)))
        se = cell_lookup.get(Position(pos.x + 1, pos.y - 1), Cell(position=Position(pos.x + 1, pos.y - 1)))

        # Wall extending north: NW has east wall OR NE has west wall
        has_north = Direction.EAST in nw.walls or Direction.WEST in ne.walls
        # Wall extending south: SW has east wall OR SE has west wall
        has_south = Direction.EAST in sw.walls or Direction.WEST in se.walls
        # Wall extending east: NE has south wall OR SE has north wall
        has_east = Direction.SOUTH in ne.walls or Direction.NORTH in se.walls
        # Wall extending west: NW has south wall OR SW has north wall
        has_west = Direction.SOUTH in nw.walls or Direction.NORTH in sw.walls

        if not (has_north or has_south or has_east or has_west):
            return None

        return _get_wall_char(has_north, has_south, has_east, has_west)

    # -------------------------------------------------------------------------
    # Feature Extraction for Narrative
    # -------------------------------------------------------------------------

    async def _extract_features(
        self,
        agent_pos: Position,
        cells: list[Cell],
        objects: list[AnyWorldObject],
        other_agents: list[Agent],
    ) -> dict:
        """Extract notable features with directions for Haiku context.

        Args:
            agent_pos: Agent's position
            cells: Visible cells
            objects: Visible objects
            other_agents: Visible agents

        Returns:
            Dict with terrain, objects, agents, and standing_on keys
        """
        features: dict = {
            "terrain": [],
            "objects": [],
            "agents": [],
            "standing_on": None,
        }

        # Check for named place at agent's position
        cell_at_agent = next((c for c in cells if c.position == agent_pos), None)
        if cell_at_agent and cell_at_agent.place_name:
            features["standing_on"] = cell_at_agent.place_name

        # Group terrain by type and direction
        terrain_by_type: dict[Terrain, list[str]] = {}
        for cell in cells:
            if cell.position == agent_pos:
                continue
            if cell.terrain != Terrain.GRASS:  # Skip unremarkable grass
                direction = self._get_direction_phrase(agent_pos, cell.position)
                if cell.terrain not in terrain_by_type:
                    terrain_by_type[cell.terrain] = []
                terrain_by_type[cell.terrain].append(direction)

        for terrain, directions in terrain_by_type.items():
            if len(directions) == 1:
                features["terrain"].append(f"{terrain.value} to the {directions[0]}")
            else:
                features["terrain"].append(f"{terrain.value} in multiple directions")

        # Objects
        for obj in objects:
            direction = self._get_direction_phrase(agent_pos, obj.position)
            if isinstance(obj, Sign):
                features["objects"].append(f"a sign to the {direction}")
            elif isinstance(obj, PlacedItem):
                features["objects"].append(f"{obj.item_type} to the {direction}")

        # Other agents
        for agent in other_agents:
            direction = self._get_direction_phrase(agent_pos, agent.position)
            features["agents"].append(f"{agent.name} to the {direction}")

        return features

    def _get_direction_phrase(self, from_pos: Position, to_pos: Position) -> str:
        """Get a natural language direction phrase.

        Args:
            from_pos: Origin position
            to_pos: Target position

        Returns:
            Direction phrase like "north", "southwest", etc.
        """
        dx = to_pos.x - from_pos.x
        dy = to_pos.y - from_pos.y

        if dx == 0 and dy == 0:
            return "here"

        # Determine primary direction
        parts = []
        if dy > 0:
            parts.append("north")
        elif dy < 0:
            parts.append("south")

        if dx > 0:
            parts.append("east")
        elif dx < 0:
            parts.append("west")

        return "".join(parts) if parts else "nearby"

    # -------------------------------------------------------------------------
    # Narrative Generation
    # -------------------------------------------------------------------------

    async def _generate_narrative(
        self,
        features: dict,
        time_of_day: str,
        weather: Weather,
    ) -> str:
        """Generate atmospheric narrative via Haiku.

        Args:
            features: Extracted features dict
            time_of_day: Current time of day
            weather: Current weather

        Returns:
            Atmospheric prose description
        """
        if self._haiku_client is None:
            self._haiku_client = anthropic.AsyncAnthropic()

        system_prompt = PERCEPTION_SYSTEM_PROMPT.format(
            weather=weather.value,
            time_of_day=time_of_day,
        )
        user_prompt = _build_narrative_user_prompt(features)

        try:
            response = await self._haiku_client.messages.create(
                model=self._haiku_model,
                max_tokens=256,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            if response.content and len(response.content) > 0:
                return response.content[0].text

            return self._fallback_narrative(features, time_of_day, weather)
        except Exception:
            return self._fallback_narrative(features, time_of_day, weather)

    def _fallback_narrative(
        self,
        features: dict,
        time_of_day: str,
        weather: Weather,
    ) -> str:
        """Generate simple fallback narrative when Haiku unavailable.

        Args:
            features: Extracted features dict
            time_of_day: Current time of day
            weather: Current weather

        Returns:
            Simple narrative description
        """
        parts = []

        # Time/weather opener
        if time_of_day == "morning":
            parts.append("The morning light spreads across the land.")
        elif time_of_day == "afternoon":
            parts.append("The afternoon sun warms the world.")
        elif time_of_day == "evening":
            parts.append("Evening shadows lengthen around you.")
        else:
            parts.append("Night holds the world in quiet darkness.")

        # Standing on
        if features.get("standing_on"):
            parts.append(f"You stand at {features['standing_on']}.")

        # Simple terrain mention
        if features.get("terrain"):
            parts.append(f"You see {features['terrain'][0]}.")

        return " ".join(parts) if parts else "You are in an open area."

    # -------------------------------------------------------------------------
    # Immediate Surroundings
    # -------------------------------------------------------------------------

    def _build_immediate_surroundings(
        self,
        agent: Agent,
        cells: list[Cell],
        objects: list[AnyWorldObject],
        other_agents: list[Agent],
        world_width: int,
        world_height: int,
    ) -> str:
        """Build explicit prose describing immediate N/S/E/W + current cell.

        Args:
            agent: The perceiving agent
            cells: All visible cells
            objects: All visible objects
            other_agents: Other agents in view
            world_width: Width of the world (for edge detection)
            world_height: Height of the world (for edge detection)

        Returns:
            Natural prose describing immediate surroundings
        """
        # Build lookups
        cell_lookup = {cell.position: cell for cell in cells}
        object_lookup: dict[Position, list[AnyWorldObject]] = {}
        for obj in objects:
            if obj.position not in object_lookup:
                object_lookup[obj.position] = []
            object_lookup[obj.position].append(obj)

        agent_lookup: dict[Position, list[Agent]] = {}
        for a in other_agents:
            if a.position not in agent_lookup:
                agent_lookup[a.position] = []
            agent_lookup[a.position].append(a)

        # Get current cell
        current_cell = cell_lookup.get(agent.position, Cell(position=agent.position))

        # Build descriptions for each direction
        descriptions: list[str] = []

        for direction in [Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST]:
            adj_pos = agent.position + direction
            phrase = DIRECTION_PHRASES[direction]

            # Check if out of bounds
            if adj_pos.x < 0 or adj_pos.x >= world_width or adj_pos.y < 0 or adj_pos.y >= world_height:
                descriptions.append(f"{phrase}: the edge of the world.")
                continue

            # Check for wall blocking this direction
            wall_blocked = direction in current_cell.walls and direction not in current_cell.doors

            adj_cell = cell_lookup.get(adj_pos, Cell(position=adj_pos))
            adj_objects = object_lookup.get(adj_pos, [])
            adj_agents = agent_lookup.get(adj_pos, [])

            desc = self._describe_adjacent_cell(
                adj_cell, adj_objects, adj_agents, wall_blocked, agent
            )
            descriptions.append(f"{phrase}: {desc}")

        # Build description for current position ("Beneath you")
        here_objects = object_lookup.get(agent.position, [])
        here_desc = self._describe_here(current_cell, here_objects)
        descriptions.append(f"{HERE_PHRASE}: {here_desc}")

        return " ".join(descriptions)

    def _describe_adjacent_cell(
        self,
        cell: Cell,
        objects_at: list[AnyWorldObject],
        agents_at: list[Agent],
        wall_blocked: bool,
        viewer: Agent,
    ) -> str:
        """Build prose description of an adjacent cell.

        Args:
            cell: The cell to describe
            objects_at: Objects at this position
            agents_at: Other agents at this position
            wall_blocked: Whether a wall blocks entry
            viewer: The viewing agent (for known/unknown agent distinction)

        Returns:
            Prose fragment like "grass" or "forest with a sign, blocked by a wall"
        """
        parts: list[str] = []

        # Terrain with natural phrasing
        terrain = cell.terrain
        terrain_name = self._terrain_to_prose(terrain)

        # Check passability
        passable = is_passable(terrain)

        # Start with terrain
        parts.append(terrain_name)

        # Add impassable note for terrain
        if not passable:
            parts[-1] += "—impassable"

        # Add objects naturally
        object_phrases = self._objects_to_prose(objects_at)
        if object_phrases:
            parts.append(object_phrases)

        # Add agents
        if agents_at:
            agent_names = []
            for a in agents_at:
                if a.name in viewer.known_agents:
                    agent_names.append(str(a.name))
                else:
                    agent_names.append("someone unfamiliar")

            if len(agent_names) == 1:
                parts.append(f"where {agent_names[0]} stands")
            else:
                parts.append(f"where {' and '.join(agent_names)} stand")

        # Add wall blocked note
        if wall_blocked:
            parts.append("blocked by a wall")

        # Join parts naturally
        if len(parts) == 1:
            return parts[0] + "."
        elif len(parts) == 2:
            # "grass, where Sage stands." or "grass—impassable."
            if parts[1].startswith("where") or parts[1].startswith("blocked"):
                return f"{parts[0]}, {parts[1]}."
            else:
                return f"{parts[0]} {parts[1]}."
        else:
            # Multiple parts: terrain + objects/agents + wall
            main = parts[0]
            extras = parts[1:]
            # Join extras with commas
            return f"{main}, {', '.join(extras)}."

    def _describe_here(
        self,
        cell: Cell,
        objects_at: list[AnyWorldObject],
    ) -> str:
        """Build prose description of current position.

        Args:
            cell: The cell the agent is standing on
            objects_at: Objects at this position

        Returns:
            Prose fragment like "grass terrain" or "sand with scattered wood"
        """
        parts: list[str] = []

        # Terrain
        terrain_name = self._terrain_to_prose(cell.terrain)
        parts.append(terrain_name)

        # Named place
        if cell.place_name:
            parts[-1] = f"{cell.place_name} ({terrain_name})"

        # Objects
        object_phrases = self._objects_to_prose(objects_at)
        if object_phrases:
            parts.append(object_phrases)

        if len(parts) == 1:
            return parts[0] + "."
        else:
            return f"{parts[0]}, {parts[1]}."

    def _terrain_to_prose(self, terrain: Terrain) -> str:
        """Convert terrain type to natural prose.

        Args:
            terrain: Terrain type

        Returns:
            Natural description like "open grass" or "forest"
        """
        terrain_phrases = {
            Terrain.GRASS: "open grass",
            Terrain.WATER: "water",
            Terrain.COAST: "shallow water",
            Terrain.STONE: "stone",
            Terrain.SAND: "sand",
            Terrain.FOREST: "forest",
            Terrain.HILL: "hillside",
        }
        return terrain_phrases.get(terrain, terrain.value)

    def _objects_to_prose(self, objects: list[AnyWorldObject]) -> str:
        """Convert objects list to natural prose.

        Args:
            objects: List of objects

        Returns:
            Natural description like "with a sign" or "with scattered wood"
        """
        if not objects:
            return ""

        object_descriptions: list[str] = []

        for obj in objects:
            if isinstance(obj, Sign):
                object_descriptions.append("a sign")
            elif isinstance(obj, PlacedItem):
                if obj.quantity > 5:
                    object_descriptions.append(f"a pile of {obj.item_type}")
                elif obj.quantity > 1:
                    object_descriptions.append(f"some {obj.item_type}")
                else:
                    object_descriptions.append(f"a {obj.item_type}")

        if not object_descriptions:
            return ""

        if len(object_descriptions) == 1:
            return f"with {object_descriptions[0]}"
        elif len(object_descriptions) == 2:
            return f"with {object_descriptions[0]} and {object_descriptions[1]}"
        else:
            all_but_last = ", ".join(object_descriptions[:-1])
            return f"with {all_but_last}, and {object_descriptions[-1]}"

    # -------------------------------------------------------------------------
    # State Formatting
    # -------------------------------------------------------------------------

    def _format_inventory(self, inventory: Inventory) -> str:
        """Format inventory for agent perception.

        Args:
            inventory: Agent's inventory

        Returns:
            Human-readable inventory string
        """
        if inventory.is_empty:
            return "Your hands are empty."

        items = []

        # Stackable resources
        for stack in inventory.stacks:
            if stack.quantity > 1:
                items.append(f"{stack.item_type} ({stack.quantity})")
            else:
                items.append(stack.item_type)

        # Unique items
        for item in inventory.items:
            if item.properties:
                props = ", ".join(item.properties)
                items.append(f"a {item.item_type} ({props})")
            else:
                items.append(f"a {item.item_type}")

        return f"You carry: {', '.join(items)}."

    def _format_journey(self, agent: Agent) -> str | None:
        """Format journey state if traveling.

        Args:
            agent: Agent to format journey for

        Returns:
            Journey description or None if not traveling
        """
        if not agent.is_journeying or agent.journey is None:
            return None

        journey = agent.journey
        remaining = len(journey.path) - journey.progress - 1

        # Format destination
        if journey.destination.landmark:
            dest_str = journey.destination.landmark
        else:
            dest_str = f"({journey.destination.position.x}, {journey.destination.position.y})"

        # Describe progress without step counts
        if remaining <= 1:
            return f"You're traveling toward {dest_str}—almost there."
        elif remaining <= 3:
            return f"You're traveling toward {dest_str}, getting close now."
        else:
            return f"You're traveling toward {dest_str}. The journey continues."

    def _format_visible_agents(
        self,
        agent: Agent,
        visible_agents: list[Agent],
    ) -> str:
        """Format visible agents for perception.

        For known agents: "Sage is north of you."
        For unknown agents: "Someone unfamiliar is west of you."

        Args:
            agent: The perceiving agent
            visible_agents: Agents visible in the grid

        Returns:
            Description of visible agents, or empty string if none
        """
        if not visible_agents:
            return ""

        descriptions = []
        for other in visible_agents:
            direction = self._get_direction_phrase(agent.position, other.position)

            if other.name in agent.known_agents:
                descriptions.append(f"{other.name} is {direction} of you.")
            else:
                descriptions.append(f"Someone unfamiliar is {direction} of you.")

        return " ".join(descriptions)

    def _format_invitation(self, invitation: Invitation) -> str:
        """Format a pending invitation for perception.

        Args:
            invitation: The pending invitation

        Returns:
            Human-readable invitation text
        """
        if invitation.privacy == "private":
            return f"{invitation.inviter} would like to speak with you privately."
        else:
            return f"{invitation.inviter} would like to talk with you."

    def _format_conversation(self, context: ConversationContext) -> str:
        """Format conversation context for perception.

        Shows only unseen turns (since agent's last turn).

        Args:
            context: ConversationContext with unseen turns

        Returns:
            Formatted conversation history
        """
        parts = []

        # Show participants with natural phrasing
        others = sorted(str(p) for p in context.other_participants)
        if len(others) == 1:
            parts.append(f"You're talking with {others[0]}.")
        elif len(others) == 2:
            parts.append(f"You're talking with {others[0]} and {others[1]}.")
        elif len(others) > 2:
            parts.append(f"You're talking with {', '.join(others[:-1])}, and {others[-1]}.")
        else:
            parts.append("You're in conversation.")

        # Show privacy status - softer phrasing
        if context.conversation.privacy == "private":
            parts.append("(Just between you.)")

        # Show unseen turns
        if context.unseen_turns:
            parts.append("")
            for turn in context.unseen_turns:
                parts.append(f'{turn.speaker}: "{turn.message}"')
        else:
            parts.append("")
            parts.append("(Waiting for you to speak.)")

        return "\n".join(parts)
