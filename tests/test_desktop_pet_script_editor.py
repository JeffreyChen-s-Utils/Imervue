"""Tests for the in-app pet-script editor.

The pure :func:`script_from_form_data` converts the dialog's
flat form-data dict into a :class:`PetScript` — testable in
isolation. The widget smoke tests cover load → edit → snapshot
round-trips for each reusable editor (StringListEditor,
DictOfListsEditor, ScheduledEditor) so a future Qt API change
fails loud here.
"""
from __future__ import annotations

import pytest

from Imervue.desktop_pet.pet_script import (
    PetScript,
    ScheduledEvent,
    load_script,
    save_script,
)
from Imervue.desktop_pet.pet_script_editor import (
    PetScriptEditorDialog,
    _DictOfListsEditor,
    _ScheduledEditor,
    _StringListEditor,
    script_from_form_data,
)

from _qt_skip import pytestmark  # noqa: E402,F401


# ---------------------------------------------------------------
# script_from_form_data — pure helper
# ---------------------------------------------------------------


def test_script_from_form_data_basic():
    out = script_from_form_data({
        "name": "March 7th",
        "greetings": ["Hi!", "Hello!"],
        "time_of_day_greetings": {
            "morning": ["Morning!"],
            "night": ["Night!"],
        },
        "hit_responses": {"head": ["Ouch", "Hey"]},
        "motion_lines": {"wave": ["Hi"]},
        "scheduled": [{"every_seconds": 60.0, "messages": ["Break?"]}],
    })
    assert out.name == "March 7th"
    assert out.greetings == ["Hi!", "Hello!"]
    assert out.time_of_day_greetings["morning"] == ["Morning!"]
    assert out.hit_responses == {"head": ["Ouch", "Hey"]}
    assert out.motion_lines == {"wave": ["Hi"]}
    assert len(out.scheduled) == 1
    assert out.scheduled[0].every_seconds == pytest.approx(60.0)


def test_script_from_form_data_drops_invalid_scheduled():
    """Same robustness rule as the JSON loader: a bad entry drops
    silently rather than blowing up the whole save."""
    out = script_from_form_data({
        "scheduled": [
            {"every_seconds": 60, "messages": ["A"]},
            {"every_seconds": 0, "messages": ["B"]},     # interval 0 → drop
            {"every_seconds": -5, "messages": ["C"]},    # negative → drop
            "not a dict",
        ],
    })
    assert len(out.scheduled) == 1
    assert out.scheduled[0].messages == ["A"]


def test_script_from_form_data_creates_all_time_of_day_bands():
    """Even when the form omits some bands, the resulting script
    has all four — empty lists where the user provided nothing.
    Matches the schema documented in pet_script.py."""
    out = script_from_form_data({
        "time_of_day_greetings": {"morning": ["Good morning!"]},
    })
    assert set(out.time_of_day_greetings.keys()) == {
        "morning", "afternoon", "evening", "night",
    }
    assert out.time_of_day_greetings["afternoon"] == []


def test_script_from_form_data_empty_input_returns_defaults():
    """No fields → a script with empty buckets but a valid
    structure. Workspace's "edit script" flow on first run starts
    here."""
    out = script_from_form_data({})
    assert out.name == ""
    assert out.greetings == []
    assert out.hit_responses == {}


def test_script_from_form_data_filters_non_string_lines():
    """Defensive — a misconfigured form (or a buggy widget) feeding
    non-strings → drop them, don't crash."""
    out = script_from_form_data({
        "greetings": ["valid", 42, None, "also valid"],
    })
    assert out.greetings == ["valid", "also valid"]


def test_form_data_round_trips_through_save_load(tmp_path):
    """script → form-data-equivalent → script (via save/load) →
    must equal the starting state. Catches a writer / loader
    schema drift."""
    original = script_from_form_data({
        "name": "rt",
        "greetings": ["a", "b"],
        "time_of_day_greetings": {"evening": ["Evening!"]},
        "hit_responses": {"head": ["ouch"]},
        "motion_lines": {"wave": ["hi"]},
        "scheduled": [{"every_seconds": 30.0, "messages": ["chime"]}],
    })
    path = tmp_path / "rt.json"
    save_script(original, path)
    reloaded = load_script(path)
    assert reloaded.name == "rt"
    assert reloaded.greetings == ["a", "b"]
    assert reloaded.time_of_day_greetings["evening"] == ["Evening!"]


# ---------------------------------------------------------------
# _StringListEditor
# ---------------------------------------------------------------


def test_string_list_editor_initial_lines(qapp):
    editor = _StringListEditor(initial=["a", "b", "c"])
    try:
        assert editor.lines() == ["a", "b", "c"]
    finally:
        editor.deleteLater()


def test_string_list_editor_set_lines_clears_old(qapp):
    editor = _StringListEditor(initial=["a", "b"])
    try:
        editor.set_lines(["x", "y", "z"])
        assert editor.lines() == ["x", "y", "z"]
    finally:
        editor.deleteLater()


def test_string_list_editor_empty_initial(qapp):
    editor = _StringListEditor()
    try:
        assert editor.lines() == []
    finally:
        editor.deleteLater()


# ---------------------------------------------------------------
# _DictOfListsEditor
# ---------------------------------------------------------------


def test_dict_of_lists_editor_loads_initial(qapp):
    editor = _DictOfListsEditor(initial={"head": ["a"], "body": ["b"]})
    try:
        snapshot = editor.data()
        assert snapshot == {"head": ["a"], "body": ["b"]}
    finally:
        editor.deleteLater()


def test_dict_of_lists_editor_round_trip_through_selection(qapp):
    """Selecting a key then snapshotting must flush the right
    pane's edits back into the dict — defends against the
    "current key never written" regression."""
    editor = _DictOfListsEditor(initial={"head": ["one"]})
    try:
        # Force selection of "head".
        editor._keys.setCurrentRow(0)   # noqa: SLF001
        # Mutate via the values editor.
        editor._values.set_lines(["one", "two", "three"])   # noqa: SLF001
        assert editor.data() == {"head": ["one", "two", "three"]}
    finally:
        editor.deleteLater()


def test_dict_of_lists_editor_empty(qapp):
    editor = _DictOfListsEditor()
    try:
        assert editor.data() == {}
    finally:
        editor.deleteLater()


# ---------------------------------------------------------------
# _ScheduledEditor
# ---------------------------------------------------------------


def test_scheduled_editor_loads_initial(qapp):
    editor = _ScheduledEditor(initial=[
        ScheduledEvent(every_seconds=30.0, messages=["a", "b"]),
        ScheduledEvent(every_seconds=300.0, messages=["c"]),
    ])
    try:
        snapshot = editor.entries()
        assert len(snapshot) == 2
        assert snapshot[0]["every_seconds"] == pytest.approx(30.0)
        assert snapshot[0]["messages"] == ["a", "b"]
        assert snapshot[1]["every_seconds"] == pytest.approx(300.0)
    finally:
        editor.deleteLater()


def test_scheduled_editor_messages_edit_round_trip(qapp):
    """Selecting an entry then editing its messages list must
    flush back into the entry on snapshot."""
    editor = _ScheduledEditor(initial=[
        ScheduledEvent(every_seconds=60.0, messages=["x"]),
    ])
    try:
        editor._entries_list.setCurrentRow(0)   # noqa: SLF001
        editor._messages.set_lines(["x", "y"])   # noqa: SLF001
        snapshot = editor.entries()
        assert snapshot[0]["messages"] == ["x", "y"]
    finally:
        editor.deleteLater()


# ---------------------------------------------------------------
# PetScriptEditorDialog — end-to-end snapshot
# ---------------------------------------------------------------


def test_dialog_snapshot_matches_initial(qapp):
    """Open the dialog with a script, immediately snapshot — must
    equal the original. Catches a load-bug where the dialog
    drops fields silently."""
    initial = PetScript(
        name="snap",
        greetings=["g1", "g2"],
        time_of_day_greetings={"morning": ["m1"], "night": ["n1"]},
        hit_responses={"head": ["ouch"]},
        motion_lines={"wave": ["hi"]},
        scheduled=[ScheduledEvent(every_seconds=60.0, messages=["chime"])],
    )
    dialog = PetScriptEditorDialog(initial)
    try:
        snap = dialog.script()
        assert snap.name == "snap"
        assert snap.greetings == ["g1", "g2"]
        assert snap.time_of_day_greetings["morning"] == ["m1"]
        assert snap.time_of_day_greetings["night"] == ["n1"]
        assert snap.hit_responses == {"head": ["ouch"]}
        assert snap.motion_lines == {"wave": ["hi"]}
        assert len(snap.scheduled) == 1
        assert snap.scheduled[0].every_seconds == pytest.approx(60.0)
    finally:
        dialog.deleteLater()


def test_dialog_mutate_then_snapshot(qapp):
    """Open dialog → mutate the greetings list → snapshot reflects
    the change. Smokes the wiring between the tab widgets and
    the snapshot path."""
    initial = PetScript(greetings=["original"])
    dialog = PetScriptEditorDialog(initial)
    try:
        dialog._greetings.set_lines(["fresh1", "fresh2"])   # noqa: SLF001
        snap = dialog.script()
        assert snap.greetings == ["fresh1", "fresh2"]
    finally:
        dialog.deleteLater()


def test_dialog_default_script_round_trips(qapp, tmp_path):
    """Open with default script → snapshot → save → load →
    matches. End-to-end roundtrip catches schema drift between
    the editor and the file format."""
    initial = PetScript.default()
    dialog = PetScriptEditorDialog(initial)
    try:
        out = dialog.script()
        path = tmp_path / "rt.json"
        save_script(out, path)
        reloaded = load_script(path)
        assert reloaded.greetings == initial.greetings
    finally:
        dialog.deleteLater()
