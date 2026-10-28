"""Route list activation and copy shortcuts after edit actions."""

from __future__ import annotations
from PySide6.QtCore import (
    Qt,
)


class ImageListKeyboardMixin:
    """Route list activation and copy shortcuts after edit actions."""

    def keyPressEvent(self, event):
        if self._handle_edit_key(event):
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            idx = self.currentIndex()
            if idx.isValid():
                path = self._model.path_at(idx.row())
                if path:
                    self.image_activated.emit(path)
                    return
        # Ctrl+C copies the selected paths to the clipboard so the
        # user can paste them into a terminal / file dialog without
        # round-tripping through the OS file manager.
        if event.key() == Qt.Key.Key_C and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            paths = self.selected_paths()
            if paths:
                from PySide6.QtWidgets import QApplication

                QApplication.clipboard().setText("\n".join(paths))
                event.accept()
                return
        super().keyPressEvent(event)
