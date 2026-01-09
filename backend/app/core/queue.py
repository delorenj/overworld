"""RabbitMQ queue configuration and topology setup."""

import asyncio
from typing import Optional

import pika
from pika.adapters.asyncio_connection import AsyncioConnection
from pika.channel import Channel

from app.core.config import settings


class QueueConfig:
    """RabbitMQ topology configuration."""

    # Exchange configuration
    EXCHANGE_NAME = "generation"
    EXCHANGE_TYPE = "topic"

    # Queue names
    QUEUE_PENDING = "generation.pending"
    QUEUE_RETRY = "generation.retry"
    QUEUE_DLQ = "generation.dlq"  # Dead Letter Queue

    # Routing keys
    ROUTING_KEY_PENDING = "generation.pending"
    ROUTING_KEY_RETRY = "generation.retry"
    ROUTING_KEY_FAILED = "generation.failed"


class RabbitMQConnection:
    """
    RabbitMQ connection manager.

    Handles connection pooling and topology setup.
    """

    def __init__(self):
        self.connection: Optional[AsyncioConnection] = None
        self.channel: Optional[Channel] = None
        self.params = pika.URLParameters(settings.RABBITMQ_URL)

    async def connect(self) -> None:
        """Establish connection to RabbitMQ."""
        if self.connection and not self.connection.is_closed:
            return

        loop = asyncio.get_event_loop()
        self.connection = await loop.run_in_executor(
            None, pika.BlockingConnection, self.params
        )
        self.channel = self.connection.channel()

    async def setup_topology(self) -> None:
        """
        Create exchanges, queues, and bindings.

        Topology:
        - Exchange: 'generation' (topic)
        - Queues:
          - generation.pending: Main processing queue
          - generation.retry: Retry queue with TTL
          - generation.dlq: Dead letter queue for failed messages
        - Bindings:
          - pending queue bound to 'generation.pending' routing key
          - retry queue bound to 'generation.retry' routing key
          - DLQ bound to 'generation.failed' routing key
        """
        await self.connect()

        # Declare topic exchange
        self.channel.exchange_declare(
            exchange=QueueConfig.EXCHANGE_NAME,
            exchange_type=QueueConfig.EXCHANGE_TYPE,
            durable=True,
        )

        # Declare pending queue (main processing queue)
        self.channel.queue_declare(
            queue=QueueConfig.QUEUE_PENDING,
            durable=True,
            arguments={
                "x-dead-letter-exchange": QueueConfig.EXCHANGE_NAME,
                "x-dead-letter-routing-key": QueueConfig.ROUTING_KEY_FAILED,
            },
        )

        # Declare retry queue (with message TTL for delayed retry)
        self.channel.queue_declare(
            queue=QueueConfig.QUEUE_RETRY,
            durable=True,
            arguments={
                "x-message-ttl": 60000,  # 60 seconds TTL
                "x-dead-letter-exchange": QueueConfig.EXCHANGE_NAME,
                "x-dead-letter-routing-key": QueueConfig.ROUTING_KEY_PENDING,
            },
        )

        # Declare dead letter queue (for permanently failed messages)
        self.channel.queue_declare(
            queue=QueueConfig.QUEUE_DLQ,
            durable=True,
        )

        # Bind queues to exchange with routing keys
        self.channel.queue_bind(
            exchange=QueueConfig.EXCHANGE_NAME,
            queue=QueueConfig.QUEUE_PENDING,
            routing_key=QueueConfig.ROUTING_KEY_PENDING,
        )

        self.channel.queue_bind(
            exchange=QueueConfig.EXCHANGE_NAME,
            queue=QueueConfig.QUEUE_RETRY,
            routing_key=QueueConfig.ROUTING_KEY_RETRY,
        )

        self.channel.queue_bind(
            exchange=QueueConfig.EXCHANGE_NAME,
            queue=QueueConfig.QUEUE_DLQ,
            routing_key=QueueConfig.ROUTING_KEY_FAILED,
        )

    async def publish_message(
        self,
        routing_key: str,
        message: bytes,
        properties: Optional[pika.BasicProperties] = None,
    ) -> None:
        """
        Publish a message to the exchange.

        Args:
            routing_key: Routing key (e.g., 'generation.pending')
            message: Message body as bytes
            properties: Optional message properties (delivery_mode, etc.)
        """
        await self.connect()

        if properties is None:
            properties = pika.BasicProperties(
                delivery_mode=2,  # Persistent
                content_type="application/json",
            )

        self.channel.basic_publish(
            exchange=QueueConfig.EXCHANGE_NAME,
            routing_key=routing_key,
            body=message,
            properties=properties,
        )

    async def close(self) -> None:
        """Close RabbitMQ connection."""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            self.connection = None
            self.channel = None


# Global RabbitMQ connection instance
rabbitmq = RabbitMQConnection()


async def get_rabbitmq() -> RabbitMQConnection:
    """Dependency for FastAPI routes to get RabbitMQ connection."""
    await rabbitmq.connect()
    return rabbitmq


async def init_queue() -> None:
    """Initialize RabbitMQ topology (run on startup)."""
    await rabbitmq.setup_topology()


async def close_queue() -> None:
    """Close RabbitMQ connection (run on shutdown)."""
    await rabbitmq.close()
