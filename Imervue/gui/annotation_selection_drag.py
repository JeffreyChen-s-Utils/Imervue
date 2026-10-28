"""Selection movement and resize gestures with one undo command on release."""
from __future__ import annotations

from PySide6.QtCore import Qt

from Imervue.gui.annotation_models import TOOL_MOVE
from Imervue.gui.annotation_crop import handle_cursor
from Imervue.gui.annotation_commands import _ModifyAnnotationCommand


class AnnotationSelectionDragMixin:
    """Selection movement and resize gestures with one undo command on release."""

    def _press_select(self, pt, ix: int, iy: int) -> None:
        handle = self._hit_handle(pt)
        if handle is not None:
            sel = self._find(self._selected_id)
            if sel is not None:
                self._drag_mode = f"resize_{handle}"
                self._drag_start_image = (ix, iy)
                self._drag_orig_points = list(sel.points)
                return
        hit = self._hit_annotation(pt)
        if hit is not None:
            self._selected_id = hit.id
            self._drag_mode = TOOL_MOVE
            self._drag_start_image = (ix, iy)
            self._drag_orig_points = list(hit.points)
            self.update()
            return
        self._selected_id = None
        self.update()


    def _update_select_cursor(self, pt) -> None:
        handle = self._hit_handle(pt)
        if handle is not None:
            self.setCursor(handle_cursor(handle))
        elif self._hit_annotation(pt) is not None:
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)


    def _drag_selected_annotation(self, ix: int, iy: int) -> None:
        sel = self._find(self._selected_id or "")
        if sel is None:
            return
        sx, sy = self._drag_start_image  # type: ignore[misc]
        dx, dy = ix - sx, iy - sy
        if self._drag_mode == TOOL_MOVE:
            sel.points = [(p[0] + dx, p[1] + dy) for p in self._drag_orig_points]
        elif self._drag_mode.startswith("resize_"):
            handle = self._drag_mode.split("_", 1)[1]
            sel.points = self._resize_points(
                self._drag_orig_points, handle, dx, dy
            )
        self.update()


    def _finish_annotation_drag(self) -> None:
        sel = self._find(self._selected_id or "")
        if sel is not None:
            new_points = list(sel.points)
            if new_points != self._drag_orig_points:
                # Revert then push command so redo/undo both go through it
                sel.points = [tuple(p) for p in self._drag_orig_points]
                cmd = _ModifyAnnotationCommand(
                    self, sel.id, self._drag_orig_points, new_points
                )
                self._undo_stack.push(cmd)
        self._drag_mode = None
        self._drag_orig_points = None
        self._drag_start_image = None
        self.annotation_changed.emit()
