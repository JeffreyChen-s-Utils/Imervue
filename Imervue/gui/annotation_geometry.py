"""Coordinate and handle geometry for annotation canvas interaction."""
from __future__ import annotations

import math

from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont

from Imervue.gui.annotation_models import Annotation


def fit_display_scale(bw: int, bh: int, cw: int, ch: int) -> float:
    """Scale to fit a ``bw×bh`` image into a ``cw×ch`` canvas, capped at 1.0.

    Never upscales — an image smaller than the canvas stays at native size and
    is centred, matching the deep-zoom fit so the Modify view doesn't blow a
    small image up to fill the (now full-width) canvas. Returns 0 for a
    degenerate image / canvas so the caller can skip painting.
    """
    if bw <= 0 or bh <= 0 or cw <= 0 or ch <= 0:
        return 0.0
    return min(cw / bw, ch / bh, 1.0)



def point_segment_distance(
    px: float, py: float,
    a: tuple[int, int], b: tuple[int, int],
) -> float:
    """Shortest distance from point ``(px,py)`` to segment ``a-b``.

    Used for line/arrow/freehand hit testing so the user can click near
    a diagonal line without having to hit the (much larger) bounding box.
    """
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    return math.hypot(px - proj_x, py - proj_y)



def resize_points(
    orig: list[tuple[int, int]],
    handle: str,
    dx: int,
    dy: int,
) -> list[tuple[int, int]]:
    """Apply a resize-handle drag to a 2-point bounding annotation.

    For freehand / multi-point annotations we only remap the *endpoints*,
    which is imperfect but keeps the interaction simple. A real scale
    around the bounding box centroid would be nicer — worth a follow-up.
    """
    if len(orig) < 2:
        return orig
    x1, y1 = orig[0]
    x2, y2 = orig[-1]
    mnx, mxx = min(x1, x2), max(x1, x2)
    mny, mxy = min(y1, y2), max(y1, y2)
    if "w" in handle:
        mnx += dx
    if "e" in handle:
        mxx += dx
    if "n" in handle:
        mny += dy
    if "s" in handle:
        mxy += dy
    return [(mnx, mny)] + orig[1:-1] + [(mxx, mxy)]



def handle_positions(r: QRectF) -> list[tuple[float, float]]:
    cx = (r.left() + r.right()) / 2
    cy = (r.top() + r.bottom()) / 2
    return [
        (r.left(), r.top()),      # nw
        (cx, r.top()),            # n
        (r.right(), r.top()),     # ne
        (r.right(), cy),          # e
        (r.right(), r.bottom()),  # se
        (cx, r.bottom()),         # s
        (r.left(), r.bottom()),   # sw
        (r.left(), cy),           # w
    ]


def text_bounding_box(ann: Annotation) -> tuple[int, int, int, int]:
    """Compute (x1, y1, x2, y2) for a text annotation using QFontMetrics."""
    if not ann.text or not ann.points:
        return ann.bounding_box()
    from PySide6.QtGui import QFontMetrics
    font = QFont(ann.font_family) if ann.font_family else QFont()
    font.setPixelSize(max(6, ann.font_size))
    fm = QFontMetrics(font)
    rect = fm.boundingRect(ann.text)
    ax, ay = ann.points[0]
    # QFontMetrics bounding rect: x offset can be negative, y is above baseline
    x1 = ax + rect.x()
    y1 = ay + rect.y()
    x2 = x1 + rect.width()
    y2 = y1 + rect.height()
    return (x1, y1, x2, y2)

