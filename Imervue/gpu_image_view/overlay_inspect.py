"""Pixel-inspection layers of ``OverlayPainter``: pixel grid, loupes, zoom band.

Mixed into :class:`~Imervue.gpu_image_view.overlay_painter.OverlayPainter`.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from Imervue.gpu_image_view.hud_geometry import (
    LOUPE_BOX_PX,
    loupe_source_rect,
    place_hud_box,
    visible_pixel_bounds,
)
from Imervue.gpu_image_view.overlay_style import _FONT_CONSOLAS, _rgba_to_pixmap

_PIXEL_VIEW_ZOOM = 4.0
_PIXEL_GRID_MAX_CELLS = 40000
_LOUPE_CURSOR_GAP = 24
_LOUPE_BORDER_RGBA = (255, 255, 255, 210)
_LOUPE_CROSSHAIR_RGBA = (255, 80, 80, 200)
# Rubber-band zoom selection rectangle (deep zoom).
_ZOOM_BAND_FILL_RGBA = (70, 140, 255, 40)
_ZOOM_BAND_BORDER_RGBA = (70, 140, 255, 220)
_ZOOM_BAND_BORDER_WIDTH = 2


class OverlayInspectMixin:
    """Pixel view, loupe and rubber-band zoom overlay layers."""

    def draw_pixel_view(self, painter: QPainter):  # pragma: no cover - GL paint
        """Shift+P — pixel grid + hover RGB when zoom >= 4x."""
        view = self.view
        if not view.deep_zoom or view.zoom < _PIXEL_VIEW_ZOOM:
            return
        base = view.deep_zoom.levels[0]
        h, w = base.shape[:2]
        x0, y0, x1, y1 = visible_pixel_bounds(
            view.zoom, view.dz_offset_x, view.dz_offset_y,
            view.width(), view.height(), w, h,
        )
        if (x1 - x0) * (y1 - y0) <= _PIXEL_GRID_MAX_CELLS:
            self._draw_pixel_grid(painter, x0, y0, x1, y1)
        if view._hover_image_xy is not None:
            cx, cy = view._hover_image_xy
            if 0 <= cx < w and 0 <= cy < h:
                self._draw_hover_pixel_hud(painter, base, cx, cy)

    def _draw_pixel_grid(self, painter: QPainter,  # pragma: no cover - GL paint
                         x0: int, y0: int, x1: int, y1: int) -> None:
        view = self.view
        pen = QPen(QColor(128, 128, 128, 120))
        pen.setWidth(0)
        painter.setPen(pen)
        y_top = int(y0 * view.zoom + view.dz_offset_y)
        y_bot = int(y1 * view.zoom + view.dz_offset_y)
        for gx in range(x0, x1 + 1):
            sx = int(gx * view.zoom + view.dz_offset_x)
            painter.drawLine(sx, y_top, sx, y_bot)
        x_left = int(x0 * view.zoom + view.dz_offset_x)
        x_right = int(x1 * view.zoom + view.dz_offset_x)
        for gy in range(y0, y1 + 1):
            sy = int(gy * view.zoom + view.dz_offset_y)
            painter.drawLine(x_left, sy, x_right, sy)

    def _draw_hover_pixel_hud(self, painter: QPainter,  # pragma: no cover - GL paint
                              base, cx: int, cy: int) -> None:
        view = self.view
        pixel = base[cy, cx]
        r, g, b = int(pixel[0]), int(pixel[1]), int(pixel[2])
        a = int(pixel[3]) if base.shape[2] >= 4 else 255
        lines = [
            f"({cx}, {cy})",
            f"RGB {r:3d} {g:3d} {b:3d}",
            f"A   {a:3d}    #{r:02X}{g:02X}{b:02X}",
        ]
        font = QFont(_FONT_CONSOLAS)
        font.setPixelSize(12)
        painter.setFont(font)
        fm = painter.fontMetrics()
        pad_x, pad_y = 6, 4
        line_h = fm.height()
        box_w = max(fm.horizontalAdvance(line) for line in lines) + pad_x * 2
        box_h = line_h * len(lines) + pad_y * 2
        sx = cx * view.zoom + view.dz_offset_x
        sy = cy * view.zoom + view.dz_offset_y
        size = view.zoom
        _draw_hover_pixel_outline(painter, sx, sy, size)
        hx, hy = place_hud_box(int(sx), int(sy), int(size), box_w, box_h,
                               view.width(), view.height())
        painter.fillRect(hx, hy, box_w, box_h, QColor(0, 0, 0, 190))
        painter.setPen(QColor(240, 240, 240))
        for i, line in enumerate(lines):
            painter.drawText(hx + pad_x, hy + pad_y + fm.ascent() + i * line_h, line)
        painter.fillRect(hx + box_w - 20, hy + pad_y, 14, 14, QColor(r, g, b))

    def draw_loupe(self, painter: QPainter):  # pragma: no cover - GL paint
        """Cursor-following magnifier showing image pixels at higher zoom."""
        view = self.view
        base = view.deep_zoom.levels[0]
        img_h, img_w = base.shape[:2]
        cx, cy = view._hover_image_xy
        if not (0 <= cx < img_w and 0 <= cy < img_h):
            return
        sample = max(1, round(LOUPE_BOX_PX / view._loupe_magnification))
        left, top, right, bottom = loupe_source_rect(cx, cy, sample, sample,
                                                      img_w, img_h)
        crop = base[top:bottom, left:right]
        if crop.size == 0:
            return
        screen_x = int(cx * view.zoom + view.dz_offset_x)
        screen_y = int(cy * view.zoom + view.dz_offset_y)
        box_x, box_y = place_hud_box(screen_x, screen_y, _LOUPE_CURSOR_GAP,
                                     LOUPE_BOX_PX, LOUPE_BOX_PX,
                                     view.width(), view.height())
        painter.drawPixmap(box_x, box_y, LOUPE_BOX_PX, LOUPE_BOX_PX,
                           _rgba_to_pixmap(crop))
        self._draw_loupe_frame(painter, box_x, box_y)

    def draw_tile_loupe(self, painter: QPainter):  # pragma: no cover - GL paint
        """Tile-grid loupe: magnify the thumbnail under the cursor."""
        view = self.view
        path = getattr(view, "_hover_tile_path", None)
        arr = view.tile_cache.get(path)
        if arr is None:
            return
        rect = next((r for r in view.tile_rects if r[4] == path), None)
        if rect is None:
            return
        x0, y0, x1, y1, _ = rect
        box_x, box_y = place_hud_box(
            int((x0 + x1) / 2), int((y0 + y1) / 2), _LOUPE_CURSOR_GAP,
            LOUPE_BOX_PX, LOUPE_BOX_PX, view.width(), view.height(),
        )
        painter.drawPixmap(box_x, box_y, LOUPE_BOX_PX, LOUPE_BOX_PX,
                           _rgba_to_pixmap(arr))
        self._draw_loupe_frame(painter, box_x, box_y)

    def _draw_loupe_frame(self, painter: QPainter,  # pragma: no cover - GL paint
                          box_x: int, box_y: int) -> None:
        pen = QPen(QColor(*_LOUPE_BORDER_RGBA))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(box_x, box_y, LOUPE_BOX_PX, LOUPE_BOX_PX)
        mid = LOUPE_BOX_PX // 2
        painter.setPen(QColor(*_LOUPE_CROSSHAIR_RGBA))
        painter.drawLine(box_x + mid, box_y, box_x + mid, box_y + LOUPE_BOX_PX)
        painter.drawLine(box_x, box_y + mid, box_x + LOUPE_BOX_PX, box_y + mid)

    def draw_zoom_band(self, painter: QPainter):  # pragma: no cover - GL paint
        """Draw the rubber-band rectangle while the user frames a zoom region."""
        view = self.view
        start, end = view._zoom_band_start, view._zoom_band_end
        left, top = min(start.x(), end.x()), min(start.y(), end.y())
        width, height = abs(end.x() - start.x()), abs(end.y() - start.y())
        painter.fillRect(int(left), int(top), int(width), int(height),
                         QColor(*_ZOOM_BAND_FILL_RGBA))
        pen = QPen(QColor(*_ZOOM_BAND_BORDER_RGBA))
        pen.setWidth(_ZOOM_BAND_BORDER_WIDTH)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(int(left), int(top), int(width), int(height))


def _draw_hover_pixel_outline(painter: QPainter,  # pragma: no cover - GL paint
                              sx: float, sy: float, size: float) -> None:
    pen = QPen(QColor(255, 220, 0, 230))
    pen.setWidth(2)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(int(sx), int(sy), int(size), int(size))
