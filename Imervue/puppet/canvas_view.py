"""Document fitting and cursor-anchored view transforms."""
from __future__ import annotations

from typing import TYPE_CHECKING
from Imervue.puppet.render_prep import fit_view
if TYPE_CHECKING:
    from PySide6.QtGui import QWheelEvent

_ZOOM_STEP = 1.15
_MIN_ZOOM = 0.05
_MAX_ZOOM = 32.0

def _fit_scale_and_pan(
    doc_size: tuple[float, float], width: int, height: int,
) -> tuple[float, float, float] | None:
    """``(scale, pan_x, pan_y)`` fitting ``doc_size`` into ``width`` x ``height``.

    Keeps the aspect ratio and centres the document, so the whole canvas
    lands inside the target with no cropping. ``None`` when the document has
    no area.
    """
    doc_w, doc_h = doc_size
    if doc_w <= 0 or doc_h <= 0:
        return None
    scale = min(width / doc_w, height / doc_h)
    return scale, (width - doc_w * scale) / 2.0, (height - doc_h * scale) / 2.0


class PuppetCanvasViewMixin:
    """Document fitting and cursor-anchored view transforms."""

    def reset_view(self) -> None:
        """Recompute fit-to-window pan/zoom on the next paint."""
        self._user_view_locked = False
        self.update()

    def zoom_factor(self) -> float:
        return self._zoom

    def _maybe_refit_view(self) -> None:  # pragma: no cover - GL needs display
        if self._user_view_locked:
            return
        size = self._device_pixel_size()
        if self._document is None:
            return
        self._zoom, self._pan_x, self._pan_y = fit_view(
            size, self._document.size,
        )

    def _device_pixel_size(self) -> tuple[int, int]:  # pragma: no cover - Qt edge
        ratio = self.devicePixelRatioF() if hasattr(self, "devicePixelRatioF") else 1.0
        return int(self.width() * ratio), int(self.height() * ratio)

    def wheelEvent(self, event: QWheelEvent) -> None:   # pragma: no cover - Qt UI
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = _ZOOM_STEP if delta > 0 else 1.0 / _ZOOM_STEP
        self._apply_zoom(factor, event.position().x(), event.position().y())

    def _screen_to_image(self, sx: float, sy: float) -> tuple[float, float]:
        if self._zoom == 0:
            return 0.0, 0.0
        return (sx - self._pan_x) / self._zoom, (sy - self._pan_y) / self._zoom

    def _apply_zoom(self, factor: float, sx: float, sy: float) -> None:   # pragma: no cover - Qt UI
        new_zoom = max(_MIN_ZOOM, min(_MAX_ZOOM, self._zoom * factor))
        actual = new_zoom / self._zoom
        # Anchor zoom on the cursor so the puppet under the mouse stays put.
        self._pan_x = sx - (sx - self._pan_x) * actual
        self._pan_y = sy - (sy - self._pan_y) * actual
        self._zoom = new_zoom
        self._user_view_locked = True
        self.zoom_changed.emit(self._zoom)
        self.update()
