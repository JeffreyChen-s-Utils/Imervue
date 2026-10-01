"""The Desktop Pet tab mirrors pet settings changed from anywhere.

A toggle from the pet's context menu, the tray or a hotkey used to leave the
tab's checkbox (and, for click-through, the tray) showing the old state. Runs
on stand-ins with real checkboxes but no PetWindow (a QOpenGLWidget), so it
runs on headless CI.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QCheckBox, QComboBox

from Imervue.desktop_pet import pet_workspace as ws_mod
from Imervue.desktop_pet.pet_window import PetWindow
from Imervue.desktop_pet.pet_workspace import PetWorkspace
from Imervue.desktop_pet.settings import DEFAULT_PET_ID


def _tab(qapp):
    """A stand-in tab: every mirrored checkbox, the size combo and a tray."""
    toggled = []
    tab = SimpleNamespace(toggled=toggled, tray=[])
    for attr in (*ws_mod._WINDOW_CHECKS.values(), *ws_mod._DRIVER_CHECKS.values()):  # noqa: SLF001
        box = QCheckBox()
        box.toggled.connect(lambda checked, name=attr: toggled.append((name, checked)))
        setattr(tab, attr, box)
    tab._size_combo = QComboBox()
    for preset in ("small", "medium", "large"):
        tab._size_combo.addItem(preset, preset)
    tab._size_combo.currentIndexChanged.connect(lambda i: toggled.append(("size", i)))
    tab._tray = SimpleNamespace(sync_click_through=tab.tray.append)
    return tab


def _changed(tab, key, value):
    PetWorkspace._on_pet_setting_changed(tab, key, value)  # noqa: SLF001


@pytest.mark.parametrize("key", sorted(ws_mod._WINDOW_CHECKS))  # noqa: SLF001
def test_a_window_setting_ticks_its_checkbox_quietly(qapp, key):
    tab = _tab(qapp)
    _changed(tab, key, True)
    assert getattr(tab, ws_mod._WINDOW_CHECKS[key]).isChecked()  # noqa: SLF001
    assert tab.toggled == []


def test_click_through_also_updates_the_tray(qapp):
    tab = _tab(qapp)
    _changed(tab, "click_through", True)
    _changed(tab, "click_through", False)
    assert tab.tray == [True, False]


def test_driver_settings_tick_their_checkboxes(qapp):
    tab = _tab(qapp)
    _changed(tab, "drivers", {"auto_blink": True, "mouse_gaze": True, "mic_lipsync": False})
    assert tab._blink_check.isChecked()  # noqa: SLF001
    assert tab._gaze_check.isChecked()  # noqa: SLF001
    assert not tab._mic_check.isChecked()  # noqa: SLF001
    assert not tab._idle_check.isChecked()  # noqa: SLF001 - absent keys are left alone
    assert tab.toggled == []


def test_a_size_change_moves_the_combo(qapp):
    tab = _tab(qapp)
    _changed(tab, "size_preset", "large")
    assert tab._size_combo.currentData() == "large"  # noqa: SLF001
    _changed(tab, "size_preset", "huge")
    assert tab._size_combo.currentData() == "large"  # noqa: SLF001
    assert tab.toggled == []


def test_other_settings_are_ignored(qapp):
    tab = _tab(qapp)
    _changed(tab, "opacity", 0.5)
    _changed(tab, "drivers", "not a dict")
    assert tab.toggled == []
    assert tab.tray == []


class _Pet(QObject):
    setting_changed = Signal(str, object)

    def __init__(self):
        super().__init__()
        self._pet_id = DEFAULT_PET_ID


def test_every_saved_pet_setting_is_announced(qapp):
    pet = _Pet()
    seen = []
    pet.setting_changed.connect(lambda key, value: seen.append((key, value)))
    PetWindow._persist(pet, click_through=True, size_preset="small")  # noqa: SLF001
    assert seen == [("click_through", True), ("size_preset", "small")]
