"""Project Notetaker Agent for extracting structured milestones and checkpoints.

This specialized notetaker analyzes EM + PM responses to extract a unified
project structure with milestones, checkpoints, dependencies, and version boundaries.
"""

import logging
from typing import Any

from theboard.agents.base import create_agno_agent, extract_agno_metrics
from agno.agent import Agent

from app.schemas.consensus import (
    ProjectStructureExtraction,
    MilestoneExtraction,
    CheckpointExtraction,
    VersionExtraction,
)

logger = logging.getLogger(__name__)


class ProjectNotetakerAgent:
    """Extracts structured project data from EM/PM consensus discussion.

    This agent reconciles technical (EM) and product (PM) perspectives into
    a unified project structure suitable for map generation.
    """

    def __init__(
        self,
        model: str = "anthropic/claude-sonnet-4"
    ):
        """Initialize Project Notetaker agent.

        Args:
            model: OpenRouter model ID (default: Claude Sonnet 4)
        """
        self.name = "Project Notetaker"
        self.model = model

        # Define notetaker-specific instructions
        self.instructions = [
            "Extract structured project milestones from EM and PM analyses",
            "Reconcile technical (EM) and product (PM) perspectives into unified structure",
            "Identify major deliverables that combine technical+product value",
            "Detect dependencies between milestones (technical prerequisites)",
            "Extract validation checkpoints (PoCs, demos, tests)",
            "Propose version boundaries (MVP, v1.0, v2.0) grouping milestones",
            "Assign effort estimates (S/M/L/XL) considering both perspectives",
            "Be precise and structured in your extractions",
            "Focus on milestone-level granularity (not individual tasks)",
            "Ensure extracted structure is actionable and complete",
        ]

        self._agent_config = {
            "name": self.name,
            "role": "Extract structured project structure from consensus discussion",
            "expertise": (
                "Identifying deliverables, validation points, dependencies, "
                "reconciling technical and product perspectives, effort estimation"
            ),
            "instructions": self.instructions,
            "model_id": model,
            "agent_type": "notetaker",
        }

        logger.info("Created ProjectNotetakerAgent (model=%s)", model)

    async def extract_project_structure(
        self,
        em_response: str,
        pm_response: str,
        round_number: int,
        previous_extraction: ProjectStructureExtraction | None = None
    ) -> tuple[ProjectStructureExtraction, dict[str, Any]]:
        """Extract structured milestones/checkpoints from EM/PM responses.

        Args:
            em_response: Engineering Manager's analysis
            pm_response: Product Manager's analysis
            round_number: Current consensus round
            previous_extraction: Previous round's extraction (for delta tracking)

        Returns:
            Tuple of (ProjectStructureExtraction, metrics_dict)

        Raises:
            RuntimeError: If extraction fails
        """
        logger.info(
            "Extracting project structure: round=%d, em_size=%d, pm_size=%d",
            round_number,
            len(em_response),
            len(pm_response)
        )

        try:
            # Create agent with structured output schema
            # Agno automatically validates response against ProjectStructureExtraction
            extractor = create_agno_agent(
                **self._agent_config,
                output_schema=ProjectStructureExtraction,
                debug_mode=False,
            )

            # Build extraction prompt
            prompt = self._build_prompt(
                em_response,
                pm_response,
                round_number,
                previous_extraction
            )

            # Run extraction
            response = extractor.run(prompt)

            # Extract metrics
            metrics = extract_agno_metrics(extractor)

            # Agno returns validated ProjectStructureExtraction
            # response.content might be the structured object or string JSON
            if isinstance(response.content, ProjectStructureExtraction):
                extraction = response.content
            elif isinstance(response.content, str):
                # Parse JSON string to Pydantic model
                import json
                extraction = ProjectStructureExtraction.model_validate_json(response.content)
            else:
                # Try direct access if it's a dict
                extraction = ProjectStructureExtraction.model_validate(response.content)

            logger.info(
                "Extraction complete: milestones=%d, checkpoints=%d, confidence=%.2f, tokens=%d",
                len(extraction.milestones),
                len(extraction.checkpoints),
                extraction.confidence,
                metrics["tokens_used"]
            )

            return extraction, metrics

        except Exception as e:
            logger.error("Extraction failed: %s", str(e), exc_info=True)
            raise RuntimeError(f"Project structure extraction failed: {e}") from e

    def _build_prompt(
        self,
        em_response: str,
        pm_response: str,
        round_number: int,
        previous_extraction: ProjectStructureExtraction | None
    ) -> str:
        """Build extraction prompt for notetaker agent."""
        prompt_parts = [
            f"# Project Structure Extraction - Round {round_number}\n",
            "## Your Task",
            "Extract structured project milestones, checkpoints, and version boundaries",
            "from the EM and PM analyses below.",
            "Reconcile technical and product perspectives into a unified structure.\n",
            "## Engineering Manager Analysis",
            "```markdown",
            em_response[:10000],  # Limit to avoid token overflow
            "```\n",
            "## Product Manager Analysis",
            "```markdown",
            pm_response[:10000],  # Limit to avoid token overflow
            "```\n",
        ]

        # Add delta context for subsequent rounds
        if previous_extraction:
            prompt_parts.extend([
                "## Previous Extraction (Round {})".format(round_number - 1),
                f"- Milestones: {len(previous_extraction.milestones)}",
                f"- Checkpoints: {len(previous_extraction.checkpoints)}",
                f"- Versions: {len(previous_extraction.versions)}",
                f"- Confidence: {previous_extraction.confidence:.2f}\n",
                "## Delta Instructions",
                "Build upon previous extraction. Focus on:",
                "- Refining milestone definitions based on new insights",
                "- Adding missing dependencies identified by EM/PM",
                "- Adjusting effort estimates if new complexity discovered",
                "- Resolving conflicts between technical and product priorities\n",
            ])

        prompt_parts.extend([
            "## Extraction Guidelines\n",
            "### Milestones",
            "- Combine related features into cohesive deliverables",
            "- Each milestone should be independently valuable",
            "- Type: 'technical' (infrastructure), 'product' (user-facing), or 'hybrid'",
            "- Effort: S (1-3 days), M (1-2 weeks), L (2-4 weeks), XL (4+ weeks)",
            "- Dependencies: List prerequisite milestone titles\n",
            "### Checkpoints",
            "- Validation points within milestones (PoC, demo, test)",
            "- Must have measurable validation criteria",
            "- Link to parent milestone by title\n",
            "### Versions",
            "- Group milestones into shippable releases",
            "- MVP: Minimum viable product (first user validation)",
            "- v1.0: Feature-complete first release",
            "- v2.0+: Enhancements and scale features\n",
            "### Confidence Score",
            "- 0.8-1.0: High confidence, clear consensus",
            "- 0.5-0.8: Moderate confidence, some ambiguity",
            "- 0.0-0.5: Low confidence, needs more rounds\n",
            "### Reasoning",
            "- Brief explanation of extraction decisions",
            "- Note any conflicts between EM/PM perspectives",
            "- Explain version boundaries\n",
            "## Output",
            "Return structured ProjectStructureExtraction matching the schema.",
            "Be precise, actionable, and comprehensive.",
        ])

        return "\n".join(prompt_parts)

    def get_agent_config(self) -> dict[str, Any]:
        """Get agent configuration for debugging/logging."""
        return {
            "name": self.name,
            "model": self.model,
            "instructions_count": len(self.instructions),
            "output_schema": "ProjectStructureExtraction",
        }
