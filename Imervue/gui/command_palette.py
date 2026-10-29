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
import math
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QPalette
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QLabel,
)

from Imervue.gui.menu_tree import iter_menu_actions, submenu_index
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.user_settings import user_setting_dict as settings

_HISTORY_KEY = "command_palette_history"
_MAX_HISTORY = 64

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow


@dataclass(frozen=True)
class _Entry:
    action: QAction
    display: str   # "File > Open File"
    search: str    # lowercased display for matching
    identity: str


def _command_identity(action: QAction, path: tuple[str, ...], keys: dict[str, str]) -> str:
    """Prefer explicit command IDs; translated labels use their language keys."""
    if action.objectName():
        return action.objectName()
    parts = (*path, action.text().replace("&", "").strip())
    return "/".join(keys.get(part, part) for part in parts)


def _history() -> dict[str, tuple[int, float]]:
    value = settings.user_setting_dict.get(_HISTORY_KEY, {})
    if not isinstance(value, dict):
        return {}
    valid = {key: (row[0], row[1]) for key, row in value.items()
             if isinstance(key, str) and isinstance(row, (list, tuple)) and len(row) == 2
             and type(row[0]) is int and row[0] > 0 and type(row[1]) in (int, float)
             and math.isfinite(row[1]) and row[1] >= 0}
    return dict(sorted(valid.items(), key=lambda item: item[1][1], reverse=True)[:_MAX_HISTORY])


def _record_command(identity: str) -> None:
    history = _history()
    count, _ = history.get(identity, (0, 0))
    history[identity] = (count + 1, time.time())
    settings.user_setting_dict[_HISTORY_KEY] = dict(
        sorted(history.items(), key=lambda item: item[1][1], reverse=True)[:_MAX_HISTORY])
    settings.schedule_save()


def _usage_score(usage: tuple[int, float], now: float) -> float:
    count, last_used = usage
    age_days = max(0, now - last_used) / 86400
    return min(count, 20) / (1 + age_days)


def _unavailable_reason(action: QAction) -> str:
    return str(action.property("disabledReason") or language_wrapper.language_word_dict.get(
        "command_palette_unavailable", "Unavailable in the current context"))


def _collect_all_entries(ui: ImervueMainWindow) -> list[_Entry]:
    """Flatten every menu action of ``ui`` into palette entries, in menu order.

    Plain actions sitting directly on the menu bar (the Modify toggle) and
    actions without text are left out. The walk goes through
    :mod:`Imervue.gui.menu_tree`: resolving submenus with ``QAction.menu()``
    invalidated menu wrappers cached elsewhere in the window.
    """
    entries: list[_Entry] = []
    occurrences: dict[str, int] = {}
    keys = {str(value).replace("&", "").strip(): key for key, value in
            sorted(language_wrapper.language_word_dict.items(), reverse=True)}
    for path, action in iter_menu_actions(ui.menuBar(), submenu_index(ui)):
        text = action.text().replace("&", "").strip()
        if not path or not text:
            continue
        label = " > ".join(part for part in (*path, text) if part)
        identity = _command_identity(action, path, keys)
        if not action.objectName():
            occurrences[identity] = occurrences.get(identity, 0) + 1
            identity = f"{identity}#{occurrences[identity]}"
        entries.append(_Entry(action=action, display=label, search=label.lower(),
                              identity=identity))
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
        self._input.setClearButtonEnabled(True)
        self._input.textChanged.connect(self._refresh)
        layout.addWidget(self._input)

        self._list = QListWidget()
        self._list.itemActivated.connect(self._trigger_item)
        layout.addWidget(self._list, 1)
        self._feedback = QLabel()
        self._feedback.setObjectName("commandPaletteFeedback")
        self._feedback.setTextFormat(Qt.TextFormat.PlainText)
        self._feedback.setWordWrap(True)
        layout.addWidget(self._feedback)
        self._list.currentItemChanged.connect(self._describe_item)

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
        history = _history()
        now = time.time()
        scored.sort(key=lambda x: (-x[0], -_usage_score(history.get(x[1].identity, (0, 0)), now),
                                  -history.get(x[1].identity, (0, 0))[1], x[1].display))
        for _, entry in scored[:self._MAX_VISIBLE]:
            item = QListWidgetItem(entry.display)
            item.setData(Qt.ItemDataRole.UserRole, entry.action)
            item.setData(Qt.ItemDataRole.UserRole + 1, entry.identity)
            if not entry.action.isEnabled():
                reason = _unavailable_reason(entry.action)
                item.setText(f"{entry.display}\n{reason}")
                item.setToolTip(reason)
                item.setForeground(self.palette().brush(
                    QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text))
            self._list.addItem(item)
        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    def _describe_item(self, item, _previous=None) -> None:
        action = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        self._feedback.setText(_unavailable_reason(action)
                               if isinstance(action, QAction) and not action.isEnabled() else "")

    def _trigger_item(self, item: QListWidgetItem) -> None:
        action = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(action, QAction) and action.isEnabled():
            _record_command(item.data(Qt.ItemDataRole.UserRole + 1))
            self.accept()
            action.trigger()
        elif isinstance(action, QAction):
            self._feedback.setText(_unavailable_reason(action))


def open_command_palette(ui: ImervueMainWindow) -> None:
    CommandPaletteDialog(ui).exec()
