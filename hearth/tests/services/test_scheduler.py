"""Tests for Scheduler service."""

import pytest

from hearth.core.types import AgentName, Position
from hearth.core.agent import Agent, AgentModel
from hearth.services.scheduler import Scheduler


@pytest.fixture
def scheduler():
    """Create a scheduler with vision radius 3."""
    return Scheduler(vision_radius=3)


@pytest.fixture
def model():
    """Create a test model."""
    return AgentModel(id="test-model", display_name="Test Model")


def make_agent(name: str, x: int, y: int, model: AgentModel) -> Agent:
    """Helper to create agent at position."""
    return Agent(
        name=AgentName(name),
        model=model,
        position=Position(x, y),
    )


class TestScheduler:
    """Tests for Scheduler clustering."""

    def test_init_with_vision_radius(self):
        """Test scheduler initializes with correct radius."""
        s = Scheduler(vision_radius=5)
        assert s.vision_radius == 5
        assert s.cluster_radius == 7  # vision + buffer(2)

    def test_empty_agents(self, scheduler):
        """Test clustering with no agents."""
        clusters = scheduler.compute_clusters({})
        assert clusters == []

    def test_single_agent(self, scheduler, model):
        """Test clustering with single agent."""
        agents = {AgentName("Ember"): make_agent("Ember", 0, 0, model)}
        clusters = scheduler.compute_clusters(agents)

        assert len(clusters) == 1
        assert AgentName("Ember") in clusters[0]

    def test_two_distant_agents(self, scheduler, model):
        """Test two agents far apart form separate clusters."""
        # Vision radius 3 + buffer 2 = cluster radius 5
        # Agents 100 apart should be in separate clusters
        agents = {
            AgentName("Ember"): make_agent("Ember", 0, 0, model),
            AgentName("Sage"): make_agent("Sage", 100, 100, model),
        }
        clusters = scheduler.compute_clusters(agents)

        assert len(clusters) == 2
        # Each agent in their own cluster
        assert any(AgentName("Ember") in c and len(c) == 1 for c in clusters)
        assert any(AgentName("Sage") in c and len(c) == 1 for c in clusters)

    def test_two_nearby_agents(self, scheduler, model):
        """Test two nearby agents form single cluster."""
        # Vision radius 3 + buffer 2 = cluster radius 5
        # Agents 3 apart should be in same cluster
        agents = {
            AgentName("Ember"): make_agent("Ember", 0, 0, model),
            AgentName("Sage"): make_agent("Sage", 2, 1, model),  # distance = 3
        }
        clusters = scheduler.compute_clusters(agents)

        assert len(clusters) == 1
        assert AgentName("Ember") in clusters[0]
        assert AgentName("Sage") in clusters[0]

    def test_three_agents_chain(self, scheduler, model):
        """Test three agents in a chain form single cluster."""
        # A-B and B-C nearby, but A-C far
        # Still should form single cluster via transitive connection
        agents = {
            AgentName("A"): make_agent("A", 0, 0, model),
            AgentName("B"): make_agent("B", 4, 0, model),  # near A
            AgentName("C"): make_agent("C", 8, 0, model),  # near B, far from A
        }
        clusters = scheduler.compute_clusters(agents)

        assert len(clusters) == 1
        assert len(clusters[0]) == 3

    def test_force_next(self, scheduler):
        """Test force_next sets and clears."""
        assert scheduler.get_forced_next() is None

        scheduler.force_next(AgentName("Ember"))
        assert scheduler.get_forced_next() == AgentName("Ember")

        # Should be cleared after get
        assert scheduler.get_forced_next() is None

    def test_force_next_overwrite(self, scheduler):
        """Test force_next overwrites previous."""
        scheduler.force_next(AgentName("Ember"))
        scheduler.force_next(AgentName("Sage"))

        assert scheduler.get_forced_next() == AgentName("Sage")

    def test_cluster_at_boundary(self, scheduler, model):
        """Test agents exactly at cluster radius boundary."""
        # Cluster radius = 5 (Manhattan distance)
        agents = {
            AgentName("A"): make_agent("A", 0, 0, model),
            AgentName("B"): make_agent("B", 5, 0, model),  # exactly at boundary
        }
        clusters = scheduler.compute_clusters(agents)

        # Should be in same cluster (boundary is inclusive)
        assert len(clusters) == 1

    def test_cluster_just_outside_boundary(self, scheduler, model):
        """Test agents just outside cluster radius."""
        # Cluster radius = 5 (Manhattan distance)
        agents = {
            AgentName("A"): make_agent("A", 0, 0, model),
            AgentName("B"): make_agent("B", 6, 0, model),  # just outside
        }
        clusters = scheduler.compute_clusters(agents)

        # Should be in separate clusters
        assert len(clusters) == 2
