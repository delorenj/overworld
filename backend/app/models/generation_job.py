"""Generation job model for async map generation tracking.

This module defines the GenerationJob model for tracking asynchronous
map generation jobs processed via ARQ (Async Redis Queue).
"""

import enum
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class JobStatus(str, enum.Enum):
    """Generation job statuses.

    State transitions:
    - PENDING -> PROCESSING (worker picks up job)
    - PROCESSING -> COMPLETED (success)
    - PROCESSING -> FAILED (error, may retry)
    - PROCESSING -> CANCELLED (user cancelled)
    - PENDING -> CANCELLED (cancelled before processing)
    - FAILED -> PENDING (retry scheduled)
    """

    PENDING = "pending"  # Queued, waiting to start
    PROCESSING = "processing"  # Currently being processed by worker
    COMPLETED = "completed"  # Successfully completed
    FAILED = "failed"  # Failed with error (may be retried)
    CANCELLED = "cancelled"  # Cancelled by user or system


class GenerationJob(Base):
    """
    Async generation job tracking.

    Tracks multi-agent pipeline progress and state for each map generation.
    Jobs are processed via ARQ (Async Redis Queue) with support for:
    - Progress tracking (0-100%)
    - Retry logic with exponential backoff
    - Job cancellation
    - State checkpointing for recovery
    """

    __tablename__ = "generation_jobs"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # ARQ job ID for tracking in Redis queue
    arq_job_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True, unique=True
    )

    # Foreign keys
    document_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True
    )  # Optional - can be triggered by document upload
    map_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("maps.id", ondelete="CASCADE"), nullable=True
    )  # Null until map created
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Job status
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus), default=JobStatus.PENDING, nullable=False, index=True
    )

    # Agent state checkpointing (JSONB)
    agent_state: Mapped[dict] = mapped_column(
        JSONB, default={}, nullable=False
    )  # Parser, Artist, Road, Icon outputs

    # Progress tracking
    progress_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    progress_message: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )  # Human-readable progress status

    # Retry tracking
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # When next retry is scheduled

    # Error details (if failed)
    error_msg: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # Error classification for retry logic

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="generation_jobs")
    document: Mapped[Optional["Document"]] = relationship(
        "Document", back_populates="generation_jobs"
    )
    map: Mapped[Optional["Map"]] = relationship("Map", back_populates="generation_jobs")

    def __repr__(self) -> str:
        return (
            f"<GenerationJob(id={self.id}, status={self.status.value}, "
            f"progress={self.progress_pct}%, retries={self.retry_count}/{self.max_retries})>"
        )

    @property
    def can_retry(self) -> bool:
        """Check if the job can be retried."""
        return (
            self.status == JobStatus.FAILED
            and self.retry_count < self.max_retries
        )

    @property
    def is_terminal(self) -> bool:
        """Check if the job is in a terminal state (no more processing)."""
        return self.status in (JobStatus.COMPLETED, JobStatus.CANCELLED)

    @property
    def is_active(self) -> bool:
        """Check if the job is currently active (pending or processing)."""
        return self.status in (JobStatus.PENDING, JobStatus.PROCESSING)
