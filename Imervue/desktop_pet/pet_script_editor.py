"""In-app editor for :class:`PetScript`.

The pet_script JSON file format is editable by hand, but the
schema is non-obvious to users who didn't write the loader.
This module wraps it in a Qt dialog so non-programmers can author
their pet's voice without leaving the app.

Structure:

* :class:`PetScriptEditorDialog` — top-level :class:`QDialog`
  with a tab per section (Greetings, Time-of-day, Hit responses,
  Motion lines, Scheduled).
* :class:`_StringListEditor` (``pet_script_string_list``) — reusable
  list-of-strings widget used for greetings and each time-of-day band.
* :class:`_DictOfListsEditor` (``pet_script_sections``) — reusable widget
  for sections shaped like ``{key: [strings]}`` (hit_responses,
  motion_lines).
* :class:`_ScheduledEditor` (``pet_script_sections``) — list of
  ``(every_seconds, messages)`` entries.

Pure helper :func:`script_from_form_data` (``pet_script_form``)
converts a flat dict (what the dialog produces) into a
:class:`PetScript` — testable without Qt, used by the dialog's accept
path. Every name stays importable from this module.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from Imervue.desktop_pet.pet_script import TIME_OF_DAY_BANDS, PetScript
from Imervue.desktop_pet.pet_script_form import (
    _coerce_rule,
    _parse_scheduled_events,
    _string_list,
    script_from_form_data,
)
from Imervue.desktop_pet.pet_script_sections import (
    _DictOfListsEditor,
    _ScheduledEditor,
)
from Imervue.desktop_pet.pet_script_string_list import _StringListEditor, _tr

__all__ = [
    "PetScriptEditorDialog",
    "_DictOfListsEditor",
    "_ScheduledEditor",
    "_StringListEditor",
    "_coerce_rule",
    "_parse_scheduled_events",
    "_string_list",
    "_tr",
    "script_from_form_data",
]


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
