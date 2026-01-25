"""Collision detection utilities for icon placement.

This module provides collision detection and avoidance functions for:
- Icon-to-icon overlap detection
- Icon-to-road overlap detection
- Boundary checking for map edges
- Position adjustment to avoid collisions
"""

import math
from typing import Optional

from app.schemas.icon import BoundingBox, IconPlacement, PlacementConfig, Position


def check_icon_overlap(
    box1: BoundingBox,
    box2: BoundingBox,
    min_spacing: float = 0.0,
) -> bool:
    """Check if two bounding boxes overlap with optional spacing.

    Args:
        box1: First bounding box
        box2: Second bounding box
        min_spacing: Minimum spacing between boxes (default: 0)

    Returns:
        True if boxes overlap (including within min_spacing), False otherwise
    """
    # Expand boxes by half the minimum spacing
    half_spacing = min_spacing / 2

    expanded1 = BoundingBox(
        x=box1.x - half_spacing,
        y=box1.y - half_spacing,
        width=box1.width + min_spacing,
        height=box1.height + min_spacing,
    )

    expanded2 = BoundingBox(
        x=box2.x - half_spacing,
        y=box2.y - half_spacing,
        width=box2.width + min_spacing,
        height=box2.height + min_spacing,
    )

    return expanded1.intersects(expanded2)


def check_any_overlap(
    placement: IconPlacement,
    existing_placements: list[IconPlacement],
    min_spacing: float = 0.0,
) -> tuple[bool, Optional[IconPlacement]]:
    """Check if a placement overlaps with any existing placements.

    Args:
        placement: The placement to check
        existing_placements: List of existing placements
        min_spacing: Minimum spacing between icons

    Returns:
        Tuple of (has_overlap, conflicting_placement)
    """
    for existing in existing_placements:
        if check_icon_overlap(placement.bounding_box, existing.bounding_box, min_spacing):
            return True, existing
    return False, None


def distance_to_line_segment(
    point: Position,
    line_start: Position,
    line_end: Position,
) -> float:
    """Calculate the shortest distance from a point to a line segment.

    Args:
        point: The point to check
        line_start: Start of the line segment
        line_end: End of the line segment

    Returns:
        The shortest distance from point to the line segment
    """
    # Vector from line_start to line_end
    dx = line_end.x - line_start.x
    dy = line_end.y - line_start.y

    # Length squared of the segment
    length_sq = dx * dx + dy * dy

    if length_sq == 0:
        # line_start and line_end are the same point
        return math.sqrt(
            (point.x - line_start.x) ** 2 + (point.y - line_start.y) ** 2
        )

    # Parameter t for the projection of point onto the line
    t = max(0, min(1, ((point.x - line_start.x) * dx + (point.y - line_start.y) * dy) / length_sq))

    # Closest point on the segment
    closest_x = line_start.x + t * dx
    closest_y = line_start.y + t * dy

    return math.sqrt((point.x - closest_x) ** 2 + (point.y - closest_y) ** 2)


def check_road_overlap(
    placement: IconPlacement,
    road_coordinates: list[dict[str, float]],
    road_buffer: float = 30.0,
) -> bool:
    """Check if a placement overlaps with the road path.

    Args:
        placement: The placement to check
        road_coordinates: List of road coordinate points {x, y}
        road_buffer: Buffer distance from the road path

    Returns:
        True if placement overlaps with road buffer zone, False otherwise
    """
    if not road_coordinates or len(road_coordinates) < 2:
        return False

    # Get the center of the icon
    center = placement.bounding_box.center

    # Check distance to each road segment
    for i in range(len(road_coordinates) - 1):
        start = Position(
            x=road_coordinates[i].get("x", 0),
            y=road_coordinates[i].get("y", 0),
        )
        end = Position(
            x=road_coordinates[i + 1].get("x", 0),
            y=road_coordinates[i + 1].get("y", 0),
        )

        distance = distance_to_line_segment(center, start, end)

        # Account for icon size (use half of the larger dimension)
        icon_radius = max(
            placement.bounding_box.width, placement.bounding_box.height
        ) / 2

        if distance < (road_buffer + icon_radius):
            return True

    return False


def check_boundary(
    placement: IconPlacement,
    config: PlacementConfig,
) -> bool:
    """Check if a placement is within the canvas boundaries.

    Args:
        placement: The placement to check
        config: Placement configuration with canvas dimensions

    Returns:
        True if placement is within bounds, False otherwise
    """
    box = placement.bounding_box

    return (
        box.x >= config.margin
        and box.y >= config.margin
        and box.right <= config.canvas_width - config.margin
        and box.bottom <= config.canvas_height - config.margin
    )


def adjust_for_boundary(
    position: Position,
    icon_width: float,
    icon_height: float,
    config: PlacementConfig,
) -> Position:
    """Adjust a position to ensure the icon stays within boundaries.

    Args:
        position: Original position
        icon_width: Icon width
        icon_height: Icon height
        config: Placement configuration

    Returns:
        Adjusted position within boundaries
    """
    # Calculate the icon's bounding box edges
    half_width = icon_width / 2
    half_height = icon_height / 2

    # Clamp to boundaries
    new_x = max(
        config.margin + half_width,
        min(config.canvas_width - config.margin - half_width, position.x),
    )
    new_y = max(
        config.margin + half_height,
        min(config.canvas_height - config.margin - half_height, position.y),
    )

    return Position(x=new_x, y=new_y)


def find_non_overlapping_position(
    original_position: Position,
    icon_width: float,
    icon_height: float,
    existing_placements: list[IconPlacement],
    road_coordinates: list[dict[str, float]],
    config: PlacementConfig,
) -> tuple[Optional[Position], int]:
    """Find a non-overlapping position near the original position.

    Uses a spiral search pattern to find an available position.

    Args:
        original_position: The desired position
        icon_width: Icon width
        icon_height: Icon height
        existing_placements: List of existing placements
        road_coordinates: Road path coordinates
        config: Placement configuration

    Returns:
        Tuple of (found_position, attempts_made)
    """
    half_width = icon_width / 2
    half_height = icon_height / 2

    # Try the original position first
    test_box = BoundingBox(
        x=original_position.x - half_width,
        y=original_position.y - half_height,
        width=icon_width,
        height=icon_height,
    )

    test_placement = IconPlacement(
        id="test",
        icon_id="test",
        position=original_position,
        bounding_box=test_box,
    )

    # Check if original position works
    has_overlap, _ = check_any_overlap(test_placement, existing_placements, config.min_spacing)
    road_conflict = check_road_overlap(test_placement, road_coordinates, config.road_buffer)
    in_bounds = check_boundary(test_placement, config)

    if not has_overlap and not road_conflict and in_bounds:
        return original_position, 1

    # Spiral search for a valid position
    step = config.min_spacing if config.min_spacing > 0 else 20
    directions = [(1, 0), (0, 1), (-1, 0), (0, -1)]  # right, down, left, up

    current_pos = original_position
    steps_in_direction = 1
    direction_index = 0
    steps_taken = 0
    direction_steps = 0
    attempts = 1

    while attempts < config.max_attempts * 10:  # Allow more attempts for spiral
        # Move in current direction
        dx, dy = directions[direction_index]
        current_pos = Position(
            x=current_pos.x + dx * step,
            y=current_pos.y + dy * step,
        )
        steps_taken += 1
        direction_steps += 1
        attempts += 1

        # Test this position
        test_box = BoundingBox(
            x=current_pos.x - half_width,
            y=current_pos.y - half_height,
            width=icon_width,
            height=icon_height,
        )

        test_placement = IconPlacement(
            id="test",
            icon_id="test",
            position=current_pos,
            bounding_box=test_box,
        )

        has_overlap, _ = check_any_overlap(test_placement, existing_placements, config.min_spacing)
        road_conflict = check_road_overlap(test_placement, road_coordinates, config.road_buffer)
        in_bounds = check_boundary(test_placement, config)

        if not has_overlap and not road_conflict and in_bounds:
            return current_pos, attempts

        # Change direction in spiral pattern
        if direction_steps >= steps_in_direction:
            direction_steps = 0
            direction_index = (direction_index + 1) % 4
            # Increase steps every two direction changes
            if direction_index % 2 == 0:
                steps_in_direction += 1

    return None, attempts


def calculate_grid_position(
    index: int,
    total_items: int,
    config: PlacementConfig,
) -> Position:
    """Calculate a grid position for an item.

    Args:
        index: Item index
        total_items: Total number of items
        config: Placement configuration

    Returns:
        Grid position for the item
    """
    # Calculate available space
    available_width = config.canvas_width - 2 * config.margin
    available_height = config.canvas_height - 2 * config.margin

    # Calculate grid dimensions
    cells_x = max(1, int(available_width / config.grid_cell_size))
    cells_y = max(1, int(available_height / config.grid_cell_size))

    # Wrap index to available cells
    cell_index = index % (cells_x * cells_y)
    cell_x = cell_index % cells_x
    cell_y = cell_index // cells_x

    # Calculate position (center of cell)
    x = config.margin + (cell_x + 0.5) * config.grid_cell_size
    y = config.margin + (cell_y + 0.5) * config.grid_cell_size

    return Position(x=x, y=y)


def get_overlap_area(box1: BoundingBox, box2: BoundingBox) -> float:
    """Calculate the overlapping area between two bounding boxes.

    Args:
        box1: First bounding box
        box2: Second bounding box

    Returns:
        The overlapping area (0 if no overlap)
    """
    # Calculate intersection rectangle
    x_left = max(box1.x, box2.x)
    y_top = max(box1.y, box2.y)
    x_right = min(box1.right, box2.right)
    y_bottom = min(box1.bottom, box2.bottom)

    if x_right <= x_left or y_bottom <= y_top:
        return 0.0

    return (x_right - x_left) * (y_bottom - y_top)


def calculate_density_at_position(
    position: Position,
    existing_placements: list[IconPlacement],
    radius: float = 100.0,
) -> float:
    """Calculate the icon density around a position.

    Args:
        position: Position to check
        existing_placements: Existing icon placements
        radius: Radius to check for density

    Returns:
        Density score (number of icons within radius)
    """
    count = 0
    for placement in existing_placements:
        center = placement.bounding_box.center
        distance = math.sqrt(
            (position.x - center.x) ** 2 + (position.y - center.y) ** 2
        )
        if distance <= radius:
            count += 1
    return count
