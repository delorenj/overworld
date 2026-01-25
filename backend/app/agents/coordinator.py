"""Pipeline Coordinator for multi-agent orchestration.

This module provides a robust coordinator for orchestrating the multi-agent
pipeline with features including:
- Sequential agent execution with dependency management
- Progress tracking and reporting
- Error handling with recovery options
- Integration with the pipeline state machine
- Checkpointing for fault tolerance
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from app.agents.artist_agent import ArtistAgent
from app.agents.base_agent import AgentResult, BaseAgent, JobContext
from app.agents.icon_agent import IconAgent
from app.agents.parser_agent import ParserAgent
from app.agents.pipeline import (
    Pipeline,
    PipelineContext,
    PipelineEvent,
    PipelineState,
    PipelineStateMachine,
)
from app.agents.road_agent import RoadAgent

logger = logging.getLogger(__name__)


class CoordinatorStatus(str, Enum):
    """Coordinator execution status."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class StageConfig:
    """Configuration for a pipeline stage.

    Attributes:
        name: Stage identifier
        agent_class: Agent class to instantiate
        required_inputs: List of required input keys from previous stages
        optional_inputs: List of optional input keys
        timeout_seconds: Maximum execution time for this stage
        retry_count: Number of retries on failure
    """

    name: str
    agent_class: type[BaseAgent]
    required_inputs: list[str] = field(default_factory=list)
    optional_inputs: list[str] = field(default_factory=list)
    timeout_seconds: int = 120
    retry_count: int = 3


@dataclass
class StageResult:
    """Result from a single stage execution.

    Attributes:
        stage_name: Name of the stage
        success: Whether the stage succeeded
        data: Output data from the stage
        error: Error message if failed
        execution_time_ms: Time taken in milliseconds
        retry_attempts: Number of retry attempts made
    """

    stage_name: str
    success: bool
    data: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: int = 0
    retry_attempts: int = 0


@dataclass
class CoordinatorResult:
    """Result from the full pipeline execution.

    Attributes:
        success: Whether the full pipeline succeeded
        final_map_data: The assembled map data
        stage_results: Results from each stage
        total_execution_time_ms: Total time taken
        stages_completed: Number of stages completed
        error: Error message if failed
    """

    success: bool
    final_map_data: Optional[dict[str, Any]] = None
    stage_results: list[StageResult] = field(default_factory=list)
    total_execution_time_ms: int = 0
    stages_completed: int = 0
    error: Optional[str] = None


# Type aliases for callbacks
ProgressCallback = Callable[[str, float, str], None]  # (stage, progress, message)
ErrorCallback = Callable[[str, str, bool], None]  # (stage, error, recoverable)


class PipelineCoordinator:
    """Orchestrates the multi-agent pipeline with enhanced features.

    This coordinator manages the execution of multiple agents in sequence,
    handling:
    - Progress reporting via callbacks
    - Error handling with configurable retry logic
    - State checkpointing for fault tolerance
    - Integration with the pipeline state machine

    Usage:
        coordinator = PipelineCoordinator()
        result = await coordinator.execute(context)

        # Or with callbacks:
        coordinator = PipelineCoordinator(
            on_progress=lambda stage, pct, msg: print(f"{stage}: {pct}% - {msg}"),
            on_error=lambda stage, err, rec: print(f"Error in {stage}: {err}"),
        )
    """

    # Default pipeline stages in execution order
    DEFAULT_STAGES: list[StageConfig] = [
        StageConfig(
            name="parser",
            agent_class=ParserAgent,
            required_inputs=["hierarchy"],
            timeout_seconds=30,
        ),
        StageConfig(
            name="artist",
            agent_class=ArtistAgent,
            required_inputs=["theme"],
            optional_inputs=["parser"],
            timeout_seconds=30,
        ),
        StageConfig(
            name="road",
            agent_class=RoadAgent,
            required_inputs=["parser"],
            timeout_seconds=60,
        ),
        StageConfig(
            name="icon",
            agent_class=IconAgent,
            required_inputs=["parser", "road"],
            optional_inputs=["artist"],
            timeout_seconds=60,
        ),
    ]

    def __init__(
        self,
        stages: Optional[list[StageConfig]] = None,
        on_progress: Optional[ProgressCallback] = None,
        on_error: Optional[ErrorCallback] = None,
        enable_checkpointing: bool = True,
    ):
        """Initialize the PipelineCoordinator.

        Args:
            stages: Custom stage configuration (uses defaults if None)
            on_progress: Callback for progress updates
            on_error: Callback for error notifications
            enable_checkpointing: Enable state checkpointing
        """
        self.stages = stages or self.DEFAULT_STAGES
        self._on_progress = on_progress
        self._on_error = on_error
        self._enable_checkpointing = enable_checkpointing

        self.status = CoordinatorStatus.IDLE
        self._cancelled = False
        self._current_stage: Optional[str] = None
        self._stage_results: dict[str, StageResult] = {}
        self._agents: dict[str, BaseAgent] = {}

    async def execute(self, context: JobContext) -> CoordinatorResult:
        """Execute the full pipeline.

        Runs all configured stages in sequence, handling errors and
        reporting progress.

        Args:
            context: Job context with input data and shared state

        Returns:
            CoordinatorResult with pipeline outcome
        """
        self.status = CoordinatorStatus.RUNNING
        self._cancelled = False
        self._stage_results = {}
        start_time = time.time()

        logger.info(
            f"PipelineCoordinator: Starting execution for job {context.job_id} "
            f"with {len(self.stages)} stages"
        )

        try:
            # Initialize all agents
            self._initialize_agents()

            # Execute stages in order
            for i, stage_config in enumerate(self.stages):
                if self._cancelled:
                    self.status = CoordinatorStatus.CANCELLED
                    return self._create_result(
                        success=False,
                        error="Pipeline cancelled",
                        start_time=start_time,
                    )

                self._current_stage = stage_config.name
                stage_progress = (i / len(self.stages)) * 100

                self._report_progress(
                    stage_config.name,
                    stage_progress,
                    f"Starting {stage_config.name} stage",
                )

                # Validate required inputs
                if not self._validate_inputs(stage_config, context):
                    error_msg = f"Missing required inputs for stage {stage_config.name}"
                    self._report_error(stage_config.name, error_msg, recoverable=False)
                    self.status = CoordinatorStatus.FAILED
                    return self._create_result(
                        success=False,
                        error=error_msg,
                        start_time=start_time,
                    )

                # Execute the stage with retry logic
                stage_result = await self._execute_stage(stage_config, context)
                self._stage_results[stage_config.name] = stage_result

                if not stage_result.success:
                    self._report_error(
                        stage_config.name,
                        stage_result.error or "Unknown error",
                        recoverable=False,
                    )
                    self.status = CoordinatorStatus.FAILED
                    return self._create_result(
                        success=False,
                        error=f"Stage '{stage_config.name}' failed: {stage_result.error}",
                        start_time=start_time,
                    )

                # Save checkpoint
                if stage_result.data:
                    context.save_checkpoint(stage_config.name, stage_result.data)

                self._report_progress(
                    stage_config.name,
                    ((i + 1) / len(self.stages)) * 100,
                    f"Completed {stage_config.name} stage",
                )

            # Assemble final map data
            final_map_data = self._assemble_final_map(context)

            self.status = CoordinatorStatus.COMPLETED
            self._current_stage = None

            logger.info(
                f"PipelineCoordinator: Successfully completed all stages "
                f"for job {context.job_id}"
            )

            return self._create_result(
                success=True,
                final_map_data=final_map_data,
                start_time=start_time,
            )

        except Exception as e:
            logger.error(
                f"PipelineCoordinator: Unexpected error for job {context.job_id}: {e}"
            )
            self.status = CoordinatorStatus.FAILED
            return self._create_result(
                success=False,
                error=f"Coordinator failed: {str(e)}",
                start_time=start_time,
            )

    def _initialize_agents(self) -> None:
        """Initialize agent instances for all stages."""
        self._agents = {}
        for stage_config in self.stages:
            self._agents[stage_config.name] = stage_config.agent_class()

    def _validate_inputs(self, stage_config: StageConfig, context: JobContext) -> bool:
        """Validate that required inputs are available for a stage.

        Args:
            stage_config: Stage configuration
            context: Job context

        Returns:
            True if all required inputs are available
        """
        for required_input in stage_config.required_inputs:
            # Check if it's from context or from a previous stage
            if required_input == "hierarchy":
                if not context.hierarchy:
                    logger.warning(f"Missing required input: hierarchy")
                    return False
            elif required_input == "theme":
                if not context.theme:
                    logger.warning(f"Missing required input: theme")
                    return False
            else:
                # Check in agent state (from previous stages)
                checkpoint = context.get_checkpoint(required_input)
                if checkpoint is None:
                    logger.warning(f"Missing required input from stage: {required_input}")
                    return False

        return True

    async def _execute_stage(
        self, stage_config: StageConfig, context: JobContext
    ) -> StageResult:
        """Execute a single stage with retry logic.

        Args:
            stage_config: Stage configuration
            context: Job context

        Returns:
            StageResult with execution outcome
        """
        agent = self._agents.get(stage_config.name)
        if agent is None:
            return StageResult(
                stage_name=stage_config.name,
                success=False,
                error=f"Agent not initialized for stage {stage_config.name}",
            )

        start_time = time.time()
        last_error: Optional[str] = None
        attempts = 0

        for attempt in range(stage_config.retry_count):
            attempts = attempt + 1

            if self._cancelled:
                return StageResult(
                    stage_name=stage_config.name,
                    success=False,
                    error="Cancelled",
                    retry_attempts=attempts,
                )

            try:
                logger.info(
                    f"PipelineCoordinator: Executing stage '{stage_config.name}' "
                    f"(attempt {attempts}/{stage_config.retry_count})"
                )

                result = await agent.run(context)
                execution_time_ms = int((time.time() - start_time) * 1000)

                if result.success:
                    return StageResult(
                        stage_name=stage_config.name,
                        success=True,
                        data=result.data,
                        execution_time_ms=execution_time_ms,
                        retry_attempts=attempts,
                    )
                else:
                    last_error = result.error
                    logger.warning(
                        f"Stage '{stage_config.name}' failed (attempt {attempts}): {last_error}"
                    )

                    # Report recoverable error for retry
                    if attempt < stage_config.retry_count - 1:
                        self._report_error(
                            stage_config.name,
                            last_error or "Unknown error",
                            recoverable=True,
                        )

            except Exception as e:
                last_error = str(e)
                logger.error(
                    f"Stage '{stage_config.name}' threw exception (attempt {attempts}): {e}"
                )

        # All retries exhausted
        execution_time_ms = int((time.time() - start_time) * 1000)
        return StageResult(
            stage_name=stage_config.name,
            success=False,
            error=last_error,
            execution_time_ms=execution_time_ms,
            retry_attempts=attempts,
        )

    def _assemble_final_map(self, context: JobContext) -> dict[str, Any]:
        """Assemble final map data from all stage outputs.

        Args:
            context: Job context with all checkpoints

        Returns:
            Complete map data dictionary
        """
        parser_data = context.get_checkpoint("parser") or {}
        artist_data = context.get_checkpoint("artist") or {}
        road_data = context.get_checkpoint("road") or {}
        icon_data = context.get_checkpoint("icon") or {}

        return {
            "version": "1.0.0",
            "theme": {
                "theme_id": artist_data.get("theme_id", "smb3"),
                "colors": artist_data.get("colors", {}),
                "textures": artist_data.get("textures", {}),
            },
            "road": {
                "coordinates": road_data.get("coordinates", []),
                "control_points": road_data.get("control_points", []),
                "arc_length": road_data.get("arc_length", 0),
            },
            "milestones": icon_data.get("icons", []),
            "metadata": {
                "source_hierarchy": parser_data.get("statistics", {}),
                "milestone_count": icon_data.get("icon_count", 0),
                "road_arc_length": road_data.get("arc_length", 0),
                "icon_library": icon_data.get("icon_library", "default"),
                "placement_stats": {
                    "collisions_avoided": icon_data.get("collisions_avoided", 0),
                    "boundary_adjustments": icon_data.get("boundary_adjustments", 0),
                },
            },
            "stage_execution": {
                stage_name: {
                    "success": result.success,
                    "execution_time_ms": result.execution_time_ms,
                    "retry_attempts": result.retry_attempts,
                }
                for stage_name, result in self._stage_results.items()
            },
        }

    def _create_result(
        self,
        success: bool,
        error: Optional[str] = None,
        final_map_data: Optional[dict[str, Any]] = None,
        start_time: float = 0,
    ) -> CoordinatorResult:
        """Create a coordinator result.

        Args:
            success: Whether the pipeline succeeded
            error: Error message if failed
            final_map_data: Assembled map data
            start_time: Pipeline start time

        Returns:
            CoordinatorResult
        """
        total_time_ms = int((time.time() - start_time) * 1000) if start_time else 0
        stage_results = list(self._stage_results.values())
        stages_completed = sum(1 for r in stage_results if r.success)

        return CoordinatorResult(
            success=success,
            final_map_data=final_map_data,
            stage_results=stage_results,
            total_execution_time_ms=total_time_ms,
            stages_completed=stages_completed,
            error=error,
        )

    def _report_progress(self, stage: str, progress: float, message: str) -> None:
        """Report progress via callback.

        Args:
            stage: Current stage name
            progress: Progress percentage (0-100)
            message: Progress message
        """
        if self._on_progress:
            try:
                self._on_progress(stage, progress, message)
            except Exception as e:
                logger.error(f"Progress callback error: {e}")

    def _report_error(self, stage: str, error: str, recoverable: bool) -> None:
        """Report error via callback.

        Args:
            stage: Stage where error occurred
            error: Error message
            recoverable: Whether the error is recoverable
        """
        if self._on_error:
            try:
                self._on_error(stage, error, recoverable)
            except Exception as e:
                logger.error(f"Error callback error: {e}")

    def cancel(self) -> None:
        """Request cancellation of the pipeline."""
        logger.info("PipelineCoordinator: Cancellation requested")
        self._cancelled = True
        self.status = CoordinatorStatus.CANCELLED

    def get_current_stage(self) -> Optional[str]:
        """Get the currently executing stage."""
        return self._current_stage

    def get_status(self) -> CoordinatorStatus:
        """Get the coordinator status."""
        return self.status

    def get_stage_result(self, stage_name: str) -> Optional[StageResult]:
        """Get the result for a specific stage.

        Args:
            stage_name: Name of the stage

        Returns:
            StageResult if available, None otherwise
        """
        return self._stage_results.get(stage_name)


class CoordinatorAgent(BaseAgent):
    """Legacy-compatible coordinator agent.

    Wraps the PipelineCoordinator to provide the BaseAgent interface
    for backward compatibility with existing code.

    This agent orchestrates the full multi-agent pipeline using the
    enhanced PipelineCoordinator.
    """

    def __init__(self):
        """Initialize the CoordinatorAgent."""
        super().__init__()
        self.coordinator: Optional[PipelineCoordinator] = None
        self._last_result: Optional[CoordinatorResult] = None

    async def execute(self, context: JobContext) -> AgentResult:
        """Execute the full pipeline with sequential agent coordination.

        Args:
            context: Job context with input data

        Returns:
            AgentResult with final map data
        """
        try:
            # Create coordinator with progress logging
            self.coordinator = PipelineCoordinator(
                on_progress=self._log_progress,
                on_error=self._log_error,
            )

            # Execute the pipeline
            result = await self.coordinator.execute(context)
            self._last_result = result

            if not result.success:
                return AgentResult(
                    success=False,
                    error=result.error,
                )

            return AgentResult(
                success=True,
                data=result.final_map_data,
            )

        except Exception as e:
            logger.error(f"CoordinatorAgent: Execution failed - {str(e)}")
            return AgentResult(
                success=False,
                error=f"Coordinator failed: {str(e)}",
            )

    def _log_progress(self, stage: str, progress: float, message: str) -> None:
        """Log progress updates.

        Args:
            stage: Current stage
            progress: Progress percentage
            message: Progress message
        """
        logger.info(f"Progress [{stage}]: {progress:.1f}% - {message}")

    def _log_error(self, stage: str, error: str, recoverable: bool) -> None:
        """Log error notifications.

        Args:
            stage: Stage with error
            error: Error message
            recoverable: Whether error is recoverable
        """
        if recoverable:
            logger.warning(f"Recoverable error in {stage}: {error}")
        else:
            logger.error(f"Fatal error in {stage}: {error}")

    def get_last_result(self) -> Optional[CoordinatorResult]:
        """Get the last pipeline execution result.

        Returns:
            CoordinatorResult from the last execution
        """
        return self._last_result

    def cancel(self) -> None:
        """Cancel the current pipeline execution."""
        if self.coordinator:
            self.coordinator.cancel()
