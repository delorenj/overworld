"""Multi-agent system for Overworld map generation.

This package provides the complete multi-agent pipeline framework for
generating maps from document hierarchies. It includes:

Core Framework (STORY-004):
    - BaseAgent: Base class with typed I/O, lifecycle hooks, progress callbacks
    - OpenRouterClient: LLM client with streaming, token counting, rate limiting
    - Messages: Pydantic models for agent communication protocol
    - Pipeline: State machine with states, transitions, guards, persistence

Concrete Agents (STORY-005: Enhanced with LLM support):
    - ParserAgent: Validates and parses document hierarchy into map structures
    - ArtistAgent: Generates visual specifications and color palettes
    - RoadAgent: Generates curved path coordinates
    - IconAgent: Places milestone icons along the road
    - CoordinatorAgent: Orchestrates the full pipeline

Prompts (STORY-005):
    - Structured prompts for LLM-based map generation
    - Theme presets for consistent 8/16-bit styling

Usage (Legacy API - for existing code):
    from app.agents import BaseAgent, JobContext, AgentResult

Usage (New API - recommended for new code):
    from app.agents.base import BaseAgent, ExecutionContext, AgentOutput
    from app.agents.messages import AgentRequest, AgentResponse, ProgressUpdate
    from app.agents.llm_client import OpenRouterClient, get_llm_client
    from app.agents.pipeline import Pipeline, PipelineContext, PipelineState

Usage (Enhanced Agents - STORY-005):
    from app.agents.parser_agent import EnhancedParserAgent, ParserInput, ParserOutput
    from app.agents.artist_agent import EnhancedArtistAgent, ArtistInput, ArtistOutput
    from app.agents.prompts import format_parser_prompt, get_theme_preset
"""

# Legacy exports (backward compatibility)
# Concrete agents
from app.agents.artist_agent import (
    ArtistAgent,
    ArtistInput,
    ArtistOutput,
    ColorPalette,
    VisualSpecification,
)
from app.agents.artist_agent import EnhancedArtistAgent

# Enhanced base agent exports
from app.agents.base import (
    AgentCapability,
    AgentConfig,
    AgentInput,
    AgentMetrics,
    AgentOutput,
    AgentStatus,
    ExecutionContext,
)
from app.agents.base import BaseAgent as EnhancedBaseAgent
from app.agents.base_agent import AgentResult, BaseAgent, JobContext

# Coordinator exports (STORY-007)
from app.agents.coordinator import (
    CoordinatorAgent,
    CoordinatorResult,
    CoordinatorStatus,
    PipelineCoordinator,
    StageConfig,
    StageResult,
)
from app.agents.icon_agent import IconAgent

# New framework exports (STORY-004)
from app.agents.llm_client import (
    AVAILABLE_MODELS,
    ChatMessage,
    LLMRequest,
    LLMResponse,
    OpenRouterClient,
    StreamChunk,
    TokenUsage,
    get_llm_client,
)
from app.agents.messages import (
    AgentRequest,
    AgentResponse,
    AnyMessage,
    BaseMessage,
    CancelMessage,
    ErrorCodes,
    ErrorMessage,
    ErrorSeverity,
    HeartbeatMessage,
    MessagePriority,
    MessageType,
    ProgressUpdate,
)
from app.agents.parser_agent import (
    EnhancedParserAgent,
    MapStructure,
    ParserAgent,
    ParserInput,
    ParserOutput,
    Region,
)
from app.agents.prompts import (
    ARTIST_THEME_PRESETS,
    format_artist_prompt,
    format_parser_prompt,
    get_theme_preset,
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
from app.agents.road_agent import RoadAgent

__all__ = [
    # Legacy exports (backward compatibility)
    "BaseAgent",
    "JobContext",
    "AgentResult",
    # Concrete agents (legacy)
    "ParserAgent",
    "ArtistAgent",
    "RoadAgent",
    "IconAgent",
    "CoordinatorAgent",
    # Coordinator (STORY-007)
    "PipelineCoordinator",
    "StageConfig",
    "StageResult",
    "CoordinatorResult",
    "CoordinatorStatus",
    # Enhanced agents (STORY-005)
    "EnhancedParserAgent",
    "EnhancedArtistAgent",
    "ParserInput",
    "ParserOutput",
    "ArtistInput",
    "ArtistOutput",
    "MapStructure",
    "Region",
    "VisualSpecification",
    "ColorPalette",
    # Prompts (STORY-005)
    "format_parser_prompt",
    "format_artist_prompt",
    "get_theme_preset",
    "ARTIST_THEME_PRESETS",
    # LLM client
    "OpenRouterClient",
    "get_llm_client",
    "ChatMessage",
    "LLMRequest",
    "LLMResponse",
    "TokenUsage",
    "StreamChunk",
    "AVAILABLE_MODELS",
    # Messages
    "MessageType",
    "MessagePriority",
    "ErrorSeverity",
    "BaseMessage",
    "AgentRequest",
    "AgentResponse",
    "ProgressUpdate",
    "ErrorMessage",
    "HeartbeatMessage",
    "CancelMessage",
    "AnyMessage",
    "ErrorCodes",
    # Pipeline
    "PipelineState",
    "PipelineEvent",
    "PipelineContext",
    "PipelineStateMachine",
    "Pipeline",
    "PipelineStage",
    "PipelineStateRepository",
    # Enhanced base agent
    "EnhancedBaseAgent",
    "AgentStatus",
    "AgentCapability",
    "AgentInput",
    "AgentOutput",
    "AgentConfig",
    "AgentMetrics",
    "ExecutionContext",
]
