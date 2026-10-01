"""Characterisation tests for ``CompareDialog``'s picker panel and tabs.

Pins the image list, the mode buttons and the slot each one runs, the four
tabs in order, and each tab's image label and slider row (range, default,
the slot it drives), so splitting the constructor cannot drop, reorder or
rewire a control.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QPushButton, QSlider

from Imervue.gpu_image_view.actions import compare_dialog as mod
from Imervue.gpu_image_view.actions.compare_dialog import CompareDialog

_PATHS = ["C:/pics/a.png", "C:/pics/b.jpg", "C:/pics/c.tif"]


@pytest.fixture(autouse=True)
def _english(monkeypatch):
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", {})


def _gui(paths=None):
    chosen = _PATHS if paths is None else paths
    return SimpleNamespace(main_window=None, model=SimpleNamespace(images=list(chosen)))


@pytest.fixture
def dialog(qapp):
    dlg = CompareDialog(_gui())
    yield dlg
    dlg.deleteLater()


def _row(layout):
    return [layout.itemAt(i).widget() for i in range(layout.count())]


def test_root_split(dialog):
    root = dialog.layout()
    assert isinstance(root, QHBoxLayout) and root.count() == 2
    assert root.itemAt(0).layout() is not None and root.itemAt(1).widget() is dialog._tabs  # noqa: SLF001
    assert [root.stretch(0), root.stretch(1)] == [1, 3]
    assert dialog.windowTitle() == "Compare Images"


def test_picker_list(dialog):
    lst = dialog._list  # noqa: SLF001
    assert isinstance(lst, QListWidget)
    assert lst.selectionMode() == QListWidget.SelectionMode.MultiSelection
    assert [lst.item(i).text() for i in range(lst.count())] == ["a.png", "b.jpg", "c.tif"]
    assert [lst.item(i).data(Qt.ItemDataRole.UserRole) for i in range(lst.count())] == _PATHS


def test_picker_panel_order_and_texts(dialog):
    left = dialog.layout().itemAt(0).layout()
    items = [left.itemAt(i).widget() or left.itemAt(i).layout() for i in range(left.count())]
    assert items[0] is dialog._list  # noqa: SLF001
    assert [w.text() for w in _row(items[1])] == ["Side-by-side (2)", "Side-by-side (4)"]
    assert [w.text() for w in items[2:]] == ["Overlay (2)", "Difference (2)", "A|B Split (2)"]


def test_mode_buttons_run_their_modes(qapp, monkeypatch):
    calls = []
    monkeypatch.setattr(CompareDialog, "_run_side_by_side", lambda self, n: calls.append(("sbs", n)))
    monkeypatch.setattr(CompareDialog, "_run_overlay", lambda self, *_a: calls.append(("overlay",)))
    monkeypatch.setattr(CompareDialog, "_run_difference", lambda self, *_a: calls.append(("diff",)))
    monkeypatch.setattr(CompareDialog, "_run_split", lambda self, *_a: calls.append(("split",)))
    dlg = CompareDialog(_gui())
    try:
        for button in dlg.findChildren(QPushButton):
            button.click()
        assert sorted(calls) == sorted([("sbs", 2), ("sbs", 4), ("overlay",), ("diff",), ("split",)])
    finally:
        dlg.deleteLater()


def test_tabs_in_order(dialog):
    tabs = dialog._tabs  # noqa: SLF001
    assert [tabs.tabText(i) for i in range(tabs.count())] == [
        "Side-by-side", "Overlay", "Difference", "A|B Split"]
    assert [tabs.widget(i) for i in range(4)] == [
        dialog._sbs_widget, dialog._overlay_widget, dialog._diff_widget,  # noqa: SLF001
        dialog._split_widget]  # noqa: SLF001
    assert dialog._sbs_layout.spacing() == 4  # noqa: SLF001
    assert dialog._sbs_labels == []  # noqa: SLF001
    assert dialog._overlay_arrs is None and dialog._diff_arrs is None  # noqa: SLF001


def _tab_parts(tab):
    lay = tab.layout()
    label = lay.itemAt(0).widget()
    assert lay.stretch(0) == 1
    return label, _row(lay.itemAt(1).layout())


def _slider_shape(slider):
    return (slider.minimum(), slider.maximum(), slider.value())


def test_overlay_tab(dialog):
    label, row = _tab_parts(dialog._overlay_widget)  # noqa: SLF001
    assert label is dialog._overlay_label and isinstance(label, mod._ImageLabel)  # noqa: SLF001
    assert [w.text() if isinstance(w, QLabel) else w for w in row] == [
        "A", dialog._overlay_slider, "B"]  # noqa: SLF001
    assert _slider_shape(dialog._overlay_slider) == (0, 100, 50)  # noqa: SLF001


def test_difference_tab(dialog):
    label, row = _tab_parts(dialog._diff_widget)  # noqa: SLF001
    assert label is dialog._diff_label  # noqa: SLF001
    assert row[0].text() == "Gain" and row[1] is dialog._diff_slider  # noqa: SLF001
    assert row[2] is dialog._diff_gain_label and row[2].text() == "1.0×"  # noqa: SLF001
    assert _slider_shape(dialog._diff_slider) == (10, 2000, 100)  # noqa: SLF001


def test_split_tab(dialog):
    label, row = _tab_parts(dialog._split_widget)  # noqa: SLF001
    assert label is dialog._split_label and isinstance(label, mod._SplitLabel)  # noqa: SLF001
    assert [w.text() if isinstance(w, QLabel) else w for w in row] == [
        "A", dialog._split_slider, "B"]  # noqa: SLF001
    assert _slider_shape(dialog._split_slider) == (0, 100, 50)  # noqa: SLF001


def test_sliders_drive_their_slots(qapp, monkeypatch):
    calls = []
    for name in ("_on_overlay_slider", "_on_diff_slider", "_on_split_slider",
                 "_on_split_widget_changed"):
        monkeypatch.setattr(CompareDialog, name, lambda self, v, n=name: calls.append((n, v)))
    dlg = CompareDialog(_gui())
    try:
        dlg._overlay_slider.setValue(20)  # noqa: SLF001
        dlg._diff_slider.setValue(300)  # noqa: SLF001
        dlg._split_slider.setValue(70)  # noqa: SLF001
        dlg._split_label.split_changed.emit(0.25)  # noqa: SLF001
        assert calls[:3] == [("_on_overlay_slider", 20), ("_on_diff_slider", 300),
                             ("_on_split_slider", 70)]
        assert calls[3][0] == "_on_split_widget_changed"
        assert calls[3][1] == pytest.approx(0.25)
        assert len(calls) == 4
    finally:
        dlg.deleteLater()


def test_empty_model(qapp):
    dlg = CompareDialog(_gui([]))
    try:
        assert dlg._list.count() == 0  # noqa: SLF001
        assert isinstance(dlg._overlay_slider, QSlider)  # noqa: SLF001
    finally:
        dlg.deleteLater()



def _selected_gui(paths, selected, mode=True):
    return SimpleNamespace(main_window=None, model=SimpleNamespace(images=list(paths)),
                           tile_selection_mode=mode, selected_tiles=set(selected))


def _chosen(dialog):
    return [item.data(Qt.ItemDataRole.UserRole) for item in dialog._list.selectedItems()]  # noqa: SLF001


def test_the_wall_selection_is_preselected_in_folder_order():
    gui = _selected_gui(_PATHS, {_PATHS[2], _PATHS[0]})
    assert mod.preselected_paths(gui) == [_PATHS[0], _PATHS[2]]
    assert mod.preselected_paths(_selected_gui(_PATHS, {_PATHS[0]}, mode=False)) == []
    assert mod.preselected_paths(_gui()) == []


def test_two_selected_thumbnails_open_side_by_side(qapp, tmp_path):
    """The dialog listed the folder with nothing selected: the choice was made twice."""
    from PIL import Image
    paths = []
    for name in ("a.png", "b.png", "c.png"):
        Image.new("RGB", (8, 8), "red").save(tmp_path / name)
        paths.append(str(tmp_path / name))
    dlg = CompareDialog(_selected_gui(paths, {paths[0], paths[2]}))
    try:
        assert sorted(_chosen(dlg)) == [paths[0], paths[2]]
        assert len(dlg._sbs_labels) == 2  # noqa: SLF001
        assert dlg._tabs.currentWidget() is dlg._sbs_widget  # noqa: SLF001
    finally:
        dlg.deleteLater()


def test_three_selected_thumbnails_are_preselected_only(qapp):
    dlg = CompareDialog(_selected_gui(_PATHS, set(_PATHS)))
    try:
        assert sorted(_chosen(dlg)) == sorted(_PATHS)
        assert dlg._sbs_labels == []  # noqa: SLF001
    finally:
        dlg.deleteLater()


def test_the_too_few_message_says_how_many(qapp, monkeypatch):
    """It showed a literal {n}."""
    shown = []
    monkeypatch.setattr(mod.QMessageBox, "information", lambda _p, _t, text: shown.append(text))
    dlg = CompareDialog(_gui())
    try:
        dlg._run_side_by_side(4)  # noqa: SLF001
    finally:
        dlg.deleteLater()
    assert shown == ["Select at least 4 images."]
