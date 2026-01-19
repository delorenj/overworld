"""Coordinator Agent for multi-agent pipeline orchestration."""

from typing import Dict

from app.agents.artist_agent import ArtistAgent
from app.agents.icon_agent import IconAgent
from app.agents.parser_agent import ParserAgent
from app.agents.road_agent import RoadAgent
from app.agents.base_agent import AgentResult, BaseAgent, JobContext


class CoordinatorAgent(BaseAgent):
    """Orchestrates the full multi-agent pipeline."""

    def __init__(self):
        super().__init__()
        self.pipeline_order = [
            ("parser", ParserAgent),
            ("artist", ArtistAgent),
            ("road", RoadAgent),
            ("icon", IconAgent),
        ]

    async def execute(self, context: JobContext) -> AgentResult:
        """Execute full pipeline with sequential agent coordination."""
        try:
            pipeline_results = {}

            for stage_name, agent_class in self.pipeline_order:
                agent = agent_class()

                result = await agent.run(context)

                if not result.success:
                    return AgentResult(
                        success=False,
                        error=f"Stage '{stage_name}' failed: {result.error}",
                    )

                context.save_checkpoint(stage_name, result.data if result.data else {})
                pipeline_results[stage_name] = result.data if result.data else {}

            # Collect final map data
            final_map_data = self._assemble_final_map(
                pipeline_results,
                context.theme,
                context.hierarchy,
            )

            return AgentResult(
                success=True,
                data=final_map_data,
            )

        except Exception as e:
            return AgentResult(
                success=False,
                error=f"Coordinator failed: {str(e)}",
            )

    def _assemble_final_map(
        self,
        pipeline_results: Dict[str, dict],
        theme: Dict[str, any],
        hierarchy: Dict[str, any],
    ) -> Dict[str, any]:
        """Assemble final map data from all agent outputs."""

        artist_data = pipeline_results.get("artist", {})
        road_data = pipeline_results.get("road", {})
        icon_data = pipeline_results.get("icon", {})

        return {
            "theme": artist_data.get("theme_id", "smb3"),
            "road": road_data,
            "milestones": icon_data.get("icons", []),
            "metadata": {
                "road_arc_length": road_data.get("arc_length", 0),
                "milestone_count": icon_data.get("icon_count", 0),
            },
        }
