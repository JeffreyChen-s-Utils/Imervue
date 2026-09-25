"""QPainter-based overlay (OSD / HUD / histogram / badges) for the viewer.

``GPUImageView`` owns one :class:`OverlayPainter` and delegates every
``QPainter`` overlay layer to it. The painter reads view state through the
``view`` back-reference but never touches the GL context — all of its drawing
goes onto an off-screen ``QImage`` composited by the view in ``_paint_overlay``.

Pure text/geometry helpers (``debug_hud_lines``, ``osd_lines``,
``place_hud_box``, ``visible_pixel_bounds``, ``favorites_set``) are module-level
functions so they can be unit-tested without a GL context.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

from Imervue.gpu_image_view.filmstrip import (
    BAND_VPAD,
    ITEM_HEIGHT,
    ITEM_WIDTH,
    compute_filmstrip_items,
    filmstrip_band,
    fit_rect_centered,
)
from Imervue.gpu_image_view.minimap import MINIMAP_MARGIN
from Imervue.gpu_image_view.hud_geometry import (
    LOUPE_BOX_PX,
    loupe_source_rect,
    place_hud_box,
    visible_pixel_bounds,
)
from Imervue.gpu_image_view.osd_text import (
    debug_hud_lines,
    favorites_set,
    format_exif_osd_lines,
    osd_lines,
)
from Imervue.gpu_image_view.tile_wall_loading import (
    should_show_wall_loading,
    spinner_dots,
    spinner_phase,
    wall_spinner_geometry,
)
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
from Imervue.gpu_image_view.video_badge import video_badge_geometry
from Imervue.gpu_image_view.view_animator import THUMB_FADE_MS
from Imervue.image.histogram import compute_clipping, compute_histogram
from Imervue.image.video_frames import is_video_path

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.gpu_image_view.overlay_painter")

_FONT_SEGOE_UI = "Segoe UI"
_FONT_CONSOLAS = "Consolas"


def _run_overlay_layers(p: QPainter, layers: list) -> list[str]:
    """Call each ``layer(p)``, isolating failures.

    Every overlay layer is composited onto one off-screen image that is blitted
    in a single ``drawImage`` at the end, so an unguarded exception in any one
    layer would discard the WHOLE overlay (filmstrip + chrome) for the frame —
    and, by unwinding past the view's ``painter.end()``, leave the widget
    QPainter open and corrupt the next GL frame (dropping the minimap too).
    Guarding each layer keeps one bad layer from taking the rest down; the
    failure is logged so the real cause surfaces. Returns the names of the
    layers that raised.
    """
    failed: list[str] = []
    for layer in layers:
        try:
            layer(p)
        except Exception:  # one bad layer must not drop the overlay
            name = getattr(layer, "__name__", repr(layer))
            logger.exception("Overlay layer %s failed; skipped this frame", name)
            failed.append(name)
    return failed
# Repaint cadence for the tile-wall placeholder spinner + fade-in pump.
_PLACEHOLDER_TICK_MS = 80

_PIXEL_VIEW_ZOOM = 4.0
_PIXEL_GRID_MAX_CELLS = 40000
_LOUPE_CURSOR_GAP = 24
_LOUPE_BORDER_RGBA = (255, 255, 255, 210)
_LOUPE_CROSSHAIR_RGBA = (255, 80, 80, 200)
# Filmstrip band background + current-item highlight (amber, matching the
# tile-wall keyboard focus ring).
_FILMSTRIP_BAND_RGBA = (0, 0, 0, 150)
_FILMSTRIP_PLACEHOLDER_RGBA = (40, 40, 40, 200)
_FILMSTRIP_HIGHLIGHT_RGBA = (255, 199, 41, 255)
_FILMSTRIP_BORDER_WIDTH = 3
_LOADING_PILL_RGBA = (0, 0, 0, 170)
# Gap between the centred wall spinner and its caption.
_WALL_LABEL_GAP = 22
# Per-tile spinner radius as a fraction of the tile's shorter edge.
_TILE_SPINNER_RATIO = 0.12
_ERROR_PANEL_RGBA = (95, 28, 28, 210)
_MISSING_PANEL_RGBA = (50, 50, 50, 215)
# Video ▶ badge — translucent disc + opaque white play triangle.
# Rubber-band zoom selection rectangle (deep zoom).
_ZOOM_BAND_FILL_RGBA = (70, 140, 255, 40)
_ZOOM_BAND_BORDER_RGBA = (70, 140, 255, 220)
_ZOOM_BAND_BORDER_WIDTH = 2


def _rgba_to_pixmap(arr: np.ndarray) -> QPixmap:
    """Convert an H×W×4 uint8 RGBA array into a detached :class:`QPixmap`.

    ``.copy()`` detaches the ``QImage`` from the numpy buffer before the array
    can be freed (the established project idiom for numpy → Qt image handoff).
    """
    contiguous = np.ascontiguousarray(arr)
    height, width = contiguous.shape[:2]
    qimg = QImage(contiguous.data, width, height, width * 4,
                  QImage.Format.Format_RGBA8888).copy()
    return QPixmap.fromImage(qimg)


class OverlayPainter:
    """Draws every ``QPainter`` overlay layer for a ``GPUImageView``."""

    _MINIMAP_OPACITY = 0.85

    def __init__(self, view: GPUImageView) -> None:
        self.view = view
        self._placeholder_timer: QTimer | None = None

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------
    def collect_layers(self) -> list:
        """Return active overlay layers in draw order (callables p -> None)."""
        view = self.view
        zoom_active = bool((not view.tile_grid_mode) and view.deep_zoom)
        anim_active = bool(view._animation and view._animation.is_animated)
        pixel_active = zoom_active and view._pixel_view and view.zoom >= _PIXEL_VIEW_ZOOM
        filmstrip_active = bool(
            (not view.tile_grid_mode) and view._filmstrip_enabled
            and len(view.model.images) > 1
        )
        loading_active = bool(
            view._deep_zoom_loading and view.deep_zoom is None
            and not view.tile_grid_mode
        )
        error_active = bool(
            getattr(view, "_deep_zoom_error", None) and view.deep_zoom is None
            and not view.tile_grid_mode
        )

        loupe_active = (zoom_active and view._loupe_enabled
                        and view._hover_image_xy is not None)
        tile_loupe_active = bool(
            view.tile_grid_mode and view._loupe_enabled
            and getattr(view, "_hover_tile_path", None) in getattr(view, "tile_cache", {})
        )
        band_active = bool(view._zoom_band_active and view._zoom_band_start
                           and view._zoom_band_end)
        layer_table: list[tuple[bool, object]] = [
            (view.tile_grid_mode and bool(view.tile_rects), self.draw_tile_overlays),
            (view.tile_grid_mode, self.draw_tile_state_overlays),
            (self._wall_loading_active(), self.draw_wall_loading),
            # Low-res preview sits in the background, below the filmstrip and
            # chrome; the "Loading…" pill is added last so it stays on top.
            (loading_active, self.draw_loading_preview),
            (filmstrip_active, self.draw_filmstrip),
            (zoom_active, self.draw_zoom_indicator),
            (zoom_active and view._show_histogram, self.draw_histogram),
            (anim_active, self.draw_anim_indicator),
            (zoom_active and view._show_osd, self.draw_osd),
            (view._show_debug_hud, self.draw_debug_hud),
            (self._quick_hud_active(), self.draw_quick_meta_hud),
            (pixel_active, self.draw_pixel_view),
            (loupe_active, self.draw_loupe),
            (tile_loupe_active, self.draw_tile_loupe),
            (band_active, self.draw_zoom_band),
            (zoom_active and self._current_is_video(), self.draw_video_badge),
            (loading_active, self.draw_loading_pill),
            (error_active, self.draw_deep_zoom_error),
        ]
        return [painter for active, painter in layer_table if active]

    def _current_is_video(self) -> bool:
        """True when the deep-zoom image is a video (so it shows a play badge)."""
        view = self.view
        images = getattr(getattr(view, "model", None), "images", None) or []
        idx = getattr(view, "current_index", -1)
        return bool(0 <= idx < len(images) and is_video_path(images[idx]))

    def draw_video_badge(self, painter: QPainter):  # pragma: no cover - GL paint
        """Centre a play badge over a deep-zoom video poster."""
        view = self.view
        paint_play_badge(painter, video_badge_geometry(0, 0, view.width(), view.height()))

    def draw_tile_overlays(self, painter: QPainter):  # pragma: no cover - GL paint
        """Draw the tile-wall QPainter overlays (labels, badges, placeholders)."""
        self.draw_tile_labels(painter)
        self.draw_tile_badges(painter)
        self.draw_tile_placeholders(painter)

    def paint(self, painter: QPainter) -> None:  # pragma: no cover - GL compositing
        try:
            layers = self.collect_layers()
        except Exception:  # layer selection must not drop the overlay
            logger.exception("Overlay layer collection failed this frame")
            return
        if not layers:
            return
        view = self.view
        dpr = view.devicePixelRatio()
        w, h = view.width(), view.height()
        img = QImage(int(w * dpr), int(h * dpr),
                     QImage.Format.Format_ARGB32_Premultiplied)
        img.setDevicePixelRatio(dpr)
        img.fill(Qt.GlobalColor.transparent)

        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        _run_overlay_layers(p, layers)
        p.end()
        painter.drawImage(0, 0, img)

    # ------------------------------------------------------------------
    # Tile labels + badges
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Indicators
    # ------------------------------------------------------------------
    def draw_zoom_indicator(self, painter: QPainter):  # pragma: no cover - GL paint
        """Show the zoom percentage above the minimap (or bottom-right)."""
        view = self.view
        pct = f"{view.zoom * 100:.0f}%"
        font = QFont(_FONT_CONSOLAS)
        font.setPixelSize(15)
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(pct)
        x = view.width() - tw - MINIMAP_MARGIN - 2
        rect = view._current_minimap_rect()
        if rect is not None:
            y = view.height() - MINIMAP_MARGIN - rect[3] - fm.height() - 4
        else:
            y = view.height() - MINIMAP_MARGIN - 8

        painter.setPen(QColor(0, 0, 0, 160))
        painter.drawText(x + 1, y + 1, pct)
        painter.setPen(QColor(230, 230, 230))
        painter.drawText(x, y, pct)

    def draw_histogram(self, painter: QPainter):  # pragma: no cover - GL paint
        """Draw the RGB+luma histogram and the exposure-clipping readout."""
        view = self.view
        if not view.deep_zoom:
            return
        images = view.model.images
        if not images or view.current_index >= len(images):
            return
        cur_path = images[view.current_index]
        cache = view._histogram_cache
        if cur_path and (not cache or cache[0] != cur_path):
            img = view.deep_zoom.levels[-1]
            view._histogram_cache = (
                cur_path, compute_histogram(img), compute_clipping(img),
            )
        if not view._histogram_cache:
            return
        _, hist, clip = view._histogram_cache
        self._draw_histogram_panel(painter, hist, clip)

    def _draw_histogram_panel(self, painter, hist, clip):  # pragma: no cover - GL paint
        hx, hy, hw, hh = 12, 12, 256, 120
        painter.fillRect(hx - 2, hy - 2, hw + 4, hh + 4, QColor(0, 0, 0, 140))
        h_max = max(hist.r.max(), hist.g.max(), hist.b.max(), hist.luma.max(), 1)
        # Luma sits behind as a faint grey backdrop; RGB curves draw over it.
        channels = (
            (hist.luma, QColor(200, 200, 200, 80)),
            (hist.r, QColor(220, 60, 60, 120)),
            (hist.g, QColor(60, 200, 60, 120)),
            (hist.b, QColor(60, 100, 220, 120)),
        )
        for counts, color in channels:
            path = QPainterPath()
            path.moveTo(hx, hy + hh)
            for i in range(256):
                path.lineTo(hx + i, hy + hh - counts[i] / h_max * hh)
            path.lineTo(hx + 255, hy + hh)
            path.closeSubpath()
            painter.fillPath(path, color)
        self._draw_clipping_readout(painter, clip, hx, hy, hw, hh)

    def _draw_clipping_readout(self, painter, clip, hx, hy, hw, hh):  # pragma: no cover - GL paint
        # Flag the clipped end of the range so the eye is drawn straight to it.
        if clip.over_fraction > 0:
            painter.fillRect(hx + hw - 3, hy, 3, hh, QColor(255, 70, 70, 200))
        if clip.under_fraction > 0:
            painter.fillRect(hx, hy, 3, hh, QColor(80, 130, 255, 200))
        font = QFont(_FONT_CONSOLAS)
        font.setPixelSize(11)
        painter.setFont(font)
        painter.setPen(QColor(235, 235, 235, 220))
        painter.drawText(
            hx, hy + hh + 14,
            f"▲ {clip.over_fraction * 100:.1f}%"
            f"   ▼ {clip.under_fraction * 100:.1f}%",
        )

    def draw_anim_indicator(self, painter: QPainter):  # pragma: no cover - GL paint
        """Draw the animation frame indicator (bottom centre)."""
        view = self.view
        anim = view._animation
        if not anim or not anim.is_animated:
            return

        from Imervue.gpu_image_view.actions.animation_player import anim_indicator_text
        text = anim_indicator_text(anim, view.main_window.language_wrapper.language_word_dict)

        font = QFont(_FONT_CONSOLAS)
        font.setPixelSize(13)
        painter.setFont(font)
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(text)
        th = fm.height()
        x = (view.width() - tw) // 2
        y = view.height() - 20

        painter.fillRect(x - 8, y - th - 2, tw + 16, th + 8, QColor(0, 0, 0, 160))
        painter.setPen(QColor(230, 230, 230))
        painter.drawText(x, y, text)

    # ------------------------------------------------------------------
    # OSD + Debug HUD
    # ------------------------------------------------------------------
    def draw_osd(self, painter: QPainter):  # pragma: no cover - GL paint
        """F3 OSD — file name / size / format in the top-right corner."""
        view = self.view
        path = view._current_path()
        if not path or not view.deep_zoom:
            return
        base = view.deep_zoom.levels[0]
        h, w = base.shape[:2]
        lines = osd_lines(path, w, h) + self._exif_osd_lines(path)

        font = QFont(_FONT_SEGOE_UI)
        font.setPixelSize(13)
        painter.setFont(font)
        fm = painter.fontMetrics()
        pad_x, pad_y = 10, 6
        line_h = fm.height()
        box_w = max(fm.horizontalAdvance(line) for line in lines) + pad_x * 2
        box_h = line_h * len(lines) + pad_y * 2
        x = view.width() - box_w - 12
        y = 12

        painter.fillRect(x, y, box_w, box_h, QColor(0, 0, 0, 170))
        painter.setPen(QColor(230, 230, 230))
        for i, line in enumerate(lines):
            painter.drawText(x + pad_x, y + pad_y + fm.ascent() + i * line_h, line)

    def _exif_osd_lines(self, path: str) -> list:  # pragma: no cover - file IO
        """Cached EXIF OSD lines for *path* (read once per image, not per frame)."""
        view = self.view
        cache = view._exif_osd_cache
        if cache and cache[0] == path:
            return cache[1]
        from Imervue.image.exif_merge import get_exif_data
        lines = format_exif_osd_lines(get_exif_data(Path(path)))
        view._exif_osd_cache = (path, lines)
        return lines

    def draw_debug_hud(self, painter: QPainter):  # pragma: no cover - GL paint
        """Ctrl+F3 Debug HUD — VRAM / cache / thread-pool stats."""
        view = self.view
        stats = {
            "vram_usage": view._vram_usage,
            "vram_limit": view._vram_limit,
            "tile_tex": len(view.tile_textures),
            "tile_cache": len(view.tile_cache),
            "prefetch": len(view._prefetch_cache),
            "prefetch_workers": len(view._prefetch_workers),
            "active_threads": view.thread_pool.activeThreadCount(),
            "max_threads": view.thread_pool.maxThreadCount(),
            "generation": view._load_generation,
            "zoom": view.zoom,
        }
        lines = debug_hud_lines(stats)

        font = QFont(_FONT_CONSOLAS)
        font.setPixelSize(12)
        painter.setFont(font)
        fm = painter.fontMetrics()
        pad_x, pad_y = 8, 5
        line_h = fm.height()
        box_w = max(fm.horizontalAdvance(line) for line in lines) + pad_x * 2
        box_h = line_h * len(lines) + pad_y * 2
        x = 12
        y = view.height() - box_h - 12

        painter.fillRect(x, y, box_w, box_h, QColor(0, 0, 0, 180))
        painter.setPen(QColor(120, 220, 120))
        for i, line in enumerate(lines):
            painter.drawText(x + pad_x, y + pad_y + fm.ascent() + i * line_h, line)

    def _quick_hud_active(self) -> bool:
        hud = getattr(self.view, "_quick_meta_hud", None)
        return bool(hud and hud[1] >= time.monotonic())

    def draw_quick_meta_hud(self, painter: QPainter):  # pragma: no cover - GL paint
        hud = getattr(self.view, "_quick_meta_hud", None)
        if not hud:
            return
        text, expires = hud
        if expires < time.monotonic():
            self.view._quick_meta_hud = None
            return
        font = QFont(_FONT_SEGOE_UI)
        font.setPixelSize(22)
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        fm = painter.fontMetrics()
        w = fm.horizontalAdvance(text) + 36
        h = fm.height() + 22
        x = int((self.view.width() - w) / 2)
        y = 28
        painter.fillRect(x, y, w, h, QColor(0, 0, 0, 185))
        painter.setPen(QColor(255, 235, 145))
        painter.drawText(x + 18, y + 12 + fm.ascent(), text)

    # ------------------------------------------------------------------
    # Pixel view
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Filmstrip + loading feedback
    # ------------------------------------------------------------------
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


def _draw_hover_pixel_outline(painter: QPainter,  # pragma: no cover - GL paint
                              sx: float, sy: float, size: float) -> None:
    pen = QPen(QColor(255, 220, 0, 230))
    pen.setWidth(2)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(int(sx), int(sy), int(size), int(size))
