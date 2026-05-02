"""Modal dialog for editing :class:`ShortcutRegistry` bindings.

The dialog renders a table with one row per registry entry —
columns: action label / current binding / Reset. Clicking a binding
cell turns it into a :class:`QKeySequenceEdit` so the user can press
the new combination; conflicts highlight the colliding row in red
but never block the save (the registry tolerates duplicate bindings,
the user gets to decide).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QKeySequenceEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.shortcut_registry import (
    DEFAULT_SHORTCUTS,
    ShortcutRegistry,
)

_COL_ACTION = 0
_COL_KEY = 1
_COL_RESET = 2

# Translation helper — falls back to a humanised version of the
# action id so a missing key never produces an empty cell.


def _humanise(action_id: str) -> str:
    return action_id.replace("paint.", "").replace(".", " · ").title()


class ShortcutDialog(QDialog):
    """Editable shortcut table backed by a :class:`ShortcutRegistry`."""

    def __init__(self, registry: ShortcutRegistry | None = None, parent=None):
        super().__init__(parent)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("paint_shortcut_title", "Shortcuts"))
        self.resize(500, 480)

        self._registry = registry or ShortcutRegistry.with_defaults()
        self._working = ShortcutRegistry.from_dict(self._registry.to_dict())

        layout = QVBoxLayout(self)

        self._table = QTableWidget(len(DEFAULT_SHORTCUTS), 3, self)
        self._table.setHorizontalHeaderLabels([
            lang.get("paint_shortcut_col_action", "Action"),
            lang.get("paint_shortcut_col_key", "Shortcut"),
            lang.get("paint_shortcut_col_reset", "Reset"),
        ])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(_COL_ACTION, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(_COL_KEY, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(_COL_RESET, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setColumnWidth(_COL_KEY, 160)
        self._populate_rows()
        layout.addWidget(self._table)

        bottom = QHBoxLayout()
        reset_all_btn = QPushButton(lang.get(
            "paint_shortcut_reset_all", "Reset all to default",
        ))
        reset_all_btn.clicked.connect(self._on_reset_all)
        bottom.addWidget(reset_all_btn)
        bottom.addStretch(1)
        layout.addLayout(bottom)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ---- public ---------------------------------------------------------

    def registry(self) -> ShortcutRegistry:
        """Return the (possibly modified) registry. Callers commit on accept."""
        return self._working

    # ---- internals ------------------------------------------------------

    def _populate_rows(self) -> None:
        lang = language_wrapper.language_word_dict
        for row, entry in enumerate(DEFAULT_SHORTCUTS):
            label = lang.get(entry.label_key, _humanise(entry.action_id))
            item = QTableWidgetItem(label)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._table.setItem(row, _COL_ACTION, item)

            key_edit = QKeySequenceEdit()
            key_edit.setKeySequence(self._working.get(entry.action_id))
            key_edit.editingFinished.connect(
                lambda *_, r=row: self._on_key_finished(r),
            )
            self._table.setCellWidget(row, _COL_KEY, key_edit)

            reset_btn = QPushButton(lang.get(
                "paint_shortcut_reset_row", "↺",
            ))
            reset_btn.clicked.connect(
                lambda *_, r=row: self._on_reset_row(r),
            )
            self._table.setCellWidget(row, _COL_RESET, reset_btn)
        self._refresh_conflict_marks()

    def _on_key_finished(self, row: int) -> None:
        entry = DEFAULT_SHORTCUTS[row]
        widget = self._table.cellWidget(row, _COL_KEY)
        new_key = widget.keySequence().toString()
        if not new_key.strip():
            # Empty entry → restore previous binding so the registry
            # never holds an empty string.
            widget.setKeySequence(self._working.get(entry.action_id))
            return
        self._working.set(entry.action_id, new_key)
        self._refresh_conflict_marks()

    def _on_reset_row(self, row: int) -> None:
        entry = DEFAULT_SHORTCUTS[row]
        self._working.reset(entry.action_id)
        widget = self._table.cellWidget(row, _COL_KEY)
        widget.setKeySequence(self._working.get(entry.action_id))
        self._refresh_conflict_marks()

    def _on_reset_all(self) -> None:
        self._working.reset_all()
        for row, entry in enumerate(DEFAULT_SHORTCUTS):
            widget = self._table.cellWidget(row, _COL_KEY)
            widget.setKeySequence(self._working.get(entry.action_id))
        self._refresh_conflict_marks()

    def _refresh_conflict_marks(self) -> None:
        """Highlight rows whose binding collides with another row."""
        for row, entry in enumerate(DEFAULT_SHORTCUTS):
            current = self._working.get(entry.action_id)
            colliding = self._working.conflicts(entry.action_id, current)
            colour = QColor("#5a1f1f") if colliding else QColor("transparent")
            for col in range(self._table.columnCount()):
                item = self._table.item(row, col)
                if item is not None:
                    item.setBackground(colour)
