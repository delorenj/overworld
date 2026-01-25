"""OpenRouter LLM client wrapper with advanced features.

This module provides a robust wrapper around the OpenRouter API with:
- Support for multiple models (Claude, GPT-4, etc.)
- Streaming response support
- Token counting and estimation
- Rate limiting with exponential backoff
- Request/response logging
"""

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

import httpx
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)


# Model definitions with token limits and pricing
@dataclass
class ModelConfig:
    """Configuration for an LLM model."""

    model_id: str
    display_name: str
    context_window: int
    max_output_tokens: int
    input_cost_per_1k: float  # USD per 1000 tokens
    output_cost_per_1k: float
    supports_streaming: bool = True
    supports_functions: bool = True


# Available models configuration
AVAILABLE_MODELS: dict[str, ModelConfig] = {
    "claude-3-5-sonnet": ModelConfig(
        model_id="anthropic/claude-3.5-sonnet",
        display_name="Claude 3.5 Sonnet",
        context_window=200000,
        max_output_tokens=8192,
        input_cost_per_1k=0.003,
        output_cost_per_1k=0.015,
    ),
    "claude-3-opus": ModelConfig(
        model_id="anthropic/claude-3-opus",
        display_name="Claude 3 Opus",
        context_window=200000,
        max_output_tokens=4096,
        input_cost_per_1k=0.015,
        output_cost_per_1k=0.075,
    ),
    "gpt-4-turbo": ModelConfig(
        model_id="openai/gpt-4-turbo",
        display_name="GPT-4 Turbo",
        context_window=128000,
        max_output_tokens=4096,
        input_cost_per_1k=0.01,
        output_cost_per_1k=0.03,
    ),
    "gpt-4o": ModelConfig(
        model_id="openai/gpt-4o",
        display_name="GPT-4o",
        context_window=128000,
        max_output_tokens=4096,
        input_cost_per_1k=0.005,
        output_cost_per_1k=0.015,
    ),
    "gpt-4o-mini": ModelConfig(
        model_id="openai/gpt-4o-mini",
        display_name="GPT-4o Mini",
        context_window=128000,
        max_output_tokens=16384,
        input_cost_per_1k=0.00015,
        output_cost_per_1k=0.0006,
    ),
}

# Default model for the pipeline
DEFAULT_MODEL = "claude-3-5-sonnet"


class ChatMessage(BaseModel):
    """A single chat message."""

    role: Literal["system", "user", "assistant"] = Field(..., description="Message role")
    content: str = Field(..., description="Message content")


class LLMRequest(BaseModel):
    """Request payload for LLM completion."""

    model: str = Field(default=DEFAULT_MODEL, description="Model identifier")
    messages: list[ChatMessage] = Field(..., description="Chat messages")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: Optional[int] = Field(default=None, description="Maximum tokens to generate")
    stream: bool = Field(default=False, description="Enable streaming response")
    stop: Optional[list[str]] = Field(default=None, description="Stop sequences")


class TokenUsage(BaseModel):
    """Token usage statistics."""

    prompt_tokens: int = Field(default=0, description="Tokens in the prompt")
    completion_tokens: int = Field(default=0, description="Tokens in the completion")
    total_tokens: int = Field(default=0, description="Total tokens used")
    estimated_cost_usd: float = Field(default=0.0, description="Estimated cost in USD")


class LLMResponse(BaseModel):
    """Response from LLM completion."""

    content: str = Field(..., description="Generated content")
    model: str = Field(..., description="Model used")
    finish_reason: Optional[str] = Field(default=None, description="Reason for completion")
    usage: TokenUsage = Field(default_factory=TokenUsage, description="Token usage")
    latency_ms: int = Field(default=0, description="Response latency in milliseconds")


class StreamChunk(BaseModel):
    """A single chunk from a streaming response."""

    content: str = Field(default="", description="Content delta")
    finish_reason: Optional[str] = Field(default=None, description="Finish reason if complete")
    is_final: bool = Field(default=False, description="Whether this is the final chunk")


@dataclass
class RateLimiter:
    """Token bucket rate limiter with exponential backoff."""

    requests_per_minute: int = 60
    tokens_per_minute: int = 100000
    _request_timestamps: list[float] = field(default_factory=list)
    _token_timestamps: list[tuple] = field(default_factory=list)  # (timestamp, token_count)
    _backoff_until: float = 0.0
    _consecutive_failures: int = 0

    def _cleanup_old_timestamps(self) -> None:
        """Remove timestamps older than 1 minute."""
        current_time = time.time()
        cutoff = current_time - 60.0

        self._request_timestamps = [
            ts for ts in self._request_timestamps if ts > cutoff
        ]
        self._token_timestamps = [
            (ts, count) for ts, count in self._token_timestamps if ts > cutoff
        ]

    async def acquire(self, estimated_tokens: int = 0) -> None:
        """Acquire permission to make a request, waiting if necessary."""
        while True:
            current_time = time.time()

            # Check backoff
            if current_time < self._backoff_until:
                wait_time = self._backoff_until - current_time
                logger.warning(f"Rate limiter backoff: waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                continue

            self._cleanup_old_timestamps()

            # Check request rate
            if len(self._request_timestamps) >= self.requests_per_minute:
                wait_time = self._request_timestamps[0] + 60.0 - current_time
                if wait_time > 0:
                    logger.debug(f"Request rate limit: waiting {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    continue

            # Check token rate
            total_tokens = sum(count for _, count in self._token_timestamps)
            if total_tokens + estimated_tokens > self.tokens_per_minute:
                oldest_ts = self._token_timestamps[0][0] if self._token_timestamps else current_time
                wait_time = oldest_ts + 60.0 - current_time
                if wait_time > 0:
                    logger.debug(f"Token rate limit: waiting {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    continue

            # Acquire
            self._request_timestamps.append(current_time)
            if estimated_tokens > 0:
                self._token_timestamps.append((current_time, estimated_tokens))

            return

    def record_success(self) -> None:
        """Record a successful request."""
        self._consecutive_failures = 0

    def record_failure(self, is_rate_limit: bool = False) -> None:
        """Record a failed request with exponential backoff."""
        self._consecutive_failures += 1

        if is_rate_limit:
            # Exponential backoff: 1s, 2s, 4s, 8s, 16s, max 60s
            backoff_seconds = min(60, 2 ** self._consecutive_failures)
            self._backoff_until = time.time() + backoff_seconds
            logger.warning(
                f"Rate limit hit, backoff for {backoff_seconds}s "
                f"(failure #{self._consecutive_failures})"
            )

    def record_tokens(self, tokens: int) -> None:
        """Record actual token usage after a request."""
        current_time = time.time()
        self._token_timestamps.append((current_time, tokens))


class OpenRouterClient:
    """Robust OpenRouter API client with advanced features.

    Features:
    - Multiple model support
    - Streaming responses
    - Token counting and cost estimation
    - Rate limiting with exponential backoff
    - Automatic retries
    - Request/response logging
    """

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: str = DEFAULT_MODEL,
        timeout: float = 120.0,
        max_retries: int = 3,
        requests_per_minute: int = 60,
        tokens_per_minute: int = 100000,
    ):
        """Initialize the OpenRouter client.

        Args:
            api_key: OpenRouter API key (defaults to settings)
            default_model: Default model to use
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            requests_per_minute: Rate limit for requests
            tokens_per_minute: Rate limit for tokens
        """
        self.api_key = api_key or settings.OPENROUTER_API_KEY
        self.default_model = default_model
        self.timeout = timeout
        self.max_retries = max_retries

        self._rate_limiter = RateLimiter(
            requests_per_minute=requests_per_minute,
            tokens_per_minute=tokens_per_minute,
        )

        # Statistics
        self._total_requests = 0
        self._total_tokens = 0
        self._total_cost = 0.0

        if not self.api_key:
            logger.warning("OpenRouter API key not configured")

    def _get_model_config(self, model: str) -> ModelConfig:
        """Get configuration for a model."""
        if model in AVAILABLE_MODELS:
            return AVAILABLE_MODELS[model]

        # Default config for unknown models
        return ModelConfig(
            model_id=model,
            display_name=model,
            context_window=8192,
            max_output_tokens=4096,
            input_cost_per_1k=0.01,
            output_cost_per_1k=0.03,
        )

    def _get_headers(self) -> dict[str, str]:
        """Get request headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://overworld.app",
            "X-Title": "Overworld Map Generator",
        }

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Uses a simple heuristic: ~4 characters per token for English text.
        For more accurate counting, use tiktoken for specific models.
        """
        # Simple estimation: ~4 chars per token for English
        return max(1, len(text) // 4)

    def estimate_message_tokens(self, messages: list[ChatMessage]) -> int:
        """Estimate total tokens for a message list."""
        total = 0
        for msg in messages:
            # Add overhead for message structure (~4 tokens)
            total += 4
            total += self.estimate_tokens(msg.content)
        return total

    def calculate_cost(
        self, model: str, prompt_tokens: int, completion_tokens: int
    ) -> float:
        """Calculate estimated cost for token usage."""
        config = self._get_model_config(model)
        input_cost = (prompt_tokens / 1000) * config.input_cost_per_1k
        output_cost = (completion_tokens / 1000) * config.output_cost_per_1k
        return input_cost + output_cost

    async def complete(
        self,
        messages: list[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop: Optional[list[str]] = None,
        retry_on_failure: bool = True,
    ) -> LLMResponse:
        """Generate a completion from the LLM.

        Args:
            messages: List of chat messages
            model: Model to use (defaults to client default)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stop: Stop sequences
            retry_on_failure: Whether to retry on transient failures

        Returns:
            LLMResponse with generated content and metadata

        Raises:
            RuntimeError: If API key not configured
            httpx.HTTPError: If request fails after retries
        """
        if not self.api_key:
            raise RuntimeError("OpenRouter API key not configured")

        model = model or self.default_model
        config = self._get_model_config(model)

        # Estimate tokens for rate limiting
        estimated_input = self.estimate_message_tokens(messages)
        estimated_output = max_tokens or config.max_output_tokens // 2

        # Build request payload
        payload = {
            "model": config.model_id,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if stop:
            payload["stop"] = stop

        last_error: Optional[Exception] = None
        attempts = 0

        while attempts < (self.max_retries if retry_on_failure else 1):
            attempts += 1

            try:
                # Acquire rate limit permission
                await self._rate_limiter.acquire(estimated_input + estimated_output)

                start_time = time.time()

                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.BASE_URL}/chat/completions",
                        headers=self._get_headers(),
                        json=payload,
                    )

                latency_ms = int((time.time() - start_time) * 1000)

                if response.status_code == 429:
                    self._rate_limiter.record_failure(is_rate_limit=True)
                    if attempts < self.max_retries:
                        continue
                    response.raise_for_status()

                response.raise_for_status()
                data = response.json()

                self._rate_limiter.record_success()

                # Parse response
                content = data["choices"][0]["message"]["content"]
                finish_reason = data["choices"][0].get("finish_reason")

                # Parse usage
                usage_data = data.get("usage", {})
                prompt_tokens = usage_data.get("prompt_tokens", estimated_input)
                completion_tokens = usage_data.get(
                    "completion_tokens", self.estimate_tokens(content)
                )

                # Record actual token usage
                self._rate_limiter.record_tokens(prompt_tokens + completion_tokens)

                # Calculate cost
                cost = self.calculate_cost(model, prompt_tokens, completion_tokens)

                # Update statistics
                self._total_requests += 1
                self._total_tokens += prompt_tokens + completion_tokens
                self._total_cost += cost

                usage = TokenUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                    estimated_cost_usd=cost,
                )

                logger.debug(
                    f"LLM completion: model={model}, tokens={usage.total_tokens}, "
                    f"cost=${cost:.4f}, latency={latency_ms}ms"
                )

                return LLMResponse(
                    content=content,
                    model=config.model_id,
                    finish_reason=finish_reason,
                    usage=usage,
                    latency_ms=latency_ms,
                )

            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(
                    f"LLM request failed (attempt {attempts}/{self.max_retries}): "
                    f"{e.response.status_code}"
                )
                if e.response.status_code >= 500:
                    # Server error, retry
                    await asyncio.sleep(1.0 * attempts)
                    continue
                raise

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                logger.warning(
                    f"LLM request failed (attempt {attempts}/{self.max_retries}): {e}"
                )
                await asyncio.sleep(1.0 * attempts)
                continue

        if last_error:
            raise last_error
        raise RuntimeError("Unexpected error in LLM completion")

    async def stream(
        self,
        messages: list[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop: Optional[list[str]] = None,
        on_chunk: Optional[Callable[[StreamChunk], None]] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a completion from the LLM.

        Args:
            messages: List of chat messages
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stop: Stop sequences
            on_chunk: Optional callback for each chunk

        Yields:
            StreamChunk objects with content deltas

        Raises:
            RuntimeError: If API key not configured
            httpx.HTTPError: If request fails
        """
        if not self.api_key:
            raise RuntimeError("OpenRouter API key not configured")

        model = model or self.default_model
        config = self._get_model_config(model)

        estimated_input = self.estimate_message_tokens(messages)

        # Build request payload
        payload = {
            "model": config.model_id,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if stop:
            payload["stop"] = stop

        await self._rate_limiter.acquire(estimated_input)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.BASE_URL}/chat/completions",
                headers=self._get_headers(),
                json=payload,
            ) as response:
                response.raise_for_status()

                accumulated_content = ""

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue

                    data_str = line[6:]  # Remove "data: " prefix

                    if data_str == "[DONE]":
                        chunk = StreamChunk(is_final=True)
                        if on_chunk:
                            on_chunk(chunk)
                        yield chunk
                        break

                    try:
                        import json

                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        finish_reason = data["choices"][0].get("finish_reason")

                        accumulated_content += content

                        chunk = StreamChunk(
                            content=content,
                            finish_reason=finish_reason,
                            is_final=finish_reason is not None,
                        )

                        if on_chunk:
                            on_chunk(chunk)

                        yield chunk

                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

                # Record token usage
                estimated_output = self.estimate_tokens(accumulated_content)
                self._rate_limiter.record_tokens(estimated_input + estimated_output)
                self._total_tokens += estimated_input + estimated_output

    def get_statistics(self) -> dict[str, Any]:
        """Get client usage statistics."""
        return {
            "total_requests": self._total_requests,
            "total_tokens": self._total_tokens,
            "total_cost_usd": round(self._total_cost, 4),
        }

    @staticmethod
    def get_available_models() -> dict[str, dict[str, Any]]:
        """Get information about available models."""
        return {
            key: {
                "model_id": config.model_id,
                "display_name": config.display_name,
                "context_window": config.context_window,
                "max_output_tokens": config.max_output_tokens,
                "supports_streaming": config.supports_streaming,
            }
            for key, config in AVAILABLE_MODELS.items()
        }


# Global client instance (lazy initialization)
_client: Optional[OpenRouterClient] = None


def get_llm_client() -> OpenRouterClient:
    """Get the global LLM client instance."""
    global _client
    if _client is None:
        _client = OpenRouterClient()
    return _client
