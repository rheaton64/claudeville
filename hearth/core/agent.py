"""Agent models for Hearth.

Agents are Claude instances living in the world. Each has:
- Position and movement state (including journeys)
- Inventory (hybrid: stackable resources + unique items)
- Relationships (who they've met)
- Session state (LLM conversation continuity)
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .types import Position, AgentName, ObjectId, LandmarkName
from .objects import Item


class JourneyDestination(BaseModel):
    """Destination for a journey: either coordinates or a named landmark.

    At least one of position or landmark must be set.
    """

    model_config = ConfigDict(frozen=True)

    position: Position | None = None
    landmark: LandmarkName | None = None

    @classmethod
    def to_position(cls, pos: Position) -> JourneyDestination:
        """Create a destination targeting specific coordinates."""
        return cls(position=pos)

    @classmethod
    def to_landmark(cls, name: LandmarkName) -> JourneyDestination:
        """Create a destination targeting a named landmark."""
        return cls(landmark=name)

    def is_resolved(self) -> bool:
        """Check if destination has been resolved to coordinates."""
        return self.position is not None


class Journey(BaseModel):
    """Active journey state.

    When an agent begins traveling to a distant location, they enter a journey.
    Each tick they advance one cell along the computed path.
    """

    model_config = ConfigDict(frozen=True)

    destination: JourneyDestination
    path: tuple[Position, ...] = ()  # Computed path to follow
    progress: int = 0  # Current index into path

    @property
    def current_position(self) -> Position | None:
        """Get the current position along the path, or None if at end."""
        if 0 <= self.progress < len(self.path):
            return self.path[self.progress]
        return None

    @property
    def next_position(self) -> Position | None:
        """Get the next position along the path, or None if complete."""
        next_idx = self.progress + 1
        if 0 <= next_idx < len(self.path):
            return self.path[next_idx]
        return None

    @property
    def is_complete(self) -> bool:
        """Check if the journey has been completed."""
        return self.progress >= len(self.path) - 1

    @property
    def remaining_steps(self) -> int:
        """Number of steps remaining in the journey."""
        return max(0, len(self.path) - 1 - self.progress)

    def advance(self) -> Journey:
        """Return a new journey advanced by one step."""
        return self.model_copy(update={"progress": self.progress + 1})

    @classmethod
    def create(
        cls,
        destination: JourneyDestination,
        path: tuple[Position, ...],
    ) -> Journey:
        """Create a new journey with the given path."""
        return cls(destination=destination, path=path, progress=0)


class InventoryStack(BaseModel):
    """A stack of a single resource type.

    Used for stackable resources like wood, stone, clay.
    """

    model_config = ConfigDict(frozen=True)

    item_type: str
    quantity: int

    def add(self, amount: int) -> InventoryStack:
        """Return a new stack with increased quantity."""
        return self.model_copy(update={"quantity": self.quantity + amount})

    def remove(self, amount: int) -> InventoryStack:
        """Return a new stack with decreased quantity."""
        new_qty = self.quantity - amount
        if new_qty < 0:
            raise ValueError(f"Cannot remove {amount} from stack of {self.quantity}")
        return self.model_copy(update={"quantity": new_qty})


class Inventory(BaseModel):
    """Hybrid inventory: stackable resources + unique items.

    Stacks are for basic resources (wood, stone, clay, etc.).
    Items are for unique/crafted objects with individual IDs.
    """

    model_config = ConfigDict(frozen=True)

    stacks: tuple[InventoryStack, ...] = ()
    items: tuple[Item, ...] = ()

    def _find_stack_index(self, item_type: str) -> int | None:
        """Find the index of a stack by item type."""
        for i, stack in enumerate(self.stacks):
            if stack.item_type == item_type:
                return i
        return None

    def get_resource_quantity(self, item_type: str) -> int:
        """Get the quantity of a stackable resource."""
        idx = self._find_stack_index(item_type)
        if idx is not None:
            return self.stacks[idx].quantity
        return 0

    def has_resource(self, item_type: str, quantity: int = 1) -> bool:
        """Check if inventory has at least the given quantity of a resource."""
        return self.get_resource_quantity(item_type) >= quantity

    def add_resource(self, item_type: str, quantity: int = 1) -> Inventory:
        """Return a new inventory with resource added."""
        idx = self._find_stack_index(item_type)

        if idx is not None:
            # Update existing stack
            new_stack = self.stacks[idx].add(quantity)
            new_stacks = self.stacks[:idx] + (new_stack,) + self.stacks[idx + 1:]
        else:
            # Create new stack
            new_stacks = self.stacks + (InventoryStack(item_type=item_type, quantity=quantity),)

        return self.model_copy(update={"stacks": new_stacks})

    def remove_resource(self, item_type: str, quantity: int = 1) -> Inventory:
        """Return a new inventory with resource removed.

        Raises ValueError if insufficient quantity.
        """
        idx = self._find_stack_index(item_type)

        if idx is None:
            raise ValueError(f"No {item_type} in inventory")

        stack = self.stacks[idx]
        if stack.quantity < quantity:
            raise ValueError(f"Only {stack.quantity} {item_type} in inventory, need {quantity}")

        if stack.quantity == quantity:
            # Remove the stack entirely
            new_stacks = self.stacks[:idx] + self.stacks[idx + 1:]
        else:
            # Decrease the quantity
            new_stack = stack.remove(quantity)
            new_stacks = self.stacks[:idx] + (new_stack,) + self.stacks[idx + 1:]

        return self.model_copy(update={"stacks": new_stacks})

    def get_item(self, item_id: ObjectId) -> Item | None:
        """Get a unique item by ID."""
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def has_item(self, item_id: ObjectId) -> bool:
        """Check if a unique item is in inventory."""
        return self.get_item(item_id) is not None

    def add_item(self, item: Item) -> Inventory:
        """Return a new inventory with a unique item added."""
        if item.is_stackable:
            # Stackable items go to stacks
            return self.add_resource(item.item_type, item.quantity)

        # Unique items get added to items list
        return self.model_copy(update={"items": self.items + (item,)})

    def remove_item(self, item_id: ObjectId) -> Inventory:
        """Return a new inventory with a unique item removed.

        Raises ValueError if item not found.
        """
        new_items = tuple(item for item in self.items if item.id != item_id)
        if len(new_items) == len(self.items):
            raise ValueError(f"Item {item_id} not in inventory")
        return self.model_copy(update={"items": new_items})

    @property
    def is_empty(self) -> bool:
        """Check if inventory is completely empty."""
        return len(self.stacks) == 0 and len(self.items) == 0

    def all_items(self) -> list[Item]:
        """Get all items (both stacks converted to items, and unique items)."""
        result: list[Item] = []

        # Convert stacks to stackable items
        for stack in self.stacks:
            result.append(Item.stackable(stack.item_type, stack.quantity))

        # Add unique items
        result.extend(self.items)

        return result


class AgentModel(BaseModel):
    """LLM model configuration for an agent."""

    model_config = ConfigDict(frozen=True)

    id: str
    display_name: str


class Agent(BaseModel):
    """Agent state snapshot.

    Represents a Claude instance living in the world.
    """

    model_config = ConfigDict(frozen=True)

    # Identity
    name: AgentName
    model: AgentModel
    personality: str = ""

    # Position and movement
    position: Position
    journey: Journey | None = None

    # Inventory
    inventory: Inventory = Field(default_factory=Inventory)

    # State
    is_sleeping: bool = False

    # Relationships (agents we've met and can sense)
    known_agents: frozenset[AgentName] = Field(default_factory=frozenset)

    # Session tracking for LLM conversation continuity
    session_id: str | None = None
    last_active_tick: int = 0

    @property
    def is_journeying(self) -> bool:
        """Check if agent is currently on a journey."""
        return self.journey is not None and not self.journey.is_complete

    def with_position(self, pos: Position) -> Agent:
        """Return a new agent at the given position."""
        return self.model_copy(update={"position": pos})

    def with_journey(self, journey: Journey | None) -> Agent:
        """Return a new agent with the given journey state."""
        return self.model_copy(update={"journey": journey})

    def with_inventory(self, inventory: Inventory) -> Agent:
        """Return a new agent with the given inventory."""
        return self.model_copy(update={"inventory": inventory})

    def with_sleeping(self, is_sleeping: bool) -> Agent:
        """Return a new agent with updated sleep state."""
        return self.model_copy(update={"is_sleeping": is_sleeping})

    def with_known_agent(self, agent_name: AgentName) -> Agent:
        """Return a new agent that knows the given agent."""
        if agent_name in self.known_agents:
            return self
        return self.model_copy(update={"known_agents": self.known_agents | {agent_name}})

    def with_session_id(self, session_id: str | None) -> Agent:
        """Return a new agent with updated session ID."""
        return self.model_copy(update={"session_id": session_id})

    def with_last_active_tick(self, tick: int) -> Agent:
        """Return a new agent with updated last active tick."""
        return self.model_copy(update={"last_active_tick": tick})

    def add_resource(self, item_type: str, quantity: int = 1) -> Agent:
        """Return a new agent with resource added to inventory."""
        new_inventory = self.inventory.add_resource(item_type, quantity)
        return self.with_inventory(new_inventory)

    def remove_resource(self, item_type: str, quantity: int = 1) -> Agent:
        """Return a new agent with resource removed from inventory."""
        new_inventory = self.inventory.remove_resource(item_type, quantity)
        return self.with_inventory(new_inventory)

    def add_item(self, item: Item) -> Agent:
        """Return a new agent with item added to inventory."""
        new_inventory = self.inventory.add_item(item)
        return self.with_inventory(new_inventory)

    def remove_item(self, item_id: ObjectId) -> Agent:
        """Return a new agent with item removed from inventory."""
        new_inventory = self.inventory.remove_item(item_id)
        return self.with_inventory(new_inventory)

    def knows(self, agent_name: AgentName) -> bool:
        """Check if this agent knows another agent."""
        return agent_name in self.known_agents
