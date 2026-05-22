"""In-app editor for :class:`PetScript`.

The pet_script JSON file format is editable by hand, but the
schema is non-obvious to users who didn't write the loader.
This module wraps it in a Qt dialog so non-programmers can author
their pet's voice without leaving the app.

Structure:

* :class:`PetScriptEditorDialog` — top-level :class:`QDialog`
  with a tab per section (Greetings, Time-of-day, Hit responses,
  Motion lines, Scheduled).
* :class:`_StringListEditor` — reusable list-of-strings widget
  used for greetings and each time-of-day band.
* :class:`_DictOfListsEditor` — reusable widget for sections
  shaped like ``{key: [strings]}`` (hit_responses, motion_lines).
* :class:`_ScheduledEditor` — list of
  ``(every_seconds, messages)`` entries.

Pure helper :func:`script_from_form_data` converts a flat dict
(what the dialog produces) into a :class:`PetScript` — testable
without Qt, used by the dialog's accept path.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from Imervue.desktop_pet.pet_script import (
    TIME_OF_DAY_BANDS,
    PetScript,
    ScheduledEvent,
)
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    pass


def _tr(key: str, default: str) -> str:
    return language_wrapper.language_word_dict.get(key, default)


def script_from_form_data(data: dict) -> PetScript:
    """Convert the dialog's flat form-data dict into a
    :class:`PetScript`. Used by the dialog's OK path; also a clean
    test seam — assertions can compare ``script_from_form_data(...)``
    directly with an expected :class:`PetScript`.

    Form-data keys:

    * ``name`` (str)
    * ``greetings`` (list[str])
    * ``time_of_day_greetings`` (dict[str, list[str]])
    * ``hit_responses`` (dict[str, list[str]])
    * ``motion_lines`` (dict[str, list[str]])
    * ``scheduled`` (list[dict] — each ``{every_seconds, messages}``)
    """
    scheduled_raw = data.get("scheduled", []) or []
    scheduled: list[ScheduledEvent] = []
    for entry in scheduled_raw:
        if not isinstance(entry, dict):
            continue
        try:
            every = float(entry.get("every_seconds", 0))
        except (TypeError, ValueError):
            continue
        if every <= 0:
            continue
        messages = entry.get("messages", []) or []
        if not isinstance(messages, list):
            continue
        scheduled.append(ScheduledEvent(
            every_seconds=every,
            messages=[str(m) for m in messages if isinstance(m, str)],
        ))
    return PetScript(
        name=str(data.get("name", "")),
        greetings=list(_string_list(data.get("greetings"))),
        time_of_day_greetings={
            band: list(_string_list(
                (data.get("time_of_day_greetings") or {}).get(band, []),
            ))
            for band in TIME_OF_DAY_BANDS
        },
        hit_responses={
            str(k): list(_string_list(v))
            for k, v in (data.get("hit_responses") or {}).items()
            if isinstance(k, str) and k
        },
        motion_lines={
            str(k): list(_string_list(v))
            for k, v in (data.get("motion_lines") or {}).items()
            if isinstance(k, str) and k
        },
        scheduled=scheduled,
    )


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(v) for v in value if isinstance(v, str))


class _StringListEditor(QWidget):
    """Editable list of strings — Add / Edit / Remove + a list
    widget showing entries. Used for greetings + each time-of-day
    band; reused inside :class:`_DictOfListsEditor` for the value
    pane."""

    def __init__(
        self, parent: QWidget | None = None, *, initial: list[str] | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._list = QListWidget(self)
        self._list.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection,
        )
        self._list.itemDoubleClicked.connect(self._on_edit)
        layout.addWidget(self._list)
        row = QHBoxLayout()
        add_btn = QPushButton(_tr("desktop_pet_editor_add", "Add"))
        add_btn.clicked.connect(self._on_add)
        edit_btn = QPushButton(_tr("desktop_pet_editor_edit", "Edit"))
        edit_btn.clicked.connect(self._on_edit_selected)
        remove_btn = QPushButton(_tr("desktop_pet_editor_remove", "Remove"))
        remove_btn.clicked.connect(self._on_remove)
        row.addWidget(add_btn)
        row.addWidget(edit_btn)
        row.addWidget(remove_btn)
        row.addStretch(1)
        layout.addLayout(row)
        if initial:
            for line in initial:
                self._list.addItem(QListWidgetItem(str(line)))

    def set_lines(self, lines: list[str]) -> None:
        self._list.clear()
        for line in lines:
            self._list.addItem(QListWidgetItem(str(line)))

    def lines(self) -> list[str]:
        return [self._list.item(i).text() for i in range(self._list.count())]

    def _on_add(self) -> None:   # pragma: no cover - Qt UI
        text, ok = QInputDialog.getText(
            self,
            _tr("desktop_pet_editor_add", "Add"),
            _tr("desktop_pet_editor_line_prompt", "Line:"),
        )
        if ok and text:
            self._list.addItem(QListWidgetItem(text))

    def _on_edit(self, item: QListWidgetItem) -> None:   # pragma: no cover - Qt UI
        text, ok = QInputDialog.getText(
            self,
            _tr("desktop_pet_editor_edit", "Edit"),
            _tr("desktop_pet_editor_line_prompt", "Line:"),
            QLineEdit.EchoMode.Normal,
            item.text(),
        )
        if ok and text:
            item.setText(text)

    def _on_edit_selected(self) -> None:   # pragma: no cover - Qt UI
        item = self._list.currentItem()
        if item is not None:
            self._on_edit(item)

    def _on_remove(self) -> None:   # pragma: no cover - Qt UI
        row = self._list.currentRow()
        if row >= 0:
            self._list.takeItem(row)


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
            {"every_seconds": float(ev.every_seconds), "messages": list(ev.messages)}
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
            {"every_seconds": e["every_seconds"], "messages": list(e["messages"])}
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


class PetScriptEditorDialog(QDialog):
    """Visual editor for one :class:`PetScript`.

    Construction: pass an existing script (from disk or the
    pet's default) and the dialog mirrors it into its widgets.
    On accept, callers read :meth:`script` to get the edited
    :class:`PetScript` back; on reject, the dialog discards
    edits.
    """

    def __init__(
        self,
        script: PetScript,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(_tr(
            "desktop_pet_editor_title", "Edit pet script",
        ))
        self.resize(640, 480)
        layout = QVBoxLayout(self)
        # Script name input
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel(_tr(
            "desktop_pet_editor_name", "Name:",
        )))
        self._name_edit = QLineEdit(script.name)
        name_row.addWidget(self._name_edit)
        layout.addLayout(name_row)
        # Tabs
        tabs = QTabWidget(self)
        self._greetings = _StringListEditor(initial=list(script.greetings))
        tabs.addTab(self._greetings, _tr(
            "desktop_pet_editor_tab_greetings", "Greetings",
        ))
        self._time_of_day_editors: dict[str, _StringListEditor] = {}
        tod_widget = QWidget()
        tod_layout = QVBoxLayout(tod_widget)
        for band in TIME_OF_DAY_BANDS:
            tod_layout.addWidget(QLabel(band.title() + ":"))
            editor = _StringListEditor(
                initial=list(script.time_of_day_greetings.get(band, [])),
            )
            self._time_of_day_editors[band] = editor
            tod_layout.addWidget(editor, 1)
        tabs.addTab(tod_widget, _tr(
            "desktop_pet_editor_tab_time_of_day", "Time of day",
        ))
        self._hit_responses = _DictOfListsEditor(
            initial=dict(script.hit_responses),
            key_label=_tr("desktop_pet_editor_hit_area", "Hit area:"),
        )
        tabs.addTab(self._hit_responses, _tr(
            "desktop_pet_editor_tab_hit_responses", "Hit responses",
        ))
        self._motion_lines = _DictOfListsEditor(
            initial=dict(script.motion_lines),
            key_label=_tr("desktop_pet_editor_motion", "Motion:"),
        )
        tabs.addTab(self._motion_lines, _tr(
            "desktop_pet_editor_tab_motion_lines", "Motion lines",
        ))
        self._scheduled = _ScheduledEditor(initial=list(script.scheduled))
        tabs.addTab(self._scheduled, _tr(
            "desktop_pet_editor_tab_scheduled", "Scheduled",
        ))
        layout.addWidget(tabs)
        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def script(self) -> PetScript:
        """Snapshot the current form state as a :class:`PetScript`.
        Callers use this after a successful exec/accept; pre-accept
        access is fine too (the dialog doesn't mutate the source
        script)."""
        return script_from_form_data({
            "name": self._name_edit.text(),
            "greetings": self._greetings.lines(),
            "time_of_day_greetings": {
                band: editor.lines()
                for band, editor in self._time_of_day_editors.items()
            },
            "hit_responses": self._hit_responses.data(),
            "motion_lines": self._motion_lines.data(),
            "scheduled": self._scheduled.entries(),
        })
