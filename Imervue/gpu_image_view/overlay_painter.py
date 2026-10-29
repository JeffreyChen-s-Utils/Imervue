"""QPainter-based overlay (OSD / HUD / histogram / badges) for the viewer.

``GPUImageView`` owns one :class:`OverlayPainter` and delegates every
``QPainter`` overlay layer to it. The painter reads view state through the
``view`` back-reference but never touches the GL context — all of its drawing
goes onto an off-screen ``QImage`` composited by the view in ``_paint_overlay``.

This module holds the orchestration (layer selection in draw order, failure
isolation, compositing); the layers are mixins in ``overlay_tiles``,
``overlay_hud``, ``overlay_inspect`` and ``overlay_filmstrip``, sharing fonts
and colours from ``overlay_style``. Pure text/geometry helpers
(``debug_hud_lines``, ``osd_lines``, ``place_hud_box``,
``visible_pixel_bounds``, ``favorites_set``) are module-level functions in
``osd_text`` / ``hud_geometry`` so they can be unit-tested without a GL context.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPainter

from Imervue.gpu_image_view.overlay_filmstrip import OverlayFilmstripMixin
from Imervue.gpu_image_view.overlay_hud import OverlayHudMixin
from Imervue.gpu_image_view.overlay_inspect import _PIXEL_VIEW_ZOOM, OverlayInspectMixin
from Imervue.gpu_image_view.overlay_style import _rgba_to_pixmap
from Imervue.gpu_image_view.overlay_tiles import OverlayTilesMixin
from Imervue.gpu_image_view.tile_badges import paint_play_badge
from Imervue.gpu_image_view.video_badge import video_badge_geometry
from Imervue.image.video_frames import is_video_path

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

__all__ = ["OverlayPainter", "_rgba_to_pixmap", "_run_overlay_layers"]

logger = logging.getLogger("Imervue.gpu_image_view.overlay_painter")


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


class OverlayPainter(OverlayTilesMixin, OverlayHudMixin,
                     OverlayInspectMixin, OverlayFilmstripMixin):
    """Draws every ``QPainter`` overlay layer for a ``GPUImageView``.

    The layers themselves live in the mixins (tile wall, indicators / HUD,
    pixel inspection, filmstrip / loading); this class picks the active ones
    in draw order and composites them.
    """

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
