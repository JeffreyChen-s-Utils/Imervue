"""Meme caption generator — top / bottom Impact text with an outline.

Renders uppercase, word-wrapped captions at the top and bottom of an image in
the classic white-fill / black-stroke meme style. Distinct from the corner
text watermark and the single caption-strip frame. Pure Pillow drawing; the
word-wrap helper is a pure function unit-tested without Qt.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_OPAQUE = 255
DEFAULT_FONT_FRACTION = 0.11
_MIN_FONT = 14
_STROKE_DIVISOR = 14
_WRAP_WIDTH_FRAC = 0.94
_MARGIN_FRAC = 0.03


def _candidate_fonts() -> list[Path]:
    return [
        Path("C:/Windows/Fonts/impact.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/System/Library/Fonts/Supplemental/Impact.ttf"),
    ]


def _load_font(size: int):
    for candidate in _candidate_fonts():
        try:
            return ImageFont.truetype(str(candidate), size)
        except (OSError, ValueError):
            continue
    return ImageFont.load_default()


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: float) -> list[str]:
    """Greedily wrap *text* so each line fits *max_width* pixels."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if not current or draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def _validate(arr: np.ndarray) -> None:
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 image, got {arr.shape}")


def _to_rgba(arr: np.ndarray) -> Image.Image:
    mode = "RGBA" if arr.shape[2] == _RGBA_CHANNELS else "RGB"
    return Image.fromarray(arr, mode).convert("RGBA")


def _draw_block(draw, text, font, stroke, img_w, img_h, *, top) -> None:
    lines = wrap_text(draw, text.upper(), font, img_w * _WRAP_WIDTH_FRAC)
    ascent, descent = font.getmetrics()
    line_h = ascent + descent + stroke
    margin = int(img_h * _MARGIN_FRAC)
    y0 = margin if top else img_h - margin - line_h * len(lines)
    for index, line in enumerate(lines):
        draw.text(
            (img_w // 2, y0 + index * line_h), line, font=font, fill="white",
            stroke_width=stroke, stroke_fill="black", anchor="ma", align="center")


def make_meme(
    arr: np.ndarray,
    top_text: str = "",
    bottom_text: str = "",
    font_fraction: float = DEFAULT_FONT_FRACTION,
) -> np.ndarray:
    """Return *arr* (HxWx3/4 uint8) with meme captions; HxWx4 RGBA."""
    _validate(arr)
    base = _to_rgba(arr)
    draw = ImageDraw.Draw(base)
    h, w = arr.shape[:2]
    size = max(_MIN_FONT, int(h * font_fraction))
    font = _load_font(size)
    stroke = max(1, size // _STROKE_DIVISOR)
    if top_text.strip():
        _draw_block(draw, top_text, font, stroke, w, h, top=True)
    if bottom_text.strip():
        _draw_block(draw, bottom_text, font, stroke, w, h, top=False)
    return np.array(base)
