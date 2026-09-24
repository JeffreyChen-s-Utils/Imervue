"""Characterisation tests for the desktop-pet workspace's "Window" group.

Pins the group's rows in order, each checkbox's text, its starting state from
the saved pet settings and the handler it drives, and the size / opacity /
snap rows (items, ranges, values, the opacity readout), so splitting the
group builder cannot drop, reorder or rewire a control.
"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QCheckBox, QComboBox, QGroupBox, QSlider, QSpinBox

from _qt_skip import pytestmark  # noqa: E402,F401
from Imervue.desktop_pet import pet_workspace as mod
from Imervue.desktop_pet import settings as pet_settings
from Imervue.desktop_pet.pet_workspace import PetWorkspace

# attribute, text, settings key (None = not restored), handler
_CHECKS = [
    ("_show_check", "Show pet on desktop", None, "_on_show_toggled"),
    ("_click_through_check", "Click-through (let mouse events pass to the desktop)",
     "click_through", "_on_click_through_toggled"),
    ("_anchor_check", "Lock position (ignore drags)", "anchor_locked", "_on_anchor_toggled"),
    ("_on_bottom_check", "Always on bottom (desktop widget — sits behind every window)",
     "always_on_bottom", "_on_always_on_bottom_toggled"),
    ("_fullscreen_check", "Hide when another app goes fullscreen", "hide_on_fullscreen",
     "_on_fullscreen_toggled"),
    ("_speech_check", "Speech bubble on click", "speech_enabled", "_on_speech_toggled"),
]


@pytest.fixture(autouse=True)
def _english(monkeypatch):
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", {})


def _window_group(ws) -> QGroupBox:
    return next(g for g in ws.findChildren(QGroupBox) if g.title() == "Window")


def _items(group):
    lay = group.layout()
    return [lay.itemAt(i).widget() or lay.itemAt(i).layout() for i in range(lay.count())]


def _row(layout):
    return [layout.itemAt(i).widget() for i in range(layout.count())]


@pytest.fixture
def workspace(qapp):
    ws = PetWorkspace()
    yield ws
    ws.deleteLater()


def test_group_rows_in_order(workspace):
    items = _items(_window_group(workspace))
    assert [getattr(workspace, attr) for attr, *_x in _CHECKS] == items[:6]
    assert [type(x).__name__ for x in items[6:]] == ["QHBoxLayout"] * 3
    for (attr, text, *_rest), box in zip(_CHECKS, items[:6], strict=True):
        assert isinstance(box, QCheckBox) and box.text() == text, attr


@pytest.mark.parametrize("flip", [False, True])
def test_checks_start_from_saved_settings(qapp, flip):
    saved = pet_settings.load()
    for _attr, _text, key, _handler in _CHECKS:
        if key is not None:
            saved[key] = flip
    pet_settings.save(saved)
    ws = PetWorkspace()
    try:
        for attr, _text, key, _handler in _CHECKS:
            if key is not None:
                assert getattr(ws, attr).isChecked() is flip, attr
    finally:
        ws.deleteLater()


def test_checks_drive_their_handlers(qapp, monkeypatch):
    calls = []
    for _attr, _text, _key, handler in _CHECKS:
        monkeypatch.setattr(PetWorkspace, handler,
                            lambda self, checked, h=handler: calls.append((h, checked)))
    ws = PetWorkspace()
    try:
        for attr, _text, _key, handler in _CHECKS:
            box = getattr(ws, attr)
            box.setChecked(not box.isChecked())
            assert calls[-1] == (handler, box.isChecked()), attr
    finally:
        ws.deleteLater()


def test_size_row(workspace):
    label, combo, stretch = _row(_items(_window_group(workspace))[6])
    assert label.text() == "Size:" and stretch is None
    assert isinstance(combo, QComboBox) and combo is workspace._size_combo  # noqa: SLF001
    assert [combo.itemData(i) for i in range(combo.count())] == ["small", "medium", "large"]
    assert [combo.itemText(i) for i in range(combo.count())] == ["Small", "Medium", "Large"]
    assert combo.currentData() == str(pet_settings.load()["size_preset"])


def test_opacity_row(workspace):
    row = _items(_window_group(workspace))[7]
    label, slider, readout = _row(row)
    assert label.text() == "Opacity:"
    assert isinstance(slider, QSlider) and slider is workspace._opacity_slider  # noqa: SLF001
    expected = int(float(pet_settings.load()["opacity"]) * 100)
    assert (slider.minimum(), slider.maximum(), slider.value()) == (10, 100, expected)
    assert readout is workspace._opacity_label and readout.text() == f"{expected}%"  # noqa: SLF001
    assert readout.minimumWidth() == 40
    assert row.stretch(1) == 1


def test_snap_row(workspace):
    label, spin, stretch = _row(_items(_window_group(workspace))[8])
    assert label.text() == "Edge-snap threshold (px):" and stretch is None
    assert isinstance(spin, QSpinBox) and spin is workspace._snap_spin  # noqa: SLF001
    assert (spin.minimum(), spin.maximum(), spin.value()) == (
        0, 200, int(pet_settings.load()["snap_threshold"]))


def test_rows_drive_their_handlers(qapp, monkeypatch):
    calls = []
    for handler in ("_on_size_changed", "_on_opacity_changed", "_on_snap_changed"):
        monkeypatch.setattr(PetWorkspace, handler,
                            lambda self, value, h=handler: calls.append((h, value)))
    ws = PetWorkspace()
    try:
        combo = ws._size_combo  # noqa: SLF001
        combo.setCurrentIndex(combo.findData("large" if combo.currentData() != "large" else "small"))
        ws._opacity_slider.setValue(42 if ws._opacity_slider.value() != 42 else 43)  # noqa: SLF001
        ws._snap_spin.setValue(7 if ws._snap_spin.value() != 7 else 8)  # noqa: SLF001
        assert [h for h, _v in calls] == ["_on_size_changed", "_on_opacity_changed",
                                          "_on_snap_changed"]
    finally:
        ws.deleteLater()
