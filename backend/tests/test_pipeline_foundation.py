"""Tests for STORY-004: Multi-Agent Pipeline Foundation.

This module tests the core framework components:
- Agent base class and interfaces
- OpenRouter LLM client wrapper
- Agent communication protocol
- Pipeline state machine
"""

import asyncio
from datetime import datetime
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel, Field

from app.agents.base import (
    AgentCapability,
    AgentConfig,
    AgentInput,
    AgentMetrics,
    AgentOutput,
    AgentStatus,
    BaseAgent,
    ExecutionContext,
)
from app.agents.base_agent import (
    AgentResult,
    BaseAgent as LegacyBaseAgent,
    JobContext,
)
from app.agents.llm_client import (
    AVAILABLE_MODELS,
    ChatMessage,
    LLMResponse,
    OpenRouterClient,
    RateLimiter,
    TokenUsage,
    get_llm_client,
)
from app.agents.messages import (
    AgentRequest,
    AgentResponse,
    ErrorCodes,
    ErrorMessage,
    ErrorSeverity,
    HeartbeatMessage,
    MessagePriority,
    MessageType,
    ProgressUpdate,
)
from app.agents.pipeline import (
    Pipeline,
    PipelineContext,
    PipelineEvent,
    PipelineStage,
    PipelineState,
    PipelineStateMachine,
    PipelineStateRepository,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_hierarchy():
    """Sample document hierarchy for testing."""
    return {
        "L0": {"title": "Test Project", "id": "root"},
        "L1": [
            {"id": "m1", "title": "Milestone 1"},
            {"id": "m2", "title": "Milestone 2"},
        ],
        "L2": [
            {"id": "e1", "title": "Epic 1"},
        ],
    }


@pytest.fixture
def job_context(sample_hierarchy):
    """Create a legacy JobContext for testing."""
    return JobContext(
        job_id=1,
        user_id=1,
        document_url="http://example.com/doc",
        hierarchy=sample_hierarchy,
        theme={"theme_id": "smb3"},
        options={},
    )


@pytest.fixture
def pipeline_context(sample_hierarchy):
    """Create a PipelineContext for testing."""
    return PipelineContext(
        job_id=1,
        user_id=1,
        document_url="http://example.com/doc",
        hierarchy=sample_hierarchy,
        theme_id="smb3",
        options={},
    )


@pytest.fixture
def agent_request():
    """Create an AgentRequest for testing."""
    return AgentRequest(
        source_agent="test",
        job_id=1,
        input_data={
            "job_id": 1,  # Required field for AgentInput
            "hierarchy": {"L0": {"title": "Test"}},
            "theme_id": "smb3",
        },
        context={},
    )


# =============================================================================
# Agent Communication Protocol Tests
# =============================================================================


class TestMessageTypes:
    """Tests for agent message types."""

    def test_agent_request_creation(self):
        """Test AgentRequest model creation."""
        request = AgentRequest(
            source_agent="parser",
            target_agent="artist",
            job_id=123,
            input_data={"key": "value"},
            context={"previous": "data"},
        )

        assert request.message_type == MessageType.REQUEST
        assert request.source_agent == "parser"
        assert request.target_agent == "artist"
        assert request.job_id == 123
        assert request.input_data == {"key": "value"}
        assert request.priority == MessagePriority.NORMAL

    def test_agent_response_creation(self):
        """Test AgentResponse model creation."""
        response = AgentResponse(
            source_agent="artist",
            job_id=123,
            success=True,
            output_data={"theme": "smb3"},
            execution_time_ms=150,
            tokens_used=100,
            model_used="claude-3-5-sonnet",
        )

        assert response.message_type == MessageType.RESPONSE
        assert response.success is True
        assert response.execution_time_ms == 150
        assert response.tokens_used == 100

    def test_progress_update_validation(self):
        """Test ProgressUpdate validation."""
        update = ProgressUpdate(
            source_agent="road",
            job_id=123,
            progress_pct=50.0,
            stage="generating",
            stage_progress_pct=75.0,
            message="Generating road coordinates",
        )

        assert update.message_type == MessageType.PROGRESS
        assert update.progress_pct == 50.0
        assert update.stage == "generating"

    def test_progress_update_validation_bounds(self):
        """Test ProgressUpdate percentage bounds validation."""
        # Valid bounds
        update = ProgressUpdate(
            source_agent="test",
            job_id=1,
            progress_pct=0.0,
            stage="test",
        )
        assert update.progress_pct == 0.0

        update = ProgressUpdate(
            source_agent="test",
            job_id=1,
            progress_pct=100.0,
            stage="test",
        )
        assert update.progress_pct == 100.0

        # Invalid bounds should raise
        with pytest.raises(ValueError):
            ProgressUpdate(
                source_agent="test",
                job_id=1,
                progress_pct=-1.0,
                stage="test",
            )

        with pytest.raises(ValueError):
            ProgressUpdate(
                source_agent="test",
                job_id=1,
                progress_pct=101.0,
                stage="test",
            )

    def test_error_message_creation(self):
        """Test ErrorMessage model creation."""
        error = ErrorMessage(
            source_agent="parser",
            job_id=123,
            severity=ErrorSeverity.ERROR,
            error_code=ErrorCodes.INVALID_INPUT,
            error_message="Invalid hierarchy format",
            error_details={"field": "L1"},
            recoverable=False,
        )

        assert error.message_type == MessageType.ERROR
        assert error.severity == ErrorSeverity.ERROR
        assert error.error_code == "E1001"
        assert error.recoverable is False

    def test_heartbeat_message_creation(self):
        """Test HeartbeatMessage creation."""
        heartbeat = HeartbeatMessage(
            source_agent="coordinator",
            agent_status="healthy",
            current_job_id=123,
            jobs_completed=10,
            uptime_seconds=3600,
        )

        assert heartbeat.message_type == MessageType.HEARTBEAT
        assert heartbeat.agent_status == "healthy"
        assert heartbeat.jobs_completed == 10

    def test_message_correlation(self):
        """Test message correlation through correlation_id."""
        request = AgentRequest(
            source_agent="pipeline",
            job_id=1,
            input_data={},
        )

        response = AgentResponse(
            source_agent="parser",
            correlation_id=request.message_id,
            job_id=1,
            success=True,
            execution_time_ms=100,
        )

        assert response.correlation_id == request.message_id


# =============================================================================
# OpenRouter LLM Client Tests
# =============================================================================


class TestOpenRouterClient:
    """Tests for OpenRouter LLM client wrapper."""

    def test_available_models(self):
        """Test that available models are configured."""
        assert "claude-3-5-sonnet" in AVAILABLE_MODELS
        assert "gpt-4-turbo" in AVAILABLE_MODELS
        assert "gpt-4o" in AVAILABLE_MODELS

    def test_model_config_properties(self):
        """Test model configuration properties."""
        claude = AVAILABLE_MODELS["claude-3-5-sonnet"]

        assert claude.model_id == "anthropic/claude-3.5-sonnet"
        assert claude.context_window == 200000
        assert claude.supports_streaming is True
        assert claude.input_cost_per_1k > 0
        assert claude.output_cost_per_1k > 0

    def test_client_initialization(self):
        """Test client initialization."""
        client = OpenRouterClient(
            api_key="test-key",
            default_model="gpt-4o",
            timeout=60.0,
            max_retries=5,
        )

        assert client.api_key == "test-key"
        assert client.default_model == "gpt-4o"
        assert client.timeout == 60.0
        assert client.max_retries == 5

    def test_token_estimation(self):
        """Test token estimation."""
        client = OpenRouterClient(api_key="test")

        # ~4 chars per token
        assert client.estimate_tokens("hello") >= 1
        assert client.estimate_tokens("a" * 100) >= 20
        assert client.estimate_tokens("") == 1  # Minimum of 1

    def test_message_token_estimation(self):
        """Test message list token estimation."""
        client = OpenRouterClient(api_key="test")

        messages = [
            ChatMessage(role="system", content="You are helpful."),
            ChatMessage(role="user", content="Hello!"),
        ]

        tokens = client.estimate_message_tokens(messages)
        assert tokens > 0
        # Should include overhead for message structure
        assert tokens > sum(len(m.content) // 4 for m in messages)

    def test_cost_calculation(self):
        """Test cost calculation."""
        client = OpenRouterClient(api_key="test")

        cost = client.calculate_cost("claude-3-5-sonnet", 1000, 500)
        assert cost > 0

        # Higher output cost
        config = AVAILABLE_MODELS["claude-3-5-sonnet"]
        expected = (1000 / 1000) * config.input_cost_per_1k + (500 / 1000) * config.output_cost_per_1k
        assert abs(cost - expected) < 0.0001

    def test_statistics_tracking(self):
        """Test client statistics tracking."""
        client = OpenRouterClient(api_key="test")

        stats = client.get_statistics()
        assert stats["total_requests"] == 0
        assert stats["total_tokens"] == 0
        assert stats["total_cost_usd"] == 0.0

    @pytest.mark.asyncio
    async def test_complete_without_api_key(self):
        """Test completion fails without API key."""
        # Create client with empty API key (need to set it to empty string explicitly)
        client = OpenRouterClient.__new__(OpenRouterClient)
        client.api_key = ""
        client.default_model = "claude-3-5-sonnet"
        client.timeout = 120.0
        client.max_retries = 3
        client._rate_limiter = RateLimiter()
        client._total_requests = 0
        client._total_tokens = 0
        client._total_cost = 0.0

        with pytest.raises(RuntimeError, match="API key not configured"):
            await client.complete(
                messages=[ChatMessage(role="user", content="Hello")],
            )


class TestRateLimiter:
    """Tests for rate limiter."""

    @pytest.mark.asyncio
    async def test_acquire_success(self):
        """Test rate limiter acquire under limits."""
        limiter = RateLimiter(requests_per_minute=60, tokens_per_minute=100000)

        # Should not block
        await asyncio.wait_for(limiter.acquire(100), timeout=1.0)

    def test_record_success_resets_failures(self):
        """Test that success resets failure count."""
        limiter = RateLimiter()
        limiter._consecutive_failures = 5

        limiter.record_success()

        assert limiter._consecutive_failures == 0

    def test_record_failure_increments_backoff(self):
        """Test that rate limit failure increases backoff."""
        limiter = RateLimiter()

        limiter.record_failure(is_rate_limit=True)
        assert limiter._consecutive_failures == 1
        assert limiter._backoff_until > 0

        limiter.record_failure(is_rate_limit=True)
        assert limiter._consecutive_failures == 2


# =============================================================================
# Enhanced Base Agent Tests
# =============================================================================


class TestInput(AgentInput):
    """Test input model."""

    data: str = Field(default="test")


class TestOutput(AgentOutput):
    """Test output model."""

    result: str = Field(default="")


class ConcreteAgent(BaseAgent[TestInput, TestOutput]):
    """Concrete test agent implementation."""

    input_type = TestInput
    output_type = TestOutput
    default_config = AgentConfig(
        name="ConcreteAgent",
        version="1.0.0",
        capabilities=[AgentCapability.LLM_CALLS],
    )

    def __init__(self):
        super().__init__()
        self.on_start_called = False
        self.on_complete_called = False
        self.on_error_called = False

    async def process(self, input_data: TestInput, ctx: ExecutionContext) -> TestOutput:
        return TestOutput(success=True, data={"processed": True}, result="done")

    async def on_start(self, ctx: ExecutionContext) -> None:
        self.on_start_called = True

    async def on_complete(self, ctx: ExecutionContext, output: TestOutput) -> None:
        self.on_complete_called = True

    async def on_error(self, ctx: ExecutionContext, error: Exception) -> None:
        self.on_error_called = True


class TestEnhancedBaseAgent:
    """Tests for enhanced BaseAgent."""

    def test_agent_initialization(self):
        """Test agent initialization."""
        agent = ConcreteAgent()

        assert agent.name == "ConcreteAgent"
        assert agent.status == AgentStatus.IDLE
        assert agent.has_capability(AgentCapability.LLM_CALLS)

    @pytest.mark.asyncio
    async def test_agent_run_lifecycle(self, agent_request):
        """Test that lifecycle hooks are called."""
        agent = ConcreteAgent()

        response = await agent.run(agent_request)

        assert response.success is True
        assert agent.on_start_called is True
        assert agent.on_complete_called is True
        assert agent.on_error_called is False

    @pytest.mark.asyncio
    async def test_agent_run_with_progress_callback(self, agent_request):
        """Test progress callback is invoked."""
        agent = ConcreteAgent()
        progress_updates = []

        def on_progress(update: ProgressUpdate):
            progress_updates.append(update)

        response = await agent.run(agent_request, on_progress=on_progress)

        assert response.success is True
        assert len(progress_updates) >= 1

    @pytest.mark.asyncio
    async def test_agent_metrics_collection(self, agent_request):
        """Test metrics are collected during execution."""
        agent = ConcreteAgent()

        await agent.run(agent_request)

        metrics = agent.get_metrics()
        assert metrics["execution_time_ms"] >= 0
        assert metrics["start_time"] is not None

    @pytest.mark.asyncio
    async def test_agent_error_handling(self):
        """Test error handling in agent execution."""

        class ErrorAgent(BaseAgent[TestInput, TestOutput]):
            input_type = TestInput
            output_type = TestOutput
            default_config = AgentConfig(name="ErrorAgent")

            async def process(self, input_data: TestInput, ctx: ExecutionContext) -> TestOutput:
                raise ValueError("Test error")

        agent = ErrorAgent()

        # Create a request with valid input for TestInput
        error_request = AgentRequest(
            source_agent="test",
            job_id=1,
            input_data={"job_id": 1, "data": "test"},  # Valid TestInput fields
            context={},
        )

        response = await agent.run(error_request)

        assert response.success is False
        assert "Test error" in response.output_data.get("error", "")


# =============================================================================
# Legacy Base Agent Compatibility Tests
# =============================================================================


class TestLegacyBaseAgent:
    """Tests for legacy BaseAgent compatibility."""

    @pytest.mark.asyncio
    async def test_legacy_agent_execution(self, job_context):
        """Test legacy agent interface still works."""

        class LegacyTestAgent(LegacyBaseAgent):
            async def execute(self, context: JobContext) -> AgentResult:
                return AgentResult(success=True, data={"test": "value"})

        agent = LegacyTestAgent()
        result = await agent.run(job_context)

        assert result.success is True
        assert result.data == {"test": "value"}
        assert result.execution_time_ms is not None

    @pytest.mark.asyncio
    async def test_legacy_agent_error_handling(self, job_context):
        """Test legacy agent error handling."""

        class LegacyErrorAgent(LegacyBaseAgent):
            async def execute(self, context: JobContext) -> AgentResult:
                raise RuntimeError("Test error")

        agent = LegacyErrorAgent()
        result = await agent.run(job_context)

        assert result.success is False
        assert "Test error" in result.error


# =============================================================================
# Pipeline State Machine Tests
# =============================================================================


class TestPipelineStateMachine:
    """Tests for pipeline state machine."""

    def test_initial_state(self, pipeline_context):
        """Test pipeline starts in IDLE state."""
        assert pipeline_context.current_state == PipelineState.IDLE

    @pytest.mark.asyncio
    async def test_start_transition(self, pipeline_context):
        """Test transition from IDLE to PARSING."""
        sm = PipelineStateMachine()

        success, error = await sm.transition(pipeline_context, PipelineEvent.START)

        assert success is True
        assert pipeline_context.current_state == PipelineState.PARSING
        assert pipeline_context.started_at is not None

    @pytest.mark.asyncio
    async def test_parse_complete_transition(self, pipeline_context):
        """Test transition from PARSING to GENERATING."""
        sm = PipelineStateMachine()

        # First transition to PARSING
        await sm.transition(pipeline_context, PipelineEvent.START)

        # Add parser output for guard
        pipeline_context.set_agent_output("parser", {"valid": True})

        success, error = await sm.transition(pipeline_context, PipelineEvent.PARSE_COMPLETE)

        assert success is True
        assert pipeline_context.current_state == PipelineState.GENERATING

    @pytest.mark.asyncio
    async def test_guard_blocks_invalid_transition(self, pipeline_context):
        """Test guard prevents invalid transitions."""
        sm = PipelineStateMachine()

        # Transition to PARSING
        await sm.transition(pipeline_context, PipelineEvent.START)

        # Try to complete without valid parser output
        success, error = await sm.transition(pipeline_context, PipelineEvent.PARSE_COMPLETE)

        assert success is False
        assert "guard" in error.lower()
        assert pipeline_context.current_state == PipelineState.PARSING

    @pytest.mark.asyncio
    async def test_error_transition(self, pipeline_context):
        """Test transition to FAILED state on error."""
        sm = PipelineStateMachine()

        await sm.transition(pipeline_context, PipelineEvent.START)
        success, error = await sm.transition(pipeline_context, PipelineEvent.ERROR)

        assert success is True
        assert pipeline_context.current_state == PipelineState.FAILED
        assert pipeline_context.completed_at is not None

    @pytest.mark.asyncio
    async def test_cancel_transition(self, pipeline_context):
        """Test cancellation from any processing state."""
        sm = PipelineStateMachine()

        await sm.transition(pipeline_context, PipelineEvent.START)
        success, error = await sm.transition(pipeline_context, PipelineEvent.CANCEL)

        assert success is True
        assert pipeline_context.current_state == PipelineState.CANCELLED

    @pytest.mark.asyncio
    async def test_retry_transition(self, pipeline_context):
        """Test retry from FAILED state."""
        sm = PipelineStateMachine()

        # Get to FAILED state
        await sm.transition(pipeline_context, PipelineEvent.START)
        await sm.transition(pipeline_context, PipelineEvent.ERROR)

        # Retry
        success, error = await sm.transition(pipeline_context, PipelineEvent.RETRY)

        assert success is True
        assert pipeline_context.current_state == PipelineState.PARSING
        assert pipeline_context.retry_count == 0  # Incremented by action, not guard

    @pytest.mark.asyncio
    async def test_retry_blocked_after_max_retries(self, pipeline_context):
        """Test retry is blocked after max retries."""
        sm = PipelineStateMachine()
        pipeline_context.retry_count = pipeline_context.max_retries

        # Get to FAILED state
        await sm.transition(pipeline_context, PipelineEvent.START)
        await sm.transition(pipeline_context, PipelineEvent.ERROR)

        # Retry should be blocked
        success, error = await sm.transition(pipeline_context, PipelineEvent.RETRY)

        assert success is False
        assert pipeline_context.current_state == PipelineState.FAILED

    def test_get_valid_transitions(self, pipeline_context):
        """Test getting valid transitions from a state."""
        sm = PipelineStateMachine()

        transitions = sm.get_valid_transitions(PipelineState.IDLE)

        assert len(transitions) == 1
        assert (PipelineEvent.START, PipelineState.PARSING) in transitions

    @pytest.mark.asyncio
    async def test_transition_callback(self, pipeline_context):
        """Test transition callbacks are invoked."""
        sm = PipelineStateMachine()
        callback_invocations = []

        def callback(from_state, to_state, ctx):
            callback_invocations.append((from_state, to_state))

        sm.on_transition(callback)

        await sm.transition(pipeline_context, PipelineEvent.START)

        assert len(callback_invocations) == 1
        assert callback_invocations[0] == (PipelineState.IDLE, PipelineState.PARSING)


class TestPipelineContext:
    """Tests for PipelineContext."""

    def test_record_event(self, pipeline_context):
        """Test event recording."""
        pipeline_context.record_event(PipelineEvent.START, {"test": "data"})

        assert len(pipeline_context.event_history) == 1
        assert pipeline_context.event_history[0]["event"] == "start"
        assert pipeline_context.event_history[0]["details"] == {"test": "data"}

    def test_agent_output_storage(self, pipeline_context):
        """Test agent output storage and retrieval."""
        output = {"theme_id": "smb3", "colors": {}}

        pipeline_context.set_agent_output("artist", output)
        retrieved = pipeline_context.get_agent_output("artist")

        assert retrieved == output

    def test_checkpoint_serialization(self, pipeline_context):
        """Test checkpoint serialization and restoration."""
        pipeline_context.set_agent_output("parser", {"valid": True})
        pipeline_context.progress_pct = 50.0

        checkpoint = pipeline_context.to_checkpoint()
        restored = PipelineContext.from_checkpoint(checkpoint)

        assert restored.job_id == pipeline_context.job_id
        assert restored.progress_pct == 50.0
        assert restored.get_agent_output("parser") == {"valid": True}


class TestPipelineStateRepository:
    """Tests for PipelineStateRepository."""

    @pytest.mark.asyncio
    async def test_save_and_load(self, pipeline_context):
        """Test saving and loading pipeline state."""
        repo = PipelineStateRepository()

        await repo.save(pipeline_context)
        loaded = await repo.load(pipeline_context.job_id)

        assert loaded is not None
        assert loaded.job_id == pipeline_context.job_id

    @pytest.mark.asyncio
    async def test_load_nonexistent(self):
        """Test loading nonexistent pipeline state."""
        repo = PipelineStateRepository()

        loaded = await repo.load(99999)

        assert loaded is None

    @pytest.mark.asyncio
    async def test_delete(self, pipeline_context):
        """Test deleting pipeline state."""
        repo = PipelineStateRepository()

        await repo.save(pipeline_context)
        await repo.delete(pipeline_context.job_id)
        loaded = await repo.load(pipeline_context.job_id)

        assert loaded is None

    @pytest.mark.asyncio
    async def test_get_active_jobs(self, pipeline_context):
        """Test getting active jobs."""
        repo = PipelineStateRepository()

        # Save an active job
        pipeline_context.current_state = PipelineState.GENERATING
        await repo.save(pipeline_context)

        active = repo.get_active_jobs()

        assert pipeline_context.job_id in active


# =============================================================================
# Integration Tests
# =============================================================================


class TestFullPipeline:
    """Integration tests for full pipeline execution."""

    @pytest.mark.asyncio
    async def test_full_pipeline_state_progression(self, pipeline_context):
        """Test pipeline progresses through all states."""
        sm = PipelineStateMachine()

        # IDLE -> PARSING
        await sm.transition(pipeline_context, PipelineEvent.START)
        assert pipeline_context.current_state == PipelineState.PARSING

        # Add outputs
        pipeline_context.set_agent_output("parser", {"valid": True, "milestones": []})

        # PARSING -> GENERATING
        await sm.transition(pipeline_context, PipelineEvent.PARSE_COMPLETE)
        assert pipeline_context.current_state == PipelineState.GENERATING

        # Add outputs
        pipeline_context.set_agent_output("artist", {"theme_id": "smb3"})
        pipeline_context.set_agent_output("road", {"coordinates": []})

        # GENERATING -> RENDERING
        await sm.transition(pipeline_context, PipelineEvent.GENERATE_COMPLETE)
        assert pipeline_context.current_state == PipelineState.RENDERING

        # Add outputs
        pipeline_context.set_agent_output("icon", {"icons": []})

        # RENDERING -> COMPLETE
        await sm.transition(pipeline_context, PipelineEvent.RENDER_COMPLETE)
        assert pipeline_context.current_state == PipelineState.COMPLETE
        assert pipeline_context.completed_at is not None

    @pytest.mark.asyncio
    async def test_progress_tracking(self, pipeline_context):
        """Test progress percentage is updated through states."""
        sm = PipelineStateMachine()

        assert pipeline_context.progress_pct == 0.0

        await sm.transition(pipeline_context, PipelineEvent.START)
        assert pipeline_context.progress_pct == 10.0  # PARSING state

        pipeline_context.set_agent_output("parser", {"valid": True})
        await sm.transition(pipeline_context, PipelineEvent.PARSE_COMPLETE)
        assert pipeline_context.progress_pct == 40.0  # GENERATING state
