"""Pipeline state machine for multi-agent orchestration.

This module provides a robust state machine for managing the pipeline lifecycle:
- Defined states: idle, parsing, generating, rendering, complete, failed
- Transitions with guards and side effects
- State persistence for recovery
- Event-driven execution
"""

import json
import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Optional,
)

from pydantic import BaseModel, Field

from app.agents.base import (
    BaseAgent,
)
from app.agents.messages import (
    AgentRequest,
    ErrorCodes,
    ErrorMessage,
    ProgressUpdate,
)

logger = logging.getLogger(__name__)


class PipelineState(str, Enum):
    """Pipeline execution states."""

    IDLE = "idle"  # Initial state, ready to start
    PARSING = "parsing"  # Parsing document hierarchy
    GENERATING = "generating"  # Generating map layout
    RENDERING = "rendering"  # Rendering visual elements
    COMPLETE = "complete"  # Successfully completed
    FAILED = "failed"  # Failed with error
    CANCELLED = "cancelled"  # Cancelled by user


class PipelineEvent(str, Enum):
    """Events that trigger state transitions."""

    START = "start"  # Start pipeline execution
    PARSE_COMPLETE = "parse_complete"  # Parsing finished
    GENERATE_COMPLETE = "generate_complete"  # Generation finished
    RENDER_COMPLETE = "render_complete"  # Rendering finished
    ERROR = "error"  # Error occurred
    CANCEL = "cancel"  # Cancel requested
    RETRY = "retry"  # Retry after failure
    RESET = "reset"  # Reset to idle


# Type aliases
GuardFunction = Callable[["PipelineContext"], bool]
ActionFunction = Callable[["PipelineContext"], Coroutine[Any, Any, None]]
TransitionCallback = Callable[[PipelineState, PipelineState, "PipelineContext"], None]


@dataclass
class Transition:
    """Definition of a state transition."""

    from_state: PipelineState
    to_state: PipelineState
    event: PipelineEvent
    guards: list[GuardFunction] = field(default_factory=list)
    actions: list[ActionFunction] = field(default_factory=list)


class PipelineContext(BaseModel):
    """Context maintaining pipeline execution state.

    This is persisted to enable recovery and progress tracking.
    """

    # Identity
    job_id: int = Field(..., description="Generation job ID")
    user_id: int = Field(..., description="User ID")

    # State
    current_state: PipelineState = Field(
        default=PipelineState.IDLE, description="Current pipeline state"
    )
    previous_state: Optional[PipelineState] = Field(
        default=None, description="Previous pipeline state"
    )

    # Input data
    document_url: str = Field(default="", description="Document URL")
    hierarchy: dict[str, Any] = Field(default_factory=dict, description="Document hierarchy")
    theme_id: str = Field(default="smb3", description="Theme ID")
    options: dict[str, Any] = Field(default_factory=dict, description="Generation options")

    # Agent checkpoints
    agent_outputs: dict[str, dict[str, Any]] = Field(
        default_factory=dict, description="Outputs from each agent"
    )

    # Progress tracking
    progress_pct: float = Field(default=0.0, description="Overall progress percentage")
    current_agent: Optional[str] = Field(default=None, description="Currently executing agent")

    # Error tracking
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    error_code: Optional[str] = Field(default=None, description="Error code if failed")
    retry_count: int = Field(default=0, description="Number of retries attempted")
    max_retries: int = Field(default=3, description="Maximum retries allowed")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Event history
    event_history: list[dict[str, Any]] = Field(
        default_factory=list, description="History of state transitions"
    )

    class Config:
        """Pydantic config."""

        use_enum_values = True

    def record_event(self, event: PipelineEvent, details: Optional[dict[str, Any]] = None) -> None:
        """Record an event in the history."""
        self.event_history.append(
            {
                "event": event.value,
                "from_state": self.current_state,
                "timestamp": datetime.utcnow().isoformat(),
                "details": details or {},
            }
        )

    def set_agent_output(self, agent_name: str, output: dict[str, Any]) -> None:
        """Store output from an agent."""
        self.agent_outputs[agent_name] = output

    def get_agent_output(self, agent_name: str) -> Optional[dict[str, Any]]:
        """Get stored output from an agent."""
        return self.agent_outputs.get(agent_name)

    def to_checkpoint(self) -> dict[str, Any]:
        """Convert to checkpoint data for persistence."""
        return self.model_dump(mode="json")

    @classmethod
    def from_checkpoint(cls, data: dict[str, Any]) -> "PipelineContext":
        """Restore from checkpoint data."""
        return cls(**data)


class PipelineStateMachine:
    """State machine for managing pipeline execution.

    Features:
    - Explicit state transitions with guards
    - Action hooks on transitions
    - State persistence for recovery
    - Event-driven execution
    """

    # Progress percentages for each state
    STATE_PROGRESS: dict[PipelineState, float] = {
        PipelineState.IDLE: 0.0,
        PipelineState.PARSING: 10.0,
        PipelineState.GENERATING: 40.0,
        PipelineState.RENDERING: 70.0,
        PipelineState.COMPLETE: 100.0,
        PipelineState.FAILED: 0.0,
        PipelineState.CANCELLED: 0.0,
    }

    def __init__(self):
        """Initialize the state machine."""
        self._transitions: list[Transition] = []
        self._on_transition_callbacks: list[TransitionCallback] = []
        self._setup_transitions()

    def _setup_transitions(self) -> None:
        """Set up the state transition table."""
        # IDLE transitions
        self._transitions.append(
            Transition(
                from_state=PipelineState.IDLE,
                to_state=PipelineState.PARSING,
                event=PipelineEvent.START,
                guards=[self._guard_has_hierarchy],
            )
        )

        # PARSING transitions
        self._transitions.append(
            Transition(
                from_state=PipelineState.PARSING,
                to_state=PipelineState.GENERATING,
                event=PipelineEvent.PARSE_COMPLETE,
                guards=[self._guard_parse_successful],
            )
        )
        self._transitions.append(
            Transition(
                from_state=PipelineState.PARSING,
                to_state=PipelineState.FAILED,
                event=PipelineEvent.ERROR,
            )
        )
        self._transitions.append(
            Transition(
                from_state=PipelineState.PARSING,
                to_state=PipelineState.CANCELLED,
                event=PipelineEvent.CANCEL,
            )
        )

        # GENERATING transitions
        self._transitions.append(
            Transition(
                from_state=PipelineState.GENERATING,
                to_state=PipelineState.RENDERING,
                event=PipelineEvent.GENERATE_COMPLETE,
                guards=[self._guard_generate_successful],
            )
        )
        self._transitions.append(
            Transition(
                from_state=PipelineState.GENERATING,
                to_state=PipelineState.FAILED,
                event=PipelineEvent.ERROR,
            )
        )
        self._transitions.append(
            Transition(
                from_state=PipelineState.GENERATING,
                to_state=PipelineState.CANCELLED,
                event=PipelineEvent.CANCEL,
            )
        )

        # RENDERING transitions
        self._transitions.append(
            Transition(
                from_state=PipelineState.RENDERING,
                to_state=PipelineState.COMPLETE,
                event=PipelineEvent.RENDER_COMPLETE,
                guards=[self._guard_render_successful],
            )
        )
        self._transitions.append(
            Transition(
                from_state=PipelineState.RENDERING,
                to_state=PipelineState.FAILED,
                event=PipelineEvent.ERROR,
            )
        )
        self._transitions.append(
            Transition(
                from_state=PipelineState.RENDERING,
                to_state=PipelineState.CANCELLED,
                event=PipelineEvent.CANCEL,
            )
        )

        # FAILED transitions
        self._transitions.append(
            Transition(
                from_state=PipelineState.FAILED,
                to_state=PipelineState.PARSING,
                event=PipelineEvent.RETRY,
                guards=[self._guard_can_retry],
            )
        )
        self._transitions.append(
            Transition(
                from_state=PipelineState.FAILED,
                to_state=PipelineState.IDLE,
                event=PipelineEvent.RESET,
            )
        )

        # CANCELLED transitions
        self._transitions.append(
            Transition(
                from_state=PipelineState.CANCELLED,
                to_state=PipelineState.IDLE,
                event=PipelineEvent.RESET,
            )
        )

        # COMPLETE transitions
        self._transitions.append(
            Transition(
                from_state=PipelineState.COMPLETE,
                to_state=PipelineState.IDLE,
                event=PipelineEvent.RESET,
            )
        )

    # --------------------------------------------------------------------------
    # Guard functions
    # --------------------------------------------------------------------------

    def _guard_has_hierarchy(self, ctx: PipelineContext) -> bool:
        """Guard: Check that hierarchy data is present."""
        return bool(ctx.hierarchy)

    def _guard_parse_successful(self, ctx: PipelineContext) -> bool:
        """Guard: Check that parsing completed successfully."""
        parser_output = ctx.get_agent_output("parser")
        return parser_output is not None and parser_output.get("valid", False)

    def _guard_generate_successful(self, ctx: PipelineContext) -> bool:
        """Guard: Check that generation completed successfully."""
        # Check both artist and road agents
        artist_output = ctx.get_agent_output("artist")
        road_output = ctx.get_agent_output("road")
        return artist_output is not None and road_output is not None

    def _guard_render_successful(self, ctx: PipelineContext) -> bool:
        """Guard: Check that rendering completed successfully."""
        icon_output = ctx.get_agent_output("icon")
        return icon_output is not None

    def _guard_can_retry(self, ctx: PipelineContext) -> bool:
        """Guard: Check that retry is allowed."""
        return ctx.retry_count < ctx.max_retries

    # --------------------------------------------------------------------------
    # Transition methods
    # --------------------------------------------------------------------------

    def get_valid_transitions(
        self, current_state: PipelineState
    ) -> list[tuple[PipelineEvent, PipelineState]]:
        """Get list of valid transitions from current state."""
        valid = []
        for t in self._transitions:
            if t.from_state == current_state:
                valid.append((t.event, t.to_state))
        return valid

    def can_transition(
        self, ctx: PipelineContext, event: PipelineEvent
    ) -> tuple[bool, Optional[str]]:
        """Check if a transition is valid.

        Returns:
            Tuple of (can_transition, reason_if_not)
        """
        current_state = PipelineState(ctx.current_state)

        # Find matching transition
        for t in self._transitions:
            if t.from_state == current_state and t.event == event:
                # Check guards
                for guard in t.guards:
                    if not guard(ctx):
                        return False, f"Guard {guard.__name__} failed"
                return True, None

        return False, f"No transition for event {event} from state {current_state}"

    async def transition(
        self, ctx: PipelineContext, event: PipelineEvent
    ) -> tuple[bool, Optional[str]]:
        """Attempt a state transition.

        Args:
            ctx: Pipeline context
            event: Event triggering the transition

        Returns:
            Tuple of (success, error_message)
        """
        current_state = PipelineState(ctx.current_state)

        # Find matching transition
        for t in self._transitions:
            if t.from_state == current_state and t.event == event:
                # Check guards
                for guard in t.guards:
                    if not guard(ctx):
                        logger.warning(
                            f"Transition blocked by guard {guard.__name__}: "
                            f"{current_state} -> {t.to_state}"
                        )
                        return False, f"Guard {guard.__name__} failed"

                # Record event
                ctx.record_event(event, {"to_state": t.to_state.value})

                # Update state
                ctx.previous_state = current_state
                ctx.current_state = t.to_state

                # Update progress
                ctx.progress_pct = self.STATE_PROGRESS.get(t.to_state, ctx.progress_pct)

                # Update timestamps
                if t.to_state == PipelineState.PARSING and ctx.started_at is None:
                    ctx.started_at = datetime.utcnow()
                elif t.to_state in (
                    PipelineState.COMPLETE,
                    PipelineState.FAILED,
                    PipelineState.CANCELLED,
                ):
                    ctx.completed_at = datetime.utcnow()

                # Execute actions
                for action in t.actions:
                    try:
                        await action(ctx)
                    except Exception as e:
                        logger.error(f"Transition action failed: {e}")

                # Notify callbacks
                for callback in self._on_transition_callbacks:
                    try:
                        callback(current_state, t.to_state, ctx)
                    except Exception as e:
                        logger.error(f"Transition callback failed: {e}")

                logger.info(
                    f"Pipeline transition: {current_state.value} -> {t.to_state.value} "
                    f"(event: {event.value}, job_id: {ctx.job_id})"
                )

                return True, None

        logger.warning(
            f"Invalid transition: no handler for event {event} "
            f"from state {current_state}"
        )
        return False, f"No transition for event {event} from state {current_state}"

    def on_transition(self, callback: TransitionCallback) -> None:
        """Register a callback for state transitions."""
        self._on_transition_callbacks.append(callback)


class PipelineStage(BaseModel):
    """Configuration for a pipeline stage."""

    name: str = Field(..., description="Stage name")
    agent_name: str = Field(..., description="Agent to execute")
    state: PipelineState = Field(..., description="Pipeline state for this stage")
    complete_event: PipelineEvent = Field(..., description="Event when stage completes")
    progress_weight: float = Field(default=1.0, description="Weight for progress calculation")


class Pipeline:
    """High-level pipeline orchestrator.

    Combines the state machine with agent execution to provide
    a complete pipeline management solution.
    """

    # Default pipeline stages
    DEFAULT_STAGES: list[PipelineStage] = [
        PipelineStage(
            name="parsing",
            agent_name="parser",
            state=PipelineState.PARSING,
            complete_event=PipelineEvent.PARSE_COMPLETE,
            progress_weight=0.1,
        ),
        PipelineStage(
            name="artist",
            agent_name="artist",
            state=PipelineState.GENERATING,
            complete_event=PipelineEvent.GENERATE_COMPLETE,
            progress_weight=0.3,
        ),
        PipelineStage(
            name="road",
            agent_name="road",
            state=PipelineState.GENERATING,
            complete_event=PipelineEvent.GENERATE_COMPLETE,
            progress_weight=0.3,
        ),
        PipelineStage(
            name="icon",
            agent_name="icon",
            state=PipelineState.RENDERING,
            complete_event=PipelineEvent.RENDER_COMPLETE,
            progress_weight=0.3,
        ),
    ]

    def __init__(
        self,
        agents: dict[str, BaseAgent],
        stages: Optional[list[PipelineStage]] = None,
        on_progress: Optional[Callable[[ProgressUpdate], None]] = None,
        on_error: Optional[Callable[[ErrorMessage], None]] = None,
    ):
        """Initialize the pipeline.

        Args:
            agents: Dictionary mapping agent names to agent instances
            stages: Pipeline stages (uses default if not provided)
            on_progress: Progress callback
            on_error: Error callback
        """
        self.agents = agents
        self.stages = stages or self.DEFAULT_STAGES
        self.state_machine = PipelineStateMachine()

        self._on_progress = on_progress
        self._on_error = on_error
        self._cancelled = False

    async def execute(self, ctx: PipelineContext) -> PipelineContext:
        """Execute the full pipeline.

        Args:
            ctx: Pipeline context with input data

        Returns:
            Updated pipeline context with results
        """
        self._cancelled = False

        # Start the pipeline
        success, error = await self.state_machine.transition(ctx, PipelineEvent.START)
        if not success:
            ctx.error_message = error
            ctx.error_code = ErrorCodes.PIPELINE_STATE_INVALID
            await self.state_machine.transition(ctx, PipelineEvent.ERROR)
            return ctx

        # Execute stages
        try:
            await self._execute_stages(ctx)
        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}")
            ctx.error_message = str(e)
            ctx.error_code = ErrorCodes.PROCESSING_FAILED
            await self.state_machine.transition(ctx, PipelineEvent.ERROR)

        return ctx

    async def _execute_stages(self, ctx: PipelineContext) -> None:
        """Execute all pipeline stages."""
        stage_groups = self._group_stages_by_state()

        for state, stages in stage_groups.items():
            if self._cancelled:
                await self.state_machine.transition(ctx, PipelineEvent.CANCEL)
                return

            # Execute all agents in this stage group
            for stage in stages:
                if self._cancelled:
                    break

                ctx.current_agent = stage.agent_name
                self._report_progress(ctx, f"Running {stage.name}")

                agent = self.agents.get(stage.agent_name)
                if agent is None:
                    raise RuntimeError(f"Agent not found: {stage.agent_name}")

                # Build request
                request = AgentRequest(
                    source_agent="pipeline",
                    target_agent=stage.agent_name,
                    job_id=ctx.job_id,
                    input_data={
                        "hierarchy": ctx.hierarchy,
                        "theme_id": ctx.theme_id,
                        "options": ctx.options,
                        "agent_outputs": ctx.agent_outputs,
                    },
                    context=ctx.agent_outputs,
                )

                # Execute agent
                response = await agent.run(
                    request,
                    on_progress=self._on_progress,
                    on_error=self._on_error,
                )

                if not response.success:
                    raise RuntimeError(
                        f"Agent {stage.agent_name} failed: "
                        f"{response.output_data.get('error', 'Unknown error')}"
                    )

                # Store output
                ctx.set_agent_output(stage.agent_name, response.output_data or {})

            # Transition after completing stage group
            if stages:
                complete_event = stages[-1].complete_event
                success, error = await self.state_machine.transition(ctx, complete_event)
                if not success:
                    raise RuntimeError(f"State transition failed: {error}")

        ctx.current_agent = None

    def _group_stages_by_state(self) -> dict[PipelineState, list[PipelineStage]]:
        """Group stages by their pipeline state."""
        groups: dict[PipelineState, list[PipelineStage]] = {}
        for stage in self.stages:
            if stage.state not in groups:
                groups[stage.state] = []
            groups[stage.state].append(stage)
        return groups

    def _report_progress(self, ctx: PipelineContext, message: str) -> None:
        """Report progress update."""
        if self._on_progress:
            update = ProgressUpdate(
                source_agent="pipeline",
                job_id=ctx.job_id,
                progress_pct=ctx.progress_pct,
                stage=ctx.current_state,
                message=message,
            )
            self._on_progress(update)

    def cancel(self) -> None:
        """Request pipeline cancellation."""
        self._cancelled = True
        logger.info("Pipeline cancellation requested")

    @staticmethod
    def create_context(
        job_id: int,
        user_id: int,
        hierarchy: dict[str, Any],
        theme_id: str = "smb3",
        options: Optional[dict[str, Any]] = None,
        document_url: str = "",
    ) -> PipelineContext:
        """Create a new pipeline context.

        Args:
            job_id: Generation job ID
            user_id: User ID
            hierarchy: Document hierarchy data
            theme_id: Theme ID
            options: Generation options
            document_url: Document URL

        Returns:
            Initialized pipeline context
        """
        return PipelineContext(
            job_id=job_id,
            user_id=user_id,
            document_url=document_url,
            hierarchy=hierarchy,
            theme_id=theme_id,
            options=options or {},
        )


class PipelineStateRepository:
    """Repository for persisting pipeline state.

    Provides methods for saving and loading pipeline state,
    enabling recovery from failures.
    """

    def __init__(self, redis_client=None):
        """Initialize the repository.

        Args:
            redis_client: Redis client for persistence (optional)
        """
        self._redis = redis_client
        self._local_cache: dict[int, PipelineContext] = {}

    async def save(self, ctx: PipelineContext) -> None:
        """Save pipeline context.

        Args:
            ctx: Pipeline context to save
        """
        checkpoint = ctx.to_checkpoint()

        # Save to local cache
        self._local_cache[ctx.job_id] = ctx

        # Save to Redis if available
        if self._redis:
            key = f"pipeline:state:{ctx.job_id}"
            await self._redis.set(key, json.dumps(checkpoint), ex=86400)  # 24hr TTL

        logger.debug(f"Pipeline state saved for job {ctx.job_id}")

    async def load(self, job_id: int) -> Optional[PipelineContext]:
        """Load pipeline context.

        Args:
            job_id: Job ID to load

        Returns:
            Pipeline context if found, None otherwise
        """
        # Try local cache first
        if job_id in self._local_cache:
            return self._local_cache[job_id]

        # Try Redis
        if self._redis:
            key = f"pipeline:state:{job_id}"
            data = await self._redis.get(key)
            if data:
                checkpoint = json.loads(data)
                ctx = PipelineContext.from_checkpoint(checkpoint)
                self._local_cache[job_id] = ctx
                return ctx

        return None

    async def delete(self, job_id: int) -> None:
        """Delete pipeline context.

        Args:
            job_id: Job ID to delete
        """
        # Remove from local cache
        self._local_cache.pop(job_id, None)

        # Remove from Redis
        if self._redis:
            key = f"pipeline:state:{job_id}"
            await self._redis.delete(key)

        logger.debug(f"Pipeline state deleted for job {job_id}")

    def get_active_jobs(self) -> list[int]:
        """Get list of jobs with active pipeline state."""
        active = []
        for job_id, ctx in self._local_cache.items():
            if ctx.current_state not in (
                PipelineState.COMPLETE,
                PipelineState.FAILED,
                PipelineState.CANCELLED,
            ):
                active.append(job_id)
        return active
