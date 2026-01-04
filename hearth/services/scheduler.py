"""Scheduler service for Hearth.

Handles cluster-based turn scheduling. All agents act every tick, but:
- Agents in different clusters execute in parallel
- Agents in the same cluster execute sequentially (round-robin)

Clustering threshold: vision_radius + CLUSTER_BUFFER (buffer for approaching agents)
"""

from __future__ import annotations

from core.types import AgentName
from core.agent import Agent


class Scheduler:
    """Cluster-based turn scheduling.

    All agents act every tick. Clustering determines execution order:
    - Separate clusters: parallel execution (efficiency)
    - Same cluster: sequential execution (see each other's actions)

    Uses union-find algorithm to compute clusters of agents that are
    within the cluster radius of each other.
    """

    CLUSTER_BUFFER = 2  # Buffer added to vision radius

    def __init__(self, vision_radius: int):
        """Initialize Scheduler.

        Args:
            vision_radius: Vision radius from PerceptionBuilder.
                          Cluster radius = vision_radius + CLUSTER_BUFFER.
        """
        self._vision_radius = vision_radius
        self._cluster_radius = vision_radius + self.CLUSTER_BUFFER
        self._forced_next: AgentName | None = None

    @property
    def vision_radius(self) -> int:
        """Get vision radius (for phases that need it)."""
        return self._vision_radius

    @property
    def cluster_radius(self) -> int:
        """Get cluster radius (vision_radius + buffer)."""
        return self._cluster_radius

    def compute_clusters(
        self, agents: dict[AgentName, Agent]
    ) -> list[list[AgentName]]:
        """Compute agent clusters based on proximity.

        Uses union-find to group agents within cluster_radius of each other.
        Two agents are in the same cluster if they can reach each other through
        a chain of agents, where each link is within cluster_radius.

        Args:
            agents: Dictionary of agent name to Agent

        Returns:
            List of clusters, each cluster is a list of agent names.
            Order within clusters is arbitrary (will be modified by force_next).
        """
        if not agents:
            return []

        agent_list = list(agents.keys())
        n = len(agent_list)

        # Union-find data structure
        parent = list(range(n))

        def find(x: int) -> int:
            """Find root with path compression."""
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x: int, y: int) -> None:
            """Union two sets."""
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        # Union agents within cluster radius
        for i in range(n):
            for j in range(i + 1, n):
                agent_i = agents[agent_list[i]]
                agent_j = agents[agent_list[j]]
                dist = agent_i.position.distance_to(agent_j.position)
                if dist <= self._cluster_radius:
                    union(i, j)

        # Group by root
        clusters_map: dict[int, list[AgentName]] = {}
        for i, name in enumerate(agent_list):
            root = find(i)
            if root not in clusters_map:
                clusters_map[root] = []
            clusters_map[root].append(name)

        return list(clusters_map.values())

    def force_next(self, agent: AgentName) -> None:
        """Force an agent to act first in their cluster next tick.

        This is used by observer commands to prioritize an agent's turn.

        Args:
            agent: Agent name to force to front of their cluster
        """
        self._forced_next = agent

    def get_forced_next(self) -> AgentName | None:
        """Get and clear forced next agent.

        Returns:
            Agent name that was forced, or None if no agent was forced.
            Clears the forced state after returning.
        """
        agent = self._forced_next
        self._forced_next = None
        return agent
