"""Qt smoke tests for ``ImageSanitizeDialog``'s layout and control wiring.

Pins the widgets the dialog builds (order, ranges, combo contents) and the
browse / resolution-hint wiring, so restructuring ``_build_ui`` cannot drop,
reorder or rewire a control.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import (
    QCheckBox, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton,
)

from Imervue.gui import image_sanitize_dialog as mod
from Imervue.gui.ai_upscale_dialog import TRADITIONAL_METHODS, UPSCALE_MODELS
from Imervue.gui.image_sanitize_dialog import TARGET_RESOLUTIONS, ImageSanitizeDialog


@pytest.fixture
def dialog(qapp):
    dlg = ImageSanitizeDialog(SimpleNamespace(main_window=None))
    yield dlg
    dlg.deleteLater()


def _row_widgets(row: QHBoxLayout) -> list:
    return [row.itemAt(i).widget() for i in range(row.count())]


def _top_level_kinds(dlg) -> list[str]:
    layout = dlg.layout()
    kinds = []
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item.widget() is not None:
            kinds.append(type(item.widget()).__name__)
        elif item.layout() is not None:
            kinds.append("row")
        else:
            kinds.append("space")
    return kinds


def test_top_level_layout_order(dialog):
    assert _top_level_kinds(dialog) == [
        "QLabel", "space", "row", "QCheckBox", "row", "row", "row", "row",
        "QGroupBox", "QProgressBar", "QProgressBar", "QLabel", "space", "row",
    ]


def test_folder_rows_hold_label_edit_and_browse(dialog):
    layout = dialog.layout()
    src_row, out_row = layout.itemAt(2).layout(), layout.itemAt(4).layout()
    for row, edit in ((src_row, dialog._src_edit), (out_row, dialog._out_edit)):  # noqa: SLF001
        label, line_edit, browse = _row_widgets(row)
        assert isinstance(label, QLabel)
        assert line_edit is edit
        assert isinstance(line_edit, QLineEdit)
        assert isinstance(browse, QPushButton)
    assert isinstance(layout.itemAt(3).widget(), QCheckBox)
    assert not dialog._recursive_check.isChecked()  # noqa: SLF001


def test_browse_buttons_fill_their_own_edit(dialog, monkeypatch):
    picks = iter(["/src/dir", "", "/out/dir"])
    monkeypatch.setattr(mod.QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *_a, **_k: next(picks)))
    layout = dialog.layout()
    src_browse = _row_widgets(layout.itemAt(2).layout())[2]
    out_browse = _row_widgets(layout.itemAt(4).layout())[2]
    src_browse.click()
    src_browse.click()  # cancelled pick keeps the previous text
    out_browse.click()
    assert dialog._src_edit.text() == "/src/dir"  # noqa: SLF001
    assert dialog._out_edit.text() == "/out/dir"  # noqa: SLF001


def test_format_combo_items(dialog):
    combo = dialog._fmt_combo  # noqa: SLF001
    assert [combo.itemData(i) for i in range(combo.count())] == [
        "same", ".png", ".jpg", ".webp", ".bmp", ".tiff"]
    assert combo.currentData() == "same"


def test_spin_ranges_and_defaults(dialog):
    rand, quality = dialog._rand_spin, dialog._quality_spin  # noqa: SLF001
    assert (rand.minimum(), rand.maximum(), rand.value()) == (4, 32, 8)
    assert (quality.minimum(), quality.maximum(), quality.value()) == (1, 100, 95)


def test_upscale_group_combos(dialog):
    res, model = dialog._res_combo, dialog._model_combo  # noqa: SLF001
    assert [res.itemData(i) for i in range(res.count())] == [px for *_x, px in TARGET_RESOLUTIONS]
    assert [model.itemData(i) for i in range(model.count())] == [
        *TRADITIONAL_METHODS, *UPSCALE_MODELS]
    group = dialog.findChild(QGroupBox)
    assert dialog._model_hint.parent() is group  # noqa: SLF001


def test_resolution_change_toggles_model_combo_and_hint(dialog):
    res, model, hint = dialog._res_combo, dialog._model_combo, dialog._model_hint  # noqa: SLF001
    assert res.currentData() == 0
    assert not model.isEnabled()
    assert hint.text() == ""
    res.setCurrentIndex(1)
    assert model.isEnabled()
    assert "1920" in hint.text()
    res.setCurrentIndex(0)
    assert not model.isEnabled()
    assert hint.text() == ""


def test_progress_widgets_start_hidden(dialog):
    bars = dialog.findChildren(QProgressBar)
    assert bars == [dialog._progress, dialog._tile_progress]  # noqa: SLF001
    assert all(bar.isHidden() for bar in bars)
    assert dialog._tile_progress.format() == "Tile: %v / %m  (%p%)"  # noqa: SLF001
    assert dialog._status_label.text() == ""  # noqa: SLF001


def test_button_row_start_then_close(dialog):
    buttons = _row_widgets(dialog.layout().itemAt(13).layout())
    start, stretch, close = buttons
    assert start is dialog._start_btn  # noqa: SLF001
    assert stretch is None
    assert isinstance(close, QPushButton)
    dialog.show()
    assert dialog.isVisible()
    close.click()
    assert not dialog.isVisible()


def test_folder_argument_prefills_source(qapp, tmp_path):
    dlg = ImageSanitizeDialog(SimpleNamespace(main_window=None), folder=str(tmp_path))
    try:
        assert dlg._src_edit.text() == str(tmp_path)  # noqa: SLF001
    finally:
        dlg.deleteLater()


def test_missing_folder_argument_leaves_source_empty(qapp, tmp_path):
    dlg = ImageSanitizeDialog(SimpleNamespace(main_window=None), folder=str(tmp_path / "gone"))
    try:
        assert dlg._src_edit.text() == ""  # noqa: SLF001
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# Start: which settings reach the worker for each upscale choice.
# ---------------------------------------------------------------------------

def _cfg(worker):
    s = worker._settings  # noqa: SLF001
    return (s.output_ext, s.rand_len, s.jpeg_quality, s.png_compress, s.target_long_edge,
            s.model_key)


@pytest.fixture
def started(qapp, tmp_path, monkeypatch):
    """Dialog with a one-image source; ``start(res, model)`` presses Start."""
    from PIL import Image
    src, out = tmp_path / "src", tmp_path / "out"
    src.mkdir()
    Image.new("RGB", (4, 4)).save(src / "a.png")
    monkeypatch.setattr(mod._SanitizeWorker, "start", lambda self: None)  # noqa: SLF001
    deps = []
    from Imervue.plugin import pip_installer
    monkeypatch.setattr(pip_installer, "ensure_dependencies",
                        lambda _parent, _packages, on_ready: deps.append(on_ready))
    dlg = ImageSanitizeDialog(SimpleNamespace(main_window=None))

    def start(res_index, model_key):
        dlg._src_edit.setText(str(src))  # noqa: SLF001
        dlg._out_edit.setText(str(out))  # noqa: SLF001
        dlg._res_combo.setCurrentIndex(res_index)  # noqa: SLF001
        dlg._model_combo.setCurrentIndex(dlg._model_combo.findData(model_key))  # noqa: SLF001
        dlg._rand_spin.setValue(12)  # noqa: SLF001
        dlg._quality_spin.setValue(80)  # noqa: SLF001
        dlg._do_start()  # noqa: SLF001
        return dlg

    yield start, deps
    dlg.deleteLater()


def _res_index(px):
    return [p for *_x, p in TARGET_RESOLUTIONS].index(px)


def test_start_without_upscale_drops_the_model(started):
    start, deps = started
    ai_model = next(iter(UPSCALE_MODELS))
    dlg = start(_res_index(0), ai_model)   # "No upscale"
    assert deps == []
    ext = dlg._fmt_combo.currentData()  # noqa: SLF001
    assert _cfg(dlg._worker) == (ext, 12, 80, 6, 0, "")  # noqa: SLF001


def test_start_with_traditional_upscale_keeps_target_and_method(started):
    start, deps = started
    px = [p for *_x, p in TARGET_RESOLUTIONS if p][0]
    method = next(iter(TRADITIONAL_METHODS))
    dlg = start(_res_index(px), method)
    assert deps == []
    assert _cfg(dlg._worker)[4:] == (px, method)  # noqa: SLF001


def test_start_with_ai_upscale_installs_dependencies_first(started):
    start, deps = started
    px = [p for *_x, p in TARGET_RESOLUTIONS if p][0]
    model = next(iter(UPSCALE_MODELS))
    dlg = start(_res_index(px), model)
    assert dlg._worker is None and len(deps) == 1  # noqa: SLF001
    deps[0]()
    assert _cfg(dlg._worker)[1:] == (12, 80, 6, px, model)  # noqa: SLF001
