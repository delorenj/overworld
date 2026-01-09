"""Token balance model for user token tracking."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class TokenBalance(Base):
    """
    Token balance for each user.

    Tracks free tokens (monthly reset) and purchased tokens (persistent).
    """

    __tablename__ = "token_balance"

    # Primary key (one-to-one with user)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )

    # Token counts
    free_tokens: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    purchased_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Monthly reset tracking
    last_reset_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="token_balance")

    @property
    def total_tokens(self) -> int:
        """Total available tokens."""
        return self.free_tokens + self.purchased_tokens

    def __repr__(self) -> str:
        return f"<TokenBalance(user_id={self.user_id}, total={self.total_tokens})>"
