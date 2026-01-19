"""Tests for multi-agent pipeline."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.parser_agent import ParserAgent
from app.agents.artist_agent import ArtistAgent
from app.agents.road_agent import RoadAgent
from app.agents.icon_agent import IconAgent
from app.agents.coordinator_agent import CoordinatorAgent
from app.agents.base_agent import AgentResult, JobContext


@pytest.mark.asyncio
async def test_base_agent_execute_interface():
    """Test BaseAgent execute interface."""
    from app.agents.base_agent import BaseAgent

    class MockAgent(BaseAgent):
        async def execute(self, context: JobContext) -> AgentResult:
            return AgentResult(
                success=True,
                data={"test": "data"},
            )

    agent = MockAgent()
    context = JobContext(
        job_id=1,
        user_id=1,
        document_url="http://example.com/doc",
        hierarchy={"L0": {"title": "Test"}},
        theme={"theme_id": "smb3"},
        options={},
    )

    result = await agent.execute(context)
    assert result.success is True
    assert result.data == {"test": "data"}


@pytest.mark.asyncio
async def test_parser_agent_valid_hierarchy():
    """Test ParserAgent with valid hierarchy."""
    agent = ParserAgent()
    context = JobContext(
        job_id=1,
        user_id=1,
        document_url="http://example.com/doc",
        hierarchy={
            "L0": {"title": "Project", "id": "root"},
            "L1": [
                {"id": "m1", "title": "Milestone 1"},
                {"id": "m2", "title": "Milestone 2"},
            ],
        },
        theme={"theme_id": "smb3"},
        options={},
    )

    result = await agent.execute(context)

    assert result.success is True
    assert result.data["valid"] is True
    assert result.data["milestone_count"] == 3
    assert result.data["levels"] == [1]


@pytest.mark.asyncio
async def test_parser_agent_invalid_hierarchy():
    """Test ParserAgent with invalid hierarchy."""
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
async def test_artist_agent_theme_generation():
    """Test ArtistAgent theme generation."""
    agent = ArtistAgent()
    context = JobContext(
        job_id=1,
        user_id=1,
        document_url="http://example.com/doc",
        hierarchy={},
        theme={"theme_id": "smb3"},
        options={},
    )

    result = await agent.execute(context)

    assert result.success is True
    assert result.data["theme_id"] == "smb3"
    assert "colors" in result.data
    assert "textures" in result.data


@pytest.mark.asyncio
async def test_road_agent_spline_generation():
    """Test RoadAgent spline generation."""
    agent = RoadAgent()
    context = JobContext(
        job_id=1,
        user_id=1,
        document_url="http://example.com/doc",
        hierarchy={},
        theme={"theme_id": "smb3"},
        agent_state={
            "parser": {"milestone_count": 5},
        },
        options={},
    )

    result = await agent.execute(context)

    assert result.success is True
    assert "coordinates" in result.data
    assert len(result.data["coordinates"]) == 50
    assert "control_points" in result.data
    assert "arc_length" in result.data


@pytest.mark.asyncio
async def test_icon_agent_placement():
    """Test IconAgent milestone placement."""
    agent = IconAgent()
    context = JobContext(
        job_id=1,
        user_id=1,
        document_url="http://example.com/doc",
        hierarchy={},
        theme={"theme_id": "smb3"},
        agent_state={
            "parser": {"milestone_count": 5},
            "road": {"coordinates": [{"x": 100, "y": 200}, {"x": 150, "y": 220}]},
        },
        options={},
    )

    result = await agent.execute(context)

    assert result.success is True
    assert "icons" in result.data
    assert result.data["icon_count"] == 5


@pytest.mark.asyncio
async def test_coordinator_full_pipeline():
    """Test CoordinatorAgent full pipeline execution."""
    agent = CoordinatorAgent()
    context = JobContext(
        job_id=1,
        user_id=1,
        document_url="http://example.com/doc",
        hierarchy={
            "L0": {"title": "Project", "id": "root"},
            "L1": [
                {"id": "m1", "title": "Milestone 1"},
                {"id": "m2", "title": "Milestone 2"},
            ],
        },
        theme={"theme_id": "smb3"},
        options={},
    )

    result = await agent.execute(context)

    assert result.success is True
    assert "theme" in result.data
    assert "road" in result.data
    assert "milestones" in result.data
    assert "metadata" in result.data
