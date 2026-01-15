"""Pydantic schemas for generation job operations."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.generation_job import JobStatus


class GenerationJobCreate(BaseModel):
    """Schema for creating a new generation job."""

    document_id: str = Field(..., description="ID of the document to generate map from")
    theme_id: Optional[str] = Field(default="smb3", description="Theme ID (defaults to smb3)")
    options: Optional[dict] = Field(
        default_factory=dict, description="Generation options (e.g., scatter_threshold)"
    )


class GenerationJobResponse(BaseModel):
    """Schema for generation job response."""

    id: int = Field(..., description="Job ID")
    status: JobStatus = Field(..., description="Current job status")
    progress_pct: float = Field(..., description="Progress percentage (0-100)")
    queue_position: Optional[int] = Field(None, description="Position in queue (if pending)")
    estimated_wait_seconds: Optional[int] = Field(
        None, description="Estimated wait time in seconds"
    )
    map_id: Optional[int] = Field(None, description="Generated map ID (if completed)")
    error_msg: Optional[str] = Field(None, description="Error message (if failed)")
    created_at: datetime = Field(..., description="Job creation timestamp")
    started_at: Optional[datetime] = Field(None, description="Job start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Job completion timestamp")

    class Config:
        from_attributes = True


class GenerationJobUpdate(BaseModel):
    """Schema for updating generation job status."""

    status: Optional[JobStatus] = None
    progress_pct: Optional[float] = Field(None, ge=0.0, le=100.0)
    agent_state: Optional[dict] = None
    error_msg: Optional[str] = None
    map_id: Optional[int] = None


class JobQueueInfo(BaseModel):
    """Schema for job queue information."""

    queue_position: int = Field(..., description="Position in queue")
    estimated_wait_seconds: int = Field(..., description="Estimated wait time in seconds")
    jobs_ahead: int = Field(..., description="Number of jobs ahead in queue")


class GenerationRequest(BaseModel):
    """Schema for generation request published to queue."""

    job_id: int = Field(..., description="Job ID")
    document_id: str = Field(..., description="Document ID")
    user_id: int = Field(..., description="User ID")
    theme_id: str = Field(..., description="Theme ID")
    options: dict = Field(..., description="Generation options")


class JobStateUpdate(BaseModel):
    """Schema for job state checkpoint updates."""

    agent_name: str = Field(..., description="Agent name (parser, artist, road, icon)")
    state: dict = Field(..., description="Agent state checkpoint")
    progress_pct: float = Field(..., ge=0.0, le=100.0)
    status: Optional[JobStatus] = None
