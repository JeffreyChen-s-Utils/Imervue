"""Paint's single-slider filters open the live-preview dialog.

``paint/filter_preview_dialog.py`` was tested but unreachable. Filter menu
entries with exactly one slider now preview live on a full-resolution crop of
the layer; the others keep the parameter form.
"""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.filter_menu import (
    FILTER_SPECS,
    ParamSpec,
    match_colour_spec,
    preview_params,
    single_slider,
    slider_steps,
)
from Imervue.paint.filter_preview_dialog import FilterPreviewDialog, preview_crop


def _spec(key: str):
    return next(s for s in FILTER_SPECS if s.key == key)


@pytest.mark.parametrize(("key", "live"), [
    ("posterize", True), ("threshold", True), ("halftone", True),
    ("levels", False), ("curves", False), ("auto_balance", False), ("film_grain", False),
])
def test_only_single_slider_filters_preview_live(key, live):
    assert (single_slider(_spec(key)) is not None) is live


def test_match_colour_previews_live_too():
    assert single_slider(match_colour_spec(np.zeros((2, 2, 4), np.uint8))).name == "strength"


def test_slider_steps_follow_the_parameter():
    assert slider_steps(ParamSpec("n", "k", "N", "int_slider", 2, 64, 4)) == 1
    assert slider_steps(ParamSpec("s", "k", "S", "float_slider", 0.0, 1.0, 1.0, step=0.05)) == 20


def test_preview_params_round_whole_numbers():
    whole = ParamSpec("levels", "k", "L", "int_slider", 2, 64, 4)
    part = ParamSpec("strength", "k", "S", "float_slider", 0.0, 1.0, 1.0, step=0.05)
    assert preview_params(whole, 6.9999) == {"levels": 7}
    assert preview_params(part, 0.35) == {"strength": pytest.approx(0.35)}


def test_the_crop_is_the_middle_at_full_resolution():
    image = np.zeros((1000, 800, 4), np.uint8)
    image[500, 400] = 255
    crop = preview_crop(image, 100)
    assert crop.shape == (100, 100, 4)
    assert crop[50, 50, 0] == 255
    small = np.zeros((40, 30, 4), np.uint8)
    assert preview_crop(small, 100).shape == (40, 30, 4)


def test_the_dialog_takes_the_filter_name_and_the_parameter_label(qapp):
    seen = []
    dialog = FilterPreviewDialog(
        np.zeros((8, 8, 4), np.uint8), lambda img, v: seen.append(v) or img,
        slider_min=2, slider_max=64, slider_default=4,
        title_key="no_such_key", title_fallback="Posterize…", value_label="Levels per channel",
    )
    try:
        assert dialog.windowTitle() == "Posterize…"
        labels = [w.text() for w in dialog.findChildren(type(dialog._value_label))]
        assert "Levels per channel" in labels
        assert seen == [4.0]
        assert dialog.slider_value() == 4.0
    finally:
        dialog.deleteLater()
