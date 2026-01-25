"""Tests for WebSocket real-time progress endpoint.

Tests cover:
- WebSocket connection authentication
- Job access verification
- Connection lifecycle (connect, disconnect, reconnect)
- Progress event broadcasting
- Pub/sub message handling
- Error handling
"""

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocket
from fastapi.testclient import TestClient

from app.api.v1.routers.websocket import (
    WebSocketConnectionManager,
    authenticate_websocket,
    verify_job_access,
)
from app.core.pubsub import PubSubManager, get_job_channel
from app.main import app
from app.models.generation_job import GenerationJob, JobStatus
from app.models.user import User
from app.schemas.websocket import (
    ConnectionEstablishedEvent,
    JobCompletedEvent,
    JobFailedEvent,
    JobStartedEvent,
    ProgressUpdateEvent,
    WebSocketEventType,
    WebSocketMessage,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def test_user():
    """Create a test user."""
    return User(
        id=1,
        email="test@example.com",
        password_hash="hashed",
        is_verified=True,
        is_premium=False,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def test_job(test_user):
    """Create a test generation job."""
    job = GenerationJob(
        id=123,
        user_id=test_user.id,
        status=JobStatus.PROCESSING,
        progress_pct=50.0,
        progress_message="Processing...",
        created_at=datetime.now(timezone.utc),
    )
    return job


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = AsyncMock()
    return db


@pytest.fixture
def connection_manager():
    """Create a fresh connection manager."""
    return WebSocketConnectionManager()


@pytest.fixture
def pubsub_manager():
    """Create a pub/sub manager."""
    return PubSubManager()


# =============================================================================
# Unit Tests - Channel Naming
# =============================================================================


class TestChannelNaming:
    """Test Redis channel naming."""

    def test_get_job_channel(self):
        """Test channel name format."""
        channel = get_job_channel(123)
        assert channel == "job:progress:123"

    def test_get_job_channel_different_ids(self):
        """Test different job IDs produce different channels."""
        channel1 = get_job_channel(1)
        channel2 = get_job_channel(2)
        assert channel1 != channel2
        assert "job:progress:1" == channel1
        assert "job:progress:2" == channel2


# =============================================================================
# Unit Tests - WebSocket Event Schemas
# =============================================================================


class TestWebSocketEventSchemas:
    """Test WebSocket event schema creation."""

    def test_connection_established_event(self):
        """Test ConnectionEstablishedEvent creation."""
        event = ConnectionEstablishedEvent(
            job_id=123,
            current_status=JobStatus.PROCESSING,
            current_progress=50.0,
        )
        assert event.type == WebSocketEventType.CONNECTION_ESTABLISHED
        assert event.job_id == 123
        assert event.current_status == JobStatus.PROCESSING
        assert event.current_progress == 50.0
        assert event.timestamp is not None

    def test_job_started_event(self):
        """Test JobStartedEvent creation."""
        started_at = datetime.now(timezone.utc)
        event = JobStartedEvent(
            job_id=123,
            started_at=started_at,
            agent_name="parser",
        )
        assert event.type == WebSocketEventType.JOB_STARTED
        assert event.job_id == 123
        assert event.started_at == started_at
        assert event.agent_name == "parser"

    def test_progress_update_event(self):
        """Test ProgressUpdateEvent creation."""
        event = ProgressUpdateEvent(
            job_id=123,
            progress_pct=75.5,
            progress_message="Building roads...",
            agent_name="road",
            stage="spline_generation",
        )
        assert event.type == WebSocketEventType.PROGRESS_UPDATE
        assert event.progress_pct == 75.5
        assert event.progress_message == "Building roads..."
        assert event.agent_name == "road"
        assert event.stage == "spline_generation"

    def test_progress_update_event_clamped(self):
        """Test progress percentage is validated."""
        # Valid range
        event = ProgressUpdateEvent(job_id=1, progress_pct=0.0)
        assert event.progress_pct == 0.0

        event = ProgressUpdateEvent(job_id=1, progress_pct=100.0)
        assert event.progress_pct == 100.0

        # Invalid range should raise
        with pytest.raises(ValueError):
            ProgressUpdateEvent(job_id=1, progress_pct=-1.0)

        with pytest.raises(ValueError):
            ProgressUpdateEvent(job_id=1, progress_pct=101.0)

    def test_job_completed_event(self):
        """Test JobCompletedEvent creation."""
        completed_at = datetime.now(timezone.utc)
        event = JobCompletedEvent(
            job_id=123,
            completed_at=completed_at,
            map_id=456,
            total_duration_seconds=30.5,
        )
        assert event.type == WebSocketEventType.JOB_COMPLETED
        assert event.job_id == 123
        assert event.map_id == 456
        assert event.total_duration_seconds == 30.5

    def test_job_failed_event(self):
        """Test JobFailedEvent creation."""
        failed_at = datetime.now(timezone.utc)
        event = JobFailedEvent(
            job_id=123,
            error_message="Processing failed",
            error_code="PROCESSING_ERROR",
            can_retry=True,
            retry_count=1,
            max_retries=3,
            failed_at=failed_at,
        )
        assert event.type == WebSocketEventType.JOB_FAILED
        assert event.error_message == "Processing failed"
        assert event.error_code == "PROCESSING_ERROR"
        assert event.can_retry is True
        assert event.retry_count == 1
        assert event.max_retries == 3

    def test_websocket_message_from_event(self):
        """Test WebSocketMessage creation from event."""
        event = ProgressUpdateEvent(
            job_id=123,
            progress_pct=50.0,
        )
        message = WebSocketMessage.from_event(event, correlation_id="test-123")

        assert message.correlation_id == "test-123"
        assert message.event["type"] == "progress_update"
        assert message.event["job_id"] == 123
        assert message.event["progress_pct"] == 50.0


# =============================================================================
# Unit Tests - Connection Manager
# =============================================================================


class TestConnectionManager:
    """Test WebSocket connection manager."""

    @pytest.mark.asyncio
    async def test_connect(self, connection_manager):
        """Test adding a connection."""
        mock_ws = AsyncMock(spec=WebSocket)

        await connection_manager.connect(mock_ws, job_id=123)

        assert connection_manager.get_connection_count(123) == 1
        mock_ws.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_multiple(self, connection_manager):
        """Test multiple connections to same job."""
        mock_ws1 = AsyncMock(spec=WebSocket)
        mock_ws2 = AsyncMock(spec=WebSocket)

        await connection_manager.connect(mock_ws1, job_id=123)
        await connection_manager.connect(mock_ws2, job_id=123)

        assert connection_manager.get_connection_count(123) == 2

    @pytest.mark.asyncio
    async def test_disconnect(self, connection_manager):
        """Test removing a connection."""
        mock_ws = AsyncMock(spec=WebSocket)

        await connection_manager.connect(mock_ws, job_id=123)
        connection_manager.disconnect(mock_ws, job_id=123)

        assert connection_manager.get_connection_count(123) == 0

    @pytest.mark.asyncio
    async def test_disconnect_cleans_up_empty_list(self, connection_manager):
        """Test that empty connection lists are removed."""
        mock_ws = AsyncMock(spec=WebSocket)

        await connection_manager.connect(mock_ws, job_id=123)
        connection_manager.disconnect(mock_ws, job_id=123)

        assert 123 not in connection_manager.active_connections

    @pytest.mark.asyncio
    async def test_send_event_success(self, connection_manager):
        """Test sending event to connection."""
        mock_ws = AsyncMock(spec=WebSocket)

        result = await connection_manager.send_event(mock_ws, {"test": "data"})

        assert result is True
        mock_ws.send_json.assert_called_once_with({"test": "data"})

    @pytest.mark.asyncio
    async def test_send_event_failure(self, connection_manager):
        """Test handling send failure."""
        mock_ws = AsyncMock(spec=WebSocket)
        mock_ws.send_json.side_effect = Exception("Connection closed")

        result = await connection_manager.send_event(mock_ws, {"test": "data"})

        assert result is False

    def test_get_connection_count_empty(self, connection_manager):
        """Test connection count for non-existent job."""
        assert connection_manager.get_connection_count(999) == 0


# =============================================================================
# Unit Tests - Authentication
# =============================================================================


class TestWebSocketAuthentication:
    """Test WebSocket authentication."""

    @pytest.mark.asyncio
    async def test_authenticate_missing_token(self, mock_db):
        """Test authentication without token."""
        is_valid, user_id, error = await authenticate_websocket(None, mock_db)

        assert is_valid is False
        assert user_id is None
        assert "Missing" in error

    @pytest.mark.asyncio
    @patch("app.api.v1.routers.websocket.AuthService")
    async def test_authenticate_valid_token(self, mock_auth_class, mock_db, test_user):
        """Test authentication with valid token."""
        mock_auth = AsyncMock()
        mock_auth.validate_access_token.return_value = test_user
        mock_auth_class.return_value = mock_auth

        is_valid, user_id, error = await authenticate_websocket("valid_token", mock_db)

        assert is_valid is True
        assert user_id == test_user.id
        assert error is None

    @pytest.mark.asyncio
    @patch("app.api.v1.routers.websocket.AuthService")
    async def test_authenticate_invalid_token(self, mock_auth_class, mock_db):
        """Test authentication with invalid token."""
        from app.services.auth_service import InvalidTokenError

        mock_auth = AsyncMock()
        mock_auth.validate_access_token.side_effect = InvalidTokenError("Invalid token")
        mock_auth_class.return_value = mock_auth

        is_valid, user_id, error = await authenticate_websocket("invalid_token", mock_db)

        assert is_valid is False
        assert user_id is None
        assert "Invalid" in error

    @pytest.mark.asyncio
    @patch("app.api.v1.routers.websocket.AuthService")
    async def test_authenticate_revoked_token(self, mock_auth_class, mock_db):
        """Test authentication with revoked token."""
        from app.services.auth_service import TokenRevokedError

        mock_auth = AsyncMock()
        mock_auth.validate_access_token.side_effect = TokenRevokedError("Token revoked")
        mock_auth_class.return_value = mock_auth

        is_valid, user_id, error = await authenticate_websocket("revoked_token", mock_db)

        assert is_valid is False
        assert user_id is None
        assert "revoked" in error


# =============================================================================
# Unit Tests - Job Access Verification
# =============================================================================


class TestJobAccessVerification:
    """Test job access verification."""

    @pytest.mark.asyncio
    async def test_verify_job_access_success(self, mock_db, test_user, test_job):
        """Test successful job access verification."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = test_job
        mock_db.execute.return_value = mock_result

        has_access, job, error = await verify_job_access(
            job_id=test_job.id,
            user_id=test_user.id,
            db=mock_db,
        )

        assert has_access is True
        assert job == test_job
        assert error is None

    @pytest.mark.asyncio
    async def test_verify_job_access_not_found(self, mock_db, test_user):
        """Test job access when job not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        has_access, job, error = await verify_job_access(
            job_id=999,
            user_id=test_user.id,
            db=mock_db,
        )

        assert has_access is False
        assert job is None
        assert "not found" in error

    @pytest.mark.asyncio
    async def test_verify_job_access_different_user(self, mock_db, test_user, test_job):
        """Test job access when user doesn't own job."""
        # Job belongs to user 1, but we're checking with user 2
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # Query won't find it
        mock_db.execute.return_value = mock_result

        has_access, job, error = await verify_job_access(
            job_id=test_job.id,
            user_id=99,  # Different user
            db=mock_db,
        )

        assert has_access is False
        assert job is None


# =============================================================================
# Unit Tests - PubSub Manager
# =============================================================================


class TestPubSubManager:
    """Test Redis pub/sub manager."""

    @pytest.mark.asyncio
    @patch.object(PubSubManager, "get_client")
    async def test_publish_event(self, mock_get_client, pubsub_manager):
        """Test publishing an event."""
        mock_redis = AsyncMock()
        mock_redis.publish.return_value = 1
        mock_get_client.return_value = mock_redis

        event = ProgressUpdateEvent(job_id=123, progress_pct=50.0)
        result = await pubsub_manager.publish_event(123, event)

        assert result == 1
        mock_redis.publish.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(PubSubManager, "get_client")
    async def test_publish_job_started(self, mock_get_client, pubsub_manager):
        """Test publishing job started event."""
        mock_redis = AsyncMock()
        mock_redis.publish.return_value = 2
        mock_get_client.return_value = mock_redis

        started_at = datetime.now(timezone.utc)
        result = await pubsub_manager.publish_job_started(
            job_id=123,
            started_at=started_at,
            agent_name="parser",
        )

        assert result == 2
        mock_redis.publish.assert_called_once()

        # Verify the published message
        call_args = mock_redis.publish.call_args
        channel = call_args[0][0]
        message_json = call_args[0][1]

        assert channel == "job:progress:123"
        message = json.loads(message_json)
        assert message["event"]["type"] == "job_started"
        assert message["event"]["job_id"] == 123

    @pytest.mark.asyncio
    @patch.object(PubSubManager, "get_client")
    async def test_publish_progress(self, mock_get_client, pubsub_manager):
        """Test publishing progress update."""
        mock_redis = AsyncMock()
        mock_redis.publish.return_value = 1
        mock_get_client.return_value = mock_redis

        result = await pubsub_manager.publish_progress(
            job_id=123,
            progress_pct=75.0,
            progress_message="Building roads...",
            agent_name="road",
        )

        assert result == 1
        call_args = mock_redis.publish.call_args
        message = json.loads(call_args[0][1])
        assert message["event"]["type"] == "progress_update"
        assert message["event"]["progress_pct"] == 75.0

    @pytest.mark.asyncio
    @patch.object(PubSubManager, "get_client")
    async def test_publish_job_completed(self, mock_get_client, pubsub_manager):
        """Test publishing job completed event."""
        mock_redis = AsyncMock()
        mock_redis.publish.return_value = 1
        mock_get_client.return_value = mock_redis

        completed_at = datetime.now(timezone.utc)
        result = await pubsub_manager.publish_job_completed(
            job_id=123,
            completed_at=completed_at,
            map_id=456,
            total_duration_seconds=30.5,
        )

        assert result == 1
        call_args = mock_redis.publish.call_args
        message = json.loads(call_args[0][1])
        assert message["event"]["type"] == "job_completed"
        assert message["event"]["map_id"] == 456

    @pytest.mark.asyncio
    @patch.object(PubSubManager, "get_client")
    async def test_publish_job_failed(self, mock_get_client, pubsub_manager):
        """Test publishing job failed event."""
        mock_redis = AsyncMock()
        mock_redis.publish.return_value = 1
        mock_get_client.return_value = mock_redis

        failed_at = datetime.now(timezone.utc)
        result = await pubsub_manager.publish_job_failed(
            job_id=123,
            error_message="Test error",
            failed_at=failed_at,
            error_code="TEST_ERROR",
            can_retry=True,
            retry_count=1,
            max_retries=3,
        )

        assert result == 1
        call_args = mock_redis.publish.call_args
        message = json.loads(call_args[0][1])
        assert message["event"]["type"] == "job_failed"
        assert message["event"]["error_message"] == "Test error"
        assert message["event"]["can_retry"] is True


# =============================================================================
# Integration Tests - WebSocket Endpoint
# =============================================================================


class TestWebSocketEndpoint:
    """Integration tests for WebSocket endpoint."""

    def test_websocket_missing_token(self):
        """Test WebSocket connection without token is rejected."""
        client = TestClient(app)

        with pytest.raises(Exception):
            # Should fail because no token provided
            with client.websocket_connect("/api/v1/ws/jobs/123"):
                pass

    @patch("app.api.v1.routers.websocket.authenticate_websocket")
    @patch("app.api.v1.routers.websocket.verify_job_access")
    @patch("app.api.v1.routers.websocket.get_async_session")
    def test_websocket_auth_failure(
        self,
        mock_get_session,
        mock_verify_access,
        mock_authenticate,
    ):
        """Test WebSocket connection with invalid auth is rejected."""
        # Mock authentication to fail
        mock_authenticate.return_value = (False, None, "Invalid token")
        mock_get_session.return_value.__aenter__ = AsyncMock()
        mock_get_session.return_value.__aexit__ = AsyncMock()

        client = TestClient(app)

        with client.websocket_connect(
            "/api/v1/ws/jobs/123?token=invalid"
        ) as websocket:
            # Should receive error event and then close
            data = websocket.receive_json()
            assert data["event"]["type"] == "connection_error"
            assert data["event"]["error_code"] == "AUTH_FAILED"


# =============================================================================
# Schema Serialization Tests
# =============================================================================


class TestSchemaSerialization:
    """Test that schemas serialize correctly for WebSocket transmission."""

    def test_connection_established_serialization(self):
        """Test ConnectionEstablishedEvent JSON serialization."""
        event = ConnectionEstablishedEvent(
            job_id=123,
            current_status=JobStatus.PROCESSING,
            current_progress=50.0,
        )
        message = WebSocketMessage.from_event(event)
        json_str = message.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["event"]["type"] == "connection_established"
        assert parsed["event"]["job_id"] == 123
        assert parsed["event"]["current_status"] == "processing"
        assert parsed["event"]["current_progress"] == 50.0

    def test_progress_update_serialization(self):
        """Test ProgressUpdateEvent JSON serialization."""
        event = ProgressUpdateEvent(
            job_id=123,
            progress_pct=75.5,
            progress_message="Building roads...",
            agent_name="road",
        )
        message = WebSocketMessage.from_event(event)
        json_str = message.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["event"]["type"] == "progress_update"
        assert parsed["event"]["progress_pct"] == 75.5
        assert parsed["event"]["progress_message"] == "Building roads..."

    def test_job_failed_serialization(self):
        """Test JobFailedEvent JSON serialization."""
        event = JobFailedEvent(
            job_id=123,
            error_message="Test error",
            error_code="TEST_ERROR",
            can_retry=True,
            retry_count=1,
            max_retries=3,
            failed_at=datetime.now(timezone.utc),
        )
        message = WebSocketMessage.from_event(event, correlation_id="test-corr-123")
        json_str = message.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["event"]["type"] == "job_failed"
        assert parsed["event"]["can_retry"] is True
        assert parsed["correlation_id"] == "test-corr-123"
