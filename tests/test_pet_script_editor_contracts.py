"""Contract tests for the pet-script editor.

Pins the pure form-data conversion edge cases and the Qt editors' row
operations (add / edit / remove through the input dialogs), labels and
tab layout that ``test_desktop_pet_script_editor.py`` does not reach. No
``QOpenGLWidget`` is built here, so these run on headless CI too.
"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QInputDialog, QLabel, QPushButton, QTabWidget

from Imervue.desktop_pet import pet_script_editor as editor_mod
from Imervue.desktop_pet.pet_script import TIME_OF_DAY_BANDS, PetScript, ScheduledEvent
from Imervue.desktop_pet.pet_script_editor import (
    PetScriptEditorDialog,
    _coerce_rule,
    _DictOfListsEditor,
    _parse_scheduled_events,
    _ScheduledEditor,
    _string_list,
    _StringListEditor,
    _tr,
    script_from_form_data,
)
from Imervue.desktop_pet.schedule_rules import rule_from_dict

_GET_TEXT = "getText"


def _answer(monkeypatch, *answers):
    """Make ``QInputDialog.getText`` return each ``(text, ok)`` in turn,
    recording the positional arguments it was called with."""
    calls: list[tuple] = []
    queue = list(answers)

    def fake(*args, **_kwargs):
        calls.append(args)
        return queue.pop(0)

    monkeypatch.setattr(QInputDialog, _GET_TEXT, staticmethod(fake))
    return calls


# ---------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------


def test_tr_falls_back_to_default_for_unknown_key():
    assert _tr("no_such_key_for_pet_script_editor", "Fallback") == "Fallback"


@pytest.mark.parametrize(("value", "expected"), [
    (["a", 1, "b", None], ("a", "b")),
    (("x", "y"), ("x", "y")),
    ([], ()),
    ("abc", ()),
    (None, ()),
    ({"a": 1}, ()),
])
def test_string_list_keeps_only_strings(value, expected):
    assert _string_list(value) == expected


def test_coerce_rule_rejects_non_rule_values():
    assert _coerce_rule(None) is None
    assert _coerce_rule("rule") is None
    assert _coerce_rule(["x"]) is None


def test_parse_scheduled_events_none_and_empty():
    assert _parse_scheduled_events(None) == []
    assert _parse_scheduled_events([]) == []


@pytest.mark.parametrize("entry", [
    "not a dict",
    {"every_seconds": "abc", "messages": ["a"]},
    {"every_seconds": None, "messages": ["a"]},
    {"every_seconds": 0, "messages": ["a"]},
    {"every_seconds": -1, "messages": ["a"]},
    {"every_seconds": 5, "messages": "a"},
    {"messages": ["a"]},
])
def test_parse_scheduled_events_skips_bad_entries(entry):
    assert _parse_scheduled_events([entry]) == []


def test_parse_scheduled_events_coerces_values():
    rule_dict = {"start_hour": 8, "end_hour": 12}
    events = _parse_scheduled_events([
        {"every_seconds": "2.5", "messages": ["a", 3, "b"], "rule": rule_dict},
        {"every_seconds": 1, "messages": None},
    ])
    assert len(events) == 2
    assert events[0].every_seconds == pytest.approx(2.5)
    assert events[0].messages == ["a", "b"]
    assert events[0].rule == rule_from_dict(rule_dict)
    assert events[1].every_seconds == pytest.approx(1.0)
    assert events[1].messages == []
    assert events[1].rule is None


def test_script_from_form_data_filters_keys_and_bands():
    script = script_from_form_data({
        "name": 7,
        "greetings": ("hi", 2),
        "time_of_day_greetings": {"morning": ["m"], "bogus": ["x"]},
        "hit_responses": {"head": ["ow"], "": ["drop"], 3: ["drop"]},
        "motion_lines": {"wave": "not-a-list", "nod": ["ok"]},
        "scheduled": None,
    })
    assert script.name == "7"
    assert script.greetings == ["hi"]
    assert list(script.time_of_day_greetings) == list(TIME_OF_DAY_BANDS)
    assert script.time_of_day_greetings["morning"] == ["m"]
    assert "bogus" not in script.time_of_day_greetings
    assert script.hit_responses == {"head": ["ow"]}
    assert script.motion_lines == {"wave": [], "nod": ["ok"]}
    assert script.scheduled == []


def test_script_from_form_data_none_sections():
    script = script_from_form_data({
        "time_of_day_greetings": None,
        "hit_responses": None,
        "motion_lines": None,
    })
    assert script.name == ""
    assert script.greetings == []
    assert all(v == [] for v in script.time_of_day_greetings.values())
    assert script.hit_responses == {}
    assert script.motion_lines == {}


# ---------------------------------------------------------------
# _StringListEditor row operations
# ---------------------------------------------------------------


def _button_texts(widget) -> list[str]:
    return [b.text() for b in widget.findChildren(QPushButton)]


def test_string_list_editor_buttons(qapp):
    editor = _StringListEditor(None)
    try:
        assert _button_texts(editor) == ["Add", "Edit", "Remove"]
    finally:
        editor.deleteLater()


def test_string_list_editor_add_accepts_and_ignores(qapp, monkeypatch):
    editor = _StringListEditor(None, initial=["a"])
    try:
        calls = _answer(monkeypatch, ("new", True), ("", True), ("x", False))
        editor._on_add()   # noqa: SLF001
        editor._on_add()   # noqa: SLF001
        editor._on_add()   # noqa: SLF001
        assert editor.lines() == ["a", "new"]
        assert calls[0][1:] == ("Add", "Line:")
    finally:
        editor.deleteLater()


def test_string_list_editor_edit_selected(qapp, monkeypatch):
    editor = _StringListEditor(None, initial=["a", "b"])
    try:
        calls = _answer(monkeypatch, ("B2", True), ("", True))
        editor._on_edit_selected()   # noqa: SLF001  (nothing selected: no prompt)
        assert calls == []
        editor._list.setCurrentRow(1)   # noqa: SLF001
        editor._on_edit_selected()   # noqa: SLF001
        assert editor.lines() == ["a", "B2"]
        assert calls[0][1:3] == ("Edit", "Line:")
        assert calls[0][4] == "b"
        editor._on_edit_selected()   # noqa: SLF001  (empty answer keeps text)
        assert editor.lines() == ["a", "B2"]
    finally:
        editor.deleteLater()


def test_string_list_editor_remove(qapp):
    editor = _StringListEditor(None, initial=["a", "b", "c"])
    try:
        editor._list.setCurrentRow(-1)   # noqa: SLF001
        editor._on_remove()   # noqa: SLF001
        assert editor.lines() == ["a", "b", "c"]
        editor._list.setCurrentRow(1)   # noqa: SLF001
        editor._on_remove()   # noqa: SLF001
        assert editor.lines() == ["a", "c"]
    finally:
        editor.deleteLater()


def test_string_list_editor_set_lines_stringifies(qapp):
    editor = _StringListEditor(None)
    try:
        editor.set_lines([1, "x"])
        assert editor.lines() == ["1", "x"]
    finally:
        editor.deleteLater()


# ---------------------------------------------------------------
# _DictOfListsEditor key operations
# ---------------------------------------------------------------


def test_dict_editor_label_and_disabled_values(qapp):
    editor = _DictOfListsEditor(None, initial={"a": ["1"]}, key_label="Area:")
    try:
        assert [lbl.text() for lbl in editor.findChildren(QLabel)] == ["Area:"]
        assert not editor._values.isEnabled()   # noqa: SLF001
        assert editor._keys.count() == 1   # noqa: SLF001
    finally:
        editor.deleteLater()


def test_dict_editor_add_key_selects_it(qapp, monkeypatch):
    editor = _DictOfListsEditor(None, initial={"a": ["1"]})
    try:
        calls = _answer(monkeypatch, ("b", True), ("a", True), ("", True), ("c", False))
        editor._on_add_key()   # noqa: SLF001
        assert calls[0][1:] == ("Add key", "Key:")
        assert editor._keys.currentItem().text() == "b"   # noqa: SLF001
        assert editor._values.isEnabled()   # noqa: SLF001
        editor._on_add_key()   # noqa: SLF001  (duplicate ignored)
        editor._on_add_key()   # noqa: SLF001
        editor._on_add_key()   # noqa: SLF001
        assert editor.data() == {"a": ["1"], "b": []}
    finally:
        editor.deleteLater()


def test_dict_editor_remove_key(qapp):
    editor = _DictOfListsEditor(None, initial={"a": ["1"], "b": ["2"]})
    try:
        editor._keys.setCurrentRow(-1)   # noqa: SLF001
        editor._on_remove_key()   # noqa: SLF001
        assert editor.data() == {"a": ["1"], "b": ["2"]}
        editor._keys.setCurrentRow(0)   # noqa: SLF001
        editor._on_remove_key()   # noqa: SLF001
        assert editor.data() == {"b": ["2"]}
        assert editor._current_key is None   # noqa: SLF001
    finally:
        editor.deleteLater()


def test_dict_editor_switching_keys_flushes_and_out_of_range(qapp):
    editor = _DictOfListsEditor(None, initial={"a": ["1"], "b": ["2"]})
    try:
        editor._keys.setCurrentRow(0)   # noqa: SLF001
        editor._values.set_lines(["edited"])   # noqa: SLF001
        editor._keys.setCurrentRow(1)   # noqa: SLF001
        assert editor._values.lines() == ["2"]   # noqa: SLF001
        editor._on_key_changed(5)   # noqa: SLF001
        assert editor._current_key is None   # noqa: SLF001
        assert editor._values.lines() == []   # noqa: SLF001
        assert not editor._values.isEnabled()   # noqa: SLF001
        assert editor.data() == {"a": ["edited"], "b": ["2"]}
    finally:
        editor.deleteLater()


def test_dict_editor_value_changed_is_noop(qapp):
    editor = _DictOfListsEditor(None, initial={"a": ["1"]})
    try:
        assert editor._on_value_changed("anything") is None   # noqa: SLF001
        assert editor.data() == {"a": ["1"]}
    finally:
        editor.deleteLater()


# ---------------------------------------------------------------
# _ScheduledEditor entry operations
# ---------------------------------------------------------------


def test_scheduled_editor_widgets_and_labels(qapp):
    editor = _ScheduledEditor(None, initial=[
        ScheduledEvent(every_seconds=30.0, messages=["a", "b"]),
    ])
    try:
        spin = editor._interval_spin   # noqa: SLF001
        assert spin.minimum() == pytest.approx(0.5)
        assert spin.maximum() == pytest.approx(86400.0)
        assert spin.value() == pytest.approx(60.0)
        assert spin.singleStep() == pytest.approx(5.0)
        labels = [lbl.text() for lbl in editor.findChildren(QLabel)]
        assert labels == ["Every (s):", "Messages:"]
        assert _button_texts(editor)[:2] == ["Add", "Remove"]
        assert editor._entries_list.item(0).text() == "every 30.0 s (2 msg)"   # noqa: SLF001
        assert not editor._messages.isEnabled()   # noqa: SLF001
    finally:
        editor.deleteLater()


def test_scheduled_editor_add_and_remove_entries(qapp):
    editor = _ScheduledEditor(None)
    try:
        editor._interval_spin.setValue(12.5)   # noqa: SLF001
        editor._on_add_entry()   # noqa: SLF001
        assert editor._entries_list.currentRow() == 0   # noqa: SLF001
        assert editor._messages.isEnabled()   # noqa: SLF001
        editor._messages.set_lines(["m"])   # noqa: SLF001
        assert editor.entries() == [
            {"every_seconds": 12.5, "messages": ["m"], "rule": None},
        ]
        editor._refresh_entries()   # noqa: SLF001
        assert editor._entries_list.item(0).text() == "every 12.5 s (1 msg)"   # noqa: SLF001
        editor._entries_list.setCurrentRow(-1)   # noqa: SLF001
        editor._on_remove_entry()   # noqa: SLF001
        assert len(editor.entries()) == 1
        editor._entries_list.setCurrentRow(0)   # noqa: SLF001
        editor._on_remove_entry()   # noqa: SLF001
        assert editor.entries() == []
        assert editor._current_row == -1   # noqa: SLF001
    finally:
        editor.deleteLater()


def test_scheduled_editor_entries_returns_copies(qapp):
    rule = rule_from_dict({"start_hour": 1, "end_hour": 2})
    editor = _ScheduledEditor(None, initial=[
        ScheduledEvent(every_seconds=5, messages=["a"], rule=rule),
    ])
    try:
        snap = editor.entries()
        snap[0]["messages"].append("mutated")
        assert editor.entries() == [
            {"every_seconds": 5.0, "messages": ["a"], "rule": rule},
        ]
    finally:
        editor.deleteLater()


# ---------------------------------------------------------------
# PetScriptEditorDialog layout
# ---------------------------------------------------------------


def test_dialog_title_tabs_and_snapshot(qapp):
    dialog = PetScriptEditorDialog(PetScript(name="n"), None)
    try:
        assert dialog.windowTitle() == "Edit pet script"
        tabs = dialog.findChild(QTabWidget)
        assert [tabs.tabText(i) for i in range(tabs.count())] == [
            "Greetings", "Time of day", "Hit responses", "Motion lines", "Scheduled",
        ]
        assert list(dialog._time_of_day_editors) == list(TIME_OF_DAY_BANDS)   # noqa: SLF001
        assert dialog.script() == script_from_form_data({"name": "n"})
    finally:
        dialog.deleteLater()


def test_editor_module_exposes_public_names():
    for name in ("PetScriptEditorDialog", "script_from_form_data"):
        assert hasattr(editor_mod, name)
