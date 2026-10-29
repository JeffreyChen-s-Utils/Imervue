"""Mouse / keyboard editing for the safety_review manual canvas.

``_ManualCanvasInputMixin`` draws a box on a left-drag over empty space, moves
the box under a left-drag, removes one on right-click or Delete / Backspace.
It is mixed into ``_ManualCanvas`` (:mod:`_manual_dialog_canvas`) ahead of
``QWidget`` and reads the canvas state that class owns.
"""
from __future__ import annotations

from PySide6.QtCore import Qt

from safety_review._manual import (
    clamp_region,
    is_valid_region,
    move_region,
    normalize_rect,
    region_at,
    to_image_point,
)


class _ManualCanvasInputMixin:
    """Qt input overrides for ``_ManualCanvas``."""

    # -- mouse / keyboard -------------------------------------------

    def mousePressEvent(self, event):  # noqa: N802 - Qt override
        pos = event.position()
        ix, iy = to_image_point(pos.x(), pos.y(), self._scale)
        if event.button() == Qt.MouseButton.RightButton:
            idx = region_at(self._regions, ix, iy)
            if idx >= 0:
                self._remove_region(idx)
                self._selected = -1
                self.update()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            idx = region_at(self._regions, ix, iy)
            if idx >= 0:
                self._selected = idx
                self._moving = True
                self._move_last = (pos.x(), pos.y())
            else:
                self._selected = -1
                self._drawing = True
                self._draw_start = (pos.x(), pos.y())
                self._draw_cur = (pos.x(), pos.y())
            self.update()

    def mouseMoveEvent(self, event):  # noqa: N802 - Qt override
        pos = event.position()
        if self._drawing:
            self._draw_cur = (pos.x(), pos.y())
            self.update()
        elif self._moving and self._selected >= 0:
            last_x, last_y = self._move_last
            dx = (pos.x() - last_x) / (self._scale or 1.0)
            dy = (pos.y() - last_y) / (self._scale or 1.0)
            iw, ih = self.image_size()
            self._regions[self._selected] = clamp_region(
                move_region(self._regions[self._selected], dx, dy), iw, ih)
            self._move_last = (pos.x(), pos.y())
            self.update()

    def mouseReleaseEvent(self, event):  # noqa: N802 - Qt override
        if self._drawing and self._draw_start and self._draw_cur:
            ix0, iy0 = to_image_point(*self._draw_start, self._scale)
            ix1, iy1 = to_image_point(*self._draw_cur, self._scale)
            iw, ih = self.image_size()
            region = clamp_region(normalize_rect(ix0, iy0, ix1, iy1), iw, ih)
            if is_valid_region(region):
                self._regions.append(region)
                self._classes.append(self._current_class)
                self._selected = len(self._regions) - 1
        self._drawing = self._moving = False
        self._draw_start = self._draw_cur = self._move_last = None
        self.update()

    def keyPressEvent(self, event):  # noqa: N802 - Qt override
        if (event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace)
                and self._selected >= 0):
            self._remove_region(self._selected)
            self._selected = -1
            self.update()
        else:
            super().keyPressEvent(event)
