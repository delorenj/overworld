"""Integration tests for document upload endpoint."""

from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient
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
    @patch("app.api.v1.routers.documents.get_r2_service")
    async def test_upload_markdown_success(self, mock_get_r2, markdown_file, test_user):
        """Test successful markdown file upload."""
        # Mock R2 service
        mock_r2 = MagicMock()
        mock_r2.upload_file = AsyncMock(
            return_value=("uploads/test/file.md", "https://r2.example.com/file.md")
        )
        mock_get_r2.return_value = mock_r2

        file_content, filename, mime_type = markdown_file

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            files = {"file": (filename, file_content, mime_type)}
            response = await client.post("/api/v1/documents/upload", files=files)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "document_id" in data
        assert data["filename"] == filename
        assert data["size_bytes"] > 0
        assert "r2_url" in data
        assert "uploaded_at" in data
        assert "content_hash" in data
        assert "status" in data
        assert data["status"] == "uploaded"

    @pytest.mark.asyncio
    @patch("app.api.v1.routers.documents.get_r2_service")
    async def test_upload_pdf_success(self, mock_get_r2, pdf_file, test_user):
        """Test successful PDF file upload."""
        # Mock R2 service
        mock_r2 = MagicMock()
        mock_r2.upload_file = AsyncMock(
            return_value=("uploads/test/file.pdf", "https://r2.example.com/file.pdf")
        )
        mock_get_r2.return_value = mock_r2

        file_content, filename, mime_type = pdf_file

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            files = {"file": (filename, file_content, mime_type)}
            response = await client.post("/api/v1/documents/upload", files=files)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["filename"] == filename
        assert data["mime_type"] == "application/pdf"

    @pytest.mark.asyncio
    async def test_upload_invalid_file_type(self, invalid_file):
        """Test upload with invalid file type (should reject)."""
        file_content, filename, mime_type = invalid_file

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            files = {"file": (filename, file_content, mime_type)}
            response = await client.post("/api/v1/documents/upload", files=files)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Unsupported file type" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_oversized_file(self, oversized_markdown):
        """Test upload with file exceeding size limit."""
        file_content, filename, mime_type = oversized_markdown

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            files = {"file": (filename, file_content, mime_type)}
            response = await client.post("/api/v1/documents/upload", files=files)

        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        assert "exceeds maximum" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("app.api.v1.routers.documents.get_r2_service")
    async def test_upload_r2_failure(self, mock_get_r2, markdown_file):
        """Test R2 upload failure."""
        from app.services.r2_storage import R2StorageError

        # Mock R2 service to fail
        mock_r2 = MagicMock()
        mock_r2.upload_file = AsyncMock(side_effect=R2StorageError("Connection failed"))
        mock_get_r2.return_value = mock_r2

        file_content, filename, mime_type = markdown_file

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            files = {"file": (filename, file_content, mime_type)}
            response = await client.post("/api/v1/documents/upload", files=files)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to upload file" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_missing_file(self):
        """Test upload without providing a file."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/documents/upload")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_upload_empty_file(self):
        """Test upload with empty file."""
        empty_content = BytesIO(b"")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            files = {"file": ("empty.md", empty_content, "text/markdown")}
            response = await client.post("/api/v1/documents/upload", files=files)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Empty file" in response.json()["detail"]


class TestDocumentCRUDEndpoints:
    """Test document CRUD endpoints."""

    @pytest.mark.asyncio
    @patch("app.api.v1.routers.documents.get_r2_service")
    async def test_list_documents(self, mock_get_r2, test_user):
        """Test listing documents."""
        # Mock R2 service
        mock_r2 = MagicMock()
        mock_r2.generate_presigned_url = AsyncMock(return_value="https://r2.example.com/signed")
        mock_get_r2.return_value = mock_r2

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/documents")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "documents" in data
        assert "total" in data
        assert "skip" in data
        assert "limit" in data

    @pytest.mark.asyncio
    async def test_get_document_not_found(self):
        """Test getting a non-existent document."""
        doc_id = str(uuid4())

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/documents/{doc_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_document_not_found(self):
        """Test deleting a non-existent document."""
        doc_id = str(uuid4())

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(f"/api/v1/documents/{doc_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_download_url_not_found(self):
        """Test getting download URL for non-existent document."""
        doc_id = str(uuid4())

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/documents/{doc_id}/download-url")

        assert response.status_code == status.HTTP_404_NOT_FOUND
