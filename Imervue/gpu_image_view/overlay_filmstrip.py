"""Filmstrip and image-loading layers of ``OverlayPainter``.

The neighbour-thumbnail strip, the low-res preview and "Loading…" pill shown
while a full image streams in, and the load-failure panel. Mixed into
:class:`~Imervue.gpu_image_view.overlay_painter.OverlayPainter`.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from Imervue.gpu_image_view.filmstrip import (
    BAND_VPAD,
    ITEM_HEIGHT,
    ITEM_WIDTH,
    compute_filmstrip_items,
    filmstrip_band,
    fit_rect_centered,
)
from Imervue.gpu_image_view.overlay_style import (
    _ERROR_PANEL_RGBA,
    _FONT_SEGOE_UI,
    _rgba_to_pixmap,
)

# Filmstrip band background + current-item highlight (amber, matching the
# tile-wall keyboard focus ring).
_FILMSTRIP_BAND_RGBA = (0, 0, 0, 150)
_FILMSTRIP_PLACEHOLDER_RGBA = (40, 40, 40, 200)
_FILMSTRIP_HIGHLIGHT_RGBA = (255, 199, 41, 255)
_FILMSTRIP_BORDER_WIDTH = 3
_LOADING_PILL_RGBA = (0, 0, 0, 170)


class OverlayFilmstripMixin:
    """Filmstrip, loading-preview, loading-pill and load-error overlay layers."""

    def draw_filmstrip(self, painter: QPainter):  # pragma: no cover - GL paint
        """Bottom-of-screen strip of neighbour thumbnails (deep-zoom only)."""
        view = self.view
        images = view.model.images
        strip_width = view._browse.filmstrip_strip_width()
        items = compute_filmstrip_items(
            enabled=view._filmstrip_enabled, in_grid_mode=view.tile_grid_mode,
            current_index=view.current_index, count=len(images),
            strip_width=strip_width,
        )
        if not items:
            return
        y_top, band_h = filmstrip_band(view.height(), ITEM_HEIGHT, BAND_VPAD)
        painter.fillRect(0, int(y_top), int(strip_width), int(band_h),
                         QColor(*_FILMSTRIP_BAND_RGBA))
        for index, x_left in items:
            self._draw_filmstrip_item(painter, images[index], x_left,
                                      y_top + BAND_VPAD, index == view.current_index)

    def _draw_filmstrip_item(self, painter: QPainter, path: str,  # pragma: no cover
                             x_left: float, item_y: float, is_current: bool) -> None:
        pixmap = self._filmstrip_pixmap(path)
        if pixmap is not None:
            fx, fy, fw, fh = fit_rect_centered(
                pixmap.width(), pixmap.height(), x_left, item_y,
                ITEM_WIDTH, ITEM_HEIGHT,
            )
            painter.drawPixmap(int(fx), int(fy), int(fw), int(fh), pixmap)
        else:
            painter.fillRect(int(x_left), int(item_y), ITEM_WIDTH, ITEM_HEIGHT,
                             QColor(*_FILMSTRIP_PLACEHOLDER_RGBA))
        if is_current:
            pen = QPen(QColor(*_FILMSTRIP_HIGHLIGHT_RGBA))
            pen.setWidth(_FILMSTRIP_BORDER_WIDTH)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(int(x_left), int(item_y), ITEM_WIDTH, ITEM_HEIGHT)

    def _filmstrip_pixmap(self, path: str):  # pragma: no cover - GL paint
        """Cached QPixmap for *path*, built lazily from the tile thumbnail cache.

        On a cache miss the thumbnail is requested asynchronously so a path that
        entered deep zoom without a tile-wall pass (open-file, folder refresh
        while zoomed) still fills in instead of staying a blank placeholder."""
        cache = self.view._filmstrip_thumb_cache
        if path in cache:
            return cache[path]
        arr = self.view.tile_cache.get(path)
        if arr is None:
            self.view._ensure_filmstrip_thumbnail(path)
            return None
        pixmap = _rgba_to_pixmap(arr)
        cache[path] = pixmap
        return pixmap

    def draw_loading_preview(self, painter: QPainter) -> None:  # pragma: no cover
        """Background low-res preview shown while the full image streams in."""
        view = self.view
        pixmap = self._filmstrip_pixmap(view._deep_zoom_loading)
        if pixmap is None:
            return
        fx, fy, fw, fh = fit_rect_centered(
            pixmap.width(), pixmap.height(), 0, 0, view.width(), view.height(),
        )
        painter.drawPixmap(int(fx), int(fy), int(fw), int(fh), pixmap)

    def draw_loading_pill(self, painter: QPainter) -> None:  # pragma: no cover
        view = self.view
        lang = view.main_window.language_wrapper.language_word_dict
        text = lang.get("status_loading_image", "Loading image...")
        font = QFont(_FONT_SEGOE_UI)
        font.setPixelSize(14)
        painter.setFont(font)
        fm = painter.fontMetrics()
        pad_x, pad_y = 16, 8
        box_w = fm.horizontalAdvance(text) + pad_x * 2
        box_h = fm.height() + pad_y * 2
        x = (view.width() - box_w) // 2
        y = (view.height() - box_h) // 2
        painter.fillRect(x, y, box_w, box_h, QColor(*_LOADING_PILL_RGBA))
        painter.setPen(QColor(235, 235, 235))
        painter.drawText(x + pad_x, y + pad_y + fm.ascent(), text)

    def draw_deep_zoom_error(self, painter: QPainter) -> None:  # pragma: no cover
        view = self.view
        path, _message = view._deep_zoom_error
        lang = view.main_window.language_wrapper.language_word_dict
        title = lang.get("image_load_failed", "Couldn't load image: {name}").format(
            name=Path(path).name,
        )
        hint = lang.get("missing_relocate_hint", "Right-click to reveal or relocate")
        font = QFont(_FONT_SEGOE_UI)
        font.setPixelSize(15)
        painter.setFont(font)
        fm = painter.fontMetrics()
        box_w = min(view.width() - 40, max(320, fm.horizontalAdvance(title) + 48))
        box_h = fm.height() * 2 + 42
        x = (view.width() - box_w) // 2
        y = (view.height() - box_h) // 2
        painter.fillRect(x, y, box_w, box_h, QColor(*_ERROR_PANEL_RGBA))
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(x + 24, y + 22 + fm.ascent(), title)
        painter.setPen(QColor(225, 225, 225))
        painter.drawText(x + 24, y + 22 + fm.height() + fm.ascent(), hint)
