"""Consensus workflow event schemas for Bloodbank integration.

These events track progress through multi-round EM/PM consensus analysis.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class BaseConsensusEvent(BaseModel):
    """Base event for all consensus workflow events."""

    event_type: str
    project_id: UUID
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConsensusStartedPayload(BaseConsensusEvent):
    """Emitted when consensus analysis begins."""

    event_type: str = "consensus.started"
    document_count: int
    document_size_chars: int
    max_rounds: int


class RoundStartedPayload(BaseConsensusEvent):
    """Emitted when a consensus round begins."""

    event_type: str = "consensus.round.started"
    round_number: int
    max_rounds: int


class RoundCompletedPayload(BaseConsensusEvent):
    """Emitted when a consensus round completes."""

    event_type: str = "consensus.round.completed"
    round_number: int
    max_rounds: int
    em_tokens: int
    pm_tokens: int
    notetaker_tokens: int
    total_tokens: int
    total_cost: float
    execution_time_seconds: float
    novelty_score: float
    confidence: float
    milestones_extracted: int
    checkpoints_extracted: int
    versions_extracted: int


class ConsensusConvergedPayload(BaseConsensusEvent):
    """Emitted when consensus is reached."""

    event_type: str = "consensus.converged"
    total_rounds: int
    convergence_reason: str  # "stable_novelty" or "high_confidence"
    final_confidence: float
    final_novelty: float
    total_tokens: int
    total_cost: float
    analysis_duration_seconds: float
    milestones_count: int
    checkpoints_count: int
    versions_count: int


class ConsensusFailedPayload(BaseConsensusEvent):
    """Emitted when consensus fails to converge."""

    event_type: str = "consensus.failed"
    total_rounds: int
    failure_reason: str  # "max_rounds_exceeded" or error message
    final_confidence: float
    final_novelty: float
    total_tokens: int
    total_cost: float
    analysis_duration_seconds: float
    error_details: dict[str, Any] | None = None
