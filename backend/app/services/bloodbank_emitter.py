"""Bloodbank event emitter for Overworld events."""

import logging
import socket
from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

import pika
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.schemas.events import (
    CustomizationType,
    EventSource,
    OverworldMapCustomizationV1,
    OverworldUserProfileV1,
    UserProfileUpdateType,
)

logger = logging.getLogger(__name__)

# Bloodbank constants
EXCHANGE_NAME = "bloodbank.events.v1"
ROUTING_KEY_MAP_CUSTOMIZED = "overworld.map.customized"
ROUTING_KEY_USER_PROFILE_UPDATED = "overworld.user.profile_updated"
ROUTING_KEY_EXPORT_GENERATED = "overworld.export.generated"


def get_event_source(trigger_type: str = "api") -> EventSource:
    """Create event source metadata.

    Args:
        trigger_type: Type of trigger (api, webhook, background_job, etc.)

    Returns:
        EventSource with host, app, and trigger info
    """
    return EventSource(
        host=socket.gethostname(),
        app="overworld",
        trigger_type=trigger_type,
    )


async def emit_map_customization_event(
    db: AsyncSession,
    map_id: int,
    user_id: int,
    customization_type: Literal[
        "theme_applied",
        "colors_changed",
        "marker_added",
        "marker_removed",
        "marker_updated",
        "watermark_toggled",
        "name_changed",
    ],
    theme_data: Optional[dict[str, Any]] = None,
    colors_data: Optional[dict[str, Any]] = None,
    marker_data: Optional[dict[str, Any]] = None,
    watermark_data: Optional[dict[str, Any]] = None,
    trigger_type: str = "api",
) -> None:
    """Emit a map customization event to Bloodbank.

    Args:
        db: Database session (unused, kept for consistency)
        map_id: Map ID
        user_id: User ID
        customization_type: Type of customization
        theme_data: Theme-specific data (optional)
        colors_data: Color customization data (optional)
        marker_data: Marker data (optional)
        watermark_data: Watermark toggle data (optional)
        trigger_type: Event trigger type

    Raises:
        Exception: If RabbitMQ connection fails
    """
    # Build event payload
    event = OverworldMapCustomizationV1(
        event_id=uuid4(),
        timestamp=datetime.now(timezone.utc),
        source=get_event_source(trigger_type),
        map_id=map_id,
        user_id=user_id,
        customization_type=CustomizationType(customization_type),
        theme=theme_data,
        colors=colors_data,
        marker=marker_data,
        watermark=watermark_data,
    )

    # Publish to Bloodbank
    try:
        connection = pika.BlockingConnection(
            pika.URLParameters(settings.RABBITMQ_URL)
        )
        channel = connection.channel()

        # Declare exchange (idempotent)
        channel.exchange_declare(
            exchange=EXCHANGE_NAME,
            exchange_type="topic",
            durable=True,
        )

        # Publish event
        channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key=ROUTING_KEY_MAP_CUSTOMIZED,
            body=event.model_dump_json().encode("utf-8"),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Persistent
                content_type="application/json",
                message_id=str(event.event_id),
                timestamp=int(event.timestamp.timestamp()),
            ),
        )

        connection.close()

        logger.info(
            f"Emitted map customization event: map_id={map_id}, "
            f"type={customization_type}, event_id={event.event_id}"
        )

    except Exception as e:
        logger.error(f"Failed to emit map customization event: {e}")
        raise


async def emit_user_profile_event(
    db: AsyncSession,
    user_id: int,
    update_type: Literal[
        "account_created",
        "email_verified",
        "oauth_linked",
        "premium_activated",
        "premium_deactivated",
        "preferences_changed",
        "history_milestone",
    ],
    account_data: Optional[dict[str, Any]] = None,
    preferences_data: Optional[dict[str, Any]] = None,
    history_data: Optional[dict[str, Any]] = None,
    premium_data: Optional[dict[str, Any]] = None,
    trigger_type: str = "api",
) -> None:
    """Emit a user profile update event to Bloodbank.

    Args:
        db: Database session (unused, kept for consistency)
        user_id: User ID
        update_type: Type of update
        account_data: Account-related data (optional)
        preferences_data: Preferences data (optional)
        history_data: History/milestone data (optional)
        premium_data: Premium status data (optional)
        trigger_type: Event trigger type

    Raises:
        Exception: If RabbitMQ connection fails
    """
    # Build event payload
    event = OverworldUserProfileV1(
        event_id=uuid4(),
        timestamp=datetime.now(timezone.utc),
        source=get_event_source(trigger_type),
        user_id=user_id,
        update_type=UserProfileUpdateType(update_type),
        account=account_data,
        preferences=preferences_data,
        history=history_data,
        premium=premium_data,
    )

    # Publish to Bloodbank
    try:
        connection = pika.BlockingConnection(
            pika.URLParameters(settings.RABBITMQ_URL)
        )
        channel = connection.channel()

        # Declare exchange (idempotent)
        channel.exchange_declare(
            exchange=EXCHANGE_NAME,
            exchange_type="topic",
            durable=True,
        )

        # Publish event
        channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key=ROUTING_KEY_USER_PROFILE_UPDATED,
            body=event.model_dump_json().encode("utf-8"),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Persistent
                content_type="application/json",
                message_id=str(event.event_id),
                timestamp=int(event.timestamp.timestamp()),
            ),
        )

        connection.close()

        logger.info(
            f"Emitted user profile event: user_id={user_id}, "
            f"type={update_type}, event_id={event.event_id}"
        )

    except Exception as e:
        logger.error(f"Failed to emit user profile event: {e}")
        raise


async def emit_export_generated_event(
    db: AsyncSession,
    export_id: int,
    map_id: int,
    user_id: int,
    format: str,
    resolution: int,
    watermarked: bool,
    file_size_bytes: int,
    theme_id: Optional[int] = None,
    trigger_type: str = "background_job",
) -> None:
    """Emit an export generation event to Bloodbank.

    Args:
        db: Database session (unused, kept for consistency)
        export_id: Export ID
        map_id: Map ID
        user_id: User ID
        format: Export format (png/svg)
        resolution: Resolution multiplier
        watermarked: Whether watermark is applied
        file_size_bytes: File size in bytes
        theme_id: Theme ID (optional)
        trigger_type: Event trigger type

    Raises:
        Exception: If RabbitMQ connection fails
    """
    from app.schemas.events import OverworldExportGeneratedV1

    # Build event payload
    event = OverworldExportGeneratedV1(
        event_id=uuid4(),
        timestamp=datetime.now(timezone.utc),
        source=get_event_source(trigger_type),
        user_id=user_id,
        export_id=export_id,
        map_id=map_id,
        format=format,
        resolution=resolution,
        watermarked=watermarked,
        file_size_bytes=file_size_bytes,
        theme_id=theme_id,
    )

    # Publish to Bloodbank
    try:
        connection = pika.BlockingConnection(
            pika.URLParameters(settings.RABBITMQ_URL)
        )
        channel = connection.channel()

        # Declare exchange (idempotent)
        channel.exchange_declare(
            exchange=EXCHANGE_NAME,
            exchange_type="topic",
            durable=True,
        )

        # Publish event
        channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key=ROUTING_KEY_EXPORT_GENERATED,
            body=event.model_dump_json().encode("utf-8"),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Persistent
                content_type="application/json",
                message_id=str(event.event_id),
                timestamp=int(event.timestamp.timestamp()),
            ),
        )

        connection.close()

        logger.info(
            f"Emitted export generated event: export_id={export_id}, "
            f"map_id={map_id}, event_id={event.event_id}"
        )

    except Exception as e:
        logger.error(f"Failed to emit export generated event: {e}")
        raise
