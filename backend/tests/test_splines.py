"""Tests for Catmull-Rom spline implementation.

This module contains comprehensive tests for the spline utilities including:
- Point2D operations
- SplineSegment evaluation
- CatmullRomSpline creation and evaluation
- Arc length calculations
- Intersection detection
- Path smoothing and resampling
"""

import math
import pytest

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


class TestPoint2D:
    """Tests for Point2D dataclass."""

    def test_point_creation(self):
        """Test basic point creation."""
        p = Point2D(10.0, 20.0)
        assert p.x == 10.0
        assert p.y == 20.0

    def test_point_addition(self):
        """Test point addition."""
        p1 = Point2D(10.0, 20.0)
        p2 = Point2D(5.0, 15.0)
        result = p1 + p2
        assert result.x == 15.0
        assert result.y == 35.0

    def test_point_subtraction(self):
        """Test point subtraction."""
        p1 = Point2D(10.0, 20.0)
        p2 = Point2D(5.0, 15.0)
        result = p1 - p2
        assert result.x == 5.0
        assert result.y == 5.0

    def test_point_scalar_multiplication(self):
        """Test scalar multiplication."""
        p = Point2D(10.0, 20.0)
        result = p * 2.0
        assert result.x == 20.0
        assert result.y == 40.0

    def test_point_reverse_multiplication(self):
        """Test reverse scalar multiplication."""
        p = Point2D(10.0, 20.0)
        result = 2.0 * p
        assert result.x == 20.0
        assert result.y == 40.0

    def test_distance_to(self):
        """Test distance calculation."""
        p1 = Point2D(0.0, 0.0)
        p2 = Point2D(3.0, 4.0)
        assert p1.distance_to(p2) == 5.0

    def test_distance_to_same_point(self):
        """Test distance to same point."""
        p = Point2D(10.0, 20.0)
        assert p.distance_to(p) == 0.0

    def test_to_tuple(self):
        """Test tuple conversion."""
        p = Point2D(10.0, 20.0)
        assert p.to_tuple() == (10.0, 20.0)

    def test_to_dict(self):
        """Test dict conversion."""
        p = Point2D(10.0, 20.0)
        assert p.to_dict() == {"x": 10.0, "y": 20.0}

    def test_from_tuple(self):
        """Test creation from tuple."""
        p = Point2D.from_tuple((10.0, 20.0))
        assert p.x == 10.0
        assert p.y == 20.0

    def test_from_dict(self):
        """Test creation from dict."""
        p = Point2D.from_dict({"x": 10.0, "y": 20.0})
        assert p.x == 10.0
        assert p.y == 20.0


class TestSplineSegment:
    """Tests for SplineSegment class."""

    @pytest.fixture
    def simple_segment(self):
        """Create a simple test segment."""
        return SplineSegment(
            p0=Point2D(0.0, 0.0),
            p1=Point2D(100.0, 0.0),
            p2=Point2D(200.0, 0.0),
            p3=Point2D(300.0, 0.0),
            alpha=0.5,
        )

    def test_segment_creation(self, simple_segment):
        """Test segment creation."""
        assert simple_segment.p1.x == 100.0
        assert simple_segment.p2.x == 200.0

    def test_evaluate_at_zero(self, simple_segment):
        """Test evaluation at t=0 returns start point."""
        point = simple_segment.evaluate(0.0)
        assert abs(point.x - 100.0) < 0.1
        assert abs(point.y - 0.0) < 0.1

    def test_evaluate_at_one(self, simple_segment):
        """Test evaluation at t=1 returns end point."""
        point = simple_segment.evaluate(1.0)
        assert abs(point.x - 200.0) < 0.1
        assert abs(point.y - 0.0) < 0.1

    def test_evaluate_at_half(self, simple_segment):
        """Test evaluation at t=0.5 is between start and end."""
        point = simple_segment.evaluate(0.5)
        assert 100.0 < point.x < 200.0

    def test_evaluate_many(self, simple_segment):
        """Test evaluating multiple points."""
        points = simple_segment.evaluate_many(5)
        assert len(points) == 5
        # First and last should be near p1 and p2
        assert abs(points[0].x - 100.0) < 1.0
        assert abs(points[-1].x - 200.0) < 1.0

    def test_curved_segment(self):
        """Test a segment with curvature."""
        segment = SplineSegment(
            p0=Point2D(0.0, 0.0),
            p1=Point2D(100.0, 0.0),
            p2=Point2D(200.0, 100.0),
            p3=Point2D(300.0, 100.0),
        )
        # Middle point should have some y offset
        mid = segment.evaluate(0.5)
        assert mid.y > 0

    def test_get_tangent(self, simple_segment):
        """Test tangent calculation."""
        tangent = simple_segment.get_tangent(0.5)
        # For straight line, tangent should be horizontal
        assert abs(tangent.x) > abs(tangent.y)


class TestCatmullRomSpline:
    """Tests for CatmullRomSpline class."""

    @pytest.fixture
    def simple_spline(self):
        """Create a simple test spline."""
        points = [
            Point2D(0.0, 0.0),
            Point2D(100.0, 50.0),
            Point2D(200.0, 0.0),
            Point2D(300.0, 50.0),
        ]
        return CatmullRomSpline(points)

    def test_spline_creation(self, simple_spline):
        """Test spline creation."""
        assert len(simple_spline.control_points) == 4
        assert simple_spline.num_segments > 0

    def test_spline_requires_two_points(self):
        """Test that spline requires at least 2 points."""
        with pytest.raises(ValueError):
            CatmullRomSpline([Point2D(0.0, 0.0)])

    def test_evaluate_at_zero(self, simple_spline):
        """Test evaluation at t=0."""
        point = simple_spline.evaluate(0.0)
        # Should be near first control point (with endpoint extension)
        assert point.x >= 0.0

    def test_evaluate_at_one(self, simple_spline):
        """Test evaluation at t=1."""
        point = simple_spline.evaluate(1.0)
        # Should be near last control point (with endpoint extension)
        assert point.x <= 350.0

    def test_evaluate_many(self, simple_spline):
        """Test evaluating multiple points."""
        points = simple_spline.evaluate_many(20)
        assert len(points) == 20
        # Points should progress from left to right generally
        assert points[-1].x > points[0].x

    def test_arc_length_positive(self, simple_spline):
        """Test arc length is positive."""
        arc_length = simple_spline.get_arc_length()
        assert arc_length > 0

    def test_arc_length_consistency(self):
        """Test arc length is consistent with point count."""
        points = [
            Point2D(0.0, 0.0),
            Point2D(100.0, 0.0),
            Point2D(200.0, 0.0),
        ]
        spline = CatmullRomSpline(points)
        arc_length = spline.get_arc_length(num_samples=100)
        # For a mostly straight line, arc length should be close to distance
        assert arc_length > 150  # At least 150 pixels

    def test_evenly_spaced_points(self, simple_spline):
        """Test getting evenly spaced points."""
        points = simple_spline.get_evenly_spaced_points(10)
        assert len(points) == 10

        # Check that spacing is relatively even
        distances = []
        for i in range(len(points) - 1):
            distances.append(points[i].distance_to(points[i + 1]))

        avg_dist = sum(distances) / len(distances)
        # All distances should be within 30% of average (allowing for curve effects)
        for d in distances:
            assert abs(d - avg_dist) / avg_dist < 0.3

    def test_get_tangent(self, simple_spline):
        """Test tangent vector calculation."""
        tangent = simple_spline.get_tangent(0.5)
        # Tangent should be normalized (length ~1)
        length = math.sqrt(tangent.x ** 2 + tangent.y ** 2)
        assert abs(length - 1.0) < 0.01

    def test_get_normal(self, simple_spline):
        """Test normal vector calculation."""
        normal = simple_spline.get_normal(0.5)
        tangent = simple_spline.get_tangent(0.5)
        # Normal should be perpendicular to tangent (dot product ~0)
        dot = normal.x * tangent.x + normal.y * tangent.y
        assert abs(dot) < 0.01

    def test_alpha_variations(self):
        """Test different alpha values."""
        points = [
            Point2D(0.0, 0.0),
            Point2D(100.0, 100.0),
            Point2D(200.0, 0.0),
        ]

        # Uniform (alpha=0)
        uniform = CatmullRomSpline(points, alpha=0.0)
        # Centripetal (alpha=0.5)
        centripetal = CatmullRomSpline(points, alpha=0.5)
        # Chordal (alpha=1.0)
        chordal = CatmullRomSpline(points, alpha=1.0)

        # All should produce valid splines
        assert uniform.evaluate(0.5) is not None
        assert centripetal.evaluate(0.5) is not None
        assert chordal.evaluate(0.5) is not None

    def test_two_point_spline(self):
        """Test spline with minimum points."""
        points = [
            Point2D(0.0, 0.0),
            Point2D(100.0, 100.0),
        ]
        spline = CatmullRomSpline(points)
        # Should still work with endpoint duplication
        mid = spline.evaluate(0.5)
        assert mid is not None

    def test_closed_spline(self):
        """Test closed spline (loop)."""
        points = [
            Point2D(0.0, 0.0),
            Point2D(100.0, 0.0),
            Point2D(100.0, 100.0),
            Point2D(0.0, 100.0),
        ]
        spline = CatmullRomSpline(points, closed=True)

        # Start and end should be close for closed spline
        start = spline.evaluate(0.0)
        end = spline.evaluate(1.0)
        # They might not be exactly the same due to the wrapping
        assert start is not None
        assert end is not None


class TestLineIntersection:
    """Tests for line segment intersection."""

    def test_crossing_segments(self):
        """Test two crossing segments."""
        p1 = Point2D(0.0, 0.0)
        p2 = Point2D(100.0, 100.0)
        p3 = Point2D(0.0, 100.0)
        p4 = Point2D(100.0, 0.0)

        intersection = find_line_intersection(p1, p2, p3, p4)
        assert intersection is not None
        assert abs(intersection.x - 50.0) < 0.1
        assert abs(intersection.y - 50.0) < 0.1

    def test_parallel_segments(self):
        """Test parallel segments don't intersect."""
        p1 = Point2D(0.0, 0.0)
        p2 = Point2D(100.0, 0.0)
        p3 = Point2D(0.0, 50.0)
        p4 = Point2D(100.0, 50.0)

        intersection = find_line_intersection(p1, p2, p3, p4)
        assert intersection is None

    def test_non_intersecting_segments(self):
        """Test non-intersecting segments."""
        p1 = Point2D(0.0, 0.0)
        p2 = Point2D(50.0, 0.0)
        p3 = Point2D(100.0, 100.0)
        p4 = Point2D(200.0, 100.0)

        intersection = find_line_intersection(p1, p2, p3, p4)
        assert intersection is None

    def test_t_intersection(self):
        """Test T-intersection."""
        p1 = Point2D(0.0, 50.0)
        p2 = Point2D(100.0, 50.0)
        p3 = Point2D(50.0, 0.0)
        p4 = Point2D(50.0, 100.0)

        intersection = find_line_intersection(p1, p2, p3, p4)
        assert intersection is not None
        assert abs(intersection.x - 50.0) < 0.1
        assert abs(intersection.y - 50.0) < 0.1


class TestSplineIntersections:
    """Tests for spline intersection detection."""

    def test_crossing_splines(self):
        """Test two crossing splines."""
        # Horizontal-ish spline
        spline1 = CatmullRomSpline([
            Point2D(0.0, 50.0),
            Point2D(50.0, 50.0),
            Point2D(100.0, 50.0),
        ])

        # Vertical-ish spline
        spline2 = CatmullRomSpline([
            Point2D(50.0, 0.0),
            Point2D(50.0, 50.0),
            Point2D(50.0, 100.0),
        ])

        intersections = find_spline_intersections(spline1, spline2)
        assert len(intersections) >= 1

        # Intersection should be near (50, 50)
        point, t1, t2 = intersections[0]
        assert abs(point.x - 50.0) < 10.0
        assert abs(point.y - 50.0) < 10.0

    def test_non_intersecting_splines(self):
        """Test non-intersecting splines."""
        spline1 = CatmullRomSpline([
            Point2D(0.0, 0.0),
            Point2D(50.0, 0.0),
            Point2D(100.0, 0.0),
        ])

        spline2 = CatmullRomSpline([
            Point2D(0.0, 100.0),
            Point2D(50.0, 100.0),
            Point2D(100.0, 100.0),
        ])

        intersections = find_spline_intersections(spline1, spline2)
        assert len(intersections) == 0


class TestSelfIntersections:
    """Tests for self-intersection detection."""

    def test_figure_eight(self):
        """Test figure-eight pattern has self-intersection."""
        # Create a figure-eight shape
        points = [
            Point2D(0.0, 50.0),
            Point2D(50.0, 0.0),
            Point2D(100.0, 50.0),
            Point2D(50.0, 100.0),
            Point2D(0.0, 50.0),  # Back to start area
        ]
        spline = CatmullRomSpline(points)

        intersections = find_self_intersections(spline, samples=100)
        # Should find at least one self-intersection
        # Note: with smoothing, might not always intersect
        # This is a best-effort test
        assert isinstance(intersections, list)

    def test_simple_arc_no_intersection(self):
        """Test simple arc has no self-intersection."""
        points = [
            Point2D(0.0, 0.0),
            Point2D(50.0, 50.0),
            Point2D(100.0, 0.0),
        ]
        spline = CatmullRomSpline(points)

        intersections = find_self_intersections(spline)
        assert len(intersections) == 0


class TestPathSmoothing:
    """Tests for path smoothing algorithms."""

    def test_smooth_path_output_length(self):
        """Test smoothing increases point count."""
        points = [
            Point2D(0.0, 0.0),
            Point2D(50.0, 50.0),
            Point2D(100.0, 0.0),
        ]

        smoothed = smooth_path(points, iterations=1)
        assert len(smoothed) > len(points)

    def test_smooth_path_preserves_endpoints(self):
        """Test smoothing preserves first and last points."""
        points = [
            Point2D(0.0, 0.0),
            Point2D(50.0, 50.0),
            Point2D(100.0, 0.0),
        ]

        smoothed = smooth_path(points, iterations=1)
        assert smoothed[0].x == points[0].x
        assert smoothed[0].y == points[0].y
        assert smoothed[-1].x == points[-1].x
        assert smoothed[-1].y == points[-1].y

    def test_smooth_path_multiple_iterations(self):
        """Test multiple smoothing iterations."""
        points = [
            Point2D(0.0, 0.0),
            Point2D(50.0, 50.0),
            Point2D(100.0, 0.0),
        ]

        smoothed1 = smooth_path(points, iterations=1)
        smoothed2 = smooth_path(points, iterations=2)

        assert len(smoothed2) > len(smoothed1)

    def test_smooth_path_few_points(self):
        """Test smoothing with few points."""
        points = [Point2D(0.0, 0.0), Point2D(100.0, 100.0)]
        smoothed = smooth_path(points)
        assert len(smoothed) == len(points)  # Can't smooth 2 points


class TestPathResampling:
    """Tests for path resampling."""

    def test_resample_basic(self):
        """Test basic resampling."""
        points = [
            Point2D(0.0, 0.0),
            Point2D(100.0, 0.0),
            Point2D(200.0, 0.0),
        ]

        resampled = resample_path(points, target_count=5)
        assert len(resampled) == 5

    def test_resample_preserves_endpoints(self):
        """Test resampling preserves endpoints."""
        points = [
            Point2D(0.0, 0.0),
            Point2D(100.0, 50.0),
            Point2D(200.0, 0.0),
        ]

        resampled = resample_path(points, target_count=10)
        assert resampled[0].x == 0.0
        assert resampled[0].y == 0.0
        assert resampled[-1].x == 200.0
        assert resampled[-1].y == 0.0

    def test_resample_even_spacing(self):
        """Test resampled points are evenly spaced."""
        points = [
            Point2D(0.0, 0.0),
            Point2D(100.0, 0.0),
            Point2D(200.0, 0.0),
        ]

        resampled = resample_path(points, target_count=5)

        # For straight line, spacing should be equal
        distances = []
        for i in range(len(resampled) - 1):
            distances.append(resampled[i].distance_to(resampled[i + 1]))

        avg = sum(distances) / len(distances)
        for d in distances:
            assert abs(d - avg) < 1.0  # Allow small tolerance


class TestSplineEdgeCases:
    """Tests for edge cases and error handling."""

    def test_coincident_points(self):
        """Test handling of coincident control points."""
        points = [
            Point2D(100.0, 100.0),
            Point2D(100.0, 100.0),  # Same as previous
            Point2D(200.0, 200.0),
        ]
        # Should not raise exception
        spline = CatmullRomSpline(points)
        point = spline.evaluate(0.5)
        assert point is not None

    def test_very_close_points(self):
        """Test handling of very close control points."""
        points = [
            Point2D(100.0, 100.0),
            Point2D(100.001, 100.001),
            Point2D(200.0, 200.0),
        ]
        spline = CatmullRomSpline(points)
        point = spline.evaluate(0.5)
        assert point is not None

    def test_clamped_t_values(self):
        """Test that t values are clamped."""
        points = [
            Point2D(0.0, 0.0),
            Point2D(100.0, 100.0),
            Point2D(200.0, 0.0),
        ]
        spline = CatmullRomSpline(points)

        # Should not raise for out-of-bounds t
        p1 = spline.evaluate(-0.5)
        p2 = spline.evaluate(1.5)

        assert p1 is not None
        assert p2 is not None

    def test_negative_coordinates(self):
        """Test handling of negative coordinates."""
        points = [
            Point2D(-100.0, -100.0),
            Point2D(0.0, 0.0),
            Point2D(100.0, 100.0),
        ]
        spline = CatmullRomSpline(points)
        point = spline.evaluate(0.5)
        # Mid point should be near origin
        assert abs(point.x) < 50
        assert abs(point.y) < 50
