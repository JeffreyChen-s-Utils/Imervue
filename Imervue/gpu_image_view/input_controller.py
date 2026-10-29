"""Pointer / wheel / gesture interaction logic for :class:`GPUImageView`.

The Qt ``*Event`` overrides must stay on the QWidget subclass for Qt to
route events to them, so the view keeps thin forwarders that delegate
here. This controller holds the behaviour: wheel zoom, minimap click
navigation, tile selection / drag-select, double-click fit toggle, and
touchpad pinch / swipe. It reads and mutates view state directly.

Pure geometry (``stepped_zoom``, ``zoom_about_point``, ``recenter_offsets``,
``toggle_zoom_target``, ``point_in_rect``) lives in the ``view_nav`` and
``minimap`` helper modules and is unit-tested there; this module is the
stateful glue between those helpers and the live view. Zoom / minimap
behaviour lives in ``input_controller_zoom`` and pointer / tile behaviour in
``input_controller_tiles``; both are mixed into :class:`InputController`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from Imervue.system.best_effort import best_effort
from Imervue.gpu_image_view.actions.select import (
    switch_to_next_image,
    switch_to_previous_image,
)
from Imervue.gpu_image_view.input_controller_tiles import InputTileMixin
from Imervue.gpu_image_view.input_controller_zoom import (
    KEYBOARD_ZOOM_FACTOR,
    WHEEL_ZOOM_IN_FACTOR,
    WHEEL_ZOOM_OUT_FACTOR,
    ZOOM_MAX,
    ZOOM_MIN,
    InputZoomMixin,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

__all__ = [
    "KEYBOARD_ZOOM_FACTOR",
    "WHEEL_ZOOM_IN_FACTOR",
    "WHEEL_ZOOM_OUT_FACTOR",
    "ZOOM_MAX",
    "ZOOM_MIN",
    "InputController",
]


class InputController(InputZoomMixin, InputTileMixin):
    """Own the pointer / wheel / gesture interaction behaviour."""

    def __init__(self, view: GPUImageView) -> None:
        self._view = view

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
        with best_effort("map the gesture centre to the view"):
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
