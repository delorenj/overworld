"""Generation job model for async map generation tracking."""

import enum
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class JobStatus(str, enum.Enum):
    """Generation job statuses."""

    PENDING = "pending"  # Queued, waiting to start
    PROCESSING = "processing"  # Currently being processed
    COMPLETED = "completed"  # Successfully completed
    FAILED = "failed"  # Failed with error


class GenerationJob(Base):
    """
    Async generation job tracking.

    Tracks multi-agent pipeline progress and state for each map generation.
    """

    __tablename__ = "generation_jobs"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

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

    # Error details (if failed)
    error_msg: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="generation_jobs")
    document: Mapped[Optional["Document"]] = relationship(
        "Document", back_populates="generation_jobs"
    )
    map: Mapped[Optional["Map"]] = relationship("Map", back_populates="generation_jobs")

    def __repr__(self) -> str:
        return f"<GenerationJob(id={self.id}, status={self.status.value}, progress={self.progress_pct}%)>"
