"""Pydantic schemas for document upload and responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentUploadResponse(BaseModel):
    """Response schema for successful document upload."""

    model_config = ConfigDict(from_attributes=True)

    document_id: UUID = Field(..., description="Unique identifier for the uploaded document")
    filename: str = Field(..., description="Original filename of the uploaded document")
    size_bytes: int = Field(..., description="Size of the uploaded file in bytes")
    r2_url: str = Field(..., description="Pre-signed URL to access the document (1-hour expiry)")
    uploaded_at: datetime = Field(..., description="Timestamp when the document was uploaded")


class DocumentResponse(BaseModel):
    """Response schema for document metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    filename: str
    file_size_bytes: int
    mime_type: str
    r2_path: str
    r2_url: str
    created_at: datetime
