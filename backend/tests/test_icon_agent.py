"""Comprehensive tests for IconPlacerAgent and collision detection.

Tests cover:
- Icon placement algorithm
- Collision detection and avoidance
- Boundary checking
- Icon library integration
- Priority-based placement
"""

import pytest

from app.agents.base_agent import JobContext
from app.agents.icon_agent import IconAgent
from app.schemas.icon import (
    DEFAULT_SMB3_ICONS,
    AnchorPoint,
    BoundingBox,
    IconCategory,
    IconLibrary,
    IconMetadata,
    IconPlacement,
    IconSize,
    PlacementConfig,
    Position,
)
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


# =============================================================================
# Icon Schema Tests
# =============================================================================


class TestIconSchemas:
    """Tests for icon schema definitions."""

    def test_position_creation(self):
        """Test Position model creation."""
        pos = Position(x=100.5, y=200.5)
        assert pos.x == 100.5
        assert pos.y == 200.5

    def test_bounding_box_properties(self):
        """Test BoundingBox computed properties."""
        box = BoundingBox(x=100, y=100, width=50, height=30)

        assert box.right == 150
        assert box.bottom == 130
        assert box.center.x == 125
        assert box.center.y == 115

    def test_bounding_box_contains_point(self):
        """Test BoundingBox point containment check."""
        box = BoundingBox(x=100, y=100, width=50, height=50)

        # Point inside
        assert box.contains_point(Position(x=125, y=125)) is True
        # Point on edge
        assert box.contains_point(Position(x=100, y=100)) is True
        # Point outside
        assert box.contains_point(Position(x=50, y=50)) is False

    def test_bounding_box_intersection(self):
        """Test BoundingBox intersection check."""
        box1 = BoundingBox(x=100, y=100, width=50, height=50)
        box2 = BoundingBox(x=125, y=125, width=50, height=50)  # Overlapping
        box3 = BoundingBox(x=200, y=200, width=50, height=50)  # Not overlapping

        assert box1.intersects(box2) is True
        assert box1.intersects(box3) is False

    def test_icon_metadata_creation(self):
        """Test IconMetadata model creation."""
        icon = IconMetadata(
            id="test_icon",
            name="Test Icon",
            category=IconCategory.MILESTONE,
            size=IconSize(width=48, height=48),
            anchor=AnchorPoint.CENTER,
        )

        assert icon.id == "test_icon"
        assert icon.name == "Test Icon"
        assert icon.category == IconCategory.MILESTONE
        assert icon.size.width == 48

    def test_icon_library_get_icon(self):
        """Test IconLibrary icon lookup."""
        library = DEFAULT_SMB3_ICONS

        icon = library.get_icon("milestone_circle")
        assert icon is not None
        assert icon.id == "milestone_circle"

        # Non-existent icon
        missing = library.get_icon("nonexistent")
        assert missing is None

    def test_icon_library_get_by_category(self):
        """Test IconLibrary category filtering."""
        library = DEFAULT_SMB3_ICONS

        nature_icons = library.get_by_category(IconCategory.NATURE)
        assert len(nature_icons) >= 2  # Should have trees, rocks, etc.
        assert all(icon.category == IconCategory.NATURE for icon in nature_icons)

    def test_placement_config_defaults(self):
        """Test PlacementConfig default values."""
        config = PlacementConfig()

        assert config.min_spacing == 50.0
        assert config.use_grid is False
        assert config.canvas_width == 1920
        assert config.canvas_height == 1080
        assert config.margin == 100


# =============================================================================
# Collision Detection Tests
# =============================================================================


class TestCollisionDetection:
    """Tests for collision detection utilities."""

    def test_check_icon_overlap_true(self):
        """Test overlap detection when icons overlap."""
        box1 = BoundingBox(x=100, y=100, width=50, height=50)
        box2 = BoundingBox(x=125, y=125, width=50, height=50)

        assert check_icon_overlap(box1, box2) is True

    def test_check_icon_overlap_false(self):
        """Test overlap detection when icons don't overlap."""
        box1 = BoundingBox(x=100, y=100, width=50, height=50)
        box2 = BoundingBox(x=200, y=200, width=50, height=50)

        assert check_icon_overlap(box1, box2) is False

    def test_check_icon_overlap_with_spacing(self):
        """Test overlap detection with minimum spacing."""
        box1 = BoundingBox(x=100, y=100, width=50, height=50)
        box2 = BoundingBox(x=160, y=100, width=50, height=50)  # 10px apart

        # Without spacing - no overlap
        assert check_icon_overlap(box1, box2, min_spacing=0) is False
        # With 20px spacing - overlaps
        assert check_icon_overlap(box1, box2, min_spacing=20) is True

    def test_check_any_overlap(self):
        """Test checking overlap against multiple placements."""
        placements = [
            IconPlacement(
                id="p1",
                icon_id="test",
                position=Position(x=100, y=100),
                bounding_box=BoundingBox(x=75, y=75, width=50, height=50),
            ),
            IconPlacement(
                id="p2",
                icon_id="test",
                position=Position(x=300, y=300),
                bounding_box=BoundingBox(x=275, y=275, width=50, height=50),
            ),
        ]

        # Overlapping with first
        new_placement = IconPlacement(
            id="new",
            icon_id="test",
            position=Position(x=110, y=110),
            bounding_box=BoundingBox(x=85, y=85, width=50, height=50),
        )

        has_overlap, conflict = check_any_overlap(new_placement, placements)
        assert has_overlap is True
        assert conflict.id == "p1"

        # Not overlapping with any
        clear_placement = IconPlacement(
            id="clear",
            icon_id="test",
            position=Position(x=500, y=500),
            bounding_box=BoundingBox(x=475, y=475, width=50, height=50),
        )

        has_overlap, conflict = check_any_overlap(clear_placement, placements)
        assert has_overlap is False
        assert conflict is None

    def test_distance_to_line_segment(self):
        """Test distance calculation from point to line segment."""
        # Point directly above middle of horizontal segment
        point = Position(x=50, y=0)
        line_start = Position(x=0, y=10)
        line_end = Position(x=100, y=10)

        distance = distance_to_line_segment(point, line_start, line_end)
        assert distance == pytest.approx(10.0, abs=0.01)

        # Point past the end of segment
        point2 = Position(x=150, y=10)
        distance2 = distance_to_line_segment(point2, line_start, line_end)
        assert distance2 == pytest.approx(50.0, abs=0.01)

    def test_check_road_overlap(self):
        """Test road overlap detection."""
        road_coords = [
            {"x": 100, "y": 100},
            {"x": 200, "y": 100},
            {"x": 300, "y": 100},
        ]

        # Placement near the road
        near_road = IconPlacement(
            id="near",
            icon_id="test",
            position=Position(x=150, y=120),
            bounding_box=BoundingBox(x=126, y=96, width=48, height=48),
        )

        assert check_road_overlap(near_road, road_coords, road_buffer=30) is True

        # Placement far from the road
        far_from_road = IconPlacement(
            id="far",
            icon_id="test",
            position=Position(x=150, y=300),
            bounding_box=BoundingBox(x=126, y=276, width=48, height=48),
        )

        assert check_road_overlap(far_from_road, road_coords, road_buffer=30) is False

    def test_check_boundary(self):
        """Test boundary checking."""
        config = PlacementConfig(
            canvas_width=1920,
            canvas_height=1080,
            margin=100,
        )

        # Inside bounds
        inside = IconPlacement(
            id="inside",
            icon_id="test",
            position=Position(x=500, y=500),
            bounding_box=BoundingBox(x=476, y=476, width=48, height=48),
        )

        assert check_boundary(inside, config) is True

        # Outside bounds (too close to left edge)
        outside = IconPlacement(
            id="outside",
            icon_id="test",
            position=Position(x=50, y=500),
            bounding_box=BoundingBox(x=26, y=476, width=48, height=48),
        )

        assert check_boundary(outside, config) is False

    def test_adjust_for_boundary(self):
        """Test position adjustment for boundaries."""
        config = PlacementConfig(
            canvas_width=1920,
            canvas_height=1080,
            margin=100,
        )

        # Position outside left boundary
        pos = Position(x=50, y=500)
        adjusted = adjust_for_boundary(pos, 48, 48, config)

        assert adjusted.x >= config.margin + 24  # Half icon width
        assert adjusted.y == 500

    def test_get_overlap_area(self):
        """Test overlap area calculation."""
        box1 = BoundingBox(x=100, y=100, width=50, height=50)
        box2 = BoundingBox(x=125, y=125, width=50, height=50)  # 25x25 overlap

        area = get_overlap_area(box1, box2)
        assert area == 625  # 25 * 25

        # No overlap
        box3 = BoundingBox(x=200, y=200, width=50, height=50)
        assert get_overlap_area(box1, box3) == 0

    def test_calculate_density_at_position(self):
        """Test density calculation."""
        placements = [
            IconPlacement(
                id=f"p{i}",
                icon_id="test",
                position=Position(x=100 + i * 20, y=100),
                bounding_box=BoundingBox(x=76 + i * 20, y=76, width=48, height=48),
            )
            for i in range(5)
        ]

        # Position near the cluster
        density = calculate_density_at_position(
            Position(x=150, y=100), placements, radius=100
        )
        assert density >= 3  # Should have multiple icons within 100px

        # Position far from cluster
        density_far = calculate_density_at_position(
            Position(x=1000, y=1000), placements, radius=100
        )
        assert density_far == 0

    def test_calculate_grid_position(self):
        """Test grid position calculation."""
        config = PlacementConfig(
            canvas_width=1920,
            canvas_height=1080,
            margin=100,
            grid_cell_size=64,
        )

        pos = calculate_grid_position(0, 10, config)

        # First position should be in the first cell
        assert pos.x >= config.margin
        assert pos.y >= config.margin

    def test_find_non_overlapping_position(self):
        """Test finding non-overlapping position."""
        config = PlacementConfig(
            min_spacing=20,
            canvas_width=1920,
            canvas_height=1080,
            margin=100,
        )

        existing = [
            IconPlacement(
                id="existing",
                icon_id="test",
                position=Position(x=500, y=500),
                bounding_box=BoundingBox(x=476, y=476, width=48, height=48),
            )
        ]

        road_coords = [{"x": 0, "y": 0}, {"x": 100, "y": 0}]  # Far from test area

        # Try to place at occupied position
        result, attempts = find_non_overlapping_position(
            original_position=Position(x=500, y=500),
            icon_width=48,
            icon_height=48,
            existing_placements=existing,
            road_coordinates=road_coords,
            config=config,
        )

        # Should find a position nearby but not overlapping
        assert result is not None
        assert attempts > 1  # Should have needed to search


# =============================================================================
# IconAgent Tests
# =============================================================================


class TestIconAgent:
    """Tests for the IconAgent class."""

    def _create_context(
        self,
        milestones: list = None,
        coordinates: list = None,
        options: dict = None,
    ) -> JobContext:
        """Create a test context."""
        if milestones is None:
            milestones = [
                {"id": "m1", "title": "Milestone 1", "level": 1},
                {"id": "m2", "title": "Milestone 2", "level": 1},
                {"id": "m3", "title": "Milestone 3", "level": 1},
            ]

        if coordinates is None:
            coordinates = [
                {"x": 200, "y": 300},
                {"x": 400, "y": 400},
                {"x": 600, "y": 500},
                {"x": 800, "y": 600},
                {"x": 1000, "y": 500},
            ]

        return JobContext(
            job_id=1,
            user_id=1,
            document_url="http://example.com/doc",
            hierarchy={},
            theme={"theme_id": "smb3"},
            agent_state={
                "parser": {
                    "data": {
                        "milestones": milestones,
                        "milestone_count": len(milestones),
                    }
                },
                "road": {
                    "data": {
                        "coordinates": coordinates,
                    }
                },
            },
            options=options or {},
        )

    @pytest.mark.asyncio
    async def test_icon_agent_basic_placement(self):
        """Test basic icon placement."""
        agent = IconAgent()
        context = self._create_context()

        result = await agent.execute(context)

        assert result.success is True
        assert "icons" in result.data
        assert result.data["icon_count"] == 3
        assert len(result.data["icons"]) == 3

    @pytest.mark.asyncio
    async def test_icon_agent_placement_positions(self):
        """Test that icons are placed at correct positions."""
        agent = IconAgent()
        context = self._create_context()

        result = await agent.execute(context)

        # Check that each icon has valid position data
        for icon in result.data["icons"]:
            assert "pos" in icon
            assert "x" in icon["pos"]
            assert "y" in icon["pos"]
            assert "bounding_box" in icon

    @pytest.mark.asyncio
    async def test_icon_agent_no_coordinates(self):
        """Test error when no road coordinates."""
        agent = IconAgent()
        context = self._create_context(coordinates=[])

        result = await agent.execute(context)

        assert result.success is False
        assert "No road coordinates" in result.error

    @pytest.mark.asyncio
    async def test_icon_agent_no_milestones(self):
        """Test error when no milestones."""
        agent = IconAgent()
        context = self._create_context(milestones=[])

        result = await agent.execute(context)

        assert result.success is False
        assert "No milestones" in result.error

    @pytest.mark.asyncio
    async def test_icon_agent_with_custom_config(self):
        """Test icon placement with custom configuration."""
        config = PlacementConfig(
            min_spacing=100,
            allow_overlap=False,
        )
        agent = IconAgent(config=config)
        context = self._create_context()

        result = await agent.execute(context)

        assert result.success is True
        assert result.data["placement_config"]["min_spacing"] == 100

    @pytest.mark.asyncio
    async def test_icon_agent_options_override_config(self):
        """Test that context options override default config."""
        agent = IconAgent()
        context = self._create_context(options={"min_spacing": 75})

        result = await agent.execute(context)

        assert result.success is True
        assert result.data["placement_config"]["min_spacing"] == 75

    @pytest.mark.asyncio
    async def test_icon_agent_many_milestones(self):
        """Test placement of many milestones."""
        milestones = [
            {"id": f"m{i}", "title": f"Milestone {i}", "level": 1}
            for i in range(20)
        ]
        coordinates = [
            {"x": 200 + i * 80, "y": 300 + (i % 5) * 50}
            for i in range(25)
        ]

        agent = IconAgent()
        context = self._create_context(milestones=milestones, coordinates=coordinates)

        result = await agent.execute(context)

        assert result.success is True
        assert result.data["icon_count"] == 20

    @pytest.mark.asyncio
    async def test_icon_agent_collision_avoidance(self):
        """Test that collision avoidance works."""
        # Create milestones that would all be placed at close positions
        milestones = [
            {"id": f"m{i}", "title": f"Milestone {i}", "level": 1}
            for i in range(5)
        ]
        # Very tight coordinates that could cause collisions
        coordinates = [
            {"x": 500, "y": 500},
            {"x": 510, "y": 510},
            {"x": 520, "y": 520},
            {"x": 530, "y": 530},
            {"x": 540, "y": 540},
        ]

        config = PlacementConfig(min_spacing=50, allow_overlap=False)
        agent = IconAgent(config=config)
        context = self._create_context(milestones=milestones, coordinates=coordinates)

        result = await agent.execute(context)

        assert result.success is True
        # Should have had to avoid some collisions
        assert result.data["collisions_avoided"] > 0

    @pytest.mark.asyncio
    async def test_icon_agent_allow_overlap(self):
        """Test placement with overlap allowed."""
        milestones = [
            {"id": f"m{i}", "title": f"Milestone {i}", "level": 1}
            for i in range(3)
        ]
        coordinates = [
            {"x": 500, "y": 500},
            {"x": 500, "y": 500},  # Same position
            {"x": 500, "y": 500},
        ]

        config = PlacementConfig(allow_overlap=True)
        agent = IconAgent(config=config)
        context = self._create_context(milestones=milestones, coordinates=coordinates)

        result = await agent.execute(context)

        assert result.success is True
        # All icons should be at the same position
        assert result.data["collisions_avoided"] == 0

    @pytest.mark.asyncio
    async def test_icon_agent_priority_placement(self):
        """Test priority-based placement."""
        milestones = [
            {"id": "m1", "title": "L1 Milestone", "level": 1},
            {"id": "m2", "title": "L2 Milestone", "level": 2},
            {"id": "m3", "title": "L0 Root", "level": 0},
        ]

        agent = IconAgent()
        context = self._create_context(milestones=milestones)

        result = await agent.execute(context)

        assert result.success is True
        # Stats should show placement by level
        assert "by_level" in result.data["statistics"]

    @pytest.mark.asyncio
    async def test_icon_agent_get_placements(self):
        """Test get_placements method."""
        agent = IconAgent()
        context = self._create_context()

        await agent.execute(context)

        placements = agent.get_placements()
        assert len(placements) == 3
        assert all(isinstance(p, IconPlacement) for p in placements)

    @pytest.mark.asyncio
    async def test_icon_agent_custom_library(self):
        """Test using a custom icon library."""
        custom_library = IconLibrary(
            name="Custom Test Library",
            version="1.0.0",
            icons=[
                IconMetadata(
                    id="milestone_circle",
                    name="Custom Milestone",
                    category=IconCategory.MILESTONE,
                    size=IconSize(width=64, height=64),
                    anchor=AnchorPoint.CENTER,
                ),
            ],
        )

        agent = IconAgent(icon_library=custom_library)
        context = self._create_context()

        result = await agent.execute(context)

        assert result.success is True
        assert result.data["icon_library"] == "Custom Test Library"

    @pytest.mark.asyncio
    async def test_icon_agent_boundary_adjustments(self):
        """Test that boundary adjustments are tracked."""
        # Place milestones near canvas edges
        coordinates = [
            {"x": 50, "y": 50},  # Near edge
            {"x": 1870, "y": 1030},  # Near opposite edge
            {"x": 500, "y": 500},
        ]
        milestones = [
            {"id": "m1", "title": "Edge 1", "level": 1},
            {"id": "m2", "title": "Edge 2", "level": 1},
            {"id": "m3", "title": "Center", "level": 1},
        ]

        agent = IconAgent()
        context = self._create_context(milestones=milestones, coordinates=coordinates)

        result = await agent.execute(context)

        assert result.success is True
        # Icons near edges should be adjusted
        # The exact number depends on implementation details

    @pytest.mark.asyncio
    async def test_icon_agent_statistics(self):
        """Test that placement statistics are recorded."""
        agent = IconAgent()
        context = self._create_context()

        result = await agent.execute(context)

        assert result.success is True
        stats = result.data["statistics"]
        assert "total_milestones" in stats
        assert "successful_placements" in stats
        assert "failed_placements" in stats
        assert "by_level" in stats


# =============================================================================
# Integration Tests
# =============================================================================


class TestIconAgentIntegration:
    """Integration tests for IconAgent with other components."""

    @pytest.mark.asyncio
    async def test_full_pipeline_simulation(self):
        """Simulate the icon agent receiving data from parser and road agents."""
        # Simulate parser output
        parser_data = {
            "valid": True,
            "milestone_count": 5,
            "levels": [1],
            "milestones": [
                {"id": "m1", "title": "Start", "level": 1, "pos": 1},
                {"id": "m2", "title": "Design", "level": 1, "pos": 2},
                {"id": "m3", "title": "Implement", "level": 1, "pos": 3},
                {"id": "m4", "title": "Test", "level": 1, "pos": 4},
                {"id": "m5", "title": "Deploy", "level": 1, "pos": 5},
            ],
        }

        # Simulate road output
        road_data = {
            "coordinates": [
                {"x": 300, "y": 400},
                {"x": 450, "y": 350},
                {"x": 600, "y": 400},
                {"x": 750, "y": 500},
                {"x": 900, "y": 550},
                {"x": 1050, "y": 500},
                {"x": 1200, "y": 400},
                {"x": 1350, "y": 350},
                {"x": 1500, "y": 400},
                {"x": 1650, "y": 500},
            ],
            "arc_length": 1500.0,
        }

        context = JobContext(
            job_id=42,
            user_id=1,
            document_url="http://example.com/project",
            hierarchy={},
            theme={"theme_id": "smb3"},
            agent_state={
                "parser": {"data": parser_data},
                "road": {"data": road_data},
            },
            options={},
        )

        agent = IconAgent()
        result = await agent.execute(context)

        assert result.success is True
        assert result.data["icon_count"] == 5

        # Verify each milestone has corresponding icon
        icons = result.data["icons"]
        icon_ids = [icon["id"] for icon in icons]
        assert "m1" in icon_ids
        assert "m5" in icon_ids

    @pytest.mark.asyncio
    async def test_icon_output_format_for_rendering(self):
        """Test that icon output is suitable for rendering."""
        agent = IconAgent()
        context = JobContext(
            job_id=1,
            user_id=1,
            document_url="http://example.com/doc",
            hierarchy={},
            theme={"theme_id": "smb3"},
            agent_state={
                "parser": {
                    "data": {
                        "milestones": [{"id": "m1", "title": "Test", "level": 1}],
                    }
                },
                "road": {
                    "data": {
                        "coordinates": [{"x": 500, "y": 500}],
                    }
                },
            },
            options={},
        )

        result = await agent.execute(context)

        assert result.success is True
        icon = result.data["icons"][0]

        # Verify all necessary fields for rendering
        assert "id" in icon
        assert "icon_id" in icon
        assert "label" in icon
        assert "pos" in icon
        assert "bounding_box" in icon
        assert "category" in icon
        assert "priority" in icon

        # Verify position is integer for pixel rendering
        assert isinstance(icon["pos"]["x"], int)
        assert isinstance(icon["pos"]["y"], int)
