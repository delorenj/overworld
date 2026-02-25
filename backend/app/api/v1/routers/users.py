"""API router for user management and profile endpoints.

Endpoints:
  GET    /users/me/profile       — Get full profile (identity + preferences + history)
  PATCH  /users/me/preferences   — Update preferences
  GET    /users/me/preferences   — Get preferences only
  DELETE /users/me/accounts/{provider} — Disconnect OAuth provider

Bloodbank events emitted:
  overworld.user.profile_updated (update_type=preferences_changed)

Related Holyfields schema: overworld/user_profile.v1.json
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.user import (
    UserPreferencesUpdate,
    UserPreferencesResponse,
    UserProfileResponse,
    UserProfileUpdateResponse,
    UserHistoryResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_or_create_profile(
    user: User, db: AsyncSession
) -> UserProfile:
    """Get user's profile, creating it if it doesn't exist."""
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        profile = UserProfile(user_id=user.id)
        db.add(profile)
        await db.flush()
        logger.info(f"Created profile for user {user.id}")

    return profile


def _profile_to_preferences(profile: UserProfile) -> UserPreferencesResponse:
    """Convert profile model to preferences response."""
    return UserPreferencesResponse(
        default_theme_id=profile.default_theme_id,
        default_map_visibility=profile.default_map_visibility,
        color_mode=profile.color_mode,
        language=profile.language,
        notifications_enabled=profile.notifications_enabled,
        email_marketing=profile.email_marketing,
        auto_watermark=profile.auto_watermark,
    )


# ---------------------------------------------------------------------------
# Profile endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/me/profile",
    response_model=UserProfileResponse,
    summary="Get current user's full profile",
    description="Returns identity, preferences, and activity history.",
)
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    profile = await _get_or_create_profile(current_user, db)
    await db.commit()

    preferences = _profile_to_preferences(profile)
    history = UserHistoryResponse(
        total_maps_created=profile.total_maps_created,
        total_exports=profile.total_exports,
        member_since=current_user.created_at,
    )

    return UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        is_verified=current_user.is_verified,
        is_premium=current_user.is_premium,
        oauth_provider=current_user.oauth_provider,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        preferences=preferences,
        history=history,
    )


@router.get(
    "/me/preferences",
    response_model=UserPreferencesResponse,
    summary="Get current user's preferences",
)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserPreferencesResponse:
    profile = await _get_or_create_profile(current_user, db)
    await db.commit()
    return _profile_to_preferences(profile)


@router.patch(
    "/me/preferences",
    response_model=UserProfileUpdateResponse,
    summary="Update user preferences",
    description="Partial update — only fields present in the request body are changed.",
)
async def update_preferences(
    body: UserPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfileUpdateResponse:
    profile = await _get_or_create_profile(current_user, db)

    # Apply only the fields that were explicitly set
    changed_fields: list[str] = []
    update_data = body.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    # Premium guard: free-tier users can't disable watermark
    if "auto_watermark" in update_data and not update_data["auto_watermark"]:
        if not current_user.is_premium:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Disabling watermark requires a premium subscription",
            )

    for field_name, value in update_data.items():
        current_value = getattr(profile, field_name, None)
        if current_value != value:
            setattr(profile, field_name, value)
            changed_fields.append(field_name)

    if changed_fields:
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
        logger.info(
            f"User {current_user.id} updated preferences: {changed_fields}"
        )
        # TODO: Emit overworld.user.profile_updated event via Bloodbank
        # (uncomment when emitter is wired in)

    return UserProfileUpdateResponse(
        success=True,
        changed_fields=changed_fields,
        preferences=_profile_to_preferences(profile),
    )


# ---------------------------------------------------------------------------
# OAuth disconnect (existing)
# ---------------------------------------------------------------------------

@router.delete(
    "/me/accounts/{provider}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect a linked social account",
    description="Disconnect a linked OAuth provider (e.g., Google, GitHub).",
)
async def disconnect_account(
    provider: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    if current_user.oauth_provider != provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User is not linked to {provider}",
        )

    if not current_user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot disconnect the only login method. Please set a password first.",
        )

    logger.info(f"Disconnecting {provider} account for user {current_user.id}")
    current_user.oauth_provider = None
    current_user.oauth_id = None
    db.add(current_user)
    await db.commit()
    return None
