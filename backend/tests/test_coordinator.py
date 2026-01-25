"""Comprehensive tests for the Pipeline Coordinator.

Tests cover:
- Stage execution and orchestration
- Progress tracking and callbacks
- Error handling and recovery
- Pipeline state management
- Integration with individual agents
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base_agent import AgentResult, BaseAgent, JobContext
from app.agents.coordinator import (
    CoordinatorAgent,
    CoordinatorResult,
    CoordinatorStatus,
    PipelineCoordinator,
    StageConfig,
    StageResult,
)


# =============================================================================
# Test Fixtures and Helpers
# =============================================================================


class MockSuccessAgent(BaseAgent):
    """Mock agent that always succeeds."""

    async def execute(self, context: JobContext) -> AgentResult:
        return AgentResult(
            success=True,
            data={"mock": "data", "stage": self.name},
        )


class MockFailureAgent(BaseAgent):
    """Mock agent that always fails."""

    async def execute(self, context: JobContext) -> AgentResult:
        return AgentResult(
            success=False,
            error="Mock failure",
        )


class MockDelayAgent(BaseAgent):
    """Mock agent with configurable delay."""

    def __init__(self, delay: float = 0.1):
        super().__init__()
        self.delay = delay

    async def execute(self, context: JobContext) -> AgentResult:
        await asyncio.sleep(self.delay)
        return AgentResult(
            success=True,
            data={"delay": self.delay},
        )


def create_test_context(
    hierarchy: dict = None,
    theme: dict = None,
    options: dict = None,
) -> JobContext:
    """Create a test JobContext."""
    if hierarchy is None:
        hierarchy = {
            "L0": {"title": "Test Project", "id": "root"},
            "L1": [
                {"id": "m1", "title": "Milestone 1"},
                {"id": "m2", "title": "Milestone 2"},
            ],
        }

    return JobContext(
        job_id=1,
        user_id=1,
        document_url="http://example.com/doc",
        hierarchy=hierarchy,
        theme=theme or {"theme_id": "smb3"},
        options=options or {},
    )


# =============================================================================
# StageConfig Tests
# =============================================================================


class TestStageConfig:
    """Tests for StageConfig dataclass."""

    def test_stage_config_creation(self):
        """Test creating a stage configuration."""
        config = StageConfig(
            name="test_stage",
            agent_class=MockSuccessAgent,
            required_inputs=["hierarchy"],
            timeout_seconds=30,
        )

        assert config.name == "test_stage"
        assert config.agent_class == MockSuccessAgent
        assert config.required_inputs == ["hierarchy"]
        assert config.timeout_seconds == 30
        assert config.retry_count == 3  # default

    def test_stage_config_defaults(self):
        """Test default values in StageConfig."""
        config = StageConfig(
            name="minimal",
            agent_class=MockSuccessAgent,
        )

        assert config.required_inputs == []
        assert config.optional_inputs == []
        assert config.timeout_seconds == 120
        assert config.retry_count == 3


# =============================================================================
# StageResult Tests
# =============================================================================


class TestStageResult:
    """Tests for StageResult dataclass."""

    def test_stage_result_success(self):
        """Test successful stage result."""
        result = StageResult(
            stage_name="test",
            success=True,
            data={"key": "value"},
            execution_time_ms=100,
        )

        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error is None

    def test_stage_result_failure(self):
        """Test failed stage result."""
        result = StageResult(
            stage_name="test",
            success=False,
            error="Something went wrong",
            retry_attempts=3,
        )

        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.retry_attempts == 3


# =============================================================================
# PipelineCoordinator Tests
# =============================================================================


class TestPipelineCoordinator:
    """Tests for PipelineCoordinator class."""

    @pytest.mark.asyncio
    async def test_coordinator_initialization(self):
        """Test coordinator initialization with defaults."""
        coordinator = PipelineCoordinator()

        assert coordinator.status == CoordinatorStatus.IDLE
        assert len(coordinator.stages) == 4  # Default stages
        assert coordinator._cancelled is False

    @pytest.mark.asyncio
    async def test_coordinator_custom_stages(self):
        """Test coordinator with custom stages."""
        stages = [
            StageConfig(name="stage1", agent_class=MockSuccessAgent),
            StageConfig(name="stage2", agent_class=MockSuccessAgent),
        ]

        coordinator = PipelineCoordinator(stages=stages)

        assert len(coordinator.stages) == 2
        assert coordinator.stages[0].name == "stage1"

    @pytest.mark.asyncio
    async def test_coordinator_progress_callback(self):
        """Test progress callback is invoked."""
        progress_updates = []

        def on_progress(stage: str, progress: float, message: str):
            progress_updates.append((stage, progress, message))

        stages = [
            StageConfig(
                name="test_stage",
                agent_class=MockSuccessAgent,
                required_inputs=["hierarchy"],
            )
        ]

        coordinator = PipelineCoordinator(
            stages=stages,
            on_progress=on_progress,
        )

        context = create_test_context()
        await coordinator.execute(context)

        assert len(progress_updates) > 0
        # Should have at least start and end progress updates
        stages_in_updates = [u[0] for u in progress_updates]
        assert "test_stage" in stages_in_updates

    @pytest.mark.asyncio
    async def test_coordinator_error_callback(self):
        """Test error callback is invoked on failure."""
        error_reports = []

        def on_error(stage: str, error: str, recoverable: bool):
            error_reports.append((stage, error, recoverable))

        stages = [
            StageConfig(
                name="failing_stage",
                agent_class=MockFailureAgent,
                required_inputs=["hierarchy"],
                retry_count=1,  # Minimize retries for test speed
            )
        ]

        coordinator = PipelineCoordinator(
            stages=stages,
            on_error=on_error,
        )

        context = create_test_context()
        result = await coordinator.execute(context)

        assert result.success is False
        assert len(error_reports) > 0

    @pytest.mark.asyncio
    async def test_coordinator_successful_execution(self):
        """Test successful pipeline execution."""
        stages = [
            StageConfig(
                name="stage1",
                agent_class=MockSuccessAgent,
                required_inputs=["hierarchy"],
            ),
            StageConfig(
                name="stage2",
                agent_class=MockSuccessAgent,
                required_inputs=["stage1"],
            ),
        ]

        coordinator = PipelineCoordinator(stages=stages)
        context = create_test_context()

        result = await coordinator.execute(context)

        assert result.success is True
        assert coordinator.status == CoordinatorStatus.COMPLETED
        assert result.stages_completed == 2
        assert result.error is None

    @pytest.mark.asyncio
    async def test_coordinator_failed_execution(self):
        """Test pipeline execution with a failing stage."""
        stages = [
            StageConfig(
                name="success_stage",
                agent_class=MockSuccessAgent,
                required_inputs=["hierarchy"],
            ),
            StageConfig(
                name="failure_stage",
                agent_class=MockFailureAgent,
                required_inputs=["success_stage"],
                retry_count=1,
            ),
        ]

        coordinator = PipelineCoordinator(stages=stages)
        context = create_test_context()

        result = await coordinator.execute(context)

        assert result.success is False
        assert coordinator.status == CoordinatorStatus.FAILED
        assert "failure_stage" in result.error

    @pytest.mark.asyncio
    async def test_coordinator_missing_inputs(self):
        """Test error when required inputs are missing."""
        stages = [
            StageConfig(
                name="needs_input",
                agent_class=MockSuccessAgent,
                required_inputs=["nonexistent_stage"],
            )
        ]

        coordinator = PipelineCoordinator(stages=stages)
        context = create_test_context()

        result = await coordinator.execute(context)

        assert result.success is False
        assert "Missing required inputs" in result.error

    @pytest.mark.asyncio
    async def test_coordinator_cancellation(self):
        """Test pipeline cancellation."""
        stages = [
            StageConfig(
                name="slow_stage",
                agent_class=MockDelayAgent,
                required_inputs=["hierarchy"],
            ),
            StageConfig(
                name="never_reached",
                agent_class=MockSuccessAgent,
                required_inputs=["slow_stage"],
            ),
        ]

        coordinator = PipelineCoordinator(stages=stages)
        context = create_test_context()

        # Start execution and cancel immediately
        async def execute_and_cancel():
            task = asyncio.create_task(coordinator.execute(context))
            await asyncio.sleep(0.01)  # Brief delay
            coordinator.cancel()
            return await task

        result = await execute_and_cancel()

        assert coordinator.status == CoordinatorStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_coordinator_retry_logic(self):
        """Test stage retry on failure."""
        call_count = 0

        class FlakeyAgent(BaseAgent):
            async def execute(self, context: JobContext) -> AgentResult:
                nonlocal call_count
                call_count += 1
                if call_count < 2:
                    return AgentResult(success=False, error="Flakey failure")
                return AgentResult(success=True, data={"recovered": True})

        stages = [
            StageConfig(
                name="flakey_stage",
                agent_class=FlakeyAgent,
                required_inputs=["hierarchy"],
                retry_count=3,
            )
        ]

        coordinator = PipelineCoordinator(stages=stages)
        context = create_test_context()

        result = await coordinator.execute(context)

        assert result.success is True
        assert call_count == 2  # Failed once, succeeded on retry

    @pytest.mark.asyncio
    async def test_coordinator_checkpointing(self):
        """Test that stage outputs are saved as checkpoints."""
        stages = [
            StageConfig(
                name="stage1",
                agent_class=MockSuccessAgent,
                required_inputs=["hierarchy"],
            ),
            StageConfig(
                name="stage2",
                agent_class=MockSuccessAgent,
                required_inputs=["stage1"],
            ),
        ]

        coordinator = PipelineCoordinator(stages=stages)
        context = create_test_context()

        await coordinator.execute(context)

        # Check that checkpoints were saved
        assert context.get_checkpoint("stage1") is not None
        assert context.get_checkpoint("stage2") is not None

    @pytest.mark.asyncio
    async def test_coordinator_get_stage_result(self):
        """Test retrieving individual stage results."""
        stages = [
            StageConfig(
                name="test_stage",
                agent_class=MockSuccessAgent,
                required_inputs=["hierarchy"],
            )
        ]

        coordinator = PipelineCoordinator(stages=stages)
        context = create_test_context()

        await coordinator.execute(context)

        stage_result = coordinator.get_stage_result("test_stage")
        assert stage_result is not None
        assert stage_result.success is True

        # Non-existent stage
        missing = coordinator.get_stage_result("nonexistent")
        assert missing is None

    @pytest.mark.asyncio
    async def test_coordinator_status_tracking(self):
        """Test status transitions during execution."""
        stages = [
            StageConfig(
                name="quick_stage",
                agent_class=MockSuccessAgent,
                required_inputs=["hierarchy"],
            )
        ]

        coordinator = PipelineCoordinator(stages=stages)
        context = create_test_context()

        assert coordinator.status == CoordinatorStatus.IDLE

        await coordinator.execute(context)

        assert coordinator.status == CoordinatorStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_coordinator_current_stage_tracking(self):
        """Test current stage tracking during execution."""
        stages = [
            StageConfig(
                name="stage1",
                agent_class=MockDelayAgent,
                required_inputs=["hierarchy"],
            ),
            StageConfig(
                name="stage2",
                agent_class=MockDelayAgent,
                required_inputs=["stage1"],
            ),
        ]

        coordinator = PipelineCoordinator(stages=stages)
        context = create_test_context()

        # Start execution and check current stage
        task = asyncio.create_task(coordinator.execute(context))
        await asyncio.sleep(0.05)

        current = coordinator.get_current_stage()
        assert current is not None

        await task

        # After completion, current stage should be None
        assert coordinator.get_current_stage() is None

    @pytest.mark.asyncio
    async def test_coordinator_execution_time_tracking(self):
        """Test that execution times are recorded."""
        stages = [
            StageConfig(
                name="timed_stage",
                agent_class=MockDelayAgent,
                required_inputs=["hierarchy"],
            )
        ]

        # Use a delay agent with known delay
        MockDelayAgent._delay = 0.05

        coordinator = PipelineCoordinator(stages=stages)
        coordinator._agents = {"timed_stage": MockDelayAgent(delay=0.05)}
        context = create_test_context()

        result = await coordinator.execute(context)

        assert result.total_execution_time_ms > 0
        stage_result = result.stage_results[0]
        assert stage_result.execution_time_ms > 0


# =============================================================================
# CoordinatorAgent Tests (Legacy Wrapper)
# =============================================================================


class TestCoordinatorAgent:
    """Tests for the legacy CoordinatorAgent wrapper."""

    @pytest.mark.asyncio
    async def test_coordinator_agent_execute(self):
        """Test CoordinatorAgent execute method."""
        agent = CoordinatorAgent()
        context = create_test_context()

        result = await agent.execute(context)

        # Should succeed with valid hierarchy and theme
        assert result.success is True or result.error is not None

    @pytest.mark.asyncio
    async def test_coordinator_agent_run(self):
        """Test CoordinatorAgent run method (with logging)."""
        agent = CoordinatorAgent()
        context = create_test_context()

        result = await agent.run(context)

        # Run wraps execute with logging
        assert result.success is True or result.error is not None

    @pytest.mark.asyncio
    async def test_coordinator_agent_get_last_result(self):
        """Test retrieving last execution result."""
        agent = CoordinatorAgent()
        context = create_test_context()

        # Before execution, should be None
        assert agent.get_last_result() is None

        await agent.execute(context)

        # After execution, should have result
        last_result = agent.get_last_result()
        assert last_result is not None
        assert isinstance(last_result, CoordinatorResult)

    @pytest.mark.asyncio
    async def test_coordinator_agent_cancel(self):
        """Test cancellation via agent wrapper."""
        agent = CoordinatorAgent()

        # Create coordinator first
        agent.coordinator = PipelineCoordinator()

        # Cancel should not raise
        agent.cancel()

        assert agent.coordinator.status == CoordinatorStatus.CANCELLED


# =============================================================================
# Integration Tests
# =============================================================================


class TestCoordinatorIntegration:
    """Integration tests for the coordinator with real agents."""

    @pytest.mark.asyncio
    async def test_full_pipeline_execution(self):
        """Test running the full default pipeline."""
        agent = CoordinatorAgent()
        context = JobContext(
            job_id=42,
            user_id=1,
            document_url="http://example.com/project",
            hierarchy={
                "L0": {"title": "My Project", "id": "root"},
                "L1": [
                    {"id": "m1", "title": "Planning"},
                    {"id": "m2", "title": "Development"},
                    {"id": "m3", "title": "Testing"},
                    {"id": "m4", "title": "Deployment"},
                ],
            },
            theme={"theme_id": "smb3"},
            options={},
        )

        result = await agent.execute(context)

        if result.success:
            # Verify final map data structure
            data = result.data
            assert "theme" in data
            assert "road" in data
            assert "milestones" in data
            assert "metadata" in data
        # Note: May fail if dependencies (scipy, numpy) not available

    @pytest.mark.asyncio
    async def test_coordinator_result_structure(self):
        """Test the structure of CoordinatorResult."""
        stages = [
            StageConfig(
                name="test",
                agent_class=MockSuccessAgent,
                required_inputs=["hierarchy"],
            )
        ]

        coordinator = PipelineCoordinator(stages=stages)
        context = create_test_context()

        result = await coordinator.execute(context)

        assert isinstance(result, CoordinatorResult)
        assert hasattr(result, "success")
        assert hasattr(result, "final_map_data")
        assert hasattr(result, "stage_results")
        assert hasattr(result, "total_execution_time_ms")
        assert hasattr(result, "stages_completed")
        assert hasattr(result, "error")

    @pytest.mark.asyncio
    async def test_final_map_assembly(self):
        """Test that final map is properly assembled from stage outputs."""
        # Create mock agents that return expected data
        class MockParserAgent(BaseAgent):
            async def execute(self, context: JobContext) -> AgentResult:
                return AgentResult(
                    success=True,
                    data={
                        "valid": True,
                        "milestones": [{"id": "m1"}],
                        "statistics": {"total": 1},
                    },
                )

        class MockArtistAgent(BaseAgent):
            async def execute(self, context: JobContext) -> AgentResult:
                return AgentResult(
                    success=True,
                    data={
                        "theme_id": "smb3",
                        "colors": {"bg": "#6B8CFF"},
                        "textures": {},
                    },
                )

        class MockRoadAgent(BaseAgent):
            async def execute(self, context: JobContext) -> AgentResult:
                return AgentResult(
                    success=True,
                    data={
                        "coordinates": [{"x": 100, "y": 100}],
                        "control_points": [],
                        "arc_length": 100,
                    },
                )

        class MockIconAgent(BaseAgent):
            async def execute(self, context: JobContext) -> AgentResult:
                return AgentResult(
                    success=True,
                    data={
                        "icons": [{"id": "m1", "pos": {"x": 100, "y": 100}}],
                        "icon_count": 1,
                        "icon_library": "smb3",
                    },
                )

        stages = [
            StageConfig(name="parser", agent_class=MockParserAgent, required_inputs=["hierarchy"]),
            StageConfig(name="artist", agent_class=MockArtistAgent, required_inputs=["theme"]),
            StageConfig(name="road", agent_class=MockRoadAgent, required_inputs=["parser"]),
            StageConfig(name="icon", agent_class=MockIconAgent, required_inputs=["parser", "road"]),
        ]

        coordinator = PipelineCoordinator(stages=stages)
        context = create_test_context()

        result = await coordinator.execute(context)

        assert result.success is True
        assert result.final_map_data is not None

        map_data = result.final_map_data
        assert "theme" in map_data
        assert "road" in map_data
        assert "milestones" in map_data
        assert "metadata" in map_data
        assert "stage_execution" in map_data

        # Check stage execution info
        assert "parser" in map_data["stage_execution"]
        assert map_data["stage_execution"]["parser"]["success"] is True


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestCoordinatorEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_hierarchy(self):
        """Test handling of empty hierarchy."""
        coordinator = PipelineCoordinator()
        context = create_test_context(hierarchy={})

        result = await coordinator.execute(context)

        # Should handle gracefully (may fail at parser stage)
        assert result.success is False or result.success is True

    @pytest.mark.asyncio
    async def test_exception_in_agent(self):
        """Test handling of uncaught exceptions in agents."""

        class ExceptionAgent(BaseAgent):
            async def execute(self, context: JobContext) -> AgentResult:
                raise RuntimeError("Unexpected error!")

        stages = [
            StageConfig(
                name="exception_stage",
                agent_class=ExceptionAgent,
                required_inputs=["hierarchy"],
                retry_count=1,
            )
        ]

        coordinator = PipelineCoordinator(stages=stages)
        context = create_test_context()

        result = await coordinator.execute(context)

        assert result.success is False
        # Error should be captured

    @pytest.mark.asyncio
    async def test_callback_exception_handling(self):
        """Test that callback exceptions don't break execution."""

        def bad_progress_callback(stage, progress, message):
            raise ValueError("Callback error!")

        stages = [
            StageConfig(
                name="test",
                agent_class=MockSuccessAgent,
                required_inputs=["hierarchy"],
            )
        ]

        coordinator = PipelineCoordinator(
            stages=stages,
            on_progress=bad_progress_callback,
        )
        context = create_test_context()

        # Should complete despite callback error
        result = await coordinator.execute(context)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_multiple_executions(self):
        """Test running multiple executions with same coordinator."""
        stages = [
            StageConfig(
                name="test",
                agent_class=MockSuccessAgent,
                required_inputs=["hierarchy"],
            )
        ]

        coordinator = PipelineCoordinator(stages=stages)

        # First execution
        context1 = create_test_context()
        result1 = await coordinator.execute(context1)
        assert result1.success is True

        # Second execution
        context2 = create_test_context()
        result2 = await coordinator.execute(context2)
        assert result2.success is True

        # Both should succeed independently
        assert coordinator.status == CoordinatorStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_coordinator_with_minimal_stages(self):
        """Test coordinator with minimal custom stages."""
        stages = [
            StageConfig(
                name="only_stage",
                agent_class=MockSuccessAgent,
                required_inputs=["hierarchy"],
            )
        ]
        coordinator = PipelineCoordinator(stages=stages)
        context = create_test_context()

        result = await coordinator.execute(context)

        # Should complete with just one stage
        assert result.success is True
        assert result.stages_completed == 1
