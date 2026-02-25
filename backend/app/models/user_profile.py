"""User profile preferences model.

Stores per-user customization preferences (default theme, color mode,
map visibility, notification settings). Separate from the auth-focused
User model to keep concerns clean.

Related Holyfields schema: overworld/user_profile.v1.json
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class UserProfile(Base):
    """
    User profile and preferences.

    One-to-one with User. Created lazily on first preference change
    or profile view (get_or_create pattern).
    """

    __tablename__ = "user_profiles"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Foreign key to user (unique = one-to-one)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Display preferences
    default_theme_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("themes.id", ondelete="SET NULL"),
        nullable=True,
    )
    default_map_visibility: Mapped[str] = mapped_column(
        String(20), nullable=False, default="private"
    )  # private | unlisted | public
    color_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="system"
    )  # light | dark | system
    language: Mapped[str] = mapped_column(
        String(10), nullable=False, default="en"
    )  # ISO 639-1

    # Notification preferences
    notifications_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    email_marketing: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # Map defaults
    auto_watermark: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )  # Free tier: always True

    # History counters (denormalized for fast reads)
    total_maps_created: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    total_exports: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="profile")
    default_theme: Mapped[Optional["Theme"]] = relationship("Theme")

    def __repr__(self) -> str:
        return f"<UserProfile(user_id={self.user_id})>"
