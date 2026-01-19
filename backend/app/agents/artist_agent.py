"""Artist Agent for map theme configuration."""

from typing import Dict

from app.agents.base_agent import AgentResult, BaseAgent, JobContext


class ArtistAgent(BaseAgent):
    """Generates theme configuration for map rendering."""

    async def execute(self, context: JobContext) -> AgentResult:
        """Generate theme configuration based on context."""
        theme_preference = context.theme.get("theme_id", "smb3")

        try:
            if theme_preference != "smb3":
                return AgentResult(
                    success=False,
                    error=f"Only 'smb3' theme supported in MVP (requested: {theme_preference})",
                )

            theme_config = {
                "theme_id": "smb3",
                "colors": {
                    "road": "#D2691E",
                    "bg": "#6B8CFF",
                    "milestone": "#FFD700",
                },
                "textures": {
                    "road": "pixelated-brown",
                    "milestone": "numbered-circle",
                },
                "icon_set": "8bit-sprites",
            }

            return AgentResult(
                success=True,
                data=theme_config,
            )

        except Exception as e:
            return AgentResult(
                success=False,
                error=f"Artist failed: {str(e)}",
            )
