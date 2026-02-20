"""Consensus extraction schemas for multi-agent project analysis.

These Pydantic models define the structured output format for TheBoard
agents analyzing project documents to extract milestones, checkpoints,
and version boundaries.
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class MilestoneExtraction(BaseModel):
    """Structured extraction for a project milestone.

    Milestones represent major deliverables with clear boundaries.
    They combine technical and product perspectives from EM/PM consensus.
    """

    title: str = Field(
        description="Clear, concise milestone title (e.g., 'User Authentication System')"
    )
    description: str = Field(
        description="Detailed description of what this milestone delivers"
    )
    type: Literal["technical", "product", "hybrid"] = Field(
        description="Primary focus: technical infrastructure, user-facing features, or both"
    )
    estimated_effort: Literal["S", "M", "L", "XL"] = Field(
        description="Relative effort estimate (S=1-3 days, M=1-2 weeks, L=2-4 weeks, XL=4+ weeks)"
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="List of milestone titles that must complete before this one"
    )
    checkpoints: list[str] = Field(
        default_factory=list,
        description="Associated checkpoint titles for validation"
    )


class CheckpointExtraction(BaseModel):
    """Structured extraction for a validation checkpoint.

    Checkpoints are intermediate validation points within milestones.
    Examples: PoC demo, integration test, user testing session.
    """

    title: str = Field(
        description="Clear checkpoint title (e.g., 'OAuth Integration PoC')"
    )
    milestone_title: str = Field(
        description="Parent milestone this checkpoint validates"
    )
    validation_criteria: list[str] = Field(
        description="Specific, measurable criteria for checkpoint success"
    )
    type: Literal["poc", "demo", "test", "review"] = Field(
        default="test",
        description="Checkpoint type for categorization"
    )


class VersionExtraction(BaseModel):
    """Structured extraction for a version/release boundary.

    Versions group milestones into shippable increments.
    """

    name: str = Field(
        description="Version identifier (e.g., 'MVP', 'v1.0', 'Beta')"
    )
    milestone_titles: list[str] = Field(
        description="Milestone titles included in this version"
    )
    release_goal: str = Field(
        description="High-level user-facing goal for this version"
    )


class ProjectStructureExtraction(BaseModel):
    """Complete structured extraction from EM/PM consensus.

    This is the output schema for ProjectNotetakerAgent.
    Agno automatically validates responses against this schema.
    """

    milestones: list[MilestoneExtraction] = Field(
        description="Extracted project milestones (3-10 typical)"
    )
    checkpoints: list[CheckpointExtraction] = Field(
        description="Validation checkpoints within milestones"
    )
    versions: list[VersionExtraction] = Field(
        description="Version/release boundaries grouping milestones"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score for this extraction (0.0-1.0)"
    )
    reasoning: str = Field(
        description="Brief explanation of why this structure was chosen"
    )


class ConsensusRound(BaseModel):
    """Represents one round of EM/PM analysis."""

    round_number: int
    em_response: str
    pm_response: str
    extraction: ProjectStructureExtraction
    novelty_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Similarity to previous rounds (0=identical, 1=novel)"
    )


class ConsensusResult(BaseModel):
    """Final consensus result after multi-round analysis."""

    project_id: UUID
    rounds: list[ConsensusRound]
    final_structure: ProjectStructureExtraction
    converged: bool = Field(
        description="Whether agents reached consensus (novelty < threshold)"
    )
    total_rounds: int
    analysis_duration_seconds: float
