"""Document model for uploaded files."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import enum
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DocumentStatus(str, enum.Enum):
    """Document processing statuses."""

    UPLOADED = "uploaded"  # File uploaded to R2
    PROCESSING = "processing"  # Being parsed/extracted
    PROCESSED = "processed"  # Hierarchy extracted successfully
    FAILED = "failed"  # Processing failed


class Document(Base):
    """Document uploaded by users."""

    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    r2_path: Mapped[str] = mapped_column(String(500), nullable=False)
    r2_url: Mapped[str] = mapped_column(String(500), nullable=False)

    # Processing fields
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus), default=DocumentStatus.UPLOADED, nullable=False, index=True
    )
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    processed_content: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    processing_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="documents")
    generation_jobs: Mapped[list["GenerationJob"]] = relationship(
        "GenerationJob", back_populates="document", cascade="all, delete-orphan"
    )
    projects: Mapped[list["ProjectDocument"]] = relationship(
        "ProjectDocument", back_populates="document", cascade="all, delete-orphan"
    )
