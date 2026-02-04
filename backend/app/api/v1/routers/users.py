"""API router for user management endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


@router.delete(
    "/me/accounts/{provider}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect a linked social account",
    description="Disconnect a linked OAuth provider (e.g., Google, GitHub) from the current user's account.",
)
async def disconnect_account(
    provider: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Disconnect a linked social account.

    Args:
        provider: The provider to disconnect (e.g., "google", "github")
        current_user: The currently authenticated user
        db: Database session

    Raises:
        HTTPException: 400 if the provider is not linked
        HTTPException: 400 if trying to disconnect the only login method
    """
    # Check if the provider matches the user's linked provider
    normalized_provider = provider.lower()
    if current_user.oauth_provider != normalized_provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User is not linked to {provider}",
        )

    # Check if this is the only login method
    # If the user has no password set, they cannot disconnect their only OAuth provider
    if not current_user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot disconnect the only login method. Please set a password first.",
        )

    # Disconnect the account
    logger.info(f"Disconnecting {normalized_provider} account for user {current_user.id}")

    current_user.oauth_provider = None
    current_user.oauth_id = None

    db.add(current_user)
    await db.commit()

    return None
