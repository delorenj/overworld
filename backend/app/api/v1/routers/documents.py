"""API router for document upload and management."""

import hashlib
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, get_session_factory
from app.models import Document
from app.models.document import DocumentStatus
from app.schemas.document import (
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadResponse,
)
from app.schemas.hierarchy import (
    HierarchyExtractionResponse,
)
from app.services import R2StorageError, get_r2_service
from app.services.hierarchy_extraction import (
    get_hierarchy_extraction_service,
)
from app.utils import FileValidationError, get_mime_type, validate_file_size, validate_file_type

router = APIRouter(prefix="/documents", tags=["documents"])


def compute_content_hash(content: bytes) -> str:
    """Compute SHA-256 hash of file content for deduplication."""
    return hashlib.sha256(content).hexdigest()


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
        HTTPException: 400 Bad Request if file type invalid or empty file
        HTTPException: 413 Payload Too Large if file size exceeds limits
        HTTPException: 500 Internal Server Error if upload fails
    """
    # Read file content for validation
    file_content = await file.read()
    file_size = len(file_content)

    # Check for empty file
    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file provided. Please upload a non-empty file.",
        )

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

    # Get MIME type and compute content hash
    mime_type = get_mime_type(file_type)
    content_hash = compute_content_hash(file_content)

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
            content_hash=content_hash,
            status=DocumentStatus.UPLOADED,
            created_at=datetime.now(UTC),
        )
        session.add(document)
        await session.commit()
        await session.refresh(document)

        # Return response
        return DocumentUploadResponse(
            document_id=document.id,
            filename=document.filename,
            size_bytes=document.file_size_bytes,
            mime_type=document.mime_type,
            content_hash=document.content_hash,
            status=document.status.value,
            r2_url=document.r2_url,
            uploaded_at=document.created_at,
        )


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List documents",
    description="Get a paginated list of documents for the current user",
)
async def list_documents(
    skip: int = Query(0, ge=0, description="Number of documents to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of documents to return"),
    status_filter: str | None = Query(None, description="Filter by document status"),
    db: AsyncSession = Depends(get_db),
) -> DocumentListResponse:
    """
    List documents for the current user with pagination.

    Args:
        skip: Number of documents to skip (for pagination)
        limit: Maximum number of documents to return
        status_filter: Optional filter by document status
        db: Database session

    Returns:
        DocumentListResponse: List of documents with pagination info
    """
    # TODO: Replace with actual authenticated user_id from JWT token
    user_id = 1  # Placeholder

    # Build query
    query = select(Document).where(Document.user_id == user_id)

    # Apply status filter if provided
    if status_filter:
        try:
            status_enum = DocumentStatus(status_filter)
            query = query.where(Document.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status filter. Valid values: {[s.value for s in DocumentStatus]}",
            )

    # Get total count
    count_query = select(Document.id).where(Document.user_id == user_id)
    if status_filter:
        count_query = count_query.where(Document.status == DocumentStatus(status_filter))
    count_result = await db.execute(count_query)
    total = len(count_result.all())

    # Apply pagination and ordering
    query = query.order_by(Document.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    documents = result.scalars().all()

    # Generate fresh signed URLs for each document
    r2_service = get_r2_service()

    document_responses = []
    for doc in documents:
        try:
            fresh_url = await r2_service.generate_presigned_url(
                bucket_name=r2_service.client.meta.endpoint_url.split("//")[1].split(".")[0]
                if hasattr(r2_service.client, "meta")
                else "overworld",
                r2_path=doc.r2_path,
            )
        except Exception:
            fresh_url = doc.r2_url  # Fallback to stored URL

        document_responses.append(
            DocumentResponse(
                id=doc.id,
                user_id=doc.user_id,
                filename=doc.filename,
                file_size_bytes=doc.file_size_bytes,
                mime_type=doc.mime_type,
                content_hash=doc.content_hash,
                status=doc.status.value,
                r2_path=doc.r2_path,
                r2_url=fresh_url,
                created_at=doc.created_at,
                processed_at=doc.processed_at,
            )
        )

    return DocumentListResponse(
        documents=document_responses,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get document",
    description="Get document metadata by ID",
)
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """
    Get document metadata by ID.

    Args:
        document_id: Document UUID
        db: Database session

    Returns:
        DocumentResponse: Document metadata

    Raises:
        HTTPException: 404 if document not found
    """
    # TODO: Replace with actual authenticated user_id from JWT token
    user_id = 1  # Placeholder

    query = select(Document).where(
        Document.id == document_id,
        Document.user_id == user_id,
    )
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found",
        )

    # Generate fresh signed URL
    r2_service = get_r2_service()
    try:
        from app.core.config import settings

        fresh_url = await r2_service.generate_presigned_url(
            bucket_name=settings.R2_BUCKET_UPLOADS,
            r2_path=document.r2_path,
        )
    except Exception:
        fresh_url = document.r2_url  # Fallback to stored URL

    return DocumentResponse(
        id=document.id,
        user_id=document.user_id,
        filename=document.filename,
        file_size_bytes=document.file_size_bytes,
        mime_type=document.mime_type,
        content_hash=document.content_hash,
        status=document.status.value,
        r2_path=document.r2_path,
        r2_url=fresh_url,
        created_at=document.created_at,
        processed_at=document.processed_at,
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete document",
    description="Delete a document and its associated file from storage",
)
async def delete_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a document and its associated file from storage.

    Args:
        document_id: Document UUID
        db: Database session

    Raises:
        HTTPException: 404 if document not found
        HTTPException: 500 if deletion from storage fails
    """
    # TODO: Replace with actual authenticated user_id from JWT token
    user_id = 1  # Placeholder

    query = select(Document).where(
        Document.id == document_id,
        Document.user_id == user_id,
    )
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found",
        )

    # Delete file from R2 storage
    r2_service = get_r2_service()
    try:
        from app.core.config import settings

        await r2_service.delete_file(
            bucket_name=settings.R2_BUCKET_UPLOADS,
            r2_path=document.r2_path,
        )
    except R2StorageError:
        # Log the error but continue with database deletion
        # The file might already be deleted or inaccessible
        pass

    # Delete document record from database
    await db.delete(document)
    await db.commit()


@router.get(
    "/{document_id}/download-url",
    summary="Get download URL",
    description="Generate a fresh pre-signed URL for downloading the document",
)
async def get_download_url(
    document_id: UUID,
    expiry_seconds: int = Query(3600, ge=60, le=86400, description="URL expiry time in seconds"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Generate a fresh pre-signed URL for downloading the document.

    Args:
        document_id: Document UUID
        expiry_seconds: URL expiry time in seconds (default: 1 hour, max: 24 hours)
        db: Database session

    Returns:
        dict: Contains download_url and expiry_seconds

    Raises:
        HTTPException: 404 if document not found
        HTTPException: 500 if URL generation fails
    """
    # TODO: Replace with actual authenticated user_id from JWT token
    user_id = 1  # Placeholder

    query = select(Document).where(
        Document.id == document_id,
        Document.user_id == user_id,
    )
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found",
        )

    # Generate fresh signed URL with custom expiry
    r2_service = get_r2_service()
    try:
        from app.core.config import settings

        download_url = await r2_service.generate_presigned_url(
            bucket_name=settings.R2_BUCKET_UPLOADS,
            r2_path=document.r2_path,
            expiry_seconds=expiry_seconds,
        )
    except R2StorageError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate download URL: {str(e)}",
        )

    return {
        "document_id": str(document_id),
        "filename": document.filename,
        "download_url": download_url,
        "expiry_seconds": expiry_seconds,
    }


@router.post(
    "/{document_id}/extract-hierarchy",
    response_model=HierarchyExtractionResponse,
    summary="Extract hierarchy from document",
    description="Extract hierarchical structure (L0-L4) from a document for map generation",
)
async def extract_hierarchy(
    document_id: UUID,
    force_reprocess: bool = Query(
        False, description="Force re-extraction even if already processed"
    ),
    use_ai_fallback: bool = Query(
        True, description="Use AI inference if structured extraction fails"
    ),
    db: AsyncSession = Depends(get_db),
) -> HierarchyExtractionResponse:
    """
    Extract hierarchical structure from a document.

    This endpoint extracts the document structure into L0-L4 levels:
    - L0: Document root
    - L1: Main sections/milestones
    - L2: Subsections/epics
    - L3: Details/tasks
    - L4: Fine-grained elements/subtasks

    The extraction method depends on the document type:
    - Markdown: Parses heading hierarchy (#, ##, ###, etc.)
    - PDF: Extracts TOC/bookmarks or infers from text structure
    - Fallback: Uses AI inference for unstructured documents

    Args:
        document_id: Document UUID to extract hierarchy from
        force_reprocess: Force re-extraction even if already processed
        use_ai_fallback: Use AI inference if structured extraction fails
        db: Database session

    Returns:
        HierarchyExtractionResponse with extracted hierarchy and statistics

    Raises:
        HTTPException: 404 if document not found
        HTTPException: 400 if document is still processing
        HTTPException: 500 if extraction fails
    """
    # TODO: Replace with actual authenticated user_id from JWT token
    user_id = 1  # Placeholder

    # Get document
    query = select(Document).where(
        Document.id == document_id,
        Document.user_id == user_id,
    )
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found",
        )

    # Check if document is currently processing
    if document.status == DocumentStatus.PROCESSING and not force_reprocess:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document is currently being processed. Please wait or set force_reprocess=true",
        )

    # Get extraction service and process
    extraction_service = get_hierarchy_extraction_service()

    response = await extraction_service.extract_hierarchy(
        document=document,
        db=db,
        force_reprocess=force_reprocess,
        use_ai_fallback=use_ai_fallback,
    )

    return response


@router.get(
    "/{document_id}/hierarchy",
    response_model=dict[str, Any],
    summary="Get document hierarchy",
    description="Get the extracted hierarchy for a processed document",
)
async def get_hierarchy(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Get the extracted hierarchy for a processed document.

    Args:
        document_id: Document UUID
        db: Database session

    Returns:
        Extracted hierarchy in L0-L4 format

    Raises:
        HTTPException: 404 if document not found
        HTTPException: 400 if document not yet processed
    """
    # TODO: Replace with actual authenticated user_id from JWT token
    user_id = 1  # Placeholder

    # Get document
    query = select(Document).where(
        Document.id == document_id,
        Document.user_id == user_id,
    )
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found",
        )

    if document.status != DocumentStatus.PROCESSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document has not been processed yet. Status: {document.status.value}",
        )

    if not document.processed_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document processed but no hierarchy content found",
        )

    return {
        "document_id": str(document_id),
        "status": document.status.value,
        "hierarchy": document.processed_content,
        "processed_at": document.processed_at.isoformat() if document.processed_at else None,
    }
