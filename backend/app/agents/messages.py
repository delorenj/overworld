"""Agent communication protocol message types.

This module defines the Pydantic models for all inter-agent communication,
enabling type-safe message passing and validation throughout the pipeline.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional, TypeVar, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

# Generic type variables for typed messages
InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


class MessageType(str, Enum):
    """Types of messages in the agent communication protocol."""

    REQUEST = "request"  # Request to process data
    RESPONSE = "response"  # Response with processed data
    PROGRESS = "progress"  # Progress update during processing
    ERROR = "error"  # Error notification
    HEARTBEAT = "heartbeat"  # Agent health check
    CANCEL = "cancel"  # Request to cancel processing


class MessagePriority(str, Enum):
    """Message priority levels for queue ordering."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorSeverity(str, Enum):
    """Severity levels for error messages."""

    WARNING = "warning"  # Non-fatal, processing can continue
    ERROR = "error"  # Fatal for current operation, may be retryable
    CRITICAL = "critical"  # Fatal, requires intervention


class BaseMessage(BaseModel):
    """Base class for all agent messages.

    Provides common fields for message tracking, routing, and correlation.
    """

    message_id: UUID = Field(default_factory=uuid4, description="Unique message identifier")
    message_type: MessageType = Field(..., description="Type of message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message creation time")
    correlation_id: Optional[UUID] = Field(
        default=None, description="ID linking related messages together"
    )
    source_agent: str = Field(..., description="Name of the sending agent")
    target_agent: Optional[str] = Field(
        default=None, description="Name of the target agent (None for broadcast)"
    )
    priority: MessagePriority = Field(
        default=MessagePriority.NORMAL, description="Message priority"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional message metadata"
    )

    class Config:
        """Pydantic config."""

        use_enum_values = True


class AgentRequest(BaseMessage):
    """Request message for agent processing.

    Contains the input data and context for an agent to process.
    """

    message_type: MessageType = Field(default=MessageType.REQUEST, frozen=True)
    job_id: int = Field(..., description="Generation job ID")
    input_data: dict[str, Any] = Field(..., description="Input data for processing")
    context: dict[str, Any] = Field(
        default_factory=dict, description="Additional context from previous agents"
    )
    timeout_seconds: Optional[int] = Field(
        default=120, description="Processing timeout in seconds"
    )
    retry_count: int = Field(default=0, description="Number of retries attempted")
    max_retries: int = Field(default=3, description="Maximum retry attempts")


class AgentResponse(BaseMessage):
    """Response message from agent processing.

    Contains the output data and processing metadata.
    """

    model_config = {"protected_namespaces": ()}

    message_type: MessageType = Field(default=MessageType.RESPONSE, frozen=True)
    job_id: int = Field(..., description="Generation job ID")
    success: bool = Field(..., description="Whether processing succeeded")
    output_data: Optional[dict[str, Any]] = Field(
        default=None, description="Processed output data"
    )
    execution_time_ms: int = Field(..., description="Processing time in milliseconds")
    tokens_used: Optional[int] = Field(
        default=None, description="LLM tokens consumed (if applicable)"
    )
    model_used: Optional[str] = Field(
        default=None, description="LLM model used (if applicable)"
    )


class ProgressUpdate(BaseMessage):
    """Progress update message during processing.

    Enables real-time progress tracking and UI updates.
    """

    message_type: MessageType = Field(default=MessageType.PROGRESS, frozen=True)
    job_id: int = Field(..., description="Generation job ID")
    progress_pct: float = Field(
        ..., ge=0.0, le=100.0, description="Progress percentage (0-100)"
    )
    stage: str = Field(..., description="Current processing stage")
    stage_progress_pct: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Progress within current stage"
    )
    message: Optional[str] = Field(
        default=None, description="Human-readable progress message"
    )
    estimated_remaining_seconds: Optional[int] = Field(
        default=None, description="Estimated time remaining"
    )


class ErrorMessage(BaseMessage):
    """Error message for processing failures.

    Contains detailed error information for debugging and recovery.
    """

    message_type: MessageType = Field(default=MessageType.ERROR, frozen=True)
    job_id: int = Field(..., description="Generation job ID")
    severity: ErrorSeverity = Field(..., description="Error severity level")
    error_code: str = Field(..., description="Machine-readable error code")
    error_message: str = Field(..., description="Human-readable error description")
    error_details: Optional[dict[str, Any]] = Field(
        default=None, description="Additional error context"
    )
    stack_trace: Optional[str] = Field(
        default=None, description="Stack trace for debugging"
    )
    recoverable: bool = Field(
        default=False, description="Whether the error is recoverable"
    )
    suggested_action: Optional[str] = Field(
        default=None, description="Suggested recovery action"
    )


class HeartbeatMessage(BaseMessage):
    """Heartbeat message for agent health monitoring."""

    message_type: MessageType = Field(default=MessageType.HEARTBEAT, frozen=True)
    agent_status: str = Field(default="healthy", description="Agent health status")
    current_job_id: Optional[int] = Field(
        default=None, description="Currently processing job ID"
    )
    jobs_completed: int = Field(default=0, description="Total jobs completed by agent")
    uptime_seconds: int = Field(default=0, description="Agent uptime in seconds")
    memory_usage_mb: Optional[float] = Field(
        default=None, description="Current memory usage in MB"
    )


class CancelMessage(BaseMessage):
    """Cancel request message.

    Requests graceful cancellation of in-progress processing.
    """

    message_type: MessageType = Field(default=MessageType.CANCEL, frozen=True)
    job_id: int = Field(..., description="Job ID to cancel")
    reason: Optional[str] = Field(default=None, description="Cancellation reason")
    force: bool = Field(
        default=False, description="Force immediate cancellation without cleanup"
    )


# Type alias for any message type
AnyMessage = Union[
    AgentRequest,
    AgentResponse,
    ProgressUpdate,
    ErrorMessage,
    HeartbeatMessage,
    CancelMessage,
]


# Error codes for standardized error handling
class ErrorCodes:
    """Standardized error codes for the agent pipeline."""

    # Input validation errors (1xxx)
    INVALID_INPUT = "E1001"
    MISSING_REQUIRED_FIELD = "E1002"
    INVALID_HIERARCHY = "E1003"
    INVALID_THEME = "E1004"

    # LLM errors (2xxx)
    LLM_UNAVAILABLE = "E2001"
    LLM_RATE_LIMITED = "E2002"
    LLM_TIMEOUT = "E2003"
    LLM_INVALID_RESPONSE = "E2004"
    LLM_TOKEN_LIMIT_EXCEEDED = "E2005"

    # Processing errors (3xxx)
    PROCESSING_FAILED = "E3001"
    PROCESSING_TIMEOUT = "E3002"
    CHECKPOINT_FAILED = "E3003"
    STATE_CORRUPTION = "E3004"

    # Resource errors (4xxx)
    RESOURCE_UNAVAILABLE = "E4001"
    STORAGE_ERROR = "E4002"
    DATABASE_ERROR = "E4003"

    # Pipeline errors (5xxx)
    PIPELINE_STATE_INVALID = "E5001"
    AGENT_NOT_FOUND = "E5002"
    TRANSITION_INVALID = "E5003"
    PIPELINE_CANCELLED = "E5004"
