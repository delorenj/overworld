"""Pydantic schemas for road generation and styling.

This module defines the data models for road definitions, including:
- Road types and visual styles
- Spline control points and segments
- Road intersections
- Complete road network definitions

These schemas are used by the RoadGeneratorAgent to output structured
road data for rendering by the frontend visualization system.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class RoadType(str, Enum):
    """Types of roads that can be generated.

    Each type has associated visual characteristics and semantic meaning.
    """

    DIRT_PATH = "dirt_path"  # Basic dirt trail, narrow
    GRAVEL_ROAD = "gravel_road"  # Gravel surface, medium width
    COBBLESTONE = "cobblestone"  # Stone-paved, medieval style
    PAVED_ROAD = "paved_road"  # Modern asphalt road
    HIGHWAY = "highway"  # Wide, multi-lane road
    TRAIL = "trail"  # Very narrow footpath
    BRIDGE = "bridge"  # Road segment over water/gap
    TUNNEL = "tunnel"  # Underground passage


class RoadStyle(BaseModel):
    """Visual style configuration for a road type.

    Defines how the road should be rendered, including colors,
    widths, borders, and texture hints.
    """

    model_config = ConfigDict(frozen=True)

    # Core visual properties
    width: float = Field(..., gt=0, description="Road width in pixels")
    color: str = Field(..., description="Primary road color (hex)")
    border_color: Optional[str] = Field(None, description="Border/edge color (hex)")
    border_width: float = Field(default=0, ge=0, description="Border width in pixels")

    # Texture and pattern
    texture_id: Optional[str] = Field(
        None, description="Texture identifier for rendering"
    )
    pattern: Optional[str] = Field(
        None, description="Pattern type (solid, dashed, dotted)"
    )
    pattern_spacing: float = Field(
        default=0, ge=0, description="Spacing for dashed/dotted patterns"
    )

    # Visual effects
    opacity: float = Field(default=1.0, ge=0.0, le=1.0, description="Road opacity")
    shadow: bool = Field(default=False, description="Whether to render shadow")
    shadow_offset: float = Field(default=2.0, description="Shadow offset in pixels")
    shadow_color: str = Field(default="#00000040", description="Shadow color with alpha")

    # Animation hints
    animated: bool = Field(default=False, description="Whether road has animation")
    animation_type: Optional[str] = Field(
        None, description="Animation type (flow, pulse, etc.)"
    )


# Predefined road styles for each road type
DEFAULT_ROAD_STYLES: dict[RoadType, RoadStyle] = {
    RoadType.DIRT_PATH: RoadStyle(
        width=8.0,
        color="#8B4513",
        border_color="#654321",
        border_width=1.0,
        texture_id="dirt",
        pattern="solid",
        opacity=0.9,
    ),
    RoadType.GRAVEL_ROAD: RoadStyle(
        width=12.0,
        color="#A0A0A0",
        border_color="#707070",
        border_width=1.5,
        texture_id="gravel",
        pattern="solid",
        opacity=0.95,
    ),
    RoadType.COBBLESTONE: RoadStyle(
        width=14.0,
        color="#696969",
        border_color="#4a4a4a",
        border_width=2.0,
        texture_id="cobblestone",
        pattern="solid",
        shadow=True,
    ),
    RoadType.PAVED_ROAD: RoadStyle(
        width=16.0,
        color="#2F2F2F",
        border_color="#FFD700",
        border_width=1.0,
        texture_id="asphalt",
        pattern="solid",
        shadow=True,
    ),
    RoadType.HIGHWAY: RoadStyle(
        width=24.0,
        color="#1a1a1a",
        border_color="#FFFFFF",
        border_width=2.0,
        texture_id="highway",
        pattern="dashed",
        pattern_spacing=10.0,
        shadow=True,
    ),
    RoadType.TRAIL: RoadStyle(
        width=4.0,
        color="#5D4037",
        border_color=None,
        border_width=0,
        texture_id="trail",
        pattern="dotted",
        pattern_spacing=3.0,
        opacity=0.7,
    ),
    RoadType.BRIDGE: RoadStyle(
        width=14.0,
        color="#8B7355",
        border_color="#4a3c2a",
        border_width=3.0,
        texture_id="wood_planks",
        pattern="solid",
        shadow=True,
        shadow_offset=4.0,
    ),
    RoadType.TUNNEL: RoadStyle(
        width=16.0,
        color="#2d2d2d",
        border_color="#1a1a1a",
        border_width=4.0,
        texture_id="stone",
        pattern="solid",
        opacity=0.85,
    ),
}


class ControlPoint(BaseModel):
    """A control point for spline-based road generation.

    Contains position and optional metadata for road path definition.
    """

    model_config = ConfigDict(frozen=False)

    x: float = Field(..., description="X coordinate")
    y: float = Field(..., description="Y coordinate")
    weight: float = Field(
        default=1.0, ge=0.0, description="Weight for curve influence"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    def to_tuple(self) -> tuple[float, float]:
        """Convert to simple tuple."""
        return (self.x, self.y)


class SplineConfig(BaseModel):
    """Configuration for Catmull-Rom spline generation.

    Controls the mathematical properties of the spline curve.
    """

    model_config = ConfigDict(frozen=True)

    # Spline parameters
    alpha: float = Field(
        default=0.5, ge=0.0, le=1.0,
        description="Parameterization type (0=uniform, 0.5=centripetal, 1=chordal)"
    )
    tension: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Curve tension (0=standard, higher=tighter)"
    )
    closed: bool = Field(
        default=False, description="Whether the spline forms a closed loop"
    )

    # Sampling parameters
    samples_per_segment: int = Field(
        default=20, ge=5, le=100,
        description="Number of points to generate per segment"
    )
    use_arc_length: bool = Field(
        default=True,
        description="Use arc-length parameterization for even spacing"
    )


class RoadSegment(BaseModel):
    """A segment of road between two control points.

    Contains the interpolated points and segment-specific styling.
    """

    model_config = ConfigDict(frozen=False)

    id: str = Field(default_factory=lambda: str(uuid4()), description="Segment ID")
    start_index: int = Field(..., ge=0, description="Start control point index")
    end_index: int = Field(..., ge=0, description="End control point index")

    # Interpolated points along this segment
    points: list[ControlPoint] = Field(
        default_factory=list,
        description="Interpolated points along the segment"
    )

    # Segment-specific overrides
    road_type_override: Optional[RoadType] = Field(
        None, description="Override road type for this segment"
    )
    style_override: Optional[RoadStyle] = Field(
        None, description="Override style for this segment"
    )

    # Segment metadata
    arc_length: float = Field(
        default=0.0, ge=0.0, description="Arc length of this segment"
    )


class IntersectionType(str, Enum):
    """Types of road intersections."""

    CROSSING = "crossing"  # Two roads crossing
    T_JUNCTION = "t_junction"  # One road joins another
    Y_JUNCTION = "y_junction"  # Road splits into two
    ROUNDABOUT = "roundabout"  # Circular intersection
    OVERPASS = "overpass"  # One road passes over another
    UNDERPASS = "underpass"  # One road passes under another


class Intersection(BaseModel):
    """Definition of a road intersection point.

    Represents where two or more roads meet or cross.
    """

    model_config = ConfigDict(frozen=False)

    id: str = Field(default_factory=lambda: str(uuid4()), description="Intersection ID")
    position: ControlPoint = Field(..., description="Intersection center point")
    intersection_type: IntersectionType = Field(
        default=IntersectionType.CROSSING,
        description="Type of intersection"
    )

    # Connected roads
    road_ids: list[str] = Field(
        default_factory=list,
        description="IDs of roads meeting at this intersection"
    )
    road_parameters: list[float] = Field(
        default_factory=list,
        description="Parameter values (0-1) where each road intersects"
    )

    # Visual properties
    radius: float = Field(
        default=10.0, gt=0,
        description="Radius of intersection area"
    )
    style: Optional[RoadStyle] = Field(
        None, description="Custom style for intersection"
    )

    # Metadata
    z_order: list[str] = Field(
        default_factory=list,
        description="Road IDs in z-order (bottom to top) for overlaps"
    )


class Road(BaseModel):
    """Complete road definition with spline path and styling.

    This is the primary output model for a single road in the network.
    """

    model_config = ConfigDict(frozen=False)

    id: str = Field(default_factory=lambda: str(uuid4()), description="Road ID")
    name: Optional[str] = Field(None, description="Optional road name")

    # Road type and style
    road_type: RoadType = Field(
        default=RoadType.DIRT_PATH,
        description="Type of road"
    )
    style: RoadStyle = Field(
        default_factory=lambda: DEFAULT_ROAD_STYLES[RoadType.DIRT_PATH],
        description="Visual style"
    )

    # Path definition
    control_points: list[ControlPoint] = Field(
        ..., min_length=2,
        description="Control points defining the road path"
    )
    spline_config: SplineConfig = Field(
        default_factory=SplineConfig,
        description="Spline configuration"
    )

    # Generated path data
    segments: list[RoadSegment] = Field(
        default_factory=list,
        description="Road segments with interpolated points"
    )
    total_arc_length: float = Field(
        default=0.0, ge=0.0,
        description="Total arc length of the road"
    )

    # Connections
    connected_landmark_ids: list[str] = Field(
        default_factory=list,
        description="IDs of landmarks this road connects"
    )

    # Metadata
    priority: int = Field(
        default=0, ge=0,
        description="Rendering priority (higher = on top)"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )

    def get_all_points(self) -> list[ControlPoint]:
        """Get all interpolated points across all segments."""
        points: list[ControlPoint] = []
        for segment in self.segments:
            points.extend(segment.points)
        return points


class RoadNetwork(BaseModel):
    """Complete road network for a map.

    Contains all roads, intersections, and network-level metadata.
    This is the primary output schema for the RoadGeneratorAgent.
    """

    model_config = ConfigDict(frozen=False)

    # Network components
    roads: list[Road] = Field(
        default_factory=list,
        description="All roads in the network"
    )
    intersections: list[Intersection] = Field(
        default_factory=list,
        description="All road intersections"
    )

    # Network metadata
    total_road_count: int = Field(default=0, ge=0, description="Number of roads")
    total_intersection_count: int = Field(
        default=0, ge=0, description="Number of intersections"
    )
    total_arc_length: float = Field(
        default=0.0, ge=0.0,
        description="Combined arc length of all roads"
    )

    # Bounds
    bounds: dict[str, float] = Field(
        default_factory=lambda: {
            "min_x": 0.0,
            "min_y": 0.0,
            "max_x": 1920.0,
            "max_y": 1080.0,
        },
        description="Bounding box of the road network"
    )

    # Generation metadata
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Generation timestamp"
    )
    generation_seed: Optional[int] = Field(
        None, description="Random seed used for generation"
    )
    generation_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters used for generation"
    )

    def get_road_by_id(self, road_id: str) -> Optional[Road]:
        """Get a road by its ID."""
        for road in self.roads:
            if road.id == road_id:
                return road
        return None

    def get_intersection_by_id(self, intersection_id: str) -> Optional[Intersection]:
        """Get an intersection by its ID."""
        for intersection in self.intersections:
            if intersection.id == intersection_id:
                return intersection
        return None

    def compute_statistics(self) -> dict[str, Any]:
        """Compute network statistics."""
        road_types = {}
        for road in self.roads:
            road_type = road.road_type.value
            road_types[road_type] = road_types.get(road_type, 0) + 1

        intersection_types = {}
        for intersection in self.intersections:
            int_type = intersection.intersection_type.value
            intersection_types[int_type] = intersection_types.get(int_type, 0) + 1

        return {
            "total_roads": len(self.roads),
            "total_intersections": len(self.intersections),
            "total_arc_length": self.total_arc_length,
            "roads_by_type": road_types,
            "intersections_by_type": intersection_types,
            "avg_road_length": (
                self.total_arc_length / len(self.roads) if self.roads else 0
            ),
        }


class RoadGenerationConfig(BaseModel):
    """Configuration for road generation.

    Controls how roads are generated from landmark positions.
    """

    model_config = ConfigDict(frozen=True)

    # Road generation settings
    default_road_type: RoadType = Field(
        default=RoadType.DIRT_PATH,
        description="Default road type for generated roads"
    )
    spline_config: SplineConfig = Field(
        default_factory=SplineConfig,
        description="Default spline configuration"
    )

    # Path smoothing
    apply_smoothing: bool = Field(
        default=True, description="Apply path smoothing"
    )
    smoothing_factor: float = Field(
        default=0.25, ge=0.0, le=1.0,
        description="Smoothing factor (0=none, 1=maximum)"
    )
    smoothing_iterations: int = Field(
        default=1, ge=0, le=5,
        description="Number of smoothing iterations"
    )

    # Scatter/randomness
    apply_scatter: bool = Field(
        default=True, description="Apply random scatter to control points"
    )
    scatter_amount: float = Field(
        default=15.0, ge=0.0,
        description="Maximum scatter distance in pixels"
    )

    # Intersection handling
    detect_intersections: bool = Field(
        default=True, description="Detect road intersections"
    )
    intersection_tolerance: float = Field(
        default=10.0, ge=0.0,
        description="Distance tolerance for intersection detection"
    )

    # Canvas constraints
    canvas_width: float = Field(default=1920.0, gt=0, description="Canvas width")
    canvas_height: float = Field(default=1080.0, gt=0, description="Canvas height")
    margin: float = Field(default=50.0, ge=0.0, description="Margin from edges")

    # Variation settings
    road_type_variation: bool = Field(
        default=False,
        description="Vary road types based on importance"
    )
    style_variation: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Amount of style variation between roads"
    )
