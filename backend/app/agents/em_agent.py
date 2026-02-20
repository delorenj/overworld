"""Engineering Manager Agent for technical project analysis.

This agent analyzes project documents from a technical feasibility perspective,
identifying architectural milestones, technical dependencies, risks, and
complexity estimates.
"""

import logging
from typing import Any

from theboard.agents.base import create_agno_agent, extract_agno_metrics
from agno.agent import Agent

logger = logging.getLogger(__name__)


class EngineeringManagerAgent:
    """EM perspective for project structure consensus.

    Focus Areas:
    - Technical architecture and system components
    - Integration points and dependencies
    - Technical risk identification
    - Effort/complexity estimation
    - Infrastructure and DevOps requirements
    """

    def __init__(
        self,
        model: str = "anthropic/claude-sonnet-4",
        session_id: str | None = None
    ):
        """Initialize Engineering Manager agent.

        Args:
            model: OpenRouter model ID (default: Claude Sonnet 4)
            session_id: Optional session ID for conversation persistence
        """
        self.name = "Engineering Manager"
        self.model = model
        self.session_id = session_id

        # Define EM-specific instructions
        self.instructions = [
            "Analyze project documents from a technical architecture perspective",
            "Identify major technical milestones (core systems, integrations, infrastructure)",
            "Focus on architectural boundaries and component relationships",
            "Detect technical dependencies (must-have-before relationships)",
            "Flag technical risks: unknowns, third-party dependencies, scalability concerns",
            "Estimate complexity using S/M/L/XL scale based on technical factors",
            "Suggest technical validation checkpoints (PoCs, integration tests, load tests)",
            "Consider DevOps and deployment requirements as separate milestones",
            "Prioritize technical debt prevention and maintainability",
            "Think in terms of: What needs to be built? How complex? What are the risks?",
        ]

        # Create Agno agent (will be instantiated per analysis)
        self._agent_config = {
            "name": self.name,
            "role": "Technical Feasibility Analyst and Architecture Planner",
            "expertise": (
                "Software architecture, system design, technical risk assessment, "
                "dependency mapping, effort estimation, and infrastructure planning"
            ),
            "instructions": self.instructions,
            "model_id": model,
            "agent_type": "worker",
            "session_id": session_id,
        }

        logger.info(
            "Created EngineeringManagerAgent (model=%s, session=%s)",
            model,
            session_id or "stateless"
        )

    async def analyze_documents(
        self,
        documents_text: str,
        round_number: int = 1,
        previous_analysis: str | None = None
    ) -> tuple[str, dict[str, Any]]:
        """Analyze project documents from technical perspective.

        Args:
            documents_text: Merged content from all project documents
            round_number: Current analysis round (for context)
            previous_analysis: Previous round's analysis (for delta tracking)

        Returns:
            Tuple of (analysis_text, metrics_dict)
        """
        logger.info(
            "EM analyzing documents: round=%d, doc_size=%d chars",
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
            "EM analysis complete: tokens=%d, cost=$%.4f",
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
        """Build analysis prompt for EM agent."""
        prompt_parts = [
            f"# Engineering Manager Analysis - Round {round_number}\n",
            "## Your Role",
            "You are the Engineering Manager analyzing these project documents.",
            "Focus on technical feasibility, architecture, and engineering concerns.\n",
            "## Project Documents",
            "```",
            documents_text[:15000],  # Limit to ~15K chars to avoid token overflow
            "```\n",
            "## Your Analysis Task",
            "Analyze these documents and identify:",
            "1. **Technical Milestones**: Major architectural deliverables",
            "   - Core systems (auth, data layer, API, frontend)",
            "   - Integration points (third-party APIs, services)",
            "   - Infrastructure (deployment, monitoring, CI/CD)",
            "2. **Technical Dependencies**: What must be built first?",
            "3. **Technical Risks**: Unknowns, complexity hotspots, third-party concerns",
            "4. **Complexity Estimates**: S/M/L/XL for each milestone",
            "5. **Validation Checkpoints**: PoCs, integration tests, performance tests\n",
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
                "- Refining milestone definitions",
                "- Resolving ambiguities from last round",
                "- Adding missing technical considerations",
                "- Adjusting estimates based on deeper understanding\n",
            ])

        prompt_parts.extend([
            "## Output Format",
            "Provide your analysis as structured markdown:",
            "- Use clear headings (## Milestones, ## Dependencies, ## Risks)",
            "- Be specific and concise",
            "- Focus on engineering concerns (not product/UX)",
            "- Estimate complexity realistically based on technical factors",
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
