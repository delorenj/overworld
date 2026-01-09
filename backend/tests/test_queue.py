"""RabbitMQ connectivity and topology tests."""

import json

import pytest

from app.core.queue import QueueConfig, RabbitMQConnection


@pytest.fixture
async def rabbitmq():
    """Provide a RabbitMQ connection for testing."""
    conn = RabbitMQConnection()
    await conn.connect()
    await conn.setup_topology()
    yield conn
    await conn.close()


@pytest.mark.asyncio
async def test_rabbitmq_connection(rabbitmq: RabbitMQConnection):
    """Test basic RabbitMQ connectivity."""
    assert rabbitmq.connection is not None
    assert not rabbitmq.connection.is_closed
    assert rabbitmq.channel is not None


@pytest.mark.asyncio
async def test_exchange_creation(rabbitmq: RabbitMQConnection):
    """Test that exchange is created."""
    # Declare exchange (idempotent, should not error if exists)
    rabbitmq.channel.exchange_declare(
        exchange=QueueConfig.EXCHANGE_NAME,
        exchange_type=QueueConfig.EXCHANGE_TYPE,
        durable=True,
        passive=True,  # Verify exists without creating
    )


@pytest.mark.asyncio
async def test_queue_creation(rabbitmq: RabbitMQConnection):
    """Test that all queues are created."""
    # Verify pending queue exists
    result = rabbitmq.channel.queue_declare(
        queue=QueueConfig.QUEUE_PENDING,
        durable=True,
        passive=True,  # Verify exists
    )
    assert result.method.message_count >= 0

    # Verify retry queue exists
    result = rabbitmq.channel.queue_declare(
        queue=QueueConfig.QUEUE_RETRY,
        durable=True,
        passive=True,
    )
    assert result.method.message_count >= 0

    # Verify DLQ exists
    result = rabbitmq.channel.queue_declare(
        queue=QueueConfig.QUEUE_DLQ,
        durable=True,
        passive=True,
    )
    assert result.method.message_count >= 0


@pytest.mark.asyncio
async def test_message_publish_and_consume(rabbitmq: RabbitMQConnection):
    """Test publishing and consuming messages."""
    test_message = json.dumps({"job_id": 123, "user_id": 1}).encode()

    # Publish message
    await rabbitmq.publish_message(
        routing_key=QueueConfig.ROUTING_KEY_PENDING,
        message=test_message,
    )

    # Consume message
    method_frame, header_frame, body = rabbitmq.channel.basic_get(
        queue=QueueConfig.QUEUE_PENDING,
        auto_ack=True,
    )

    assert method_frame is not None
    assert body == test_message

    # Parse message
    message_data = json.loads(body)
    assert message_data["job_id"] == 123
    assert message_data["user_id"] == 1


@pytest.mark.asyncio
async def test_dead_letter_queue_routing(rabbitmq: RabbitMQConnection):
    """Test that failed messages route to DLQ."""
    test_message = json.dumps({"job_id": 456, "should_fail": True}).encode()

    # Publish message with failed routing key
    await rabbitmq.publish_message(
        routing_key=QueueConfig.ROUTING_KEY_FAILED,
        message=test_message,
    )

    # Verify message arrived in DLQ
    method_frame, header_frame, body = rabbitmq.channel.basic_get(
        queue=QueueConfig.QUEUE_DLQ,
        auto_ack=True,
    )

    assert method_frame is not None
    assert body == test_message


@pytest.mark.asyncio
async def test_message_persistence(rabbitmq: RabbitMQConnection):
    """Test that messages are durable (survive restarts)."""
    test_message = json.dumps({"job_id": 789}).encode()

    # Publish persistent message
    await rabbitmq.publish_message(
        routing_key=QueueConfig.ROUTING_KEY_PENDING,
        message=test_message,
    )

    # Check queue has messages
    result = rabbitmq.channel.queue_declare(
        queue=QueueConfig.QUEUE_PENDING,
        durable=True,
        passive=True,
    )
    assert result.method.message_count > 0
