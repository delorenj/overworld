"""Regression tests for export-generated event export/import flows.

OWRLD-36 focuses on preventing regressions in event payload handling after
watermark-related export changes.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.events import EventSource, OverworldExportGeneratedV1
from app.services.bloodbank_emitter import (
    EXCHANGE_NAME,
    ROUTING_KEY_EXPORT_GENERATED,
    emit_export_generated_event,
)


class TestExportEventRoundTrip:
    """Schema-level export/import regression checks."""

    @pytest.mark.parametrize("fmt", ["png", "svg"])
    @pytest.mark.parametrize("watermarked", [True, False])
    def test_round_trip_supported_formats(self, fmt: str, watermarked: bool):
        """Export payloads should round-trip without data loss."""
        event = OverworldExportGeneratedV1(
            source=EventSource(host="qa-runner", trigger_type="background_job"),
            user_id=10,
            export_id=20,
            map_id=30,
            format=fmt,
            resolution=2,
            watermarked=watermarked,
            file_size_bytes=2048,
            theme_id=7,
        )

        exported_payload = event.model_dump_json()
        imported_event = OverworldExportGeneratedV1.model_validate_json(exported_payload)

        assert imported_event.user_id == event.user_id
        assert imported_event.export_id == event.export_id
        assert imported_event.map_id == event.map_id
        assert imported_event.format == fmt
        assert imported_event.resolution == event.resolution
        assert imported_event.watermarked is watermarked
        assert imported_event.file_size_bytes == event.file_size_bytes
        assert imported_event.theme_id == event.theme_id

    def test_round_trip_empty_event_payload_values(self):
        """Edge case: valid events with empty-ish payload values should survive round-trip."""
        event = OverworldExportGeneratedV1(
            source=EventSource(host="", trigger_type="background_job"),
            user_id=0,
            export_id=0,
            map_id=0,
            format="png",
            resolution=1,
            watermarked=False,
            file_size_bytes=0,
            theme_id=None,
        )

        imported = OverworldExportGeneratedV1.model_validate_json(event.model_dump_json())

        assert imported.user_id == 0
        assert imported.export_id == 0
        assert imported.file_size_bytes == 0
        assert imported.watermarked is False
        assert imported.theme_id is None

    def test_round_trip_large_payload_values(self):
        """Edge case: very large numeric/string payload fields remain intact."""
        large_host = "export-node-" + ("x" * 2048)
        event = OverworldExportGeneratedV1(
            source=EventSource(host=large_host, trigger_type="background_job"),
            user_id=999_999,
            export_id=888_888,
            map_id=777_777,
            format="svg",
            resolution=4,
            watermarked=True,
            file_size_bytes=2_147_483_647,
            theme_id=123_456,
        )

        imported = OverworldExportGeneratedV1.model_validate_json(event.model_dump_json())

        assert imported.source.host == large_host
        assert imported.file_size_bytes == 2_147_483_647
        assert imported.theme_id == 123_456

    def test_round_trip_special_characters(self):
        """Edge case: unicode/special chars are preserved across export/import."""
        special_host = "qa-ñode-東京-🚀"
        event = OverworldExportGeneratedV1(
            source=EventSource(host=special_host, trigger_type="background_job"),
            user_id=1,
            export_id=2,
            map_id=3,
            format="png",
            resolution=2,
            watermarked=True,
            file_size_bytes=4096,
        )

        imported = OverworldExportGeneratedV1.model_validate_json(event.model_dump_json())

        assert imported.source.host == special_host

    @pytest.mark.parametrize(
        "bad_payload",
        [
            "{not-json}",
            json.dumps(
                {
                    "source": {"host": "qa-runner", "trigger_type": "background_job"},
                    "user_id": 1,
                    "export_id": 2,
                    "map_id": 3,
                    "format": "png",
                    "resolution": 2,
                    # missing watermarked
                    "file_size_bytes": 100,
                }
            ),
            json.dumps(
                {
                    "source": {"host": "qa-runner", "trigger_type": "background_job"},
                    "user_id": "not-an-int",
                    "export_id": 2,
                    "map_id": 3,
                    "format": "png",
                    "resolution": 2,
                    "watermarked": True,
                    "file_size_bytes": 100,
                }
            ),
        ],
    )
    def test_import_rejects_malformed_payloads(self, bad_payload: str):
        """Malformed input should fail import validation."""
        with pytest.raises(ValidationError):
            OverworldExportGeneratedV1.model_validate_json(bad_payload)

    @pytest.mark.xfail(
        reason="Known gap: export event format is unconstrained string; should enforce png/svg",
    )
    def test_import_rejects_unsupported_export_format(self):
        """Unsupported formats should be rejected at schema import time."""
        bad_format_payload = json.dumps(
            {
                "source": {"host": "qa-runner", "trigger_type": "background_job"},
                "user_id": 1,
                "export_id": 2,
                "map_id": 3,
                "format": "pdf",
                "resolution": 2,
                "watermarked": True,
                "file_size_bytes": 100,
            }
        )

        with pytest.raises(ValidationError):
            OverworldExportGeneratedV1.model_validate_json(bad_format_payload)


class TestExportEventEmission:
    """Emitter-level regression checks for watermark + format propagation."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("fmt", ["png", "svg"])
    @pytest.mark.parametrize("watermarked", [True, False])
    async def test_emit_export_generated_event_formats_and_watermark(
        self,
        fmt: str,
        watermarked: bool,
    ):
        """Emitter should publish export events for all formats with correct watermark flag."""
        mock_db = AsyncMock(spec=AsyncSession)

        mock_channel = MagicMock()
        mock_connection = MagicMock()
        mock_connection.channel.return_value = mock_channel

        with patch(
            "app.services.bloodbank_emitter.pika.BlockingConnection",
            return_value=mock_connection,
        ):
            await emit_export_generated_event(
                db=mock_db,
                export_id=99,
                map_id=123,
                user_id=456,
                format=fmt,
                resolution=2,
                watermarked=watermarked,
                file_size_bytes=54321,
                theme_id=77,
            )

        mock_channel.exchange_declare.assert_called_once_with(
            exchange=EXCHANGE_NAME,
            exchange_type="topic",
            durable=True,
        )
        mock_channel.basic_publish.assert_called_once()

        publish_kwargs = mock_channel.basic_publish.call_args.kwargs
        assert publish_kwargs["routing_key"] == ROUTING_KEY_EXPORT_GENERATED

        payload = OverworldExportGeneratedV1.model_validate_json(
            publish_kwargs["body"].decode("utf-8")
        )
        assert payload.export_id == 99
        assert payload.map_id == 123
        assert payload.user_id == 456
        assert payload.format == fmt
        assert payload.resolution == 2
        assert payload.watermarked is watermarked
        assert payload.file_size_bytes == 54321
        assert payload.theme_id == 77

        mock_connection.close.assert_called_once()
