"""Theme schemas for map customization."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ThemePalette(BaseModel):
    """Color palette for a theme."""

    primary: str = Field(..., pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary: str = Field(..., pattern=r"^#[0-9A-Fa-f]{6}$")
    background: str = Field(..., pattern=r"^#[0-9A-Fa-f]{6}$")
    surface: str = Field(..., pattern=r"^#[0-9A-Fa-f]{6}$")
    text: str = Field(..., pattern=r"^#[0-9A-Fa-f]{6}$")
    text_secondary: str = Field(..., pattern=r"^#[0-9A-Fa-f]{6}$")
    accent: str = Field(..., pattern=r"^#[0-9A-Fa-f]{6}$")
    success: str = Field(..., pattern=r"^#[0-9A-Fa-f]{6}$")
    warning: str = Field(..., pattern=r"^#[0-9A-Fa-f]{6}$")
    error: str = Field(..., pattern=r"^#[0-9A-Fa-f]{6}$")


class ThemeTypography(BaseModel):
    """Typography settings for a theme."""

    heading_font: str
    body_font: str
    mono_font: str


class ThemeIcons(BaseModel):
    """Icon URLs for a theme."""

    milestone: str
    region: str
    road: str


class ThemeEffects(BaseModel):
    """Visual effects for a theme."""

    drop_shadow: bool = True
    gradient_overlays: bool = False
    particle_effects: bool = False


class ThemeAssetManifest(BaseModel):
    """Complete asset manifest for a theme."""

    version: str = "1.0"
    palette: ThemePalette
    typography: ThemeTypography
    icons: ThemeIcons
    backgrounds: list[str] = Field(default_factory=list)
    effects: ThemeEffects = Field(default_factory=ThemeEffects)


class ThemeBase(BaseModel):
    """Base theme model (matches actual DB schema)."""

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_premium: bool = False
    asset_manifest: ThemeAssetManifest


class ThemeCreate(ThemeBase):
    """Schema for creating a theme."""

    pass


class ThemeUpdate(BaseModel):
    """Schema for updating a theme."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_premium: Optional[bool] = None
    asset_manifest: Optional[ThemeAssetManifest] = None


class Theme(ThemeBase):
    """Full theme model with metadata."""

    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ThemeListResponse(BaseModel):
    """Response for theme listing."""

    themes: list[Theme]
    total: int


class ApplyThemeRequest(BaseModel):
    """Request to apply a theme to a map."""

    theme_id: int = Field(..., gt=0)


class ApplyThemeResponse(BaseModel):
    """Response after applying a theme."""

    success: bool
    map_id: int
    theme_id: int
    theme_name: str
    previous_theme_id: Optional[int] = None
    message: str
