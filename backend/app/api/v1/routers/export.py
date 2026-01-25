"""Export router for map export endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.export import ExportStatus
from app.models.user import User
from app.schemas.export import (
    ExportListResponse,
    ExportRequest,
    ExportResponse,
    ExportStatusResponse,
)
from app.services.export_service import ExportService, get_export_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/maps", tags=["exports"])


@router.post(
    "/{map_id}/export",
    response_model=ExportResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request map export",
    description="Create a new export request for a map. Export will be processed in background.",
)
async def create_export(
    map_id: int,
    export_request: ExportRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExportResponse:
    """Create a new export request.

    Args:
        map_id: Map ID to export
        export_request: Export configuration
        background_tasks: FastAPI background tasks
        current_user: Current authenticated user
        db: Database session

    Returns:
        ExportResponse with export details

    Raises:
        HTTPException: If map not found or access denied
    """
    export_service = get_export_service(db)

    try:
        # Create export record
        export = await export_service.create_export(
            map_id=map_id,
            user_id=current_user.id,
            format=export_request.format,
            resolution=export_request.resolution,
            include_watermark=export_request.include_watermark,
        )

        # Schedule background processing
        background_tasks.add_task(
            export_service.process_export,
            export.id,
        )

        # Build response
        return ExportResponse(
            id=export.id,
            map_id=export.map_id,
            user_id=export.user_id,
            format=export.format,
            resolution=export.resolution,
            status=export.status,
            watermarked=export.watermarked,
            file_size=export.file_size,
            download_url=None,  # Not ready yet
            error_message=export.error_message,
            created_at=export.created_at,
            completed_at=export.completed_at,
            expires_at=export.expires_at,
        )

    except ValueError as e:
        logger.warning(f"Export creation failed for map {map_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error creating export: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create export",
        )


@router.get(
    "/{map_id}/export/{export_id}",
    response_model=ExportResponse,
    summary="Get export details",
    description="Get details for a specific export, including download URL if completed.",
)
async def get_export(
    map_id: int,
    export_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExportResponse:
    """Get export details with download URL.

    Args:
        map_id: Map ID
        export_id: Export ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        ExportResponse with export details

    Raises:
        HTTPException: If export not found or access denied
    """
    export_service = get_export_service(db)

    # Get export
    export = await export_service.get_export(export_id, current_user.id)

    if not export or export.map_id != map_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export not found",
        )

    # Generate download URL if completed
    download_url = None
    if export.status == ExportStatus.COMPLETED:
        download_url = await export_service.get_download_url(export)

    return ExportResponse(
        id=export.id,
        map_id=export.map_id,
        user_id=export.user_id,
        format=export.format,
        resolution=export.resolution,
        status=export.status,
        watermarked=export.watermarked,
        file_size=export.file_size,
        download_url=download_url,
        error_message=export.error_message,
        created_at=export.created_at,
        completed_at=export.completed_at,
        expires_at=export.expires_at,
    )


@router.get(
    "/{map_id}/export/{export_id}/status",
    response_model=ExportStatusResponse,
    summary="Get export status",
    description="Quick status check for polling export progress.",
)
async def get_export_status(
    map_id: int,
    export_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExportStatusResponse:
    """Get quick export status for polling.

    Args:
        map_id: Map ID
        export_id: Export ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        ExportStatusResponse with status and download URL

    Raises:
        HTTPException: If export not found or access denied
    """
    export_service = get_export_service(db)

    # Get export
    export = await export_service.get_export(export_id, current_user.id)

    if not export or export.map_id != map_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export not found",
        )

    # Calculate progress
    progress = None
    if export.status == ExportStatus.PENDING:
        progress = 0
    elif export.status == ExportStatus.PROCESSING:
        progress = 50
    elif export.status == ExportStatus.COMPLETED:
        progress = 100
    elif export.status == ExportStatus.FAILED:
        progress = 0

    # Get download URL if completed
    download_url = None
    if export.status == ExportStatus.COMPLETED:
        download_url = await export_service.get_download_url(export)

    return ExportStatusResponse(
        status=export.status,
        progress=progress,
        download_url=download_url,
        error_message=export.error_message,
    )


@router.get(
    "/{map_id}/exports",
    response_model=ExportListResponse,
    summary="List exports for map",
    description="Get list of all exports for a specific map.",
)
async def list_map_exports(
    map_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
    offset: int = 0,
) -> ExportListResponse:
    """List exports for a map.

    Args:
        map_id: Map ID to filter by
        limit: Maximum number of exports to return
        offset: Offset for pagination
        current_user: Current authenticated user
        db: Database session

    Returns:
        ExportListResponse with list of exports
    """
    export_service = get_export_service(db)

    # Get exports
    exports, total = await export_service.list_user_exports(
        user_id=current_user.id,
        map_id=map_id,
        limit=limit,
        offset=offset,
    )

    # Build response with download URLs
    export_responses = []
    for export in exports:
        download_url = None
        if export.status == ExportStatus.COMPLETED:
            download_url = await export_service.get_download_url(export)

        export_responses.append(
            ExportResponse(
                id=export.id,
                map_id=export.map_id,
                user_id=export.user_id,
                format=export.format,
                resolution=export.resolution,
                status=export.status,
                watermarked=export.watermarked,
                file_size=export.file_size,
                download_url=download_url,
                error_message=export.error_message,
                created_at=export.created_at,
                completed_at=export.completed_at,
                expires_at=export.expires_at,
            )
        )

    return ExportListResponse(
        exports=export_responses,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/exports",
    response_model=ExportListResponse,
    summary="List all user exports",
    description="Get list of all exports for the current user across all maps.",
)
async def list_user_exports(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
    offset: int = 0,
) -> ExportListResponse:
    """List all exports for current user.

    Args:
        limit: Maximum number of exports to return
        offset: Offset for pagination
        current_user: Current authenticated user
        db: Database session

    Returns:
        ExportListResponse with list of exports
    """
    export_service = get_export_service(db)

    # Get exports
    exports, total = await export_service.list_user_exports(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )

    # Build response with download URLs
    export_responses = []
    for export in exports:
        download_url = None
        if export.status == ExportStatus.COMPLETED:
            download_url = await export_service.get_download_url(export)

        export_responses.append(
            ExportResponse(
                id=export.id,
                map_id=export.map_id,
                user_id=export.user_id,
                format=export.format,
                resolution=export.resolution,
                status=export.status,
                watermarked=export.watermarked,
                file_size=export.file_size,
                download_url=download_url,
                error_message=export.error_message,
                created_at=export.created_at,
                completed_at=export.completed_at,
                expires_at=export.expires_at,
            )
        )

    return ExportListResponse(
        exports=export_responses,
        total=total,
        limit=limit,
        offset=offset,
    )
