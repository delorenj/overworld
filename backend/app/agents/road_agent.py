"""Road Generator Agent for curved path generation using Catmull-Rom splines.

This agent generates road networks connecting landmarks on the map using
mathematically smooth Catmull-Rom spline curves. It handles:
- Multiple road types and visual styles
- Smooth curve generation through control points
- Intersection detection and handling
- Path smoothing and optimization

The agent takes landmark/milestone data from the ParserAgent and produces
a complete road network definition for rendering.
"""

import logging
import random
from typing import Any, Optional

from app.agents.base_agent import AgentResult, BaseAgent, JobContext
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
from app.utils.splines import (
    CatmullRomSpline,
    Point2D,
    find_spline_intersections,
    smooth_path,
)

logger = logging.getLogger(__name__)


class RoadGeneratorAgent(BaseAgent):
    """Generates road networks using Catmull-Rom spline interpolation.

    This agent creates smooth, visually appealing roads that connect
    landmarks on the map. It uses Catmull-Rom splines for natural-looking
    curves that pass through all control points.

    Features:
    - Catmull-Rom spline-based path generation
    - Multiple road types with distinct visual styles
    - Automatic intersection detection
    - Configurable path smoothing
    - Support for scattered control points for organic feel

    Input (from context.agent_state):
        - parser.data.milestones: List of milestones with positions
        - parser.data.milestone_count: Total number of milestones

    Output:
        - road_network: Complete RoadNetwork with roads and intersections
        - coordinates: Legacy format for backward compatibility
        - control_points: Original control points
        - arc_length: Total road network length
    """

    def __init__(self, config: Optional[RoadGenerationConfig] = None):
        """Initialize the RoadGeneratorAgent.

        Args:
            config: Optional generation configuration. If not provided,
                   default configuration is used.
        """
        super().__init__()
        self.config = config or RoadGenerationConfig()
        self._random = random.Random()

    async def execute(self, context: JobContext) -> AgentResult:
        """Generate road network from landmark data.

        Processes milestone data from the ParserAgent to create a connected
        road network with smooth spline-based paths.

        Args:
            context: Job context containing agent state and options

        Returns:
            AgentResult with road network data
        """
        try:
            # Extract milestone data from parser
            parser_data = context.agent_state.get("parser", {})
            if isinstance(parser_data, dict) and "data" in parser_data:
                parser_data = parser_data.get("data", {})

            milestone_count = parser_data.get("milestone_count", 10)
            milestones = parser_data.get("milestones", [])

            # Get generation options from context
            scatter_threshold = context.options.get(
                "scatter_threshold", self.config.scatter_amount
            )
            road_type_str = context.options.get("road_type", "dirt_path")
            seed = context.options.get("seed")

            # Set random seed if provided
            if seed is not None:
                self._random.seed(seed)

            # Determine road type
            road_type = self._parse_road_type(road_type_str)

            # Generate control points from milestones or create default layout
            control_points = self._generate_control_points(
                milestones, milestone_count
            )

            # Apply scatter if enabled
            if self.config.apply_scatter and scatter_threshold > 0:
                control_points = self._apply_scatter(
                    control_points, scatter_threshold
                )

            # Validate and constrain to canvas bounds
            control_points = self._validate_canvas_bounds(control_points)

            # Create the main road spline
            main_road = self._create_road(
                control_points=control_points,
                road_type=road_type,
                name="Main Path",
            )

            # Build road network
            road_network = RoadNetwork(
                roads=[main_road],
                total_road_count=1,
                total_arc_length=main_road.total_arc_length,
                bounds={
                    "min_x": self.config.margin,
                    "min_y": self.config.margin,
                    "max_x": self.config.canvas_width - self.config.margin,
                    "max_y": self.config.canvas_height - self.config.margin,
                },
                generation_seed=seed,
                generation_params={
                    "scatter_threshold": scatter_threshold,
                    "road_type": road_type.value,
                    "milestone_count": milestone_count,
                },
            )

            # Detect intersections if we have multiple roads
            if self.config.detect_intersections and len(road_network.roads) > 1:
                intersections = self._detect_intersections(road_network.roads)
                road_network.intersections = intersections
                road_network.total_intersection_count = len(intersections)

            # Build result data with both new and legacy formats
            all_points = main_road.get_all_points()
            result_data = {
                # New structured format
                "road_network": road_network.model_dump(),

                # Legacy format for backward compatibility
                "coordinates": [
                    {"x": int(p.x), "y": int(p.y)} for p in all_points
                ],
                "control_points": [
                    {"x": int(p.x), "y": int(p.y)}
                    for p in control_points
                ],
                "arc_length": main_road.total_arc_length,
                "milestone_count": milestone_count,

                # Additional metadata
                "road_type": road_type.value,
                "spline_type": "catmull_rom",
                "alpha": self.config.spline_config.alpha,
            }

            logger.info(
                f"Generated road network with {len(road_network.roads)} roads, "
                f"total length {main_road.total_arc_length:.1f}px"
            )

            return AgentResult(
                success=True,
                data=result_data,
            )

        except Exception as e:
            logger.error(f"Road generation failed: {str(e)}")
            return AgentResult(
                success=False,
                error=f"Road generation failed: {str(e)}",
            )

    def _parse_road_type(self, road_type_str: str) -> RoadType:
        """Parse road type from string."""
        try:
            return RoadType(road_type_str.lower())
        except ValueError:
            logger.warning(
                f"Unknown road type '{road_type_str}', defaulting to dirt_path"
            )
            return RoadType.DIRT_PATH

    def _generate_control_points(
        self,
        milestones: list[dict[str, Any]],
        milestone_count: int,
    ) -> list[ControlPoint]:
        """Generate control points from milestones or create default layout.

        If milestones have position data, uses that. Otherwise, generates
        a serpentine path across the canvas.

        Args:
            milestones: List of milestone dicts with optional position data
            milestone_count: Total number of points to generate

        Returns:
            List of control points for the road path
        """
        points: list[ControlPoint] = []

        # Try to use milestone positions if available
        if milestones:
            for milestone in milestones:
                if "x" in milestone and "y" in milestone:
                    points.append(ControlPoint(
                        x=float(milestone["x"]),
                        y=float(milestone["y"]),
                        metadata={"milestone_id": milestone.get("id")},
                    ))

        # If we have enough points, return them
        if len(points) >= 2:
            return points

        # Otherwise, generate a serpentine path
        return self._generate_serpentine_path(milestone_count)

    def _generate_serpentine_path(
        self, num_points: int
    ) -> list[ControlPoint]:
        """Generate a serpentine path across the canvas.

        Creates a visually appealing S-curve path that winds across
        the available canvas space.

        Args:
            num_points: Number of control points to generate

        Returns:
            List of control points forming a serpentine path
        """
        points: list[ControlPoint] = []

        # Effective canvas area
        x_min = self.config.margin
        x_max = self.config.canvas_width - self.config.margin
        y_min = self.config.margin
        y_max = self.config.canvas_height - self.config.margin

        # Calculate spacing
        x_span = x_max - x_min
        y_span = y_max - y_min

        # Start point (left side)
        points.append(ControlPoint(
            x=x_min + x_span * 0.1,
            y=y_min + y_span * 0.3,
        ))

        # Generate intermediate points with serpentine pattern
        num_intermediate = max(0, num_points - 2)
        for i in range(num_intermediate):
            t = (i + 1) / (num_intermediate + 1)

            # X progresses linearly
            x = x_min + x_span * (0.1 + 0.8 * t)

            # Y oscillates in a serpentine pattern
            # Using a combination of linear progression and sine wave
            y_base = y_min + y_span * (0.3 + 0.4 * t)
            y_offset = y_span * 0.15 * ((-1) ** i) * (1 - abs(0.5 - t) * 2)
            y = y_base + y_offset

            points.append(ControlPoint(x=x, y=y))

        # End point (right side)
        points.append(ControlPoint(
            x=x_min + x_span * 0.9,
            y=y_min + y_span * 0.7,
        ))

        return points

    def _apply_scatter(
        self,
        points: list[ControlPoint],
        threshold: float,
    ) -> list[ControlPoint]:
        """Apply random scatter to control points for organic feel.

        Args:
            points: Original control points
            threshold: Maximum scatter distance

        Returns:
            Scattered control points
        """
        if threshold <= 0:
            return points

        scattered: list[ControlPoint] = []
        for i, point in enumerate(points):
            # Don't scatter first and last points as much
            if i == 0 or i == len(points) - 1:
                factor = 0.3
            else:
                factor = 1.0

            offset_x = self._random.uniform(-threshold, threshold) * factor
            offset_y = self._random.uniform(-threshold, threshold) * factor

            scattered.append(ControlPoint(
                x=point.x + offset_x,
                y=point.y + offset_y,
                weight=point.weight,
                metadata=point.metadata,
            ))

        return scattered

    def _validate_canvas_bounds(
        self,
        points: list[ControlPoint],
    ) -> list[ControlPoint]:
        """Ensure all points stay within canvas bounds.

        Args:
            points: Input control points

        Returns:
            Points constrained to canvas bounds
        """
        x_min = self.config.margin
        x_max = self.config.canvas_width - self.config.margin
        y_min = self.config.margin
        y_max = self.config.canvas_height - self.config.margin

        validated: list[ControlPoint] = []
        for point in points:
            validated.append(ControlPoint(
                x=max(x_min, min(x_max, point.x)),
                y=max(y_min, min(y_max, point.y)),
                weight=point.weight,
                metadata=point.metadata,
            ))

        return validated

    def _create_road(
        self,
        control_points: list[ControlPoint],
        road_type: RoadType,
        name: Optional[str] = None,
    ) -> Road:
        """Create a road with spline interpolation.

        Args:
            control_points: Control points for the road path
            road_type: Type of road to create
            name: Optional name for the road

        Returns:
            Road object with interpolated path
        """
        # Convert control points to Point2D for spline calculation
        spline_points = [
            Point2D(p.x, p.y) for p in control_points
        ]

        # Apply smoothing if enabled
        if self.config.apply_smoothing and self.config.smoothing_iterations > 0:
            spline_points = smooth_path(
                spline_points,
                smoothing_factor=self.config.smoothing_factor,
                iterations=self.config.smoothing_iterations,
            )

        # Create Catmull-Rom spline
        spline = CatmullRomSpline(
            control_points=spline_points,
            alpha=self.config.spline_config.alpha,
            tension=self.config.spline_config.tension,
            closed=self.config.spline_config.closed,
        )

        # Get evenly spaced points along the spline
        num_points = len(control_points) * self.config.spline_config.samples_per_segment
        if self.config.spline_config.use_arc_length:
            interpolated_points = spline.get_evenly_spaced_points(num_points)
        else:
            interpolated_points = spline.evaluate_many(num_points)

        # Convert back to ControlPoints
        path_points = [
            ControlPoint(x=p.x, y=p.y) for p in interpolated_points
        ]

        # Create road segment
        segment = RoadSegment(
            start_index=0,
            end_index=len(control_points) - 1,
            points=path_points,
            arc_length=spline.get_arc_length(),
        )

        # Get style for road type
        style = DEFAULT_ROAD_STYLES.get(road_type, DEFAULT_ROAD_STYLES[RoadType.DIRT_PATH])

        return Road(
            name=name,
            road_type=road_type,
            style=style,
            control_points=control_points,
            spline_config=self.config.spline_config,
            segments=[segment],
            total_arc_length=segment.arc_length,
        )

    def _detect_intersections(
        self,
        roads: list[Road],
    ) -> list[Intersection]:
        """Detect intersections between roads.

        Args:
            roads: List of roads to check for intersections

        Returns:
            List of detected intersections
        """
        intersections: list[Intersection] = []

        # Check each pair of roads
        for i, road1 in enumerate(roads):
            for road2 in roads[i + 1:]:
                # Get spline points for each road
                points1 = [
                    Point2D(p.x, p.y) for p in road1.get_all_points()
                ]
                points2 = [
                    Point2D(p.x, p.y) for p in road2.get_all_points()
                ]

                if len(points1) < 4 or len(points2) < 4:
                    continue

                # Create splines for intersection detection
                spline1 = CatmullRomSpline(points1)
                spline2 = CatmullRomSpline(points2)

                # Find intersections
                found = find_spline_intersections(
                    spline1,
                    spline2,
                    samples_per_spline=100,
                    tolerance=self.config.intersection_tolerance,
                )

                for point, t1, t2 in found:
                    intersections.append(Intersection(
                        position=ControlPoint(x=point.x, y=point.y),
                        intersection_type=IntersectionType.CROSSING,
                        road_ids=[road1.id, road2.id],
                        road_parameters=[t1, t2],
                        radius=max(
                            road1.style.width,
                            road2.style.width,
                        ) * 1.5,
                    ))

        return intersections

    def create_branch_road(
        self,
        main_road: Road,
        branch_point_t: float,
        end_point: ControlPoint,
        road_type: Optional[RoadType] = None,
    ) -> Road:
        """Create a branch road from an existing road.

        Useful for creating side paths or connections to landmarks
        that aren't on the main path.

        Args:
            main_road: The main road to branch from
            branch_point_t: Parameter value (0-1) on main road for branch point
            end_point: End point of the branch road
            road_type: Type of branch road (defaults to trail)

        Returns:
            New branch road
        """
        # Get branch point on main road
        all_points = main_road.get_all_points()
        if not all_points:
            raise ValueError("Main road has no points")

        # Find point at parameter t
        idx = int(branch_point_t * (len(all_points) - 1))
        branch_start = all_points[idx]

        # Create branch road with intermediate point for curve
        mid_x = (branch_start.x + end_point.x) / 2
        mid_y = (branch_start.y + end_point.y) / 2
        # Add some perpendicular offset for curve
        dx = end_point.x - branch_start.x
        dy = end_point.y - branch_start.y
        perp_x = -dy * 0.2
        perp_y = dx * 0.2

        control_points = [
            branch_start,
            ControlPoint(x=mid_x + perp_x, y=mid_y + perp_y),
            end_point,
        ]

        return self._create_road(
            control_points=control_points,
            road_type=road_type or RoadType.TRAIL,
            name="Branch Path",
        )


# Backward compatibility alias
RoadAgent = RoadGeneratorAgent
