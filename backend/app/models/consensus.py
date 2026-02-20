"""Consensus analysis models for storing EM/PM consensus results.

These models persist the output of multi-agent consensus analysis including:
- ConsensusAnalysis: Top-level analysis tracking and job status
- Milestone: Extracted project milestones
- Checkpoint: Validation checkpoints within milestones
- Version: Release boundaries grouping milestones
"""

import enum
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    ARRAY,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AnalysisStatus(str, enum.Enum):
    """Consensus analysis job statuses."""

    PENDING = "pending"  # Queued, waiting to start
    ANALYZING = "analyzing"  # Consensus rounds in progress
    CONVERGED = "converged"  # Successfully converged
    FAILED = "failed"  # Failed (max rounds or error)
    CANCELLED = "cancelled"  # Cancelled by user


class MilestoneType(str, enum.Enum):
    """Milestone categorization."""

    TECHNICAL = "technical"  # Infrastructure/architecture
    PRODUCT = "product"  # User-facing features
    HYBRID = "hybrid"  # Both technical and product


class EffortSize(str, enum.Enum):
    """Relative effort estimation."""

    S = "S"  # Small: 1-3 days
    M = "M"  # Medium: 1-2 weeks
    L = "L"  # Large: 2-4 weeks
    XL = "XL"  # Extra Large: 4+ weeks


class CheckpointType(str, enum.Enum):
    """Checkpoint categorization."""

    POC = "poc"  # Proof of concept
    DEMO = "demo"  # Demonstration
    TEST = "test"  # Testing checkpoint
    REVIEW = "review"  # Review/approval gate


class ConsensusAnalysis(Base):
    """Top-level consensus analysis tracking.

    Represents a single consensus run with all extracted milestones,
    checkpoints, and versions.
    """

    __tablename__ = "consensus_analyses"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, index=True)

    # Foreign keys
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ARQ job tracking
    arq_job_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True, unique=True
    )

    # Analysis status
    status: Mapped[AnalysisStatus] = mapped_column(
        Enum(AnalysisStatus), default=AnalysisStatus.PENDING, nullable=False, index=True
    )

    # Convergence metrics
    converged: Mapped[bool] = mapped_column(default=False, nullable=False)
    convergence_reason: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # "stable_novelty" or "high_confidence"
    total_rounds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    final_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    final_novelty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Token/cost tracking
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Structured output counts
    milestones_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    checkpoints_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    versions_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Full consensus result (JSONB for flexibility)
    consensus_rounds: Mapped[dict] = mapped_column(
        JSONB, default={}, nullable=False
    )  # Full round history
    reasoning: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Notetaker's reasoning

    # Error details (if failed)
    error_msg: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="consensus_analyses")
    project: Mapped["Project"] = relationship("Project", back_populates="consensus_analyses")
    milestones: Mapped[list["Milestone"]] = relationship(
        "Milestone",
        back_populates="analysis",
        cascade="all, delete-orphan",
        order_by="Milestone.created_order",
    )
    checkpoints: Mapped[list["Checkpoint"]] = relationship(
        "Checkpoint", back_populates="analysis", cascade="all, delete-orphan"
    )
    versions: Mapped[list["Version"]] = relationship(
        "Version",
        back_populates="analysis",
        cascade="all, delete-orphan",
        order_by="Version.created_order",
    )

    def __repr__(self) -> str:
        return (
            f"<ConsensusAnalysis(id={self.id}, project_id={self.project_id}, "
            f"status={self.status.value}, rounds={self.total_rounds}, "
            f"milestones={self.milestones_count})>"
        )

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate analysis duration if completed."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class Milestone(Base):
    """Extracted project milestone from consensus analysis."""

    __tablename__ = "milestones"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, index=True)

    # Foreign keys
    analysis_id: Mapped[UUID] = mapped_column(
        ForeignKey("consensus_analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Milestone data
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[MilestoneType] = mapped_column(
        Enum(MilestoneType), nullable=False, index=True
    )
    estimated_effort: Mapped[EffortSize] = mapped_column(Enum(EffortSize), nullable=False)

    # Dependencies (array of milestone titles)
    dependencies: Mapped[list[str]] = mapped_column(
        ARRAY(String), default=[], nullable=False
    )

    # Ordering
    created_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )  # Order in extraction

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    analysis: Mapped["ConsensusAnalysis"] = relationship(
        "ConsensusAnalysis", back_populates="milestones"
    )
    checkpoints: Mapped[list["Checkpoint"]] = relationship(
        "Checkpoint",
        back_populates="milestone",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Milestone(id={self.id}, title={self.title!r}, "
            f"type={self.type.value}, effort={self.estimated_effort.value})>"
        )


class Checkpoint(Base):
    """Validation checkpoint within a milestone."""

    __tablename__ = "checkpoints"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, index=True)

    # Foreign keys
    analysis_id: Mapped[UUID] = mapped_column(
        ForeignKey("consensus_analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    milestone_id: Mapped[UUID] = mapped_column(
        ForeignKey("milestones.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Checkpoint data
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    type: Mapped[CheckpointType] = mapped_column(
        Enum(CheckpointType), default=CheckpointType.TEST, nullable=False
    )
    validation_criteria: Mapped[list[str]] = mapped_column(
        ARRAY(String), default=[], nullable=False
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    analysis: Mapped["ConsensusAnalysis"] = relationship(
        "ConsensusAnalysis", back_populates="checkpoints"
    )
    milestone: Mapped["Milestone"] = relationship("Milestone", back_populates="checkpoints")

    def __repr__(self) -> str:
        return (
            f"<Checkpoint(id={self.id}, title={self.title!r}, "
            f"type={self.type.value}, milestone_id={self.milestone_id})>"
        )


class Version(Base):
    """Version/release boundary grouping milestones."""

    __tablename__ = "versions"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, index=True)

    # Foreign keys
    analysis_id: Mapped[UUID] = mapped_column(
        ForeignKey("consensus_analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Version data
    name: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # "MVP", "v1.0", "Beta"
    release_goal: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # High-level user-facing goal
    milestone_titles: Mapped[list[str]] = mapped_column(
        ARRAY(String), default=[], nullable=False
    )

    # Ordering
    created_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )  # Order in roadmap

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    analysis: Mapped["ConsensusAnalysis"] = relationship(
        "ConsensusAnalysis", back_populates="versions"
    )

    def __repr__(self) -> str:
        return (
            f"<Version(id={self.id}, name={self.name!r}, "
            f"milestones={len(self.milestone_titles)})>"
        )
