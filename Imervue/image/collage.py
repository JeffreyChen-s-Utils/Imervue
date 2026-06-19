"""Photo collage / grid montage.

Arranges several images into a tidy grid — equal cells with a configurable
inner gap, outer margin and background colour — each image scaled to fit
(letterboxed) and centred in its cell. The single most-requested layout
feature that the contact-sheet PDF doesn't cover (it composites to a flat
image rather than a paginated PDF).

Pure Pillow compositing; takes and returns NumPy RGBA arrays.
"""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from PIL import Image

_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_OPAQUE = 255
DEFAULT_CELL = (400, 400)
DEFAULT_GAP = 12
DEFAULT_MARGIN = 20


def _to_pil_rgba(arr: np.ndarray) -> Image.Image:
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 image, got {arr.shape}")
    mode = "RGBA" if arr.shape[2] == _RGBA_CHANNELS else "RGB"
    return Image.fromarray(arr, mode).convert("RGBA")


def build_collage(
    images: Sequence[np.ndarray],
    columns: int,
    *,
    cell: tuple[int, int] = DEFAULT_CELL,
    gap: int = DEFAULT_GAP,
    margin: int = DEFAULT_MARGIN,
    background: tuple[int, int, int] = (255, 255, 255),
) -> np.ndarray:
    """Composite *images* into a grid; returns an HxWx4 RGBA array."""
    if not images:
        raise ValueError("collage needs at least one image")
    columns = max(1, int(columns))
    rows = -(-len(images) // columns)  # ceil division
    cell_w, cell_h = cell
    gap = max(0, int(gap))
    margin = max(0, int(margin))

    width = margin * 2 + columns * cell_w + (columns - 1) * gap
    height = margin * 2 + rows * cell_h + (rows - 1) * gap
    canvas = Image.new("RGBA", (width, height), (*background, _OPAQUE))

    for index, arr in enumerate(images):
        row, col = divmod(index, columns)
        x = margin + col * (cell_w + gap)
        y = margin + row * (cell_h + gap)
        tile = _to_pil_rgba(arr).copy()
        tile.thumbnail((cell_w, cell_h), Image.Resampling.LANCZOS)
        ox = x + (cell_w - tile.width) // 2
        oy = y + (cell_h - tile.height) // 2
        canvas.alpha_composite(tile, (ox, oy))
    return np.array(canvas)
