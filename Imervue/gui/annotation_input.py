"""Inline text editing, keyboard commands, and context menu input."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit

from Imervue.gui.annotation_commands import _AddAnnotationCommand, _DeleteAnnotationCommand
from Imervue.gui.annotation_models import Annotation, KIND_TEXT


class AnnotationInputMixin:
    """Inline text editing, keyboard commands, and context menu input."""

    def _begin_text_edit(self, ix: int, iy: int) -> None:
        self._cancel_text_edit()
        self._text_anchor_image = (ix, iy)
        edit = QLineEdit(self)
        edit.setStyleSheet(
            "QLineEdit { background: rgba(255,255,255,230); "
            "border: 1px solid #0080ff; padding: 2px; }"
        )
        font = edit.font()
        font.setPointSize(14)
        edit.setFont(font)
        pt = self._image_to_screen(ix, iy)
        edit.setGeometry(int(pt.x()), int(pt.y()), 220, 28)
        edit.returnPressed.connect(self._commit_text_edit)
        edit.editingFinished.connect(self._commit_text_edit)
        edit.show()
        edit.setFocus()
        self._text_edit = edit


    def _commit_text_edit(self) -> None:
        if self._text_edit is None or self._text_anchor_image is None:
            return
        text = self._text_edit.text().strip()
        edit = self._text_edit
        anchor = self._text_anchor_image
        # Clear state first so reentrant editingFinished (fires on
        # deleteLater focus-out) doesn't double-commit
        self._text_edit = None
        self._text_anchor_image = None
        edit.deleteLater()
        if text:
            ix, iy = anchor
            ann = Annotation(
                kind=KIND_TEXT,
                points=[(ix, iy)],
                color=self._color,
                stroke_width=self._stroke_width,
                text=text,
                font_size=self._font_size,
                font_family=self._font_family,
            )
            cmd = _AddAnnotationCommand(self, ann)
            self._undo_stack.push(cmd)
            self.annotation_changed.emit()


    def _cancel_text_edit(self) -> None:
        if self._text_edit is not None:
            edit = self._text_edit
            self._text_edit = None
            self._text_anchor_image = None
            edit.deleteLater()


    def _handle_ctrl_key(self, key: int, shift: bool) -> bool:
        """Ctrl-modified shortcuts (save / undo / redo). Returns True when
        consumed.

        The inline Modify panel has no menu bar, so these chords reach the
        canvas; the host wires ``save_requested`` to its save + toast. In the
        standalone dialog the Save/Undo/Redo QActions claim the chords first,
        so this only takes effect where nothing else does.
        """
        actions = {
            (Qt.Key.Key_S, False): self.save_requested.emit,
            (Qt.Key.Key_S, True): self.save_requested.emit,
            (Qt.Key.Key_Z, False): self._undo_stack.undo,
            (Qt.Key.Key_Z, True): self._undo_stack.redo,
            (Qt.Key.Key_Y, False): self._undo_stack.redo,
            (Qt.Key.Key_Y, True): self._undo_stack.redo,
        }
        action = actions.get((key, shift))
        if action is None:
            return False
        action()
        return True


    def contextMenuEvent(self, event):
        """Right-click → let the host (DevelopPanel) show its image menu.

        The canvas only draws with the left button, so the right button is free
        for a context menu. The standalone dialog leaves the signal unconnected,
        so nothing pops up there."""
        self.context_menu_requested.emit(event.globalPos())
        event.accept()


    def keyPressEvent(self, event):
        key = event.key()
        mods = event.modifiers()
        if mods & Qt.KeyboardModifier.ControlModifier and self._handle_ctrl_key(
                key, bool(mods & Qt.KeyboardModifier.ShiftModifier)):
            return
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self._selected_id is not None:
                sel = self._find(self._selected_id)
                if sel is not None:
                    cmd = _DeleteAnnotationCommand(self, sel)
                    self._undo_stack.push(cmd)
                    self.annotation_changed.emit()
                return
            # Nothing selected: Delete acts on the image itself (trash it),
            # like the Imervue tab. Backspace is left alone to avoid surprises.
            if key == Qt.Key.Key_Delete:
                self.delete_image_requested.emit()
                return
        elif key == Qt.Key.Key_Escape:
            self._selected_id = None
            self._cancel_text_edit()
            self.update()
            return
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Right) and self._text_edit is None:
            direction = {Qt.Key.Key_Left: -1, Qt.Key.Key_Right: 1}[key]
            self.navigate_image.emit(direction)
            return
        super().keyPressEvent(event)
