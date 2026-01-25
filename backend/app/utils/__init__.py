"""Utility functions for the Overworld backend."""

from app.utils.collision import (
    adjust_for_boundary,
    calculate_density_at_position,
    calculate_grid_position,
    check_any_overlap,
    check_boundary,
    check_icon_overlap,
    check_road_overlap,
    distance_to_line_segment,
    find_non_overlapping_position,
    get_overlap_area,
)
from app.utils.file_validation import (
    FileValidationError,
    get_mime_type,
    validate_file_size,
    validate_file_type,
)
from app.utils.splines import (
    CatmullRomSpline,
    Point2D,
    SplineSegment,
    SplineType,
    find_line_intersection,
    find_self_intersections,
    find_spline_intersections,
    resample_path,
    smooth_path,
)

__all__ = [
    # File validation
    "FileValidationError",
    "validate_file_type",
    "validate_file_size",
    "get_mime_type",
    # Collision detection
    "check_icon_overlap",
    "check_any_overlap",
    "distance_to_line_segment",
    "check_road_overlap",
    "check_boundary",
    "adjust_for_boundary",
    "find_non_overlapping_position",
    "calculate_grid_position",
    "get_overlap_area",
    "calculate_density_at_position",
    # Splines
    "Point2D",
    "SplineSegment",
    "SplineType",
    "CatmullRomSpline",
    "find_line_intersection",
    "find_spline_intersections",
    "find_self_intersections",
    "smooth_path",
    "resample_path",
]
