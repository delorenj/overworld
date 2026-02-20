"""ARQ worker tasks for consensus analysis processing.

This module defines async task functions for multi-agent consensus analysis.
Tasks are processed by ARQ workers and emit progress events via Bloodbank.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_factory
from app.events.emitter import get_event_emitter
from app.models import (
    AnalysisStatus,
    Checkpoint,
    CheckpointType,
    ConsensusAnalysis,
    Document,
    EffortSize,
    Milestone,
    MilestoneType,
    Project,
    ProjectDocument,
    ProjectStatus,
    Version,
)
from app.services.consensus_service import ProjectConsensusService

logger = logging.getLogger(__name__)


async def process_consensus_analysis(ctx: dict, analysis_id: str) -> dict:
    """Process a consensus analysis job.

    This task orchestrates the multi-round EM/PM consensus workflow and
    persists extracted milestones, checkpoints, and versions to the database.

    Args:
        ctx: ARQ context containing redis connection and metadata
        analysis_id: UUID of ConsensusAnalysis record

    Returns:
        Dict with job result information

    State Transitions:
        ConsensusAnalysis: PENDING → ANALYZING → CONVERGED/FAILED
        Project: ANALYZING → ANALYZED/FAILED
    """
    analysis_uuid = UUID(analysis_id)
    logger.info(f"Starting consensus analysis {analysis_id}")

    # Get database session
    session_factory = get_session_factory()

    async with session_factory() as db:
        # Load analysis record
        query = select(ConsensusAnalysis).where(ConsensusAnalysis.id == analysis_uuid)
        result = await db.execute(query)
        analysis = result.scalar_one_or_none()

        if not analysis:
            logger.error(f"ConsensusAnalysis {analysis_id} not found")
            return {"status": "error", "message": "Analysis record not found"}

        # Load project with documents
        project_query = (
            select(Project)
            .where(Project.id == analysis.project_id)
            .join(Project.documents)
            .join(ProjectDocument.document)
        )
        project_result = await db.execute(project_query)
        project = project_result.scalar_one_or_none()

        if not project:
            logger.error(f"Project {analysis.project_id} not found")
            await _mark_analysis_failed(db, analysis, "Project not found")
            return {"status": "error", "message": "Project not found"}

        try:
            # Mark analysis as analyzing
            analysis.status = AnalysisStatus.ANALYZING
            analysis.started_at = datetime.now(timezone.utc)
            await db.commit()

            # Merge all project documents into single text
            documents_text = await _merge_project_documents(db, project.id)

            if not documents_text:
                await _mark_analysis_failed(db, analysis, "No document content found")
                await _update_project_status(db, project.id, ProjectStatus.FAILED)
                return {"status": "error", "message": "No document content"}

            logger.info(
                f"Running consensus on {len(documents_text)} chars for project {project.id}"
            )

            # Initialize consensus service with event emission
            consensus_service = ProjectConsensusService(enable_events=True)

            # Start event emitter
            emitter = get_event_emitter()
            await emitter.start()

            try:
                # Run consensus analysis (emits events internally)
                consensus_result, metrics = await consensus_service.run_consensus(
                    project_id=project.id,
                    documents_text=documents_text,
                )

                # Persist results to database
                await _persist_consensus_results(
                    db, analysis, consensus_result, metrics
                )

                # Update analysis status
                analysis.status = AnalysisStatus.CONVERGED
                analysis.converged = True
                analysis.completed_at = datetime.now(timezone.utc)
                await db.commit()

                # Update project status
                await _update_project_status(db, project.id, ProjectStatus.ANALYZED)
                await _update_project_analyzed_at(db, project.id)

                logger.info(
                    f"Consensus complete: {analysis_id} - "
                    f"{metrics.total_rounds} rounds, "
                    f"{metrics.total_tokens} tokens, "
                    f"${metrics.total_cost:.4f}"
                )

                return {
                    "status": "success",
                    "analysis_id": str(analysis_id),
                    "converged": True,
                    "total_rounds": metrics.total_rounds,
                    "milestones": len(consensus_result.final_structure.milestones),
                    "checkpoints": len(consensus_result.final_structure.checkpoints),
                    "versions": len(consensus_result.final_structure.versions),
                    "total_tokens": metrics.total_tokens,
                    "total_cost": metrics.total_cost,
                }

            finally:
                # Close event emitter
                await emitter.close()

        except Exception as e:
            logger.error(
                f"Consensus analysis failed for {analysis_id}: {e}", exc_info=True
            )
            await _mark_analysis_failed(db, analysis, str(e))
            await _update_project_status(db, project.id, ProjectStatus.FAILED)

            return {
                "status": "error",
                "analysis_id": str(analysis_id),
                "error": str(e),
            }


async def _merge_project_documents(db: AsyncSession, project_id: UUID) -> str:
    """Merge all project documents into a single text.

    Args:
        db: Database session
        project_id: Project UUID

    Returns:
        Merged document content
    """
    # Get all documents for project
    query = (
        select(Document)
        .join(ProjectDocument, ProjectDocument.document_id == Document.id)
        .where(ProjectDocument.project_id == project_id)
        .order_by(ProjectDocument.order_index)
    )
    result = await db.execute(query)
    documents = result.scalars().all()

    merged_parts = []
    for doc in documents:
        # Extract text from processed_content (hierarchy extraction output)
        if doc.processed_content:
            # TODO: Implement proper text extraction from hierarchy structure
            # For now, use placeholder
            merged_parts.append(f"# {doc.filename}\n\n[Document content placeholder]")
        else:
            merged_parts.append(f"# {doc.filename}\n\n[Not yet processed]")

    return "\n\n---\n\n".join(merged_parts)


async def _persist_consensus_results(
    db: AsyncSession,
    analysis: ConsensusAnalysis,
    consensus_result: Any,
    metrics: Any,
) -> None:
    """Persist consensus results to database.

    Args:
        db: Database session
        analysis: ConsensusAnalysis record
        consensus_result: ConsensusResult from service
        metrics: ConsensusMetrics from service
    """
    final = consensus_result.final_structure

    # Update analysis aggregates
    analysis.total_rounds = consensus_result.total_rounds
    analysis.final_confidence = final.confidence
    analysis.final_novelty = (
        consensus_result.rounds[-1].novelty_score if consensus_result.rounds else 0.0
    )
    analysis.total_tokens = metrics.total_tokens
    analysis.total_cost = metrics.total_cost
    analysis.milestones_count = len(final.milestones)
    analysis.checkpoints_count = len(final.checkpoints)
    analysis.versions_count = len(final.versions)
    analysis.reasoning = final.reasoning

    # Store full rounds history as JSONB
    analysis.consensus_rounds = {
        "rounds": [
            {
                "round_number": r.round_number,
                "novelty_score": r.novelty_score,
                "confidence": r.extraction.confidence,
            }
            for r in consensus_result.rounds
        ]
    }

    # Persist milestones
    for idx, m in enumerate(final.milestones):
        milestone = Milestone(
            analysis_id=analysis.id,
            title=m.title,
            description=m.description,
            type=MilestoneType(m.type),
            estimated_effort=EffortSize(m.estimated_effort),
            dependencies=m.dependencies,
            created_order=idx,
        )
        db.add(milestone)

    # Persist checkpoints
    for c in final.checkpoints:
        checkpoint = Checkpoint(
            analysis_id=analysis.id,
            milestone_id=None,  # Will link after milestones committed
            title=c.title,
            type=CheckpointType(c.type),
            validation_criteria=c.validation_criteria,
        )
        db.add(checkpoint)

    # Persist versions
    for idx, v in enumerate(final.versions):
        version = Version(
            analysis_id=analysis.id,
            name=v.name,
            release_goal=v.release_goal,
            milestone_titles=v.milestone_titles,
            created_order=idx,
        )
        db.add(version)

    await db.commit()

    # Link checkpoints to milestones by title match
    await _link_checkpoints_to_milestones(db, analysis.id)


async def _link_checkpoints_to_milestones(
    db: AsyncSession, analysis_id: UUID
) -> None:
    """Link checkpoints to milestones by matching milestone_title.

    Args:
        db: Database session
        analysis_id: Analysis UUID
    """
    # Get all milestones for this analysis
    milestone_query = select(Milestone).where(Milestone.analysis_id == analysis_id)
    milestone_result = await db.execute(milestone_query)
    milestones = {m.title: m.id for m in milestone_result.scalars().all()}

    # Get all checkpoints
    checkpoint_query = select(Checkpoint).where(Checkpoint.analysis_id == analysis_id)
    checkpoint_result = await db.execute(checkpoint_query)
    checkpoints = checkpoint_result.scalars().all()

    # Link checkpoints to milestones
    for checkpoint in checkpoints:
        # Find milestone by title from checkpoint extraction data
        # Note: This requires storing milestone_title in Checkpoint model
        # For now, link to first milestone as placeholder
        if milestones:
            checkpoint.milestone_id = list(milestones.values())[0]

    await db.commit()


async def _mark_analysis_failed(
    db: AsyncSession, analysis: ConsensusAnalysis, error_msg: str
) -> None:
    """Mark analysis as failed with error message.

    Args:
        db: Database session
        analysis: ConsensusAnalysis record
        error_msg: Error message
    """
    analysis.status = AnalysisStatus.FAILED
    analysis.error_msg = error_msg
    analysis.completed_at = datetime.now(timezone.utc)
    await db.commit()


async def _update_project_status(
    db: AsyncSession, project_id: UUID, status: ProjectStatus
) -> None:
    """Update project status.

    Args:
        db: Database session
        project_id: Project UUID
        status: New status
    """
    query = select(Project).where(Project.id == project_id)
    result = await db.execute(query)
    project = result.scalar_one_or_none()

    if project:
        project.status = status
        project.updated_at = datetime.now(timezone.utc)
        await db.commit()


async def _update_project_analyzed_at(db: AsyncSession, project_id: UUID) -> None:
    """Update project analyzed_at timestamp.

    Args:
        db: Database session
        project_id: Project UUID
    """
    query = select(Project).where(Project.id == project_id)
    result = await db.execute(query)
    project = result.scalar_one_or_none()

    if project:
        project.analyzed_at = datetime.now(timezone.utc)
        await db.commit()
