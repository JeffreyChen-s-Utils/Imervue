"""The Desktop Pet tab refuses a hotkey another action uses and warns about shared ones.

``desktop_pet/hotkey_conflicts.py`` (order- and case-independent chord
comparison) was tested but unreachable, so two actions could be saved on one
key and the global listener fired only one of them. The Global hotkeys rows now
check every edit, and the status line names saved bindings that share a key.
"""
from __future__ import annotations

import pytest
from PySide6.QtGui import QKeySequence

from Imervue.desktop_pet import settings as pet_settings
from Imervue.desktop_pet.hotkey_conflicts import clashing_action
from Imervue.desktop_pet.hotkey_manager import (
    ACTION_SPEAK_NOW,
    ACTION_TOGGLE_LOCK,
    ACTION_TOGGLE_VISIBLE,
    DEFAULT_HOTKEY_BINDINGS,
)
from Imervue.desktop_pet.pet_workspace import PetWorkspace, hotkey_conflict_notice, saved_hotkeys


def test_clashing_action_ignores_order_case_and_the_action_itself():
    bindings = {"a": "Ctrl+Shift+P", "b": "Alt+X"}
    assert clashing_action(bindings, "b", "shift+ctrl+p") == "a"
    assert clashing_action(bindings, "a", "Ctrl+Shift+P") is None     # its own key
    assert clashing_action(bindings, "b", "Ctrl+Q") is None
    assert clashing_action(bindings, "b", "not a key+") is None


def test_saved_hotkeys_overlay_the_defaults():
    pet_settings.update(hotkeys={ACTION_SPEAK_NOW: "Ctrl+Alt+S", ACTION_TOGGLE_LOCK: ""})
    merged = saved_hotkeys()
    assert merged[ACTION_SPEAK_NOW] == "Ctrl+Alt+S"
    assert merged[ACTION_TOGGLE_LOCK] == DEFAULT_HOTKEY_BINDINGS[ACTION_TOGGLE_LOCK]


def test_the_notice_names_the_actions_that_share_a_key():
    assert hotkey_conflict_notice(dict(DEFAULT_HOTKEY_BINDINGS)) == ""
    shared = dict(DEFAULT_HOTKEY_BINDINGS)
    shared[ACTION_SPEAK_NOW] = shared[ACTION_TOGGLE_VISIBLE]
    notice = hotkey_conflict_notice(shared)
    assert "Show / hide pet / Speak now" in notice


@pytest.fixture
def workspace(qapp):
    ws = PetWorkspace()
    yield ws
    ws.deleteLater()


def _edit(ws, action: str, key: str) -> None:
    edit = ws._hotkey_edits[action]                         # noqa: SLF001
    edit.setKeySequence(QKeySequence(key))
    ws._on_hotkey_edited(action, edit)                      # noqa: SLF001


def test_a_key_another_action_uses_is_refused(workspace):
    taken = DEFAULT_HOTKEY_BINDINGS[ACTION_TOGGLE_VISIBLE]
    _edit(workspace, ACTION_SPEAK_NOW, taken)
    edit = workspace._hotkey_edits[ACTION_SPEAK_NOW]        # noqa: SLF001
    assert edit.keySequence().toString() == QKeySequence(
        DEFAULT_HOTKEY_BINDINGS[ACTION_SPEAK_NOW]).toString()
    assert "Show / hide pet" in workspace._status.text()    # noqa: SLF001
    assert not (pet_settings.load().get("hotkeys") or {}).get(ACTION_SPEAK_NOW)


def test_a_free_key_is_saved_and_clears_the_warning(workspace):
    workspace._status.setText("old warning")                # noqa: SLF001
    _edit(workspace, ACTION_SPEAK_NOW, "Ctrl+Alt+F9")
    assert pet_settings.load()["hotkeys"][ACTION_SPEAK_NOW] == "Ctrl+Alt+F9"
    assert workspace._status.text() == ""                   # noqa: SLF001


def test_saved_bindings_that_share_a_key_are_reported_when_the_tab_opens(qapp):
    pet_settings.update(hotkeys={ACTION_SPEAK_NOW: DEFAULT_HOTKEY_BINDINGS[ACTION_TOGGLE_LOCK]})
    ws = PetWorkspace()
    try:
        assert "Lock / unlock position / Speak now" in ws._status.text()   # noqa: SLF001
    finally:
        ws.deleteLater()
