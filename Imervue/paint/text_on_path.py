"""Render text glyphs along a polyline path.

Two layers:

* Pure-math helpers (Qt-free, easy to unit-test):
  :func:`path_length` measures a polyline's total arc length;
  :func:`sample_path` returns the ``(x, y, tangent_radians)`` point
  at a given distance along the polyline.
* :func:`render_text_on_path` (Qt) walks the path placing each
  glyph rotated to the local tangent, mirroring Photoshop /
  MediBang's Text-on-Path tool.

The renderer takes a target canvas size + the path points + font
parameters and returns an HxWx4 RGBA buffer the caller can
composite onto a layer.
"""
from __future__ import annotations

import math

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter

from Imervue.paint.text_render import DEFAULT_FAMILY, SIZE_MAX, SIZE_MIN


# ---------------------------------------------------------------------------
# Pure-math helpers
# ---------------------------------------------------------------------------


def path_length(points: list[tuple[float, float]]) -> float:
    """Total arc length of a polyline."""
    if len(points) < 2:
        return 0.0
    total = 0.0
    for i in range(1, len(points)):
        dx = points[i][0] - points[i - 1][0]
        dy = points[i][1] - points[i - 1][1]
        total += math.hypot(dx, dy)
    return total


def cumulative_distances(points: list[tuple[float, float]]) -> list[float]:
    """Per-vertex cumulative arc lengths starting at 0."""
    if not points:
        return []
    out = [0.0]
    for i in range(1, len(points)):
        dx = points[i][0] - points[i - 1][0]
        dy = points[i][1] - points[i - 1][1]
        out.append(out[-1] + math.hypot(dx, dy))
    return out


def sample_path(
    points: list[tuple[float, float]],
    distance: float,
    cumulative: list[float] | None = None,
) -> tuple[float, float, float]:
    """Return ``(x, y, tangent_radians)`` at ``distance`` along the path.

    ``distance`` is clamped to ``[0, path_length]``. ``cumulative``
    can be supplied to avoid recomputing for repeated queries — the
    caller must pass the same list :func:`cumulative_distances`
    would produce.
    """
    if len(points) < 2:
        raise ValueError("path must have at least 2 points")
    if cumulative is None:
        cumulative = cumulative_distances(points)
    total = cumulative[-1]
    if total <= 0.0:
        x, y = points[0]
        return (float(x), float(y), 0.0)
    d = max(0.0, min(float(distance), total))
    # Find the segment whose right endpoint is the first one >= d.
    seg = 1
    while seg < len(cumulative) - 1 and cumulative[seg] < d:
        seg += 1
    seg_start = cumulative[seg - 1]
    seg_end = cumulative[seg]
    seg_len = seg_end - seg_start
    if seg_len <= 0.0:
        x, y = points[seg]
    else:
        t = (d - seg_start) / seg_len
        x0, y0 = points[seg - 1]
        x1, y1 = points[seg]
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
    dx = points[seg][0] - points[seg - 1][0]
    dy = points[seg][1] - points[seg - 1][1]
    angle = math.atan2(dy, dx) if (dx != 0.0 or dy != 0.0) else 0.0
    return (float(x), float(y), angle)


# ---------------------------------------------------------------------------
# Qt renderer
# ---------------------------------------------------------------------------


def render_text_on_path(
    text: str,
    points: list[tuple[float, float]],
    canvas_size: tuple[int, int],
    *,
    family: str = DEFAULT_FAMILY,
    size: int = 36,
    color: tuple[int, int, int] = (0, 0, 0),
    bold: bool = False,
    italic: bool = False,
    char_spacing: float = 0.0,
) -> np.ndarray:
    """Render ``text`` along ``points`` into an HxWx4 RGBA buffer.

    ``canvas_size`` is ``(h, w)``. The buffer is fully transparent
    everywhere except where glyphs land. Glyphs that overflow the
    end of the path are silently dropped — useful for "fit text on
    this curve" workflows where the user types more than the path
    can hold.
    """
    h, w = canvas_size
    if h <= 0 or w <= 0:
        raise ValueError(f"canvas_size must be positive, got {canvas_size!r}")
    if len(points) < 2:
        raise ValueError("path must have at least 2 points")
    if not text:
        return np.zeros((h, w, 4), dtype=np.uint8)

    cumulative = cumulative_distances(points)
    total = cumulative[-1]
    if total <= 0.0:
        return np.zeros((h, w, 4), dtype=np.uint8)

    pixel_size = max(SIZE_MIN, min(SIZE_MAX, int(size)))
    font = QFont(family or DEFAULT_FAMILY)
    font.setPixelSize(pixel_size)
    font.setBold(bool(bold))
    font.setItalic(bool(italic))
    metrics = QFontMetricsF(font)

    image = QImage(w, h, QImage.Format.Format_RGBA8888)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    painter.setFont(font)
    painter.setPen(QColor(*color))

    distance = 0.0
    spacing = max(-pixel_size, float(char_spacing))
    try:
        for char in text:
            advance = metrics.horizontalAdvance(char)
            if distance + advance > total + 1e-6:
                break
            centre_distance = distance + advance / 2.0
            x, y, angle = sample_path(points, centre_distance, cumulative)
            painter.save()
            painter.translate(x, y)
            painter.rotate(math.degrees(angle))
            # Draw with the glyph centred on (0, 0); the baseline shift
            # leaves the visible glyph above the path.
            painter.drawText(-advance / 2.0, 0.0, char)
            painter.restore()
            distance += advance + spacing
    finally:
        painter.end()

    from Imervue.paint.text_render import _qimage_to_rgba
    return _qimage_to_rgba(image)
