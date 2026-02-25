"""Bloodbank event schemas for Overworld."""

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# Enums

class CustomizationType(str, Enum):
    """Types of map customizations."""

    THEME_APPLIED = "theme_applied"
    COLORS_CHANGED = "colors_changed"
    MARKER_ADDED = "marker_added"
    MARKER_REMOVED = "marker_removed"
    MARKER_UPDATED = "marker_updated"
    WATERMARK_TOGGLED = "watermark_toggled"
    NAME_CHANGED = "name_changed"


class MarkerType(str, Enum):
    """Types of map markers."""

    PIN = "pin"
    LABEL = "label"
    ICON = "icon"
    REGION = "region"
    PATH = "path"
    CUSTOM = "custom"


class UserProfileUpdateType(str, Enum):
    """Types of user profile updates."""

    ACCOUNT_CREATED = "account_created"
    EMAIL_VERIFIED = "email_verified"
    OAUTH_LINKED = "oauth_linked"
    PREMIUM_ACTIVATED = "premium_activated"
    PREMIUM_DEACTIVATED = "premium_deactivated"
    PREFERENCES_CHANGED = "preferences_changed"
    HISTORY_MILESTONE = "history_milestone"


class HistoryMilestone(str, Enum):
    """User history milestones."""

    FIRST_MAP_CREATED = "first_map_created"
    MAPS_COUNT_10 = "maps_count_10"
    MAPS_COUNT_50 = "maps_count_50"
    MAPS_COUNT_100 = "maps_count_100"
    FIRST_EXPORT = "first_export"
    FIRST_PREMIUM_THEME = "first_premium_theme"
    FIRST_SHARED_MAP = "first_shared_map"
    CONSENSUS_FIRST_RUN = "consensus_first_run"


# Sub-schemas

class EventSource(BaseModel):
    """Event source metadata."""

    host: str
    app: str = "overworld"
    trigger_type: str  # "api", "webhook", "background_job", etc.


class ThemeEventData(BaseModel):
    """Theme-related event data."""

    theme_id: int
    theme_name: str
    is_premium: bool
    previous_theme_id: Optional[int] = None


class ColorOverride(BaseModel):
    """Color override data."""

    primary: Optional[str] = None
    secondary: Optional[str] = None
    background: Optional[str] = None
    text: Optional[str] = None


class ColorsEventData(BaseModel):
    """Color customization event data."""

    overrides: dict[str, str]  # Hex color map
    previous_overrides: Optional[dict[str, str]] = None


class MarkerPosition(BaseModel):
    """Marker position on map."""

    x: float
    y: float
    level: int  # L0-L4 hierarchy level
    parent_node_id: Optional[str] = None


class MarkerEventData(BaseModel):
    """Marker-related event data."""

    marker_id: str
    marker_type: MarkerType
    position: MarkerPosition
    label: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class WatermarkEventData(BaseModel):
    """Watermark toggle event data."""

    enabled: bool
    reason: Literal["premium_upgrade", "user_toggle"]


class AccountEventData(BaseModel):
    """Account-related event data."""

    email: Optional[str] = None
    oauth_provider: Optional[str] = None
    is_verified: Optional[bool] = None
    is_premium: Optional[bool] = None


class PreferencesEventData(BaseModel):
    """User preferences event data."""

    changed_fields: list[str]
    default_theme_id: Optional[int] = None
    default_map_visibility: Optional[str] = None
    color_mode: Optional[str] = None
    language: Optional[str] = None
    notifications_enabled: Optional[bool] = None
    auto_watermark: Optional[bool] = None


class HistoryEventData(BaseModel):
    """User history event data."""

    milestone: Optional[HistoryMilestone] = None
    total_maps_created: Optional[int] = None
    total_exports: Optional[int] = None
    member_since: Optional[datetime] = None


class PremiumEventData(BaseModel):
    """Premium status event data."""

    activated: bool
    plan: Optional[str] = None  # "campfire", "guild", "studio_plus"
    source: Optional[str] = None  # "stripe", "manual", "promo"
    token_balance: Optional[int] = None


# Main Event Models

class OverworldMapCustomizationV1(BaseModel):
    """Map customization event (Bloodbank routing key: overworld.map.customized)."""

    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: EventSource
    map_id: int
    user_id: int
    customization_type: CustomizationType
    theme: Optional[ThemeEventData] = None
    colors: Optional[ColorsEventData] = None
    marker: Optional[MarkerEventData] = None
    watermark: Optional[WatermarkEventData] = None


class OverworldUserProfileV1(BaseModel):
    """User profile update event (Bloodbank routing key: overworld.user.profile_updated)."""

    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: EventSource
    user_id: int
    update_type: UserProfileUpdateType
    account: Optional[AccountEventData] = None
    preferences: Optional[PreferencesEventData] = None
    history: Optional[HistoryEventData] = None
    premium: Optional[PremiumEventData] = None


# Legacy Export Event (already exists in codebase, adding for completeness)

class OverworldExportGeneratedV1(BaseModel):
    """Export generation event (Bloodbank routing key: overworld.export.generated)."""

    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: EventSource
    user_id: int
    export_id: int
    map_id: int
    format: str  # "png" | "svg"
    resolution: int
    watermarked: bool
    file_size_bytes: int
    theme_id: Optional[int] = None
