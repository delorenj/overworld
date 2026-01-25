"""Catmull-Rom spline implementation for smooth path generation.

This module provides a pure Python implementation of Catmull-Rom splines,
which are particularly useful for generating smooth curves through a set of
control points. Unlike Bezier curves, Catmull-Rom splines pass through all
their control points, making them ideal for road/path generation.

Key features:
- Configurable tension parameter (alpha) for curve tightness
- Support for both uniform and centripetal parameterization
- Efficient point interpolation and batch evaluation
- Arc length calculation for evenly-spaced point sampling
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import math


class SplineType(str, Enum):
    """Type of Catmull-Rom spline parameterization."""

    UNIFORM = "uniform"  # alpha = 0.0, evenly spaced knots
    CENTRIPETAL = "centripetal"  # alpha = 0.5, better for sharp turns
    CHORDAL = "chordal"  # alpha = 1.0, follows chord lengths


@dataclass
class Point2D:
    """A 2D point with x and y coordinates."""

    x: float
    y: float

    def __add__(self, other: "Point2D") -> "Point2D":
        return Point2D(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Point2D") -> "Point2D":
        return Point2D(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> "Point2D":
        return Point2D(self.x * scalar, self.y * scalar)

    def __rmul__(self, scalar: float) -> "Point2D":
        return self.__mul__(scalar)

    def distance_to(self, other: "Point2D") -> float:
        """Calculate Euclidean distance to another point."""
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)

    def to_tuple(self) -> tuple[float, float]:
        """Convert to tuple representation."""
        return (self.x, self.y)

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary representation."""
        return {"x": self.x, "y": self.y}

    @classmethod
    def from_tuple(cls, t: tuple[float, float]) -> "Point2D":
        """Create from tuple."""
        return cls(x=t[0], y=t[1])

    @classmethod
    def from_dict(cls, d: dict[str, float]) -> "Point2D":
        """Create from dictionary."""
        return cls(x=d["x"], y=d["y"])


@dataclass
class SplineSegment:
    """A segment of the Catmull-Rom spline between two control points.

    The segment is defined by four control points:
    - p0: previous control point (for tangent calculation)
    - p1: start point of this segment
    - p2: end point of this segment
    - p3: next control point (for tangent calculation)
    """

    p0: Point2D
    p1: Point2D
    p2: Point2D
    p3: Point2D
    alpha: float = 0.5  # Centripetal by default

    # Cached knot values
    _t0: float = field(default=0.0, init=False)
    _t1: float = field(default=0.0, init=False)
    _t2: float = field(default=0.0, init=False)
    _t3: float = field(default=0.0, init=False)

    def __post_init__(self):
        """Calculate knot values after initialization."""
        self._calculate_knots()

    def _calculate_knots(self) -> None:
        """Calculate knot values based on alpha parameterization."""
        self._t0 = 0.0
        self._t1 = self._get_knot_interval(self.p0, self.p1) + self._t0
        self._t2 = self._get_knot_interval(self.p1, self.p2) + self._t1
        self._t3 = self._get_knot_interval(self.p2, self.p3) + self._t2

    def _get_knot_interval(self, p_a: Point2D, p_b: Point2D) -> float:
        """Calculate knot interval between two points.

        For centripetal (alpha=0.5): interval = sqrt(distance)
        For uniform (alpha=0): interval = 1.0
        For chordal (alpha=1.0): interval = distance
        """
        d = p_a.distance_to(p_b)
        if d < 1e-10:  # Avoid division by zero for coincident points
            return 1e-10
        return d ** self.alpha

    def evaluate(self, t: float) -> Point2D:
        """Evaluate the spline segment at parameter t in [0, 1].

        Uses the Barry-Goldman algorithm for numerical stability.

        Args:
            t: Parameter value between 0 and 1

        Returns:
            Point on the spline at parameter t
        """
        # Clamp t to [0, 1]
        t = max(0.0, min(1.0, t))

        # Map t from [0, 1] to [t1, t2]
        t_mapped = self._t1 + t * (self._t2 - self._t1)

        # Barry-Goldman algorithm
        a1 = self._lerp_point(self.p0, self.p1, self._t0, self._t1, t_mapped)
        a2 = self._lerp_point(self.p1, self.p2, self._t1, self._t2, t_mapped)
        a3 = self._lerp_point(self.p2, self.p3, self._t2, self._t3, t_mapped)

        b1 = self._lerp_point(a1, a2, self._t0, self._t2, t_mapped)
        b2 = self._lerp_point(a2, a3, self._t1, self._t3, t_mapped)

        c = self._lerp_point(b1, b2, self._t1, self._t2, t_mapped)

        return c

    def _lerp_point(
        self, p_a: Point2D, p_b: Point2D, t_a: float, t_b: float, t: float
    ) -> Point2D:
        """Linear interpolation between two points at given knot values."""
        if abs(t_b - t_a) < 1e-10:
            return p_a
        factor = (t - t_a) / (t_b - t_a)
        return Point2D(
            x=p_a.x + factor * (p_b.x - p_a.x),
            y=p_a.y + factor * (p_b.y - p_a.y),
        )

    def evaluate_many(self, num_points: int) -> list[Point2D]:
        """Evaluate the segment at evenly spaced parameter values.

        Args:
            num_points: Number of points to generate

        Returns:
            List of points along the segment
        """
        if num_points < 2:
            return [self.evaluate(0.5)]

        return [self.evaluate(i / (num_points - 1)) for i in range(num_points)]

    def get_tangent(self, t: float, epsilon: float = 0.001) -> Point2D:
        """Get the tangent vector at parameter t using finite differences.

        Args:
            t: Parameter value between 0 and 1
            epsilon: Small value for numerical differentiation

        Returns:
            Normalized tangent vector at parameter t
        """
        t1 = max(0.0, t - epsilon)
        t2 = min(1.0, t + epsilon)

        p1 = self.evaluate(t1)
        p2 = self.evaluate(t2)

        dx = p2.x - p1.x
        dy = p2.y - p1.y

        length = math.sqrt(dx * dx + dy * dy)
        if length < 1e-10:
            return Point2D(1.0, 0.0)  # Default tangent

        return Point2D(dx / length, dy / length)


@dataclass
class CatmullRomSpline:
    """A complete Catmull-Rom spline through multiple control points.

    The spline passes through all control points (except the first and last,
    which are used only for tangent calculation). For a spline that passes
    through all points including endpoints, the first and last points are
    automatically duplicated.

    Attributes:
        control_points: List of control points (minimum 2)
        alpha: Parameterization type (0=uniform, 0.5=centripetal, 1=chordal)
        tension: Additional tension parameter (0=default, higher=tighter curve)
        closed: Whether the spline forms a closed loop
    """

    control_points: list[Point2D]
    alpha: float = 0.5  # Centripetal parameterization
    tension: float = 0.0  # Standard tension
    closed: bool = False

    # Internal state
    _segments: list[SplineSegment] = field(default_factory=list, init=False)
    _total_arc_length: float = field(default=0.0, init=False)
    _arc_lengths: list[float] = field(default_factory=list, init=False)

    def __post_init__(self):
        """Build spline segments after initialization."""
        if len(self.control_points) < 2:
            raise ValueError("Catmull-Rom spline requires at least 2 control points")
        self._build_segments()

    def _build_segments(self) -> None:
        """Build spline segments from control points."""
        self._segments = []
        points = self._get_extended_points()

        if len(points) < 4:
            # Not enough points for a proper spline, duplicate endpoints
            while len(points) < 4:
                points = [points[0]] + points + [points[-1]]

        # Create segments for each consecutive group of 4 points
        for i in range(len(points) - 3):
            segment = SplineSegment(
                p0=points[i],
                p1=points[i + 1],
                p2=points[i + 2],
                p3=points[i + 3],
                alpha=self.alpha,
            )
            self._segments.append(segment)

    def _get_extended_points(self) -> list[Point2D]:
        """Get control points with proper endpoint handling.

        For open splines, duplicates first and last points.
        For closed splines, wraps around appropriately.
        """
        if self.closed:
            # For closed splines, wrap around
            n = len(self.control_points)
            return [
                self.control_points[(i - 1) % n]
                for i in range(n + 3)
            ]
        else:
            # For open splines, duplicate endpoints
            return (
                [self.control_points[0]]
                + self.control_points
                + [self.control_points[-1]]
            )

    @property
    def num_segments(self) -> int:
        """Number of spline segments."""
        return len(self._segments)

    def evaluate(self, t: float) -> Point2D:
        """Evaluate the spline at global parameter t in [0, 1].

        Args:
            t: Global parameter value between 0 and 1

        Returns:
            Point on the spline at parameter t
        """
        if not self._segments:
            return self.control_points[0]

        # Clamp t
        t = max(0.0, min(1.0, t))

        # Map to segment and local t
        segment_float = t * self.num_segments
        segment_idx = int(segment_float)

        # Handle t = 1.0 case
        if segment_idx >= self.num_segments:
            segment_idx = self.num_segments - 1
            local_t = 1.0
        else:
            local_t = segment_float - segment_idx

        return self._segments[segment_idx].evaluate(local_t)

    def evaluate_many(self, num_points: int) -> list[Point2D]:
        """Evaluate the spline at evenly spaced parameter values.

        Args:
            num_points: Total number of points to generate

        Returns:
            List of points along the spline
        """
        if num_points < 2:
            return [self.evaluate(0.5)]

        return [self.evaluate(i / (num_points - 1)) for i in range(num_points)]

    def evaluate_at_arc_length(self, s: float, total_points: int = 100) -> Point2D:
        """Evaluate the spline at a specific arc length.

        Uses numerical integration to find the point at arc length s.

        Args:
            s: Arc length from start (0 to total_arc_length)
            total_points: Points to use for arc length calculation

        Returns:
            Point at the specified arc length
        """
        if not self._arc_lengths:
            self._compute_arc_lengths(total_points)

        # Clamp s
        s = max(0.0, min(self._total_arc_length, s))

        # Binary search for the segment containing s
        for i, (arc_start, arc_end) in enumerate(
            zip(self._arc_lengths[:-1], self._arc_lengths[1:])
        ):
            if s <= arc_end:
                # Linearly interpolate within this segment
                if arc_end - arc_start < 1e-10:
                    local_t = 0.0
                else:
                    local_t = (s - arc_start) / (arc_end - arc_start)

                # Map to global t
                t = (i + local_t) / (len(self._arc_lengths) - 1)
                return self.evaluate(t)

        return self.evaluate(1.0)

    def _compute_arc_lengths(self, num_points: int) -> None:
        """Compute cumulative arc lengths for the spline."""
        points = self.evaluate_many(num_points)
        self._arc_lengths = [0.0]
        total = 0.0

        for i in range(1, len(points)):
            dist = points[i - 1].distance_to(points[i])
            total += dist
            self._arc_lengths.append(total)

        self._total_arc_length = total

    def get_arc_length(self, num_samples: int = 100) -> float:
        """Calculate the total arc length of the spline.

        Args:
            num_samples: Number of samples for numerical integration

        Returns:
            Approximate arc length of the spline
        """
        if not self._arc_lengths:
            self._compute_arc_lengths(num_samples)
        return self._total_arc_length

    def get_evenly_spaced_points(
        self, num_points: int, samples_per_segment: int = 50
    ) -> list[Point2D]:
        """Get points evenly spaced along the arc length of the spline.

        This is more visually uniform than evenly-spaced parameter values.

        Args:
            num_points: Number of points to generate
            samples_per_segment: Samples for arc length calculation

        Returns:
            List of evenly-spaced points along the spline
        """
        if num_points < 2:
            return [self.evaluate(0.5)]

        total_samples = samples_per_segment * self.num_segments
        self._compute_arc_lengths(total_samples)

        target_spacing = self._total_arc_length / (num_points - 1)
        result = [self.evaluate(0.0)]

        for i in range(1, num_points - 1):
            target_arc = i * target_spacing
            result.append(
                self.evaluate_at_arc_length(target_arc, total_samples)
            )

        result.append(self.evaluate(1.0))
        return result

    def get_tangent(self, t: float) -> Point2D:
        """Get the tangent vector at global parameter t.

        Args:
            t: Global parameter value between 0 and 1

        Returns:
            Normalized tangent vector at parameter t
        """
        if not self._segments:
            return Point2D(1.0, 0.0)

        t = max(0.0, min(1.0, t))

        segment_float = t * self.num_segments
        segment_idx = int(segment_float)

        if segment_idx >= self.num_segments:
            segment_idx = self.num_segments - 1
            local_t = 1.0
        else:
            local_t = segment_float - segment_idx

        return self._segments[segment_idx].get_tangent(local_t)

    def get_normal(self, t: float) -> Point2D:
        """Get the normal vector (perpendicular to tangent) at parameter t.

        Args:
            t: Global parameter value between 0 and 1

        Returns:
            Normalized normal vector at parameter t
        """
        tangent = self.get_tangent(t)
        # Rotate 90 degrees counterclockwise
        return Point2D(-tangent.y, tangent.x)


def find_line_intersection(
    p1: Point2D, p2: Point2D, p3: Point2D, p4: Point2D
) -> Optional[Point2D]:
    """Find intersection point of two line segments.

    Uses the parametric line-line intersection algorithm.

    Args:
        p1, p2: Endpoints of first line segment
        p3, p4: Endpoints of second line segment

    Returns:
        Intersection point if segments intersect, None otherwise
    """
    x1, y1 = p1.x, p1.y
    x2, y2 = p2.x, p2.y
    x3, y3 = p3.x, p3.y
    x4, y4 = p4.x, p4.y

    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)

    if abs(denom) < 1e-10:
        return None  # Lines are parallel

    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom

    # Check if intersection is within both segments
    if 0 <= t <= 1 and 0 <= u <= 1:
        x = x1 + t * (x2 - x1)
        y = y1 + t * (y2 - y1)
        return Point2D(x, y)

    return None


def find_spline_intersections(
    spline1: CatmullRomSpline,
    spline2: CatmullRomSpline,
    samples_per_spline: int = 100,
    tolerance: float = 5.0,
) -> list[tuple[Point2D, float, float]]:
    """Find intersection points between two splines.

    Uses sampling and line segment intersection for efficiency.

    Args:
        spline1: First spline
        spline2: Second spline
        samples_per_spline: Number of samples per spline for intersection detection
        tolerance: Distance tolerance for considering points as intersecting

    Returns:
        List of tuples (intersection_point, t1, t2) where t1 and t2 are
        the approximate parameter values on each spline
    """
    points1 = spline1.evaluate_many(samples_per_spline)
    points2 = spline2.evaluate_many(samples_per_spline)

    intersections: list[tuple[Point2D, float, float]] = []

    for i in range(len(points1) - 1):
        for j in range(len(points2) - 1):
            intersection = find_line_intersection(
                points1[i], points1[i + 1], points2[j], points2[j + 1]
            )
            if intersection:
                t1 = (i + 0.5) / (samples_per_spline - 1)
                t2 = (j + 0.5) / (samples_per_spline - 1)
                intersections.append((intersection, t1, t2))

    # Remove duplicate intersections within tolerance
    filtered: list[tuple[Point2D, float, float]] = []
    for point, t1, t2 in intersections:
        is_duplicate = False
        for existing_point, _, _ in filtered:
            if point.distance_to(existing_point) < tolerance:
                is_duplicate = True
                break
        if not is_duplicate:
            filtered.append((point, t1, t2))

    return filtered


def find_self_intersections(
    spline: CatmullRomSpline,
    samples: int = 100,
    min_segment_gap: int = 5,
    tolerance: float = 5.0,
) -> list[tuple[Point2D, float, float]]:
    """Find self-intersection points in a spline.

    Args:
        spline: The spline to check for self-intersections
        samples: Number of samples for intersection detection
        min_segment_gap: Minimum gap between segments to check (avoids false positives)
        tolerance: Distance tolerance for considering points as intersecting

    Returns:
        List of tuples (intersection_point, t1, t2) for each self-intersection
    """
    points = spline.evaluate_many(samples)
    intersections: list[tuple[Point2D, float, float]] = []

    for i in range(len(points) - 1):
        for j in range(i + min_segment_gap, len(points) - 1):
            intersection = find_line_intersection(
                points[i], points[i + 1], points[j], points[j + 1]
            )
            if intersection:
                t1 = (i + 0.5) / (samples - 1)
                t2 = (j + 0.5) / (samples - 1)
                intersections.append((intersection, t1, t2))

    # Remove duplicates within tolerance
    filtered: list[tuple[Point2D, float, float]] = []
    for point, t1, t2 in intersections:
        is_duplicate = False
        for existing_point, _, _ in filtered:
            if point.distance_to(existing_point) < tolerance:
                is_duplicate = True
                break
        if not is_duplicate:
            filtered.append((point, t1, t2))

    return filtered


def smooth_path(
    points: list[Point2D],
    smoothing_factor: float = 0.5,
    iterations: int = 1,
) -> list[Point2D]:
    """Apply path smoothing using Chaikin's corner-cutting algorithm.

    Args:
        points: Input points to smooth
        smoothing_factor: How much to cut corners (0-1, default 0.5)
        iterations: Number of smoothing passes

    Returns:
        Smoothed list of points (will have more points than input)
    """
    if len(points) < 3:
        return points

    result = points
    q = smoothing_factor
    p = 1.0 - q

    for _ in range(iterations):
        new_points = [result[0]]  # Keep first point

        for i in range(len(result) - 1):
            # Generate two points for each segment
            p1 = Point2D(
                q * result[i].x + p * result[i + 1].x,
                q * result[i].y + p * result[i + 1].y,
            )
            p2 = Point2D(
                p * result[i].x + q * result[i + 1].x,
                p * result[i].y + q * result[i + 1].y,
            )
            new_points.extend([p1, p2])

        new_points.append(result[-1])  # Keep last point
        result = new_points

    return result


def resample_path(
    points: list[Point2D], target_count: int
) -> list[Point2D]:
    """Resample a path to have a specific number of evenly-spaced points.

    Args:
        points: Input points
        target_count: Desired number of output points

    Returns:
        Resampled list of points
    """
    if len(points) < 2 or target_count < 2:
        return points

    # Calculate total arc length
    arc_lengths = [0.0]
    for i in range(1, len(points)):
        dist = points[i - 1].distance_to(points[i])
        arc_lengths.append(arc_lengths[-1] + dist)

    total_length = arc_lengths[-1]
    if total_length < 1e-10:
        return points

    target_spacing = total_length / (target_count - 1)
    result = [points[0]]

    current_idx = 0
    for i in range(1, target_count - 1):
        target_arc = i * target_spacing

        # Find the segment containing target_arc
        while current_idx < len(arc_lengths) - 1 and arc_lengths[current_idx + 1] < target_arc:
            current_idx += 1

        if current_idx >= len(points) - 1:
            result.append(points[-1])
            continue

        # Interpolate within the segment
        seg_start = arc_lengths[current_idx]
        seg_end = arc_lengths[current_idx + 1]
        seg_length = seg_end - seg_start

        if seg_length < 1e-10:
            result.append(points[current_idx])
        else:
            t = (target_arc - seg_start) / seg_length
            result.append(
                Point2D(
                    points[current_idx].x + t * (points[current_idx + 1].x - points[current_idx].x),
                    points[current_idx].y + t * (points[current_idx + 1].y - points[current_idx].y),
                )
            )

    result.append(points[-1])
    return result
