"""Icon Placer Agent for milestone placement."""

from typing import List, Dict

from app.agents.base_agent import AgentResult, BaseAgent, JobContext


class IconAgent(BaseAgent):
    """Places milestones as numbered circles along the road."""

    async def execute(self, context: JobContext) -> AgentResult:
        """Place milestones as numbered circles along the road."""
        road_data = context.agent_state.get("road", {}).get("data", {})
        parser_data = context.agent_state.get("parser", {}).get("data", {})
        coordinates = road_data.get("coordinates", [])
        milestones = parser_data.get("milestones", [])

        try:
            if not coordinates or not milestones:
                return AgentResult(
                    success=False,
                    error="No road coordinates or milestones available",
                )

            icon_data = []

            for i, milestone in enumerate(milestones, 1):
                milestone_id = milestone.get("id", f"m{i}")
                milestone_title = milestone.get("title", f"Milestone {i}")

                if i <= len(coordinates):
                    pos = coordinates[min(i, len(coordinates) - 1)]
                    x, y = pos["x"], pos["y"]

                    icon = {
                        "number": i,
                        "id": milestone_id,
                        "label": milestone_title,
                        "pos": {"x": int(x), "y": int(y)},
                    }
                    icon_data.append(icon)
                else:
                    return AgentResult(
                        success=False,
                        error=f"Not enough road coordinates for milestone {i}",
                    )

            result_data = {
                "icons": icon_data,
                "icon_count": len(icon_data),
            }

            return AgentResult(
                success=True,
                data=result_data,
            )

        except Exception as e:
            return AgentResult(
                success=False,
                error=f"Icon placement failed: {str(e)}",
            )
