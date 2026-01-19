"""Road Generator Agent for curved path generation."""

import random
from typing import List, Tuple

import numpy as np
from scipy import interpolate

from app.agents.base_agent import AgentResult, BaseAgent, JobContext


class RoadAgent(BaseAgent):
    """Generates curved paths using spline interpolation."""

    async def execute(self, context: JobContext) -> AgentResult:
        """Generate Bezier/spline curve for milestone placement."""
        parser_data = context.agent_state.get("parser", {}).get("data", {})
        milestone_count = parser_data.get("milestone_count", 10)
        scatter_threshold = context.options.get("scatter_threshold", 20)

        try:
            control_points = self._generate_control_points(milestone_count)
            t_values = np.linspace(0, 1, milestone_count * 10)
            spline = interpolate.BSpline(t_values, control_points, k=min(milestone_count - 1, 3))
            coordinates = self._evaluate_spline(spline, milestone_count)

            coordinates = self._apply_scatter_offset(coordinates, scatter_threshold)

            coordinates = self._validate_canvas_bounds(coordinates)

            arc_length = self._calculate_arc_length(coordinates)

            result_data = {
                "coordinates": [{"x": int(x), "y": int(y)} for x, y in coordinates],
                "control_points": [{"x": int(x), "y": int(y)} for x, y in control_points],
                "arc_length": arc_length,
                "milestone_count": milestone_count,
            }

            return AgentResult(
                success=True,
                data=result_data,
            )

        except Exception as e:
            return AgentResult(
                success=False,
                error=f"Road generation failed: {str(e)}",
            )

    def _generate_control_points(self, milestone_count: int) -> List[Tuple[float, float]]:
        """Generate control points for spline curve."""
        points = []
        canvas_width = 1920
        canvas_height = 1080

        # Start point (top-left area)
        points.append((canvas_width * 0.2, canvas_height * 0.3))

        # End point (bottom-right area)
        points.append((canvas_width * 0.8, canvas_height * 0.7))

        # Generate middle control points for organic curve
        num_middle_points = max(1, milestone_count - 2)

        for i in range(num_middle_points):
            t = (i + 1) / (num_middle_points + 1)
            x = canvas_width * (0.2 + 0.6 * t)
            y = canvas_height * (0.3 + 0.4 * t)
            points.append((x, y))

        return points

    def _evaluate_spline(self, spline, milestone_count: int) -> List[Tuple[float, float]]:
        """Evaluate spline at evenly spaced intervals."""
        t_values = np.linspace(0, 1, milestone_count * 10)
        coordinates = []

        for t in t_values:
            point = spline(t)
            x, y = point[0], point[1]
            coordinates.append((float(x), float(y)))

        return coordinates

    def _apply_scatter_offset(
        self, coordinates: List[Tuple[float, float]], threshold: float
    ) -> List[Tuple[float, float]]:
        """Apply random offset to create hand-placed feel."""
        if threshold == 0:
            return coordinates

        offset_coordinates = []
        for x, y in coordinates:
            offset_x = random.uniform(-threshold, threshold)
            offset_y = random.uniform(-threshold, threshold)
            new_x = max(100, min(1820, x + offset_x))
            new_y = max(100, min(980, y + offset_y))
            offset_coordinates.append((new_x, new_y))

        return offset_coordinates

    def _validate_canvas_bounds(
        self, coordinates: List[Tuple[float, float]]
    ) -> List[Tuple[float, float]]:
        """Ensure all coordinates stay within canvas with margin."""
        canvas_width = 1920
        canvas_height = 1080
        margin = 100
        valid_coordinates = []

        for x, y in coordinates:
            new_x = max(margin, min(canvas_width - margin, x))
            new_y = max(margin, min(canvas_height - margin, y))
            valid_coordinates.append((new_x, new_y))

        return valid_coordinates

    def _calculate_arc_length(self, coordinates: List[Tuple[float, float]]) -> float:
        """Calculate total arc length of the path."""
        total_length = 0.0

        for i in range(len(coordinates) - 1):
            x1, y1 = coordinates[i]
            x2, y2 = coordinates[i + 1]
            segment_length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
            total_length += segment_length

        return total_length
