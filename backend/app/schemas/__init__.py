"""Pydantic schemas for API requests and responses."""

from app.schemas.document import DocumentListResponse, DocumentResponse, DocumentUploadResponse
from app.schemas.hierarchy import (
    ExtractionMethod,
    ExtractionResult,
    HierarchyExtractionRequest,
    HierarchyExtractionResponse,
    HierarchyLevel,
    HierarchyNode,
    HierarchyTree,
    NodeType,
)
from app.schemas.icon import (
    DEFAULT_SMB3_ICONS,
    AnchorPoint,
    BoundingBox,
    IconCategory,
    IconLibrary,
    IconMetadata,
    IconPlacement,
    IconSize,
    IconStyle,
    PlacementConfig,
    PlacementResult,
    Position,
)
from app.schemas.road import (
    ControlPoint,
    DEFAULT_ROAD_STYLES,
    Intersection,
    IntersectionType,
    Road,
    RoadGenerationConfig,
    RoadNetwork,
    RoadSegment,
    RoadStyle,
    RoadType,
    SplineConfig,
)

__all__ = [
    # Document schemas
    "DocumentUploadResponse",
    "DocumentResponse",
    "DocumentListResponse",
    # Hierarchy schemas
    "ExtractionMethod",
    "ExtractionResult",
    "HierarchyExtractionRequest",
    "HierarchyExtractionResponse",
    "HierarchyLevel",
    "HierarchyNode",
    "HierarchyTree",
    "NodeType",
    # Icon schemas
    "IconCategory",
    "IconStyle",
    "AnchorPoint",
    "IconSize",
    "IconMetadata",
    "Position",
    "BoundingBox",
    "IconPlacement",
    "IconLibrary",
    "PlacementResult",
    "PlacementConfig",
    "DEFAULT_SMB3_ICONS",
    # Road schemas
    "RoadType",
    "RoadStyle",
    "DEFAULT_ROAD_STYLES",
    "ControlPoint",
    "SplineConfig",
    "RoadSegment",
    "IntersectionType",
    "Intersection",
    "Road",
    "RoadNetwork",
    "RoadGenerationConfig",
]
