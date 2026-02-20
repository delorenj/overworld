"""Pydantic schemas for project API endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    """Request schema for creating a new project."""

    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: str | None = Field(None, description="Optional project description")


class ProjectResponse(BaseModel):
    """Response schema for project details."""

    id: UUID
    user_id: int
    name: str
    description: str | None
    status: str
    document_count: int
    created_at: datetime
    updated_at: datetime
    analyzed_at: datetime | None

    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    """Response schema for paginated project list."""

    projects: list[ProjectResponse]
    total: int
    skip: int
    limit: int


class AddDocumentRequest(BaseModel):
    """Request schema for adding a document to a project."""

    document_id: UUID = Field(..., description="Document UUID to add to project")


class ProjectAnalysisRequest(BaseModel):
    """Request schema for triggering consensus analysis."""

    force_reanalyze: bool = Field(
        False, description="Force re-analysis even if already analyzed"
    )


class ProjectAnalysisResponse(BaseModel):
    """Response schema for consensus analysis job status."""

    analysis_id: UUID
    project_id: UUID
    status: str
    arq_job_id: str | None
    converged: bool
    total_rounds: int
    milestones_count: int
    checkpoints_count: int
    versions_count: int
    total_tokens: int
    total_cost: float
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    class Config:
        from_attributes = True


class MilestoneResponse(BaseModel):
    """Response schema for milestone details."""

    id: UUID
    title: str
    description: str
    type: str
    estimated_effort: str
    dependencies: list[str]
    created_order: int

    class Config:
        from_attributes = True


class CheckpointResponse(BaseModel):
    """Response schema for checkpoint details."""

    id: UUID
    title: str
    type: str
    validation_criteria: list[str]
    milestone_id: UUID

    class Config:
        from_attributes = True


class VersionResponse(BaseModel):
    """Response schema for version details."""

    id: UUID
    name: str
    release_goal: str
    milestone_titles: list[str]
    created_order: int

    class Config:
        from_attributes = True


class ConsensusResultResponse(BaseModel):
    """Response schema for complete consensus analysis result."""

    analysis: ProjectAnalysisResponse
    milestones: list[MilestoneResponse]
    checkpoints: list[CheckpointResponse]
    versions: list[VersionResponse]
    reasoning: str | None

    class Config:
        from_attributes = True
