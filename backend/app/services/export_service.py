"""Export service for generating map exports (PNG/SVG) with watermarks."""

import asyncio
import logging
import math
import os
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.export import Export, ExportFormat, ExportStatus
from app.models.map import Map

logger = logging.getLogger(__name__)

# Export configuration
EXPORT_EXPIRY_HOURS = 24
BASE_MAP_WIDTH = 1024
BASE_MAP_HEIGHT = 768
WATERMARK_TEXT = "OVERWORLD"
WATERMARK_OPACITY = 90

# Local export directory for dev mode (no R2)
LOCAL_EXPORT_DIR = Path("/app/exports")

# ── Theme palette ──────────────────────────────────────────────────
REGION_COLORS = [
    (72, 161, 77),   # grass green
    (58, 123, 213),  # water blue
    (200, 169, 106), # sand
    (168, 112, 58),  # earth brown
    (140, 100, 180), # mountain purple
    (210, 140, 60),  # sunset orange
]
BG_COLOR = (248, 244, 236)
ROAD_COLOR = (180, 160, 130)
NODE_RADIUS = 18
NODE_OUTLINE = (60, 50, 40)
TEXT_COLOR = (50, 45, 40)
SUBTITLE_COLOR = (100, 90, 80)


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Get a DejaVu font at the requested size, falling back gracefully."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


class ExportError(Exception):
    pass


# ── Hierarchy helpers ──────────────────────────────────────────────

def _parse_hierarchy(raw: Any) -> dict:
    """Normalise hierarchy JSON into {title, regions: [{name, milestones}]}."""
    if not isinstance(raw, dict):
        return {"title": "Untitled Map", "regions": []}

    title = "Untitled Map"
    l0 = raw.get("L0")
    if isinstance(l0, dict):
        title = l0.get("title", title)
    elif isinstance(l0, str):
        title = l0

    # L2 entries are regions
    regions_raw = raw.get("L2", [])
    if not isinstance(regions_raw, list):
        regions_raw = []

    milestones_raw = raw.get("L3", [])
    if not isinstance(milestones_raw, list):
        milestones_raw = []

    # Index milestones by parent
    ms_by_parent: dict[str, list[str]] = {}
    for m in milestones_raw:
        if isinstance(m, dict):
            pid = m.get("parent_id", "")
            ms_by_parent.setdefault(pid, []).append(
                m.get("title", m.get("content", "?"))
            )

    regions = []
    for r in regions_raw:
        if isinstance(r, dict):
            rid = r.get("id", "")
            regions.append({
                "name": r.get("title", r.get("content", "Region")),
                "milestones": ms_by_parent.get(rid, []),
            })

    # Fallback: if no L2 but L1 exists, treat L1 children as regions
    if not regions:
        l1 = raw.get("L1", [])
        if isinstance(l1, list):
            for item in l1:
                if isinstance(item, dict):
                    regions.append({
                        "name": item.get("title", item.get("content", "Region")),
                        "milestones": [],
                    })

    return {"title": title, "regions": regions}


# ── PNG rendering ──────────────────────────────────────────────────

def _render_png(
    hierarchy: dict,
    map_name: str,
    width: int,
    height: int,
    watermarked: bool,
) -> bytes:
    """Render a hierarchy-based map as PNG."""
    img = Image.new("RGB", (width, height), color=BG_COLOR)
    draw = ImageDraw.Draw(img, mode="RGBA")

    parsed = _parse_hierarchy(hierarchy)
    title = parsed["title"] or map_name
    regions = parsed["regions"] or [{"name": "Empty Map", "milestones": []}]

    # ── Title ──
    title_font = _get_font(max(22, width // 28), bold=True)
    bbox = draw.textbbox((0, 0), title, font=title_font)
    tw = bbox[2] - bbox[0]
    draw.text(((width - tw) // 2, 30), title, fill=TEXT_COLOR, font=title_font)

    # ── Layout regions in a grid ──
    n = len(regions)
    cols = min(n, max(1, round(math.sqrt(n * (width / height)))))
    rows = math.ceil(n / cols)
    pad = width // 24
    region_w = (width - (cols + 1) * pad) // cols
    region_h = (height - 100 - (rows + 1) * pad) // rows

    label_font = _get_font(max(14, width // 50), bold=True)
    ms_font = _get_font(max(11, width // 65))

    node_positions: list[tuple[int, int]] = []

    for idx, region in enumerate(regions):
        col = idx % cols
        row = idx // cols
        rx = pad + col * (region_w + pad)
        ry = 90 + pad + row * (region_h + pad)
        color = REGION_COLORS[idx % len(REGION_COLORS)]

        # Filled rounded rect
        draw.rounded_rectangle(
            [rx, ry, rx + region_w, ry + region_h],
            radius=12,
            fill=(*color, 60),
            outline=(*color, 180),
            width=2,
        )

        # Region label
        draw.text((rx + 12, ry + 8), region["name"], fill=TEXT_COLOR, font=label_font)

        # Milestones as nodes
        milestones = region["milestones"][:8]  # cap for visual clarity
        ms_start_y = ry + 36
        for mi, ms in enumerate(milestones):
            mx = rx + 30
            my = ms_start_y + mi * (NODE_RADIUS * 2 + 8)
            if my + NODE_RADIUS > ry + region_h - 8:
                break
            # node circle
            draw.ellipse(
                [mx - NODE_RADIUS, my - NODE_RADIUS, mx + NODE_RADIUS, my + NODE_RADIUS],
                fill=(*color, 200),
                outline=NODE_OUTLINE,
                width=2,
            )
            # label
            draw.text((mx + NODE_RADIUS + 8, my - 8), ms[:32], fill=TEXT_COLOR, font=ms_font)
            node_positions.append((mx, my))

    # ── Roads between sequential nodes ──
    for i in range(len(node_positions) - 1):
        ax, ay = node_positions[i]
        bx, by = node_positions[i + 1]
        draw.line([(ax, ay), (bx, by)], fill=(*ROAD_COLOR, 120), width=3)

    # ── Watermark ──
    if watermarked:
        _apply_watermark_png(draw, width, height)

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _apply_watermark_png(draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
    """Draw diagonal repeating watermark."""
    wm_font = _get_font(max(28, w // 20), bold=True)
    step_x = w // 3
    step_y = h // 3
    for iy in range(-1, 4):
        for ix in range(-1, 4):
            x = ix * step_x + (iy % 2) * (step_x // 2)
            y = iy * step_y
            draw.text(
                (x, y),
                WATERMARK_TEXT,
                fill=(0, 0, 0, WATERMARK_OPACITY),
                font=wm_font,
            )


# ── SVG rendering ──────────────────────────────────────────────────

def _render_svg(
    hierarchy: dict,
    map_name: str,
    width: int,
    height: int,
    watermarked: bool,
) -> bytes:
    """Render a hierarchy-based map as SVG."""
    parsed = _parse_hierarchy(hierarchy)
    title = parsed["title"] or map_name
    regions = parsed["regions"] or [{"name": "Empty Map", "milestones": []}]

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="rgb{BG_COLOR}"/>',
    ]

    # Title
    ts = max(22, width // 28)
    parts.append(
        f'<text x="{width // 2}" y="50" text-anchor="middle" '
        f'font-family="DejaVu Sans,sans-serif" font-size="{ts}" '
        f'font-weight="bold" fill="rgb{TEXT_COLOR}">{_svg_esc(title)}</text>'
    )

    n = len(regions)
    cols = min(n, max(1, round(math.sqrt(n * (width / height)))))
    rows = math.ceil(n / cols)
    pad = width // 24
    rw = (width - (cols + 1) * pad) // cols
    rh = (height - 100 - (rows + 1) * pad) // rows
    ls = max(14, width // 50)
    ms_s = max(11, width // 65)

    nodes: list[tuple[int, int]] = []

    for idx, region in enumerate(regions):
        col = idx % cols
        row = idx // cols
        rx = pad + col * (rw + pad)
        ry = 90 + pad + row * (rh + pad)
        c = REGION_COLORS[idx % len(REGION_COLORS)]

        parts.append(
            f'<rect x="{rx}" y="{ry}" width="{rw}" height="{rh}" rx="12" '
            f'fill="rgba({c[0]},{c[1]},{c[2]},0.25)" '
            f'stroke="rgba({c[0]},{c[1]},{c[2]},0.7)" stroke-width="2"/>'
        )
        parts.append(
            f'<text x="{rx + 12}" y="{ry + 24}" font-family="DejaVu Sans,sans-serif" '
            f'font-size="{ls}" font-weight="bold" fill="rgb{TEXT_COLOR}">'
            f'{_svg_esc(region["name"])}</text>'
        )

        milestones = region["milestones"][:8]
        ms_start = ry + 46
        for mi, ms in enumerate(milestones):
            mx = rx + 30
            my = ms_start + mi * (NODE_RADIUS * 2 + 8)
            if my + NODE_RADIUS > ry + rh - 8:
                break
            parts.append(
                f'<circle cx="{mx}" cy="{my}" r="{NODE_RADIUS}" '
                f'fill="rgba({c[0]},{c[1]},{c[2]},0.8)" '
                f'stroke="rgb{NODE_OUTLINE}" stroke-width="2"/>'
            )
            parts.append(
                f'<text x="{mx + NODE_RADIUS + 8}" y="{my + 4}" '
                f'font-family="DejaVu Sans,sans-serif" font-size="{ms_s}" '
                f'fill="rgb{TEXT_COLOR}">{_svg_esc(ms[:32])}</text>'
            )
            nodes.append((mx, my))

    # Roads
    for i in range(len(nodes) - 1):
        ax, ay = nodes[i]
        bx, by = nodes[i + 1]
        parts.append(
            f'<line x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}" '
            f'stroke="rgba({ROAD_COLOR[0]},{ROAD_COLOR[1]},{ROAD_COLOR[2]},0.5)" '
            f'stroke-width="3"/>'
        )

    # Watermark
    if watermarked:
        parts.append(_svg_watermark(width, height))

    parts.append("</svg>")
    return "\n".join(parts).encode("utf-8")


def _svg_esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _svg_watermark(w: int, h: int) -> str:
    fs = max(28, w // 20)
    lines = []
    step_x = w // 3
    step_y = h // 3
    for iy in range(-1, 4):
        for ix in range(-1, 4):
            x = ix * step_x + (iy % 2) * (step_x // 2)
            y = iy * step_y
            lines.append(
                f'<text x="{x}" y="{y}" font-family="DejaVu Sans,sans-serif" '
                f'font-size="{fs}" font-weight="bold" fill="#000" '
                f'opacity="0.08">{WATERMARK_TEXT}</text>'
            )
    return "\n".join(lines)


# ── Service ────────────────────────────────────────────────────────

class ExportService:
    """Service for generating and managing map exports."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_export(
        self,
        map_id: int,
        user_id: int,
        format: ExportFormat,
        resolution: int = 1,
        include_watermark: bool = True,
    ) -> Export:
        stmt = select(Map).where(Map.id == map_id, Map.user_id == user_id)
        result = await self.db.execute(stmt)
        map_obj = result.scalar_one_or_none()
        if not map_obj:
            raise ValueError(f"Map {map_id} not found or access denied")

        # Free users always get watermark
        from app.services.token_service import TokenService
        token_service = TokenService(self.db)
        balance = await token_service.get_balance(user_id)
        is_premium = balance > 0
        watermarked = include_watermark if is_premium else True

        expires_at = datetime.now(timezone.utc) + timedelta(hours=EXPORT_EXPIRY_HOURS)

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
            "Created export %s for map %s (format=%s res=%sx wm=%s)",
            export.id, map_id, format, resolution, watermarked,
        )
        return export

    async def process_export(self, export_id: int) -> Export:
        stmt = select(Export).where(Export.id == export_id)
        result = await self.db.execute(stmt)
        export = result.scalar_one_or_none()
        if not export:
            raise ExportError(f"Export {export_id} not found")

        # Eagerly load the map
        map_stmt = select(Map).where(Map.id == export.map_id)
        map_result = await self.db.execute(map_stmt)
        map_obj = map_result.scalar_one_or_none()
        if not map_obj:
            raise ExportError(f"Map {export.map_id} not found for export {export_id}")

        try:
            export.status = ExportStatus.PROCESSING
            await self.db.commit()

            width = BASE_MAP_WIDTH * export.resolution
            height = BASE_MAP_HEIGHT * export.resolution
            hierarchy = map_obj.hierarchy or {}

            if export.format == ExportFormat.PNG:
                file_content = await asyncio.get_event_loop().run_in_executor(
                    None,
                    _render_png,
                    hierarchy, map_obj.name, width, height, export.watermarked,
                )
                file_ext = "png"
            else:
                file_content = _render_svg(
                    hierarchy, map_obj.name, width, height, export.watermarked,
                )
                file_ext = "svg"

            filename = f"map_{export.map_id}_export_{export.id}.{file_ext}"

            # Try R2 upload; fall back to local for dev
            file_path = await self._store_file(file_content, filename, export.user_id, file_ext)

            export.status = ExportStatus.COMPLETED
            export.file_path = file_path
            export.file_size = len(file_content)
            export.completed_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self.db.refresh(export)
            logger.info("Export %s completed (%d bytes) -> %s", export_id, len(file_content), file_path)
            return export

        except Exception as e:
            export.status = ExportStatus.FAILED
            export.error_message = str(e)[:1024]
            await self.db.commit()
            logger.error("Export %s failed: %s", export_id, e, exc_info=True)
            raise ExportError(f"Export generation failed: {e}") from e

    async def _store_file(
        self,
        content: bytes,
        filename: str,
        user_id: int,
        ext: str,
    ) -> str:
        """Upload to R2 if configured, otherwise save locally."""
        try:
            from app.services.r2_storage import get_r2_service
            r2 = get_r2_service()
            mime = "image/png" if ext == "png" else "image/svg+xml"
            r2_path, _ = await r2.upload_file(
                file_content=content,
                filename=filename,
                user_id=user_id,
                mime_type=mime,
            )
            return r2_path
        except Exception as e:
            logger.warning("R2 upload failed, saving locally: %s", e)
            LOCAL_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
            local_path = LOCAL_EXPORT_DIR / filename
            local_path.write_bytes(content)
            return str(local_path)

    async def get_export(self, export_id: int, user_id: int) -> Optional[Export]:
        stmt = select(Export).where(Export.id == export_id, Export.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_download_url(self, export: Export) -> Optional[str]:
        if export.status != ExportStatus.COMPLETED or not export.file_path:
            return None
        if export.expires_at and export.expires_at < datetime.now(timezone.utc):
            return None

        # Local file — return direct path
        if export.file_path.startswith("/app/exports/"):
            return f"/api/v1/maps/exports/file/{os.path.basename(export.file_path)}"

        # R2 — presigned URL
        try:
            from app.services.r2_storage import get_r2_service
            r2 = get_r2_service()
            return await r2.generate_presigned_url(
                bucket_name=settings.R2_BUCKET_EXPORTS,
                r2_path=export.file_path,
                expiry_seconds=3600,
            )
        except Exception:
            return None

    async def list_user_exports(
        self,
        user_id: int,
        map_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Export], int]:
        from sqlalchemy import func
        stmt = select(Export).where(Export.user_id == user_id)
        if map_id:
            stmt = stmt.where(Export.map_id == map_id)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await self.db.scalar(count_stmt) or 0
        stmt = stmt.order_by(Export.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total


def get_export_service(db: AsyncSession) -> ExportService:
    return ExportService(db)
