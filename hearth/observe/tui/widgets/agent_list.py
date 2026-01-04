"""Agent list widget for Hearth TUI.

Shows all agents with their positions and status.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rich.text import Text
from textual.widget import Widget
from textual.reactive import reactive

if TYPE_CHECKING:
    from core.agent import Agent


@dataclass
class AgentSummary:
    """Summary of agent state for display."""

    name: str
    position: tuple[int, int]
    is_sleeping: bool
    is_journeying: bool
    journey_destination: str | None


class AgentList(Widget):
    """Widget showing list of all agents."""

    selected: reactive[str | None] = reactive(None)
    _agents: list[AgentSummary]

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ):
        """Initialize AgentList."""
        super().__init__(name=name, id=id, classes=classes)
        self._agents = []

    def update_agents(self, agents: list["Agent"]) -> None:
        """Update the agent list.

        Args:
            agents: List of Agent objects
        """
        self._agents = []
        for agent in agents:
            journey_dest = None
            if agent.journey:
                dest = agent.journey.destination
                if dest.landmark:
                    journey_dest = str(dest.landmark)
                elif dest.position:
                    journey_dest = f"({dest.position.x}, {dest.position.y})"

            self._agents.append(
                AgentSummary(
                    name=str(agent.name),
                    position=(agent.position.x, agent.position.y),
                    is_sleeping=agent.is_sleeping,
                    is_journeying=agent.is_journeying,
                    journey_destination=journey_dest,
                )
            )
        self.refresh()

    def render(self) -> Text:
        """Render the agent list."""
        text = Text()
        text.append("Agents\n", style="bold underline")
        text.append("\n")

        if not self._agents:
            text.append("No agents", style="dim")
            return text

        for agent in self._agents:
            # Selection indicator
            if self.selected == agent.name:
                text.append("> ", style="bold yellow")
            else:
                text.append("  ")

            # Agent name with color
            color = self._get_agent_color(agent.name)
            text.append(agent.name, style=f"bold {color}")

            # Position
            text.append(f" ({agent.position[0]}, {agent.position[1]})", style="dim")

            # Status icons
            if agent.is_sleeping:
                text.append(" ZzZ", style="blue")
            elif agent.is_journeying and agent.journey_destination:
                text.append(f" -> {agent.journey_destination}", style="yellow")

            text.append("\n")

        # Instructions
        text.append("\n")
        text.append("1/2/3 to focus agent\n", style="dim")
        text.append("f to toggle follow\n", style="dim")

        return text

    def _get_agent_color(self, name: str) -> str:
        """Get color for agent name."""
        colors = {
            "Ember": "red",
            "Sage": "magenta",
            "River": "cyan",
        }
        return colors.get(name, "white")

    def select(self, agent_name: str | None) -> None:
        """Select an agent.

        Args:
            agent_name: Name of agent to select, or None
        """
        self.selected = agent_name
        self.refresh()
