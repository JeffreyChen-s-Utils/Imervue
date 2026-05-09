"""Keyboard-shortcut cheat sheet dialog.

Walks every ``QAction`` on the workspace's menu bar that carries a
non-empty shortcut and renders the results in a scrollable two-
column table — action label on the left, key combination on the
right — so the user can discover bindings without grepping the
codebase. Built on demand from the live menus, so no shortcut list
goes stale: adding a new menu entry with a shortcut automatically
shows up here.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from PySide6.QtWidgets import QMainWindow


class ShortcutsDialog(QDialog):
    """Two-column read-only table of every active shortcut."""

    def __init__(self, workspace: QMainWindow, parent=None):
        super().__init__(parent or workspace)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(
            lang.get("paint_shortcuts_title", "Keyboard Shortcuts"),
        )
        self.setMinimumSize(520, 420)

        rows = collect_shortcut_rows(workspace)

        self._table = QTableWidget(len(rows), 2)
        self._table.setHorizontalHeaderLabels((
            lang.get("paint_shortcuts_action_col", "Action"),
            lang.get("paint_shortcuts_key_col", "Shortcut"),
        ))
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        for row, (label, key) in enumerate(rows):
            self._table.setItem(row, 0, QTableWidgetItem(label))
            self._table.setItem(row, 1, QTableWidgetItem(key))
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setAlternatingRowColors(True)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(self._table)
        layout.addWidget(buttons)


def collect_shortcut_rows(workspace) -> list[tuple[str, str]]:
    """Return ``(action_label, key_string)`` pairs for the cheat sheet.

    Walks the workspace's menu-bar menus in order, deduplicating by
    (label, key) so the same QAction registered to both a menu and
    a toolbar appears once. Sort is stable: menu order is preserved
    so related shortcuts (File ▸ ..., then Edit ▸ ...) cluster.
    """
    seen: set[tuple[str, str]] = set()
    rows: list[tuple[str, str]] = []
    menu_bar = workspace.menuBar() if hasattr(workspace, "menuBar") else None
    if menu_bar is None:
        return rows
    for action in menu_bar.actions():
        menu = action.menu()
        if menu is None:
            continue
        rows.extend(_collect_from_menu(menu, seen))
    return rows


def _collect_from_menu(menu, seen) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for action in menu.actions():
        if action.isSeparator():
            continue
        sub = action.menu()
        if sub is not None:
            rows.extend(_collect_from_menu(sub, seen))
            continue
        seq = action.shortcut()
        if seq.isEmpty():
            continue
        label = action.text().replace("&", "")
        key = seq.toString(seq.SequenceFormat.NativeText) or seq.toString()
        entry = (label, key)
        if entry in seen:
            continue
        seen.add(entry)
        rows.append(entry)
    return rows


def open_shortcuts_dialog(workspace, parent=None) -> None:
    dialog = ShortcutsDialog(workspace, parent=parent)
    dialog.exec()
