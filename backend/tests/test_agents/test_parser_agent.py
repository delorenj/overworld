"""Tests for STORY-005: ParserAgent.

This module tests both the legacy ParserAgent and the new EnhancedParserAgent
for document hierarchy parsing and map structure generation.
"""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from app.agents.base import ExecutionContext
from app.agents.base_agent import AgentResult, JobContext
from app.agents.messages import AgentRequest
from app.agents.parser_agent import (
    DetailPoint,
    EnhancedParserAgent,
    Landmark,
    MapMetadata,
    MapPath,
    MapStructure,
    ParserAgent,
    ParserInput,
    ParserOutput,
    Region,
    SourceMilestone,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def simple_hierarchy():
    """Simple hierarchy with L0 and L1 data."""
    return {
        "L0": {"title": "Test Project", "id": "root"},
        "L1": [
            {"id": "m1", "title": "Milestone 1"},
            {"id": "m2", "title": "Milestone 2"},
        ],
    }


@pytest.fixture
def complex_hierarchy():
    """Complex hierarchy with all levels (L0-L4)."""
    return {
        "L0": {"title": "Software Development Project", "id": "root"},
        "L1": [
            {"id": "m1", "title": "Planning Phase", "content": "Initial planning"},
            {"id": "m2", "title": "Development Phase", "content": "Core development"},
            {"id": "m3", "title": "Testing Phase", "content": "Quality assurance"},
        ],
        "L2": [
            {"id": "e1", "title": "Requirements Gathering", "parent_id": "m1"},
            {"id": "e2", "title": "Architecture Design", "parent_id": "m1"},
            {"id": "e3", "title": "Backend Development", "parent_id": "m2"},
            {"id": "e4", "title": "Frontend Development", "parent_id": "m2"},
        ],
        "L3": [
            {"id": "t1", "title": "User Interviews", "parent_id": "e1"},
            {"id": "t2", "title": "Database Schema", "parent_id": "e2"},
            {"id": "t3", "title": "API Endpoints", "parent_id": "e3"},
        ],
        "L4": [
            {"id": "st1", "title": "Interview Script", "parent_id": "t1"},
            {"id": "st2", "title": "Entity Relationships", "parent_id": "t2"},
        ],
    }


@pytest.fixture
def job_context(simple_hierarchy):
    """Create a legacy JobContext for testing."""
    return JobContext(
        job_id=1,
        user_id=1,
        document_url="http://example.com/doc",
        hierarchy=simple_hierarchy,
        theme={"theme_id": "smb3"},
        options={},
    )


@pytest.fixture
def agent_request(simple_hierarchy):
    """Create an AgentRequest for testing."""
    return AgentRequest(
        source_agent="test",
        job_id=1,
        input_data={
            "job_id": 1,
            "hierarchy": simple_hierarchy,
            "use_llm": False,
        },
        context={},
    )


@pytest.fixture
def mock_llm_response():
    """Mock LLM response with valid map structure."""
    return json.dumps({
        "map_title": "Test Project Map",
        "map_description": "A journey through the test project",
        "total_regions": 2,
        "total_landmarks": 0,
        "regions": [
            {
                "id": "r1",
                "name": "Milestone 1 Region",
                "theme": "forest",
                "position_hint": "start",
                "description": "The beginning of the journey",
                "source_milestone": {
                    "level": 1,
                    "id": "m1",
                    "title": "Milestone 1",
                },
                "landmarks": [],
            },
            {
                "id": "r2",
                "name": "Milestone 2 Region",
                "theme": "plains",
                "position_hint": "end",
                "description": "The final destination",
                "source_milestone": {
                    "level": 1,
                    "id": "m2",
                    "title": "Milestone 2",
                },
                "landmarks": [],
            },
        ],
        "paths": [
            {
                "id": "p1",
                "from_region": "r1",
                "to_region": "r2",
                "path_type": "road",
                "description": "Main road connecting the regions",
            }
        ],
        "metadata": {
            "complexity": "simple",
            "suggested_style": "linear",
            "estimated_journey_length": 2,
        },
    })


# =============================================================================
# Pydantic Model Tests
# =============================================================================


class TestPydanticModels:
    """Tests for Parser Agent Pydantic models."""

    def test_source_milestone_creation(self):
        """Test SourceMilestone model creation."""
        milestone = SourceMilestone(level=1, id="m1", title="Milestone 1")
        assert milestone.level == 1
        assert milestone.id == "m1"
        assert milestone.title == "Milestone 1"

    def test_source_milestone_validation(self):
        """Test SourceMilestone validation."""
        # Valid levels 0-4
        for level in range(5):
            milestone = SourceMilestone(level=level, id="test", title="Test")
            assert milestone.level == level

        # Invalid level should raise
        with pytest.raises(ValueError):
            SourceMilestone(level=5, id="test", title="Test")

        with pytest.raises(ValueError):
            SourceMilestone(level=-1, id="test", title="Test")

    def test_detail_point_creation(self):
        """Test DetailPoint model creation."""
        point = DetailPoint(
            id="dp1",
            name="Detail Point 1",
            icon_hint="star",
            source_item=SourceMilestone(level=3, id="t1", title="Task 1"),
        )
        assert point.id == "dp1"
        assert point.icon_hint == "star"
        assert point.source_item.level == 3

    def test_landmark_creation(self):
        """Test Landmark model creation."""
        landmark = Landmark(
            id="l1",
            name="Test Landmark",
            type="town",
            description="A small town",
            detail_points=[
                DetailPoint(id="dp1", name="Point 1"),
            ],
        )
        assert landmark.id == "l1"
        assert landmark.type == "town"
        assert len(landmark.detail_points) == 1

    def test_region_creation(self):
        """Test Region model creation."""
        region = Region(
            id="r1",
            name="Test Region",
            theme="forest",
            position_hint="north",
            description="A forest region",
            landmarks=[
                Landmark(id="l1", name="Landmark 1"),
            ],
        )
        assert region.id == "r1"
        assert region.theme == "forest"
        assert len(region.landmarks) == 1

    def test_map_path_creation(self):
        """Test MapPath model creation."""
        path = MapPath(
            id="p1",
            from_region="r1",
            to_region="r2",
            path_type="road",
            description="Main road",
        )
        assert path.id == "p1"
        assert path.from_region == "r1"
        assert path.to_region == "r2"

    def test_map_structure_creation(self):
        """Test MapStructure model creation."""
        structure = MapStructure(
            map_title="Test Map",
            map_description="A test map",
            total_regions=1,
            total_landmarks=0,
            regions=[Region(id="r1", name="Region 1")],
            paths=[],
            metadata=MapMetadata(complexity="simple"),
        )
        assert structure.map_title == "Test Map"
        assert structure.total_regions == 1
        assert structure.metadata.complexity == "simple"

    def test_parser_input_creation(self):
        """Test ParserInput model creation."""
        input_data = ParserInput(
            job_id=1,
            hierarchy={"L0": {"title": "Test"}},
            use_llm=False,
            fallback_to_simple=True,
        )
        assert input_data.job_id == 1
        assert input_data.use_llm is False

    def test_parser_output_creation(self):
        """Test ParserOutput model creation."""
        output = ParserOutput(
            success=True,
            valid=True,
            milestone_count=5,
            levels=[1, 2],
            milestones=[{"id": "m1", "title": "Test"}],
            parsing_mode="simple",
        )
        assert output.success is True
        assert output.milestone_count == 5
        assert output.parsing_mode == "simple"


# =============================================================================
# Legacy ParserAgent Tests
# =============================================================================


class TestLegacyParserAgent:
    """Tests for the legacy ParserAgent class."""

    @pytest.mark.asyncio
    async def test_valid_hierarchy(self, job_context):
        """Test ParserAgent with valid hierarchy."""
        agent = ParserAgent()
        result = await agent.execute(job_context)

        assert result.success is True
        assert result.data["valid"] is True
        assert result.data["milestone_count"] == 3  # L0 + 2 L1
        assert 1 in result.data["levels"]

    @pytest.mark.asyncio
    async def test_empty_hierarchy(self):
        """Test ParserAgent with empty hierarchy."""
        agent = ParserAgent()
        context = JobContext(
            job_id=1,
            user_id=1,
            document_url="http://example.com/doc",
            hierarchy={},
            theme={"theme_id": "smb3"},
            options={},
        )

        result = await agent.execute(context)

        assert result.success is False
        assert "No hierarchy data provided" in result.error

    @pytest.mark.asyncio
    async def test_hierarchy_without_l1(self):
        """Test ParserAgent with hierarchy missing L1."""
        agent = ParserAgent()
        context = JobContext(
            job_id=1,
            user_id=1,
            document_url="http://example.com/doc",
            hierarchy={"L0": {"title": "Test"}},
            theme={"theme_id": "smb3"},
            options={},
        )

        result = await agent.execute(context)

        assert result.success is False
        assert "At least 1 L1 milestone required" in result.error

    @pytest.mark.asyncio
    async def test_complex_hierarchy(self, complex_hierarchy):
        """Test ParserAgent with complex hierarchy."""
        agent = ParserAgent()
        context = JobContext(
            job_id=1,
            user_id=1,
            document_url="http://example.com/doc",
            hierarchy=complex_hierarchy,
            theme={"theme_id": "smb3"},
            options={},
        )

        result = await agent.execute(context)

        assert result.success is True
        assert result.data["valid"] is True
        # L0 (1) + L1 (3) + L2 (4) + L3 (3) + L4 (2) = 13
        assert result.data["milestone_count"] == 13
        assert 1 in result.data["levels"]
        assert 2 in result.data["levels"]
        assert 3 in result.data["levels"]
        assert 4 in result.data["levels"]

    @pytest.mark.asyncio
    async def test_too_many_milestones(self):
        """Test ParserAgent rejects too many milestones."""
        agent = ParserAgent()

        # Create hierarchy with 51 L1 milestones
        hierarchy = {
            "L0": {"title": "Test"},
            "L1": [{"id": f"m{i}", "title": f"Milestone {i}"} for i in range(51)],
        }

        context = JobContext(
            job_id=1,
            user_id=1,
            document_url="http://example.com/doc",
            hierarchy=hierarchy,
            theme={"theme_id": "smb3"},
            options={},
        )

        result = await agent.execute(context)

        assert result.success is False
        assert "Too many milestones" in result.error

    @pytest.mark.asyncio
    async def test_milestones_sorted_by_position(self, complex_hierarchy):
        """Test that milestones are sorted by position."""
        agent = ParserAgent()
        context = JobContext(
            job_id=1,
            user_id=1,
            document_url="http://example.com/doc",
            hierarchy=complex_hierarchy,
            theme={"theme_id": "smb3"},
            options={},
        )

        result = await agent.execute(context)

        milestones = result.data["milestones"]

        # Check that positions are in ascending order
        positions = [m["pos"] for m in milestones]
        assert positions == sorted(positions)


# =============================================================================
# Enhanced ParserAgent Tests
# =============================================================================


class TestEnhancedParserAgent:
    """Tests for the enhanced EnhancedParserAgent class."""

    @pytest.mark.asyncio
    async def test_simple_parsing_mode(self, agent_request):
        """Test EnhancedParserAgent in simple parsing mode."""
        agent = EnhancedParserAgent()

        response = await agent.run(agent_request)

        assert response.success is True
        output = response.output_data
        assert output["valid"] is True
        assert output["milestone_count"] == 3
        assert output["parsing_mode"] == "simple"

    @pytest.mark.asyncio
    async def test_validation_failure(self):
        """Test EnhancedParserAgent with invalid hierarchy."""
        agent = EnhancedParserAgent()

        request = AgentRequest(
            source_agent="test",
            job_id=1,
            input_data={
                "job_id": 1,
                "hierarchy": {},
                "use_llm": False,
            },
            context={},
        )

        response = await agent.run(request)

        # The AgentResponse.success reflects overall processing success
        # The output_data contains the actual result with valid=False for invalid hierarchy
        output = response.output_data
        assert output.get("valid") is False or output.get("success") is False
        assert "No hierarchy data provided" in (
            output.get("error_message", "") or output.get("error", "")
        )

    @pytest.mark.asyncio
    async def test_llm_mode_with_mock(self, simple_hierarchy, mock_llm_response):
        """Test EnhancedParserAgent in LLM mode with mocked response."""
        agent = EnhancedParserAgent()

        # Mock the LLM call
        with patch.object(
            agent, "call_llm_with_system", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = mock_llm_response

            request = AgentRequest(
                source_agent="test",
                job_id=1,
                input_data={
                    "job_id": 1,
                    "hierarchy": simple_hierarchy,
                    "use_llm": True,
                    "fallback_to_simple": False,
                },
                context={},
            )

            response = await agent.run(request)

            assert response.success is True
            output = response.output_data
            assert output.get("parsing_mode") == "llm"
            assert "map_structure" in output or output.get("valid") is True

    @pytest.mark.asyncio
    async def test_llm_fallback_on_error(self, simple_hierarchy):
        """Test EnhancedParserAgent falls back to simple mode on LLM error."""
        agent = EnhancedParserAgent()

        # Mock the LLM call to raise an error
        with patch.object(
            agent, "call_llm_with_system", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.side_effect = RuntimeError("LLM unavailable")

            request = AgentRequest(
                source_agent="test",
                job_id=1,
                input_data={
                    "job_id": 1,
                    "hierarchy": simple_hierarchy,
                    "use_llm": True,
                    "fallback_to_simple": True,
                },
                context={},
            )

            response = await agent.run(request)

            # Should succeed with fallback
            assert response.success is True
            output = response.output_data
            assert output.get("parsing_mode") == "simple_fallback"

    @pytest.mark.asyncio
    async def test_progress_reporting(self, agent_request):
        """Test that progress is reported during processing."""
        agent = EnhancedParserAgent()
        progress_updates = []

        def on_progress(update):
            progress_updates.append(update)

        response = await agent.run(agent_request, on_progress=on_progress)

        assert response.success is True
        assert len(progress_updates) >= 1

        # Check that progress percentages are reasonable
        for update in progress_updates:
            assert 0 <= update.progress_pct <= 100

    @pytest.mark.asyncio
    async def test_metrics_collection(self, agent_request):
        """Test that metrics are collected during execution."""
        agent = EnhancedParserAgent()

        await agent.run(agent_request)

        metrics = agent.get_metrics()
        assert metrics["execution_time_ms"] >= 0
        assert metrics["start_time"] is not None


class TestEnhancedParserAgentHelpers:
    """Tests for EnhancedParserAgent helper methods."""

    def test_validate_hierarchy_empty(self):
        """Test hierarchy validation with empty input."""
        agent = EnhancedParserAgent()

        result = agent._validate_hierarchy({})
        assert result["valid"] is False
        assert "No hierarchy data" in result["error"]

    def test_validate_hierarchy_no_l0_or_l1(self):
        """Test hierarchy validation without L0 or L1."""
        agent = EnhancedParserAgent()

        result = agent._validate_hierarchy({"L2": []})
        assert result["valid"] is False

    def test_validate_hierarchy_empty_l1(self):
        """Test hierarchy validation with empty L1 list."""
        agent = EnhancedParserAgent()

        result = agent._validate_hierarchy({"L1": []})
        assert result["valid"] is False
        assert "empty" in result["error"].lower()

    def test_validate_hierarchy_valid(self):
        """Test hierarchy validation with valid input."""
        agent = EnhancedParserAgent()

        result = agent._validate_hierarchy({
            "L0": {"title": "Test"},
            "L1": [{"id": "m1", "title": "Milestone 1"}],
        })
        assert result["valid"] is True

    def test_simple_parse_l0_only(self):
        """Test simple parsing with only L0."""
        agent = EnhancedParserAgent()

        result = agent._simple_parse({"L0": {"title": "Test Project", "id": "root"}})

        assert result["milestone_count"] == 1
        assert len(result["milestones"]) == 1
        assert result["milestones"][0]["level"] == 0

    def test_simple_parse_all_levels(self, complex_hierarchy):
        """Test simple parsing with all levels."""
        agent = EnhancedParserAgent()

        result = agent._simple_parse(complex_hierarchy)

        assert result["milestone_count"] == 13
        assert 1 in result["levels"]
        assert 2 in result["levels"]
        assert 3 in result["levels"]
        assert 4 in result["levels"]

        # Check statistics
        assert result["statistics"]["total"] == 13
        assert result["statistics"]["by_level"][1] == 3
        assert result["statistics"]["by_level"][2] == 4
        assert result["statistics"]["by_level"][3] == 3
        assert result["statistics"]["by_level"][4] == 2

    def test_extract_json_from_code_block(self):
        """Test JSON extraction from markdown code blocks."""
        agent = EnhancedParserAgent()

        text = '''Here is the response:
```json
{"key": "value"}
```
Additional text.'''

        result = agent._extract_json(text)
        assert result == '{"key": "value"}'

    def test_extract_json_raw(self):
        """Test JSON extraction from raw JSON."""
        agent = EnhancedParserAgent()

        text = 'Some text {"key": "value"} more text'
        result = agent._extract_json(text)
        assert result == '{"key": "value"}'

    def test_extract_json_nested(self):
        """Test JSON extraction with nested objects."""
        agent = EnhancedParserAgent()

        text = '{"outer": {"inner": "value"}, "array": [1, 2, 3]}'
        result = agent._extract_json(text)
        data = json.loads(result)
        assert data["outer"]["inner"] == "value"


# =============================================================================
# Integration Tests
# =============================================================================


class TestParserAgentIntegration:
    """Integration tests for Parser Agent."""

    @pytest.mark.asyncio
    async def test_legacy_and_enhanced_consistency(self, complex_hierarchy):
        """Test that legacy and enhanced agents produce consistent results."""
        legacy_agent = ParserAgent()
        enhanced_agent = EnhancedParserAgent()

        # Legacy execution
        legacy_context = JobContext(
            job_id=1,
            user_id=1,
            document_url="http://example.com/doc",
            hierarchy=complex_hierarchy,
            theme={"theme_id": "smb3"},
            options={},
        )
        legacy_result = await legacy_agent.execute(legacy_context)

        # Enhanced execution (simple mode)
        enhanced_request = AgentRequest(
            source_agent="test",
            job_id=1,
            input_data={
                "job_id": 1,
                "hierarchy": complex_hierarchy,
                "use_llm": False,
            },
            context={},
        )
        enhanced_response = await enhanced_agent.run(enhanced_request)

        # Compare results
        assert legacy_result.success == enhanced_response.success
        assert legacy_result.data["milestone_count"] == enhanced_response.output_data["milestone_count"]
        assert legacy_result.data["levels"] == enhanced_response.output_data["levels"]

    @pytest.mark.asyncio
    async def test_full_workflow_simulation(self, complex_hierarchy, mock_llm_response):
        """Test full workflow from hierarchy to map structure."""
        agent = EnhancedParserAgent()

        # Mock LLM for predictable output
        with patch.object(
            agent, "call_llm_with_system", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = mock_llm_response

            request = AgentRequest(
                source_agent="pipeline",
                job_id=123,
                input_data={
                    "job_id": 123,
                    "hierarchy": complex_hierarchy,
                    "use_llm": True,
                },
                context={},
            )

            response = await agent.run(request)

            assert response.success is True
            assert response.job_id == 123

            # Verify the output can be used by downstream agents
            output = response.output_data
            assert "milestone_count" in output
            assert "milestones" in output or "map_structure" in output
