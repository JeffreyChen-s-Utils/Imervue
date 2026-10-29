"""Tile-wall layers of ``OverlayPainter``: captions, badges and loading feedback.

Mixed into :class:`~Imervue.gpu_image_view.overlay_painter.OverlayPainter`;
reads ``self.view`` and owns the placeholder / fade-in repaint pump
(``self._placeholder_timer``).
"""
from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter

from Imervue.gpu_image_view.osd_text import favorites_set
from Imervue.gpu_image_view.overlay_style import _ERROR_PANEL_RGBA, _FONT_SEGOE_UI
from Imervue.gpu_image_view.tile_badges import (
    mtime_date_label,
    paint_bookmark_badge,
    paint_color_strip,
    paint_date_chip,
    paint_favorite_badge,
    paint_play_badge,
    paint_rating_badge,
    paint_stack_badge,
)
from Imervue.gpu_image_view.tile_wall_loading import (
    should_show_wall_loading,
    spinner_dots,
    spinner_phase,
    wall_spinner_geometry,
)
from Imervue.gpu_image_view.video_badge import video_badge_geometry
from Imervue.gpu_image_view.view_animator import THUMB_FADE_MS
from Imervue.image.video_frames import is_video_path

# Repaint cadence for the tile-wall placeholder spinner + fade-in pump.
_PLACEHOLDER_TICK_MS = 80
# Gap between the centred wall spinner and its caption.
_WALL_LABEL_GAP = 22
# Per-tile spinner radius as a fraction of the tile's shorter edge.
_TILE_SPINNER_RATIO = 0.12
_MISSING_PANEL_RGBA = (50, 50, 50, 215)


class OverlayTilesMixin:
    """Tile-wall overlay layers and the placeholder repaint pump."""

    def draw_tile_labels(self, painter: QPainter):  # pragma: no cover - GL paint
        """Draw the file-name caption under each thumbnail."""
        view = self.view
        font = QFont(_FONT_SEGOE_UI)
        font.setPixelSize(13)
        painter.setFont(font)
        fm = painter.fontMetrics()

        for x0, _y0, x1, y1, path in view.tile_rects:
            name = Path(path).stem
            tw = x1 - x0
            elided = fm.elidedText(name, Qt.TextElideMode.ElideRight, int(tw))
            tx = int(x0 + (tw - fm.horizontalAdvance(elided)) / 2)
            ty = int(y1 + fm.ascent() + 2)
            if ty < view.height() + fm.height():
                painter.setPen(QColor(0, 0, 0, 180))
                painter.drawText(tx + 1, ty + 1, elided)
                painter.setPen(QColor(220, 220, 220))
                painter.drawText(tx, ty, elided)

    def draw_tile_badges(self, painter: QPainter):  # pragma: no cover - GL paint
        """Draw rating / favorite / bookmark / colour-label badges per tile."""
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        from Imervue.user_settings.color_labels import _store as _color_store

        ratings = user_setting_dict.get("image_ratings", {}) or {}
        favs = favorites_set(user_setting_dict.get("image_favorites", set()))
        color_store = _color_store()

        font = QFont(_FONT_SEGOE_UI)
        font.setPixelSize(11)
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)

        last_date = None
        for x0, y0, x1, y1, path in self.view.tile_rects:
            color_name = color_store.get(path)
            paint_color_strip(painter, x0, y0, y1, color_name)
            paint_favorite_badge(painter, x0, y0, path in favs, color_name)
            paint_bookmark_badge(painter, y0, x1, path)
            paint_rating_badge(painter, x0, y1, ratings.get(path, 0))
            stack_count = len(getattr(self.view, "_stack_members", {}).get(path, []))
            paint_stack_badge(painter, x1, y1, stack_count)
            if getattr(self.view, "_timeline_grouping_enabled", False):
                date_label = mtime_date_label(path)
                if date_label and date_label != last_date:
                    paint_date_chip(painter, x0, y0, date_label)
                    last_date = date_label
            if is_video_path(path):
                paint_play_badge(painter, video_badge_geometry(x0, y0, x1, y1))

    def draw_tile_placeholders(self, painter: QPainter):  # pragma: no cover - GL paint
        """Draw a rotating dot spinner on tile slots without a thumbnail yet."""
        view = self.view
        rects = getattr(view, "placeholder_rects", None)
        if not rects:
            return

        phase = spinner_phase(time.monotonic())
        for x0, y0, x1, y1 in rects:
            radius = min(x1 - x0, y1 - y0) * _TILE_SPINNER_RATIO
            self._paint_spinner(painter, (x0 + x1) / 2, (y0 + y1) / 2, radius, phase)

        self.ensure_fade_pump()

    @staticmethod
    def _paint_spinner(painter: QPainter, center_x: float, center_y: float,
                       radius: float, phase: float) -> None:  # pragma: no cover
        """Draw one rotating-dot spinner ring centred on (*center_x*, *center_y*)."""
        painter.setPen(Qt.PenStyle.NoPen)
        for dot_x, dot_y, dot_radius, alpha in spinner_dots(
            center_x, center_y, radius, phase,
        ):
            painter.setBrush(QColor(200, 200, 200, alpha))
            painter.drawEllipse(
                int(dot_x - dot_radius), int(dot_y - dot_radius),
                int(dot_radius * 2), int(dot_radius * 2),
            )

    def _wall_loading_active(self) -> bool:
        """Whether the wall-level "scanning folder" spinner should be drawn."""
        view = self.view
        images = getattr(getattr(view, "model", None), "images", None) or []
        return should_show_wall_loading(
            getattr(view, "tile_grid_mode", False),
            len(images),
            getattr(view, "_folder_scan_active", False),
        )

    def draw_wall_loading(self, painter: QPainter):  # pragma: no cover - GL paint
        """Centred spinner + caption while a folder scan has yet to yield tiles."""
        view = self.view
        center_x, center_y, radius = wall_spinner_geometry(view.width(), view.height())
        self._paint_spinner(painter, center_x, center_y, radius,
                            spinner_phase(time.monotonic()))

        lang = view.main_window.language_wrapper.language_word_dict
        text = lang.get("tile_wall_loading", "Loading images...")
        font = QFont(_FONT_SEGOE_UI)
        font.setPixelSize(14)
        painter.setFont(font)
        fm = painter.fontMetrics()
        painter.setPen(QColor(200, 200, 200, 220))
        painter.drawText(
            int(center_x - fm.horizontalAdvance(text) / 2),
            int(center_y + radius + _WALL_LABEL_GAP + fm.ascent()),
            text,
        )
        self.ensure_fade_pump()

    def draw_tile_state_overlays(self, painter: QPainter):  # pragma: no cover - GL paint
        """Draw explicit error/offline messages over failed tile slots."""
        view = self.view
        font = QFont(_FONT_SEGOE_UI)
        font.setPixelSize(12)
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        for rect in getattr(view, "error_tile_rects", []):
            self._draw_tile_state(
                painter, rect,
                view.main_window.language_wrapper.language_word_dict.get(
                    "tile_load_failed", "Load failed",
                ),
                QColor(*_ERROR_PANEL_RGBA),
            )
        for rect in getattr(view, "missing_tile_rects", []):
            self._draw_tile_state(
                painter, rect,
                view.main_window.language_wrapper.language_word_dict.get(
                    "tile_missing", "Missing",
                ),
                QColor(*_MISSING_PANEL_RGBA),
            )

    @staticmethod
    def _draw_tile_state(painter: QPainter, rect, text: str, color: QColor) -> None:
        x0, y0, x1, y1, _path = rect
        w, h = int(x1 - x0), int(y1 - y0)
        if w <= 0 or h <= 0:
            return
        painter.fillRect(int(x0), int(y0), w, h, color)
        painter.setPen(QColor(245, 245, 245))
        painter.drawText(
            int(x0), int(y0), w, h,
            int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap),
            text,
        )

    def tick_placeholder(self) -> None:
        view = self.view
        if view.tile_grid_mode and (getattr(view, "placeholder_rects", None)
                                    or self._tiles_fading()
                                    or self._wall_loading_active()):
            view.update()
        elif self._placeholder_timer and self._placeholder_timer.isActive():
            self._placeholder_timer.stop()

    def _tiles_fading(self) -> bool:
        """True while any tile is still within its fade-in window."""
        times = getattr(self.view, "_tile_load_times", None)
        if not times:
            return False
        now = time.monotonic()
        return any((now - start) * 1000 < THUMB_FADE_MS for start in times.values())

    def ensure_fade_pump(self) -> None:
        """Start the repaint timer so freshly loaded tiles animate their fade.

        Called when a thumbnail arrives even if no placeholders remain, so the
        last tiles of a folder still fade in smoothly rather than popping.
        """
        if self._placeholder_timer is None:
            timer = QTimer(self.view)
            timer.setInterval(_PLACEHOLDER_TICK_MS)
            timer.timeout.connect(self.tick_placeholder)
            self._placeholder_timer = timer
        if not self._placeholder_timer.isActive():
            self._placeholder_timer.start()
