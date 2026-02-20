"""Project model for grouping multiple documents into a cohesive project.

A project represents a logical container for related documents that will be
analyzed together through consensus-based milestone extraction.
"""

import enum
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ProjectStatus(str, enum.Enum):
    """Project lifecycle statuses."""

    CREATED = "created"  # Project created, awaiting documents
    READY = "ready"  # Has documents, ready for analysis
    ANALYZING = "analyzing"  # Consensus analysis in progress
    ANALYZED = "analyzed"  # Consensus complete
    FAILED = "failed"  # Analysis failed


class Project(Base):
    """Project container for multi-document consensus analysis.

    Projects group related documents (PRDs, specs, diagrams, audio transcripts)
    for unified milestone/checkpoint extraction through EM + PM consensus.
    """

    __tablename__ = "projects"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, index=True)

    # Foreign keys
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Project metadata
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status tracking
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus), default=ProjectStatus.CREATED, nullable=False, index=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    analyzed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="projects")
    documents: Mapped[list["ProjectDocument"]] = relationship(
        "ProjectDocument",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectDocument.added_at",
    )
    consensus_analyses: Mapped[list["ConsensusAnalysis"]] = relationship(
        "ConsensusAnalysis",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ConsensusAnalysis.created_at.desc()",
    )

    def __repr__(self) -> str:
        return (
            f"<Project(id={self.id}, name={self.name!r}, "
            f"status={self.status.value}, documents={len(self.documents)})>"
        )

    @property
    def document_count(self) -> int:
        """Number of documents attached to this project."""
        return len(self.documents)

    @property
    def has_documents(self) -> bool:
        """Whether project has any documents."""
        return len(self.documents) > 0

    @property
    def latest_analysis(self) -> Optional["ConsensusAnalysis"]:
        """Get the most recent consensus analysis (if any)."""
        return self.consensus_analyses[0] if self.consensus_analyses else None


class ProjectDocument(Base):
    """Join table linking documents to projects with metadata."""

    __tablename__ = "project_documents"

    # Composite primary key
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )

    # Metadata
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    order_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )  # For ordering documents

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="documents")
    document: Mapped["Document"] = relationship("Document", back_populates="projects")

    def __repr__(self) -> str:
        return (
            f"<ProjectDocument(project_id={self.project_id}, "
            f"document_id={self.document_id}, order={self.order_index})>"
        )
