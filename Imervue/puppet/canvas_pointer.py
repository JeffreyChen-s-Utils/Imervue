"""Pointer routing for pan, mesh editing and rig hit areas."""
from __future__ import annotations

from typing import TYPE_CHECKING
from PySide6.QtCore import Qt
from Imervue.puppet.hit_test import hit_test
if TYPE_CHECKING:
    from PySide6.QtGui import QMouseEvent


class PuppetCanvasPointerMixin:
    """Pointer routing for pan, mesh editing and rig hit areas."""

    def mousePressEvent(self, event: QMouseEvent) -> None:   # pragma: no cover - Qt UI
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_anchor = (event.position().x(), event.position().y())
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if event.button() == Qt.MouseButton.RightButton:
            # Right-click anywhere on the canvas clears the bone
            # selection overlay. Cheap shortcut for the user — the
            # tree dock's row picks up the deselect through the
            # ``selection_cleared`` signal.
            self.clear_selection()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        ix, iy = self._screen_to_image(
            event.position().x(), event.position().y(),
        )
        if self._mesh_edit_enabled:
            self.begin_mesh_edit_at(ix, iy)
            return
        self.try_trigger_hit_area_at(ix, iy)

    def try_trigger_hit_area_at(self, image_x: float, image_y: float) -> str | None:
        """Run hit-testing at ``(image_x, image_y)`` and, if a hit area
        contains the point, emit :attr:`hit_area_triggered`. Returns the
        triggered id (or ``None``) so callers can act without going
        through the signal. Exposed as a method so tests can exercise
        the hit path without a real Qt mouse event."""
        if self._document is None or not self._document.hit_areas:
            return None
        hit = hit_test(
            self._document, image_x, image_y,
            deformed_vertices=self._deformed_vertices or None,
        )
        if hit is not None:
            self.hit_area_triggered.emit(hit)
        return hit

    def mouseMoveEvent(self, event: QMouseEvent) -> None:   # pragma: no cover - Qt UI
        if self._panning:
            dx = event.position().x() - self._pan_anchor[0]
            dy = event.position().y() - self._pan_anchor[1]
            self._pan_anchor = (event.position().x(), event.position().y())
            self._pan_x += dx
            self._pan_y += dy
            self._user_view_locked = True
            self.update()
            return
        ix, iy = self._screen_to_image(
            event.position().x(), event.position().y(),
        )
        if self._mesh_edit_enabled and self._mesh_edit_target is not None:
            self.update_mesh_edit_drag(ix, iy)
            return
        self.cursor_moved.emit(ix, iy)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:   # pragma: no cover - Qt UI
        if event.button() == Qt.MouseButton.MiddleButton and self._panning:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return
        if self._mesh_edit_enabled and event.button() == Qt.MouseButton.LeftButton:
            self.end_mesh_edit_drag()
