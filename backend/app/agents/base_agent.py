"""Base agent framework for multi-agent pipeline.

This module provides backward-compatible exports for the legacy agent interface,
while the new enhanced agent framework is available in app.agents.base.

Legacy imports (maintained for backward compatibility):
    - JobContext: Legacy context dataclass
    - AgentResult: Legacy result dataclass
    - BaseAgent: Legacy base agent class

New imports (recommended for new code):
    - app.agents.base: Enhanced BaseAgent with typed I/O, lifecycle hooks
    - app.agents.messages: Pydantic message types for agent communication
    - app.agents.llm_client: OpenRouter client with streaming, rate limiting
    - app.agents.pipeline: Pipeline state machine with persistence
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from app.agents.llm_client import (
    ChatMessage,
    OpenRouterClient,
    get_llm_client,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class JobContext:
    """Context passed to each agent during execution.

    This is the legacy context class maintained for backward compatibility.
    For new agents, consider using ExecutionContext from app.agents.base.

    Attributes:
        job_id: Generation job ID
        user_id: User ID who initiated the job
        document_url: URL of the source document
        hierarchy: Parsed document hierarchy
        theme: Theme configuration
        options: Generation options
        agent_state: Checkpointed state from previous agents
    """

    job_id: int
    user_id: int
    document_url: str
    hierarchy: dict[str, Any]
    theme: dict[str, Any]
    options: dict[str, Any]
    agent_state: dict[str, Any] = field(default_factory=dict)

    def get_checkpoint(self, agent_name: str) -> Optional[dict[str, Any]]:
        """Get checkpoint for specific agent.

        Args:
            agent_name: Name of the agent

        Returns:
            Checkpoint data if exists, None otherwise
        """
        return self.agent_state.get(agent_name)

    def save_checkpoint(self, agent_name: str, state: dict[str, Any]) -> None:
        """Save checkpoint for specific agent.

        Args:
            agent_name: Name of the agent
            state: State data to checkpoint
        """
        self.agent_state[agent_name] = state


@dataclass
class AgentResult:
    """Result returned by each agent.

    This is the legacy result class maintained for backward compatibility.
    For new agents, consider using typed AgentOutput subclasses from app.agents.base.

    Attributes:
        success: Whether the agent completed successfully
        data: Output data from the agent
        error: Error message if failed
        execution_time_ms: Time taken to execute in milliseconds
        tokens_used: Number of LLM tokens consumed
    """

    success: bool
    data: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: Optional[int] = None
    tokens_used: Optional[int] = None


class BaseAgent(ABC):
    """Base agent class for multi-agent pipeline.

    This is the legacy base agent maintained for backward compatibility.
    For new agents, consider using the enhanced BaseAgent from app.agents.base
    which provides:
    - Typed input/output through generics
    - Lifecycle hooks (on_start, on_complete, on_error)
    - Progress reporting callbacks
    - Better LLM integration with the OpenRouter client

    Usage:
        class MyAgent(BaseAgent):
            async def execute(self, context: JobContext) -> AgentResult:
                # Your processing logic here
                return AgentResult(success=True, data={...})
    """

    def __init__(self):
        """Initialize the agent."""
        self.name: str = self.__class__.__name__
        self._llm_client: Optional[OpenRouterClient] = None
        self._tokens_used: int = 0

    @property
    def llm_client(self) -> OpenRouterClient:
        """Get the LLM client, initializing if needed."""
        if self._llm_client is None:
            self._llm_client = get_llm_client()
        return self._llm_client

    @abstractmethod
    async def execute(self, context: JobContext) -> AgentResult:
        """Execute agent's primary logic.

        This method must be implemented by subclasses.

        Args:
            context: Job context with input data and shared state

        Returns:
            AgentResult with success status and output data
        """
        pass

    async def run(self, context: JobContext) -> AgentResult:
        """Run agent with logging and error handling.

        This wraps the execute() method with:
        - Structured logging for monitoring
        - Error handling and recovery
        - Execution time tracking

        Args:
            context: Job context with input data

        Returns:
            AgentResult with execution metadata
        """
        self._tokens_used = 0

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
            result.tokens_used = self._tokens_used

            logger.info(
                f'{{"timestamp": "{time.strftime("%Y-%m-%dT%H:%M:%SZ")}", '
                f'"job_id": {context.job_id}, '
                f'"agent": "{self.name}", '
                f'"stage": "completed", '
                f'"success": {str(result.success).lower()}, '
                f'"tokens_used": {self._tokens_used}, '
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
                tokens_used=self._tokens_used,
            )

    async def call_llm(
        self,
        messages: list,
        model: str = "claude-3-5-sonnet",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Call LLM via OpenRouter with error handling and retry logic.

        This method uses the enhanced OpenRouterClient which provides:
        - Automatic rate limiting
        - Exponential backoff on failures
        - Token usage tracking

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model identifier (use keys from AVAILABLE_MODELS)
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate

        Returns:
            Generated content string

        Raises:
            RuntimeError: If API key not configured
        """
        if not settings.OPENROUTER_API_KEY:
            raise RuntimeError("OpenRouter API key not configured")

        # Convert dict messages to ChatMessage objects
        chat_messages: list[ChatMessage] = []
        for msg in messages:
            chat_messages.append(
                ChatMessage(role=msg["role"], content=msg["content"])
            )

        response = await self.llm_client.complete(
            messages=chat_messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Track token usage
        self._tokens_used += response.usage.total_tokens

        return response.content
