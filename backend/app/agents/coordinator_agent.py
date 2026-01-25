"""Backward compatibility wrapper for the CoordinatorAgent.

This module re-exports the CoordinatorAgent from the new coordinator module
for backward compatibility with existing code.

For new code, import directly from app.agents.coordinator:
    from app.agents.coordinator import CoordinatorAgent, PipelineCoordinator
"""

from app.agents.coordinator import (
    CoordinatorAgent,
    CoordinatorResult,
    CoordinatorStatus,
    PipelineCoordinator,
    StageConfig,
    StageResult,
)

__all__ = [
    "CoordinatorAgent",
    "PipelineCoordinator",
    "StageConfig",
    "StageResult",
    "CoordinatorResult",
    "CoordinatorStatus",
]
