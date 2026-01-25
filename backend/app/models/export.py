"""Export model for map exports."""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class ExportFormat(str, Enum):
    """Supported export formats."""
    PNG = "png"
    SVG = "svg"


class ExportStatus(str, Enum):
    """Export processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Export(Base):
    """
    Map export record.

    Tracks user-generated exports with format, resolution, and watermark settings.
    Exports are stored in R2 with time-limited access URLs.
    """

    __tablename__ = "exports"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Foreign keys
    map_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("maps.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Export configuration
    format: Mapped[ExportFormat] = mapped_column(
        SQLEnum(ExportFormat), nullable=False
    )
    resolution: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
    )  # 1x, 2x, 4x multiplier

    # Export status and result
    status: Mapped[ExportStatus] = mapped_column(
        SQLEnum(ExportStatus), nullable=False, default=ExportStatus.PENDING, index=True
    )
    file_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # bytes

    # Watermark flag
    watermarked: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="exports")
    map: Mapped["Map"] = relationship("Map", back_populates="exports")

    def __repr__(self) -> str:
        return f"<Export(id={self.id}, format={self.format}, status={self.status})>"
