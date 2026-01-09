"""Transaction model for token usage tracking."""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class TransactionType(str, enum.Enum):
    """Transaction types for token operations."""

    GENERATION = "generation"  # Map generation cost
    PURCHASE = "purchase"  # Token purchase via Stripe
    REFUND = "refund"  # Refund for failed generation
    GRANT = "grant"  # Admin grant or promotion
    MONTHLY_RESET = "monthly_reset"  # Monthly free token reset


class Transaction(Base):
    """
    Immutable audit log for all token operations.

    This table is append-only. Never UPDATE or DELETE records.
    """

    __tablename__ = "transactions"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Foreign key to user
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Transaction details
    type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType), nullable=False, index=True
    )
    tokens_delta: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # Positive for add, negative for deduct

    # External references
    stripe_event_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )  # For Stripe webhook idempotency

    # Additional context (JSON) - Note: 'metadata' is reserved by SQLAlchemy
    tx_metadata: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSONB, nullable=True
    )  # map_id, theme_id, etc.

    # Timestamp (immutable)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="transactions")

    def __repr__(self) -> str:
        return f"<Transaction(id={self.id}, type={self.type.value}, delta={self.tokens_delta})>"
