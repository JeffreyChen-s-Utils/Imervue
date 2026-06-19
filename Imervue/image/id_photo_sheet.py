"""Passport / ID photo sheet imposition.

Tiles as many copies of a portrait at an exact real-world ID size (e.g.
35×45 mm) as fit on a standard print paper at a chosen DPI, with a small gap
between copies — the everyday "print a sheet of passport photos" need that no
existing tool covers.

Pure Pillow + arithmetic; takes and returns NumPy RGBA arrays.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageOps

_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_OPAQUE = 255
_MM_PER_INCH = 25.4

# Paper sizes in inches (width, height, portrait).
PAPER_SIZES_IN = {
    "4x6": (4.0, 6.0),
    "5x7": (5.0, 7.0),
    "A4": (8.27, 11.69),
    "Letter": (8.5, 11.0),
}
DEFAULT_PHOTO_MM = (35.0, 45.0)
DEFAULT_PAPER = "4x6"
DEFAULT_DPI = 300
DEFAULT_GAP_MM = 3.0


def _to_pil_rgba(arr: np.ndarray) -> Image.Image:
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 image, got {arr.shape}")
    mode = "RGBA" if arr.shape[2] == _RGBA_CHANNELS else "RGB"
    return Image.fromarray(arr, mode).convert("RGBA")


def id_photo_sheet(
    face: np.ndarray,
    photo_mm: tuple[float, float] = DEFAULT_PHOTO_MM,
    paper: str = DEFAULT_PAPER,
    dpi: int = DEFAULT_DPI,
    gap_mm: float = DEFAULT_GAP_MM,
    background: tuple[int, int, int] = (255, 255, 255),
) -> np.ndarray:
    """Tile *face* at ID size across a print sheet; returns an HxWx4 RGBA array."""
    dpi = max(1, int(dpi))
    ppmm = dpi / _MM_PER_INCH
    photo_w = max(1, round(photo_mm[0] * ppmm))
    photo_h = max(1, round(photo_mm[1] * ppmm))
    paper_w_in, paper_h_in = PAPER_SIZES_IN.get(paper, PAPER_SIZES_IN[DEFAULT_PAPER])
    sheet_w = round(paper_w_in * dpi)
    sheet_h = round(paper_h_in * dpi)
    gap = max(0, round(gap_mm * ppmm))

    cols = max(1, (sheet_w + gap) // (photo_w + gap))
    rows = max(1, (sheet_h + gap) // (photo_h + gap))
    tile = ImageOps.fit(_to_pil_rgba(face), (photo_w, photo_h), Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", (sheet_w, sheet_h), (*background, _OPAQUE))
    block_w = cols * photo_w + (cols - 1) * gap
    block_h = rows * photo_h + (rows - 1) * gap
    origin_x = (sheet_w - block_w) // 2
    origin_y = (sheet_h - block_h) // 2
    for row in range(rows):
        for col in range(cols):
            x = origin_x + col * (photo_w + gap)
            y = origin_y + row * (photo_h + gap)
            canvas.alpha_composite(tile, (x, y))
    return np.array(canvas)
