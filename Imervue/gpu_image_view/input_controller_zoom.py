"""Wheel, keyboard, double-click, minimap and rubber-band zoom for the GPU view.

Mixed into :class:`~Imervue.gpu_image_view.input_controller.InputController`;
reads and mutates the live view through ``self._view``. Owns the zoom limits
and step factors that the gesture path shares.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QApplication

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.qt_timers import call_later
from Imervue.gpu_image_view.minimap import point_in_rect, recenter_offsets
from Imervue.gpu_image_view.view_nav import (
    stepped_zoom,
    toggle_zoom_target,
    zoom_about_point,
    zoom_to_region,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

ZOOM_MIN = 0.05
ZOOM_MAX = 50.0
WHEEL_ZOOM_IN_FACTOR = 1.1
WHEEL_ZOOM_OUT_FACTOR = 0.9
KEYBOARD_ZOOM_FACTOR = 1.25
_ZOOM_LIMIT_REARM_MS = 2000


class InputZoomMixin:
    """Zoom and minimap navigation behaviour of the input controller."""

    _view: GPUImageView

    # -- wheel / zoom -------------------------------------------------

    def handle_deep_zoom_wheel(self, event, delta) -> None:
        """Apply a wheel zoom step to the deep-zoom view. Scrolling over the
        minimap zooms into the pointed location; elsewhere the zoom re-anchors
        around the cursor. At the zoom limit, surface a throttled toast."""
        view = self._view
        factor = WHEEL_ZOOM_IN_FACTOR if delta > 0 else WHEEL_ZOOM_OUT_FACTOR
        old_zoom = view.zoom
        new_zoom = stepped_zoom(old_zoom, factor, ZOOM_MIN, ZOOM_MAX)
        if new_zoom == old_zoom:
            self.notify_zoom_limit_once(new_zoom)
            return
        pos = event.position()
        rect = view._current_minimap_rect()
        if rect is not None and point_in_rect(pos.x(), pos.y(), rect):
            view.zoom = new_zoom
            self._recenter_on_minimap(pos, rect, new_zoom)
        elif view._smooth_nav_enabled:
            view._zoom_ease.animate_to(new_zoom, pos.x(), pos.y())
        else:
            view.zoom = new_zoom
            self.anchor_zoom_about(pos, old_zoom, new_zoom)

    def zoom_step(self, zoom_in: bool) -> None:
        """Keyboard zoom in/out, anchored on the viewport centre."""
        view = self._view
        if not view.deep_zoom:
            return
        from PySide6.QtCore import QPointF
        factor = KEYBOARD_ZOOM_FACTOR if zoom_in else 1 / KEYBOARD_ZOOM_FACTOR
        old_zoom = view.zoom
        new_zoom = stepped_zoom(old_zoom, factor, ZOOM_MIN, ZOOM_MAX)
        if new_zoom == old_zoom:
            self.notify_zoom_limit_once(new_zoom)
            return
        center = QPointF(view.width() / 2, view.height() / 2)
        if view._smooth_nav_enabled:
            view._zoom_ease.animate_to(new_zoom, center.x(), center.y())
        else:
            view.zoom = new_zoom
            self.anchor_zoom_about(center, old_zoom, new_zoom)

    def anchor_zoom_about(self, pos, old_zoom: float, new_zoom: float) -> None:
        """Re-anchor the deep-zoom offset so the image point under *pos* stays
        put across a zoom change, then refresh status + repaint."""
        view = self._view
        view.dz_offset_x = zoom_about_point(view.dz_offset_x, pos.x(), old_zoom, new_zoom)
        view.dz_offset_y = zoom_about_point(view.dz_offset_y, pos.y(), old_zoom, new_zoom)
        view._browse.clamp_pan()
        view._user_locked_view = True
        view._update_status_info()
        view.update()

    def notify_zoom_limit_once(self, new_zoom: float) -> None:
        """Toast the zoom-limit hint once and rearm 2 s later."""
        view = self._view
        if getattr(view, "_zoom_limit_shown", False):
            return
        view._zoom_limit_shown = True
        if hasattr(view.main_window, "toast"):
            limit = "5000%" if new_zoom >= ZOOM_MAX else "5%"
            lang = language_wrapper.language_word_dict
            view.main_window.toast.info(
                lang.get("zoom_limit_toast", "Zoom limit: {limit}").format(limit=limit))
        call_later(_ZOOM_LIMIT_REARM_MS, view, lambda: setattr(view, "_zoom_limit_shown", False))

    def toggle_zoom_at(self, pos) -> None:
        """Toggle between fit-to-window and 100%.

        Zooming to 100% anchors on the cursor; returning to fit re-centres the
        image (anchoring on the cursor would leave it off-centre once it's
        small enough to fit).
        """
        view = self._view
        fit = view._fit_zoom()
        target = toggle_zoom_target(view.zoom, fit)
        if target == fit:
            view._fit_to_window()
            view.update()
            return
        old_zoom = view.zoom
        view.zoom = target
        self.anchor_zoom_about(pos, old_zoom, target)

    # -- minimap navigation -------------------------------------------

    def begin_minimap_nav(self, pos) -> bool:
        """Start click-to-navigate if *pos* is inside the minimap. Returns
        True when the click was consumed by the minimap."""
        view = self._view
        rect = view._current_minimap_rect()
        if rect is None or not point_in_rect(pos.x(), pos.y(), rect):
            return False
        view._minimap_dragging = True
        self.minimap_nav_to(pos)
        return True

    def minimap_nav_to(self, pos) -> None:
        """Recenter the deep-zoom viewport on the image point under *pos*."""
        view = self._view
        rect = view._current_minimap_rect()
        if rect is None:
            return
        self._recenter_on_minimap(pos, rect, view.zoom)

    def _recenter_on_minimap(self, pos, rect, zoom: float) -> None:
        from Imervue.gpu_image_view.fit_view import content_size
        view = self._view
        base = view.deep_zoom.levels[0]
        # Centre the clicked image point in the content area (above the reserved
        # band), not the full canvas, so the target doesn't land ~band/2 low.
        content_w, content_h = content_size(view)
        view.dz_offset_x, view.dz_offset_y = recenter_offsets(
            (pos.x(), pos.y()), rect, (base.shape[1], base.shape[0]),
            (content_w, content_h), zoom,
        )
        view._browse.clamp_pan()
        view._user_locked_view = True
        view._update_status_info()
        view.update()

    # -- rubber-band zoom (deep zoom) ---------------------------------

    def begin_zoom_band(self, pos) -> None:
        """Start a left-drag rubber-band that zooms into the framed region."""
        view = self._view
        view._zoom_band_active = True
        view._zoom_band_start = pos
        view._zoom_band_end = pos

    def update_zoom_band(self, event) -> None:
        from PySide6.QtCore import Qt
        view = self._view
        if not (view._zoom_band_active
                and event.buttons() & Qt.MouseButton.LeftButton):
            return
        view._zoom_band_end = event.position()
        view.update()

    def finish_zoom_band(self, pos) -> bool:
        """Apply the rubber-band zoom on release; a too-small box is ignored."""
        view = self._view
        if not view._zoom_band_active:
            return False
        view._zoom_band_active = False
        start = view._zoom_band_start
        view._zoom_band_start = None
        view._zoom_band_end = None
        if start is not None and view.deep_zoom and self._band_big_enough(start, pos):
            self._apply_zoom_band(start, pos)
        else:
            view.update()
        return True

    @staticmethod
    def _band_big_enough(start, end) -> bool:
        threshold = QApplication.startDragDistance()
        return (abs(end.x() - start.x()) > threshold
                and abs(end.y() - start.y()) > threshold)

    def _apply_zoom_band(self, start, end) -> None:
        view = self._view
        # Fit the boxed region into the content area (canvas minus the reserved
        # overlay band), not the full canvas — otherwise a height-limited
        # selection over-zooms and its bottom rows land behind the minimap /
        # filmstrip instead of filling the visible area above them.
        from Imervue.gpu_image_view.fit_view import content_size
        new_zoom, off_x, off_y = zoom_to_region(
            (start.x(), start.y(), end.x(), end.y()),
            view.zoom, (view.dz_offset_x, view.dz_offset_y),
            content_size(view), (ZOOM_MIN, ZOOM_MAX),
        )
        view.zoom = new_zoom
        view.dz_offset_x = off_x
        view.dz_offset_y = off_y
        view._browse.clamp_pan()
        view._user_locked_view = True
        view._update_status_info()
        view.update()
