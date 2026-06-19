"""Photo framing — matte border, Polaroid frame and burned-in caption.

Wraps an image in a coloured matte border, optionally with the thick bottom
margin of an instant-film/Polaroid frame, and can burn a caption into that
bottom band. A common presentation/sharing finish that pairs with the
watermark and export pipeline.

Pure Pillow drawing; takes and returns NumPy RGBA arrays.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw, ImageFont

_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_OPAQUE = 255
_CAPTION_INSET = 8


@dataclass
class FrameOptions:
    """Matte border width, colour, extra bottom margin and an optional caption."""

    border: int = 40
    color: tuple[int, int, int] = (255, 255, 255)
    bottom_extra: int = 0
    caption: str = ""
    text_color: tuple[int, int, int] = (40, 40, 40)


def _to_pil_rgba(arr: np.ndarray) -> Image.Image:
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 image, got {arr.shape}")
    mode = "RGBA" if arr.shape[2] == _RGBA_CHANNELS else "RGB"
    return Image.fromarray(arr, mode).convert("RGBA")


def add_frame(arr: np.ndarray, options: FrameOptions | None = None) -> np.ndarray:
    """Return *arr* wrapped in a matte (+ optional caption); HxWx4 RGBA."""
    opts = options or FrameOptions()
    base = _to_pil_rgba(arr)
    border = max(0, int(opts.border))
    bottom_extra = max(0, int(opts.bottom_extra))
    width = base.width + border * 2
    height = base.height + border * 2 + bottom_extra

    canvas = Image.new("RGBA", (width, height), (*opts.color, _OPAQUE))
    canvas.alpha_composite(base, (border, border))
    if opts.caption.strip():
        _draw_caption(canvas, opts, border, base.height)
    return np.array(canvas)


def _draw_caption(canvas: Image.Image, opts: FrameOptions, border: int, image_h: int) -> None:
    draw = ImageDraw.Draw(canvas)
    band_top = border + image_h
    band_height = canvas.height - band_top
    font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), opts.caption, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = max(border, (canvas.width - text_w) // 2)
    y = band_top + max(_CAPTION_INSET, (band_height - text_h) // 2)
    draw.text((x, y), opts.caption, fill=(*opts.text_color, _OPAQUE), font=font)
