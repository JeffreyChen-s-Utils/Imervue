"""
Command Palette — VS Code-style fuzzy action launcher (Ctrl+Shift+P).

Walks the application's ``menuBar()`` at invocation time and flattens every
``QAction`` into a searchable list (``[menu path] / action text``). A
subsequence-based fuzzy matcher ranks results; ``Enter`` triggers the chosen
action. Designed to stay in sync automatically — any menu entry added
elsewhere in the project becomes instantly discoverable without registration.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QMenu,
)

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow


@dataclass(frozen=True)
class _Entry:
    action: QAction
    display: str   # "File > Open File"
    search: str    # lowercased display for matching


def _collect_menu_actions(menu: QMenu, prefix: str) -> list[_Entry]:
    entries: list[_Entry] = []
    for action in menu.actions():
        if action.isSeparator():
            continue
        text = action.text().replace("&", "").strip()
        if not text:
            continue
        label = f"{prefix} > {text}" if prefix else text
        sub = action.menu()
        if sub is not None:
            entries.extend(_collect_menu_actions(sub, label))
            continue
        entries.append(_Entry(action=action, display=label, search=label.lower()))
    return entries


def _collect_all_entries(ui: ImervueMainWindow) -> list[_Entry]:
    entries: list[_Entry] = []
    for top_action in ui.menuBar().actions():
        sub = top_action.menu()
        if sub is None:
            continue
        top_text = top_action.text().replace("&", "").strip()
        entries.extend(_collect_menu_actions(sub, top_text))
    return entries


def fuzzy_score(query: str, candidate: str) -> int:
    """Return a subsequence match score (higher = better), or -1 if no match.

    Scoring: +10 per matched char, +5 bonus when matching a new word boundary
    (after space/separator), -1 per gap between matches. Returns -1 when
    ``query`` is not a subsequence of ``candidate``.
    """
    if not query:
        return 0
    q = query.lower()
    c = candidate.lower()
    qi = 0
    score = 0
    last_match = -1
    for i, ch in enumerate(c):
        if qi < len(q) and ch == q[qi]:
            score += 10
            at_boundary = i == 0 or c[i - 1] in " >/-_."
            if at_boundary:
                score += 5
            if last_match >= 0:
                score -= max(0, i - last_match - 1)
            last_match = i
            qi += 1
            if qi == len(q):
                return score
    return -1


class CommandPaletteDialog(QDialog):
    """Floating modal that fuzzy-matches menu actions."""

    _MAX_VISIBLE = 100

    def __init__(self, ui: ImervueMainWindow):
        super().__init__(ui)
        self._ui = ui
        self._entries = _collect_all_entries(ui)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("command_palette_title", "Command Palette"))
        self.setModal(True)
        self.resize(640, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self._input = QLineEdit()
        self._input.setPlaceholderText(
            lang.get("command_palette_placeholder", "Type a command…"))
        self._input.textChanged.connect(self._refresh)
        layout.addWidget(self._input)

        self._list = QListWidget()
        self._list.itemActivated.connect(self._trigger_item)
        layout.addWidget(self._list, 1)

        self._refresh("")

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            self._move_selection(1 if key == Qt.Key.Key_Down else -1)
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            item = self._list.currentItem()
            if item is not None:
                self._trigger_item(item)
            return
        if key == Qt.Key.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)

    def _move_selection(self, delta: int) -> None:
        count = self._list.count()
        if count == 0:
            return
        row = self._list.currentRow()
        row = (row + delta) % count
        self._list.setCurrentRow(row)

    def _refresh(self, text: str) -> None:
        self._list.clear()
        query = text.strip()
        scored: list[tuple[int, _Entry]] = []
        for entry in self._entries:
            s = fuzzy_score(query, entry.search)
            if s < 0:
                continue
            scored.append((s, entry))
        scored.sort(key=lambda x: (-x[0], x[1].display))
        for _, entry in scored[:self._MAX_VISIBLE]:
            item = QListWidgetItem(entry.display)
            item.setData(Qt.ItemDataRole.UserRole, entry.action)
            self._list.addItem(item)
        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    def _trigger_item(self, item: QListWidgetItem) -> None:
        action = item.data(Qt.ItemDataRole.UserRole)
        self.accept()
        if isinstance(action, QAction) and action.isEnabled():
            action.trigger()


def open_command_palette(ui: ImervueMainWindow) -> None:
    CommandPaletteDialog(ui).exec()
