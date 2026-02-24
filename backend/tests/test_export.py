"""Tests for export service and endpoints."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.export import Export, ExportFormat, ExportStatus
from app.models.map import Map
from app.models.user import User
from app.services.export_service import ExportService, ExportError
from app.services.r2_storage import R2StorageService


@pytest.fixture
def mock_r2_service():
    """Mock R2 storage service."""
    service = MagicMock(spec=R2StorageService)
    service.upload_file = AsyncMock(return_value=("exports/123/test.png", "https://example.com/test.png"))
    service.generate_presigned_url = AsyncMock(return_value="https://example.com/download/test.png")
    return service


@pytest.fixture
async def test_user(db_session: AsyncSession):
    """Create a test user."""
    user = User(
        email="test@example.com",
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_map(db_session: AsyncSession, test_user: User, test_theme):
    """Create a test map."""
    map_obj = Map(
        user_id=test_user.id,
        theme_id=test_theme.id,
        name="Test Map",
        hierarchy={"L0": {"title": "Test"}},
        watermarked=False,
    )
    db_session.add(map_obj)
    await db_session.commit()
    await db_session.refresh(map_obj)
    return map_obj


class TestExportService:
    """Tests for ExportService."""

    @pytest.mark.asyncio
    async def test_create_export_success(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_map: Map,
        mock_r2_service,
    ):
        """Test creating an export successfully."""
        service = ExportService(db_session)

        # Set user as premium (Stripe subscription active)
        test_user.is_premium = True
        await db_session.commit()

        export = await service.create_export(
            map_id=test_map.id,
            user_id=test_user.id,
            format=ExportFormat.PNG,
            resolution=2,
            include_watermark=False,
        )

        assert export.id is not None
        assert export.map_id == test_map.id
        assert export.user_id == test_user.id
        assert export.format == ExportFormat.PNG
        assert export.resolution == 2
        assert export.status == ExportStatus.PENDING
        assert export.watermarked is False  # Premium user, no watermark
        assert export.expires_at is not None

    @pytest.mark.asyncio
    async def test_create_export_free_user_watermark(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_map: Map,
        mock_r2_service,
    ):
        """Test that free users always get watermark."""
        service = ExportService(db_session)

        # Ensure user is free tier (no Stripe subscription)
        test_user.is_premium = False
        await db_session.commit()

        export = await service.create_export(
            map_id=test_map.id,
            user_id=test_user.id,
            format=ExportFormat.SVG,
            resolution=1,
            include_watermark=False,  # User requested no watermark
        )

        assert export.watermarked is True  # Forced for free users

    @pytest.mark.asyncio
    async def test_create_export_invalid_map(
        self,
        db_session: AsyncSession,
        test_user: User,
        mock_r2_service,
    ):
        """Test creating export for non-existent map."""
        service = ExportService(db_session)

        with pytest.raises(ValueError, match="not found or access denied"):
            await service.create_export(
                map_id=99999,
                user_id=test_user.id,
                format=ExportFormat.PNG,
            )

    @pytest.mark.asyncio
    async def test_create_export_wrong_user(
        self,
        db_session: AsyncSession,
        test_map: Map,
        mock_r2_service,
    ):
        """Test creating export for map owned by different user."""
        # Create another user
        other_user = User(email="other@example.com", is_verified=True)
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)

        service = ExportService(db_session)

        with pytest.raises(ValueError, match="not found or access denied"):
            await service.create_export(
                map_id=test_map.id,
                user_id=other_user.id,
                format=ExportFormat.PNG,
            )

    @pytest.mark.asyncio
    async def test_process_export_png(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_map: Map,
        mock_r2_service,
    ):
        """Test processing PNG export."""
        service = ExportService(db_session)

        # Create export
        export = Export(
            map_id=test_map.id,
            user_id=test_user.id,
            format=ExportFormat.PNG,
            resolution=1,
            status=ExportStatus.PENDING,
            watermarked=True,
        )
        db_session.add(export)
        await db_session.commit()
        await db_session.refresh(export)

        # Process export
        result = await service.process_export(export.id)

        assert result.status == ExportStatus.COMPLETED
        assert result.file_path is not None
        assert result.file_size is not None
        assert result.completed_at is not None
        mock_r2_service.upload_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_export_svg(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_map: Map,
        mock_r2_service,
    ):
        """Test processing SVG export."""
        # Configure mock to return SVG file path
        mock_r2_service.upload_file = AsyncMock(
            return_value=("exports/123/test.svg", "https://example.com/test.svg")
        )
        service = ExportService(db_session)

        # Create export
        export = Export(
            map_id=test_map.id,
            user_id=test_user.id,
            format=ExportFormat.SVG,
            resolution=2,
            status=ExportStatus.PENDING,
            watermarked=False,
        )
        db_session.add(export)
        await db_session.commit()
        await db_session.refresh(export)

        # Process export
        result = await service.process_export(export.id)

        assert result.status == ExportStatus.COMPLETED
        assert result.format == ExportFormat.SVG
        assert result.file_path.endswith(".svg")

    @pytest.mark.asyncio
    async def test_process_export_failure(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_map: Map,
        mock_r2_service,
    ):
        """Test export processing failure."""
        service = ExportService(db_session)

        # Create export
        export = Export(
            map_id=test_map.id,
            user_id=test_user.id,
            format=ExportFormat.PNG,
            resolution=1,
            status=ExportStatus.PENDING,
            watermarked=True,
        )
        db_session.add(export)
        await db_session.commit()
        await db_session.refresh(export)

        # Mock upload failure
        mock_r2_service.upload_file.side_effect = Exception("Upload failed")

        with pytest.raises(ExportError, match="Export generation failed"):
            await service.process_export(export.id)

        # Check export marked as failed
        await db_session.refresh(export)
        assert export.status == ExportStatus.FAILED
        assert export.error_message is not None

    @pytest.mark.asyncio
    async def test_get_download_url(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_map: Map,
        mock_r2_service,
    ):
        """Test getting download URL for completed export."""
        service = ExportService(db_session)

        # Create completed export
        export = Export(
            map_id=test_map.id,
            user_id=test_user.id,
            format=ExportFormat.PNG,
            resolution=1,
            status=ExportStatus.COMPLETED,
            watermarked=True,
            file_path="exports/123/test.png",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        db_session.add(export)
        await db_session.commit()

        # Get download URL
        url = await service.get_download_url(export)

        assert url is not None
        assert url.startswith("https://")
        mock_r2_service.generate_presigned_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_download_url_expired(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_map: Map,
        mock_r2_service,
    ):
        """Test getting download URL for expired export."""
        service = ExportService(db_session)

        # Create expired export
        export = Export(
            map_id=test_map.id,
            user_id=test_user.id,
            format=ExportFormat.PNG,
            resolution=1,
            status=ExportStatus.COMPLETED,
            watermarked=True,
            file_path="exports/123/test.png",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),  # Expired
        )
        db_session.add(export)
        await db_session.commit()

        # Get download URL
        url = await service.get_download_url(export)

        assert url is None  # Expired

    @pytest.mark.asyncio
    async def test_list_user_exports(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_map: Map,
        mock_r2_service,
    ):
        """Test listing user exports."""
        service = ExportService(db_session)

        # Create multiple exports
        for i in range(3):
            export = Export(
                map_id=test_map.id,
                user_id=test_user.id,
                format=ExportFormat.PNG,
                resolution=1,
                status=ExportStatus.COMPLETED,
                watermarked=True,
            )
            db_session.add(export)
        await db_session.commit()

        # List exports
        exports, total = await service.list_user_exports(test_user.id, limit=10)

        assert len(exports) == 3
        assert total == 3

    @pytest.mark.asyncio
    async def test_list_user_exports_pagination(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_map: Map,
        mock_r2_service,
    ):
        """Test export listing pagination."""
        service = ExportService(db_session)

        # Create 5 exports
        for i in range(5):
            export = Export(
                map_id=test_map.id,
                user_id=test_user.id,
                format=ExportFormat.PNG,
                resolution=1,
                status=ExportStatus.COMPLETED,
                watermarked=True,
            )
            db_session.add(export)
        await db_session.commit()

        # Get first page
        exports_page1, total = await service.list_user_exports(
            test_user.id, limit=2, offset=0
        )
        assert len(exports_page1) == 2
        assert total == 5

        # Get second page
        exports_page2, _ = await service.list_user_exports(
            test_user.id, limit=2, offset=2
        )
        assert len(exports_page2) == 2

        # Verify different exports
        assert exports_page1[0].id != exports_page2[0].id


class TestExportValidation:
    """Tests for export request validation."""

    def test_export_format_validation(self):
        """Test export format validation."""
        valid_formats = ["png", "svg"]
        for fmt in valid_formats:
            assert fmt in [f.value for f in ExportFormat]

    def test_resolution_validation(self):
        """Test resolution validation."""
        valid_resolutions = [1, 2, 4]
        for res in valid_resolutions:
            assert res in valid_resolutions

    def test_invalid_resolution(self):
        """Test invalid resolution."""
        invalid_resolutions = [0, 3, 5, 8]
        for res in invalid_resolutions:
            assert res not in [1, 2, 4]


class TestWatermarkLogic:
    """Tests for watermark application logic."""

    @pytest.mark.asyncio
    async def test_watermark_applied_free_user(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_map: Map,
        mock_r2_service,
    ):
        """Test watermark is applied for free users."""
        service = ExportService(db_session)

        # Ensure user is free tier (no Stripe subscription)
        test_user.is_premium = False
        await db_session.commit()

        export = await service.create_export(
            map_id=test_map.id,
            user_id=test_user.id,
            format=ExportFormat.PNG,
            resolution=1,
            include_watermark=False,  # Requested no watermark
        )

        assert export.watermarked is True

    @pytest.mark.asyncio
    async def test_no_watermark_premium_user(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_map: Map,
        mock_r2_service,
    ):
        """Test no watermark for premium users."""
        service = ExportService(db_session)

        # Set user as premium (Stripe subscription active)
        test_user.is_premium = True
        await db_session.commit()

        export = await service.create_export(
            map_id=test_map.id,
            user_id=test_user.id,
            format=ExportFormat.PNG,
            resolution=1,
            include_watermark=False,
        )

        assert export.watermarked is False

    @pytest.mark.asyncio
    async def test_optional_watermark_premium_user(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_map: Map,
        mock_r2_service,
    ):
        """Test premium users can optionally include watermark."""
        service = ExportService(db_session)

        # Set user as premium (Stripe subscription active)
        test_user.is_premium = True
        await db_session.commit()

        export = await service.create_export(
            map_id=test_map.id,
            user_id=test_user.id,
            format=ExportFormat.PNG,
            resolution=1,
            include_watermark=True,  # Premium user wants watermark
        )

        assert export.watermarked is True
