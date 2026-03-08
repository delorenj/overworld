"""API routes for token management.

This module provides REST endpoints for:
- GET /api/v1/tokens/balance - Get current balance
- GET /api/v1/tokens/history - Get transaction history
- POST /api/v1/tokens/estimate - Estimate job cost
"""

from typing import Optional, Union

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    build_anonymous_client_hash,
    get_current_user,
    get_db,
    get_optional_user,
    require_admin_api_key,
)
from app.models.user import User
from app.models.transaction import TransactionType
from app.schemas.token import (
    AdminCreditRequest,
    AdminCreditResponse,
    AnonymousBalanceResponse,
    CostBreakdown,
    CostEstimateRequest,
    CostEstimateResponse,
    TokenBalanceResponse,
    TransactionHistoryResponse,
    TransactionResponse,
)
from app.services.token_service import (
    ANONYMOUS_OPERATION_EXPORT,
    AnonymousFreeTierExceededError,
    get_token_service,
)

router = APIRouter(prefix="/tokens", tags=["tokens"])


@router.get(
    "/balance",
    response_model=Union[TokenBalanceResponse, AnonymousBalanceResponse],
    summary="Get token balance",
    description="Get token balance for authenticated users, or free-tier balance for anonymous users",
)
async def get_balance(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
    x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID"),
) -> Union[TokenBalanceResponse, AnonymousBalanceResponse]:
    """Get token balance for authenticated or anonymous users."""
    token_service = get_token_service(db)

    if current_user:
        balance_details = await token_service.get_balance_details(current_user.id)
        return TokenBalanceResponse(
            free_tokens=balance_details["free_tokens"],
            purchased_tokens=balance_details["purchased_tokens"],
            total_tokens=balance_details["total_tokens"],
            last_reset_at=balance_details["last_reset_at"],
            is_low_balance=balance_details["is_low_balance"],
        )

    client_hash = build_anonymous_client_hash(request, x_session_id)
    anon_balance = await token_service.get_anonymous_balance(
        client_id_hash=client_hash,
        operation=ANONYMOUS_OPERATION_EXPORT,
    )

    return AnonymousBalanceResponse(**anon_balance)


@router.get(
    "/history",
    response_model=TransactionHistoryResponse,
    summary="Get transaction history",
    description="Get paginated transaction history for the authenticated user",
)
async def get_history(
    transaction_type: Optional[TransactionType] = Query(
        default=None,
        description="Filter by transaction type",
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of transactions to return",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Offset for pagination",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionHistoryResponse:
    """Get transaction history for the current user.

    Supports pagination and filtering by transaction type.

    Args:
        transaction_type: Optional filter by type (GENERATION, PURCHASE, etc.)
        limit: Maximum transactions to return (1-100)
        offset: Pagination offset
        current_user: Authenticated user
        db: Database session

    Returns:
        TransactionHistoryResponse with paginated transactions
    """
    token_service = get_token_service(db)
    transactions, total = await token_service.get_transaction_history(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        transaction_type=transaction_type,
    )

    transaction_responses = [
        TransactionResponse(
            id=tx.id,
            type=tx.type,
            tokens_delta=tx.tokens_delta,
            metadata=tx.tx_metadata,
            created_at=tx.created_at,
        )
        for tx in transactions
    ]

    return TransactionHistoryResponse(
        transactions=transaction_responses,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/estimate",
    response_model=CostEstimateResponse,
    summary="Estimate job cost",
    description="Estimate the token cost for a generation job",
)
async def estimate_cost(
    request: CostEstimateRequest,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> CostEstimateResponse:
    """Estimate the token cost for a generation job.

    Cost is calculated based on document size:
    - Minimum cost: 1 token
    - Size-based: ~0.1 tokens per KB
    - Maximum cost: 50 tokens (cap)

    Args:
        request: Cost estimation request with document_id or file_size_bytes
        current_user: Optional authenticated user (for balance check)
        db: Database session

    Returns:
        CostEstimateResponse with estimated cost and breakdown
    """
    token_service = get_token_service(db)

    # Estimate cost
    estimate = await token_service.estimate_job_cost(
        document_id=request.document_id,
        file_size_bytes=request.file_size_bytes,
    )

    # Check if user can afford it
    can_afford = True
    current_balance = None

    if current_user:
        current_balance = await token_service.get_balance(current_user.id)
        can_afford = current_balance >= estimate["estimated_cost"]

    return CostEstimateResponse(
        estimated_cost=estimate["estimated_cost"],
        file_size_bytes=estimate["file_size_bytes"],
        breakdown=CostBreakdown(**estimate["breakdown"]),
        can_afford=can_afford,
        current_balance=current_balance,
    )


@router.get(
    "/check/{amount}",
    response_model=dict,
    summary="Check sufficient balance",
    description="Check if user has sufficient balance for an amount",
)
async def check_balance(
    amount: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Check if user has sufficient balance for a specific amount.

    Args:
        amount: Required token amount
        current_user: Authenticated user
        db: Database session

    Returns:
        Dict with sufficient (bool), current_balance, and shortfall if insufficient
    """
    if amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amount must be positive",
        )

    token_service = get_token_service(db)
    current_balance = await token_service.get_balance(current_user.id)
    sufficient = current_balance >= amount

    result = {
        "sufficient": sufficient,
        "current_balance": current_balance,
        "required": amount,
    }

    if not sufficient:
        result["shortfall"] = amount - current_balance

    return result


@router.post(
    "/anonymous/consume-export",
    response_model=AnonymousBalanceResponse,
    summary="Consume anonymous free export",
    description="Consume one anonymous free-tier export credit tracked by session/IP",
)
async def consume_anonymous_export(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID"),
) -> AnonymousBalanceResponse:
    """Consume one anonymous export free-tier unit."""
    token_service = get_token_service(db)
    client_hash = build_anonymous_client_hash(request, x_session_id)

    try:
        result = await token_service.consume_anonymous_operation(
            client_id_hash=client_hash,
            operation=ANONYMOUS_OPERATION_EXPORT,
            amount=1,
        )
        return AnonymousBalanceResponse(**result)
    except AnonymousFreeTierExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message": "Anonymous free tier exhausted",
                "limit": e.limit,
                "used": e.used,
                "remaining": e.remaining,
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/credit",
    response_model=AdminCreditResponse,
    summary="Admin credit tokens",
    description="Credit tokens to a user balance (admin-only; webhook-ready)",
)
async def credit_tokens(
    payload: AdminCreditRequest,
    _: None = Depends(require_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> AdminCreditResponse:
    """Admin endpoint used to credit user tokens."""
    token_service = get_token_service(db)

    metadata = payload.metadata or {}
    if payload.reason:
        metadata["reason"] = payload.reason

    new_balance = await token_service.add_tokens(
        user_id=payload.user_id,
        amount=payload.amount,
        reason=TransactionType.GRANT,
        metadata=metadata,
    )

    return AdminCreditResponse(
        user_id=payload.user_id,
        amount=payload.amount,
        new_balance=new_balance,
    )
