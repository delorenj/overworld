"""API router for project management and consensus analysis."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models import (
    ConsensusAnalysis,
    Document,
    Project,
    ProjectDocument,
    AnalysisStatus,
    ProjectStatus,
    Milestone,
    Checkpoint,
    Version,
)
from app.schemas.project import (
    AddDocumentRequest,
    CheckpointResponse,
    ConsensusResultResponse,
    MilestoneResponse,
    ProjectAnalysisRequest,
    ProjectAnalysisResponse,
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    VersionResponse,
)

router = APIRouter(prefix="/projects", tags=["projects"])
logger = logging.getLogger(__name__)


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create project",
    description="Create a new project for organizing documents and consensus analysis",
)
async def create_project(
    project_data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Create a new project.

    Args:
        project_data: Project creation data
        db: Database session

    Returns:
        ProjectResponse with created project details
    """
    # TODO: Replace with actual authenticated user_id
    user_id = 1

    project = Project(
        user_id=user_id,
        name=project_data.name,
        description=project_data.description,
        status=ProjectStatus.CREATED,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    db.add(project)
    await db.commit()
    await db.refresh(project)

    logger.info(f"Created project {project.id} for user {user_id}")

    return ProjectResponse(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        description=project.description,
        status=project.status.value,
        document_count=0,
        created_at=project.created_at,
        updated_at=project.updated_at,
        analyzed_at=project.analyzed_at,
    )


@router.get(
    "",
    response_model=ProjectListResponse,
    summary="List projects",
    description="Get a paginated list of projects for the current user",
)
async def list_projects(
    skip: int = Query(0, ge=0, description="Number of projects to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of projects to return"),
    status_filter: str | None = Query(None, description="Filter by project status"),
    db: AsyncSession = Depends(get_db),
) -> ProjectListResponse:
    """List projects for the current user with pagination.

    Args:
        skip: Number of projects to skip
        limit: Maximum number of projects to return
        status_filter: Optional status filter
        db: Database session

    Returns:
        ProjectListResponse with paginated projects
    """
    # TODO: Replace with actual authenticated user_id
    user_id = 1

    # Build query
    query = (
        select(Project)
        .where(Project.user_id == user_id)
        .options(selectinload(Project.documents))
    )

    # Apply status filter
    if status_filter:
        try:
            status_enum = ProjectStatus(status_filter)
            query = query.where(Project.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status filter. Valid values: {[s.value for s in ProjectStatus]}",
            )

    # Get total count
    count_query = select(Project.id).where(Project.user_id == user_id)
    if status_filter:
        count_query = count_query.where(Project.status == ProjectStatus(status_filter))
    count_result = await db.execute(count_query)
    total = len(count_result.all())

    # Apply pagination and ordering
    query = query.order_by(Project.updated_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    projects = result.scalars().all()

    project_responses = [
        ProjectResponse(
            id=p.id,
            user_id=p.user_id,
            name=p.name,
            description=p.description,
            status=p.status.value,
            document_count=len(p.documents),
            created_at=p.created_at,
            updated_at=p.updated_at,
            analyzed_at=p.analyzed_at,
        )
        for p in projects
    ]

    return ProjectListResponse(
        projects=project_responses,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get project",
    description="Get project details by ID",
)
async def get_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Get project by ID.

    Args:
        project_id: Project UUID
        db: Database session

    Returns:
        ProjectResponse with project details

    Raises:
        HTTPException: 404 if project not found
    """
    # TODO: Replace with actual authenticated user_id
    user_id = 1

    query = (
        select(Project)
        .where(Project.id == project_id, Project.user_id == user_id)
        .options(selectinload(Project.documents))
    )
    result = await db.execute(query)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    return ProjectResponse(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        description=project.description,
        status=project.status.value,
        document_count=len(project.documents),
        created_at=project.created_at,
        updated_at=project.updated_at,
        analyzed_at=project.analyzed_at,
    )


@router.post(
    "/{project_id}/documents",
    status_code=status.HTTP_201_CREATED,
    summary="Add document to project",
    description="Associate an existing document with a project",
)
async def add_document_to_project(
    project_id: UUID,
    request: AddDocumentRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Add a document to a project.

    Args:
        project_id: Project UUID
        request: Document addition request
        db: Database session

    Returns:
        Success message with document association details

    Raises:
        HTTPException: 404 if project or document not found
        HTTPException: 400 if document already in project
    """
    # TODO: Replace with actual authenticated user_id
    user_id = 1

    # Verify project exists and belongs to user
    project_query = select(Project).where(
        Project.id == project_id, Project.user_id == user_id
    )
    project_result = await db.execute(project_query)
    project = project_result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    # Verify document exists and belongs to user
    doc_query = select(Document).where(
        Document.id == request.document_id, Document.user_id == user_id
    )
    doc_result = await db.execute(doc_query)
    document = doc_result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {request.document_id} not found",
        )

    # Check if document already in project
    existing_query = select(ProjectDocument).where(
        ProjectDocument.project_id == project_id,
        ProjectDocument.document_id == request.document_id,
    )
    existing_result = await db.execute(existing_query)
    existing = existing_result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document {request.document_id} already in project",
        )

    # Get current document count for order_index
    count_query = select(ProjectDocument).where(
        ProjectDocument.project_id == project_id
    )
    count_result = await db.execute(count_query)
    current_count = len(count_result.all())

    # Create association
    project_doc = ProjectDocument(
        project_id=project_id,
        document_id=request.document_id,
        added_at=datetime.now(UTC),
        order_index=current_count,
    )
    db.add(project_doc)

    # Update project status to READY if it was CREATED
    if project.status == ProjectStatus.CREATED:
        project.status = ProjectStatus.READY
        project.updated_at = datetime.now(UTC)

    await db.commit()

    logger.info(f"Added document {request.document_id} to project {project_id}")

    return {
        "message": "Document added to project successfully",
        "project_id": str(project_id),
        "document_id": str(request.document_id),
        "order_index": current_count,
    }


@router.post(
    "/{project_id}/analyze",
    response_model=ProjectAnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger consensus analysis",
    description="Queue a consensus analysis job for the project",
)
async def trigger_analysis(
    project_id: UUID,
    request: ProjectAnalysisRequest,
    db: AsyncSession = Depends(get_db),
) -> ProjectAnalysisResponse:
    """Trigger consensus analysis for a project.

    This endpoint queues an ARQ background job to run multi-agent
    consensus analysis on all documents in the project.

    Args:
        project_id: Project UUID
        request: Analysis request parameters
        db: Database session

    Returns:
        ProjectAnalysisResponse with job details

    Raises:
        HTTPException: 404 if project not found
        HTTPException: 400 if project has no documents or is already analyzing
    """
    # TODO: Replace with actual authenticated user_id
    user_id = 1

    # Get project with documents
    query = (
        select(Project)
        .where(Project.id == project_id, Project.user_id == user_id)
        .options(selectinload(Project.documents))
    )
    result = await db.execute(query)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    # Check if project has documents
    if not project.has_documents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project must have at least one document before analysis",
        )

    # Check if project is already being analyzed
    if project.status == ProjectStatus.ANALYZING and not request.force_reanalyze:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project is currently being analyzed. Use force_reanalyze=true to override.",
        )

    # Create consensus analysis record
    analysis = ConsensusAnalysis(
        project_id=project_id,
        user_id=user_id,
        status=AnalysisStatus.PENDING,
        created_at=datetime.now(UTC),
    )
    db.add(analysis)

    # Update project status
    project.status = ProjectStatus.ANALYZING
    project.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(analysis)

    # Queue ARQ job for consensus analysis
    from app.core.arq_config import enqueue_job

    arq_job_id = f"consensus-{analysis.id}"
    job = await enqueue_job(
        "app.workers.consensus_tasks.process_consensus_analysis",
        str(analysis.id),
        _job_id=arq_job_id,
    )

    if job:
        analysis.arq_job_id = arq_job_id
        await db.commit()
        logger.info(f"Queued consensus analysis {analysis.id} (ARQ: {arq_job_id})")
    else:
        logger.warning(f"Failed to enqueue consensus job for analysis {analysis.id}")

    return ProjectAnalysisResponse(
        analysis_id=analysis.id,
        project_id=analysis.project_id,
        status=analysis.status.value,
        arq_job_id=analysis.arq_job_id,
        converged=analysis.converged,
        total_rounds=analysis.total_rounds,
        milestones_count=analysis.milestones_count,
        checkpoints_count=analysis.checkpoints_count,
        versions_count=analysis.versions_count,
        total_tokens=analysis.total_tokens,
        total_cost=analysis.total_cost,
        created_at=analysis.created_at,
        started_at=analysis.started_at,
        completed_at=analysis.completed_at,
    )


@router.get(
    "/{project_id}/analysis",
    response_model=ConsensusResultResponse,
    summary="Get latest analysis",
    description="Get the most recent consensus analysis result for a project",
)
async def get_latest_analysis(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ConsensusResultResponse:
    """Get the latest consensus analysis for a project.

    Args:
        project_id: Project UUID
        db: Database session

    Returns:
        ConsensusResultResponse with full analysis details

    Raises:
        HTTPException: 404 if project not found or no analysis exists
    """
    # TODO: Replace with actual authenticated user_id
    user_id = 1

    # Get project
    project_query = select(Project).where(
        Project.id == project_id, Project.user_id == user_id
    )
    project_result = await db.execute(project_query)
    project = project_result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    # Get latest analysis with all relationships
    analysis_query = (
        select(ConsensusAnalysis)
        .where(ConsensusAnalysis.project_id == project_id)
        .options(
            selectinload(ConsensusAnalysis.milestones),
            selectinload(ConsensusAnalysis.checkpoints),
            selectinload(ConsensusAnalysis.versions),
        )
        .order_by(ConsensusAnalysis.created_at.desc())
    )
    analysis_result = await db.execute(analysis_query)
    analysis = analysis_result.scalar_one_or_none()

    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No analysis found for project {project_id}",
        )

    # Build response
    return ConsensusResultResponse(
        analysis=ProjectAnalysisResponse(
            analysis_id=analysis.id,
            project_id=analysis.project_id,
            status=analysis.status.value,
            arq_job_id=analysis.arq_job_id,
            converged=analysis.converged,
            total_rounds=analysis.total_rounds,
            milestones_count=analysis.milestones_count,
            checkpoints_count=analysis.checkpoints_count,
            versions_count=analysis.versions_count,
            total_tokens=analysis.total_tokens,
            total_cost=analysis.total_cost,
            created_at=analysis.created_at,
            started_at=analysis.started_at,
            completed_at=analysis.completed_at,
        ),
        milestones=[
            MilestoneResponse(
                id=m.id,
                title=m.title,
                description=m.description,
                type=m.type.value,
                estimated_effort=m.estimated_effort.value,
                dependencies=m.dependencies,
                created_order=m.created_order,
            )
            for m in analysis.milestones
        ],
        checkpoints=[
            CheckpointResponse(
                id=c.id,
                title=c.title,
                type=c.type.value,
                validation_criteria=c.validation_criteria,
                milestone_id=c.milestone_id,
            )
            for c in analysis.checkpoints
        ],
        versions=[
            VersionResponse(
                id=v.id,
                name=v.name,
                release_goal=v.release_goal,
                milestone_titles=v.milestone_titles,
                created_order=v.created_order,
            )
            for v in analysis.versions
        ],
        reasoning=analysis.reasoning,
    )
