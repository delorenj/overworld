"""Watermark helpers for PNG and SVG map exports."""

import math
import os
from html import escape

from PIL import Image, ImageDraw, ImageFont

WATERMARK_TEXT = "Made with Overworld"
WATERMARK_OPACITY = 88


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


def apply_png_watermark(
    image: Image.Image,
    text: str = WATERMARK_TEXT,
    opacity: int = WATERMARK_OPACITY,
) -> Image.Image:
    """Apply a visible diagonal watermark overlay to a PIL image."""
    width, height = image.size
    base = image.convert("RGBA")

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_size = max(26, width // 16)
    font = _get_font(font_size, bold=True)
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]

    pad_x = max(100, text_w // 2)
    pad_y = max(80, text_h * 2)

    for y in range(-height, height * 2, text_h + pad_y):
        for x in range(-width, width * 2, text_w + pad_x):
            draw.text((x, y), text, fill=(45, 55, 72, opacity), font=font)

    rotated = overlay.rotate(-30, expand=False, resample=Image.Resampling.BICUBIC)
    combined = Image.alpha_composite(base, rotated)
    return combined.convert(image.mode)


def build_svg_watermark(
    width: int,
    height: int,
    text: str = WATERMARK_TEXT,
    opacity: float = 0.18,
) -> str:
    """Build SVG watermark markup to inject into an SVG document."""
    safe_text = escape(text)
    font_size = max(26, width // 16)

    diagonal = int(math.hypot(width, height))
    step_x = max(font_size * 6, width // 2)
    step_y = max(font_size * 3, height // 3)

    cx = width // 2
    cy = height // 2

    parts = [
        f'<g id="overworld-watermark" transform="rotate(-30 {cx} {cy})" '
        f'opacity="{opacity}">'
    ]

    for y in range(-diagonal, diagonal * 2, step_y):
        for x in range(-diagonal, diagonal * 2, step_x):
            parts.append(
                f'<text x="{x}" y="{y}" font-family="DejaVu Sans,sans-serif" '
                f'font-size="{font_size}" font-weight="700" fill="#334155">{safe_text}</text>'
            )

    parts.append("</g>")
    return "\n".join(parts)
