"""Icon schema definitions for map icon placement.

This module defines the data structures for:
- Icon categories (buildings, nature, landmarks, etc.)
- Icon metadata (name, size, anchor point)
- Icon placements with positions and collision info
- 8/16-bit style icon references
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class IconCategory(str, Enum):
    """Categories for icon classification."""

    BUILDING = "building"  # Buildings, houses, castles
    NATURE = "nature"  # Trees, rocks, mountains
    LANDMARK = "landmark"  # Significant locations, monuments
    MILESTONE = "milestone"  # Progress markers on the road
    DECORATION = "decoration"  # Decorative elements
    INTERACTIVE = "interactive"  # Clickable/interactive elements
    OBSTACLE = "obstacle"  # Obstacles, enemies, hazards
    COLLECTIBLE = "collectible"  # Items, coins, power-ups


class IconStyle(str, Enum):
    """Visual style for icons."""

    PIXEL_8BIT = "8bit"  # Classic 8-bit pixel art
    PIXEL_16BIT = "16bit"  # 16-bit enhanced pixel art
    RETRO = "retro"  # Mixed retro style


class AnchorPoint(str, Enum):
    """Anchor point for icon positioning."""

    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    CENTER_LEFT = "center_left"
    CENTER = "center"
    CENTER_RIGHT = "center_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"


class IconSize(BaseModel):
    """Size dimensions for an icon."""

    width: int = Field(..., ge=1, description="Icon width in pixels")
    height: int = Field(..., ge=1, description="Icon height in pixels")


class IconMetadata(BaseModel):
    """Metadata for a single icon definition.

    Defines the properties of an icon type in the icon library.
    """

    id: str = Field(..., description="Unique icon identifier")
    name: str = Field(..., description="Human-readable icon name")
    category: IconCategory = Field(..., description="Icon category")
    style: IconStyle = Field(default=IconStyle.PIXEL_8BIT, description="Visual style")
    size: IconSize = Field(..., description="Icon dimensions")
    anchor: AnchorPoint = Field(
        default=AnchorPoint.BOTTOM_CENTER,
        description="Anchor point for positioning",
    )
    sprite_path: Optional[str] = Field(
        default=None, description="Path to sprite asset"
    )
    z_index: int = Field(default=0, description="Rendering layer order")
    tags: list[str] = Field(default_factory=list, description="Searchable tags")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class Position(BaseModel):
    """2D position coordinates."""

    x: float = Field(..., description="X coordinate")
    y: float = Field(..., description="Y coordinate")


class BoundingBox(BaseModel):
    """Axis-aligned bounding box for collision detection."""

    x: float = Field(..., description="Top-left X coordinate")
    y: float = Field(..., description="Top-left Y coordinate")
    width: float = Field(..., ge=0, description="Box width")
    height: float = Field(..., ge=0, description="Box height")

    @property
    def right(self) -> float:
        """Get right edge X coordinate."""
        return self.x + self.width

    @property
    def bottom(self) -> float:
        """Get bottom edge Y coordinate."""
        return self.y + self.height

    @property
    def center(self) -> Position:
        """Get center point of the bounding box."""
        return Position(x=self.x + self.width / 2, y=self.y + self.height / 2)

    def contains_point(self, point: Position) -> bool:
        """Check if a point is inside this bounding box."""
        return (
            self.x <= point.x <= self.right and self.y <= point.y <= self.bottom
        )

    def intersects(self, other: "BoundingBox") -> bool:
        """Check if this bounding box intersects with another."""
        return not (
            self.right < other.x
            or other.right < self.x
            or self.bottom < other.y
            or other.bottom < self.y
        )


class IconPlacement(BaseModel):
    """A placed icon instance on the map.

    Represents a specific icon placed at a position with associated data.
    """

    id: str = Field(..., description="Unique placement identifier")
    icon_id: str = Field(..., description="Reference to icon metadata ID")
    position: Position = Field(..., description="Icon position on map")
    bounding_box: BoundingBox = Field(..., description="Collision bounding box")
    rotation: float = Field(default=0.0, description="Rotation in degrees")
    scale: float = Field(default=1.0, ge=0.1, le=10.0, description="Scale factor")
    label: Optional[str] = Field(default=None, description="Optional label text")
    data: dict[str, Any] = Field(
        default_factory=dict, description="Additional custom data"
    )
    priority: int = Field(
        default=0, description="Placement priority (higher = placed first)"
    )
    category: IconCategory = Field(
        default=IconCategory.MILESTONE, description="Icon category"
    )

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class IconLibrary(BaseModel):
    """Collection of icon definitions.

    Represents the complete icon library available for map generation.
    """

    name: str = Field(..., description="Library name")
    version: str = Field(default="1.0.0", description="Library version")
    style: IconStyle = Field(default=IconStyle.PIXEL_8BIT, description="Default style")
    icons: list[IconMetadata] = Field(
        default_factory=list, description="Available icons"
    )

    def get_icon(self, icon_id: str) -> Optional[IconMetadata]:
        """Get an icon by ID."""
        for icon in self.icons:
            if icon.id == icon_id:
                return icon
        return None

    def get_by_category(self, category: IconCategory) -> list[IconMetadata]:
        """Get all icons in a category."""
        return [icon for icon in self.icons if icon.category == category]

    def get_by_tags(self, tags: list[str]) -> list[IconMetadata]:
        """Get icons matching any of the given tags."""
        result = []
        for icon in self.icons:
            if any(tag in icon.tags for tag in tags):
                result.append(icon)
        return result


class PlacementResult(BaseModel):
    """Result of icon placement operation.

    Contains the placed icons and any placement statistics.
    """

    success: bool = Field(..., description="Whether placement succeeded")
    placements: list[IconPlacement] = Field(
        default_factory=list, description="Placed icons"
    )
    total_icons: int = Field(default=0, description="Total icons placed")
    collisions_avoided: int = Field(
        default=0, description="Number of collisions avoided"
    )
    out_of_bounds_adjusted: int = Field(
        default=0, description="Icons adjusted for boundary"
    )
    error_message: Optional[str] = Field(
        default=None, description="Error message if failed"
    )
    statistics: dict[str, Any] = Field(
        default_factory=dict, description="Placement statistics"
    )


class PlacementConfig(BaseModel):
    """Configuration for icon placement algorithm.

    Controls spacing, grid settings, and placement behavior.
    """

    min_spacing: float = Field(
        default=50.0, ge=0, description="Minimum spacing between icons"
    )
    use_grid: bool = Field(
        default=False, description="Use grid-based placement"
    )
    grid_cell_size: float = Field(
        default=64.0, ge=16, description="Grid cell size for grid placement"
    )
    canvas_width: int = Field(default=1920, ge=100, description="Canvas width")
    canvas_height: int = Field(default=1080, ge=100, description="Canvas height")
    margin: int = Field(
        default=100, ge=0, description="Margin from canvas edges"
    )
    road_buffer: float = Field(
        default=30.0, ge=0, description="Buffer distance from road path"
    )
    priority_placement: bool = Field(
        default=True, description="Place higher priority icons first"
    )
    allow_overlap: bool = Field(
        default=False, description="Allow icon overlap"
    )
    max_attempts: int = Field(
        default=10, ge=1, description="Max attempts to find valid position"
    )


# Default icon library for SMB3 theme
DEFAULT_SMB3_ICONS = IconLibrary(
    name="Super Mario Bros 3 Style",
    version="1.0.0",
    style=IconStyle.PIXEL_8BIT,
    icons=[
        IconMetadata(
            id="milestone_circle",
            name="Numbered Circle",
            category=IconCategory.MILESTONE,
            size=IconSize(width=48, height=48),
            anchor=AnchorPoint.CENTER,
            tags=["milestone", "numbered", "progress"],
        ),
        IconMetadata(
            id="castle",
            name="Castle",
            category=IconCategory.LANDMARK,
            size=IconSize(width=96, height=96),
            anchor=AnchorPoint.BOTTOM_CENTER,
            tags=["building", "boss", "end"],
        ),
        IconMetadata(
            id="tree_small",
            name="Small Tree",
            category=IconCategory.NATURE,
            size=IconSize(width=32, height=48),
            anchor=AnchorPoint.BOTTOM_CENTER,
            tags=["nature", "decoration"],
        ),
        IconMetadata(
            id="tree_large",
            name="Large Tree",
            category=IconCategory.NATURE,
            size=IconSize(width=48, height=64),
            anchor=AnchorPoint.BOTTOM_CENTER,
            tags=["nature", "decoration"],
        ),
        IconMetadata(
            id="rock",
            name="Rock",
            category=IconCategory.NATURE,
            size=IconSize(width=32, height=24),
            anchor=AnchorPoint.BOTTOM_CENTER,
            tags=["nature", "obstacle"],
        ),
        IconMetadata(
            id="house_small",
            name="Small House",
            category=IconCategory.BUILDING,
            size=IconSize(width=48, height=48),
            anchor=AnchorPoint.BOTTOM_CENTER,
            tags=["building", "town"],
        ),
        IconMetadata(
            id="bridge",
            name="Bridge",
            category=IconCategory.LANDMARK,
            size=IconSize(width=64, height=32),
            anchor=AnchorPoint.CENTER,
            tags=["path", "crossing"],
        ),
        IconMetadata(
            id="mushroom_house",
            name="Mushroom House",
            category=IconCategory.INTERACTIVE,
            size=IconSize(width=48, height=56),
            anchor=AnchorPoint.BOTTOM_CENTER,
            tags=["bonus", "interactive", "powerup"],
        ),
        IconMetadata(
            id="star",
            name="Star",
            category=IconCategory.COLLECTIBLE,
            size=IconSize(width=32, height=32),
            anchor=AnchorPoint.CENTER,
            tags=["collectible", "bonus"],
        ),
        IconMetadata(
            id="coin",
            name="Coin",
            category=IconCategory.COLLECTIBLE,
            size=IconSize(width=24, height=24),
            anchor=AnchorPoint.CENTER,
            tags=["collectible", "currency"],
        ),
    ],
)
