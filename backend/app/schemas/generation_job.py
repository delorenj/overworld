"""Pydantic schemas for generation job operations.

This module defines the request/response schemas for the job queue API,
supporting ARQ-based job processing with progress tracking and retries.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.generation_job import JobStatus


class GenerationJobCreate(BaseModel):
    """Schema for creating a new generation job.

    Request body for POST /api/jobs endpoint.
    """

    document_id: Optional[str] = Field(
        default=None, description="ID of the document to generate map from (optional)"
    )
    theme_id: str = Field(default="smb3", description="Theme ID (defaults to smb3)")
    options: dict = Field(
        default_factory=dict, description="Generation options (e.g., scatter_threshold)"
    )
    max_retries: int = Field(
        default=3, ge=0, le=10, description="Maximum retry attempts on failure"
    )

    @field_validator("document_id")
    @classmethod
    def validate_document_id(cls, v: Optional[str]) -> Optional[str]:
        """Validate document_id is a valid UUID if provided."""
        if v is not None:
            try:
                UUID(v)
            except ValueError:
                raise ValueError("document_id must be a valid UUID")
        return v


class GenerationJobResponse(BaseModel):
    """Schema for generation job response.

    Response body for GET /api/jobs/{id} and POST /api/jobs endpoints.
    """

    id: int = Field(..., description="Job ID")
    arq_job_id: Optional[str] = Field(None, description="ARQ queue job ID")
    status: JobStatus = Field(..., description="Current job status")
    progress_pct: float = Field(..., description="Progress percentage (0-100)")
    progress_message: Optional[str] = Field(None, description="Human-readable progress status")
    queue_position: Optional[int] = Field(None, description="Position in queue (if pending)")
    estimated_wait_seconds: Optional[int] = Field(
        None, description="Estimated wait time in seconds"
    )
    map_id: Optional[int] = Field(None, description="Generated map ID (if completed)")
    document_id: Optional[str] = Field(None, description="Source document ID")

    # Retry information
    retry_count: int = Field(0, description="Number of retry attempts")
    max_retries: int = Field(3, description="Maximum retry attempts")
    next_retry_at: Optional[datetime] = Field(None, description="When next retry is scheduled")

    # Error information
    error_msg: Optional[str] = Field(None, description="Error message (if failed)")
    error_code: Optional[str] = Field(None, description="Error classification code")

    # Timestamps
    created_at: datetime = Field(..., description="Job creation timestamp")
    started_at: Optional[datetime] = Field(None, description="Job start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Job completion timestamp")
    cancelled_at: Optional[datetime] = Field(None, description="Job cancellation timestamp")

    class Config:
        from_attributes = True


class GenerationJobUpdate(BaseModel):
    """Schema for updating generation job status (internal use)."""

    status: Optional[JobStatus] = None
    progress_pct: Optional[float] = Field(None, ge=0.0, le=100.0)
    progress_message: Optional[str] = None
    agent_state: Optional[dict] = None
    error_msg: Optional[str] = None
    error_code: Optional[str] = None
    map_id: Optional[int] = None


class JobQueueInfo(BaseModel):
    """Schema for job queue information."""

    queue_position: int = Field(..., description="Position in queue")
    estimated_wait_seconds: int = Field(..., description="Estimated wait time in seconds")
    jobs_ahead: int = Field(..., description="Number of jobs ahead in queue")


class GenerationRequest(BaseModel):
    """Schema for generation request passed to ARQ worker.

    This is the payload enqueued to the ARQ job queue.
    """

    job_id: int = Field(..., description="Database job ID")
    arq_job_id: str = Field(..., description="ARQ job ID for tracking")
    document_id: Optional[str] = Field(None, description="Document ID")
    user_id: int = Field(..., description="User ID")
    theme_id: Optional[str] = Field(None, description="Theme ID (optional)")
    options: dict = Field(default_factory=dict, description="Generation options")
    retry_count: int = Field(0, description="Current retry attempt")
    max_retries: int = Field(3, description="Maximum retry attempts")


class JobStateUpdate(BaseModel):
    """Schema for job state checkpoint updates from workers."""

    agent_name: str = Field(..., description="Agent name (parser, artist, road, icon)")
    state: dict = Field(..., description="Agent state checkpoint")
    progress_pct: float = Field(..., ge=0.0, le=100.0)
    progress_message: Optional[str] = Field(None, description="Human-readable progress")
    status: Optional[JobStatus] = None


class JobProgressUpdate(BaseModel):
    """Schema for real-time progress updates via Redis pub/sub."""

    job_id: int = Field(..., description="Job ID")
    progress_pct: float = Field(..., ge=0.0, le=100.0, description="Progress percentage")
    progress_message: Optional[str] = Field(None, description="Progress message")
    status: JobStatus = Field(..., description="Current status")
    agent_name: Optional[str] = Field(None, description="Current agent processing")


class JobCancellationResponse(BaseModel):
    """Schema for job cancellation response."""

    id: int = Field(..., description="Job ID")
    status: JobStatus = Field(..., description="Updated status (should be CANCELLED)")
    cancelled_at: datetime = Field(..., description="Cancellation timestamp")
    message: str = Field(..., description="Cancellation result message")


class JobListResponse(BaseModel):
    """Schema for paginated job list response."""

    jobs: list[GenerationJobResponse] = Field(..., description="List of jobs")
    total: int = Field(..., description="Total number of jobs matching filter")
    limit: int = Field(..., description="Page size limit")
    offset: int = Field(..., description="Page offset")
