"""Apply list edit shortcuts while retaining selection after rebuilds."""

from __future__ import annotations
from PySide6.QtCore import (
    Qt,
)

from Imervue.gui.image_list_values import LIST_MARK_ACTIONS


class ImageListEditMixin:
    """Apply list edit shortcuts while retaining selection after rebuilds."""

    @staticmethod
    def _list_action(event, action: str | None) -> str | None:
        """The Shortcut Settings action, or ``label_<colour>`` for the fixed F1-F5 keys."""
        from Imervue.gpu_image_view.key_input_handler import COLOR_LABEL_KEYS

        no_ctrl_alt = not (
            event.modifiers()
            & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
        )
        if event.key() in COLOR_LABEL_KEYS and no_ctrl_alt:
            return f"label_{COLOR_LABEL_KEYS[event.key()]}"
        return action

    def _handle_edit_key(self, event) -> bool:
        """Delete, Undo, ratings, favourite, cull flags and colours act on the list as on the wall.

        Delete removes the selected rows (undoable, sent to the Recycle Bin
        later) and puts the cursor on the row that takes their place.
        """
        from Imervue.gui.shortcut_settings_dialog import shortcut_manager

        window = self._main_window
        if window is None:
            return False
        if event.key() == Qt.Key.Key_Escape and not event.modifiers():
            window.escape_from_list()
            event.accept()
            return True
        bound = shortcut_manager.get_action(event.key(), event.modifiers())
        action = self._list_action(event, bound)
        if action in LIST_MARK_ACTIONS and self.selected_paths():
            window.mark_list_selection(action, self.selected_paths())
        elif action == "undo":
            window.undo_from_list()
        elif action == "delete" and self.selected_paths():
            row = min(index.row() for index in self.selectionModel().selectedRows())
            window.delete_list_selection(self.selected_paths())
            if self._model.rowCount():
                self.selectRow(min(row, self._model.rowCount() - 1))
        else:
            return False
        event.accept()
        return True
