"""Pydantic schemas for token API endpoints.

This module defines request and response models for:
- Token balance queries
- Transaction history
- Cost estimation
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.transaction import TransactionType


class TokenBalanceResponse(BaseModel):
    """Response model for token balance queries."""

    free_tokens: int = Field(description="Free tokens (monthly reset)")
    purchased_tokens: int = Field(description="Purchased tokens (persistent)")
    total_tokens: int = Field(description="Total available tokens")
    last_reset_at: datetime = Field(description="Last monthly reset timestamp")
    is_low_balance: bool = Field(description="True if balance is below warning threshold")

    class Config:
        from_attributes = True


class TransactionResponse(BaseModel):
    """Response model for a single transaction."""

    id: int = Field(description="Transaction ID")
    type: TransactionType = Field(description="Transaction type")
    tokens_delta: int = Field(description="Token change (positive=add, negative=deduct)")
    metadata: Optional[dict] = Field(default=None, description="Additional transaction context")
    created_at: datetime = Field(description="Transaction timestamp")

    class Config:
        from_attributes = True


class TransactionHistoryResponse(BaseModel):
    """Response model for transaction history queries."""

    transactions: list[TransactionResponse] = Field(description="List of transactions")
    total: int = Field(description="Total number of transactions")
    limit: int = Field(description="Page size limit")
    offset: int = Field(description="Current offset")


class CostBreakdown(BaseModel):
    """Breakdown of cost calculation."""

    base_cost: int = Field(description="Minimum base cost")
    size_cost: int = Field(description="Cost based on file size")
    total: int = Field(description="Total calculated cost")
    capped: bool = Field(default=False, description="Whether cost was capped at maximum")


class CostEstimateRequest(BaseModel):
    """Request model for cost estimation."""

    document_id: Optional[str] = Field(
        default=None,
        description="Document ID to estimate cost for"
    )
    file_size_bytes: Optional[int] = Field(
        default=None,
        ge=0,
        description="Direct file size in bytes"
    )


class CostEstimateResponse(BaseModel):
    """Response model for cost estimation."""

    estimated_cost: int = Field(description="Estimated token cost")
    file_size_bytes: Optional[int] = Field(description="File size used for calculation")
    breakdown: CostBreakdown = Field(description="Detailed cost breakdown")
    can_afford: bool = Field(default=True, description="Whether user can afford this cost")
    current_balance: Optional[int] = Field(
        default=None,
        description="User's current balance (if authenticated)"
    )


class InsufficientBalanceResponse(BaseModel):
    """Response model when user has insufficient balance."""

    detail: str = Field(description="Error message")
    required: int = Field(description="Tokens required for operation")
    available: int = Field(description="Tokens currently available")
    shortfall: int = Field(description="Additional tokens needed")
