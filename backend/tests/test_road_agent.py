"""Tests for RoadGeneratorAgent.

This module contains comprehensive tests for the road generation agent including:
- Basic road generation
- Road type and style handling
- Spline-based path creation
- Intersection detection
- Configuration options
- Backward compatibility
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.base_agent import AgentResult, JobContext
from app.agents.road_agent import RoadAgent, RoadGeneratorAgent
from app.schemas.road import (
    ControlPoint,
    DEFAULT_ROAD_STYLES,
    RoadGenerationConfig,
    RoadNetwork,
    RoadType,
    SplineConfig,
)


class TestRoadGeneratorAgentBasic:
    """Basic tests for RoadGeneratorAgent."""

    @pytest.fixture
    def agent(self):
        """Create a default agent instance."""
        return RoadGeneratorAgent()

    @pytest.fixture
    def basic_context(self):
        """Create a basic job context."""
        return JobContext(
            job_id=1,
            user_id=1,
            document_url="http://example.com/doc",
            hierarchy={},
            theme={"theme_id": "smb3"},
            agent_state={
                "parser": {
                    "data": {
                        "milestone_count": 5,
                        "milestones": [],
                    }
                }
            },
            options={},
        )

    @pytest.mark.asyncio
    async def test_execute_basic(self, agent, basic_context):
        """Test basic execution."""
        result = await agent.execute(basic_context)

        assert result.success is True
        assert result.data is not None
        assert "coordinates" in result.data
        assert "control_points" in result.data
        assert "arc_length" in result.data

    @pytest.mark.asyncio
    async def test_execute_returns_coordinates(self, agent, basic_context):
        """Test that execution returns coordinate list."""
        result = await agent.execute(basic_context)

        assert result.success is True
        coordinates = result.data["coordinates"]
        assert isinstance(coordinates, list)
        assert len(coordinates) > 0

        # Each coordinate should have x and y
        for coord in coordinates:
            assert "x" in coord
            assert "y" in coord
            assert isinstance(coord["x"], int)
            assert isinstance(coord["y"], int)

    @pytest.mark.asyncio
    async def test_execute_returns_control_points(self, agent, basic_context):
        """Test that execution returns control points."""
        result = await agent.execute(basic_context)

        assert result.success is True
        control_points = result.data["control_points"]
        assert isinstance(control_points, list)
        assert len(control_points) >= 2

    @pytest.mark.asyncio
    async def test_execute_returns_arc_length(self, agent, basic_context):
        """Test that execution returns positive arc length."""
        result = await agent.execute(basic_context)

        assert result.success is True
        arc_length = result.data["arc_length"]
        assert arc_length > 0

    @pytest.mark.asyncio
    async def test_execute_returns_road_network(self, agent, basic_context):
        """Test that execution returns road network structure."""
        result = await agent.execute(basic_context)

        assert result.success is True
        assert "road_network" in result.data
        road_network = result.data["road_network"]

        assert "roads" in road_network
        assert "intersections" in road_network
        assert "total_road_count" in road_network


class TestRoadGeneratorAgentMilestones:
    """Tests for milestone-based road generation."""

    @pytest.fixture
    def agent(self):
        """Create agent instance."""
        return RoadGeneratorAgent()

    @pytest.mark.asyncio
    async def test_respects_milestone_count(self, agent):
        """Test that milestone count affects output."""
        context = JobContext(
            job_id=1,
            user_id=1,
            document_url="http://example.com/doc",
            hierarchy={},
            theme={"theme_id": "smb3"},
            agent_state={
                "parser": {
                    "data": {
                        "milestone_count": 10,
                        "milestones": [],
                    }
                }
            },
            options={},
        )

        result = await agent.execute(context)
        assert result.success is True

        # More milestones should produce more control points
        assert len(result.data["control_points"]) >= 10

    @pytest.mark.asyncio
    async def test_uses_milestone_positions(self, agent):
        """Test using milestone position data."""
        context = JobContext(
            job_id=1,
            user_id=1,
            document_url="http://example.com/doc",
            hierarchy={},
            theme={"theme_id": "smb3"},
            agent_state={
                "parser": {
                    "data": {
                        "milestone_count": 3,
                        "milestones": [
                            {"id": "m1", "x": 200, "y": 300},
                            {"id": "m2", "x": 500, "y": 400},
                            {"id": "m3", "x": 800, "y": 300},
                        ],
                    }
                }
            },
            options={"scatter_threshold": 0},  # No scatter
        )

        result = await agent.execute(context)
        assert result.success is True

        # Control points should be near milestone positions
        control_points = result.data["control_points"]
        assert len(control_points) == 3

        # First point should be near (200, 300)
        assert abs(control_points[0]["x"] - 200) < 100
        assert abs(control_points[0]["y"] - 300) < 100


class TestRoadGeneratorAgentTypes:
    """Tests for different road types."""

    @pytest.fixture
    def agent(self):
        """Create agent instance."""
        return RoadGeneratorAgent()

    @pytest.fixture
    def basic_context(self):
        """Create basic context."""
        return JobContext(
            job_id=1,
            user_id=1,
            document_url="http://example.com/doc",
            hierarchy={},
            theme={"theme_id": "smb3"},
            agent_state={
                "parser": {"data": {"milestone_count": 5}}
            },
            options={},
        )

    @pytest.mark.asyncio
    async def test_dirt_path_type(self, agent, basic_context):
        """Test dirt path road type."""
        basic_context.options["road_type"] = "dirt_path"
        result = await agent.execute(basic_context)

        assert result.success is True
        assert result.data["road_type"] == "dirt_path"

    @pytest.mark.asyncio
    async def test_cobblestone_type(self, agent, basic_context):
        """Test cobblestone road type."""
        basic_context.options["road_type"] = "cobblestone"
        result = await agent.execute(basic_context)

        assert result.success is True
        assert result.data["road_type"] == "cobblestone"

    @pytest.mark.asyncio
    async def test_paved_road_type(self, agent, basic_context):
        """Test paved road type."""
        basic_context.options["road_type"] = "paved_road"
        result = await agent.execute(basic_context)

        assert result.success is True
        assert result.data["road_type"] == "paved_road"

    @pytest.mark.asyncio
    async def test_invalid_road_type_defaults(self, agent, basic_context):
        """Test that invalid road type defaults to dirt_path."""
        basic_context.options["road_type"] = "invalid_type"
        result = await agent.execute(basic_context)

        assert result.success is True
        assert result.data["road_type"] == "dirt_path"

    @pytest.mark.asyncio
    async def test_all_road_types(self, agent, basic_context):
        """Test all defined road types work."""
        for road_type in RoadType:
            basic_context.options["road_type"] = road_type.value
            result = await agent.execute(basic_context)
            assert result.success is True, f"Failed for road type: {road_type}"


class TestRoadGeneratorAgentConfiguration:
    """Tests for agent configuration."""

    @pytest.mark.asyncio
    async def test_custom_config(self):
        """Test agent with custom configuration."""
        config = RoadGenerationConfig(
            default_road_type=RoadType.COBBLESTONE,
            apply_smoothing=False,
            apply_scatter=False,
            canvas_width=800,
            canvas_height=600,
        )
        agent = RoadGeneratorAgent(config=config)

        context = JobContext(
            job_id=1,
            user_id=1,
            document_url="http://example.com/doc",
            hierarchy={},
            theme={"theme_id": "smb3"},
            agent_state={"parser": {"data": {"milestone_count": 5}}},
            options={},
        )

        result = await agent.execute(context)
        assert result.success is True

        # Check bounds reflect custom canvas size
        road_network = result.data["road_network"]
        bounds = road_network["bounds"]
        assert bounds["max_x"] <= 800
        assert bounds["max_y"] <= 600

    @pytest.mark.asyncio
    async def test_scatter_threshold_option(self):
        """Test scatter threshold from options."""
        agent = RoadGeneratorAgent()

        # With zero scatter
        context = JobContext(
            job_id=1,
            user_id=1,
            document_url="http://example.com/doc",
            hierarchy={},
            theme={"theme_id": "smb3"},
            agent_state={"parser": {"data": {"milestone_count": 5}}},
            options={"scatter_threshold": 0},
        )

        result = await agent.execute(context)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_seed_produces_deterministic_output(self):
        """Test that same seed produces same output."""
        agent = RoadGeneratorAgent()

        context1 = JobContext(
            job_id=1,
            user_id=1,
            document_url="http://example.com/doc",
            hierarchy={},
            theme={"theme_id": "smb3"},
            agent_state={"parser": {"data": {"milestone_count": 5}}},
            options={"seed": 12345, "scatter_threshold": 20},
        )

        context2 = JobContext(
            job_id=2,
            user_id=1,
            document_url="http://example.com/doc",
            hierarchy={},
            theme={"theme_id": "smb3"},
            agent_state={"parser": {"data": {"milestone_count": 5}}},
            options={"seed": 12345, "scatter_threshold": 20},
        )

        result1 = await agent.execute(context1)
        result2 = await agent.execute(context2)

        # Same seed should produce same coordinates
        assert result1.data["control_points"] == result2.data["control_points"]


class TestRoadGeneratorAgentSpline:
    """Tests for spline-specific functionality."""

    @pytest.fixture
    def agent(self):
        """Create agent with specific spline config."""
        config = RoadGenerationConfig(
            spline_config=SplineConfig(
                alpha=0.5,
                samples_per_segment=20,
                use_arc_length=True,
            ),
            apply_smoothing=False,
            apply_scatter=False,
        )
        return RoadGeneratorAgent(config=config)

    @pytest.fixture
    def basic_context(self):
        """Create basic context."""
        return JobContext(
            job_id=1,
            user_id=1,
            document_url="http://example.com/doc",
            hierarchy={},
            theme={"theme_id": "smb3"},
            agent_state={"parser": {"data": {"milestone_count": 5}}},
            options={},
        )

    @pytest.mark.asyncio
    async def test_spline_type_in_output(self, agent, basic_context):
        """Test spline type is in output."""
        result = await agent.execute(basic_context)

        assert result.success is True
        assert result.data["spline_type"] == "catmull_rom"

    @pytest.mark.asyncio
    async def test_alpha_in_output(self, agent, basic_context):
        """Test alpha parameter is in output."""
        result = await agent.execute(basic_context)

        assert result.success is True
        assert "alpha" in result.data
        assert result.data["alpha"] == 0.5

    @pytest.mark.asyncio
    async def test_coordinates_are_smooth(self, agent, basic_context):
        """Test that generated coordinates form a smooth path."""
        result = await agent.execute(basic_context)

        assert result.success is True
        coordinates = result.data["coordinates"]

        # Check that consecutive points aren't too far apart
        # (indicates smooth interpolation)
        max_gap = 0
        for i in range(len(coordinates) - 1):
            dx = coordinates[i + 1]["x"] - coordinates[i]["x"]
            dy = coordinates[i + 1]["y"] - coordinates[i]["y"]
            gap = (dx ** 2 + dy ** 2) ** 0.5
            max_gap = max(max_gap, gap)

        # Gap should be reasonable (not > 100 pixels)
        assert max_gap < 100


class TestRoadGeneratorAgentBounds:
    """Tests for canvas bounds handling."""

    @pytest.mark.asyncio
    async def test_coordinates_within_bounds(self):
        """Test all coordinates are within canvas bounds."""
        config = RoadGenerationConfig(
            canvas_width=1920,
            canvas_height=1080,
            margin=50,
        )
        agent = RoadGeneratorAgent(config=config)

        context = JobContext(
            job_id=1,
            user_id=1,
            document_url="http://example.com/doc",
            hierarchy={},
            theme={"theme_id": "smb3"},
            agent_state={"parser": {"data": {"milestone_count": 10}}},
            options={"scatter_threshold": 50},
        )

        result = await agent.execute(context)
        assert result.success is True

        for coord in result.data["coordinates"]:
            assert coord["x"] >= 50, f"X too small: {coord['x']}"
            assert coord["x"] <= 1870, f"X too large: {coord['x']}"
            assert coord["y"] >= 50, f"Y too small: {coord['y']}"
            assert coord["y"] <= 1030, f"Y too large: {coord['y']}"


class TestRoadGeneratorAgentBackwardCompatibility:
    """Tests for backward compatibility."""

    def test_road_agent_alias(self):
        """Test that RoadAgent is an alias for RoadGeneratorAgent."""
        assert RoadAgent is RoadGeneratorAgent

    @pytest.mark.asyncio
    async def test_legacy_coordinate_format(self):
        """Test legacy coordinate format in output."""
        agent = RoadAgent()  # Using alias

        context = JobContext(
            job_id=1,
            user_id=1,
            document_url="http://example.com/doc",
            hierarchy={},
            theme={"theme_id": "smb3"},
            agent_state={"parser": {"milestone_count": 5}},
            options={},
        )

        result = await agent.execute(context)

        assert result.success is True
        # Legacy format checks
        assert "coordinates" in result.data
        assert "control_points" in result.data
        assert "arc_length" in result.data
        assert "milestone_count" in result.data


class TestRoadGeneratorAgentEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def agent(self):
        """Create agent instance."""
        return RoadGeneratorAgent()

    @pytest.mark.asyncio
    async def test_empty_parser_data(self, agent):
        """Test handling of empty parser data."""
        context = JobContext(
            job_id=1,
            user_id=1,
            document_url="http://example.com/doc",
            hierarchy={},
            theme={"theme_id": "smb3"},
            agent_state={},  # No parser data
            options={},
        )

        result = await agent.execute(context)
        # Should succeed with default values
        assert result.success is True

    @pytest.mark.asyncio
    async def test_single_milestone(self, agent):
        """Test handling of single milestone."""
        context = JobContext(
            job_id=1,
            user_id=1,
            document_url="http://example.com/doc",
            hierarchy={},
            theme={"theme_id": "smb3"},
            agent_state={
                "parser": {"data": {"milestone_count": 1}}
            },
            options={},
        )

        result = await agent.execute(context)
        # Should succeed even with minimal milestones
        assert result.success is True

    @pytest.mark.asyncio
    async def test_large_milestone_count(self, agent):
        """Test handling of large milestone count."""
        context = JobContext(
            job_id=1,
            user_id=1,
            document_url="http://example.com/doc",
            hierarchy={},
            theme={"theme_id": "smb3"},
            agent_state={
                "parser": {"data": {"milestone_count": 50}}
            },
            options={},
        )

        result = await agent.execute(context)
        assert result.success is True
        # Should have many coordinates
        assert len(result.data["coordinates"]) > 100


class TestRoadGeneratorAgentRoadNetwork:
    """Tests for road network output structure."""

    @pytest.fixture
    def agent(self):
        """Create agent instance."""
        return RoadGeneratorAgent()

    @pytest.fixture
    def basic_context(self):
        """Create basic context."""
        return JobContext(
            job_id=1,
            user_id=1,
            document_url="http://example.com/doc",
            hierarchy={},
            theme={"theme_id": "smb3"},
            agent_state={"parser": {"data": {"milestone_count": 5}}},
            options={},
        )

    @pytest.mark.asyncio
    async def test_road_network_structure(self, agent, basic_context):
        """Test road network has correct structure."""
        result = await agent.execute(basic_context)

        assert result.success is True
        network = result.data["road_network"]

        # Check required fields
        assert "roads" in network
        assert "intersections" in network
        assert "total_road_count" in network
        assert "total_arc_length" in network
        assert "bounds" in network
        assert "generated_at" in network

    @pytest.mark.asyncio
    async def test_road_structure(self, agent, basic_context):
        """Test individual road has correct structure."""
        result = await agent.execute(basic_context)

        assert result.success is True
        roads = result.data["road_network"]["roads"]
        assert len(roads) >= 1

        road = roads[0]
        assert "id" in road
        assert "road_type" in road
        assert "style" in road
        assert "control_points" in road
        assert "segments" in road
        assert "total_arc_length" in road

    @pytest.mark.asyncio
    async def test_road_style_structure(self, agent, basic_context):
        """Test road style has correct structure."""
        result = await agent.execute(basic_context)

        assert result.success is True
        road = result.data["road_network"]["roads"][0]
        style = road["style"]

        # Check style fields
        assert "width" in style
        assert "color" in style
        assert "opacity" in style

    @pytest.mark.asyncio
    async def test_generation_params_recorded(self, agent, basic_context):
        """Test that generation params are recorded."""
        basic_context.options["scatter_threshold"] = 25
        basic_context.options["road_type"] = "cobblestone"

        result = await agent.execute(basic_context)

        assert result.success is True
        params = result.data["road_network"]["generation_params"]

        assert params["scatter_threshold"] == 25
        assert params["road_type"] == "cobblestone"


class TestRoadStyles:
    """Tests for road style definitions."""

    def test_all_road_types_have_styles(self):
        """Test that all road types have default styles."""
        for road_type in RoadType:
            assert road_type in DEFAULT_ROAD_STYLES, f"Missing style for {road_type}"

    def test_style_has_required_fields(self):
        """Test that styles have required fields."""
        for road_type, style in DEFAULT_ROAD_STYLES.items():
            assert style.width > 0, f"Invalid width for {road_type}"
            assert style.color.startswith("#"), f"Invalid color for {road_type}"
            assert 0 <= style.opacity <= 1, f"Invalid opacity for {road_type}"


class TestRoadGeneratorAgentBranchRoads:
    """Tests for branch road creation."""

    @pytest.mark.asyncio
    async def test_create_branch_road(self):
        """Test creating a branch road from main road."""
        agent = RoadGeneratorAgent()

        context = JobContext(
            job_id=1,
            user_id=1,
            document_url="http://example.com/doc",
            hierarchy={},
            theme={"theme_id": "smb3"},
            agent_state={"parser": {"data": {"milestone_count": 5}}},
            options={"scatter_threshold": 0},
        )

        result = await agent.execute(context)
        assert result.success is True

        # Get the main road
        main_road_data = result.data["road_network"]["roads"][0]

        # Create a branch road (need to reconstruct Road object)
        from app.schemas.road import Road, ControlPoint

        main_road = Road(**main_road_data)

        branch_end = ControlPoint(x=1500.0, y=200.0)
        branch = agent.create_branch_road(
            main_road=main_road,
            branch_point_t=0.5,
            end_point=branch_end,
        )

        assert branch is not None
        assert branch.road_type == RoadType.TRAIL
        assert len(branch.control_points) >= 2
