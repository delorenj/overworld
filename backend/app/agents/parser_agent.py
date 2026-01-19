"""Parser Agent for document hierarchy validation."""

from typing import Dict, List, Set

from app.agents.base_agent import AgentResult, BaseAgent, JobContext


class ParserAgent(BaseAgent):
    """Validates and analyzes document hierarchy from STORY-002."""

    async def execute(self, context: JobContext) -> AgentResult:
        """Validate and parse document hierarchy."""
        hierarchy = context.hierarchy
        milestones = []
        levels: Set[int] = set()

        try:
            if not hierarchy:
                return AgentResult(
                    success=False,
                    error="No hierarchy data provided",
                )

            if "L0" in hierarchy:
                root = hierarchy["L0"]
                if root:
                    milestones.append(
                        {
                            "level": 0,
                            "id": "root",
                            "title": root.get("title", "Project"),
                            "pos": 0,
                        }
                    )

            if "L1" in hierarchy and isinstance(hierarchy["L1"], list):
                for i, milestone in enumerate(hierarchy["L1"], 51):
                    if milestone:
                        data = {
                            "level": 1,
                            "id": milestone.get("id", f"m{i}"),
                            "title": milestone.get("title", f"Milestone {i}"),
                            "pos": i + 1,
                        }
                        milestones.append(data)
                        levels.add(1)

            if "L2" in hierarchy and isinstance(hierarchy["L2"], list):
                for i, group in enumerate(hierarchy["L2"], 51):
                    if isinstance(group, dict) and "id" in group:
                        data = {
                            "level": 2,
                            "id": group.get("id", f"e{i}"),
                            "title": group.get("title", f"Epic {i}"),
                            "pos": i + 51,
                        }
                        milestones.append(data)
                        levels.add(2)

            if "L3" in hierarchy and isinstance(hierarchy["L3"], list):
                for i, task in enumerate(hierarchy["L3"], 51):
                    if isinstance(task, dict) and "id" in task:
                        data = {
                            "level": 3,
                            "id": task.get("id", f"t{i}"),
                            "title": task.get("title", f"Task {i}"),
                            "pos": i + 101,
                        }
                        milestones.append(data)
                        levels.add(3)

            if "L4" in hierarchy and isinstance(hierarchy["L4"], list):
                for i, subtask in enumerate(hierarchy["L4"], 51):
                    if isinstance(subtask, dict) and "id" in subtask:
                        data = {
                            "level": 4,
                            "id": subtask.get("id", f"st{i}"),
                            "title": subtask.get("title", f"Subtask {i}"),
                            "pos": i + 151,
                        }
                        milestones.append(data)
                        levels.add(4)

            if not any(m["level"] == 1 for m in milestones):
                return AgentResult(
                    success=False,
                    error="At least 1 L1 milestone required",
                )

            if len(milestones) > 50:
                return AgentResult(
                    success=False,
                    error=f"Too many milestones: {len(milestones)} (max 50 for MVP)",
                )

            milestones.sort(key=lambda m: m["pos"])

            result_data = {
                "valid": True,
                "milestone_count": len(milestones),
                "levels": sorted(list(levels)),
                "milestones": milestones,
                "statistics": {
                    "total": len(milestones),
                    "by_level": {
                        level: sum(1 for m in milestones if m["level"] == level) for level in levels
                    },
                },
            }

            return AgentResult(
                success=True,
                data=result_data,
            )

        except Exception as e:
            return AgentResult(
                success=False,
                error=f"Parser failed: {str(e)}",
            )
