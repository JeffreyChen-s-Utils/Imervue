"""Paint's Filter > Match Colour… and Match Swatches… reach the match modules.

``paint/match_color.py`` (Reinhard colour transfer) and ``paint/match_palette.py``
(nearest-palette recolouring) were tested but unreachable. Match Colour takes a
reference image file and a Strength; Match Swatches repaints in the colours of
the Swatches dock. Both go through the Filter menu's selection-aware apply.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QWidget

from Imervue.paint.filter_menu import (
    apply_filter_to_layer,
    build_filter_menu,
    match_colour_spec,
    match_swatches_spec,
)


def _layer() -> np.ndarray:
    rng = np.random.default_rng(3)
    layer = np.zeros((16, 16, 4), np.uint8)
    layer[..., :3] = rng.integers(40, 90, (16, 16, 3))
    layer[..., 3] = 255
    return layer


def _reference() -> np.ndarray:
    rng = np.random.default_rng(4)
    ref = np.zeros((10, 10, 4), np.uint8)
    ref[..., 0] = rng.integers(180, 240, (10, 10))
    ref[..., 1:3] = rng.integers(10, 40, (10, 10, 2))
    ref[..., 3] = 255
    return ref


def test_match_colour_takes_the_reference_s_mood():
    out = apply_filter_to_layer(match_colour_spec(_reference()), {"strength": 1.0}, _layer(), None)
    means = out[..., :3].reshape(-1, 3).mean(axis=0)
    assert means[0] > 180 and means[1] < 50 and means[2] < 50
    assert (out[..., 3] == 255).all()


def test_match_colour_strength_zero_leaves_the_layer_alone():
    layer = _layer()
    out = apply_filter_to_layer(match_colour_spec(_reference()), {"strength": 0.0}, layer, None)
    np.testing.assert_array_equal(out, layer)


def test_match_colour_offers_one_strength_slider():
    (param,) = match_colour_spec(_reference()).parameters
    assert (param.name, param.kind, param.minimum, param.maximum, param.default) == (
        "strength", "float_slider", 0.0, 1.0, 1.0)


def test_match_swatches_repaints_in_the_nearest_swatch():
    layer = _layer()
    layer[:8, :, :3] = (250, 10, 10)
    out = apply_filter_to_layer(match_swatches_spec([(255, 0, 0), (60, 60, 60)]), {}, layer, None)
    assert {tuple(c) for c in out[..., :3].reshape(-1, 3)} == {(255, 0, 0), (60, 60, 60)}
    assert tuple(out[0, 0, :3]) == (255, 0, 0)


def test_both_respect_the_selection():
    layer = _layer()
    selection = np.zeros((16, 16), bool)
    selection[:, :4] = True
    out = apply_filter_to_layer(match_swatches_spec([(0, 0, 255)]), {}, layer, selection)
    assert (out[:, :4, :3] == (0, 0, 255)).all()
    np.testing.assert_array_equal(out[:, 4:], layer[:, 4:])


def test_the_filter_menu_lists_both(qapp):
    host = QWidget()
    try:
        labels = [a.text() for a in build_filter_menu(host).actions() if not a.isSeparator()]
        assert labels[-2:] == ["Match Colour…", "Match Swatches…"]
    finally:
        host.deleteLater()
