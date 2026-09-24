"""Characterisation tests for ``SlideshowMp4Dialog``'s layout and wiring.

Pins the source label, every settings row (label, range, default, step,
suffix, tooltip) and the Export / Close row, so splitting the constructor
cannot drop, reorder or rewire a control.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QDoubleSpinBox, QFormLayout, QSpinBox

from Imervue.gui import slideshow_mp4_dialog as mod
from Imervue.gui.slideshow_mp4_dialog import SlideshowMp4Dialog

# attribute, label, type, (min, max), default, step, suffix, tooltip
_ROWS = [
    ("_width_spin", "Width", QSpinBox, (160, 7680), 1920, 1, "",
     "Output video width in pixels (default 1920 = HD)"),
    ("_height_spin", "Height", QSpinBox, (120, 4320), 1080, 1, "",
     "Output video height in pixels (default 1080 = HD)"),
    ("_fps_spin", "FPS", QSpinBox, (10, 60), 24, 1, "",
     "Frames per second — 24 is cinematic, 30 / 60 are common for screen playback"),
    ("_hold_spin", "Hold per image", QDoubleSpinBox, (0.2, 30.0), 3.0, 0.1, " s",
     "Seconds each image stays on-screen before the fade"),
    ("_fade_spin", "Fade duration", QDoubleSpinBox, (0.0, 5.0), 0.5, 0.1, " s",
     "Cross-fade duration between consecutive images. Set to 0 for hard cuts."),
    ("_quality_spin", "Quality", QSpinBox, (1, 10), 8, 1, "",
     "Encoder quality (1 worst / smallest, 10 best / largest)"),
]


@pytest.fixture(autouse=True)
def _english(monkeypatch):
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", {})


@pytest.fixture
def dialog(qapp):
    dlg = SlideshowMp4Dialog(None)
    yield dlg
    dlg.deleteLater()


def _items(layout):
    return [layout.itemAt(i).widget() or layout.itemAt(i).layout() for i in range(layout.count())]


def test_top_level_order_and_title(dialog):
    label, form, buttons = _items(dialog.layout())
    assert label.text() == "0 image(s) will be rendered."
    assert isinstance(form, QFormLayout)
    assert type(buttons).__name__ == "QHBoxLayout"
    assert dialog.windowTitle() == "Slideshow Video"
    assert (dialog.minimumWidth(), dialog.minimumHeight()) == (440, 320)


def test_settings_rows(dialog):
    form = _items(dialog.layout())[1]
    assert form.rowCount() == len(_ROWS)
    for row, (attr, label, kind, (lo, hi), default, step, suffix, tip) in enumerate(_ROWS):
        field = form.itemAt(row, QFormLayout.ItemRole.FieldRole).widget()
        assert form.itemAt(row, QFormLayout.ItemRole.LabelRole).widget().text() == label
        assert field is getattr(dialog, attr) and type(field) is kind, attr
        assert (field.minimum(), field.maximum()) == (pytest.approx(lo), pytest.approx(hi))
        assert field.value() == pytest.approx(default)
        assert field.singleStep() == pytest.approx(step)
        assert field.suffix() == suffix
        assert field.toolTip() == tip


def test_button_row(qapp, monkeypatch):
    calls = []
    monkeypatch.setattr(SlideshowMp4Dialog, "_export", lambda self, images: calls.append(images))
    monkeypatch.setattr(SlideshowMp4Dialog, "_resolve_images", lambda self: ["a.png", "b.png"])
    dlg = SlideshowMp4Dialog(None)
    try:
        label, _form, row = _items(dlg.layout())
        assert label.text() == "2 image(s) will be rendered."
        stretch, export, close = _items(row)
        assert stretch is None
        assert export is dlg._export_btn and export.text() == "Export MP4…"  # noqa: SLF001
        assert close.text() == "Close"
        export.click()
        assert calls == [["a.png", "b.png"]]
        dlg.show()
        close.click()
        assert not dlg.isVisible()
    finally:
        dlg.deleteLater()


def test_resolve_images_prefers_the_selection(qapp):
    viewer = SimpleNamespace(selected_tiles={"s.png"}, model=SimpleNamespace(images=["a.png"]))
    dlg = SlideshowMp4Dialog(None)
    try:
        dlg.ui = SimpleNamespace(viewer=viewer)
        assert dlg._resolve_images() == ["s.png"]  # noqa: SLF001
        viewer.selected_tiles = set()
        assert dlg._resolve_images() == ["a.png"]  # noqa: SLF001
    finally:
        dlg.deleteLater()
