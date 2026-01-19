"""Base agent framework for multi-agent pipeline."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from uuid import UUID

from openrouter import OpenRouter as AsyncOpenRouter

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class JobContext:
    """Context passed to each agent during execution."""

    job_id: int
    user_id: int
    document_url: str
    hierarchy: Dict[str, Any]
    theme: Dict[str, Any]
    options: Dict[str, Any]
    agent_state: Dict[str, Any] = field(default_factory=dict)

    def get_checkpoint(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Get checkpoint for specific agent."""
        return self.agent_state.get(agent_name)

    def save_checkpoint(self, agent_name: str, state: Dict[str, Any]) -> None:
        """Save checkpoint for specific agent."""
        self.agent_state[agent_name] = state


@dataclass
class AgentResult:
    """Result returned by each agent."""

    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: Optional[int] = None
    tokens_used: Optional[int] = None


class BaseAgent(ABC):
    """Base agent class for multi-agent pipeline."""

    def __init__(self):
        self.name: str = self.__class__.__name__
        self.client: Optional[AsyncOpenRouter] = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize OpenRouter client for LLM calls."""
        if settings.OPENROUTER_API_KEY:
            self.client = AsyncOpenRouter(
                api_key=settings.OPENROUTER_API_KEY,
            )
        else:
            logger.warning(f"{self.name}: No OpenRouter API key configured")

    @abstractmethod
    async def execute(self, context: JobContext) -> AgentResult:
        """Execute agent's primary logic."""
        pass

    async def run(self, context: JobContext) -> AgentResult:
        """Run agent with logging and error handling."""
        import time

        logger.info(
            f'{{"timestamp": "{time.strftime("%Y-%m-%dT%H:%M:%SZ")}", '
            f'"job_id": {context.job_id}, '
            f'"agent": "{self.name}", '
            f'"stage": "starting", '
            f'"elapsed_ms": 0}}'
        )

        start_time = time.time()

        try:
            result = await self.execute(context)
            execution_time_ms = int((time.time() - start_time) * 1000)
            result.execution_time_ms = execution_time_ms

            logger.info(
                f'{{"timestamp": "{time.strftime("%Y-%m-%dT%H:%M:%SZ")}", '
                f'"job_id": {context.job_id}, '
                f'"agent": "{self.name}", '
                f'"stage": "completed", '
                f'"success": {str(result.success).lower()}, '
                f'"elapsed_ms": {execution_time_ms}}}'
            )

            if result.error:
                logger.error(f"{self.name}: {result.error}")

            return result

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)

            logger.error(
                f'{{"timestamp": "{time.strftime("%Y-%m-%dT%H:%M:%SZ")}", '
                f'"job_id": {context.job_id}, '
                f'"agent": "{self.name}", '
                f'"stage": "failed", '
                f'"error": "{str(e)}", '
                f'"elapsed_ms": {execution_time_ms}}}'
            )

            return AgentResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time_ms,
            )

    async def call_llm(
        self,
        messages: list,
        model: str = "openai/gpt-4",
        temperature: float = 0.7,
    ) -> str:
        """Call LLM via OpenRouter with error handling and retry logic."""
        if not self.client:
            raise RuntimeError("OpenRouter client not initialized")

        try:
            completion = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )

            return completion.choices[0].message.content

        except Exception as e:
            error_str = str(e)

            if "429" in error_str or "rate limit" in error_str.lower():
                logger.warning(f"{self.name}: Rate limit hit, will retry")
                raise
            else:
                logger.error(f"{self.name}: LLM call failed: {e}")
                raise
