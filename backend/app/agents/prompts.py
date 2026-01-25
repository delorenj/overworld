"""Agent prompts and templates for the multi-agent pipeline.

This module contains structured prompts for LLM-based agents. Prompts are
designed to produce consistent, parseable JSON outputs for downstream processing.

STORY-005: Parser & Artist Agents
"""

from typing import Any

# =============================================================================
# Parser Agent Prompts
# =============================================================================

PARSER_SYSTEM_PROMPT = """You are a document structure analyzer for the Overworld map generation system.
Your task is to analyze a document hierarchy and transform it into a structured map layout.

The document hierarchy follows an L0-L4 level structure:
- L0: Root/Document level (single node) - The overarching project or document title
- L1: Main sections/milestones (H1 headers) - Major milestones or chapters
- L2: Subsections/epics (H2 headers) - Sub-milestones or sections within L1
- L3: Details/tasks (H3 headers) - Individual tasks or details
- L4: Fine-grained elements/subtasks (H4+ headers) - Subtasks or atomic items

Your output will be used to generate an 8/16-bit style adventure map where:
- Regions correspond to L1 milestones
- Landmarks correspond to L2 items within each region
- Paths connect regions and landmarks
- Icons represent L3/L4 detail items

You MUST respond with valid JSON only. No markdown, no explanations."""

PARSER_USER_PROMPT_TEMPLATE = """Analyze the following document hierarchy and generate a map structure.

## Document Hierarchy:
{hierarchy_json}

## Requirements:
1. Create regions from L1 milestones (each region should have a descriptive name and theme hint)
2. Place landmarks from L2 items within appropriate regions
3. Identify natural path connections between regions (linear progression or branching)
4. Assign L3/L4 items as detail points within landmarks
5. Suggest region themes based on content (e.g., "forest", "mountain", "castle", "village")

## Output Format:
Respond with a JSON object containing:
{{
    "map_title": "string - title for the entire map",
    "map_description": "string - brief description of the map's journey",
    "total_regions": number,
    "total_landmarks": number,
    "regions": [
        {{
            "id": "string - unique region ID",
            "name": "string - display name",
            "theme": "string - visual theme hint (forest/mountain/desert/castle/village/cave/ocean/sky)",
            "position_hint": "string - suggested position (north/south/east/west/center/start/end)",
            "description": "string - brief description",
            "source_milestone": {{
                "level": number,
                "id": "string",
                "title": "string"
            }},
            "landmarks": [
                {{
                    "id": "string - unique landmark ID",
                    "name": "string - display name",
                    "type": "string - landmark type (town/fortress/tower/bridge/shrine/camp/ruins/portal)",
                    "description": "string - brief description",
                    "source_item": {{
                        "level": number,
                        "id": "string",
                        "title": "string"
                    }},
                    "detail_points": [
                        {{
                            "id": "string",
                            "name": "string",
                            "icon_hint": "string - icon suggestion (star/chest/flag/key/scroll/gem)",
                            "source_item": {{
                                "level": number,
                                "id": "string",
                                "title": "string"
                            }}
                        }}
                    ]
                }}
            ]
        }}
    ],
    "paths": [
        {{
            "id": "string - unique path ID",
            "from_region": "string - source region ID",
            "to_region": "string - target region ID",
            "path_type": "string - path type (road/bridge/river/mountain_pass/teleport)",
            "description": "string - brief description"
        }}
    ],
    "metadata": {{
        "complexity": "string - simple/medium/complex",
        "suggested_style": "string - linear/branching/hub_spoke/circular",
        "estimated_journey_length": number
    }}
}}"""


PARSER_VALIDATION_PROMPT = """Validate the following map structure for consistency and completeness.

## Map Structure:
{map_structure_json}

## Validation Rules:
1. All region IDs must be unique
2. All landmark IDs must be unique
3. Path connections must reference valid region IDs
4. Each region should have at least one landmark (if L2 items exist)
5. Theme assignments should be consistent with content

## Output Format:
{{
    "valid": boolean,
    "errors": ["list of error messages"],
    "warnings": ["list of warning messages"],
    "suggestions": ["list of improvement suggestions"]
}}"""


# =============================================================================
# Artist Agent Prompts
# =============================================================================

ARTIST_SYSTEM_PROMPT = """You are a visual designer for the Overworld map generation system.
Your task is to generate visual descriptions and style specifications for an 8/16-bit style adventure map.

You specialize in creating retro-gaming aesthetic descriptions that evoke classic games like:
- Super Mario Bros 3 (world maps)
- The Legend of Zelda (overworld maps)
- Final Fantasy (world maps)
- Dragon Quest (town and dungeon maps)

Your output will be used to:
1. Generate color palettes for regions and landmarks
2. Suggest icon styles for different element types
3. Provide visual descriptions for map elements
4. Define texture and pattern hints for rendering

You MUST respond with valid JSON only. No markdown, no explanations."""

ARTIST_USER_PROMPT_TEMPLATE = """Generate visual specifications for the following map structure.

## Map Structure:
{map_structure_json}

## Theme Preference: {theme_id}

## Requirements:
1. Generate a cohesive color palette for each region based on its theme
2. Suggest icon styles for landmarks and detail points
3. Provide visual descriptions that capture the 8/16-bit aesthetic
4. Define path styling (color, pattern, width hints)
5. Suggest background and ambient elements

## Output Format:
Respond with a JSON object containing:
{{
    "map_style": {{
        "overall_palette": {{
            "primary": "#hexcolor - main color",
            "secondary": "#hexcolor - accent color",
            "background": "#hexcolor - background color",
            "text": "#hexcolor - text color",
            "highlight": "#hexcolor - highlight/selection color"
        }},
        "pixel_density": "string - low/medium/high (affects detail level)",
        "outline_style": "string - none/thin/thick/double",
        "shadow_style": "string - none/drop/pixel"
    }},
    "regions": [
        {{
            "region_id": "string - matches region ID from input",
            "visual_description": "string - 1-2 sentence visual description",
            "palette": {{
                "primary": "#hexcolor",
                "secondary": "#hexcolor",
                "accent": "#hexcolor",
                "ground": "#hexcolor"
            }},
            "texture_hint": "string - grass/sand/stone/water/lava/ice/cloud",
            "ambient_elements": ["list of decorative elements - trees/rocks/flowers/crystals/etc"],
            "mood": "string - peaceful/mysterious/dangerous/magical/industrial"
        }}
    ],
    "landmarks": [
        {{
            "landmark_id": "string - matches landmark ID from input",
            "visual_description": "string - 1-2 sentence visual description",
            "icon_style": {{
                "base_shape": "string - circle/square/triangle/diamond/custom",
                "size": "string - small/medium/large",
                "primary_color": "#hexcolor",
                "secondary_color": "#hexcolor",
                "animation_hint": "string - none/pulse/bounce/glow/sparkle"
            }},
            "sprite_suggestion": "string - description of ideal sprite/icon"
        }}
    ],
    "paths": [
        {{
            "path_id": "string - matches path ID from input",
            "style": {{
                "color": "#hexcolor",
                "width": "string - thin/medium/thick",
                "pattern": "string - solid/dotted/dashed/cobblestone/grass",
                "border_color": "#hexcolor or null"
            }},
            "decoration_hint": "string - optional path decoration (signs/flowers/stones)"
        }}
    ],
    "detail_icons": {{
        "star": {{
            "color": "#hexcolor",
            "style": "string - description"
        }},
        "chest": {{
            "color": "#hexcolor",
            "style": "string - description"
        }},
        "flag": {{
            "color": "#hexcolor",
            "style": "string - description"
        }},
        "key": {{
            "color": "#hexcolor",
            "style": "string - description"
        }},
        "scroll": {{
            "color": "#hexcolor",
            "style": "string - description"
        }},
        "gem": {{
            "color": "#hexcolor",
            "style": "string - description"
        }}
    }},
    "metadata": {{
        "style_coherence_score": number (0-100),
        "retro_authenticity_score": number (0-100),
        "visual_complexity": "string - minimal/moderate/detailed"
    }}
}}"""


ARTIST_THEME_PRESETS = {
    "smb3": {
        "name": "Super Mario Bros 3",
        "description": "Bright, cheerful colors with distinct world themes",
        "base_palette": {
            "primary": "#6B8CFF",  # Sky blue
            "secondary": "#D2691E",  # Brown (roads)
            "background": "#87CEEB",
            "text": "#FFFFFF",
            "highlight": "#FFD700",  # Gold
        },
        "world_themes": {
            "grass": {"ground": "#228B22", "accent": "#90EE90"},
            "desert": {"ground": "#F4A460", "accent": "#FFE4B5"},
            "water": {"ground": "#4169E1", "accent": "#87CEFA"},
            "ice": {"ground": "#E0FFFF", "accent": "#B0E0E6"},
            "sky": {"ground": "#87CEEB", "accent": "#FFFFFF"},
            "pipe": {"ground": "#32CD32", "accent": "#006400"},
            "castle": {"ground": "#696969", "accent": "#8B0000"},
        },
    },
    "zelda": {
        "name": "Legend of Zelda",
        "description": "Earthy tones with fantasy elements",
        "base_palette": {
            "primary": "#228B22",  # Forest green
            "secondary": "#8B4513",  # Brown
            "background": "#F5DEB3",  # Wheat
            "text": "#000000",
            "highlight": "#FFD700",
        },
        "world_themes": {
            "forest": {"ground": "#228B22", "accent": "#006400"},
            "mountain": {"ground": "#808080", "accent": "#A0522D"},
            "desert": {"ground": "#DEB887", "accent": "#D2691E"},
            "lake": {"ground": "#4682B4", "accent": "#87CEEB"},
            "volcano": {"ground": "#8B0000", "accent": "#FF4500"},
            "graveyard": {"ground": "#2F4F4F", "accent": "#708090"},
        },
    },
    "ff": {
        "name": "Final Fantasy",
        "description": "Rich, detailed world with varied biomes",
        "base_palette": {
            "primary": "#4169E1",  # Royal blue
            "secondary": "#2E8B57",  # Sea green
            "background": "#191970",  # Midnight blue
            "text": "#FFFFFF",
            "highlight": "#FFD700",
        },
        "world_themes": {
            "plains": {"ground": "#90EE90", "accent": "#32CD32"},
            "forest": {"ground": "#006400", "accent": "#228B22"},
            "mountain": {"ground": "#A0522D", "accent": "#D2691E"},
            "ocean": {"ground": "#0000CD", "accent": "#4169E1"},
            "desert": {"ground": "#F4A460", "accent": "#DEB887"},
            "snow": {"ground": "#FFFAFA", "accent": "#B0C4DE"},
            "castle": {"ground": "#708090", "accent": "#C0C0C0"},
        },
    },
}


# =============================================================================
# Fallback/Error Prompts
# =============================================================================

PARSER_FALLBACK_PROMPT = """The previous parsing attempt failed or produced invalid output.
Please generate a simplified map structure with the following constraints:

## Original Hierarchy:
{hierarchy_json}

## Error from previous attempt:
{error_message}

## Simplified Requirements:
1. Create at least 2 regions from L1 milestones
2. Use simple, sequential path connections
3. Include only essential landmarks
4. Skip L3/L4 detail points if causing issues

Generate a valid JSON response following the standard format."""


ARTIST_FALLBACK_PROMPT = """The previous visual generation failed or produced invalid output.
Please generate a simplified visual specification using the theme preset.

## Map Structure:
{map_structure_json}

## Theme: {theme_id}

## Error from previous attempt:
{error_message}

## Simplified Requirements:
1. Use the preset theme colors directly
2. Generate minimal region styling
3. Use default icon styles
4. Skip complex ambient elements

Generate a valid JSON response following the standard format."""


# =============================================================================
# Utility Functions
# =============================================================================

def format_parser_prompt(hierarchy: dict[str, Any]) -> tuple[str, str]:
    """Format the parser prompt with hierarchy data.

    Args:
        hierarchy: Document hierarchy in L0-L4 format

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    import json
    hierarchy_json = json.dumps(hierarchy, indent=2)
    user_prompt = PARSER_USER_PROMPT_TEMPLATE.format(hierarchy_json=hierarchy_json)
    return PARSER_SYSTEM_PROMPT, user_prompt


def format_artist_prompt(
    map_structure: dict[str, Any],
    theme_id: str = "smb3"
) -> tuple[str, str]:
    """Format the artist prompt with map structure data.

    Args:
        map_structure: Parsed map structure from ParserAgent
        theme_id: Theme preset identifier

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    import json
    map_json = json.dumps(map_structure, indent=2)
    user_prompt = ARTIST_USER_PROMPT_TEMPLATE.format(
        map_structure_json=map_json,
        theme_id=theme_id
    )
    return ARTIST_SYSTEM_PROMPT, user_prompt


def format_parser_fallback_prompt(
    hierarchy: dict[str, Any],
    error_message: str
) -> tuple[str, str]:
    """Format the parser fallback prompt.

    Args:
        hierarchy: Document hierarchy
        error_message: Error from previous attempt

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    import json
    hierarchy_json = json.dumps(hierarchy, indent=2)
    user_prompt = PARSER_FALLBACK_PROMPT.format(
        hierarchy_json=hierarchy_json,
        error_message=error_message
    )
    return PARSER_SYSTEM_PROMPT, user_prompt


def format_artist_fallback_prompt(
    map_structure: dict[str, Any],
    theme_id: str,
    error_message: str
) -> tuple[str, str]:
    """Format the artist fallback prompt.

    Args:
        map_structure: Map structure data
        theme_id: Theme preset identifier
        error_message: Error from previous attempt

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    import json
    map_json = json.dumps(map_structure, indent=2)
    user_prompt = ARTIST_FALLBACK_PROMPT.format(
        map_structure_json=map_json,
        theme_id=theme_id,
        error_message=error_message
    )
    return ARTIST_SYSTEM_PROMPT, user_prompt


def get_theme_preset(theme_id: str) -> dict[str, Any]:
    """Get a theme preset by ID.

    Args:
        theme_id: Theme identifier (smb3, zelda, ff)

    Returns:
        Theme preset dictionary, defaults to smb3 if not found
    """
    return ARTIST_THEME_PRESETS.get(theme_id, ARTIST_THEME_PRESETS["smb3"])
