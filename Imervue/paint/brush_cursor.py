"""Brush-footprint cursor preview generator.

The canvas widget shows a translucent ring at the cursor so the
user can see exactly where the next dab will land. This module is
the pure-numpy half — produces an HxWx4 RGBA buffer with the ring
rasterised at the requested cursor position; the widget blits it
on top of the layer composite as a hover overlay.

Two ring modes:

* outer ring at the brush radius (always rendered);
* an optional inner ring at ``hardness_radius`` so the user sees
  the brush's hard core boundary when working with a soft brush.
"""
from __future__ import annotations

import numpy as np

DEFAULT_CURSOR_COLOR = (0, 0, 0, 200)
# Quick-mask brush cursor — translucent red, 50 % alpha, matches the
# overlay colour rendered by ``quick_mask.quick_mask_overlay`` so the
# user knows their next dab edits the mask, not the layer pixels.
QUICK_MASK_CURSOR_COLOR = (255, 0, 0, 128)
MAX_RADIUS = 4096
MIN_THICKNESS = 1
MAX_THICKNESS = 64


def cursor_color_for_state(
    foreground_rgb: tuple[int, int, int],
    *,
    quick_mask_active: bool = False,
    foreground_alpha: int = 200,
) -> tuple[int, int, int, int]:
    """Pick the cursor ring colour given the active state.

    When quick mask is active the cursor switches to the mask-edit
    red so the user has a visual cue that the brush is editing the
    selection instead of the layer pixels. Otherwise the cursor
    inherits the user's foreground colour with the standard alpha.
    """
    if quick_mask_active:
        return QUICK_MASK_CURSOR_COLOR
    r, g, b = foreground_rgb
    return (int(r), int(g), int(b), int(foreground_alpha))


def render_cursor_ring(
    canvas_size: tuple[int, int],
    cx: float,
    cy: float,
    radius: float,
    *,
    color: tuple[int, int, int, int] = DEFAULT_CURSOR_COLOR,
    thickness: int = 1,
    inner_radius: float | None = None,
) -> np.ndarray:
    """Render a circle outline at ``(cx, cy)`` onto a fresh transparent
    buffer.

    ``thickness`` is the band width in pixels (1 = single-pixel
    outline, 3 = thicker ring etc.). ``inner_radius`` (optional) draws
    a second concentric outline; useful for showing the brush's hard
    core inside a soft falloff.
    """
    h, w = canvas_size
    if h <= 0 or w <= 0:
        raise ValueError(f"canvas_size must be positive, got {canvas_size!r}")
    if radius < 0:
        raise ValueError(f"radius must be >= 0, got {radius!r}")
    if radius > MAX_RADIUS:
        raise ValueError(
            f"radius must be <= {MAX_RADIUS}, got {radius!r}",
        )
    if not MIN_THICKNESS <= int(thickness) <= MAX_THICKNESS:
        raise ValueError(
            f"thickness must be in [{MIN_THICKNESS}, {MAX_THICKNESS}], "
            f"got {thickness!r}",
        )

    out = np.zeros((h, w, 4), dtype=np.uint8)
    if radius == 0 and inner_radius is None:
        return out

    ys, xs = np.indices((h, w), dtype=np.float32)
    dx = xs - float(cx)
    dy = ys - float(cy)
    dist = np.sqrt(dx * dx + dy * dy)
    band = float(thickness) / 2.0

    if radius > 0:
        outer_mask = (dist >= radius - band) & (dist <= radius + band)
        out[outer_mask] = color

    if inner_radius is not None and inner_radius > 0:
        if 0 < radius <= inner_radius:
            raise ValueError(
                f"inner_radius {inner_radius} must be < radius {radius}",
            )
        inner_mask = (
            (dist >= inner_radius - band)
            & (dist <= inner_radius + band)
        )
        out[inner_mask] = color
    return out


def cursor_bbox(
    cx: float, cy: float, radius: float, *, thickness: int = 1,
) -> tuple[int, int, int, int]:
    """Return the smallest pixel rect that contains the cursor ring.

    Useful when the canvas widget wants to limit the redraw region —
    no need to repaint the whole canvas when only a small area
    around the cursor changed."""
    band = max(1, int(thickness)) / 2.0
    half = float(radius) + band + 1.0
    x0 = int(np.floor(cx - half))
    y0 = int(np.floor(cy - half))
    x1 = int(np.ceil(cx + half))
    y1 = int(np.ceil(cy + half))
    return (x0, y0, x1 - x0, y1 - y0)


# ---------------------------------------------------------------------------
# Qt-aware QPixmap cursor — used by ``PaintCanvas`` to render a Medibang-style
# size preview on the system mouse cursor.
# ---------------------------------------------------------------------------

# Below this screen-pixel diameter the ring is too small to read, so the
# canvas falls back to the per-tool ``Qt.CursorShape`` (typically a
# crosshair). Above the upper bound the ring is bigger than the cursor
# bitmap budget would tolerate; the canvas falls back the same way.
BRUSH_CURSOR_MIN_PX = 8
BRUSH_CURSOR_MAX_PX = 512
# Centre crosshair length in pixels — small "+" in the middle of the
# ring so the user can pinpoint where the next dab will land even when
# the brush radius is huge.
_CROSSHAIR_LEN_PX = 4


def make_brush_cursor(
    diameter_px: int, *, eraser: bool = False,
) -> tuple[object, int, int]:
    """Return ``(QPixmap, hot_x, hot_y)`` for a brush-size preview cursor.

    The pixmap holds a transparent canvas with a thin ring at the
    requested screen diameter and a small ``+`` at the centre. Eraser
    cursors get the same ring plus a diagonal slash to distinguish
    them from the brush at a glance — Medibang does the same. The
    hot-spot is the centre of the ring (where the next dab lands).

    ``diameter_px`` must be in
    ``[BRUSH_CURSOR_MIN_PX, BRUSH_CURSOR_MAX_PX]``. Callers above /
    below that range should pick a fallback cursor instead — the
    function raises rather than silently producing an unreadable
    bitmap.

    Lazily imports PySide6 so this module can still be imported in
    test environments that drive only the numpy ring.
    """
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QColor, QPainter, QPen, QPixmap

    if not BRUSH_CURSOR_MIN_PX <= int(diameter_px) <= BRUSH_CURSOR_MAX_PX:
        raise ValueError(
            f"diameter_px must be in [{BRUSH_CURSOR_MIN_PX}, "
            f"{BRUSH_CURSOR_MAX_PX}], got {diameter_px!r}",
        )
    diameter = int(diameter_px)
    # 2-pixel margin so the antialiased ring isn't clipped at the
    # bitmap boundary even on the most zoomed-in case.
    bitmap_size = diameter + 4
    pixmap = QPixmap(bitmap_size, bitmap_size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # Outer ring: black with a 1-pixel white "ghost" beneath so
        # the cursor stays visible on dark and light layer pixels.
        ring_centre = bitmap_size / 2.0
        radius = diameter / 2.0
        for color, width in (
            (QColor(255, 255, 255, 220), 3),
            (QColor(0, 0, 0, 220), 1),
        ):
            pen = QPen(color)
            pen.setWidth(width)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(
                int(ring_centre - radius),
                int(ring_centre - radius),
                diameter,
                diameter,
            )
        # Centre crosshair so the hot-spot is locatable when the
        # ring is too large to imply where the dab will fall.
        cross_pen = QPen(QColor(0, 0, 0, 220))
        cross_pen.setWidth(1)
        painter.setPen(cross_pen)
        cx = bitmap_size // 2
        painter.drawLine(
            QPoint(cx - _CROSSHAIR_LEN_PX, cx),
            QPoint(cx + _CROSSHAIR_LEN_PX, cx),
        )
        painter.drawLine(
            QPoint(cx, cx - _CROSSHAIR_LEN_PX),
            QPoint(cx, cx + _CROSSHAIR_LEN_PX),
        )
        if eraser:
            # Diagonal slash distinguishes eraser from brush at a glance.
            slash_pen = QPen(QColor(0, 0, 0, 220))
            slash_pen.setWidth(1)
            painter.setPen(slash_pen)
            offset = int(diameter / 2.0 * 0.707)   # 45° on the ring
            painter.drawLine(
                QPoint(cx - offset, cx - offset),
                QPoint(cx + offset, cx + offset),
            )
    finally:
        painter.end()
    return (pixmap, bitmap_size // 2, bitmap_size // 2)


# ---------------------------------------------------------------------------
# Per-tool QPixmap icons — Medibang-style "every tool gets its own cursor"
# ---------------------------------------------------------------------------

_TOOL_ICON_SIZE = 24


def make_tool_cursor(tool: str) -> tuple[object, int, int] | None:
    """Return ``(QPixmap, hot_x, hot_y)`` for a tool-icon cursor.

    Drawing tools that paint with ``state.brush.size`` (brush, eraser,
    smudge, blur, clone_stamp) get the size-tracking ring from
    :func:`make_brush_cursor`; this function covers everything else
    where a small recognisable glyph carries more information than
    Qt's generic crosshair / pointing-hand. Returns ``None`` for
    tools that should keep their Qt.CursorShape fallback (move,
    hand, text — those have well-known system shapes already).
    """
    drawer = _TOOL_ICON_DRAWERS.get(tool)
    if drawer is None:
        return None
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPainter, QPixmap

    pixmap = QPixmap(_TOOL_ICON_SIZE, _TOOL_ICON_SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        hot = drawer(painter)
    finally:
        painter.end()
    return (pixmap, hot[0], hot[1])


def _outline_pen(width: float, color):
    """Pen used for the stroked outline pass of every icon.

    Each icon is rendered twice: a thick white-or-light pass for the
    halo and a thin black pass on top for the ink. This keeps the
    cursor legible against both bright and dark canvas pixels.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPen
    pen = QPen(QColor(*color))
    pen.setWidthF(float(width))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _stroke_outlined(painter, path) -> None:
    """Outline-pass + ink-pass stroke for a path."""
    from PySide6.QtCore import Qt
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(_outline_pen(3.5, (255, 255, 255, 220)))
    painter.drawPath(path)
    painter.setPen(_outline_pen(1.2, (0, 0, 0, 230)))
    painter.drawPath(path)


def _fill_outlined(painter, path, fill_color=(0, 0, 0, 220)) -> None:
    """White halo + black-fill rendering for an enclosed shape."""
    from PySide6.QtGui import QBrush, QColor
    painter.setPen(_outline_pen(3.5, (255, 255, 255, 220)))
    painter.setBrush(QBrush(QColor(255, 255, 255, 0)))
    painter.drawPath(path)
    painter.setPen(_outline_pen(1.2, (0, 0, 0, 230)))
    painter.setBrush(QBrush(QColor(*fill_color)))
    painter.drawPath(path)


def _draw_eyedropper(painter) -> tuple[int, int]:
    """Diagonal pipette — bulb at upper-right, tip at lower-left."""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QPainterPath
    body = QPainterPath()
    body.moveTo(QPointF(3.0, 21.0))           # tip (hot-spot)
    body.lineTo(QPointF(15.0, 9.0))           # along the shaft
    body.lineTo(QPointF(20.0, 14.0))          # bulb base corner
    body.lineTo(QPointF(8.0, 26.0))           # back to tip side
    body.closeSubpath()
    _stroke_outlined(painter, body)
    bulb = QPainterPath()
    bulb.addEllipse(QPointF(19.5, 5.5), 4.0, 4.0)
    _fill_outlined(painter, bulb)
    return (3, 21)


def _draw_fill(painter) -> tuple[int, int]:
    """Tilted paint bucket with a drip — hot-spot at the drip."""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QPainterPath
    bucket = QPainterPath()
    bucket.moveTo(QPointF(6.0, 6.0))
    bucket.lineTo(QPointF(18.0, 6.0))
    bucket.lineTo(QPointF(16.0, 16.0))
    bucket.lineTo(QPointF(8.0, 16.0))
    bucket.closeSubpath()
    _stroke_outlined(painter, bucket)
    handle = QPainterPath()
    handle.moveTo(QPointF(8.0, 6.0))
    handle.cubicTo(
        QPointF(8.0, 1.0), QPointF(16.0, 1.0), QPointF(16.0, 6.0),
    )
    _stroke_outlined(painter, handle)
    drip = QPainterPath()
    drip.addEllipse(QPointF(12.0, 21.0), 1.8, 2.5)
    _fill_outlined(painter, drip, fill_color=(50, 110, 220, 230))
    return (12, 22)


def _draw_gradient(painter) -> tuple[int, int]:
    """Black square fading into white square with an arrow."""
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QBrush, QColor, QPainterPath
    dark = QPainterPath()
    dark.addRect(QRectF(2.0, 8.0, 8.0, 8.0))
    painter.setPen(_outline_pen(2.5, (255, 255, 255, 220)))
    painter.setBrush(QBrush(QColor(0, 0, 0, 230)))
    painter.drawPath(dark)
    light = QPainterPath()
    light.addRect(QRectF(14.0, 8.0, 8.0, 8.0))
    painter.setBrush(QBrush(QColor(245, 245, 245, 230)))
    painter.drawPath(light)
    arrow = QPainterPath()
    arrow.moveTo(QPointF(3.0, 12.0))
    arrow.lineTo(QPointF(21.0, 12.0))
    arrow.moveTo(QPointF(18.0, 9.0))
    arrow.lineTo(QPointF(21.0, 12.0))
    arrow.lineTo(QPointF(18.0, 15.0))
    _stroke_outlined(painter, arrow)
    return (3, 12)


def _draw_bezier_pen(painter) -> tuple[int, int]:
    """Pen nib pointing to the lower-left."""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QPainterPath
    nib = QPainterPath()
    nib.moveTo(QPointF(3.0, 21.0))
    nib.lineTo(QPointF(11.0, 7.0))
    nib.lineTo(QPointF(17.0, 13.0))
    nib.lineTo(QPointF(7.0, 23.0))
    nib.closeSubpath()
    _fill_outlined(painter, nib)
    slit = QPainterPath()
    slit.moveTo(QPointF(6.0, 18.0))
    slit.lineTo(QPointF(13.0, 11.0))
    painter.setPen(_outline_pen(1.0, (255, 255, 255, 220)))
    painter.drawPath(slit)
    return (3, 21)


def _draw_select_rect(painter) -> tuple[int, int]:
    """Dashed rectangle with a crosshair — hot-spot at the centre."""
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QPainterPath, QPen
    rect_path = QPainterPath()
    rect_path.addRect(4.0, 4.0, 16.0, 16.0)
    painter.setPen(_outline_pen(3.0, (255, 255, 255, 220)))
    painter.drawPath(rect_path)
    dashed = QPen(QColor(0, 0, 0, 230))
    dashed.setWidthF(1.0)
    dashed.setStyle(Qt.PenStyle.DashLine)
    painter.setPen(dashed)
    painter.drawPath(rect_path)
    cross = QPainterPath()
    cross.moveTo(QPointF(12.0, 8.0))
    cross.lineTo(QPointF(12.0, 16.0))
    cross.moveTo(QPointF(8.0, 12.0))
    cross.lineTo(QPointF(16.0, 12.0))
    _stroke_outlined(painter, cross)
    return (12, 12)


def _draw_select_lasso(painter) -> tuple[int, int]:
    """Open-ended squiggle suggesting a lasso loop."""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QPainterPath
    lasso = QPainterPath()
    lasso.moveTo(QPointF(4.0, 12.0))
    lasso.cubicTo(
        QPointF(4.0, 4.0), QPointF(20.0, 4.0), QPointF(18.0, 13.0),
    )
    lasso.cubicTo(
        QPointF(17.0, 19.0), QPointF(8.0, 21.0), QPointF(7.0, 17.0),
    )
    _stroke_outlined(painter, lasso)
    return (12, 12)


def _draw_select_wand(painter) -> tuple[int, int]:
    """Magic wand with a star at the tip."""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QPainterPath
    wand = QPainterPath()
    wand.moveTo(QPointF(4.0, 21.0))
    wand.lineTo(QPointF(16.0, 9.0))
    _stroke_outlined(painter, wand)
    star = QPainterPath()
    star.moveTo(QPointF(18.0, 4.0))
    star.lineTo(QPointF(20.0, 7.0))
    star.lineTo(QPointF(23.0, 7.5))
    star.lineTo(QPointF(20.5, 10.0))
    star.lineTo(QPointF(21.0, 13.0))
    star.lineTo(QPointF(18.0, 11.5))
    star.lineTo(QPointF(15.0, 13.0))
    star.lineTo(QPointF(15.5, 10.0))
    star.lineTo(QPointF(13.0, 7.5))
    star.lineTo(QPointF(16.0, 7.0))
    star.closeSubpath()
    _fill_outlined(painter, star, fill_color=(240, 200, 50, 230))
    return (4, 21)


def _draw_select_quick(painter) -> tuple[int, int]:
    """Brush-on-bracket — quick selection's "expand from a stroke" feel."""
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QBrush, QColor, QPainterPath
    bracket = QPainterPath()
    bracket.moveTo(QPointF(5.0, 4.0))
    bracket.lineTo(QPointF(2.0, 4.0))
    bracket.lineTo(QPointF(2.0, 20.0))
    bracket.lineTo(QPointF(5.0, 20.0))
    _stroke_outlined(painter, bracket)
    bracket2 = QPainterPath()
    bracket2.moveTo(QPointF(19.0, 4.0))
    bracket2.lineTo(QPointF(22.0, 4.0))
    bracket2.lineTo(QPointF(22.0, 20.0))
    bracket2.lineTo(QPointF(19.0, 20.0))
    _stroke_outlined(painter, bracket2)
    blob = QPainterPath()
    blob.addEllipse(QRectF(8.0, 9.0, 9.0, 6.0))
    painter.setPen(_outline_pen(3.0, (255, 255, 255, 220)))
    painter.setBrush(QBrush(QColor(80, 130, 220, 200)))
    painter.drawPath(blob)
    painter.setPen(_outline_pen(1.0, (0, 0, 0, 230)))
    painter.drawPath(blob)
    return (12, 12)


def _draw_zoom(painter) -> tuple[int, int]:
    """Magnifier with a "+" — hot-spot at the lens centre."""
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QPainterPath
    lens = QPainterPath()
    lens.addEllipse(QRectF(3.0, 3.0, 13.0, 13.0))
    _stroke_outlined(painter, lens)
    handle = QPainterPath()
    handle.moveTo(QPointF(13.5, 13.5))
    handle.lineTo(QPointF(21.0, 21.0))
    _stroke_outlined(painter, handle)
    plus = QPainterPath()
    plus.moveTo(QPointF(9.5, 6.5))
    plus.lineTo(QPointF(9.5, 12.5))
    plus.moveTo(QPointF(6.5, 9.5))
    plus.lineTo(QPointF(12.5, 9.5))
    _stroke_outlined(painter, plus)
    return (10, 10)


_TOOL_ICON_DRAWERS = {
    "eyedropper": _draw_eyedropper,
    "fill": _draw_fill,
    "gradient": _draw_gradient,
    "bezier_pen": _draw_bezier_pen,
    "select_rect": _draw_select_rect,
    "select_lasso": _draw_select_lasso,
    "select_wand": _draw_select_wand,
    "select_quick": _draw_select_quick,
    "zoom": _draw_zoom,
}
