"""Render a tiny brush-kind preview thumbnail.

Each entry in :data:`Imervue.paint.tool_state.BRUSH_KINDS` paints
with a different stroke profile (pencil grain, marker flat ink,
airbrush soft falloff, watercolor wet edge, sumi pressure curve).
The brush dock surfaces those kinds in a combo box, but the names
alone don't communicate what each one *looks* like — so we render
a 1-line sample stroke per kind and ship it as the combo item icon.

Pure-numpy / Qt-free renderer plus a thin Qt adapter so callers
that just want a numpy buffer (tests, future plugin docs) don't
have to spin up a QApplication.
"""
from __future__ import annotations

import numpy as np

from Imervue.paint.brush_engine import (
    BrushStroke,
    BrushStrokeOptions,
)

# Default thumbnail size is wide-and-short so the entire stroke
# direction is visible inside a typical combo-box row height.
DEFAULT_THUMBNAIL_W = 96
DEFAULT_THUMBNAIL_H = 18


def render_brush_kind_thumbnail(
    kind: str,
    *,
    width: int = DEFAULT_THUMBNAIL_W,
    height: int = DEFAULT_THUMBNAIL_H,
    color: tuple[int, int, int] = (32, 32, 32),
) -> np.ndarray:
    """Return an HxWx4 uint8 RGBA buffer with one sample stroke.

    Layout — single horizontal stroke across the middle of the
    canvas with a small pressure ramp (start / end slightly thinner)
    so kinds with edge-aware shading (sumi, watercolor) telegraph
    their behaviour.

    Falls back to a solid-color stroke for any unknown kind so the
    helper never crashes on a typo or a future kind name.
    """
    if int(width) <= 0 or int(height) <= 0:
        raise ValueError(
            f"thumbnail dimensions must be positive, got {width}×{height}",
        )
    canvas = np.zeros((int(height), int(width), 4), dtype=np.uint8)
    options = BrushStrokeOptions(
        color=color,
        size=max(3, int(height) - 2),
        opacity=1.0,
        hardness=0.6,
        kind=kind,
        seed=0xBEEF,   # deterministic so the thumbnails are stable
    )
    stroke = BrushStroke(options)
    margin = 4
    y = int(height) // 2
    stroke.begin(canvas, float(margin), float(y))
    stroke.extend(canvas, float(int(width) - margin), float(y))
    stroke.end(canvas, float(int(width) - margin), float(y))
    return canvas


def render_brush_kind_pixmap(
    kind: str,
    *,
    width: int = DEFAULT_THUMBNAIL_W,
    height: int = DEFAULT_THUMBNAIL_H,
    color: tuple[int, int, int] = (32, 32, 32),
):
    """Wrap :func:`render_brush_kind_thumbnail` into a ``QPixmap``.

    Lazily imports PySide6 so the numpy renderer above stays usable
    in tests that don't pull in Qt.
    """
    from PySide6.QtGui import QImage, QPixmap

    arr = render_brush_kind_thumbnail(
        kind, width=width, height=height, color=color,
    )
    h, w = arr.shape[:2]
    img = QImage(
        bytes(arr.tobytes()), w, h, 4 * w, QImage.Format.Format_RGBA8888,
    )
    return QPixmap.fromImage(img)
