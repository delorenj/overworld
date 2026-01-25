"""Tests for STORY-005: ArtistAgent.

This module tests both the legacy ArtistAgent and the new EnhancedArtistAgent
for visual element generation and map styling.
"""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from app.agents.artist_agent import (
    ArtistAgent,
    ArtistInput,
    ArtistOutput,
    ColorPalette,
    DetailIconStyle,
    DetailIcons,
    EnhancedArtistAgent,
    IconStyle,
    LandmarkVisual,
    MapStyle,
    PathStyle,
    PathVisual,
    RegionPalette,
    RegionVisual,
    VisualMetadata,
    VisualSpecification,
)
from app.agents.base_agent import AgentResult, JobContext
from app.agents.messages import AgentRequest
from app.agents.prompts import ARTIST_THEME_PRESETS, get_theme_preset


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_map_structure():
    """Sample map structure from ParserAgent."""
    return {
        "map_title": "Test Project Map",
        "map_description": "A journey through the test project",
        "total_regions": 2,
        "total_landmarks": 2,
        "regions": [
            {
                "id": "r1",
                "name": "Planning Region",
                "theme": "forest",
                "position_hint": "start",
                "description": "The beginning of the journey",
                "landmarks": [
                    {
                        "id": "l1",
                        "name": "Requirements Town",
                        "type": "town",
                        "description": "Where requirements are gathered",
                    }
                ],
            },
            {
                "id": "r2",
                "name": "Development Region",
                "theme": "mountain",
                "position_hint": "end",
                "description": "The final destination",
                "landmarks": [
                    {
                        "id": "l2",
                        "name": "Code Fortress",
                        "type": "fortress",
                        "description": "Where code is built",
                    }
                ],
            },
        ],
        "paths": [
            {
                "id": "p1",
                "from_region": "r1",
                "to_region": "r2",
                "path_type": "road",
            }
        ],
    }


@pytest.fixture
def job_context():
    """Create a legacy JobContext for testing."""
    return JobContext(
        job_id=1,
        user_id=1,
        document_url="http://example.com/doc",
        hierarchy={},
        theme={"theme_id": "smb3"},
        options={},
    )


@pytest.fixture
def agent_request():
    """Create an AgentRequest for testing."""
    return AgentRequest(
        source_agent="test",
        job_id=1,
        input_data={
            "job_id": 1,
            "theme_id": "smb3",
            "use_llm": False,
        },
        context={},
    )


@pytest.fixture
def mock_llm_visual_response():
    """Mock LLM response with valid visual specification."""
    return json.dumps({
        "map_style": {
            "overall_palette": {
                "primary": "#6B8CFF",
                "secondary": "#D2691E",
                "background": "#87CEEB",
                "text": "#FFFFFF",
                "highlight": "#FFD700",
            },
            "pixel_density": "medium",
            "outline_style": "thin",
            "shadow_style": "pixel",
        },
        "regions": [
            {
                "region_id": "r1",
                "visual_description": "A lush forest region with tall trees",
                "palette": {
                    "primary": "#228B22",
                    "secondary": "#90EE90",
                    "accent": "#FFD700",
                    "ground": "#8B4513",
                },
                "texture_hint": "grass",
                "ambient_elements": ["trees", "flowers"],
                "mood": "peaceful",
            }
        ],
        "landmarks": [
            {
                "landmark_id": "l1",
                "visual_description": "A cozy town with wooden buildings",
                "icon_style": {
                    "base_shape": "circle",
                    "size": "medium",
                    "primary_color": "#8B4513",
                    "secondary_color": "#D2691E",
                    "animation_hint": "none",
                },
                "sprite_suggestion": "Small village with thatched roofs",
            }
        ],
        "paths": [
            {
                "path_id": "p1",
                "style": {
                    "color": "#D2691E",
                    "width": "medium",
                    "pattern": "cobblestone",
                    "border_color": "#8B4513",
                },
                "decoration_hint": "small stones",
            }
        ],
        "detail_icons": {
            "star": {"color": "#FFD700", "style": "golden sparkle"},
            "chest": {"color": "#8B4513", "style": "wooden treasure chest"},
            "flag": {"color": "#FF0000", "style": "triangular pennant"},
            "key": {"color": "#C0C0C0", "style": "silver skeleton key"},
            "scroll": {"color": "#F5DEB3", "style": "rolled parchment"},
            "gem": {"color": "#9400D3", "style": "faceted crystal"},
        },
        "metadata": {
            "style_coherence_score": 85,
            "retro_authenticity_score": 90,
            "visual_complexity": "moderate",
        },
    })


# =============================================================================
# Pydantic Model Tests
# =============================================================================


class TestPydanticModels:
    """Tests for Artist Agent Pydantic models."""

    def test_color_palette_creation(self):
        """Test ColorPalette model creation."""
        palette = ColorPalette(
            primary="#6B8CFF",
            secondary="#D2691E",
            background="#87CEEB",
            text="#FFFFFF",
            highlight="#FFD700",
        )
        assert palette.primary == "#6B8CFF"
        assert palette.highlight == "#FFD700"

    def test_color_palette_defaults(self):
        """Test ColorPalette default values."""
        palette = ColorPalette()
        assert palette.primary == "#6B8CFF"
        assert palette.secondary == "#D2691E"

    def test_region_palette_creation(self):
        """Test RegionPalette model creation."""
        palette = RegionPalette(
            primary="#228B22",
            secondary="#90EE90",
            accent="#FFD700",
            ground="#8B4513",
        )
        assert palette.primary == "#228B22"
        assert palette.ground == "#8B4513"

    def test_map_style_creation(self):
        """Test MapStyle model creation."""
        style = MapStyle(
            overall_palette=ColorPalette(),
            pixel_density="high",
            outline_style="thick",
            shadow_style="drop",
        )
        assert style.pixel_density == "high"
        assert style.outline_style == "thick"

    def test_region_visual_creation(self):
        """Test RegionVisual model creation."""
        visual = RegionVisual(
            region_id="r1",
            visual_description="A lush forest",
            palette=RegionPalette(),
            texture_hint="grass",
            ambient_elements=["trees", "flowers"],
            mood="peaceful",
        )
        assert visual.region_id == "r1"
        assert visual.mood == "peaceful"
        assert "trees" in visual.ambient_elements

    def test_icon_style_creation(self):
        """Test IconStyle model creation."""
        style = IconStyle(
            base_shape="diamond",
            size="large",
            primary_color="#FFD700",
            secondary_color="#FFA500",
            animation_hint="glow",
        )
        assert style.base_shape == "diamond"
        assert style.animation_hint == "glow"

    def test_landmark_visual_creation(self):
        """Test LandmarkVisual model creation."""
        visual = LandmarkVisual(
            landmark_id="l1",
            visual_description="A medieval castle",
            icon_style=IconStyle(),
            sprite_suggestion="Stone fortress with towers",
        )
        assert visual.landmark_id == "l1"
        assert "castle" in visual.visual_description.lower()

    def test_path_style_creation(self):
        """Test PathStyle model creation."""
        style = PathStyle(
            color="#D2691E",
            width="thick",
            pattern="cobblestone",
            border_color="#8B4513",
        )
        assert style.width == "thick"
        assert style.pattern == "cobblestone"

    def test_path_visual_creation(self):
        """Test PathVisual model creation."""
        visual = PathVisual(
            path_id="p1",
            style=PathStyle(),
            decoration_hint="signposts",
        )
        assert visual.path_id == "p1"
        assert visual.decoration_hint == "signposts"

    def test_detail_icons_creation(self):
        """Test DetailIcons model creation."""
        icons = DetailIcons()
        assert icons.star.color == "#FFD700"
        assert icons.chest.color == "#8B4513"

    def test_visual_metadata_creation(self):
        """Test VisualMetadata model creation."""
        metadata = VisualMetadata(
            style_coherence_score=90,
            retro_authenticity_score=85,
            visual_complexity="detailed",
        )
        assert metadata.style_coherence_score == 90
        assert metadata.visual_complexity == "detailed"

    def test_visual_metadata_validation(self):
        """Test VisualMetadata validation bounds."""
        # Valid scores
        metadata = VisualMetadata(style_coherence_score=0, retro_authenticity_score=100)
        assert metadata.style_coherence_score == 0

        # Invalid scores should raise
        with pytest.raises(ValueError):
            VisualMetadata(style_coherence_score=-1)

        with pytest.raises(ValueError):
            VisualMetadata(retro_authenticity_score=101)

    def test_visual_specification_creation(self):
        """Test VisualSpecification model creation."""
        spec = VisualSpecification(
            map_style=MapStyle(),
            regions=[RegionVisual(region_id="r1")],
            landmarks=[LandmarkVisual(landmark_id="l1")],
            paths=[PathVisual(path_id="p1")],
            detail_icons=DetailIcons(),
            metadata=VisualMetadata(),
        )
        assert len(spec.regions) == 1
        assert len(spec.landmarks) == 1
        assert spec.metadata.style_coherence_score == 80

    def test_artist_input_creation(self):
        """Test ArtistInput model creation."""
        input_data = ArtistInput(
            job_id=1,
            map_structure={"regions": []},
            theme_id="zelda",
            use_llm=True,
        )
        assert input_data.theme_id == "zelda"
        assert input_data.use_llm is True

    def test_artist_output_creation(self):
        """Test ArtistOutput model creation."""
        output = ArtistOutput(
            success=True,
            theme_id="smb3",
            colors={"primary": "#6B8CFF"},
            textures={"road": "pixelated"},
            icon_set="8bit-sprites",
            generation_mode="preset",
        )
        assert output.success is True
        assert output.theme_id == "smb3"


# =============================================================================
# Theme Preset Tests
# =============================================================================


class TestThemePresets:
    """Tests for theme presets."""

    def test_smb3_preset_exists(self):
        """Test that SMB3 preset exists and is complete."""
        preset = get_theme_preset("smb3")

        assert preset["name"] == "Super Mario Bros 3"
        assert "base_palette" in preset
        assert "world_themes" in preset

        # Check palette colors
        palette = preset["base_palette"]
        assert "primary" in palette
        assert "secondary" in palette
        assert "background" in palette

        # Check world themes
        themes = preset["world_themes"]
        assert "grass" in themes
        assert "desert" in themes
        assert "water" in themes

    def test_zelda_preset_exists(self):
        """Test that Zelda preset exists and is complete."""
        preset = get_theme_preset("zelda")

        assert preset["name"] == "Legend of Zelda"
        assert "forest" in preset["world_themes"]
        assert "mountain" in preset["world_themes"]

    def test_ff_preset_exists(self):
        """Test that Final Fantasy preset exists and is complete."""
        preset = get_theme_preset("ff")

        assert preset["name"] == "Final Fantasy"
        assert "plains" in preset["world_themes"]
        assert "ocean" in preset["world_themes"]

    def test_unknown_preset_fallback(self):
        """Test that unknown preset falls back to SMB3."""
        preset = get_theme_preset("unknown_theme")

        assert preset["name"] == "Super Mario Bros 3"

    def test_all_presets_have_required_fields(self):
        """Test that all presets have required fields."""
        for theme_id in ARTIST_THEME_PRESETS:
            preset = ARTIST_THEME_PRESETS[theme_id]

            assert "name" in preset
            assert "description" in preset
            assert "base_palette" in preset
            assert "world_themes" in preset

            # Check palette has all required colors
            palette = preset["base_palette"]
            assert "primary" in palette
            assert "secondary" in palette
            assert "background" in palette
            assert "text" in palette
            assert "highlight" in palette


# =============================================================================
# Legacy ArtistAgent Tests
# =============================================================================


class TestLegacyArtistAgent:
    """Tests for the legacy ArtistAgent class."""

    @pytest.mark.asyncio
    async def test_smb3_theme(self, job_context):
        """Test ArtistAgent with SMB3 theme."""
        agent = ArtistAgent()
        result = await agent.execute(job_context)

        assert result.success is True
        assert result.data["theme_id"] == "smb3"
        assert "colors" in result.data
        assert "textures" in result.data

    @pytest.mark.asyncio
    async def test_zelda_theme(self):
        """Test ArtistAgent with Zelda theme."""
        agent = ArtistAgent()
        context = JobContext(
            job_id=1,
            user_id=1,
            document_url="http://example.com/doc",
            hierarchy={},
            theme={"theme_id": "zelda"},
            options={},
        )

        result = await agent.execute(context)

        assert result.success is True
        assert result.data["theme_id"] == "zelda"

    @pytest.mark.asyncio
    async def test_ff_theme(self):
        """Test ArtistAgent with Final Fantasy theme."""
        agent = ArtistAgent()
        context = JobContext(
            job_id=1,
            user_id=1,
            document_url="http://example.com/doc",
            hierarchy={},
            theme={"theme_id": "ff"},
            options={},
        )

        result = await agent.execute(context)

        assert result.success is True
        assert result.data["theme_id"] == "ff"

    @pytest.mark.asyncio
    async def test_unsupported_theme(self):
        """Test ArtistAgent with unsupported theme."""
        agent = ArtistAgent()
        context = JobContext(
            job_id=1,
            user_id=1,
            document_url="http://example.com/doc",
            hierarchy={},
            theme={"theme_id": "unsupported_theme"},
            options={},
        )

        result = await agent.execute(context)

        assert result.success is False
        assert "not supported" in result.error

    @pytest.mark.asyncio
    async def test_default_theme(self):
        """Test ArtistAgent with no theme specified."""
        agent = ArtistAgent()
        context = JobContext(
            job_id=1,
            user_id=1,
            document_url="http://example.com/doc",
            hierarchy={},
            theme={},  # No theme_id
            options={},
        )

        result = await agent.execute(context)

        assert result.success is True
        assert result.data["theme_id"] == "smb3"

    @pytest.mark.asyncio
    async def test_backward_compatible_colors(self, job_context):
        """Test that legacy color keys are present."""
        agent = ArtistAgent()
        result = await agent.execute(job_context)

        assert result.success is True
        colors = result.data["colors"]

        # Check legacy color keys
        assert "road" in colors
        assert "bg" in colors
        assert "milestone" in colors


# =============================================================================
# Enhanced ArtistAgent Tests
# =============================================================================


class TestEnhancedArtistAgent:
    """Tests for the enhanced EnhancedArtistAgent class."""

    @pytest.mark.asyncio
    async def test_preset_mode(self, agent_request):
        """Test EnhancedArtistAgent in preset mode."""
        agent = EnhancedArtistAgent()

        response = await agent.run(agent_request)

        assert response.success is True
        output = response.output_data
        assert output["theme_id"] == "smb3"
        assert output["generation_mode"] == "preset"

    @pytest.mark.asyncio
    async def test_unknown_theme_fallback(self):
        """Test EnhancedArtistAgent falls back to SMB3 for unknown theme."""
        agent = EnhancedArtistAgent()

        request = AgentRequest(
            source_agent="test",
            job_id=1,
            input_data={
                "job_id": 1,
                "theme_id": "unknown_theme",
                "use_llm": False,
            },
            context={},
        )

        response = await agent.run(request)

        assert response.success is True
        # Should fall back to smb3
        output = response.output_data
        assert output["theme_id"] == "smb3"

    @pytest.mark.asyncio
    async def test_llm_mode_with_mock(
        self, sample_map_structure, mock_llm_visual_response
    ):
        """Test EnhancedArtistAgent in LLM mode with mocked response."""
        agent = EnhancedArtistAgent()

        with patch.object(
            agent, "call_llm_with_system", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = mock_llm_visual_response

            request = AgentRequest(
                source_agent="test",
                job_id=1,
                input_data={
                    "job_id": 1,
                    "map_structure": sample_map_structure,
                    "theme_id": "smb3",
                    "use_llm": True,
                    "fallback_to_preset": False,
                },
                context={},
            )

            response = await agent.run(request)

            assert response.success is True
            output = response.output_data
            assert output.get("generation_mode") == "llm"

    @pytest.mark.asyncio
    async def test_llm_mode_without_map_structure(self):
        """Test EnhancedArtistAgent in LLM mode but without map structure."""
        agent = EnhancedArtistAgent()

        request = AgentRequest(
            source_agent="test",
            job_id=1,
            input_data={
                "job_id": 1,
                "map_structure": None,  # No map structure
                "theme_id": "smb3",
                "use_llm": True,
            },
            context={},
        )

        response = await agent.run(request)

        # Should fall back to preset mode
        assert response.success is True
        output = response.output_data
        assert output["generation_mode"] == "preset"

    @pytest.mark.asyncio
    async def test_llm_fallback_on_error(self, sample_map_structure):
        """Test EnhancedArtistAgent falls back to preset on LLM error."""
        agent = EnhancedArtistAgent()

        with patch.object(
            agent, "call_llm_with_system", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.side_effect = RuntimeError("LLM unavailable")

            request = AgentRequest(
                source_agent="test",
                job_id=1,
                input_data={
                    "job_id": 1,
                    "map_structure": sample_map_structure,
                    "theme_id": "smb3",
                    "use_llm": True,
                    "fallback_to_preset": True,
                },
                context={},
            )

            response = await agent.run(request)

            assert response.success is True
            output = response.output_data
            assert output.get("generation_mode") == "preset_fallback"

    @pytest.mark.asyncio
    async def test_progress_reporting(self, agent_request):
        """Test that progress is reported during processing."""
        agent = EnhancedArtistAgent()
        progress_updates = []

        def on_progress(update):
            progress_updates.append(update)

        response = await agent.run(agent_request, on_progress=on_progress)

        assert response.success is True
        assert len(progress_updates) >= 1

    @pytest.mark.asyncio
    async def test_metrics_collection(self, agent_request):
        """Test that metrics are collected during execution."""
        agent = EnhancedArtistAgent()

        await agent.run(agent_request)

        metrics = agent.get_metrics()
        assert metrics["execution_time_ms"] >= 0


class TestEnhancedArtistAgentHelpers:
    """Tests for EnhancedArtistAgent helper methods."""

    def test_create_preset_output(self):
        """Test preset output creation."""
        agent = EnhancedArtistAgent()
        preset = get_theme_preset("smb3")

        output = agent._create_preset_output("smb3", preset)

        assert output.success is True
        assert output.theme_id == "smb3"
        assert output.generation_mode == "preset"
        assert "primary" in output.colors

    def test_extract_json_from_code_block(self):
        """Test JSON extraction from markdown code blocks."""
        agent = EnhancedArtistAgent()

        text = '''Here is the visual specification:
```json
{"map_style": {"pixel_density": "high"}}
```
'''

        result = agent._extract_json(text)
        data = json.loads(result)
        assert data["map_style"]["pixel_density"] == "high"

    def test_get_ambient_elements(self):
        """Test ambient element generation for different themes."""
        agent = EnhancedArtistAgent()

        grass_elements = agent._get_ambient_elements("grass")
        assert "trees" in grass_elements

        desert_elements = agent._get_ambient_elements("desert")
        assert "cacti" in desert_elements

        castle_elements = agent._get_ambient_elements("castle")
        assert "flags" in castle_elements

        # Unknown theme should have defaults
        unknown_elements = agent._get_ambient_elements("unknown")
        assert len(unknown_elements) > 0

    def test_get_mood_for_theme(self):
        """Test mood generation for different themes."""
        agent = EnhancedArtistAgent()

        assert agent._get_mood_for_theme("grass") == "peaceful"
        assert agent._get_mood_for_theme("forest") == "mysterious"
        assert agent._get_mood_for_theme("volcano") == "dangerous"
        assert agent._get_mood_for_theme("unknown") == "neutral"

    def test_generate_region_visuals_from_preset(self):
        """Test region visual generation from presets."""
        agent = EnhancedArtistAgent()

        regions = [
            {"id": "r1", "theme": "grass"},
            {"id": "r2", "theme": "desert"},
        ]

        visuals = agent.generate_region_visuals_from_preset(regions, "smb3")

        assert len(visuals) == 2
        assert visuals[0].region_id == "r1"
        assert visuals[0].texture_hint == "grass"
        assert visuals[0].mood == "peaceful"

        assert visuals[1].region_id == "r2"
        assert visuals[1].texture_hint == "desert"


# =============================================================================
# Integration Tests
# =============================================================================


class TestArtistAgentIntegration:
    """Integration tests for Artist Agent."""

    @pytest.mark.asyncio
    async def test_legacy_and_enhanced_consistency(self):
        """Test that legacy and enhanced agents produce consistent results."""
        legacy_agent = ArtistAgent()
        enhanced_agent = EnhancedArtistAgent()

        # Legacy execution
        legacy_context = JobContext(
            job_id=1,
            user_id=1,
            document_url="http://example.com/doc",
            hierarchy={},
            theme={"theme_id": "smb3"},
            options={},
        )
        legacy_result = await legacy_agent.execute(legacy_context)

        # Enhanced execution (preset mode)
        enhanced_request = AgentRequest(
            source_agent="test",
            job_id=1,
            input_data={
                "job_id": 1,
                "theme_id": "smb3",
                "use_llm": False,
            },
            context={},
        )
        enhanced_response = await enhanced_agent.run(enhanced_request)

        # Compare results
        assert legacy_result.success == enhanced_response.success
        assert legacy_result.data["theme_id"] == enhanced_response.output_data["theme_id"]

    @pytest.mark.asyncio
    async def test_full_workflow_with_parser_output(
        self, sample_map_structure, mock_llm_visual_response
    ):
        """Test full workflow using parser output."""
        agent = EnhancedArtistAgent()

        with patch.object(
            agent, "call_llm_with_system", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = mock_llm_visual_response

            request = AgentRequest(
                source_agent="parser",
                job_id=123,
                input_data={
                    "job_id": 123,
                    "map_structure": sample_map_structure,
                    "theme_id": "smb3",
                    "use_llm": True,
                },
                context={
                    "parser": {
                        "valid": True,
                        "milestone_count": 5,
                    }
                },
            )

            response = await agent.run(request)

            assert response.success is True
            assert response.job_id == 123

    @pytest.mark.asyncio
    async def test_all_themes_work(self):
        """Test that all theme presets work correctly."""
        agent = EnhancedArtistAgent()

        for theme_id in ARTIST_THEME_PRESETS:
            request = AgentRequest(
                source_agent="test",
                job_id=1,
                input_data={
                    "job_id": 1,
                    "theme_id": theme_id,
                    "use_llm": False,
                },
                context={},
            )

            response = await agent.run(request)

            assert response.success is True, f"Theme {theme_id} failed"
            assert response.output_data["theme_id"] == theme_id
