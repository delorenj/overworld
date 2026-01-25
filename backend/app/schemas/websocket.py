"""WebSocket event schemas for real-time job progress updates.

This module defines the event types and payload schemas for WebSocket
communication between the backend and frontend clients.

Event Types:
- job_started: Fired when a job begins processing
- progress_update: Fired periodically with progress percentage
- job_completed: Fired when a job finishes successfully
- job_failed: Fired when a job fails with error details
- connection_established: Acknowledgment of successful connection
- error: General error event
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.models.generation_job import JobStatus


class WebSocketEventType(str, Enum):
    """WebSocket event types for job progress updates."""

    # Connection events
    CONNECTION_ESTABLISHED = "connection_established"
    CONNECTION_ERROR = "connection_error"

    # Job lifecycle events
    JOB_STARTED = "job_started"
    PROGRESS_UPDATE = "progress_update"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    JOB_CANCELLED = "job_cancelled"

    # Client commands
    PING = "ping"
    PONG = "pong"


class BaseWebSocketEvent(BaseModel):
    """Base class for all WebSocket events."""

    type: WebSocketEventType = Field(..., description="Event type identifier")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Event timestamp (UTC)"
    )


class ConnectionEstablishedEvent(BaseWebSocketEvent):
    """Event sent when WebSocket connection is established successfully."""

    type: WebSocketEventType = WebSocketEventType.CONNECTION_ESTABLISHED
    job_id: int = Field(..., description="Job ID being monitored")
    current_status: JobStatus = Field(..., description="Current job status")
    current_progress: float = Field(..., ge=0.0, le=100.0, description="Current progress")
    message: str = Field(default="Connected to job progress stream")


class ConnectionErrorEvent(BaseWebSocketEvent):
    """Event sent when there's a connection-level error."""

    type: WebSocketEventType = WebSocketEventType.CONNECTION_ERROR
    error_code: str = Field(..., description="Error code for client handling")
    message: str = Field(..., description="Human-readable error message")


class JobStartedEvent(BaseWebSocketEvent):
    """Event sent when a job begins processing."""

    type: WebSocketEventType = WebSocketEventType.JOB_STARTED
    job_id: int = Field(..., description="Job ID")
    started_at: datetime = Field(..., description="Job start timestamp")
    agent_name: Optional[str] = Field(None, description="First agent to process")


class ProgressUpdateEvent(BaseWebSocketEvent):
    """Event sent periodically with job progress updates."""

    type: WebSocketEventType = WebSocketEventType.PROGRESS_UPDATE
    job_id: int = Field(..., description="Job ID")
    progress_pct: float = Field(..., ge=0.0, le=100.0, description="Progress percentage")
    progress_message: Optional[str] = Field(None, description="Human-readable progress status")
    agent_name: Optional[str] = Field(None, description="Current agent processing")
    stage: Optional[str] = Field(None, description="Current processing stage")


class JobCompletedEvent(BaseWebSocketEvent):
    """Event sent when a job completes successfully."""

    type: WebSocketEventType = WebSocketEventType.JOB_COMPLETED
    job_id: int = Field(..., description="Job ID")
    map_id: Optional[int] = Field(None, description="Generated map ID")
    completed_at: datetime = Field(..., description="Completion timestamp")
    total_duration_seconds: Optional[float] = Field(
        None, description="Total processing time in seconds"
    )


class JobFailedEvent(BaseWebSocketEvent):
    """Event sent when a job fails."""

    type: WebSocketEventType = WebSocketEventType.JOB_FAILED
    job_id: int = Field(..., description="Job ID")
    error_message: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error classification code")
    can_retry: bool = Field(..., description="Whether the job can be retried")
    retry_count: int = Field(..., description="Number of retries attempted")
    max_retries: int = Field(..., description="Maximum retries allowed")
    failed_at: datetime = Field(..., description="Failure timestamp")


class JobCancelledEvent(BaseWebSocketEvent):
    """Event sent when a job is cancelled."""

    type: WebSocketEventType = WebSocketEventType.JOB_CANCELLED
    job_id: int = Field(..., description="Job ID")
    cancelled_at: datetime = Field(..., description="Cancellation timestamp")


class PingEvent(BaseWebSocketEvent):
    """Ping event for connection keep-alive."""

    type: WebSocketEventType = WebSocketEventType.PING


class PongEvent(BaseWebSocketEvent):
    """Pong response to ping for connection keep-alive."""

    type: WebSocketEventType = WebSocketEventType.PONG


# Type alias for all possible WebSocket events
WebSocketEvent = (
    ConnectionEstablishedEvent
    | ConnectionErrorEvent
    | JobStartedEvent
    | ProgressUpdateEvent
    | JobCompletedEvent
    | JobFailedEvent
    | JobCancelledEvent
    | PingEvent
    | PongEvent
)


class WebSocketMessage(BaseModel):
    """Wrapper for WebSocket messages with optional metadata."""

    event: dict = Field(..., description="Event payload")
    correlation_id: Optional[str] = Field(
        None, description="Optional correlation ID for tracking"
    )

    @classmethod
    def from_event(
        cls, event: BaseWebSocketEvent, correlation_id: Optional[str] = None
    ) -> "WebSocketMessage":
        """Create a message from an event."""
        return cls(
            event=event.model_dump(mode="json"),
            correlation_id=correlation_id,
        )
