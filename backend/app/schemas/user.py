"""Pydantic schemas for user profile endpoints.

Maps to Holyfields: overworld/user_profile.v1.json
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Profile preferences
# ---------------------------------------------------------------------------


class UserPreferencesUpdate(BaseModel):
    """Request to update user preferences."""

    default_theme_id: Optional[int] = Field(None, gt=0, description="Default theme ID for new maps")
    default_map_visibility: Optional[str] = Field(
        None, pattern="^(private|unlisted|public)$", description="Default visibility for new maps"
    )
    color_mode: Optional[str] = Field(
        None, pattern="^(light|dark|system)$", description="UI color mode"
    )
    language: Optional[str] = Field(
        None, pattern="^[a-z]{2}(-[A-Z]{2})?$", description="ISO 639-1 language code"
    )
    notifications_enabled: Optional[bool] = Field(None, description="Enable email notifications")
    email_marketing: Optional[bool] = Field(None, description="Enable marketing emails")
    auto_watermark: Optional[bool] = Field(None, description="Auto-apply watermark on free-tier maps")


class UserPreferencesResponse(BaseModel):
    """Current user preferences."""

    model_config = ConfigDict(from_attributes=True)

    default_theme_id: Optional[int] = None
    default_map_visibility: str = "private"
    color_mode: str = "system"
    language: str = "en"
    notifications_enabled: bool = True
    email_marketing: bool = False
    auto_watermark: bool = True


# ---------------------------------------------------------------------------
# Profile (full)
# ---------------------------------------------------------------------------


class UserProfileResponse(BaseModel):
    """Full user profile with preferences and history."""

    model_config = ConfigDict(from_attributes=True)

    # Identity (from User)
    id: int
    email: str
    is_verified: bool
    is_premium: bool
    oauth_provider: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Preferences (from UserProfile)
    preferences: UserPreferencesResponse

    # History
    history: "UserHistoryResponse"


class UserHistoryResponse(BaseModel):
    """User activity history summary."""

    total_maps_created: int = 0
    total_exports: int = 0
    member_since: datetime


class UserProfileUpdateResponse(BaseModel):
    """Response after updating profile preferences."""

    success: bool
    changed_fields: list[str]
    preferences: UserPreferencesResponse


# ---------------------------------------------------------------------------
# Milestone tracking
# ---------------------------------------------------------------------------


class MilestoneResponse(BaseModel):
    """A user milestone event."""

    milestone: str
    reached_at: datetime
    total_maps_created: int
    total_exports: int
