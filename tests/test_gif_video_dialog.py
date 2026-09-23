"""Characterisation tests for ``GifVideoDialog``'s layout and control wiring.

Pins the frame list (order, path data, drag mode), the move buttons, the
settings group (format, FPS, size spins with their "Auto" value, loop box and
its GIF-only visibility), the output row, and the Cancel / Create row, so
restructuring ``_build_ui`` cannot drop, reorder or rewire a control.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QGroupBox, QLabel, QListWidget, QProgressBar, QPushButton, QSpinBox,
)

from Imervue.gui import gif_video_dialog as mod
from Imervue.gui.gif_video_dialog import GifVideoDialog

_PATHS = ["C:/shots/one.png", "C:/shots/two.png", "C:/shots/three.png"]


@pytest.fixture(autouse=True)
def _english(monkeypatch):
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", {})


@pytest.fixture
def dialog(qapp):
    dlg = GifVideoDialog(SimpleNamespace(main_window=None), list(_PATHS))
    yield dlg
    dlg.deleteLater()


def _items(dlg):
    layout = dlg.layout()
    return [layout.itemAt(i).widget() or layout.itemAt(i).layout() for i in range(layout.count())]


def _row(layout):
    return [layout.itemAt(i).widget() for i in range(layout.count())]


def test_top_level_order(dialog):
    kinds = [type(x).__name__ for x in _items(dialog)]
    assert kinds == ["QLabel", "QListWidget", "QHBoxLayout", "QGroupBox", "QHBoxLayout",
                     "QProgressBar", "QLabel", "QHBoxLayout"]
    assert _items(dialog)[0].text() == "Drag to reorder (top = first frame):"


def test_frame_list(dialog):
    lst = _items(dialog)[1]
    assert lst is dialog._list and isinstance(lst, QListWidget)  # noqa: SLF001
    assert lst.dragDropMode() == QListWidget.DragDropMode.InternalMove
    assert [lst.item(i).text() for i in range(lst.count())] == ["one.png", "two.png", "three.png"]
    assert [lst.item(i).data(Qt.ItemDataRole.UserRole) for i in range(lst.count())] == _PATHS


def test_order_row_moves_items(dialog):
    up, down, stretch = _row(_items(dialog)[2])
    assert (up.text(), down.text(), stretch) == ("Move Up", "Move Down", None)
    lst = dialog._list  # noqa: SLF001
    lst.setCurrentRow(1)
    up.click()
    assert lst.item(0).text() == "two.png"
    down.click()
    assert lst.item(1).text() == "two.png"


def test_settings_group(dialog):
    group = _items(dialog)[3]
    assert isinstance(group, QGroupBox) and group.title() == "Settings"
    lay = group.layout()
    fmt_row, fps_row, size_row = (lay.itemAt(i).layout() for i in range(3))
    loop = lay.itemAt(3).widget()
    label, combo = _row(fmt_row)
    assert label.text() == "Format:" and combo is dialog._fmt_combo  # noqa: SLF001
    assert isinstance(combo, QComboBox)
    assert [combo.itemText(i) for i in range(combo.count())] == ["GIF", "MP4"]
    fps_label, fps, fps_stretch = _row(fps_row)
    assert fps_label.text() == "FPS:" and fps is dialog._fps_spin and fps_stretch is None  # noqa: SLF001
    assert (fps.minimum(), fps.maximum(), fps.value()) == (1, 60, 5)
    w_label, width, h_label, height = _row(size_row)
    assert (w_label.text(), h_label.text()) == ("Width:", "Height:")
    for spin, attr in ((width, "_width_spin"), (height, "_height_spin")):
        assert isinstance(spin, QSpinBox) and spin is getattr(dialog, attr)
        assert (spin.minimum(), spin.maximum(), spin.value()) == (0, 99999, 0)
        assert spin.specialValueText() == "Auto"
    assert isinstance(loop, QCheckBox) and loop is dialog._loop_check  # noqa: SLF001
    assert loop.text() == "Loop forever" and loop.isChecked()


def test_loop_box_only_for_gif(dialog):
    combo, loop = dialog._fmt_combo, dialog._loop_check  # noqa: SLF001
    combo.setCurrentText("MP4")
    assert loop.isHidden()
    combo.setCurrentText("GIF")
    assert not loop.isHidden()


def test_progress_status_and_buttons(qapp, monkeypatch):
    calls = []
    monkeypatch.setattr(GifVideoDialog, "_on_cancel", lambda self, *_a: calls.append("cancel"))
    monkeypatch.setattr(GifVideoDialog, "_do_create", lambda self, *_a: calls.append("create"))
    dlg = GifVideoDialog(SimpleNamespace(main_window=None), list(_PATHS))
    try:
        items = _items(dlg)
        assert isinstance(items[5], QProgressBar) and items[5].isHidden()
        assert isinstance(items[6], QLabel) and items[6] is dlg._status_label  # noqa: SLF001
        stretch, cancel, create = _row(items[7])
        assert stretch is None and cancel.text() == "Cancel"
        assert create is dlg._create_btn and create.text() == "Create"  # noqa: SLF001
        assert isinstance(create, QPushButton)
        cancel.click()
        create.click()
        assert calls == ["cancel", "create"]
    finally:
        dlg.deleteLater()
