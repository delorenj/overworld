"""Export service for generating map exports (PNG/SVG) with watermarks."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Optional

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.export import Export, ExportFormat, ExportStatus
from app.models.map import Map
from app.services.r2_storage import R2StorageService, get_r2_service
from app.services.token_service import TokenService

logger = logging.getLogger(__name__)

# Export configuration
EXPORT_EXPIRY_HOURS = 24
BASE_MAP_WIDTH = 1024  # Base width for 1x resolution
BASE_MAP_HEIGHT = 768  # Base height for 1x resolution
WATERMARK_TEXT = "Overworld"
WATERMARK_OPACITY = 128  # 0-255, 128 is 50% transparent


class ExportError(Exception):
    """Raised when export generation fails."""
    pass


class ExportService:
    """Service for generating and managing map exports."""

    def __init__(self, db: AsyncSession, r2_service: Optional[R2StorageService] = None):
        """Initialize the export service.

        Args:
            db: Database session
            r2_service: Optional R2 storage service (auto-created if not provided)
        """
        self.db = db
        self.r2_service = r2_service or get_r2_service()

    async def create_export(
        self,
        map_id: int,
        user_id: int,
        format: ExportFormat,
        resolution: int = 1,
        include_watermark: bool = True,
    ) -> Export:
        """Create a new export request.

        Args:
            map_id: ID of the map to export
            user_id: ID of the user requesting the export
            format: Export format (PNG or SVG)
            resolution: Resolution multiplier (1, 2, or 4)
            include_watermark: Whether to include watermark

        Returns:
            Created Export instance

        Raises:
            ValueError: If map not found or user doesn't own map
        """
        # Verify map exists and user owns it
        stmt = select(Map).where(Map.id == map_id, Map.user_id == user_id)
        result = await self.db.execute(stmt)
        map_obj = result.scalar_one_or_none()

        if not map_obj:
            raise ValueError(f"Map {map_id} not found or access denied")

        # Check if user is premium (has tokens > 0)
        token_service = TokenService(self.db)
        balance = await token_service.get_balance(user_id)
        is_premium = balance > 0

        # Free users must have watermark
        watermarked = include_watermark if is_premium else True

        # Calculate expiration time
        expires_at = datetime.now(timezone.utc) + timedelta(hours=EXPORT_EXPIRY_HOURS)

        # Create export record
        export = Export(
            map_id=map_id,
            user_id=user_id,
            format=format,
            resolution=resolution,
            status=ExportStatus.PENDING,
            watermarked=watermarked,
            expires_at=expires_at,
        )

        self.db.add(export)
        await self.db.commit()
        await self.db.refresh(export)

        logger.info(
            f"Created export {export.id} for map {map_id} "
            f"(format={format}, resolution={resolution}x, watermarked={watermarked})"
        )

        return export

    async def process_export(self, export_id: int) -> Export:
        """Process an export (generate file and upload to R2).

        This should be called in a background task.

        Args:
            export_id: ID of the export to process

        Returns:
            Updated Export instance

        Raises:
            ExportError: If export processing fails
        """
        # Get export with map data
        stmt = (
            select(Export)
            .where(Export.id == export_id)
            .join(Export.map)
        )
        result = await self.db.execute(stmt)
        export = result.scalar_one_or_none()

        if not export:
            raise ExportError(f"Export {export_id} not found")

        try:
            # Update status to processing
            export.status = ExportStatus.PROCESSING
            await self.db.commit()

            # Generate the export file
            if export.format == ExportFormat.PNG:
                file_content = await self._generate_png(
                    export.map,
                    export.resolution,
                    export.watermarked,
                )
                mime_type = "image/png"
                file_ext = "png"
            else:  # SVG
                file_content = await self._generate_svg(
                    export.map,
                    export.resolution,
                    export.watermarked,
                )
                mime_type = "image/svg+xml"
                file_ext = "svg"

            # Upload to R2
            filename = f"map_{export.map_id}_export_{export.id}.{file_ext}"
            r2_path, _ = await self.r2_service.upload_file(
                file_content=file_content,
                filename=filename,
                user_id=export.user_id,
                mime_type=mime_type,
            )

            # Update export record
            export.status = ExportStatus.COMPLETED
            export.file_path = r2_path
            export.file_size = len(file_content)
            export.completed_at = datetime.now(timezone.utc)

            await self.db.commit()
            await self.db.refresh(export)

            logger.info(
                f"Export {export_id} completed successfully "
                f"({export.file_size} bytes)"
            )

            return export

        except Exception as e:
            # Update status to failed
            export.status = ExportStatus.FAILED
            export.error_message = str(e)[:1024]  # Truncate to column size
            await self.db.commit()

            logger.error(f"Export {export_id} failed: {e}", exc_info=True)
            raise ExportError(f"Export generation failed: {e}") from e

    async def get_export(self, export_id: int, user_id: int) -> Optional[Export]:
        """Get an export by ID (with access control).

        Args:
            export_id: Export ID
            user_id: User ID for access control

        Returns:
            Export instance or None if not found
        """
        stmt = select(Export).where(
            Export.id == export_id,
            Export.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_download_url(self, export: Export) -> Optional[str]:
        """Generate a pre-signed download URL for an export.

        Args:
            export: Export instance

        Returns:
            Pre-signed download URL or None if export not completed
        """
        if export.status != ExportStatus.COMPLETED or not export.file_path:
            return None

        # Check if export has expired
        if export.expires_at and export.expires_at < datetime.now(timezone.utc):
            return None

        # Generate pre-signed URL (1 hour expiry)
        bucket_name = settings.R2_BUCKET_EXPORTS
        url = await self.r2_service.generate_presigned_url(
            bucket_name=bucket_name,
            r2_path=export.file_path,
            expiry_seconds=3600,  # 1 hour
        )

        return url

    async def list_user_exports(
        self,
        user_id: int,
        map_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Export], int]:
        """List exports for a user.

        Args:
            user_id: User ID
            map_id: Optional map ID to filter by
            limit: Maximum number of exports to return
            offset: Offset for pagination

        Returns:
            Tuple of (list of exports, total count)
        """
        # Build query
        stmt = select(Export).where(Export.user_id == user_id)

        if map_id:
            stmt = stmt.where(Export.map_id == map_id)

        # Get total count
        from sqlalchemy import func
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await self.db.scalar(count_stmt) or 0

        # Get paginated results
        stmt = stmt.order_by(Export.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        exports = list(result.scalars().all())

        return exports, total

    async def _generate_png(
        self,
        map_obj: Map,
        resolution: int,
        watermarked: bool,
    ) -> bytes:
        """Generate PNG export from map data.

        Args:
            map_obj: Map instance with hierarchy data
            resolution: Resolution multiplier (1, 2, or 4)
            watermarked: Whether to apply watermark

        Returns:
            PNG file content as bytes
        """
        # Calculate dimensions
        width = BASE_MAP_WIDTH * resolution
        height = BASE_MAP_HEIGHT * resolution

        # Create image in executor (PIL is CPU-bound)
        def create_image():
            # Create base image with background
            img = Image.new("RGB", (width, height), color=(240, 240, 240))
            draw = ImageDraw.Draw(img, mode="RGBA")

            # Draw simple placeholder content
            # In production, this would render the actual map hierarchy
            self._draw_placeholder_map(draw, width, height, map_obj)

            # Apply watermark if needed
            if watermarked:
                self._apply_watermark(img, draw, width, height)

            # Convert to bytes
            buffer = BytesIO()
            img.save(buffer, format="PNG", optimize=True)
            return buffer.getvalue()

        # Run in executor to avoid blocking
        return await asyncio.get_event_loop().run_in_executor(None, create_image)

    async def _generate_svg(
        self,
        map_obj: Map,
        resolution: int,
        watermarked: bool,
    ) -> bytes:
        """Generate SVG export from map data.

        Args:
            map_obj: Map instance with hierarchy data
            resolution: Resolution multiplier (1, 2, or 4)
            watermarked: Whether to apply watermark

        Returns:
            SVG file content as bytes
        """
        # Calculate dimensions
        width = BASE_MAP_WIDTH * resolution
        height = BASE_MAP_HEIGHT * resolution

        # Build SVG content
        svg_parts = [
            f'<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" ',
            f'width="{width}" height="{height}" ',
            f'viewBox="0 0 {width} {height}">',
            f'<rect width="{width}" height="{height}" fill="#f0f0f0"/>',
        ]

        # Add placeholder content
        # In production, this would render the actual map hierarchy
        svg_parts.extend(self._get_placeholder_svg_elements(width, height, map_obj))

        # Add watermark if needed
        if watermarked:
            svg_parts.append(self._get_watermark_svg(width, height))

        svg_parts.append("</svg>")

        return "\n".join(svg_parts).encode("utf-8")

    def _draw_placeholder_map(
        self,
        draw: ImageDraw.ImageDraw,
        width: int,
        height: int,
        map_obj: Map,
    ) -> None:
        """Draw placeholder map content (replace with actual map rendering).

        Args:
            draw: PIL ImageDraw instance
            width: Image width
            height: Image height
            map_obj: Map instance
        """
        # Draw title
        title = map_obj.name
        title_font_size = max(20, width // 30)

        try:
            # Try to use a nice font
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", title_font_size)
        except Exception:
            # Fall back to default font
            font = ImageFont.load_default()

        # Draw title centered at top
        bbox = draw.textbbox((0, 0), title, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = (width - text_width) // 2
        draw.text((text_x, 40), title, fill=(50, 50, 50), font=font)

        # Draw placeholder regions
        padding = width // 20
        region_width = (width - 3 * padding) // 2
        region_height = (height - 3 * padding) // 2

        colors = [
            (200, 220, 240),  # Light blue
            (220, 240, 200),  # Light green
            (240, 220, 200),  # Light orange
            (240, 200, 220),  # Light pink
        ]

        for i in range(4):
            row = i // 2
            col = i % 2
            x = padding + col * (region_width + padding)
            y = 100 + padding + row * (region_height + padding)

            # Draw rectangle
            draw.rectangle(
                [x, y, x + region_width, y + region_height],
                fill=colors[i],
                outline=(100, 100, 100),
                width=2,
            )

            # Draw label
            label = f"Region {i + 1}"
            label_bbox = draw.textbbox((0, 0), label, font=font)
            label_width = label_bbox[2] - label_bbox[0]
            label_x = x + (region_width - label_width) // 2
            label_y = y + region_height // 2
            draw.text((label_x, label_y), label, fill=(50, 50, 50), font=font)

    def _apply_watermark(
        self,
        img: Image.Image,
        draw: ImageDraw.ImageDraw,
        width: int,
        height: int,
    ) -> None:
        """Apply watermark to image.

        Args:
            img: PIL Image instance
            draw: PIL ImageDraw instance
            width: Image width
            height: Image height
        """
        # Create semi-transparent watermark text
        watermark_size = max(24, width // 40)

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", watermark_size)
        except Exception:
            font = ImageFont.load_default()

        # Position in bottom-right corner
        bbox = draw.textbbox((0, 0), WATERMARK_TEXT, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = width - text_width - 20
        y = height - text_height - 20

        # Draw with semi-transparency
        draw.text(
            (x, y),
            WATERMARK_TEXT,
            fill=(0, 0, 0, WATERMARK_OPACITY),
            font=font,
        )

    def _get_placeholder_svg_elements(
        self,
        width: int,
        height: int,
        map_obj: Map,
    ) -> list[str]:
        """Get placeholder SVG elements (replace with actual map rendering).

        Args:
            width: SVG width
            height: SVG height
            map_obj: Map instance

        Returns:
            List of SVG element strings
        """
        elements = []

        # Add title
        title_size = max(20, width // 30)
        elements.append(
            f'<text x="{width // 2}" y="40" '
            f'text-anchor="middle" font-size="{title_size}" '
            f'font-weight="bold" fill="#323232">{map_obj.name}</text>'
        )

        # Add placeholder regions
        padding = width // 20
        region_width = (width - 3 * padding) // 2
        region_height = (height - 3 * padding) // 2

        colors = ["#c8dcf0", "#dcf0c8", "#f0dcc8", "#f0c8dc"]

        for i in range(4):
            row = i // 2
            col = i % 2
            x = padding + col * (region_width + padding)
            y = 100 + padding + row * (region_height + padding)

            elements.append(
                f'<rect x="{x}" y="{y}" width="{region_width}" '
                f'height="{region_height}" fill="{colors[i]}" '
                f'stroke="#646464" stroke-width="2"/>'
            )

            label_x = x + region_width // 2
            label_y = y + region_height // 2
            elements.append(
                f'<text x="{label_x}" y="{label_y}" '
                f'text-anchor="middle" font-size="{title_size}" '
                f'fill="#323232">Region {i + 1}</text>'
            )

        return elements

    def _get_watermark_svg(self, width: int, height: int) -> str:
        """Get SVG watermark element.

        Args:
            width: SVG width
            height: SVG height

        Returns:
            SVG watermark element string
        """
        watermark_size = max(24, width // 40)
        x = width - 20
        y = height - 20

        return (
            f'<text x="{x}" y="{y}" '
            f'text-anchor="end" font-size="{watermark_size}" '
            f'font-weight="bold" fill="#000000" '
            f'opacity="0.5">{WATERMARK_TEXT}</text>'
        )


def get_export_service(db: AsyncSession) -> ExportService:
    """Factory function to create ExportService.

    Args:
        db: Database session

    Returns:
        Configured ExportService instance
    """
    return ExportService(db)
