"""User model for authentication and profile management."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class User(Base):
    """
    User model for authentication.

    Supports both email/password and OAuth2 authentication.
    """

    __tablename__ = "users"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Email authentication
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # OAuth2 authentication
    oauth_provider: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # google, github, etc.
    oauth_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Account status
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    # Relationships
    token_balance: Mapped["TokenBalance"] = relationship(
        "TokenBalance", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="user", cascade="all, delete-orphan"
    )
    maps: Mapped[list["Map"]] = relationship(
        "Map", back_populates="user", cascade="all, delete-orphan"
    )
    generation_jobs: Mapped[list["GenerationJob"]] = relationship(
        "GenerationJob", back_populates="user", cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"
