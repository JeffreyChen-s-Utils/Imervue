"""Pointer-event routing between crop, selection, text and drawing gestures."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent

from Imervue.gui.annotation_models import TOOL_CROP, TOOL_SELECT, KIND_TEXT, KIND_FREEHAND
from Imervue.gui.annotation_selection_drag import AnnotationSelectionDragMixin
from Imervue.gui.annotation_creation import AnnotationCreationMixin


class AnnotationPointerMixin(AnnotationSelectionDragMixin, AnnotationCreationMixin):
    """Pointer-event routing between crop, selection, text and drawing gestures."""

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pt = event.position()
        ix, iy = self._screen_to_image(pt.x(), pt.y())

        if self._tool == TOOL_CROP:
            self._press_crop(pt, ix, iy)
            return
        if self._tool == TOOL_SELECT:
            self._press_select(pt, ix, iy)
            return
        if self._tool == KIND_TEXT:
            self._begin_text_edit(ix, iy)
            return
        self._begin_shape(ix, iy)


    def mouseMoveEvent(self, event: QMouseEvent):
        pt = event.position()
        ix, iy = self._screen_to_image(pt.x(), pt.y())
        self.cursor_image_pos.emit(ix, iy)

        if self._tool == TOOL_CROP:
            self._handle_crop_move(pt, ix, iy)
            return

        if self._tool == TOOL_SELECT and self._drag_mode is None:
            self._update_select_cursor(pt)

        if self._drag_mode is not None and self._drag_orig_points is not None:
            self._drag_selected_annotation(ix, iy)
            return

        if self._drawing is not None:
            if self._drawing.kind == KIND_FREEHAND:
                self._drawing.points.append((ix, iy))
            else:
                self._drawing.points[-1] = (ix, iy)
            self.update()


    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._tool == TOOL_CROP and self._crop_dragging:
            self._finish_crop_drag()
            return
        if self._drag_mode is not None and self._drag_orig_points is not None:
            self._finish_annotation_drag()
            return
        if self._drawing is not None:
            self._finish_drawing()
