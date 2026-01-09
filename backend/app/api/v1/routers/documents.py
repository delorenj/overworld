"""API router for document upload and management."""

from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_factory
from app.models import Document
from app.schemas import DocumentUploadResponse
from app.services import R2StorageError, get_r2_service
from app.utils import FileValidationError, get_mime_type, validate_file_size, validate_file_type

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload document",
    description="Upload a markdown or PDF document for map generation",
)
async def upload_document(
    file: UploadFile = File(..., description="Markdown or PDF file to upload"),
) -> DocumentUploadResponse:
    """
    Upload a document file (markdown or PDF).

    Validates file type via magic number (not extension), uploads to R2 storage,
    and returns document metadata with pre-signed URL for access.

    Args:
        file: Uploaded file (multipart/form-data)

    Returns:
        DocumentUploadResponse: Document metadata including pre-signed URL

    Raises:
        HTTPException: 400 Bad Request if file type invalid
        HTTPException: 413 Payload Too Large if file size exceeds limits
        HTTPException: 500 Internal Server Error if upload fails
    """
    # Read file content for validation
    file_content = await file.read()
    file_size = len(file_content)

    # Validate file type by magic number
    try:
        # Read first 512 bytes for magic number detection
        magic_bytes = file_content[:512]
        file_type = await validate_file_type(magic_bytes, file.filename or "unknown")
    except FileValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Validate file size
    try:
        await validate_file_size(file_size, file_type)
    except FileValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(e),
        )

    # Get MIME type
    mime_type = get_mime_type(file_type)

    # For now, use hardcoded user_id (will be replaced with actual auth in STORY-010)
    # TODO: Replace with actual authenticated user_id from JWT token
    user_id = 1  # Placeholder (matches User model Integer primary key)

    # Upload to R2
    r2_service = get_r2_service()

    try:
        r2_path, r2_url = await r2_service.upload_file(
            file_content=file_content,
            filename=file.filename or "unknown",
            user_id=user_id,
            mime_type=mime_type,
        )
    except R2StorageError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}",
        )

    # Create document record in database
    session_factory = get_session_factory()
    async with session_factory() as session:
        document = Document(
            user_id=user_id,
            filename=file.filename or "unknown",
            file_size_bytes=file_size,
            mime_type=mime_type,
            r2_path=r2_path,
            r2_url=r2_url,
            created_at=datetime.now(timezone.utc),
        )
        session.add(document)
        await session.commit()
        await session.refresh(document)

        # Return response
        return DocumentUploadResponse(
            document_id=document.id,
            filename=document.filename,
            size_bytes=document.file_size_bytes,
            r2_url=document.r2_url,
            uploaded_at=document.created_at,
        )
