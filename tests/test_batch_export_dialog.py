"""Qt smoke tests for ``BatchExportDialog``'s layout and control wiring.

Pins every top-level item in order, the preset / format rows, the quality
label + slider, the resize and watermark groups, the output row, and the
button row, plus a preset filling the controls, so restructuring
``_build_ui`` cannot drop, reorder or rewire a control.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QGroupBox, QLabel, QPushButton

from Imervue.gui import batch_export_dialog as mod
from Imervue.gui.batch_export_dialog import BatchExportDialog
from Imervue.image import export_presets


@pytest.fixture(autouse=True)
def _english(monkeypatch):
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", {})


@pytest.fixture
def dialog(qapp, tmp_path):
    dlg = BatchExportDialog(SimpleNamespace(main_window=None),
                            [str(tmp_path / "a.png"), str(tmp_path / "b.png")])
    yield dlg
    dlg.deleteLater()


def _items(dlg):
    layout = dlg.layout()
    return [layout.itemAt(i).widget() or layout.itemAt(i).layout() for i in range(layout.count())]


def _row(layout):
    return [layout.itemAt(i).widget() for i in range(layout.count())]


def _describe(x):
    if isinstance(x, (QLabel, QPushButton, QGroupBox)):
        text = x.title() if isinstance(x, QGroupBox) else x.text()
        return (type(x).__name__, text)
    return type(x).__name__


def test_top_level_order(dialog):
    assert [_describe(x) for x in _items(dialog)] == [
        ("QLabel", "2 image(s) selected"), "QHBoxLayout", "QHBoxLayout",
        ("QLabel", "Quality: 85"), "QSlider", ("QGroupBox", "Resize"),
        ("QGroupBox", "Watermark"), "QHBoxLayout", "QProgressBar", ("QLabel", ""),
        "QHBoxLayout",
    ]


def test_preset_row(dialog):
    label, combo = _row(_items(dialog)[1])
    assert label.text() == "Preset:" and combo is dialog._preset_combo  # noqa: SLF001
    assert combo.itemText(0) == "Custom" and combo.itemData(0) is None
    assert [combo.itemData(i) for i in range(1, combo.count())] == [
        p.key for p in export_presets.builtin_presets()]
    assert _items(dialog)[1].stretch(1) == 1


def test_format_row_and_quality(dialog):
    label, combo = _row(_items(dialog)[2])
    assert label.text() == "Format:" and combo is dialog._fmt_combo  # noqa: SLF001
    assert [combo.itemText(i) for i in range(combo.count())] == list(mod.available_formats())
    q_label, slider = dialog._quality_label, dialog._quality_slider  # noqa: SLF001
    assert (slider.minimum(), slider.maximum(), slider.value()) == (0, 100, 85)
    slider.setValue(33)
    assert q_label.text() == "Quality: 33"
    combo.setCurrentText("PNG")
    assert q_label.isHidden() and slider.isHidden()
    combo.setCurrentText("JPEG")
    assert not q_label.isHidden() and not slider.isHidden()


def test_resize_group(dialog):
    group = _items(dialog)[5]
    assert group is dialog._resize_grp  # noqa: SLF001
    assert group.isCheckable() and not group.isChecked()
    lay = group.layout()
    widgets = [lay.itemAt(i).widget() for i in range(lay.count())]
    assert [w.text() for w in widgets[::2]] == ["Max Width:", "Max Height:"]
    assert widgets[1] is dialog._max_w and widgets[3] is dialog._max_h  # noqa: SLF001
    for spin, value in ((dialog._max_w, 1920), (dialog._max_h, 1080)):  # noqa: SLF001
        assert (spin.minimum(), spin.maximum(), spin.value()) == (0, 99999, value)
        assert spin.specialValueText() == "--"


def test_watermark_group(dialog):
    group = _items(dialog)[6]
    assert group is dialog._wm_grp  # noqa: SLF001
    assert group.isCheckable() and not group.isChecked()
    text_row, opts_row = (group.layout().itemAt(i).layout() for i in range(2))
    label, edit = _row(text_row)
    assert label.text() == "Text:" and edit is dialog._wm_text  # noqa: SLF001
    assert edit.placeholderText() == "© Your name"
    pos_label, corner, op_label, opacity = _row(opts_row)
    assert (pos_label.text(), op_label.text()) == ("Position:", "Opacity:")
    assert corner is dialog._wm_corner and opacity is dialog._wm_opacity  # noqa: SLF001
    assert [corner.itemData(i) for i in range(corner.count())] == [
        "top-left", "top-right", "bottom-left", "bottom-right", "center"]
    assert corner.currentData() == "bottom-right"
    assert (opacity.minimum(), opacity.maximum(), opacity.value()) == (10, 100, 60)
    assert opts_row.stretch(3) == 1


def test_output_row(dialog, monkeypatch, tmp_path):
    row = _items(dialog)[7]
    edit, browse = _row(row)
    assert edit is dialog._dir_edit and edit.text() == str(tmp_path)  # noqa: SLF001
    assert browse.text() == "Browse..." and row.stretch(0) == 1
    picks = iter(["/out", ""])
    monkeypatch.setattr(mod.QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *_a, **_k: next(picks)))
    browse.click()
    browse.click()
    assert edit.text() == "/out"


def test_progress_and_buttons(dialog):
    bar = _items(dialog)[8]
    assert bar is dialog._progress and bar.isHidden()  # noqa: SLF001
    stretch, cancel, export = _row(_items(dialog)[10])
    assert stretch is None and cancel.text() == "Cancel"
    assert export is dialog._export_btn and export.text() == "Export"  # noqa: SLF001
    dialog.show()
    cancel.click()
    assert not dialog.isVisible()


def test_preset_fills_the_controls(dialog):
    preset = next(p for p in export_presets.builtin_presets() if p.max_width > 0)
    combo = dialog._preset_combo  # noqa: SLF001
    combo.setCurrentIndex(combo.findData(preset.key))
    assert dialog._fmt_combo.currentText() == preset.format  # noqa: SLF001
    assert dialog._quality_slider.value() == preset.quality  # noqa: SLF001
    assert dialog._resize_grp.isChecked()  # noqa: SLF001
    assert dialog._max_w.value() == preset.max_width  # noqa: SLF001


def test_empty_paths_leave_output_blank(qapp):
    dlg = BatchExportDialog(SimpleNamespace(main_window=None), [])
    try:
        assert dlg._dir_edit.text() == ""  # noqa: SLF001
        assert _items(dlg)[0].text() == "0 image(s) selected"
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# Export: which settings reach the worker.
# ---------------------------------------------------------------------------

def _cfg(worker):
    s = worker._settings  # noqa: SLF001
    return (s.fmt, s.quality, s.resize, s.max_w, s.max_h, s.square_crop, s.dpi, s.watermark)


@pytest.fixture
def export(dialog, tmp_path, monkeypatch):
    monkeypatch.setattr(mod._ExportWorker, "start", lambda self: None)  # noqa: SLF001

    def run():
        dialog._dir_edit.setText(str(tmp_path))  # noqa: SLF001
        dialog._do_export()  # noqa: SLF001
        return dialog._worker  # noqa: SLF001
    return run


def test_export_passes_the_manual_settings(dialog, export):
    dialog._fmt_combo.setCurrentText("JPEG")  # noqa: SLF001
    dialog._quality_slider.setValue(70)  # noqa: SLF001
    dialog._resize_grp.setChecked(True)  # noqa: SLF001
    dialog._max_w.setValue(800)  # noqa: SLF001
    dialog._max_h.setValue(600)  # noqa: SLF001
    worker = export()
    assert worker._paths == dialog._paths  # noqa: SLF001
    assert _cfg(worker) == ("JPEG", 70, True, 800, 600, False, 0, mod.WatermarkOptions())


def test_export_takes_crop_and_dpi_from_the_active_preset(dialog, export):
    preset = next(p for p in export_presets.builtin_presets() if p.square_crop or p.dpi)
    combo = dialog._preset_combo  # noqa: SLF001
    combo.setCurrentIndex(combo.findData(preset.key))
    cfg = _cfg(export())
    assert cfg[5:7] == (preset.square_crop, preset.dpi)
    assert cfg[0] == preset.format


def test_export_ignores_preset_extras_once_the_preset_is_cleared(dialog, export):
    preset = next(p for p in export_presets.builtin_presets() if p.square_crop or p.dpi)
    combo = dialog._preset_combo  # noqa: SLF001
    combo.setCurrentIndex(combo.findData(preset.key))
    combo.setCurrentIndex(combo.findData(None))
    assert _cfg(export())[5:7] == (False, 0)


# ---------------------------------------------------------------------------
# Worker: every setting is applied to the written file.
# ---------------------------------------------------------------------------

def _run_worker(tmp_path, settings, size=(200, 100)):
    from PIL import Image
    src = tmp_path / "src.png"
    Image.new("RGB", size, (200, 30, 30)).save(src)
    out = tmp_path / "out"
    out.mkdir()
    worker = mod._ExportWorker([str(src)], str(out), settings)  # noqa: SLF001
    results = []
    worker.result_ready.connect(lambda ok, bad: results.append((ok, bad)))
    worker.run()
    worker.deleteLater()
    (written,) = out.iterdir()
    return results, Image.open(written)


def test_worker_writes_the_format_unresized_by_default(qapp, tmp_path):
    results, img = _run_worker(tmp_path, mod.ExportSettings("JPEG", 80))
    assert results == [(1, 0)]
    assert (img.format, img.size) == ("JPEG", (200, 100))


def test_worker_resizes_within_the_limits(qapp, tmp_path):
    for name, resize, expected in (("on", True, (50, 25)), ("off", False, (200, 100))):
        folder = tmp_path / name
        folder.mkdir()
        _results, img = _run_worker(
            folder, mod.ExportSettings("PNG", 90, resize=resize, max_w=50))
        assert img.size == expected, name


def test_worker_square_crops_and_stamps_dpi(qapp, tmp_path):
    _results, img = _run_worker(tmp_path, mod.ExportSettings("PNG", 90, square_crop=True, dpi=300))
    assert img.size == (100, 100)
    assert tuple(round(v) for v in img.info["dpi"]) == (300, 300)
