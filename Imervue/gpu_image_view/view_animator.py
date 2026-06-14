"""Time-based easing for smooth deep-zoom interactions.

The pure functions (``ease_out_cubic``, ``animation_progress``, ``fade_opacity``,
``should_transition`` …) hold the curve / decision math so it is unit-testable
without a timer or GL context; the small Qt controllers drive them off a frame
timer. Used by the image fade-in transition (and, later, eased zoom / momentum
pan), all of which animate view state the renderer already understands.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QElapsedTimer, QTimer

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

# Fade-in duration for a freshly displayed deep-zoom image.
IMAGE_FADE_MS = 160
# Eased-zoom settle time and momentum-pan decay / stop threshold.
ZOOM_EASE_MS = 120
PAN_DECAY = 0.85
PAN_STOP_SPEED = 0.4
# ~60 FPS frame tick for the timer-driven animations.
_TICK_MS = 16
_FULL_OPACITY = 1.0
_COMPLETE = 1.0


def clamp01(value: float) -> float:
    """Clamp a value to the closed unit interval ``[0, 1]``."""
    return max(0.0, min(1.0, value))


def ease_out_cubic(t: float) -> float:
    """Cubic ease-out on a normalised 0..1 progress value (fast then settling)."""
    t = clamp01(t)
    return 1.0 - (1.0 - t) ** 3


def animation_progress(elapsed_ms: float, duration_ms: float) -> float:
    """Linear 0..1 progress; a non-positive duration completes immediately."""
    if duration_ms <= 0:
        return 1.0
    return clamp01(elapsed_ms / duration_ms)


def fade_opacity(elapsed_ms: float, duration_ms: float) -> float:
    """Eased fade-in opacity (0 → 1) for the given elapsed time."""
    return ease_out_cubic(animation_progress(elapsed_ms, duration_ms))


def should_transition(enabled: bool, slideshow_running: bool) -> bool:
    """Whether to play the image fade-in.

    Skipped while a slideshow is running because the slideshow already drives
    the same opacity channel through its own fade animation.
    """
    return bool(enabled and not slideshow_running)


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation from *a* to *b* by fraction *t*."""
    return a + (b - a) * t


def eased_zoom(start_zoom: float, target_zoom: float,
               elapsed_ms: float, duration_ms: float) -> float:
    """Zoom value along the ease-out curve between start and target."""
    return lerp(start_zoom, target_zoom,
                ease_out_cubic(animation_progress(elapsed_ms, duration_ms)))


def image_point_at(screen: float, offset: float, zoom: float) -> float:
    """Image-space coordinate currently under a screen coordinate."""
    return (screen - offset) / zoom if zoom else 0.0


def offset_for_fixed_point(screen: float, image_point: float,
                           zoom: float) -> float:
    """Pan offset that keeps *image_point* pinned under *screen* at *zoom*."""
    return screen - image_point * zoom


def decayed_velocity(velocity: float, factor: float) -> float:
    """One step of exponential velocity decay for momentum panning."""
    return velocity * factor


def velocity_settled(vx: float, vy: float, stop_speed: float) -> bool:
    """True once a flick's speed has decayed below the stop threshold."""
    return (vx * vx + vy * vy) <= stop_speed * stop_speed


class ImageFadeController:
    """Fades a freshly displayed deep-zoom image in via a frame timer."""

    def __init__(self, view: GPUImageView) -> None:
        self._view = view
        self._timer = QTimer(view)
        self._timer.setInterval(_TICK_MS)
        self._timer.timeout.connect(self._tick)
        self._clock = QElapsedTimer()

    def start(self) -> None:  # pragma: no cover - timer-driven
        self._view._slideshow_opacity = 0.0
        self._clock.restart()
        if not self._timer.isActive():
            self._timer.start()
        self._view.update()

    def _tick(self) -> None:  # pragma: no cover - timer-driven
        opacity = fade_opacity(self._clock.elapsed(), IMAGE_FADE_MS)
        self._view._slideshow_opacity = opacity
        self._view.update()
        if opacity >= _FULL_OPACITY:
            self._view._slideshow_opacity = _FULL_OPACITY
            self._timer.stop()


class ZoomEaseController:
    """Eases ``view.zoom`` toward a target while pinning the anchor point."""

    def __init__(self, view: GPUImageView) -> None:
        self._view = view
        self._timer = QTimer(view)
        self._timer.setInterval(_TICK_MS)
        self._timer.timeout.connect(self._tick)
        self._clock = QElapsedTimer()
        self._start_zoom = 1.0
        self._target_zoom = 1.0
        self._anchor = (0.0, 0.0)
        self._image_point = (0.0, 0.0)

    def animate_to(self, target_zoom: float, anchor_x: float,
                   anchor_y: float) -> None:  # pragma: no cover - timer-driven
        view = self._view
        self._start_zoom = view.zoom
        self._target_zoom = target_zoom
        self._anchor = (anchor_x, anchor_y)
        self._image_point = (
            image_point_at(anchor_x, view.dz_offset_x, view.zoom),
            image_point_at(anchor_y, view.dz_offset_y, view.zoom),
        )
        self._clock.restart()
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:  # pragma: no cover - timer-driven
        self._timer.stop()

    def _apply(self, zoom: float) -> None:  # pragma: no cover - timer-driven
        view = self._view
        view.zoom = zoom
        view.dz_offset_x = offset_for_fixed_point(
            self._anchor[0], self._image_point[0], zoom)
        view.dz_offset_y = offset_for_fixed_point(
            self._anchor[1], self._image_point[1], zoom)
        view._clamp_deep_zoom_pan()
        view._user_locked_view = True
        view._update_status_info()
        view.update()

    def _tick(self) -> None:  # pragma: no cover - timer-driven
        elapsed = self._clock.elapsed()
        self._apply(eased_zoom(self._start_zoom, self._target_zoom,
                               elapsed, ZOOM_EASE_MS))
        if animation_progress(elapsed, ZOOM_EASE_MS) >= _COMPLETE:
            self._apply(self._target_zoom)
            self._timer.stop()


class PanMomentumController:
    """Continues a flick-panned deep-zoom image with decaying velocity."""

    def __init__(self, view: GPUImageView) -> None:
        self._view = view
        self._timer = QTimer(view)
        self._timer.setInterval(_TICK_MS)
        self._timer.timeout.connect(self._tick)
        self._velocity = (0.0, 0.0)

    def start(self, vx: float, vy: float) -> None:  # pragma: no cover - timer-driven
        self._velocity = (vx, vy)
        if (not velocity_settled(vx, vy, PAN_STOP_SPEED)
                and not self._timer.isActive()):
            self._timer.start()

    def stop(self) -> None:  # pragma: no cover - timer-driven
        self._velocity = (0.0, 0.0)
        self._timer.stop()

    def _tick(self) -> None:  # pragma: no cover - timer-driven
        view = self._view
        vx, vy = self._velocity
        if not view.deep_zoom or velocity_settled(vx, vy, PAN_STOP_SPEED):
            self._timer.stop()
            return
        view.dz_offset_x += vx
        view.dz_offset_y += vy
        view._clamp_deep_zoom_pan()
        view.update()
        self._velocity = (decayed_velocity(vx, PAN_DECAY),
                          decayed_velocity(vy, PAN_DECAY))
