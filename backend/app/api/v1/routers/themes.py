"""API routes for theme management."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.map import Map
from app.models.theme import Theme
from app.models.user import User
from app.schemas.theme import (
    ApplyThemeRequest,
    ApplyThemeResponse,
    Theme as ThemeSchema,
    ThemeListResponse,
)
from app.services.bloodbank_emitter import emit_map_customization_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/themes", tags=["themes"])


@router.get(
    "",
    response_model=ThemeListResponse,
    summary="List available themes",
    description="Get all available themes, optionally filtered by premium status",
)
async def list_themes(
    is_premium: Optional[bool] = Query(None, description="Filter by premium status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> ThemeListResponse:
    """List all available themes.

    Free users can see all themes but cannot apply premium themes.
    Premium users can apply any theme.

    Args:
        is_premium: Filter by premium status (None = all)
        limit: Maximum number of results
        offset: Number of results to skip
        db: Database session

    Returns:
        ThemeListResponse with filtered themes
    """
    # Build query
    stmt = select(Theme)

    if is_premium is not None:
        stmt = stmt.where(Theme.is_premium == is_premium)

    stmt = stmt.offset(offset).limit(limit)

    result = await db.execute(stmt)
    themes = result.scalars().all()

    # Count total (without pagination)
    count_stmt = select(Theme)
    if is_premium is not None:
        count_stmt = count_stmt.where(Theme.is_premium == is_premium)

    count_result = await db.execute(count_stmt)
    total = len(count_result.scalars().all())

    return ThemeListResponse(
        themes=[ThemeSchema.model_validate(t) for t in themes],
        total=total,
    )


@router.get(
    "/{theme_id}",
    response_model=ThemeSchema,
    summary="Get theme details",
    description="Get detailed information about a specific theme",
)
async def get_theme(
    theme_id: int,
    db: AsyncSession = Depends(get_db),
) -> ThemeSchema:
    """Get theme by ID.

    Args:
        theme_id: Theme ID
        db: Database session

    Returns:
        Theme details

    Raises:
        HTTPException(404): If theme not found
    """
    stmt = select(Theme).where(Theme.id == theme_id)
    result = await db.execute(stmt)
    theme = result.scalar_one_or_none()

    if not theme:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Theme {theme_id} not found",
        )

    return ThemeSchema.model_validate(theme)


@router.post(
    "/{theme_id}/apply/{map_id}",
    response_model=ApplyThemeResponse,
    summary="Apply theme to map",
    description="Apply a theme to a map (requires ownership, premium for premium themes)",
)
async def apply_theme_to_map(
    theme_id: int,
    map_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplyThemeResponse:
    """Apply a theme to a map.

    Args:
        theme_id: Theme to apply
        map_id: Map to apply theme to
        current_user: Authenticated user
        db: Database session

    Returns:
        ApplyThemeResponse with operation result

    Raises:
        HTTPException(404): If theme or map not found
        HTTPException(403): If user doesn't own map or lacks premium for premium theme
    """
    # Get theme
    theme_stmt = select(Theme).where(Theme.id == theme_id)
    theme_result = await db.execute(theme_stmt)
    theme = theme_result.scalar_one_or_none()

    if not theme:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Theme {theme_id} not found",
        )

    # Get map
    map_stmt = select(Map).where(Map.id == map_id, Map.user_id == current_user.id)
    map_result = await db.execute(map_stmt)
    map_obj = map_result.scalar_one_or_none()

    if not map_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Map {map_id} not found or access denied",
        )

    # Check premium requirement
    if theme.is_premium and not current_user.is_premium:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Premium theme requires active subscription",
        )

    # Store previous theme for revert capability
    previous_theme_id = map_obj.theme_id

    # Apply theme
    map_obj.theme_id = theme_id
    await db.commit()
    await db.refresh(map_obj)

    logger.info(
        f"Applied theme {theme_id} to map {map_id} for user {current_user.id}"
    )

    # Emit Bloodbank event
    try:
        await emit_map_customization_event(
            db=db,
            map_id=map_id,
            user_id=current_user.id,
            customization_type="theme_applied",
            theme_data={
                "theme_id": theme_id,
                "theme_name": theme.name,
                "is_premium": theme.is_premium,
                "previous_theme_id": previous_theme_id,
            },
        )
    except Exception as e:
        logger.error(f"Failed to emit map customization event: {e}")
        # Don't fail the request if event emission fails

    return ApplyThemeResponse(
        success=True,
        map_id=map_id,
        theme_id=theme_id,
        theme_name=theme.name,
        previous_theme_id=previous_theme_id,
        message=f"Theme '{theme.name}' applied successfully",
    )
