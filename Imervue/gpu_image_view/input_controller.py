"""Pointer / wheel / gesture interaction logic for :class:`GPUImageView`.

The Qt ``*Event`` overrides must stay on the QWidget subclass for Qt to
route events to them, so the view keeps thin forwarders that delegate
here. This controller holds the behaviour: wheel zoom, minimap click
navigation, tile selection / drag-select, double-click fit toggle, and
touchpad pinch / swipe. It reads and mutates view state directly.

Pure geometry (``stepped_zoom``, ``zoom_about_point``, ``recenter_offsets``,
``toggle_zoom_target``, ``point_in_rect``) lives in the ``view_nav`` and
``minimap`` helper modules and is unit-tested there; this module is the
stateful glue between those helpers and the live view.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QApplication

from Imervue.gpu_image_view.actions.select import (
    select_tiles_in_rect,
    switch_to_next_image,
    switch_to_previous_image,
)
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
_EPSILON = 1e-9


class InputController:
    """Own the pointer / wheel / gesture interaction behaviour."""

    def __init__(self, view: GPUImageView) -> None:
        self._view = view

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
            view.main_window.toast.info(f"Zoom limit: {limit}")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(
            _ZOOM_LIMIT_REARM_MS,
            lambda: setattr(view, "_zoom_limit_shown", False),
        )

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
        view = self._view
        base = view.deep_zoom.levels[0]
        view.dz_offset_x, view.dz_offset_y = recenter_offsets(
            pos.x(), pos.y(), rect, base.shape[1], base.shape[0],
            view.width(), view.height(), zoom,
        )
        view._browse.clamp_pan()
        view._user_locked_view = True
        view._update_status_info()
        view.update()

    # -- move / drag --------------------------------------------------

    def update_hover_state(self, event) -> None:
        view = self._view
        # hover 圖片像素座標（status bar 用）
        if view.deep_zoom and not view.tile_grid_mode:
            mx, my = event.position().x(), event.position().y()
            img_x = int((mx - view.dz_offset_x) / max(view.zoom, _EPSILON))
            img_y = int((my - view.dz_offset_y) / max(view.zoom, _EPSILON))
            view._hover_image_xy = (img_x, img_y)
            view._update_status_info()
            if view._loupe_enabled:
                view.update()  # repaint so the magnifier tracks the cursor
        if view.tile_grid_mode:
            view._update_hover_preview(event)

    def handle_middle_drag(self, delta) -> None:
        view = self._view
        if view.tile_grid_mode:
            view.grid_offset_x += delta.x()
            view.grid_offset_y += delta.y()
        elif view.deep_zoom:
            view.dz_offset_x += delta.x()
            view.dz_offset_y += delta.y()
            view._browse.clamp_pan()
            view._user_locked_view = True
            view._last_pan_velocity = (delta.x(), delta.y())
        view.update()

    def start_pan_momentum(self) -> None:
        """Fling the deep-zoom image after a middle-drag release."""
        view = self._view
        if view._smooth_nav_enabled and view.deep_zoom:
            view._pan_momentum.start(*view._last_pan_velocity)

    def handle_left_drag_select(self, event) -> None:
        from PySide6.QtCore import Qt
        view = self._view
        if not (
            view.tile_grid_mode
            and event.buttons() & Qt.MouseButton.LeftButton
            and view._drag_start_pos
        ):
            return
        if not view._drag_selecting and not self._try_begin_drag_select(event):
            return
        view._drag_end_pos = event.position()
        view.update()

    def _try_begin_drag_select(self, event) -> bool:
        """Return True once the drag threshold has been exceeded and a frame-
        selection has started. Returns False while still below threshold or
        when the gesture was consumed by drag-out."""
        view = self._view
        move_delta = event.position() - view._drag_start_pos
        if move_delta.manhattanLength() < QApplication.startDragDistance():
            return False
        from Imervue.gpu_image_view.actions.drag_out import try_start_drag_out
        if try_start_drag_out(view, view._drag_start_pos):
            view._drag_start_pos = None
            view._drag_end_pos = None
            return False
        view.tile_selection_mode = True
        view._drag_selecting = True
        return True

    # -- release / tile activation ------------------------------------

    def handle_tile_release(self, event) -> bool:
        view = self._view
        if view._drag_selecting:
            self.finish_drag_select()
            return True
        mx, my = event.position().x(), event.position().y()
        clicked_tile = self.tile_at(mx, my)
        if not clicked_tile:
            return False
        if not view.tile_selection_mode:
            self.enter_deep_zoom(clicked_tile)
            return True
        self.toggle_tile_selection(clicked_tile)
        return True

    def finish_drag_select(self) -> None:
        view = self._view
        select_tiles_in_rect(view._drag_start_pos, view._drag_end_pos, view)
        view._drag_selecting = False
        view._drag_start_pos = None
        view._drag_end_pos = None
        view.update()

    def tile_at(self, mx: float, my: float) -> str | None:
        for x0, y0, x1, y1, path in self._view.tile_rects:
            if x0 <= mx <= x1 and y0 <= my <= y1:
                return path
        return None

    def enter_deep_zoom(self, path: str) -> None:
        view = self._view
        view._saved_tile_state = {
            "grid_offset_x": view.grid_offset_x,
            "grid_offset_y": view.grid_offset_y,
            "tile_scale": view.tile_scale,
        }
        view.tile_grid_mode = False
        if path in view.model.images:
            view.current_index = view.model.images.index(path)
        view.load_deep_zoom_image(path)

    def toggle_tile_selection(self, path: str) -> None:
        view = self._view
        if path in view.selected_tiles:
            view.selected_tiles.remove(path)
        else:
            view.selected_tiles.add(path)
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
        new_zoom, off_x, off_y = zoom_to_region(
            (start.x(), start.y(), end.x(), end.y()),
            view.zoom, (view.dz_offset_x, view.dz_offset_y),
            (view.width(), view.height()), (ZOOM_MIN, ZOOM_MAX),
        )
        view.zoom = new_zoom
        view.dz_offset_x = off_x
        view.dz_offset_y = off_y
        view._browse.clamp_pan()
        view._user_locked_view = True
        view._update_status_info()
        view.update()

    # -- gestures -----------------------------------------------------

    def handle_gesture_event(self, event) -> None:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QPinchGesture, QSwipeGesture

        pinch = event.gesture(Qt.GestureType.PinchGesture)
        if isinstance(pinch, QPinchGesture):
            self.apply_pinch(pinch)
        swipe = event.gesture(Qt.GestureType.SwipeGesture)
        if isinstance(swipe, QSwipeGesture):
            self.apply_swipe(swipe)

    def apply_pinch(self, pinch) -> None:
        """Two-finger pinch → deep-zoom scale anchored at pinch center."""
        view = self._view
        if not view.deep_zoom:
            return
        from PySide6.QtWidgets import QPinchGesture
        if not (pinch.changeFlags() & QPinchGesture.ChangeFlag.ScaleFactorChanged):
            return
        scale_factor = pinch.scaleFactor()
        if scale_factor <= 0:
            return
        old_zoom = view.zoom
        new_zoom = max(ZOOM_MIN, min(ZOOM_MAX, old_zoom * scale_factor))
        if new_zoom == old_zoom:
            return
        cx, cy = self._pinch_center(pinch)
        ratio = new_zoom / old_zoom
        view.zoom = new_zoom
        view.dz_offset_x = cx - (cx - view.dz_offset_x) * ratio
        view.dz_offset_y = cy - (cy - view.dz_offset_y) * ratio
        view._browse.clamp_pan()
        view._update_status_info()
        view.update()

    def _pinch_center(self, pinch) -> tuple[float, float]:
        """Resolve the pinch anchor in local widget coords.

        Falls back to the widget centre when Qt reports no centre point;
        QPinchGesture reports global coords, so convert when possible."""
        view = self._view
        center = pinch.centerPoint()
        cx = center.x() if center is not None else view.width() / 2
        cy = center.y() if center is not None else view.height() / 2
        with contextlib.suppress(Exception):
            local = view.mapFromGlobal(center.toPoint())
            cx, cy = local.x(), local.y()
        return cx, cy

    def apply_swipe(self, swipe) -> None:
        """Horizontal swipe → previous / next image in deep zoom."""
        view = self._view
        if not view.deep_zoom:
            return
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QSwipeGesture
        if swipe.state() != Qt.GestureState.GestureFinished:
            return
        direction = swipe.horizontalDirection()
        if direction == QSwipeGesture.SwipeDirection.Left:
            switch_to_next_image(main_gui=view)
        elif direction == QSwipeGesture.SwipeDirection.Right:
            switch_to_previous_image(main_gui=view)
