"""Pydantic schemas for API requests and responses."""

from app.schemas.document import DocumentResponse, DocumentUploadResponse

__all__ = [
    "DocumentUploadResponse",
    "DocumentResponse",
]
