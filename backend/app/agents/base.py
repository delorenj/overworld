"""Enhanced base agent framework for multi-agent pipeline.

This module provides a robust foundation for building agents with:
- Typed input/output definitions
- Error handling hooks
- Progress reporting callbacks
- Lifecycle management
- LLM integration
"""

import logging
import time
import traceback
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    ClassVar,
    Generic,
    Optional,
    TypeVar,
)

from pydantic import BaseModel, Field

from app.agents.llm_client import (
    ChatMessage,
    LLMResponse,
    OpenRouterClient,
    get_llm_client,
)
from app.agents.messages import (
    AgentRequest,
    AgentResponse,
    ErrorCodes,
    ErrorMessage,
    ErrorSeverity,
    ProgressUpdate,
)

logger = logging.getLogger(__name__)


# Type variables for generic input/output
InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class AgentStatus(str, Enum):
    """Agent lifecycle status."""

    IDLE = "idle"  # Ready to accept work
    INITIALIZING = "initializing"  # Setting up
    PROCESSING = "processing"  # Actively processing
    PAUSED = "paused"  # Temporarily paused
    ERROR = "error"  # In error state
    SHUTDOWN = "shutdown"  # Shutting down


class AgentCapability(str, Enum):
    """Capabilities that an agent can declare."""

    LLM_CALLS = "llm_calls"  # Can make LLM calls
    STREAMING = "streaming"  # Supports streaming output
    CHECKPOINTING = "checkpointing"  # Supports state checkpointing
    CANCELLATION = "cancellation"  # Supports graceful cancellation
    PARALLEL = "parallel"  # Can process multiple requests in parallel


class AgentInput(BaseModel):
    """Base class for agent input data.

    Subclass this to define typed input for your agent.
    """

    job_id: int = Field(..., description="Generation job ID")
    context: dict[str, Any] = Field(
        default_factory=dict, description="Context from previous agents"
    )


class AgentOutput(BaseModel):
    """Base class for agent output data.

    Subclass this to define typed output for your agent.
    """

    success: bool = Field(..., description="Whether processing succeeded")
    data: dict[str, Any] = Field(default_factory=dict, description="Output data")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")


class AgentMetrics(BaseModel):
    """Metrics collected during agent execution."""

    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    execution_time_ms: int = 0
    tokens_used: int = 0
    llm_calls: int = 0
    llm_latency_ms: int = 0
    checkpoints_saved: int = 0
    errors_encountered: int = 0


class AgentConfig(BaseModel):
    """Configuration for an agent instance."""

    name: str = Field(..., description="Agent name")
    version: str = Field(default="1.0.0", description="Agent version")
    default_model: str = Field(
        default="claude-3-5-sonnet", description="Default LLM model"
    )
    temperature: float = Field(default=0.7, description="Default temperature")
    timeout_seconds: int = Field(default=120, description="Processing timeout")
    max_retries: int = Field(default=3, description="Maximum retries on failure")
    capabilities: list[AgentCapability] = Field(
        default_factory=list, description="Agent capabilities"
    )


# Callback type definitions
ProgressCallback = Callable[[ProgressUpdate], None]
ErrorCallback = Callable[[ErrorMessage], None]


@dataclass
class ExecutionContext:
    """Context passed to agent during execution.

    Provides access to shared state, callbacks, and utilities.
    """

    job_id: int
    user_id: int
    request: AgentRequest
    agent_state: dict[str, Any] = field(default_factory=dict)

    # Callbacks
    on_progress: Optional[ProgressCallback] = None
    on_error: Optional[ErrorCallback] = None

    # Execution tracking
    start_time: float = field(default_factory=time.time)
    cancelled: bool = False

    def get_checkpoint(self, agent_name: str) -> Optional[dict[str, Any]]:
        """Get checkpoint for a specific agent."""
        return self.agent_state.get(agent_name)

    def save_checkpoint(self, agent_name: str, state: dict[str, Any]) -> None:
        """Save checkpoint for a specific agent."""
        self.agent_state[agent_name] = state

    def report_progress(
        self,
        agent_name: str,
        progress_pct: float,
        stage: str,
        message: Optional[str] = None,
        stage_progress_pct: float = 0.0,
    ) -> None:
        """Report progress update."""
        if self.on_progress:
            update = ProgressUpdate(
                source_agent=agent_name,
                job_id=self.job_id,
                progress_pct=progress_pct,
                stage=stage,
                stage_progress_pct=stage_progress_pct,
                message=message,
            )
            self.on_progress(update)

    def report_error(
        self,
        agent_name: str,
        error_code: str,
        error_message: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        recoverable: bool = False,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Report an error."""
        if self.on_error:
            error = ErrorMessage(
                source_agent=agent_name,
                job_id=self.job_id,
                severity=severity,
                error_code=error_code,
                error_message=error_message,
                error_details=details,
                recoverable=recoverable,
            )
            self.on_error(error)

    def elapsed_ms(self) -> int:
        """Get elapsed time in milliseconds."""
        return int((time.time() - self.start_time) * 1000)

    def is_cancelled(self) -> bool:
        """Check if execution has been cancelled."""
        return self.cancelled

    def request_cancellation(self) -> None:
        """Request cancellation of execution."""
        self.cancelled = True


class BaseAgent(ABC, Generic[InputT, OutputT]):
    """Enhanced base agent class for multi-agent pipeline.

    Provides:
    - Typed input/output through generics
    - Lifecycle hooks (on_start, on_complete, on_error)
    - Progress reporting
    - LLM integration with the OpenRouter client
    - Metrics collection
    - Graceful cancellation support

    Usage:
        class MyAgent(BaseAgent[MyInput, MyOutput]):
            input_type = MyInput
            output_type = MyOutput

            async def process(self, input_data: MyInput, ctx: ExecutionContext) -> MyOutput:
                # Your processing logic here
                return MyOutput(success=True, data={...})
    """

    # Class-level type hints (override in subclass)
    input_type: ClassVar[type[BaseModel]] = AgentInput
    output_type: ClassVar[type[BaseModel]] = AgentOutput

    # Default configuration (override in subclass)
    default_config: ClassVar[AgentConfig] = AgentConfig(name="BaseAgent")

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        llm_client: Optional[OpenRouterClient] = None,
    ):
        """Initialize the agent.

        Args:
            config: Agent configuration (uses default_config if not provided)
            llm_client: LLM client instance (uses global client if not provided)
        """
        self.config = config or self.default_config
        self.name = self.config.name
        self.status = AgentStatus.IDLE
        self.metrics = AgentMetrics()

        # LLM client
        self._llm_client = llm_client

        # Internal state
        self._current_context: Optional[ExecutionContext] = None

        logger.info(f"Agent {self.name} initialized (v{self.config.version})")

    @property
    def llm_client(self) -> OpenRouterClient:
        """Get the LLM client, initializing if needed."""
        if self._llm_client is None:
            self._llm_client = get_llm_client()
        return self._llm_client

    # --------------------------------------------------------------------------
    # Abstract methods (must be implemented by subclasses)
    # --------------------------------------------------------------------------

    @abstractmethod
    async def process(self, input_data: InputT, ctx: ExecutionContext) -> OutputT:
        """Process input data and return output.

        This is the main processing method that subclasses must implement.

        Args:
            input_data: Validated input data
            ctx: Execution context with utilities and callbacks

        Returns:
            Processed output data
        """
        pass

    # --------------------------------------------------------------------------
    # Lifecycle hooks (optional, override in subclasses)
    # --------------------------------------------------------------------------

    async def on_start(self, ctx: ExecutionContext) -> None:
        """Called before processing starts.

        Override to perform setup or validation.
        """
        pass

    async def on_complete(self, ctx: ExecutionContext, output: OutputT) -> None:
        """Called after successful processing.

        Override to perform cleanup or post-processing.
        """
        pass

    async def on_error(self, ctx: ExecutionContext, error: Exception) -> None:
        """Called when processing fails.

        Override to handle errors or perform recovery.
        """
        pass

    async def on_cancel(self, ctx: ExecutionContext) -> None:
        """Called when processing is cancelled.

        Override to perform cleanup on cancellation.
        """
        pass

    # --------------------------------------------------------------------------
    # Main execution methods
    # --------------------------------------------------------------------------

    async def run(
        self,
        request: AgentRequest,
        on_progress: Optional[ProgressCallback] = None,
        on_error: Optional[ErrorCallback] = None,
    ) -> AgentResponse:
        """Run the agent with full lifecycle management.

        This is the primary entry point for executing the agent.

        Args:
            request: Agent request with input data
            on_progress: Optional progress callback
            on_error: Optional error callback

        Returns:
            AgentResponse with output data and metadata
        """
        self.status = AgentStatus.PROCESSING
        self.metrics = AgentMetrics()

        # Create execution context
        ctx = ExecutionContext(
            job_id=request.job_id,
            user_id=request.metadata.get("user_id", 0),
            request=request,
            agent_state=request.context.copy(),
            on_progress=on_progress,
            on_error=on_error,
        )
        self._current_context = ctx

        self._log_start(ctx)

        try:
            # Lifecycle: on_start
            await self.on_start(ctx)

            # Check for early cancellation
            if ctx.is_cancelled():
                await self.on_cancel(ctx)
                return self._create_cancelled_response(request, ctx)

            # Validate and parse input
            input_data = self._validate_input(request.input_data)

            # Report initial progress
            ctx.report_progress(
                agent_name=self.name,
                progress_pct=0.0,
                stage="processing",
                message=f"{self.name} started",
            )

            # Main processing
            output = await self.process(input_data, ctx)

            # Check for cancellation during processing
            if ctx.is_cancelled():
                await self.on_cancel(ctx)
                return self._create_cancelled_response(request, ctx)

            # Lifecycle: on_complete
            await self.on_complete(ctx, output)

            # Update metrics
            self.metrics.end_time = datetime.utcnow()
            self.metrics.execution_time_ms = ctx.elapsed_ms()

            self._log_complete(ctx, output)
            self.status = AgentStatus.IDLE

            return self._create_success_response(request, output, ctx)

        except Exception as e:
            self.metrics.errors_encountered += 1
            self.metrics.end_time = datetime.utcnow()
            self.metrics.execution_time_ms = ctx.elapsed_ms()

            # Lifecycle: on_error
            await self.on_error(ctx, e)

            self._log_error(ctx, e)
            self.status = AgentStatus.ERROR

            # Report error via callback
            ctx.report_error(
                agent_name=self.name,
                error_code=ErrorCodes.PROCESSING_FAILED,
                error_message=str(e),
                severity=ErrorSeverity.ERROR,
                recoverable=self._is_recoverable_error(e),
                details={"traceback": traceback.format_exc()},
            )

            return self._create_error_response(request, e, ctx)

        finally:
            self._current_context = None

    def _validate_input(self, input_data: dict[str, Any]) -> InputT:
        """Validate and parse input data."""
        return self.input_type(**input_data)

    def _create_success_response(
        self, request: AgentRequest, output: OutputT, ctx: ExecutionContext
    ) -> AgentResponse:
        """Create a successful response."""
        return AgentResponse(
            source_agent=self.name,
            target_agent=request.source_agent,
            correlation_id=request.message_id,
            job_id=request.job_id,
            success=True,
            output_data=output.model_dump() if hasattr(output, "model_dump") else output.dict(),
            execution_time_ms=ctx.elapsed_ms(),
            tokens_used=self.metrics.tokens_used,
            model_used=self.config.default_model if self.metrics.llm_calls > 0 else None,
        )

    def _create_error_response(
        self, request: AgentRequest, error: Exception, ctx: ExecutionContext
    ) -> AgentResponse:
        """Create an error response."""
        return AgentResponse(
            source_agent=self.name,
            target_agent=request.source_agent,
            correlation_id=request.message_id,
            job_id=request.job_id,
            success=False,
            output_data={"error": str(error)},
            execution_time_ms=ctx.elapsed_ms(),
        )

    def _create_cancelled_response(
        self, request: AgentRequest, ctx: ExecutionContext
    ) -> AgentResponse:
        """Create a cancelled response."""
        return AgentResponse(
            source_agent=self.name,
            target_agent=request.source_agent,
            correlation_id=request.message_id,
            job_id=request.job_id,
            success=False,
            output_data={"error": "Processing cancelled"},
            execution_time_ms=ctx.elapsed_ms(),
        )

    def _is_recoverable_error(self, error: Exception) -> bool:
        """Determine if an error is recoverable."""
        recoverable_types = (
            TimeoutError,
            ConnectionError,
        )
        return isinstance(error, recoverable_types)

    # --------------------------------------------------------------------------
    # LLM helper methods
    # --------------------------------------------------------------------------

    async def call_llm(
        self,
        messages: list[ChatMessage],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        ctx: Optional[ExecutionContext] = None,
    ) -> LLMResponse:
        """Make an LLM call with tracking.

        Args:
            messages: Chat messages
            model: Model to use (defaults to agent default)
            temperature: Temperature (defaults to agent default)
            max_tokens: Maximum tokens
            ctx: Execution context for cancellation checking

        Returns:
            LLMResponse with generated content
        """
        # Check for cancellation
        if ctx and ctx.is_cancelled():
            raise RuntimeError("Processing cancelled before LLM call")

        model = model or self.config.default_model
        temperature = temperature if temperature is not None else self.config.temperature

        start_time = time.time()

        response = await self.llm_client.complete(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Update metrics
        self.metrics.llm_calls += 1
        self.metrics.tokens_used += response.usage.total_tokens
        self.metrics.llm_latency_ms += int((time.time() - start_time) * 1000)

        return response

    async def call_llm_with_system(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        ctx: Optional[ExecutionContext] = None,
    ) -> str:
        """Convenience method for simple system/user message LLM calls.

        Args:
            system_prompt: System prompt
            user_message: User message
            model: Model to use
            temperature: Temperature
            ctx: Execution context

        Returns:
            Generated content string
        """
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_message),
        ]
        response = await self.call_llm(messages, model, temperature, ctx=ctx)
        return response.content

    # --------------------------------------------------------------------------
    # Logging helpers
    # --------------------------------------------------------------------------

    def _log_start(self, ctx: ExecutionContext) -> None:
        """Log agent start."""
        logger.info(
            f'{{"timestamp": "{datetime.utcnow().isoformat()}Z", '
            f'"job_id": {ctx.job_id}, '
            f'"agent": "{self.name}", '
            f'"stage": "starting", '
            f'"elapsed_ms": 0}}'
        )

    def _log_complete(self, ctx: ExecutionContext, output: OutputT) -> None:
        """Log agent completion."""
        success = getattr(output, "success", True)
        logger.info(
            f'{{"timestamp": "{datetime.utcnow().isoformat()}Z", '
            f'"job_id": {ctx.job_id}, '
            f'"agent": "{self.name}", '
            f'"stage": "completed", '
            f'"success": {str(success).lower()}, '
            f'"tokens_used": {self.metrics.tokens_used}, '
            f'"elapsed_ms": {ctx.elapsed_ms()}}}'
        )

    def _log_error(self, ctx: ExecutionContext, error: Exception) -> None:
        """Log agent error."""
        logger.error(
            f'{{"timestamp": "{datetime.utcnow().isoformat()}Z", '
            f'"job_id": {ctx.job_id}, '
            f'"agent": "{self.name}", '
            f'"stage": "failed", '
            f'"error": "{str(error)}", '
            f'"elapsed_ms": {ctx.elapsed_ms()}}}'
        )

    # --------------------------------------------------------------------------
    # Utility methods
    # --------------------------------------------------------------------------

    def get_metrics(self) -> dict[str, Any]:
        """Get current agent metrics."""
        return self.metrics.model_dump()

    def has_capability(self, capability: AgentCapability) -> bool:
        """Check if agent has a specific capability."""
        return capability in self.config.capabilities

    def cancel(self) -> None:
        """Request cancellation of current processing."""
        if self._current_context:
            self._current_context.request_cancellation()


# Legacy compatibility - aliases for existing code
# These map to the new structures while maintaining backward compatibility


@dataclass
class JobContext:
    """Legacy context passed to each agent during execution.

    Deprecated: Use ExecutionContext instead.
    """

    job_id: int
    user_id: int
    document_url: str
    hierarchy: dict[str, Any]
    theme: dict[str, Any]
    options: dict[str, Any]
    agent_state: dict[str, Any] = field(default_factory=dict)

    def get_checkpoint(self, agent_name: str) -> Optional[dict[str, Any]]:
        """Get checkpoint for specific agent."""
        return self.agent_state.get(agent_name)

    def save_checkpoint(self, agent_name: str, state: dict[str, Any]) -> None:
        """Save checkpoint for specific agent."""
        self.agent_state[agent_name] = state


@dataclass
class AgentResult:
    """Legacy result returned by each agent.

    Deprecated: Use AgentOutput subclasses instead.
    """

    success: bool
    data: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: Optional[int] = None
    tokens_used: Optional[int] = None
