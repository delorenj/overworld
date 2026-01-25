"""Export schemas for API requests and responses."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models.export import ExportFormat, ExportStatus


class ExportRequest(BaseModel):
    """Request schema for creating a new export."""

    format: ExportFormat = Field(
        ...,
        description="Export format (png or svg)"
    )
    resolution: int = Field(
        1,
        ge=1,
        le=4,
        description="Resolution multiplier (1x, 2x, or 4x)"
    )
    include_watermark: bool = Field(
        True,
        description="Whether to include watermark (auto-determined for free users)"
    )

    @field_validator("resolution")
    @classmethod
    def validate_resolution(cls, v: int) -> int:
        """Validate resolution is 1, 2, or 4."""
        if v not in [1, 2, 4]:
            raise ValueError("Resolution must be 1, 2, or 4")
        return v


class ExportResponse(BaseModel):
    """Response schema for export details."""

    id: int = Field(..., description="Export ID")
    map_id: int = Field(..., description="Map ID")
    user_id: int = Field(..., description="User ID")
    format: ExportFormat = Field(..., description="Export format")
    resolution: int = Field(..., description="Resolution multiplier")
    status: ExportStatus = Field(..., description="Export status")
    watermarked: bool = Field(..., description="Whether export has watermark")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    download_url: Optional[str] = Field(None, description="Pre-signed download URL")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    created_at: datetime = Field(..., description="Creation timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    expires_at: Optional[datetime] = Field(None, description="URL expiration timestamp")

    class Config:
        from_attributes = True


class ExportListResponse(BaseModel):
    """Response schema for list of exports."""

    exports: list[ExportResponse] = Field(..., description="List of exports")
    total: int = Field(..., description="Total number of exports")
    limit: int = Field(..., description="Page size limit")
    offset: int = Field(..., description="Page offset")


class ExportStatusResponse(BaseModel):
    """Quick status response for polling."""

    status: ExportStatus = Field(..., description="Current export status")
    progress: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Progress percentage (0-100)"
    )
    download_url: Optional[str] = Field(None, description="Download URL if completed")
    error_message: Optional[str] = Field(None, description="Error message if failed")

    class Config:
        from_attributes = True
