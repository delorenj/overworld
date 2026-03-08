"""Anonymous usage tracking model for free-tier token operations."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class AnonymousUsage(Base):
    """Tracks anonymous free-tier usage by session/IP fingerprint.

    We keep one rolling 24h window row per (client_id_hash, operation).
    """

    __tablename__ = "anonymous_usage"
    __table_args__ = (
        UniqueConstraint("client_id_hash", "operation", name="uq_anonymous_usage_client_op"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # SHA256 hash of session/IP fingerprint (never store raw IP)
    client_id_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Operation key (e.g. "export")
    operation: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Rolling window usage and limit snapshot
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    free_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    # Window timestamps
    window_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    window_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<AnonymousUsage(operation={self.operation}, usage={self.usage_count}/"
            f"{self.free_limit})>"
        )
