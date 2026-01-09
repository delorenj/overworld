"""Integration tests for document upload endpoint."""

from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base, get_engine, get_session_factory
from app.main import app
from app.models import User


@pytest.fixture
async def db_session():
    """Provide a test database session."""
    engine = get_engine()
    session_factory = get_session_factory()

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Provide session
    async with session_factory() as session:
        yield session

    # Drop tables after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def test_user(db_session: AsyncSession):
    """Create a test user."""
    user = User(
        id=1,
        email="test@example.com",
        password_hash="hashed_password",
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def markdown_file():
    """Create a test markdown file."""
    content = b"# Test Document\n\nThis is a test markdown file."
    return BytesIO(content), "test.md", "text/markdown"


@pytest.fixture
def pdf_file():
    """Create a test PDF file."""
    content = b"%PDF-1.4\n%Test PDF content"
    return BytesIO(content), "test.pdf", "application/pdf"


@pytest.fixture
def invalid_file():
    """Create an invalid file (PNG)."""
    content = b"\x89PNG\r\n\x1a\n"  # PNG signature
    return BytesIO(content), "test.png", "image/png"


@pytest.fixture
def oversized_markdown():
    """Create an oversized markdown file (>5MB)."""
    content = b"# Large File\n" + b"x" * (6 * 1024 * 1024)  # 6 MB
    return BytesIO(content), "large.md", "text/markdown"


class TestDocumentUploadEndpoint:
    """Test document upload endpoint."""

    @pytest.mark.asyncio
    @patch("app.services.r2_storage.R2StorageService.upload_file")
    async def test_upload_markdown_success(self, mock_upload, markdown_file, test_user):
        """Test successful markdown file upload."""
        # Mock R2 upload
        mock_upload.return_value = ("uploads/test/file.md", "https://r2.example.com/file.md")

        file_content, filename, mime_type = markdown_file

        async with AsyncClient(app=app, base_url="http://test") as client:
            files = {"file": (filename, file_content, mime_type)}
            response = await client.post("/api/v1/documents/upload", files=files)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "document_id" in data
        assert data["filename"] == filename
        assert data["size_bytes"] > 0
        assert "r2_url" in data
        assert "uploaded_at" in data

    @pytest.mark.asyncio
    @patch("app.services.r2_storage.R2StorageService.upload_file")
    async def test_upload_pdf_success(self, mock_upload, pdf_file, test_user):
        """Test successful PDF file upload."""
        # Mock R2 upload
        mock_upload.return_value = ("uploads/test/file.pdf", "https://r2.example.com/file.pdf")

        file_content, filename, mime_type = pdf_file

        async with AsyncClient(app=app, base_url="http://test") as client:
            files = {"file": (filename, file_content, mime_type)}
            response = await client.post("/api/v1/documents/upload", files=files)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["filename"] == filename

    @pytest.mark.asyncio
    async def test_upload_invalid_file_type(self, invalid_file):
        """Test upload with invalid file type (should reject)."""
        file_content, filename, mime_type = invalid_file

        async with AsyncClient(app=app, base_url="http://test") as client:
            files = {"file": (filename, file_content, mime_type)}
            response = await client.post("/api/v1/documents/upload", files=files)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Unsupported file type" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_oversized_file(self, oversized_markdown):
        """Test upload with file exceeding size limit."""
        file_content, filename, mime_type = oversized_markdown

        async with AsyncClient(app=app, base_url="http://test") as client:
            files = {"file": (filename, file_content, mime_type)}
            response = await client.post("/api/v1/documents/upload", files=files)

        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        assert "exceeds maximum" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("app.services.r2_storage.R2StorageService.upload_file")
    async def test_upload_r2_failure_retry(self, mock_upload, markdown_file):
        """Test R2 upload failure and retry logic."""
        from app.services.r2_storage import R2StorageError

        # Mock R2 upload to fail
        mock_upload.side_effect = R2StorageError("Connection failed")

        file_content, filename, mime_type = markdown_file

        async with AsyncClient(app=app, base_url="http://test") as client:
            files = {"file": (filename, file_content, mime_type)}
            response = await client.post("/api/v1/documents/upload", files=files)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to upload file" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_missing_file(self):
        """Test upload without providing a file."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post("/api/v1/documents/upload")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    @patch("app.services.r2_storage.R2StorageService.upload_file")
    async def test_upload_empty_file(self, mock_upload):
        """Test upload with empty file."""
        empty_content = BytesIO(b"")

        async with AsyncClient(app=app, base_url="http://test") as client:
            files = {"file": ("empty.md", empty_content, "text/markdown")}
            response = await client.post("/api/v1/documents/upload", files=files)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
