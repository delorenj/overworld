"""Map model for generated overworld maps."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Map(Base):
    """
    Generated overworld map.

    Stores hierarchy, theme reference, and generation metadata.
    """

    __tablename__ = "maps"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Foreign keys
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    theme_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("themes.id", ondelete="RESTRICT"), nullable=False
    )

    # Map metadata
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Hierarchy data (JSONB with GIN index for fast queries)
    hierarchy: Mapped[dict] = mapped_column(
        JSONB, nullable=False
    )  # L0-L4 structure from parser

    # Watermark flag
    watermarked: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # R2 storage URL
    r2_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="maps")
    theme: Mapped["Theme"] = relationship("Theme", back_populates="maps")
    generation_jobs: Mapped[list["GenerationJob"]] = relationship(
        "GenerationJob", back_populates="map", cascade="all, delete-orphan"
    )
    exports: Mapped[list["Export"]] = relationship(
        "Export", back_populates="map", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Map(id={self.id}, name={self.name})>"
