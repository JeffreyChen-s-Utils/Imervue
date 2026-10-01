"""Paint's File > New Canvas… sizes a new tab from the presets or by hand.

``paint/canvas_presets.py`` (paper, manga and screen sizes, plus your own,
persisted) was tested but unreachable: New Tab always made a 1024 px canvas.
"""
from __future__ import annotations

import pytest

from Imervue.paint.canvas_presets import BUILT_IN_PRESETS, CanvasPreset, load_custom_presets, save_custom_presets
from Imervue.paint.new_canvas_dialog import TRANSPARENT, WHITE, NewCanvasDialog, preset_choices
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean():
    user_setting_dict.pop("paint_canvas_presets", None)
    yield
    user_setting_dict.pop("paint_canvas_presets", None)


@pytest.fixture
def dialog(qapp):
    widget = NewCanvasDialog(None)
    yield widget
    widget.deleteLater()


def _select(dialog: NewCanvasDialog, name: str) -> None:
    box = dialog._preset_box
    box.setCurrentIndex(next(i for i in range(box.count()) if box.itemText(i).startswith(name)))


def test_it_opens_on_the_default_size_custom_and_white(dialog):
    assert dialog._preset_box.currentIndex() == 0
    assert dialog.values() == (1024, 1024, WHITE)


def test_every_preset_is_offered_after_custom(dialog):
    assert dialog._preset_box.count() == 1 + len(BUILT_IN_PRESETS)
    assert dialog._preset_box.itemText(1) == "A4 Portrait (300dpi) — 2480 × 3508 px"


def test_a_preset_fills_in_its_size(dialog):
    _select(dialog, "HD 1080p")
    assert dialog.values()[:2] == (1920, 1080)


def test_typing_a_size_switches_back_to_custom(dialog):
    _select(dialog, "4K UHD")
    dialog._width.setValue(3000)
    assert dialog._preset_box.currentIndex() == 0
    assert dialog.values()[:2] == (3000, 2160)


def test_a_transparent_background(dialog):
    dialog._background.setCurrentIndex(1)
    assert dialog.values()[2] == TRANSPARENT


def test_saving_the_size_as_your_preset(dialog):
    dialog._width.setValue(800)
    dialog._height.setValue(600)
    assert dialog.save_preset("  Banner ") is True
    assert load_custom_presets() == [CanvasPreset("Banner", 800, 600)]
    assert dialog._preset_box.currentText() == "Banner — 800 × 600 px"


@pytest.mark.parametrize("name", ["", "  ", "HD 1080p"])
def test_an_empty_or_taken_preset_name_is_refused(dialog, name):
    assert dialog.save_preset(name) is False
    assert load_custom_presets() == []


def test_your_presets_follow_the_built_in_ones(qapp):
    save_custom_presets([CanvasPreset("Mine", 640, 480)])
    assert preset_choices()[-1].name == "Mine"
    widget = NewCanvasDialog(None)
    try:
        _select(widget, "Mine")
        assert widget.values()[:2] == (640, 480)
    finally:
        widget.deleteLater()
