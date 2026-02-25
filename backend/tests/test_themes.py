"""Integration tests for theme management endpoints."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.theme import Theme
from app.models.user import User
from app.models.map import Map


@pytest.mark.asyncio
async def test_list_themes(db_session: AsyncSession, test_theme):
    """Test listing themes returns all themes."""
    from app.api.v1.routers.themes import list_themes
    
    result = await list_themes(
        is_premium=None,
        limit=50,
        offset=0,
        db=db_session,
    )
    
    assert len(result.themes) >= 1
    assert result.total >= 1
    assert any(t.id == test_theme.id for t in result.themes)


@pytest.mark.asyncio
async def test_list_themes_premium_filter(db_session: AsyncSession, test_theme):
    """Test filtering themes by premium status."""
    # Create a premium theme
    premium_theme = Theme(
        name="Premium Theme Test",
        description="Test premium theme",
        is_premium=True,
        asset_manifest={
            "version": "1.0",
            "palette": {"primary": "#FF0000"},
            "typography": {"heading_font": "Inter"},
            "icons": {},
            "backgrounds": [],
            "effects": {},
        },
    )
    db_session.add(premium_theme)
    await db_session.commit()
    
    from app.api.v1.routers.themes import list_themes
    
    # Filter for premium only
    result = await list_themes(
        is_premium=True,
        limit=50,
        offset=0,
        db=db_session,
    )
    
    assert all(t.is_premium for t in result.themes)
    assert any(t.id == premium_theme.id for t in result.themes)


@pytest.mark.asyncio
async def test_get_theme(db_session: AsyncSession, test_theme):
    """Test getting a specific theme by ID."""
    from app.api.v1.routers.themes import get_theme
    
    result = await get_theme(
        theme_id=test_theme.id,
        db=db_session,
    )
    
    assert result.id == test_theme.id
    assert result.name == test_theme.name
    assert result.is_premium == test_theme.is_premium


@pytest.mark.asyncio
async def test_get_theme_not_found(db_session: AsyncSession):
    """Test getting a non-existent theme returns 404."""
    from fastapi import HTTPException
    from app.api.v1.routers.themes import get_theme
    
    with pytest.raises(HTTPException) as exc_info:
        await get_theme(theme_id=99999, db=db_session)
    
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_apply_theme_to_map(db_session: AsyncSession, test_theme, test_user):
    """Test applying a theme to a user's map."""
    # Create a map for the user
    map_obj = Map(
        user_id=test_user.id,
        theme_id=test_theme.id,
        name="Test Map",
        hierarchy={"title": "Test", "regions": []},
    )
    db_session.add(map_obj)
    await db_session.commit()
    await db_session.refresh(map_obj)
    
    # Create a different theme to apply
    new_theme = Theme(
        name="New Theme",
        description="Test",
        is_premium=False,
        asset_manifest={
            "version": "1.0",
            "palette": {"primary": "#00FF00"},
            "typography": {"heading_font": "Inter"},
            "icons": {},
            "backgrounds": [],
            "effects": {},
        },
    )
    db_session.add(new_theme)
    await db_session.commit()
    await db_session.refresh(new_theme)
    
    from app.api.v1.routers.themes import apply_theme_to_map
    
    result = await apply_theme_to_map(
        theme_id=new_theme.id,
        map_id=map_obj.id,
        current_user=test_user,
        db=db_session,
    )
    
    assert result.success is True
    assert result.map_id == map_obj.id
    assert result.theme_id == new_theme.id
    assert result.theme_name == new_theme.name
    assert result.previous_theme_id == test_theme.id
    
    # Verify map was updated
    await db_session.refresh(map_obj)
    assert map_obj.theme_id == new_theme.id


@pytest.mark.asyncio
async def test_apply_premium_theme_requires_premium(db_session: AsyncSession, test_user):
    """Test that applying a premium theme requires premium subscription."""
    # Create a premium theme
    premium_theme = Theme(
        name="Premium Theme",
        description="Premium only",
        is_premium=True,
        asset_manifest={
            "version": "1.0",
            "palette": {"primary": "#FF00FF"},
            "typography": {"heading_font": "Inter"},
            "icons": {},
            "backgrounds": [],
            "effects": {},
        },
    )
    db_session.add(premium_theme)
    
    # Create a free theme for the map
    free_theme = Theme(
        name="Free Theme",
        description="Free",
        is_premium=False,
        asset_manifest={
            "version": "1.0",
            "palette": {"primary": "#000000"},
            "typography": {"heading_font": "Inter"},
            "icons": {},
            "backgrounds": [],
            "effects": {},
        },
    )
    db_session.add(free_theme)
    await db_session.commit()
    await db_session.refresh(premium_theme)
    await db_session.refresh(free_theme)
    
    # Create a map for free user
    map_obj = Map(
        user_id=test_user.id,
        theme_id=free_theme.id,
        name="Test Map",
        hierarchy={"title": "Test", "regions": []},
    )
    db_session.add(map_obj)
    await db_session.commit()
    await db_session.refresh(map_obj)
    
    # Ensure user is free (not premium)
    test_user.is_premium = False
    await db_session.commit()
    
    from fastapi import HTTPException
    from app.api.v1.routers.themes import apply_theme_to_map
    
    # Try to apply premium theme as free user
    with pytest.raises(HTTPException) as exc_info:
        await apply_theme_to_map(
            theme_id=premium_theme.id,
            map_id=map_obj.id,
            current_user=test_user,
            db=db_session,
        )
    
    assert exc_info.value.status_code == 403
    assert "Premium theme requires active subscription" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_apply_premium_theme_allowed_for_premium_user(db_session: AsyncSession, test_user):
    """Test that premium users can apply premium themes."""
    # Create a premium theme
    premium_theme = Theme(
        name="Premium Theme 2",
        description="Premium only",
        is_premium=True,
        asset_manifest={
            "version": "1.0",
            "palette": {"primary": "#FF00FF"},
            "typography": {"heading_font": "Inter"},
            "icons": {},
            "backgrounds": [],
            "effects": {},
        },
    )
    db_session.add(premium_theme)
    
    # Create a free theme for the map
    free_theme = Theme(
        name="Free Theme 2",
        description="Free",
        is_premium=False,
        asset_manifest={
            "version": "1.0",
            "palette": {"primary": "#000000"},
            "typography": {"heading_font": "Inter"},
            "icons": {},
            "backgrounds": [],
            "effects": {},
        },
    )
    db_session.add(free_theme)
    await db_session.commit()
    await db_session.refresh(premium_theme)
    await db_session.refresh(free_theme)
    
    # Create a map
    map_obj = Map(
        user_id=test_user.id,
        theme_id=free_theme.id,
        name="Test Map",
        hierarchy={"title": "Test", "regions": []},
    )
    db_session.add(map_obj)
    
    # Make user premium
    test_user.is_premium = True
    await db_session.commit()
    await db_session.refresh(map_obj)
    
    from app.api.v1.routers.themes import apply_theme_to_map
    
    result = await apply_theme_to_map(
        theme_id=premium_theme.id,
        map_id=map_obj.id,
        current_user=test_user,
        db=db_session,
    )
    
    assert result.success is True
    assert result.theme_id == premium_theme.id
