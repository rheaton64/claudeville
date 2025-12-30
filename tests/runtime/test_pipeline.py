"""Tests for engine.runtime.pipeline module."""

import pytest
from datetime import datetime

from engine.domain import AgentName, LocationId, MoveAgentEffect
from engine.runtime.context import TickContext, TickResult
from engine.runtime.pipeline import (
    Phase,
    BasePhase,
    PhaseError,
    PipelineMetrics,
    TickPipeline,
)


class SimplePhase(BasePhase):
    """Simple phase for testing."""

    def __init__(self, phase_name: str = "simple"):
        self._phase_name = phase_name

    @property
    def name(self) -> str:
        return self._phase_name

    async def _execute(self, ctx: TickContext) -> TickContext:
        return ctx


class EffectProducingPhase(BasePhase):
    """Phase that produces an effect."""

    async def _execute(self, ctx: TickContext) -> TickContext:
        effect = MoveAgentEffect(
            agent=AgentName("Ember"),
            from_location=LocationId("workshop"),
            to_location=LocationId("garden"),
        )
        return ctx.with_effect(effect)


class AgentActingPhase(BasePhase):
    """Phase that marks an agent as acted."""

    async def _execute(self, ctx: TickContext) -> TickContext:
        return ctx.with_agent_acted(AgentName("Ember"))


class ErrorPhase(BasePhase):
    """Phase that raises an error."""

    def __init__(self, error_message: str = "Test error"):
        self.error_message = error_message

    async def _execute(self, ctx: TickContext) -> TickContext:
        raise ValueError(self.error_message)


class ContextModifyingPhase(BasePhase):
    """Phase that modifies context in a specific way."""

    def __init__(self, modification: str):
        self.modification = modification

    async def _execute(self, ctx: TickContext) -> TickContext:
        if self.modification == "set_agents_to_act":
            return ctx.with_agents_to_act(frozenset([AgentName("Ember")]))
        elif self.modification == "mark_acted":
            return ctx.with_agent_acted(AgentName("Ember"))
        return ctx


class TestPhaseProtocol:
    """Tests for Phase protocol compliance."""

    def test_base_phase_implements_protocol(self):
        """Test BasePhase implements Phase protocol."""
        phase = SimplePhase()

        assert isinstance(phase, Phase)

    def test_phase_has_name_property(self):
        """Test phase has name property."""
        phase = EffectProducingPhase()

        assert phase.name == "effect_producing"

    def test_phase_name_strips_phase_suffix(self):
        """Test phase name strips 'Phase' suffix."""
        phase = AgentActingPhase()

        assert phase.name == "agent_acting"


class TestBasePhase:
    """Tests for BasePhase execution."""

    @pytest.mark.asyncio
    async def test_execute_returns_context(self, tick_context: TickContext):
        """Test execute returns context."""
        phase = SimplePhase()

        result = await phase.execute(tick_context)

        assert isinstance(result, TickContext)

    @pytest.mark.asyncio
    async def test_execute_wraps_error(self, tick_context: TickContext):
        """Test execute wraps errors in PhaseError."""
        phase = ErrorPhase("Something went wrong")

        with pytest.raises(PhaseError) as exc_info:
            await phase.execute(tick_context)

        assert exc_info.value.phase_name == "error"
        assert isinstance(exc_info.value.original_error, ValueError)
        assert "Something went wrong" in str(exc_info.value.original_error)

    @pytest.mark.asyncio
    async def test_execute_preserves_original_error(self, tick_context: TickContext):
        """Test original error is preserved in PhaseError."""
        phase = ErrorPhase("Original error message")

        with pytest.raises(PhaseError) as exc_info:
            await phase.execute(tick_context)

        # Can access original error
        assert str(exc_info.value.original_error) == "Original error message"


class TestPhaseError:
    """Tests for PhaseError."""

    def test_creation(self):
        """Test creating PhaseError."""
        original = ValueError("test")
        error = PhaseError(phase_name="test_phase", original_error=original)

        assert error.phase_name == "test_phase"
        assert error.original_error == original

    def test_str_representation(self):
        """Test string representation."""
        original = ValueError("something failed")
        error = PhaseError(phase_name="my_phase", original_error=original)

        assert "my_phase" in str(error)
        assert "something failed" in str(error)


class TestPipelineMetrics:
    """Tests for PipelineMetrics."""

    def test_default_values(self):
        """Test default metric values."""
        metrics = PipelineMetrics()

        assert metrics.total_duration_ms == 0.0
        assert metrics.phase_durations_ms == {}
        assert metrics.effects_produced == 0
        assert metrics.events_produced == 0
        assert metrics.agents_acted == 0


class TestTickPipeline:
    """Tests for TickPipeline."""

    def test_creation(self):
        """Test creating pipeline."""
        phases = [SimplePhase("phase1"), SimplePhase("phase2")]
        pipeline = TickPipeline(phases)

        assert len(pipeline.phases) == 2

    @pytest.mark.asyncio
    async def test_execute_empty_pipeline(self, tick_context: TickContext):
        """Test executing empty pipeline."""
        pipeline = TickPipeline([])

        result = await pipeline.execute(tick_context)

        assert isinstance(result, TickResult)
        assert result.tick == tick_context.tick

    @pytest.mark.asyncio
    async def test_execute_single_phase(self, tick_context: TickContext):
        """Test executing single phase."""
        pipeline = TickPipeline([SimplePhase()])

        result = await pipeline.execute(tick_context)

        assert isinstance(result, TickResult)

    @pytest.mark.asyncio
    async def test_execute_multiple_phases_in_order(self, tick_context: TickContext):
        """Test phases execute in order."""
        phases = [
            ContextModifyingPhase("set_agents_to_act"),
            ContextModifyingPhase("mark_acted"),
        ]
        pipeline = TickPipeline(phases)

        result = await pipeline.execute(tick_context)

        assert AgentName("Ember") in result.agents_acted

    @pytest.mark.asyncio
    async def test_execute_accumulates_effects(self, tick_context: TickContext):
        """Test effects accumulate across phases."""
        pipeline = TickPipeline([
            EffectProducingPhase(),
            EffectProducingPhase(),
        ])

        result = await pipeline.execute(tick_context)

        assert len(result.effects) == 2

    @pytest.mark.asyncio
    async def test_execute_propagates_error(self, tick_context: TickContext):
        """Test pipeline propagates phase errors."""
        pipeline = TickPipeline([
            SimplePhase(),
            ErrorPhase("mid-pipeline error"),
            SimplePhase(),  # Should not execute
        ])

        with pytest.raises(PhaseError):
            await pipeline.execute(tick_context)

    @pytest.mark.asyncio
    async def test_metrics_collected(self, tick_context: TickContext):
        """Test metrics are collected during execution."""
        pipeline = TickPipeline([
            SimplePhase("phase_a"),
            EffectProducingPhase(),
            AgentActingPhase(),
        ])

        await pipeline.execute(tick_context)
        metrics = pipeline.get_metrics()

        assert metrics is not None
        assert metrics.total_duration_ms > 0
        assert "phase_a" in metrics.phase_durations_ms
        assert "effect_producing" in metrics.phase_durations_ms
        assert metrics.effects_produced == 1
        assert metrics.agents_acted == 1

    @pytest.mark.asyncio
    async def test_metrics_none_before_execute(self):
        """Test metrics are None before execution."""
        pipeline = TickPipeline([SimplePhase()])

        assert pipeline.get_metrics() is None

    def test_get_phase_by_name(self):
        """Test getting phase by name."""
        phase1 = SimplePhase("first")
        phase2 = SimplePhase("second")
        pipeline = TickPipeline([phase1, phase2])

        found = pipeline.get_phase("second")

        assert found == phase2

    def test_get_phase_not_found(self):
        """Test getting nonexistent phase returns None."""
        pipeline = TickPipeline([SimplePhase("only_one")])

        found = pipeline.get_phase("nonexistent")

        assert found is None

    @pytest.mark.asyncio
    async def test_returns_tick_result(self, tick_context: TickContext):
        """Test pipeline returns TickResult."""
        pipeline = TickPipeline([
            EffectProducingPhase(),
            AgentActingPhase(),
        ])

        result = await pipeline.execute(tick_context)

        assert isinstance(result, TickResult)
        assert result.tick == tick_context.tick
        assert result.timestamp == tick_context.timestamp
        assert len(result.effects) == 1
        assert len(result.agents_acted) == 1
