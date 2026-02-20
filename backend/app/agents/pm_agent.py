"""Product Manager Agent for user value and MVP analysis.

This agent analyzes project documents from a product/user perspective,
identifying user-facing milestones, MVP boundaries, feature prioritization,
and release strategy.
"""

import logging
from typing import Any

from theboard.agents.base import create_agno_agent, extract_agno_metrics
from agno.agent import Agent

logger = logging.getLogger(__name__)


class ProductManagerAgent:
    """PM perspective for project structure consensus.

    Focus Areas:
    - User-facing features and user value
    - MVP definition and scope boundaries
    - Feature prioritization by user impact
    - Version/release planning
    - User validation checkpoints
    """

    def __init__(
        self,
        model: str = "anthropic/claude-sonnet-4",
        session_id: str | None = None
    ):
        """Initialize Product Manager agent.

        Args:
            model: OpenRouter model ID (default: Claude Sonnet 4)
            session_id: Optional session ID for conversation persistence
        """
        self.name = "Product Manager"
        self.model = model
        self.session_id = session_id

        # Define PM-specific instructions
        self.instructions = [
            "Analyze project documents from a product and user value perspective",
            "Identify user-facing milestones (feature sets with clear user benefits)",
            "Define MVP boundaries: minimum features needed for user validation",
            "Prioritize features by user impact and business value",
            "Think in terms of user journeys and workflows",
            "Suggest version markers (MVP, v1.0, v2.0) based on feature completeness",
            "Propose user validation checkpoints (usability tests, beta releases)",
            "Consider go-to-market timing and competitive positioning",
            "Balance 'must-have' vs 'nice-to-have' features ruthlessly",
            "Think in terms of: What delivers user value? What can we defer?",
        ]

        # Create Agno agent (will be instantiated per analysis)
        self._agent_config = {
            "name": self.name,
            "role": "Product Strategy and MVP Definition Expert",
            "expertise": (
                "User value assessment, feature prioritization, MVP scoping, "
                "release planning, user validation, and product-market fit"
            ),
            "instructions": self.instructions,
            "model_id": model,
            "agent_type": "worker",
            "session_id": session_id,
        }

        logger.info(
            "Created ProductManagerAgent (model=%s, session=%s)",
            model,
            session_id or "stateless"
        )

    async def analyze_documents(
        self,
        documents_text: str,
        round_number: int = 1,
        previous_analysis: str | None = None
    ) -> tuple[str, dict[str, Any]]:
        """Analyze project documents from product perspective.

        Args:
            documents_text: Merged content from all project documents
            round_number: Current analysis round (for context)
            previous_analysis: Previous round's analysis (for delta tracking)

        Returns:
            Tuple of (analysis_text, metrics_dict)
        """
        logger.info(
            "PM analyzing documents: round=%d, doc_size=%d chars",
            round_number,
            len(documents_text)
        )

        # Create agent instance for this analysis
        agent = create_agno_agent(**self._agent_config)

        # Build analysis prompt
        prompt = self._build_prompt(
            documents_text,
            round_number,
            previous_analysis
        )

        # Run agent analysis
        response = agent.run(prompt)

        # Extract metrics
        metrics = extract_agno_metrics(agent)

        logger.info(
            "PM analysis complete: tokens=%d, cost=$%.4f",
            metrics["tokens_used"],
            metrics["cost"]
        )

        return response.content, metrics

    def _build_prompt(
        self,
        documents_text: str,
        round_number: int,
        previous_analysis: str | None
    ) -> str:
        """Build analysis prompt for PM agent."""
        prompt_parts = [
            f"# Product Manager Analysis - Round {round_number}\n",
            "## Your Role",
            "You are the Product Manager analyzing these project documents.",
            "Focus on user value, MVP definition, and feature prioritization.\n",
            "## Project Documents",
            "```",
            documents_text[:15000],  # Limit to ~15K chars to avoid token overflow
            "```\n",
            "## Your Analysis Task",
            "Analyze these documents and identify:",
            "1. **User-Facing Milestones**: Feature sets with clear user benefits",
            "   - What can users do after this milestone?",
            "   - How does it improve their workflow?",
            "   - Is it 'must-have' or 'nice-to-have'?",
            "2. **MVP Boundaries**: Minimum features for launch",
            "   - What's the core user journey we need to support?",
            "   - What can we defer to v1.1+?",
            "3. **Feature Prioritization**: Order by user impact",
            "4. **Version Markers**: Group milestones into releases",
            "   - MVP (minimum viable product)",
            "   - v1.0 (feature-complete first version)",
            "   - v2.0+ (enhancements and scale features)",
            "5. **User Validation Checkpoints**: When to test with users?\n",
        ]

        # Add delta context for subsequent rounds
        if previous_analysis:
            prompt_parts.extend([
                "## Previous Analysis (Round {})".format(round_number - 1),
                "```",
                previous_analysis[:5000],  # Limit previous context
                "```\n",
                "## Delta Instructions",
                "Build upon your previous analysis. Focus on:",
                "- Refining MVP scope based on technical constraints (from EM)",
                "- Adjusting priorities based on feasibility",
                "- Clarifying user value propositions",
                "- Resolving feature vs complexity trade-offs\n",
            ])

        prompt_parts.extend([
            "## Output Format",
            "Provide your analysis as structured markdown:",
            "- Use clear headings (## Milestones, ## MVP Scope, ## Versions)",
            "- Be specific about user value (not technical details)",
            "- Prioritize ruthlessly (fewer high-value features > many low-value)",
            "- Think like a user: What would delight them?",
        ])

        return "\n".join(prompt_parts)

    def get_agent_config(self) -> dict[str, Any]:
        """Get agent configuration for debugging/logging."""
        return {
            "name": self.name,
            "model": self.model,
            "session_id": self.session_id,
            "instructions_count": len(self.instructions),
        }
