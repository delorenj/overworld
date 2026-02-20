"""Bloodbank event emitter for Overworld consensus events.

This module wraps Bloodbank's Publisher to emit consensus workflow events
to the RabbitMQ event bus for real-time progress updates.
"""

import asyncio
import logging
import socket
from pathlib import Path
from typing import Any

from app.events.consensus_events import BaseConsensusEvent

# Lazy import bloodbank components (optional dependency)
_bloodbank_available = False
_Publisher = None
_create_envelope = None
_TriggerType = None
_Source = None

try:
    # Add bloodbank to path if needed (same pattern as TheBoard)
    import sys
    bloodbank_path = Path.home() / "code" / "33GOD" / "bloodbank" / "trunk-main"
    if bloodbank_path.exists() and str(bloodbank_path) not in sys.path:
        sys.path.insert(0, str(bloodbank_path))

    from event_producers.rabbit import Publisher as _Publisher_class
    from event_producers.events.base import (
        TriggerType as _TriggerType_enum,
        Source as _Source_class,
        create_envelope as _create_envelope_func,
    )

    _Publisher = _Publisher_class
    _create_envelope = _create_envelope_func
    _TriggerType = _TriggerType_enum
    _Source = _Source_class
    _bloodbank_available = True
except ImportError as e:
    logging.getLogger(__name__).warning(
        f"Bloodbank components not available: {e}. "
        "Event emission will be disabled."
    )

logger = logging.getLogger(__name__)


def _event_to_routing_key(event: BaseConsensusEvent) -> str:
    """Convert consensus event to bloodbank routing key.

    Maps:
    - consensus.started -> overworld.consensus.started
    - consensus.round.completed -> overworld.consensus.round.completed
    - etc.

    Args:
        event: Consensus event instance

    Returns:
        Bloodbank-compatible routing key with 'overworld.' prefix
    """
    return f"overworld.{event.event_type}"


def _create_bloodbank_envelope(event: BaseConsensusEvent) -> dict[str, Any]:
    """Create Bloodbank EventEnvelope from consensus event.

    Args:
        event: Consensus event instance

    Returns:
        EventEnvelope as dict ready for publishing
    """
    if not _bloodbank_available:
        raise RuntimeError("Bloodbank components not available")

    # Create source metadata
    source = _Source(
        host=socket.gethostname(),
        type=_TriggerType.MANUAL,  # Service-initiated events
        app="overworld",
        meta={"version": "0.1.0"},
    )

    # Create envelope with consensus event as payload
    envelope = _create_envelope(
        event_type=_event_to_routing_key(event),
        payload=event.model_dump(),  # Serialize Pydantic event
        source=source,
    )

    return envelope.model_dump()


class ConsensusEventEmitter:
    """Event emitter for consensus workflow progress.

    Publishes consensus events to Bloodbank for real-time progress tracking.
    Gracefully degrades if Bloodbank is unavailable (logs warnings instead of errors).
    """

    def __init__(self, enabled: bool = True) -> None:
        """Initialize consensus event emitter.

        Args:
            enabled: Whether to enable event emission (default True)
        """
        self.enabled = enabled and _bloodbank_available
        self._publisher: _Publisher | None = None
        self._started = False

        if not _bloodbank_available:
            logger.warning(
                "ConsensusEventEmitter: Bloodbank not available, events will not be emitted"
            )
        elif self.enabled:
            logger.info("ConsensusEventEmitter: Initialized (enabled)")
        else:
            logger.info("ConsensusEventEmitter: Initialized (disabled)")

    async def start(self) -> None:
        """Start the event publisher connection."""
        if not self.enabled or self._started:
            return

        try:
            self._publisher = _Publisher(enable_correlation_tracking=False)
            await self._publisher.start()
            self._started = True
            logger.info("ConsensusEventEmitter: Connected to Bloodbank")
        except Exception as e:
            logger.error(f"ConsensusEventEmitter: Failed to start: {e}")
            self.enabled = False  # Disable on connection failure

    async def emit(self, event: BaseConsensusEvent) -> None:
        """Emit consensus event to Bloodbank.

        Args:
            event: Consensus event to publish

        Note:
            Failures are logged but not raised (graceful degradation)
        """
        if not self.enabled:
            return

        if not self._started:
            await self.start()

        if not self._started:
            # Still not started after attempt, skip emission
            return

        try:
            # Create Bloodbank envelope
            envelope = _create_bloodbank_envelope(event)
            routing_key = _event_to_routing_key(event)

            # Publish to Bloodbank
            await self._publisher.publish(routing_key=routing_key, body=envelope)

            logger.debug(
                f"ConsensusEventEmitter: Published {routing_key} (project_id={event.project_id})"
            )

        except Exception as e:
            logger.warning(
                f"ConsensusEventEmitter: Failed to emit {event.event_type}: {e}"
            )
            # Don't raise - graceful degradation

    async def close(self) -> None:
        """Close publisher connection and clean up resources."""
        if not self._started or not self._publisher:
            return

        try:
            await self._publisher.close()
            self._publisher = None
            self._started = False
            logger.info("ConsensusEventEmitter: Closed connection")
        except Exception as e:
            logger.error(f"ConsensusEventEmitter: Failed to close: {e}")


# Singleton emitter instance
_emitter: ConsensusEventEmitter | None = None


def get_event_emitter(enabled: bool = True) -> ConsensusEventEmitter:
    """Get or create singleton event emitter instance.

    Args:
        enabled: Whether event emission should be enabled (default True)

    Returns:
        Singleton ConsensusEventEmitter instance
    """
    global _emitter
    if _emitter is None:
        _emitter = ConsensusEventEmitter(enabled=enabled)
    return _emitter
