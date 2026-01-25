"""Artist Agent for visual element generation and styling.

This module implements the ArtistAgent which generates visual descriptions,
color palettes, and styling specifications for 8/16-bit style adventure maps.

STORY-005: Parser & Artist Agents

The ArtistAgent supports two modes of operation:
1. Simple mode (legacy): Returns preset theme configurations
2. LLM-enhanced mode: Generates custom visual specifications using AI
"""

import json
import logging
import re
from typing import Any, ClassVar, Optional

from pydantic import BaseModel, Field

from app.agents.base import (
    AgentCapability,
    AgentConfig,
    AgentInput,
    AgentOutput,
    BaseAgent,
    ExecutionContext,
)
from app.agents.base_agent import AgentResult, JobContext
from app.agents.base_agent import BaseAgent as LegacyBaseAgent
from app.agents.prompts import (
    ARTIST_THEME_PRESETS,
    format_artist_fallback_prompt,
    format_artist_prompt,
    get_theme_preset,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic Models for Artist Agent
# =============================================================================


class ColorPalette(BaseModel):
    """A color palette with named colors."""

    primary: str = Field(default="#6B8CFF", description="Primary color (hex)")
    secondary: str = Field(default="#D2691E", description="Secondary color (hex)")
    background: str = Field(default="#87CEEB", description="Background color (hex)")
    text: str = Field(default="#FFFFFF", description="Text color (hex)")
    highlight: str = Field(default="#FFD700", description="Highlight color (hex)")


class RegionPalette(BaseModel):
    """Color palette for a specific region."""

    primary: str = Field(default="#228B22", description="Primary region color")
    secondary: str = Field(default="#90EE90", description="Secondary region color")
    accent: str = Field(default="#FFD700", description="Accent color")
    ground: str = Field(default="#8B4513", description="Ground/terrain color")


class MapStyle(BaseModel):
    """Overall map styling configuration."""

    overall_palette: ColorPalette = Field(
        default_factory=ColorPalette, description="Main color palette"
    )
    pixel_density: str = Field(default="medium", description="Pixel density level")
    outline_style: str = Field(default="thin", description="Outline style")
    shadow_style: str = Field(default="pixel", description="Shadow style")


class RegionVisual(BaseModel):
    """Visual specification for a region."""

    region_id: str = Field(..., description="Region ID reference")
    visual_description: str = Field(default="", description="Visual description")
    palette: RegionPalette = Field(
        default_factory=RegionPalette, description="Region colors"
    )
    texture_hint: str = Field(default="grass", description="Texture suggestion")
    ambient_elements: list[str] = Field(
        default_factory=list, description="Decorative elements"
    )
    mood: str = Field(default="peaceful", description="Visual mood")


class IconStyle(BaseModel):
    """Style specification for an icon/landmark."""

    base_shape: str = Field(default="circle", description="Base shape")
    size: str = Field(default="medium", description="Icon size")
    primary_color: str = Field(default="#FFD700", description="Primary color")
    secondary_color: str = Field(default="#FFA500", description="Secondary color")
    animation_hint: str = Field(default="none", description="Animation suggestion")


class LandmarkVisual(BaseModel):
    """Visual specification for a landmark."""

    landmark_id: str = Field(..., description="Landmark ID reference")
    visual_description: str = Field(default="", description="Visual description")
    icon_style: IconStyle = Field(default_factory=IconStyle, description="Icon styling")
    sprite_suggestion: str = Field(default="", description="Sprite description")


class PathStyle(BaseModel):
    """Style specification for a path."""

    color: str = Field(default="#D2691E", description="Path color")
    width: str = Field(default="medium", description="Path width")
    pattern: str = Field(default="solid", description="Path pattern")
    border_color: Optional[str] = Field(default=None, description="Border color")


class PathVisual(BaseModel):
    """Visual specification for a path."""

    path_id: str = Field(..., description="Path ID reference")
    style: PathStyle = Field(default_factory=PathStyle, description="Path styling")
    decoration_hint: str = Field(default="", description="Decoration suggestion")


class DetailIconStyle(BaseModel):
    """Style for a detail icon type."""

    color: str = Field(default="#FFD700", description="Icon color")
    style: str = Field(default="pixelated 8-bit style", description="Style description")


class DetailIcons(BaseModel):
    """Collection of detail icon styles."""

    star: DetailIconStyle = Field(
        default_factory=lambda: DetailIconStyle(color="#FFD700", style="golden sparkle")
    )
    chest: DetailIconStyle = Field(
        default_factory=lambda: DetailIconStyle(color="#8B4513", style="wooden treasure chest")
    )
    flag: DetailIconStyle = Field(
        default_factory=lambda: DetailIconStyle(color="#FF0000", style="triangular pennant")
    )
    key: DetailIconStyle = Field(
        default_factory=lambda: DetailIconStyle(color="#C0C0C0", style="silver skeleton key")
    )
    scroll: DetailIconStyle = Field(
        default_factory=lambda: DetailIconStyle(color="#F5DEB3", style="rolled parchment")
    )
    gem: DetailIconStyle = Field(
        default_factory=lambda: DetailIconStyle(color="#9400D3", style="faceted crystal")
    )


class VisualMetadata(BaseModel):
    """Metadata about the visual generation."""

    style_coherence_score: int = Field(
        default=80, ge=0, le=100, description="Style coherence score"
    )
    retro_authenticity_score: int = Field(
        default=85, ge=0, le=100, description="Retro authenticity score"
    )
    visual_complexity: str = Field(default="moderate", description="Visual complexity")


class VisualSpecification(BaseModel):
    """Complete visual specification for a map."""

    map_style: MapStyle = Field(default_factory=MapStyle, description="Overall style")
    regions: list[RegionVisual] = Field(
        default_factory=list, description="Region visuals"
    )
    landmarks: list[LandmarkVisual] = Field(
        default_factory=list, description="Landmark visuals"
    )
    paths: list[PathVisual] = Field(default_factory=list, description="Path visuals")
    detail_icons: DetailIcons = Field(
        default_factory=DetailIcons, description="Detail icon styles"
    )
    metadata: VisualMetadata = Field(
        default_factory=VisualMetadata, description="Generation metadata"
    )


class ArtistInput(AgentInput):
    """Input data for ArtistAgent."""

    map_structure: Optional[dict[str, Any]] = Field(
        default=None, description="Parsed map structure from ParserAgent"
    )
    theme_id: str = Field(default="smb3", description="Theme preset identifier")
    use_llm: bool = Field(default=False, description="Use LLM for custom visuals")
    fallback_to_preset: bool = Field(
        default=True, description="Fallback to preset on LLM failure"
    )


class ArtistOutput(AgentOutput):
    """Output data from ArtistAgent."""

    theme_id: str = Field(default="smb3", description="Theme used")
    colors: dict[str, str] = Field(default_factory=dict, description="Color palette")
    textures: dict[str, str] = Field(default_factory=dict, description="Texture hints")
    icon_set: str = Field(default="8bit-sprites", description="Icon set identifier")
    visual_specification: Optional[VisualSpecification] = Field(
        default=None, description="Full visual specification (LLM mode)"
    )
    generation_mode: str = Field(
        default="preset", description="Mode used: preset or llm"
    )


# =============================================================================
# Enhanced Artist Agent (New Framework)
# =============================================================================


class EnhancedArtistAgent(BaseAgent[ArtistInput, ArtistOutput]):
    """Enhanced Artist Agent using the new BaseAgent framework.

    This agent generates visual specifications for maps including:
    - Color palettes for regions and landmarks
    - Icon styles and animations
    - Path styling
    - 8/16-bit aesthetic descriptions

    Features:
    - Typed input/output with Pydantic validation
    - LLM integration for custom visual generation
    - Theme presets for consistent styling
    - Fallback strategies for error recovery
    """

    input_type: ClassVar[type[BaseModel]] = ArtistInput
    output_type: ClassVar[type[BaseModel]] = ArtistOutput
    default_config: ClassVar[AgentConfig] = AgentConfig(
        name="ArtistAgent",
        version="2.0.0",
        default_model="claude-3-5-sonnet",
        temperature=0.7,  # Higher temperature for creative output
        timeout_seconds=90,
        max_retries=3,
        capabilities=[AgentCapability.LLM_CALLS, AgentCapability.CHECKPOINTING],
    )

    async def process(
        self, input_data: ArtistInput, ctx: ExecutionContext
    ) -> ArtistOutput:
        """Generate visual specifications for the map.

        Args:
            input_data: Artist input with map structure and theme
            ctx: Execution context

        Returns:
            Artist output with visual specifications
        """
        theme_id = input_data.theme_id
        map_structure = input_data.map_structure

        # Report progress
        ctx.report_progress(
            agent_name=self.name,
            progress_pct=10.0,
            stage="generating",
            message=f"Loading theme preset: {theme_id}",
        )

        # Validate theme
        if theme_id not in ARTIST_THEME_PRESETS:
            logger.warning(f"Unknown theme '{theme_id}', falling back to 'smb3'")
            theme_id = "smb3"

        # Get base preset
        preset = get_theme_preset(theme_id)

        if not input_data.use_llm or not map_structure:
            # Return preset-based configuration
            ctx.report_progress(
                agent_name=self.name,
                progress_pct=100.0,
                stage="generating",
                message="Preset theme applied",
            )

            return self._create_preset_output(theme_id, preset)

        # LLM-enhanced visual generation
        ctx.report_progress(
            agent_name=self.name,
            progress_pct=30.0,
            stage="generating",
            message="Generating custom visuals with LLM",
        )

        try:
            visual_spec = await self._llm_generate(map_structure, theme_id, ctx)

            ctx.report_progress(
                agent_name=self.name,
                progress_pct=100.0,
                stage="generating",
                message="Custom visual generation complete",
            )

            return ArtistOutput(
                success=True,
                data={
                    "theme_id": theme_id,
                    "visual_specification": visual_spec.model_dump(),
                },
                theme_id=theme_id,
                colors=visual_spec.map_style.overall_palette.model_dump(),
                textures={"default": "pixelated"},
                icon_set="8bit-sprites",
                visual_specification=visual_spec,
                generation_mode="llm",
            )

        except Exception as e:
            logger.warning(f"LLM visual generation failed: {e}")

            if input_data.fallback_to_preset:
                ctx.report_progress(
                    agent_name=self.name,
                    progress_pct=100.0,
                    stage="generating",
                    message="Falling back to preset theme",
                )

                output = self._create_preset_output(theme_id, preset)
                output.generation_mode = "preset_fallback"
                return output

            return ArtistOutput(
                success=False,
                error_message=f"Visual generation failed: {str(e)}",
                theme_id=theme_id,
            )

    def _create_preset_output(
        self, theme_id: str, preset: dict[str, Any]
    ) -> ArtistOutput:
        """Create output from a theme preset.

        Args:
            theme_id: Theme identifier
            preset: Theme preset data

        Returns:
            ArtistOutput with preset configuration
        """
        base_palette = preset.get("base_palette", {})

        return ArtistOutput(
            success=True,
            data={
                "theme_id": theme_id,
                "colors": base_palette,
                "textures": {
                    "road": "pixelated-brown",
                    "milestone": "numbered-circle",
                },
                "icon_set": "8bit-sprites",
            },
            theme_id=theme_id,
            colors=base_palette,
            textures={
                "road": "pixelated-brown",
                "milestone": "numbered-circle",
            },
            icon_set="8bit-sprites",
            generation_mode="preset",
        )

    async def _llm_generate(
        self,
        map_structure: dict[str, Any],
        theme_id: str,
        ctx: ExecutionContext,
    ) -> VisualSpecification:
        """Use LLM to generate custom visual specifications.

        Args:
            map_structure: Parsed map structure
            theme_id: Theme identifier
            ctx: Execution context

        Returns:
            Generated VisualSpecification

        Raises:
            ValueError: If LLM response cannot be parsed
        """
        system_prompt, user_prompt = format_artist_prompt(map_structure, theme_id)

        # Make LLM call
        response = await self.call_llm_with_system(
            system_prompt=system_prompt,
            user_message=user_prompt,
            temperature=0.7,
            ctx=ctx,
        )

        # Parse JSON response
        try:
            json_content = self._extract_json(response)
            data = json.loads(json_content)
            return VisualSpecification(**data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            # Try fallback prompt
            return await self._llm_generate_with_fallback(
                map_structure, theme_id, str(e), ctx
            )
        except Exception as e:
            logger.error(f"Failed to validate LLM response: {e}")
            raise ValueError(f"Invalid LLM response: {e}")

    async def _llm_generate_with_fallback(
        self,
        map_structure: dict[str, Any],
        theme_id: str,
        error: str,
        ctx: ExecutionContext,
    ) -> VisualSpecification:
        """Retry LLM generation with fallback prompt.

        Args:
            map_structure: Map structure data
            theme_id: Theme identifier
            error: Previous error message
            ctx: Execution context

        Returns:
            Generated VisualSpecification

        Raises:
            ValueError: If fallback also fails
        """
        system_prompt, user_prompt = format_artist_fallback_prompt(
            map_structure, theme_id, error
        )

        response = await self.call_llm_with_system(
            system_prompt=system_prompt,
            user_message=user_prompt,
            temperature=0.5,  # Lower for retry
            ctx=ctx,
        )

        try:
            json_content = self._extract_json(response)
            data = json.loads(json_content)
            return VisualSpecification(**data)
        except Exception as e:
            raise ValueError(f"Fallback generation also failed: {e}")

    def _extract_json(self, text: str) -> str:
        """Extract JSON from text that may contain markdown code blocks.

        Args:
            text: Raw text that may contain JSON

        Returns:
            Extracted JSON string
        """
        # Try to find JSON in code blocks
        code_block_pattern = r"```(?:json)?\s*([\s\S]*?)```"
        matches = re.findall(code_block_pattern, text)
        if matches:
            return matches[0].strip()

        # Try to find raw JSON object
        json_pattern = r"\{[\s\S]*\}"
        matches = re.findall(json_pattern, text)
        if matches:
            # Return the largest match (most likely the full response)
            return max(matches, key=len)

        # Return original text as last resort
        return text.strip()

    def generate_region_visuals_from_preset(
        self, regions: list[dict[str, Any]], theme_id: str
    ) -> list[RegionVisual]:
        """Generate region visuals from preset theme.

        Args:
            regions: List of region data from parser
            theme_id: Theme identifier

        Returns:
            List of RegionVisual objects
        """
        preset = get_theme_preset(theme_id)
        world_themes = preset.get("world_themes", {})

        visuals = []
        for region in regions:
            region_id = region.get("id", "unknown")
            theme = region.get("theme", "grass")

            # Get colors from world theme
            theme_colors = world_themes.get(theme, world_themes.get("grass", {}))

            visuals.append(
                RegionVisual(
                    region_id=region_id,
                    visual_description=f"A {theme} region with {preset['description']}",
                    palette=RegionPalette(
                        primary=theme_colors.get("ground", "#228B22"),
                        secondary=theme_colors.get("accent", "#90EE90"),
                        accent=preset["base_palette"].get("highlight", "#FFD700"),
                        ground=theme_colors.get("ground", "#8B4513"),
                    ),
                    texture_hint=theme,
                    ambient_elements=self._get_ambient_elements(theme),
                    mood=self._get_mood_for_theme(theme),
                )
            )

        return visuals

    def _get_ambient_elements(self, theme: str) -> list[str]:
        """Get ambient elements for a theme.

        Args:
            theme: Theme type

        Returns:
            List of ambient element names
        """
        elements = {
            "grass": ["trees", "flowers", "bushes"],
            "forest": ["trees", "mushrooms", "logs"],
            "desert": ["cacti", "rocks", "tumbleweeds"],
            "mountain": ["rocks", "snow", "pine_trees"],
            "water": ["waves", "fish", "coral"],
            "ice": ["icicles", "snowflakes", "crystals"],
            "castle": ["flags", "torches", "shields"],
            "cave": ["stalactites", "crystals", "bats"],
            "sky": ["clouds", "birds", "rainbows"],
            "volcano": ["lava", "smoke", "rocks"],
        }
        return elements.get(theme, ["grass", "rocks"])

    def _get_mood_for_theme(self, theme: str) -> str:
        """Get mood for a theme.

        Args:
            theme: Theme type

        Returns:
            Mood string
        """
        moods = {
            "grass": "peaceful",
            "forest": "mysterious",
            "desert": "harsh",
            "mountain": "majestic",
            "water": "serene",
            "ice": "cold",
            "castle": "imposing",
            "cave": "dark",
            "sky": "ethereal",
            "volcano": "dangerous",
        }
        return moods.get(theme, "neutral")


# =============================================================================
# Legacy Artist Agent (Backward Compatibility)
# =============================================================================


class ArtistAgent(LegacyBaseAgent):
    """Legacy Artist Agent for backward compatibility.

    This agent generates theme configuration for map rendering.
    It uses the legacy JobContext/AgentResult interface for compatibility
    with existing code.
    """

    def __init__(self):
        """Initialize the artist agent."""
        super().__init__()
        self._enhanced = EnhancedArtistAgent()

    async def execute(self, context: JobContext) -> AgentResult:
        """Generate theme configuration based on context.

        Args:
            context: Job context with theme preferences

        Returns:
            AgentResult with theme configuration
        """
        theme_preference = context.theme.get("theme_id", "smb3")

        try:
            # Validate theme - only smb3 supported in MVP
            if theme_preference not in ARTIST_THEME_PRESETS:
                return AgentResult(
                    success=False,
                    error=f"Theme '{theme_preference}' not supported. Available: {list(ARTIST_THEME_PRESETS.keys())}",
                )

            # Get preset
            preset = get_theme_preset(theme_preference)

            # Build theme config
            theme_config = {
                "theme_id": theme_preference,
                "colors": preset.get("base_palette", {}),
                "textures": {
                    "road": "pixelated-brown",
                    "milestone": "numbered-circle",
                },
                "icon_set": "8bit-sprites",
                "world_themes": preset.get("world_themes", {}),
            }

            # Add basic milestone colors for backward compatibility
            theme_config["colors"]["road"] = preset["base_palette"].get(
                "secondary", "#D2691E"
            )
            theme_config["colors"]["bg"] = preset["base_palette"].get(
                "background", "#6B8CFF"
            )
            theme_config["colors"]["milestone"] = preset["base_palette"].get(
                "highlight", "#FFD700"
            )

            return AgentResult(
                success=True,
                data=theme_config,
            )

        except Exception as e:
            return AgentResult(
                success=False,
                error=f"Artist failed: {str(e)}",
            )


# Export both versions
__all__ = [
    "ArtistAgent",
    "EnhancedArtistAgent",
    "ArtistInput",
    "ArtistOutput",
    "VisualSpecification",
    "MapStyle",
    "RegionVisual",
    "LandmarkVisual",
    "PathVisual",
    "ColorPalette",
    "IconStyle",
    "DetailIcons",
]
