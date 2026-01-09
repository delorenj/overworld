"""Theme model for map visual styles."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Theme(Base):
    """
    Visual theme for generated maps.

    Includes default themes (SMB3, etc.) and user-uploaded custom themes (Phase 2).
    """

    __tablename__ = "themes"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Theme metadata
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Premium flag
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Asset manifest (JSON)
    asset_manifest: Mapped[dict] = mapped_column(
        JSONB, nullable=False
    )  # Colors, textures, icons, fonts

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    # Relationships
    maps: Mapped[list["Map"]] = relationship("Map", back_populates="theme")

    def __repr__(self) -> str:
        return f"<Theme(id={self.id}, name={self.name})>"
