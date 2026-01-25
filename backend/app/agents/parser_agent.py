"""Parser Agent for document hierarchy analysis and map structure generation.

This module implements the ParserAgent which analyzes document hierarchies
and transforms them into structured map layouts for the Overworld map generator.

STORY-005: Parser & Artist Agents

The ParserAgent supports two modes of operation:
1. Simple mode (legacy): Basic hierarchy validation and milestone extraction
2. LLM-enhanced mode: Full map structure generation using AI prompts
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
    format_parser_fallback_prompt,
    format_parser_prompt,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic Models for Parser Agent
# =============================================================================


class SourceMilestone(BaseModel):
    """Source milestone reference from the original hierarchy."""

    level: int = Field(..., ge=0, le=4, description="Hierarchy level")
    id: str = Field(..., description="Original milestone ID")
    title: str = Field(..., description="Original milestone title")


class DetailPoint(BaseModel):
    """A detail point within a landmark (L3/L4 items)."""

    id: str = Field(..., description="Unique detail point ID")
    name: str = Field(..., description="Display name")
    icon_hint: str = Field(default="star", description="Icon suggestion")
    source_item: Optional[SourceMilestone] = Field(
        default=None, description="Source hierarchy item"
    )


class Landmark(BaseModel):
    """A landmark within a region (L2 items)."""

    id: str = Field(..., description="Unique landmark ID")
    name: str = Field(..., description="Display name")
    type: str = Field(default="town", description="Landmark type")
    description: str = Field(default="", description="Brief description")
    source_item: Optional[SourceMilestone] = Field(
        default=None, description="Source hierarchy item"
    )
    detail_points: list[DetailPoint] = Field(
        default_factory=list, description="Detail points within this landmark"
    )


class Region(BaseModel):
    """A region in the map (L1 items)."""

    id: str = Field(..., description="Unique region ID")
    name: str = Field(..., description="Display name")
    theme: str = Field(default="plains", description="Visual theme hint")
    position_hint: str = Field(default="center", description="Position suggestion")
    description: str = Field(default="", description="Brief description")
    source_milestone: Optional[SourceMilestone] = Field(
        default=None, description="Source hierarchy milestone"
    )
    landmarks: list[Landmark] = Field(
        default_factory=list, description="Landmarks in this region"
    )


class MapPath(BaseModel):
    """A path connecting regions."""

    id: str = Field(..., description="Unique path ID")
    from_region: str = Field(..., description="Source region ID")
    to_region: str = Field(..., description="Target region ID")
    path_type: str = Field(default="road", description="Path type")
    description: str = Field(default="", description="Brief description")


class MapMetadata(BaseModel):
    """Metadata about the generated map structure."""

    complexity: str = Field(default="medium", description="Map complexity")
    suggested_style: str = Field(default="linear", description="Layout style")
    estimated_journey_length: int = Field(default=1, description="Journey length")


class MapStructure(BaseModel):
    """Complete parsed map structure."""

    map_title: str = Field(..., description="Title for the map")
    map_description: str = Field(default="", description="Map description")
    total_regions: int = Field(default=0, description="Total region count")
    total_landmarks: int = Field(default=0, description="Total landmark count")
    regions: list[Region] = Field(default_factory=list, description="Map regions")
    paths: list[MapPath] = Field(default_factory=list, description="Connecting paths")
    metadata: MapMetadata = Field(
        default_factory=MapMetadata, description="Map metadata"
    )


class ParserInput(AgentInput):
    """Input data for ParserAgent."""

    hierarchy: dict[str, Any] = Field(..., description="Document hierarchy in L0-L4 format")
    use_llm: bool = Field(default=False, description="Use LLM for enhanced parsing")
    fallback_to_simple: bool = Field(
        default=True, description="Fallback to simple mode on LLM failure"
    )


class ParserOutput(AgentOutput):
    """Output data from ParserAgent."""

    valid: bool = Field(default=False, description="Whether hierarchy is valid")
    milestone_count: int = Field(default=0, description="Total milestone count")
    levels: list[int] = Field(default_factory=list, description="Hierarchy levels found")
    milestones: list[dict[str, Any]] = Field(
        default_factory=list, description="Processed milestones (simple mode)"
    )
    map_structure: Optional[MapStructure] = Field(
        default=None, description="Full map structure (LLM mode)"
    )
    statistics: dict[str, Any] = Field(
        default_factory=dict, description="Parsing statistics"
    )
    parsing_mode: str = Field(default="simple", description="Mode used: simple or llm")


# =============================================================================
# Enhanced Parser Agent (New Framework)
# =============================================================================


class EnhancedParserAgent(BaseAgent[ParserInput, ParserOutput]):
    """Enhanced Parser Agent using the new BaseAgent framework.

    This agent analyzes document hierarchies and generates map structures
    using either simple rule-based parsing or LLM-enhanced analysis.

    Features:
    - Typed input/output with Pydantic validation
    - LLM integration for intelligent map structure generation
    - Fallback strategies for error recovery
    - Progress reporting during processing
    """

    input_type: ClassVar[type[BaseModel]] = ParserInput
    output_type: ClassVar[type[BaseModel]] = ParserOutput
    default_config: ClassVar[AgentConfig] = AgentConfig(
        name="ParserAgent",
        version="2.0.0",
        default_model="claude-3-5-sonnet",
        temperature=0.3,  # Lower temperature for more consistent parsing
        timeout_seconds=60,
        max_retries=3,
        capabilities=[AgentCapability.LLM_CALLS, AgentCapability.CHECKPOINTING],
    )

    async def process(
        self, input_data: ParserInput, ctx: ExecutionContext
    ) -> ParserOutput:
        """Process the hierarchy and generate map structure.

        Args:
            input_data: Parser input with hierarchy data
            ctx: Execution context

        Returns:
            Parser output with map structure
        """
        hierarchy = input_data.hierarchy

        # Report progress
        ctx.report_progress(
            agent_name=self.name,
            progress_pct=10.0,
            stage="parsing",
            message="Validating hierarchy structure",
        )

        # Validate basic hierarchy structure
        validation_result = self._validate_hierarchy(hierarchy)
        if not validation_result["valid"]:
            return ParserOutput(
                success=False,
                valid=False,
                error_message=validation_result["error"],
            )

        ctx.report_progress(
            agent_name=self.name,
            progress_pct=30.0,
            stage="parsing",
            message="Extracting milestones",
        )

        # Extract milestones using simple parsing
        simple_result = self._simple_parse(hierarchy)

        if not input_data.use_llm:
            # Return simple parsing result
            ctx.report_progress(
                agent_name=self.name,
                progress_pct=100.0,
                stage="parsing",
                message="Simple parsing complete",
            )
            return ParserOutput(
                success=True,
                valid=True,
                data=simple_result,
                milestone_count=simple_result["milestone_count"],
                levels=simple_result["levels"],
                milestones=simple_result["milestones"],
                statistics=simple_result["statistics"],
                parsing_mode="simple",
            )

        # LLM-enhanced parsing
        ctx.report_progress(
            agent_name=self.name,
            progress_pct=50.0,
            stage="parsing",
            message="Generating map structure with LLM",
        )

        try:
            map_structure = await self._llm_parse(hierarchy, ctx)

            ctx.report_progress(
                agent_name=self.name,
                progress_pct=100.0,
                stage="parsing",
                message="LLM parsing complete",
            )

            return ParserOutput(
                success=True,
                valid=True,
                data={
                    "valid": True,
                    "map_structure": map_structure.model_dump(),
                    "milestone_count": simple_result["milestone_count"],
                },
                milestone_count=simple_result["milestone_count"],
                levels=simple_result["levels"],
                milestones=simple_result["milestones"],
                map_structure=map_structure,
                statistics={
                    **simple_result["statistics"],
                    "regions": map_structure.total_regions,
                    "landmarks": map_structure.total_landmarks,
                    "paths": len(map_structure.paths),
                },
                parsing_mode="llm",
            )

        except Exception as e:
            logger.warning(f"LLM parsing failed: {e}")

            if input_data.fallback_to_simple:
                ctx.report_progress(
                    agent_name=self.name,
                    progress_pct=100.0,
                    stage="parsing",
                    message="Falling back to simple parsing",
                )

                return ParserOutput(
                    success=True,
                    valid=True,
                    data=simple_result,
                    milestone_count=simple_result["milestone_count"],
                    levels=simple_result["levels"],
                    milestones=simple_result["milestones"],
                    statistics=simple_result["statistics"],
                    parsing_mode="simple_fallback",
                )

            return ParserOutput(
                success=False,
                valid=False,
                error_message=f"LLM parsing failed: {str(e)}",
            )

    def _validate_hierarchy(self, hierarchy: dict[str, Any]) -> dict[str, Any]:
        """Validate the basic hierarchy structure.

        Args:
            hierarchy: Document hierarchy

        Returns:
            Validation result with 'valid' and 'error' keys
        """
        if not hierarchy:
            return {"valid": False, "error": "No hierarchy data provided"}

        # Check for required L0 or L1 data
        has_l0 = "L0" in hierarchy and hierarchy["L0"]
        has_l1 = "L1" in hierarchy and isinstance(hierarchy["L1"], list)

        if not has_l0 and not has_l1:
            return {
                "valid": False,
                "error": "Hierarchy must contain at least L0 or L1 data",
            }

        # Validate L1 has items
        if has_l1 and len(hierarchy["L1"]) == 0:
            return {"valid": False, "error": "L1 milestone list is empty"}

        return {"valid": True, "error": None}

    def _simple_parse(self, hierarchy: dict[str, Any]) -> dict[str, Any]:
        """Perform simple rule-based parsing.

        Args:
            hierarchy: Document hierarchy

        Returns:
            Parsed milestone data
        """
        milestones: list[dict[str, Any]] = []
        levels: set[int] = set()

        # Process L0 (root)
        if "L0" in hierarchy and hierarchy["L0"]:
            root = hierarchy["L0"]
            milestones.append({
                "level": 0,
                "id": root.get("id", "root"),
                "title": root.get("title", "Project"),
                "pos": 0,
            })

        # Process L1 milestones
        if "L1" in hierarchy and isinstance(hierarchy["L1"], list):
            for i, milestone in enumerate(hierarchy["L1"]):
                if milestone:
                    milestones.append({
                        "level": 1,
                        "id": milestone.get("id", f"m{i+1}"),
                        "title": milestone.get("title", f"Milestone {i+1}"),
                        "pos": i + 1,
                    })
                    levels.add(1)

        # Process L2 epics
        if "L2" in hierarchy and isinstance(hierarchy["L2"], list):
            for i, epic in enumerate(hierarchy["L2"]):
                if isinstance(epic, dict) and ("id" in epic or "title" in epic):
                    milestones.append({
                        "level": 2,
                        "id": epic.get("id", f"e{i+1}"),
                        "title": epic.get("title", f"Epic {i+1}"),
                        "parent_id": epic.get("parent_id"),
                        "pos": i + 51,
                    })
                    levels.add(2)

        # Process L3 tasks
        if "L3" in hierarchy and isinstance(hierarchy["L3"], list):
            for i, task in enumerate(hierarchy["L3"]):
                if isinstance(task, dict) and ("id" in task or "title" in task):
                    milestones.append({
                        "level": 3,
                        "id": task.get("id", f"t{i+1}"),
                        "title": task.get("title", f"Task {i+1}"),
                        "parent_id": task.get("parent_id"),
                        "pos": i + 101,
                    })
                    levels.add(3)

        # Process L4 subtasks
        if "L4" in hierarchy and isinstance(hierarchy["L4"], list):
            for i, subtask in enumerate(hierarchy["L4"]):
                if isinstance(subtask, dict) and ("id" in subtask or "title" in subtask):
                    milestones.append({
                        "level": 4,
                        "id": subtask.get("id", f"st{i+1}"),
                        "title": subtask.get("title", f"Subtask {i+1}"),
                        "parent_id": subtask.get("parent_id"),
                        "pos": i + 151,
                    })
                    levels.add(4)

        # Sort by position
        milestones.sort(key=lambda m: m["pos"])

        # Build statistics
        level_counts = {}
        for level in levels:
            level_counts[level] = sum(1 for m in milestones if m["level"] == level)

        return {
            "valid": True,
            "milestone_count": len(milestones),
            "levels": sorted(list(levels)),
            "milestones": milestones,
            "statistics": {
                "total": len(milestones),
                "by_level": level_counts,
            },
        }

    async def _llm_parse(
        self, hierarchy: dict[str, Any], ctx: ExecutionContext
    ) -> MapStructure:
        """Use LLM to generate a rich map structure.

        Args:
            hierarchy: Document hierarchy
            ctx: Execution context

        Returns:
            Parsed MapStructure

        Raises:
            ValueError: If LLM response cannot be parsed
        """
        system_prompt, user_prompt = format_parser_prompt(hierarchy)

        # Make LLM call
        response = await self.call_llm_with_system(
            system_prompt=system_prompt,
            user_message=user_prompt,
            temperature=0.3,
            ctx=ctx,
        )

        # Parse JSON response
        try:
            # Extract JSON from response (handle potential markdown code blocks)
            json_content = self._extract_json(response)
            data = json.loads(json_content)
            return MapStructure(**data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            # Try fallback prompt
            return await self._llm_parse_with_fallback(hierarchy, str(e), ctx)
        except Exception as e:
            logger.error(f"Failed to validate LLM response: {e}")
            raise ValueError(f"Invalid LLM response: {e}")

    async def _llm_parse_with_fallback(
        self, hierarchy: dict[str, Any], error: str, ctx: ExecutionContext
    ) -> MapStructure:
        """Retry LLM parsing with fallback prompt.

        Args:
            hierarchy: Document hierarchy
            error: Previous error message
            ctx: Execution context

        Returns:
            Parsed MapStructure

        Raises:
            ValueError: If fallback also fails
        """
        system_prompt, user_prompt = format_parser_fallback_prompt(hierarchy, error)

        response = await self.call_llm_with_system(
            system_prompt=system_prompt,
            user_message=user_prompt,
            temperature=0.2,  # Even lower for retry
            ctx=ctx,
        )

        try:
            json_content = self._extract_json(response)
            data = json.loads(json_content)
            return MapStructure(**data)
        except Exception as e:
            raise ValueError(f"Fallback parsing also failed: {e}")

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


# =============================================================================
# Legacy Parser Agent (Backward Compatibility)
# =============================================================================


class ParserAgent(LegacyBaseAgent):
    """Legacy Parser Agent for backward compatibility.

    This agent validates and analyzes document hierarchy from STORY-002.
    It uses the legacy JobContext/AgentResult interface for compatibility
    with existing code while internally using the enhanced parsing logic.
    """

    def __init__(self):
        """Initialize the parser agent."""
        super().__init__()
        self._enhanced = EnhancedParserAgent()

    async def execute(self, context: JobContext) -> AgentResult:
        """Validate and parse document hierarchy.

        Args:
            context: Job context with hierarchy data

        Returns:
            AgentResult with parsed milestones
        """
        hierarchy = context.hierarchy

        try:
            # Use the enhanced parser's simple parsing logic
            validation = self._enhanced._validate_hierarchy(hierarchy)
            if not validation["valid"]:
                return AgentResult(
                    success=False,
                    error=validation["error"],
                )

            result = self._enhanced._simple_parse(hierarchy)

            # Validate minimum requirements
            if not any(m["level"] == 1 for m in result["milestones"]):
                return AgentResult(
                    success=False,
                    error="At least 1 L1 milestone required",
                )

            if len(result["milestones"]) > 50:
                return AgentResult(
                    success=False,
                    error=f"Too many milestones: {len(result['milestones'])} (max 50 for MVP)",
                )

            return AgentResult(
                success=True,
                data=result,
            )

        except Exception as e:
            return AgentResult(
                success=False,
                error=f"Parser failed: {str(e)}",
            )


# Export both versions
__all__ = [
    "ParserAgent",
    "EnhancedParserAgent",
    "ParserInput",
    "ParserOutput",
    "MapStructure",
    "Region",
    "Landmark",
    "MapPath",
    "DetailPoint",
]
