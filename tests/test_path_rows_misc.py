"""The path + Browse rows of the export, GIF / video, anaglyph and LUT dialogs.

Each pins the row's widgets, the edit's starting text and the exact file
dialog call Browse makes (title, start path, filter), including a cancelled
pick keeping the edit — the contract the shared ``dialog_rows`` builders have
to keep when these rows are built through them.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image
from PySide6.QtWidgets import QFileDialog, QLabel, QPushButton

from Imervue.multi_language.language_wrapper import language_wrapper


@pytest.fixture(autouse=True)
def _english(monkeypatch):
    monkeypatch.setattr(language_wrapper, "language_word_dict", {})


@pytest.fixture
def image(tmp_path):
    path = tmp_path / "photo.png"
    Image.fromarray(np.full((12, 16, 3), 90, dtype=np.uint8)).save(path)
    return str(path)


def _find_layout(layout, widget):
    """The (possibly nested) layout that directly holds ``widget``."""
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item.widget() is widget:
            return layout
        if item.layout() is not None:
            found = _find_layout(item.layout(), widget)
            if found is not None:
                return found
    return None


def _row_widgets(dialog, edit):
    row = _find_layout(dialog.layout(), edit)
    assert row is not None
    return row, [row.itemAt(i).widget() for i in range(row.count())]


def _record(monkeypatch, method, answers):
    calls = []
    it = iter(answers)

    def fake(*args):
        calls.append(args)
        return next(it)

    monkeypatch.setattr(QFileDialog, method, staticmethod(fake))
    return calls


def _click_twice(button, edit, picked):
    button.click()
    assert edit.text() == picked
    button.click()  # cancelled
    assert edit.text() == picked


def test_export_dialog_path_row(qapp, monkeypatch, image):
    from Imervue.gui.export_dialog import FORMAT_EXTENSIONS, ExportDialog
    dialog = ExportDialog(image)
    try:
        edit = dialog.path_edit
        row, widgets = _row_widgets(dialog, edit)
        assert widgets == [edit, widgets[1]]
        assert isinstance(widgets[1], QPushButton) and widgets[1].text() == "Browse..."
        assert row.stretch(0) == 1
        assert edit.placeholderText() == "Output path"
        start = edit.text()
        assert start
        fmt = dialog.format_combo.currentText()
        calls = _record(monkeypatch, "getSaveFileName", [("C:/x/out.png", ""), ("", "")])
        _click_twice(widgets[1], edit, "C:/x/out.png")
        assert calls[0] == (dialog, "Save", start, f"{fmt} (*{FORMAT_EXTENSIONS.get(fmt, '.*')})")
    finally:
        dialog.deleteLater()


def test_gif_video_dialog_path_row(qapp, monkeypatch, image):
    from Imervue.gui.gif_video_dialog import GifVideoDialog
    dialog = GifVideoDialog(SimpleNamespace(main_window=None), [image])
    try:
        edit = dialog._path_edit  # noqa: SLF001
        row, widgets = _row_widgets(dialog, edit)
        assert widgets == [edit, widgets[1]]
        assert widgets[1].text() == "Browse..." and row.stretch(0) == 1
        assert edit.text() == str(Path(image).parent / "output.gif")
        fmt = dialog._fmt_combo.currentText()  # noqa: SLF001
        ext = ".gif" if fmt == "GIF" else ".mp4"
        start = edit.text()
        calls = _record(monkeypatch, "getSaveFileName", [("C:/x/a.gif", ""), ("", "")])
        _click_twice(widgets[1], edit, "C:/x/a.gif")
        assert calls[0] == (dialog, "Save As", start, f"{fmt} (*{ext})")
    finally:
        dialog.deleteLater()


def test_gif_video_dialog_without_paths_starts_empty(qapp):
    from Imervue.gui.gif_video_dialog import GifVideoDialog
    dialog = GifVideoDialog(SimpleNamespace(main_window=None), [])
    try:
        assert dialog._path_edit.text() == ""  # noqa: SLF001
    finally:
        dialog.deleteLater()


def test_anaglyph_dialog_right_eye_row(qapp, monkeypatch, image):
    from Imervue.gui.anaglyph_dialog import AnaglyphDialog
    dialog = AnaglyphDialog(object(), image)
    try:
        edit = dialog._right_edit  # noqa: SLF001
        row, widgets = _row_widgets(dialog, edit)
        assert widgets == [edit, widgets[1]]
        assert widgets[1].text() == "Browse..." and row.stretch(0) == 1
        assert edit.text() == ""
        calls = _record(monkeypatch, "getOpenFileName", [("C:/x/r.png", ""), ("", "")])
        _click_twice(widgets[1], edit, "C:/x/r.png")
        assert calls[0] == (dialog, "Right-eye image:", "",
                            "Images (*.jpg *.jpeg *.png *.tif *.tiff *.webp)")
    finally:
        dialog.deleteLater()


@pytest.mark.parametrize("preset", ["", "C:/luts/film.cube"])
def test_lut_dialog_row(qapp, monkeypatch, image, preset):
    from Imervue.gui import lut_dialog
    from Imervue.image.recipe import Recipe
    recipe = Recipe()
    recipe.lut_path = preset
    monkeypatch.setattr(lut_dialog.recipe_store, "get_for_path", lambda _p: recipe)
    dialog = lut_dialog.LutDialog(None, image)
    try:
        edit = dialog._path_edit  # noqa: SLF001
        row, widgets = _row_widgets(dialog, edit)
        label, _edit, browse, clear = widgets
        assert isinstance(label, QLabel) and label.text() == ".cube file:"
        assert (browse.text(), clear.text()) == ("Browse...", "Clear")
        assert [row.stretch(i) for i in range(4)] == [0, 1, 0, 0]
        assert edit.text() == preset
        calls = _record(monkeypatch, "getOpenFileName", [("C:/x/a.cube", ""), ("", "")])
        _click_twice(browse, edit, "C:/x/a.cube")
        assert calls[0] == (dialog, "Select .cube LUT", preset or str(Path.home()),
                            "Cube LUT (*.cube)")
        assert calls[1][2] == "C:/x/a.cube"
        clear.click()
        assert edit.text() == ""
    finally:
        dialog.deleteLater()
