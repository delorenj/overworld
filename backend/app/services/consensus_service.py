"""Project Consensus Service for multi-agent milestone extraction.

This service orchestrates EM + PM agents to analyze project documents and
reach consensus on milestones, checkpoints, and version boundaries through
iterative rounds with convergence detection.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.agents.em_agent import EngineeringManagerAgent
from app.agents.pm_agent import ProductManagerAgent
from app.agents.project_notetaker import ProjectNotetakerAgent
from app.schemas.consensus import (
    ConsensusResult,
    ConsensusRound,
    ProjectStructureExtraction,
)
from app.events.emitter import get_event_emitter
from app.events.consensus_events import (
    ConsensusStartedPayload,
    RoundStartedPayload,
    RoundCompletedPayload,
    ConsensusConvergedPayload,
    ConsensusFailedPayload,
)

logger = logging.getLogger(__name__)


@dataclass
class RoundMetrics:
    """Metrics for a single consensus round."""

    round_number: int
    em_tokens: int
    em_cost: float
    pm_tokens: int
    pm_cost: float
    notetaker_tokens: int
    notetaker_cost: float
    execution_time_seconds: float
    novelty_score: float

    @property
    def total_tokens(self) -> int:
        """Total tokens used in this round."""
        return self.em_tokens + self.pm_tokens + self.notetaker_tokens

    @property
    def total_cost(self) -> float:
        """Total cost for this round."""
        return self.em_cost + self.pm_cost + self.notetaker_cost


@dataclass
class ConsensusMetrics:
    """Aggregated metrics across all consensus rounds."""

    total_rounds: int
    total_execution_time_seconds: float
    total_tokens: int
    total_cost: float
    converged: bool
    final_confidence: float
    round_metrics: list[RoundMetrics] = field(default_factory=list)

    @property
    def avg_tokens_per_round(self) -> float:
        """Average tokens per round."""
        return self.total_tokens / self.total_rounds if self.total_rounds > 0 else 0.0

    @property
    def avg_cost_per_round(self) -> float:
        """Average cost per round."""
        return self.total_cost / self.total_rounds if self.total_rounds > 0 else 0.0


class ProjectConsensusService:
    """Orchestrates multi-agent consensus for project structure extraction.

    Workflow:
    1. EM and PM agents analyze documents in parallel (independent perspectives)
    2. ProjectNotetaker reconciles EM + PM analyses into unified structure
    3. Compare extracted structure to previous round (novelty scoring)
    4. Repeat until convergence or max rounds reached

    Convergence Detection:
    - Novelty score measures similarity between rounds (0.0 = identical, 1.0 = completely new)
    - Converged when novelty < threshold for min_stable_rounds consecutive rounds
    - Early stopping if confidence score > confidence_threshold
    """

    def __init__(
        self,
        model: str = "anthropic/claude-sonnet-4",
        novelty_threshold: float = 0.2,
        confidence_threshold: float = 0.85,
        min_rounds: int = 2,
        max_rounds: int = 5,
        min_stable_rounds: int = 2,
        enable_events: bool = True,
    ):
        """Initialize consensus service.

        Args:
            model: OpenRouter model ID for all agents
            novelty_threshold: Convergence threshold (novelty below this = converged)
            confidence_threshold: Early stop if confidence above this
            min_rounds: Minimum rounds before convergence can be detected
            max_rounds: Maximum rounds to execute
            min_stable_rounds: Consecutive low-novelty rounds needed for convergence
            enable_events: Whether to emit Bloodbank events (default True)
        """
        self.model = model
        self.novelty_threshold = novelty_threshold
        self.confidence_threshold = confidence_threshold
        self.min_rounds = min_rounds
        self.max_rounds = max_rounds
        self.min_stable_rounds = min_stable_rounds

        # Initialize agents (stateless, created per analysis)
        self.em_agent_config = {"model": model}
        self.pm_agent_config = {"model": model}
        self.notetaker_config = {"model": model}

        # Initialize event emitter
        self.emitter = get_event_emitter(enabled=enable_events)

        logger.info(
            "ProjectConsensusService initialized: model=%s, novelty_threshold=%.2f, "
            "confidence_threshold=%.2f, min_rounds=%d, max_rounds=%d, events=%s",
            model,
            novelty_threshold,
            confidence_threshold,
            min_rounds,
            max_rounds,
            "enabled" if enable_events else "disabled",
        )

    async def run_consensus(
        self,
        project_id: UUID,
        documents_text: str,
    ) -> tuple[ConsensusResult, ConsensusMetrics]:
        """Run multi-round consensus analysis on project documents.

        Args:
            project_id: UUID of the project being analyzed
            documents_text: Merged content from all project documents

        Returns:
            Tuple of (ConsensusResult, ConsensusMetrics)

        Raises:
            RuntimeError: If consensus fails to converge within max_rounds
        """
        logger.info(
            "Starting consensus analysis: project_id=%s, doc_size=%d chars",
            project_id,
            len(documents_text),
        )

        import time
        start_time = time.time()

        # Emit consensus.started event
        await self.emitter.emit(
            ConsensusStartedPayload(
                project_id=project_id,
                document_count=1,  # Single merged document for now
                document_size_chars=len(documents_text),
                max_rounds=self.max_rounds,
            )
        )

        rounds: list[ConsensusRound] = []
        round_metrics: list[RoundMetrics] = []
        previous_extraction: ProjectStructureExtraction | None = None
        previous_em_analysis: str | None = None
        previous_pm_analysis: str | None = None
        stable_rounds_count = 0  # Track consecutive low-novelty rounds

        for round_num in range(1, self.max_rounds + 1):
            logger.info("Starting consensus round %d/%d", round_num, self.max_rounds)
            round_start = time.time()

            # Emit round.started event
            await self.emitter.emit(
                RoundStartedPayload(
                    project_id=project_id,
                    round_number=round_num,
                    max_rounds=self.max_rounds,
                )
            )

            # Phase 1: Run EM and PM analyses in parallel (independent perspectives)
            em_agent = EngineeringManagerAgent(**self.em_agent_config)
            pm_agent = ProductManagerAgent(**self.pm_agent_config)

            (em_response, em_metrics), (pm_response, pm_metrics) = await asyncio.gather(
                em_agent.analyze_documents(
                    documents_text,
                    round_number=round_num,
                    previous_analysis=previous_em_analysis,
                ),
                pm_agent.analyze_documents(
                    documents_text,
                    round_number=round_num,
                    previous_analysis=previous_pm_analysis,
                ),
            )

            logger.info(
                "Round %d: EM analysis complete (tokens=%d, cost=$%.4f)",
                round_num,
                em_metrics["tokens_used"],
                em_metrics["cost"],
            )
            logger.info(
                "Round %d: PM analysis complete (tokens=%d, cost=$%.4f)",
                round_num,
                pm_metrics["tokens_used"],
                pm_metrics["cost"],
            )

            # Phase 2: Notetaker extracts unified structure from EM + PM analyses
            notetaker = ProjectNotetakerAgent(**self.notetaker_config)
            extraction, notetaker_metrics = await notetaker.extract_project_structure(
                em_response=em_response,
                pm_response=pm_response,
                round_number=round_num,
                previous_extraction=previous_extraction,
            )

            logger.info(
                "Round %d: Notetaker extraction complete "
                "(milestones=%d, confidence=%.2f, tokens=%d, cost=$%.4f)",
                round_num,
                len(extraction.milestones),
                extraction.confidence,
                notetaker_metrics["tokens_used"],
                notetaker_metrics["cost"],
            )

            # Phase 3: Calculate novelty score (similarity to previous round)
            novelty_score = self._calculate_novelty(previous_extraction, extraction)

            logger.info(
                "Round %d: Novelty score=%.3f (threshold=%.3f)",
                round_num,
                novelty_score,
                self.novelty_threshold,
            )

            # Phase 4: Record round results
            round_time = time.time() - round_start
            metrics = RoundMetrics(
                round_number=round_num,
                em_tokens=em_metrics["tokens_used"],
                em_cost=em_metrics["cost"],
                pm_tokens=pm_metrics["tokens_used"],
                pm_cost=pm_metrics["cost"],
                notetaker_tokens=notetaker_metrics["tokens_used"],
                notetaker_cost=notetaker_metrics["cost"],
                execution_time_seconds=round_time,
                novelty_score=novelty_score,
            )
            round_metrics.append(metrics)

            rounds.append(
                ConsensusRound(
                    round_number=round_num,
                    em_response=em_response,
                    pm_response=pm_response,
                    extraction=extraction,
                    novelty_score=novelty_score,
                )
            )

            # Emit round.completed event
            await self.emitter.emit(
                RoundCompletedPayload(
                    project_id=project_id,
                    round_number=round_num,
                    max_rounds=self.max_rounds,
                    em_tokens=metrics.em_tokens,
                    pm_tokens=metrics.pm_tokens,
                    notetaker_tokens=metrics.notetaker_tokens,
                    total_tokens=metrics.total_tokens,
                    total_cost=metrics.total_cost,
                    execution_time_seconds=metrics.execution_time_seconds,
                    novelty_score=novelty_score,
                    confidence=extraction.confidence,
                    milestones_extracted=len(extraction.milestones),
                    checkpoints_extracted=len(extraction.checkpoints),
                    versions_extracted=len(extraction.versions),
                )
            )

            # Phase 5: Check convergence conditions
            converged = False

            # Update stable rounds counter
            if novelty_score < self.novelty_threshold and round_num >= self.min_rounds:
                stable_rounds_count += 1
                logger.info(
                    "Round %d: Low novelty detected (%d/%d consecutive stable rounds)",
                    round_num,
                    stable_rounds_count,
                    self.min_stable_rounds,
                )
            else:
                stable_rounds_count = 0  # Reset counter if novelty spikes

            # Check convergence via stable rounds
            convergence_reason = None
            if stable_rounds_count >= self.min_stable_rounds:
                converged = True
                convergence_reason = "stable_novelty"
                logger.info(
                    "Consensus converged after %d rounds (stable novelty)", round_num
                )

            # Check early stopping via high confidence
            if extraction.confidence >= self.confidence_threshold:
                converged = True
                convergence_reason = "high_confidence"
                logger.info(
                    "Consensus converged after %d rounds (high confidence=%.2f)",
                    round_num,
                    extraction.confidence,
                )

            # Prepare for next round (if needed)
            previous_extraction = extraction
            previous_em_analysis = em_response
            previous_pm_analysis = pm_response

            # Exit if converged
            if converged:
                # Emit consensus.converged event
                total_time = time.time() - start_time
                aggregate_tokens = sum(m.total_tokens for m in round_metrics)
                aggregate_cost = sum(m.total_cost for m in round_metrics)

                await self.emitter.emit(
                    ConsensusConvergedPayload(
                        project_id=project_id,
                        total_rounds=round_num,
                        convergence_reason=convergence_reason,
                        final_confidence=extraction.confidence,
                        final_novelty=novelty_score,
                        total_tokens=aggregate_tokens,
                        total_cost=aggregate_cost,
                        analysis_duration_seconds=total_time,
                        milestones_count=len(extraction.milestones),
                        checkpoints_count=len(extraction.checkpoints),
                        versions_count=len(extraction.versions),
                    )
                )
                break

        # Build final result
        total_time = time.time() - start_time
        final_structure = rounds[-1].extraction

        # Emit consensus.failed if not converged
        if not converged:
            aggregate_tokens = sum(m.total_tokens for m in round_metrics)
            aggregate_cost = sum(m.total_cost for m in round_metrics)

            await self.emitter.emit(
                ConsensusFailedPayload(
                    project_id=project_id,
                    total_rounds=len(rounds),
                    failure_reason="max_rounds_exceeded",
                    final_confidence=final_structure.confidence,
                    final_novelty=rounds[-1].novelty_score,
                    total_tokens=aggregate_tokens,
                    total_cost=aggregate_cost,
                    analysis_duration_seconds=total_time,
                )
            )

            logger.warning(
                "Consensus failed to converge after %d rounds (final_confidence=%.2f, final_novelty=%.3f)",
                len(rounds),
                final_structure.confidence,
                rounds[-1].novelty_score,
            )

        result = ConsensusResult(
            project_id=project_id,
            rounds=rounds,
            final_structure=final_structure,
            converged=converged,
            total_rounds=len(rounds),
            analysis_duration_seconds=total_time,
        )

        # Aggregate metrics
        aggregate_metrics = ConsensusMetrics(
            total_rounds=len(rounds),
            total_execution_time_seconds=total_time,
            total_tokens=sum(m.total_tokens for m in round_metrics),
            total_cost=sum(m.total_cost for m in round_metrics),
            converged=converged,
            final_confidence=final_structure.confidence,
            round_metrics=round_metrics,
        )

        logger.info(
            "Consensus complete: converged=%s, rounds=%d, total_tokens=%d, total_cost=$%.4f",
            converged,
            len(rounds),
            aggregate_metrics.total_tokens,
            aggregate_metrics.total_cost,
        )

        return result, aggregate_metrics

    def _calculate_novelty(
        self,
        previous: ProjectStructureExtraction | None,
        current: ProjectStructureExtraction,
    ) -> float:
        """Calculate novelty score between two extractions.

        Novelty score measures how different the current extraction is from
        the previous one. Higher score = more novel/different.

        Score components:
        - Milestone title changes (added, removed, modified)
        - Checkpoint changes
        - Version boundary changes
        - Confidence delta

        Args:
            previous: Previous round's extraction (None for first round)
            current: Current round's extraction

        Returns:
            Novelty score from 0.0 (identical) to 1.0 (completely different)
        """
        if previous is None:
            return 1.0  # First round is maximally novel

        # Extract milestone titles for comparison
        prev_milestone_titles = {m.title for m in previous.milestones}
        curr_milestone_titles = {m.title for m in current.milestones}

        # Calculate set differences
        added_milestones = curr_milestone_titles - prev_milestone_titles
        removed_milestones = prev_milestone_titles - curr_milestone_titles
        stable_milestones = prev_milestone_titles & curr_milestone_titles

        # Milestone novelty: proportion of changed milestones
        total_milestones = len(prev_milestone_titles | curr_milestone_titles)
        if total_milestones == 0:
            milestone_novelty = 0.0
        else:
            milestone_novelty = (len(added_milestones) + len(removed_milestones)) / total_milestones

        # Checkpoint novelty
        prev_checkpoint_titles = {c.title for c in previous.checkpoints}
        curr_checkpoint_titles = {c.title for c in current.checkpoints}
        total_checkpoints = len(prev_checkpoint_titles | curr_checkpoint_titles)
        if total_checkpoints == 0:
            checkpoint_novelty = 0.0
        else:
            added_checkpoints = curr_checkpoint_titles - prev_checkpoint_titles
            removed_checkpoints = prev_checkpoint_titles - curr_checkpoint_titles
            checkpoint_novelty = (len(added_checkpoints) + len(removed_checkpoints)) / total_checkpoints

        # Version novelty
        prev_version_names = {v.name for v in previous.versions}
        curr_version_names = {v.name for v in current.versions}
        total_versions = len(prev_version_names | curr_version_names)
        if total_versions == 0:
            version_novelty = 0.0
        else:
            added_versions = curr_version_names - prev_version_names
            removed_versions = prev_version_names - curr_version_names
            version_novelty = (len(added_versions) + len(removed_versions)) / total_versions

        # Confidence delta (normalized)
        confidence_delta = abs(current.confidence - previous.confidence)

        # Weighted average (milestones are most important)
        novelty = (
            0.5 * milestone_novelty +
            0.2 * checkpoint_novelty +
            0.2 * version_novelty +
            0.1 * confidence_delta
        )

        return min(novelty, 1.0)  # Cap at 1.0
