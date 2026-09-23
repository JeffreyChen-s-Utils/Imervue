"""Qt smoke tests for ``AIUpscaleDialog``'s layout and control wiring.

Pins the dialog's items in order, the source section, the model / scale rows,
the overwrite toggle hiding the output row, the progress bars and the button
row, so restructuring ``_build_ui`` cannot drop, reorder or rewire a control.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PIL import Image
from PySide6.QtWidgets import QCheckBox, QLabel, QLineEdit, QProgressBar, QPushButton, QWidget

from Imervue.gui import ai_upscale_dialog as mod
from Imervue.gui.ai_upscale_dialog import TRADITIONAL_METHODS, UPSCALE_MODELS, AIUpscaleDialog


@pytest.fixture(autouse=True)
def _english(monkeypatch):
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", {})


def _make(**kwargs):
    return AIUpscaleDialog(SimpleNamespace(main_window=None), **kwargs)


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
    return type(x).__name__ if x is not None else None


def test_top_level_order(dialog):
    items = [_describe(x) for x in _items(dialog)]
    assert items[0][0] == "QLabel" and items[0][1].startswith("Upscale images using Real-ESRGAN")
    assert items[1:] == [
        "QWidget", ("QLabel", ""), "QHBoxLayout", "QHBoxLayout",
        ("QCheckBox", "Overwrite original files"), ("QLabel", "Output folder:"),
        "QHBoxLayout", "QProgressBar", "QProgressBar", ("QLabel", ""), "QHBoxLayout",
    ]
    assert _items(dialog)[0].wordWrap()


def test_source_section(dialog):
    section = _items(dialog)[1]
    assert section is dialog._src_row_widget  # noqa: SLF001
    inner = section.layout()
    margins = inner.contentsMargins()
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (0, 0, 0, 0)
    assert inner.spacing() == 4
    row = inner.itemAt(0).layout()
    label, edit, browse = _row(row)
    assert label.text() == "Source folder:"
    assert edit is dialog._src_edit and isinstance(edit, QLineEdit)  # noqa: SLF001
    assert browse.text() == "Browse..."
    assert row.stretch(1) == 1
    assert inner.itemAt(1).widget() is dialog._recursive_check  # noqa: SLF001
    assert dialog._recursive_check.text() == "Include subfolders"  # noqa: SLF001
    assert not section.isHidden()


def test_source_browse_rescans_and_defaults_output(dialog, monkeypatch, tmp_path):
    Image.new("RGB", (4, 4)).save(tmp_path / "a.png")
    (tmp_path / "sub").mkdir()
    Image.new("RGB", (4, 4)).save(tmp_path / "sub" / "b.png")
    monkeypatch.setattr(mod.QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *_a, **_k: str(tmp_path)))
    browse = _row(dialog._src_row_widget.layout().itemAt(0).layout())[2]  # noqa: SLF001
    browse.click()
    assert dialog._src_edit.text() == str(tmp_path)  # noqa: SLF001
    assert dialog._out_edit.text() == str(tmp_path)  # noqa: SLF001
    assert len(dialog._paths) == 1  # noqa: SLF001
    assert dialog._start_btn.isEnabled()  # noqa: SLF001
    dialog._recursive_check.setChecked(True)  # noqa: SLF001
    assert len(dialog._paths) == 2  # noqa: SLF001


def test_model_row(dialog):
    label, combo = _row(_items(dialog)[3])
    assert label.text() == "Model:"
    assert combo is dialog._model_combo  # noqa: SLF001
    assert [combo.itemData(i) for i in range(combo.count())] == [
        *TRADITIONAL_METHODS, *UPSCALE_MODELS]
    assert combo.toolTip().startswith("AI models reconstruct detail")
    assert _items(dialog)[3].stretch(1) == 1


def test_scale_row_follows_the_method(dialog):
    label, spin, stretch = _row(_items(dialog)[4])
    assert label is dialog._scale_label and spin is dialog._scale_spin  # noqa: SLF001
    assert stretch is None
    assert (spin.minimum(), spin.maximum(), spin.value()) == (2, 8, 2)
    assert spin.toolTip().startswith("Output multiplier")
    combo = dialog._model_combo  # noqa: SLF001
    combo.setCurrentIndex(len(TRADITIONAL_METHODS))
    assert label.isHidden() and spin.isHidden()
    combo.setCurrentIndex(0)
    assert not label.isHidden() and not spin.isHidden()


def test_overwrite_hides_output_row(dialog):
    check = dialog._overwrite_check  # noqa: SLF001
    assert not check.isChecked()
    assert check.toolTip().startswith("Replace each source file in place")
    edit, browse = _row(_items(dialog)[7])
    assert edit is dialog._out_edit and browse is dialog._out_browse  # noqa: SLF001
    assert browse.text() == "Browse..."
    widgets = (dialog._out_label, edit, browse)  # noqa: SLF001
    check.setChecked(True)
    assert all(w.isHidden() for w in widgets)
    check.setChecked(False)
    assert not any(w.isHidden() for w in widgets)


def test_output_browse(dialog, monkeypatch):
    monkeypatch.setattr(mod.QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *_a, **_k: "/out"))
    dialog._out_browse.click()  # noqa: SLF001
    assert dialog._out_edit.text() == "/out"  # noqa: SLF001


def test_progress_bars(dialog):
    bar, tile = _items(dialog)[8], _items(dialog)[9]
    assert (bar, tile) == (dialog._progress, dialog._tile_progress)  # noqa: SLF001
    assert bar.format() == "%v / %m  (%p%)"
    assert tile.format() == "Tile: %v / %m  (%p%)"
    assert bar.isHidden() and tile.isHidden()
    assert isinstance(bar, QProgressBar)


def test_button_row(dialog):
    stretch, cancel, start = _row(_items(dialog)[11])
    assert stretch is None
    assert cancel.text() == "Cancel" and start is dialog._start_btn  # noqa: SLF001
    assert start.text() == "Upscale" and not start.isEnabled()
    dialog.show()
    cancel.click()
    assert not dialog.isVisible()


def test_preset_paths_hide_source_and_fill_output(qapp, tmp_path):
    path = tmp_path / "x.png"
    Image.new("RGB", (4, 4)).save(path)
    dlg = _make(paths=[str(path)])
    try:
        assert dlg._src_row_widget.isHidden()  # noqa: SLF001
        assert dlg._out_edit.text() == str(tmp_path)  # noqa: SLF001
        assert dlg._start_btn.isEnabled()  # noqa: SLF001
        assert dlg._count_label.text() == "1 image(s)"  # noqa: SLF001
    finally:
        dlg.deleteLater()


def test_source_section_is_a_widget(dialog):
    assert isinstance(dialog._src_row_widget, QWidget)  # noqa: SLF001


def test_fill_upscale_model_combo(qapp):
    from PySide6.QtWidgets import QComboBox
    first_key, first = next(iter(TRADITIONAL_METHODS.items()))
    combo = QComboBox()
    try:
        mod.fill_upscale_model_combo(combo, {first["desc_key"]: "TRANSLATED"})
        assert [combo.itemData(i) for i in range(combo.count())] == [
            *TRADITIONAL_METHODS, *UPSCALE_MODELS]
        assert combo.itemData(0) == first_key and combo.itemText(0) == "TRANSLATED"
        last = list(UPSCALE_MODELS.values())[-1]
        assert combo.itemText(combo.count() - 1) == last["desc_default"]
    finally:
        combo.deleteLater()


def test_fill_upscale_model_combo_appends(qapp):
    from PySide6.QtWidgets import QComboBox
    combo = QComboBox()
    combo.addItem("existing", "x")
    try:
        mod.fill_upscale_model_combo(combo, {})
        assert combo.itemData(0) == "x"
        assert combo.count() == 1 + len(TRADITIONAL_METHODS) + len(UPSCALE_MODELS)
    finally:
        combo.deleteLater()
