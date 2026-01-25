"""Pydantic schemas for document upload and responses."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentUploadResponse(BaseModel):
    """Response schema for successful document upload."""

    model_config = ConfigDict(from_attributes=True)

    document_id: str = Field(..., description="Unique identifier for the uploaded document")
    filename: str = Field(..., description="Original filename of the uploaded document")
    size_bytes: int = Field(..., description="Size of the uploaded file in bytes")
    mime_type: str = Field(..., description="MIME type of the uploaded file")
    content_hash: str = Field(..., description="SHA-256 hash of the file content")
    status: str = Field(..., description="Document processing status")
    r2_url: str = Field(..., description="Pre-signed URL to access the document (1-hour expiry)")
    uploaded_at: datetime = Field(..., description="Timestamp when the document was uploaded")


class DocumentResponse(BaseModel):
    """Response schema for document metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique document identifier")
    user_id: int = Field(..., description="ID of the user who uploaded the document")
    filename: str = Field(..., description="Original filename")
    file_size_bytes: int = Field(..., description="File size in bytes")
    mime_type: str = Field(..., description="MIME type of the file")
    content_hash: str | None = Field(None, description="SHA-256 hash of file content")
    status: str = Field(..., description="Document processing status")
    r2_path: str = Field(..., description="Path to the file in R2 storage")
    r2_url: str = Field(..., description="Pre-signed URL for file access")
    created_at: datetime = Field(..., description="Upload timestamp")
    processed_at: datetime | None = Field(None, description="Processing completion timestamp")


class DocumentListResponse(BaseModel):
    """Response schema for paginated document list."""

    model_config = ConfigDict(from_attributes=True)

    documents: list[DocumentResponse] = Field(..., description="List of documents")
    total: int = Field(..., description="Total number of documents matching the query")
    skip: int = Field(..., description="Number of documents skipped")
    limit: int = Field(..., description="Maximum number of documents returned")
