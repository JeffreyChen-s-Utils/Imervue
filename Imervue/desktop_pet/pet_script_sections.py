"""Section editors for the pet-script editor.

* :class:`_DictOfListsEditor` — ``{key: [strings]}`` sections
  (hit_responses, motion_lines).
* :class:`_ScheduledEditor` — the ``(every_seconds, messages)`` list.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from Imervue.desktop_pet.pet_script import ScheduledEvent
from Imervue.desktop_pet.pet_script_string_list import _StringListEditor, _tr


class _DictOfListsEditor(QWidget):
    """Two-pane widget for ``{key: [strings]}`` sections. Left
    pane lists the keys (user-managed; Add / Remove buttons), right
    pane is a :class:`_StringListEditor` for the selected key's
    values. Used by hit_responses + motion_lines."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        initial: dict[str, list[str]] | None = None,
        key_label: str = "Key",
    ) -> None:
        super().__init__(parent)
        self._data: dict[str, list[str]] = {
            k: list(v) for k, v in (initial or {}).items()
        }
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        # Left: key list + add/remove
        left = QVBoxLayout()
        left.addWidget(QLabel(key_label))
        self._keys = QListWidget(self)
        self._keys.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection,
        )
        self._keys.currentRowChanged.connect(self._on_key_changed)
        left.addWidget(self._keys)
        krow = QHBoxLayout()
        add_btn = QPushButton(_tr("desktop_pet_editor_add", "Add"))
        add_btn.clicked.connect(self._on_add_key)
        remove_btn = QPushButton(_tr("desktop_pet_editor_remove", "Remove"))
        remove_btn.clicked.connect(self._on_remove_key)
        krow.addWidget(add_btn)
        krow.addWidget(remove_btn)
        krow.addStretch(1)
        left.addLayout(krow)
        layout.addLayout(left, 1)
        # Right: value list
        self._values = _StringListEditor(self)
        self._values.setEnabled(False)
        layout.addWidget(self._values, 2)
        self._current_key: str | None = None
        self._refresh_keys()
        # Hook so edits flow back into the dict.
        self._values._list.itemChanged.connect(self._on_value_changed)  # noqa: SLF001

    def data(self) -> dict[str, list[str]]:
        """Flush the currently-selected key's editor before
        returning the snapshot — otherwise pending edits in the
        right pane don't get committed to ``_data``."""
        self._flush_current()
        return {k: list(v) for k, v in self._data.items() if v or k}

    def _refresh_keys(self) -> None:
        self._keys.clear()
        for key in self._data:
            self._keys.addItem(QListWidgetItem(key))

    def _flush_current(self) -> None:
        if self._current_key is None:
            return
        if self._current_key in self._data:
            self._data[self._current_key] = self._values.lines()

    def _on_key_changed(self, row: int) -> None:
        self._flush_current()
        if row < 0 or row >= self._keys.count():
            self._current_key = None
            self._values.set_lines([])
            self._values.setEnabled(False)
            return
        key = self._keys.item(row).text()
        self._current_key = key
        self._values.set_lines(self._data.get(key, []))
        self._values.setEnabled(True)

    def _on_value_changed(self, *_args) -> None:   # pragma: no cover - Qt UI
        # Nothing extra needed — `data()` reads `_values.lines()`
        # when the caller requests a snapshot.
        return

    def _on_add_key(self) -> None:   # pragma: no cover - Qt UI
        text, ok = QInputDialog.getText(
            self,
            _tr("desktop_pet_editor_add_key", "Add key"),
            _tr("desktop_pet_editor_key_prompt", "Key:"),
        )
        if not (ok and text):
            return
        if text not in self._data:
            self._data[text] = []
            self._refresh_keys()
            # Auto-select the new entry.
            for i in range(self._keys.count()):
                if self._keys.item(i).text() == text:
                    self._keys.setCurrentRow(i)
                    break

    def _on_remove_key(self) -> None:   # pragma: no cover - Qt UI
        row = self._keys.currentRow()
        if row < 0:
            return
        key = self._keys.item(row).text()
        self._data.pop(key, None)
        self._current_key = None
        self._refresh_keys()


class _ScheduledEditor(QWidget):
    """Editor for the ``scheduled`` list: each entry is
    ``(every_seconds, [messages])``."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        initial: list[ScheduledEvent] | None = None,
    ) -> None:
        super().__init__(parent)
        self._entries: list[dict] = [
            {
                "every_seconds": float(ev.every_seconds),
                "messages": list(ev.messages),
                # Carry the wall-clock rule opaquely so editing an entry doesn't
                # strip its schedule gating (the editor only edits interval +
                # messages, but must preserve the rule).
                "rule": ev.rule,
            }
            for ev in (initial or [])
        ]
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        # Top: list of entries + interval spin
        row = QHBoxLayout()
        row.addWidget(QLabel(_tr(
            "desktop_pet_editor_every_seconds", "Every (s):",
        )))
        self._interval_spin = QDoubleSpinBox(self)
        self._interval_spin.setRange(0.5, 86400.0)
        self._interval_spin.setValue(60.0)
        self._interval_spin.setSingleStep(5.0)
        row.addWidget(self._interval_spin)
        add_btn = QPushButton(_tr("desktop_pet_editor_add", "Add"))
        add_btn.clicked.connect(self._on_add_entry)
        remove_btn = QPushButton(_tr("desktop_pet_editor_remove", "Remove"))
        remove_btn.clicked.connect(self._on_remove_entry)
        row.addWidget(add_btn)
        row.addWidget(remove_btn)
        row.addStretch(1)
        layout.addLayout(row)
        self._entries_list = QListWidget(self)
        self._entries_list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self._entries_list)
        layout.addWidget(QLabel(_tr(
            "desktop_pet_editor_messages", "Messages:",
        )))
        self._messages = _StringListEditor(self)
        self._messages.setEnabled(False)
        layout.addWidget(self._messages)
        self._current_row: int = -1
        self._refresh_entries()

    def entries(self) -> list[dict]:
        """Flush + return the form-data list ready to feed into
        :func:`script_from_form_data`."""
        self._flush_current()
        return [
            {
                "every_seconds": e["every_seconds"],
                "messages": list(e["messages"]),
                "rule": e.get("rule"),
            }
            for e in self._entries
        ]

    def _refresh_entries(self) -> None:
        self._entries_list.clear()
        for entry in self._entries:
            label = _tr(
                "desktop_pet_editor_entry_label",
                "every {seconds:.1f} s ({count} msg)",
            ).format(
                seconds=entry["every_seconds"],
                count=len(entry["messages"]),
            )
            self._entries_list.addItem(QListWidgetItem(label))

    def _flush_current(self) -> None:
        if 0 <= self._current_row < len(self._entries):
            self._entries[self._current_row]["messages"] = self._messages.lines()

    def _on_row_changed(self, row: int) -> None:
        self._flush_current()
        self._current_row = row
        if row < 0 or row >= len(self._entries):
            self._messages.set_lines([])
            self._messages.setEnabled(False)
            return
        entry = self._entries[row]
        self._messages.set_lines(entry["messages"])
        self._messages.setEnabled(True)

    def _on_add_entry(self) -> None:   # pragma: no cover - Qt UI
        self._entries.append({
            "every_seconds": float(self._interval_spin.value()),
            "messages": [],
        })
        self._refresh_entries()
        self._entries_list.setCurrentRow(len(self._entries) - 1)

    def _on_remove_entry(self) -> None:   # pragma: no cover - Qt UI
        row = self._entries_list.currentRow()
        if 0 <= row < len(self._entries):
            del self._entries[row]
            self._current_row = -1
            self._refresh_entries()
