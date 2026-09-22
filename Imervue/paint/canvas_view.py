"""View transform of the paint canvas.

Zoom (clamped, anchored on a screen point), canvas rotation around the
widget centre, fit-to-view, and the screen-to-image mapping every tool uses.
``PaintCanvas`` mixes these methods in.
"""
from __future__ import annotations

import math


ZOOM_MIN = 0.05
ZOOM_MAX = 32.0


def clamp_zoom(value: float) -> float:
    """Clamp a zoom factor into the allowed canvas range."""
    return max(ZOOM_MIN, min(ZOOM_MAX, float(value)))


def wrap_rotation(degrees: float) -> float:
    """Fold a rotation angle into the canonical ``(-180, 180]`` range.

    The view rotation accumulates over multiple ``set_rotation_around_centre``
    calls; without wrapping, an artist who rotates many times in one
    direction would push the field past 360° and surprise downstream
    code that assumes a bounded angle.
    """
    wrapped = ((float(degrees) + 180.0) % 360.0) - 180.0
    if wrapped == -180.0:
        return 180.0
    return wrapped


class PaintCanvasViewMixin:
    """View transform of the paint canvas."""

    def reset_view(self) -> None:
        # Explicit "fit to window" — re-enable auto-fit so subsequent
        # window resizes keep the canvas centred until the user wheels
        # / pans again.
        self._user_view_locked = False
        self._reset_view_to_fit()
        self.update()

    def zoom_factor(self) -> float:
        return self._zoom

    def rotation_degrees(self) -> float:
        """Return the current view rotation in degrees."""
        return float(self._rotation_deg)

    def set_canvas_rotation(self, degrees: float) -> None:
        """Set the view rotation absolutely. Repaints; never mutates pixels."""
        wrapped = wrap_rotation(float(degrees))
        if wrapped == self._rotation_deg:
            return
        self._rotation_deg = wrapped
        self._user_view_locked = True
        self.update()

    def set_rotation_around_centre(
        self, anchor_zoom: float, delta_deg: float,
    ) -> None:
        """Rotate the view by ``delta_deg`` keeping the widget centre fixed.

        ``anchor_zoom`` is informational — the widget centre is the
        anchor in screen space; the maths reduces to a simple delta
        because rotating about the visual midpoint doesn't shift it.
        Pan stays valid because the rotation pivots about the centre,
        not about an off-centre image-space point.
        """
        del anchor_zoom   # accepted for callsite stability; unused
        new_rotation = wrap_rotation(self._rotation_deg + float(delta_deg))
        if new_rotation == self._rotation_deg:
            return
        self._rotation_deg = new_rotation
        self._user_view_locked = True
        self.update()

    def set_zoom(self, factor: float) -> None:
        """Programmatic zoom — pivots about the widget centre.

        Used by the Navigator dock's zoom slider. Marks the view as
        user-controlled so subsequent window resizes don't auto-fit
        away the chosen zoom.
        """
        target = clamp_zoom(factor)
        if target == self._zoom:
            return
        widget_w = max(1, self.width())
        widget_h = max(1, self.height())
        anchor_x = widget_w * 0.5
        anchor_y = widget_h * 0.5
        rel_x = (anchor_x - self._pan_x) / self._zoom
        rel_y = (anchor_y - self._pan_y) / self._zoom
        self._zoom = target
        self._pan_x = anchor_x - rel_x * target
        self._pan_y = anchor_y - rel_y * target
        self._user_view_locked = True
        self.zoom_changed.emit(target)
        self.update()

    def _screen_to_image(self, sx: float, sy: float) -> tuple[float, float]:
        if self._zoom <= 0:
            return (0.0, 0.0)
        # Undo pan + zoom first; then unwind the view rotation around
        # the canvas's image-space midpoint so a rotated canvas still
        # routes brush dabs onto the pixel under the cursor.
        rel_x = (sx - self._pan_x) / self._zoom
        rel_y = (sy - self._pan_y) / self._zoom
        if math.isclose(self._rotation_deg, 0.0, abs_tol=1e-6):
            return (rel_x, rel_y)
        shape = self._document.shape
        if shape is None:
            return (rel_x, rel_y)
        h, w = shape
        cx = float(w) / 2.0
        cy = float(h) / 2.0
        rad = math.radians(-self._rotation_deg)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        dx = rel_x - cx
        dy = rel_y - cy
        return (cx + dx * cos_a - dy * sin_a,
                cy + dx * sin_a + dy * cos_a)

    def _apply_zoom(self, factor: float, anchor_x: float, anchor_y: float) -> None:
        # Keep the point under the cursor stationary while zooming.
        old_zoom = self._zoom
        new_zoom = clamp_zoom(self._zoom * factor)
        if new_zoom == old_zoom:
            return
        rel_x = (anchor_x - self._pan_x) / old_zoom
        rel_y = (anchor_y - self._pan_y) / old_zoom
        self._zoom = new_zoom
        self._pan_x = anchor_x - rel_x * new_zoom
        self._pan_y = anchor_y - rel_y * new_zoom
        # User wheel-zoomed — stop auto-fitting on subsequent resizes.
        self._user_view_locked = True
        self.zoom_changed.emit(new_zoom)
        self.update()

    def _reset_view_to_fit(
        self,
        widget_size: tuple[int, int] | None = None,
    ) -> None:
        """Centre and zoom the document inside the widget.

        ``widget_size`` is an explicit ``(w, h)`` override — used by
        ``resizeGL`` to pass the freshly-reported GL viewport size,
        which can differ from ``self.width() / self.height()`` for a
        few frames during the QTabWidget layout cycle. Without it the
        canvas would fit to the stale cached size and the user would
        see the document anchored off-screen.
        """
        shape = self._document.shape
        if shape is None:
            return
        h, w = shape
        if w <= 0 or h <= 0:
            return
        if widget_size is not None:
            widget_w, widget_h = widget_size
        elif self._last_resize_size != (0, 0):
            # Prefer the last ``resizeGL``-reported size — Qt 6's
            # logical-pixel convention there is consistent across
            # platforms, while ``self.width()`` can briefly lag while
            # the layout settles.
            widget_w, widget_h = self._last_resize_size
        else:
            widget_w = self.width()
            widget_h = self.height()
        if widget_w <= 0 or widget_h <= 0:
            self._fit_pending = True
            return
        raw_zoom = min(widget_w / w, widget_h / h, 1.0)
        if raw_zoom <= ZOOM_MIN:
            # Widget too small (or document oversized) — defer to the
            # next resizeGL so the canvas doesn't lock at the floor zoom.
            self._fit_pending = True
            return
        self._zoom = clamp_zoom(raw_zoom)
        self._pan_x = (widget_w - w * self._zoom) * 0.5
        self._pan_y = (widget_h - h * self._zoom) * 0.5
        self._fit_pending = False
        self._fitted_widget_size = (widget_w, widget_h)
