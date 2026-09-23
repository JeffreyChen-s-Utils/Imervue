"""Qt smoke tests for ``BatchConvertDialog``'s layout and control wiring.

Pins every top-level item in order, the source row and Browse rescan, the
format combo, the quality label + slider (text tracking, format-driven
visibility), the option boxes, the same-folder toggle hiding the output row,
and the button row, so restructuring ``_build_ui`` cannot drop, reorder or
rewire a control.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PIL import Image
from PySide6.QtWidgets import QCheckBox, QLabel, QPushButton

from Imervue.gui import batch_convert_dialog as mod
from Imervue.gui.batch_convert_dialog import BatchConvertDialog


@pytest.fixture(autouse=True)
def _english(monkeypatch):
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", {})


def _make(paths=None):
    return BatchConvertDialog(SimpleNamespace(main_window=None), paths=paths)


@pytest.fixture
def dialog(qapp):
    dlg = _make()
    yield dlg
    dlg.deleteLater()


def _items(dlg):
    layout = dlg.layout()
    return [layout.itemAt(i).widget() or layout.itemAt(i).layout() for i in range(layout.count())]


def _row(layout):
    return [layout.itemAt(i).widget() for i in range(layout.count())]


def _describe(x):
    if isinstance(x, (QLabel, QCheckBox, QPushButton)):
        return (type(x).__name__, x.text())
    return type(x).__name__


def test_top_level_order(dialog):
    assert [_describe(x) for x in _items(dialog)] == [
        ("QLabel", "Source folder:"), "QHBoxLayout", ("QLabel", ""),
        "QHBoxLayout", ("QLabel", "Quality: 85"), "QSlider",
        ("QCheckBox", "Skip images already in target format"),
        ("QCheckBox", "Delete original files after conversion"),
        ("QCheckBox", "Save to same folder as source"), ("QLabel", "Output folder:"),
        "QHBoxLayout", "QProgressBar", ("QLabel", ""), "QHBoxLayout",
    ]


def test_source_row(dialog):
    row = _items(dialog)[1]
    edit, browse = _row(row)
    assert edit is dialog._src_edit  # noqa: SLF001
    assert edit.placeholderText() == "Choose a folder with images..."
    assert browse.text() == "Browse..."
    assert row.stretch(0) == 1


def test_source_browse_scans_and_fills_output(dialog, monkeypatch, tmp_path):
    for name in ("a.png", "b.jpg"):
        Image.new("RGB", (4, 4)).save(tmp_path / name)
    monkeypatch.setattr(mod.QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *_a, **_k: str(tmp_path)))
    _row(_items(dialog)[1])[1].click()
    assert dialog._src_edit.text() == str(tmp_path)  # noqa: SLF001
    assert len(dialog._paths) == 2  # noqa: SLF001
    assert dialog._count_label.text() == "2 image(s) found"  # noqa: SLF001
    assert dialog._out_edit.text() == str(tmp_path)  # noqa: SLF001
    assert dialog._start_btn.isEnabled()  # noqa: SLF001


def test_format_row(dialog):
    label, combo = _row(_items(dialog)[3])
    assert label.text() == "Convert to:"
    assert combo is dialog._fmt_combo  # noqa: SLF001
    assert combo.currentText() == "WebP"
    assert [combo.itemText(i) for i in range(combo.count())] == list(mod.available_formats())
    assert combo.toolTip().startswith("Output container")


def test_quality_tracks_the_slider_and_the_format(dialog):
    label, slider = dialog._quality_label, dialog._quality_slider  # noqa: SLF001
    assert (slider.minimum(), slider.maximum(), slider.value()) == (0, 100, 85)
    assert slider.toolTip().startswith("Compression quality")
    slider.setValue(40)
    assert label.text() == "Quality: 40"
    assert not label.isHidden() and not slider.isHidden()
    dialog._fmt_combo.setCurrentText("PNG")  # noqa: SLF001
    assert label.isHidden() and slider.isHidden()
    dialog._fmt_combo.setCurrentText("JPEG")  # noqa: SLF001
    assert not label.isHidden() and not slider.isHidden()


def test_option_boxes(dialog):
    assert dialog._skip_same.isChecked()  # noqa: SLF001
    assert not dialog._delete_orig.isChecked()  # noqa: SLF001
    assert dialog._skip_same.toolTip().startswith("Don't re-encode")  # noqa: SLF001
    assert dialog._delete_orig.toolTip().startswith("Move originals to recycle bin")  # noqa: SLF001


def test_same_dir_toggle_shows_output_row(dialog, monkeypatch):
    check = dialog._same_dir_check  # noqa: SLF001
    edit, browse = _row(_items(dialog)[10])
    assert (edit, browse) == (dialog._out_edit, dialog._out_browse)  # noqa: SLF001
    widgets = (dialog._out_label, edit, browse)  # noqa: SLF001
    assert check.isChecked()
    assert all(w.isHidden() for w in widgets)
    check.setChecked(False)
    assert not any(w.isHidden() for w in widgets)
    monkeypatch.setattr(mod.QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *_a, **_k: "/out"))
    browse.click()
    assert edit.text() == "/out"
    check.setChecked(True)
    assert all(w.isHidden() for w in widgets)


def test_progress_and_buttons(dialog):
    bar = _items(dialog)[11]
    assert bar is dialog._progress and bar.isHidden()  # noqa: SLF001
    assert bar.format() == "%v / %m  (%p%)"
    stretch, cancel, start = _row(_items(dialog)[13])
    assert stretch is None
    assert cancel.text() == "Cancel"
    assert start is dialog._start_btn and start.text() == "Convert"  # noqa: SLF001
    dialog.show()
    cancel.click()
    assert not dialog.isVisible()


def test_paths_prefill_both_folders(qapp, tmp_path):
    path = tmp_path / "x.png"
    Image.new("RGB", (4, 4)).save(path)
    dlg = _make(paths=[str(path)])
    try:
        assert dlg._src_edit.text() == str(tmp_path)  # noqa: SLF001
        assert dlg._out_edit.text() == str(tmp_path)  # noqa: SLF001
        assert dlg._count_label.text() == "1 image(s) found"  # noqa: SLF001
        assert dlg._start_btn.isEnabled()  # noqa: SLF001
    finally:
        dlg.deleteLater()
