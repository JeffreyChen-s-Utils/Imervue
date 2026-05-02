"""Tests for selection refinement helpers."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import selection_ops as sops


# ---------------------------------------------------------------------------
# select_all / empty_selection
# ---------------------------------------------------------------------------


def test_select_all_has_all_true_pixels():
    mask = sops.select_all((10, 20))
    assert mask.shape == (10, 20)
    assert mask.dtype == np.bool_
    assert mask.all()


def test_empty_selection_has_no_true_pixels():
    mask = sops.empty_selection((10, 20))
    assert mask.shape == (10, 20)
    assert mask.dtype == np.bool_
    assert not mask.any()


def test_select_all_rejects_non_tuple():
    with pytest.raises(ValueError, match=r"\(h, w\) tuple"):
        sops.select_all([10, 20])  # type: ignore[arg-type]


def test_select_all_rejects_zero_dimension():
    with pytest.raises(ValueError, match="positive"):
        sops.select_all((0, 10))


def test_select_all_rejects_three_axes():
    with pytest.raises(ValueError, match=r"\(h, w\) tuple"):
        sops.select_all((10, 20, 4))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# invert
# ---------------------------------------------------------------------------


def test_invert_flips_every_pixel():
    base = np.array([[True, False], [False, True]])
    flipped = sops.invert(base)
    np.testing.assert_array_equal(flipped, np.array([[False, True], [True, False]]))


def test_invert_does_not_mutate_input():
    base = np.array([[True, False]])
    snapshot = base.copy()
    sops.invert(base)
    np.testing.assert_array_equal(base, snapshot)


def test_invert_double_returns_original():
    base = np.array([[True, False, True], [False, True, False]])
    np.testing.assert_array_equal(sops.invert(sops.invert(base)), base)


def test_invert_rejects_non_bool_mask():
    with pytest.raises(ValueError, match="bool"):
        sops.invert(np.zeros((4, 4), dtype=np.uint8))


def test_invert_rejects_3d_mask():
    with pytest.raises(ValueError, match="2-D"):
        sops.invert(np.zeros((4, 4, 4), dtype=np.bool_))


# ---------------------------------------------------------------------------
# expand
# ---------------------------------------------------------------------------


def _single_pixel_mask(h: int, w: int, y: int, x: int) -> np.ndarray:
    mask = np.zeros((h, w), dtype=np.bool_)
    mask[y, x] = True
    return mask


def test_expand_zero_returns_copy():
    base = _single_pixel_mask(5, 5, 2, 2)
    out = sops.expand(base, 0)
    np.testing.assert_array_equal(out, base)
    assert out is not base   # is a fresh copy


def test_expand_single_pixel_grows_to_plus():
    base = _single_pixel_mask(5, 5, 2, 2)
    out = sops.expand(base, 1)
    # Plus-shaped neighbourhood (4-connectivity).
    expected = np.zeros((5, 5), dtype=np.bool_)
    expected[2, 1] = expected[2, 3] = expected[1, 2] = expected[3, 2] = True
    expected[2, 2] = True
    np.testing.assert_array_equal(out, expected)


def test_expand_grows_pixel_count_monotonically():
    base = _single_pixel_mask(11, 11, 5, 5)
    sizes = [sops.expand(base, r).sum() for r in range(4)]
    assert sizes == sorted(sizes)


def test_expand_clips_at_canvas_edge():
    """Expansion past the edge does not raise nor wrap around."""
    base = _single_pixel_mask(5, 5, 0, 0)
    out = sops.expand(base, 3)
    # Every True pixel must lie within the canvas.
    assert out.shape == (5, 5)
    assert out.any()


def test_expand_rejects_negative_radius():
    base = sops.empty_selection((4, 4))
    with pytest.raises(ValueError, match=">= 0"):
        sops.expand(base, -1)


def test_expand_rejects_radius_above_cap():
    base = sops.empty_selection((4, 4))
    with pytest.raises(ValueError, match=str(sops.MAX_RADIUS)):
        sops.expand(base, sops.MAX_RADIUS + 1)


# ---------------------------------------------------------------------------
# contract
# ---------------------------------------------------------------------------


def test_contract_zero_returns_copy():
    base = sops.select_all((5, 5))
    out = sops.contract(base, 0)
    np.testing.assert_array_equal(out, base)


def test_contract_full_canvas_shrinks_inward():
    base = sops.select_all((5, 5))
    out = sops.contract(base, 1)
    # Border pixels are eroded.
    assert not out[0, :].any()
    assert not out[-1, :].any()
    assert not out[:, 0].any()
    assert not out[:, -1].any()
    # Interior remains.
    assert out[2, 2]


def test_contract_can_clear_a_thin_mask():
    base = np.zeros((7, 7), dtype=np.bool_)
    base[3, :] = True   # one-pixel-thick horizontal strip
    out = sops.contract(base, 1)
    assert not out.any()


def test_contract_inverse_of_expand_for_isolated_blob():
    base = np.zeros((11, 11), dtype=np.bool_)
    base[5, 5] = True
    expanded = sops.expand(base, 2)
    contracted = sops.contract(expanded, 2)
    # Round-trip recovers the single pixel (or close — a small-radius
    # erosion+dilation should bring it back to a single pixel).
    assert contracted[5, 5]
    assert contracted.sum() == 1


def test_contract_rejects_negative_radius():
    base = sops.empty_selection((4, 4))
    with pytest.raises(ValueError, match=">= 0"):
        sops.contract(base, -1)


# ---------------------------------------------------------------------------
# feather
# ---------------------------------------------------------------------------


def test_feather_returns_float32_in_unit_range():
    base = sops.select_all((10, 10))
    out = sops.feather(base, 2)
    assert out.dtype == np.float32
    assert out.min() >= 0.0
    assert out.max() <= 1.0


def test_feather_zero_radius_is_bool_to_float_cast():
    base = np.array([[True, False, True], [False, True, False]])
    out = sops.feather(base, 0)
    expected = base.astype(np.float32)
    np.testing.assert_array_equal(out, expected)


def test_feather_softens_step_edge():
    """A vertical step edge must produce intermediate alpha values
    in the transition band."""
    h = 9
    w = 9
    base = np.zeros((h, w), dtype=np.bool_)
    base[:, w // 2:] = True
    out = sops.feather(base, 2)
    # Far left = 0, far right = 1, middle column should be in between.
    assert out[h // 2, 0] == pytest.approx(0.0, abs=1e-3)
    assert out[h // 2, -1] == pytest.approx(1.0, abs=1e-3)
    middle = out[h // 2, w // 2]
    assert 0.1 < middle < 0.9


def test_feather_does_not_mutate_input():
    base = np.array([[True, False, True], [False, True, False]])
    snapshot = base.copy()
    sops.feather(base, 2)
    np.testing.assert_array_equal(base, snapshot)


def test_feather_rejects_negative_radius():
    base = sops.empty_selection((4, 4))
    with pytest.raises(ValueError, match=">= 0"):
        sops.feather(base, -1)


# ---------------------------------------------------------------------------
# from_layer_alpha
# ---------------------------------------------------------------------------


def test_from_layer_alpha_default_threshold_selects_any_opacity():
    img = np.zeros((4, 4, 4), dtype=np.uint8)
    img[1, 2, 3] = 1   # tiniest opacity
    img[2, 1, 3] = 255
    mask = sops.from_layer_alpha(img)
    assert mask[1, 2]
    assert mask[2, 1]
    assert not mask[0, 0]


def test_from_layer_alpha_threshold_filters_semi_transparent():
    img = np.zeros((1, 4, 4), dtype=np.uint8)
    img[0, 0, 3] = 50
    img[0, 1, 3] = 127   # exactly at threshold — strictly-greater check excludes it
    img[0, 2, 3] = 200
    mask = sops.from_layer_alpha(img, threshold=127)
    np.testing.assert_array_equal(mask[0], [False, False, True, False])


def test_from_layer_alpha_rejects_rgb_only():
    rgb = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="HxWx4"):
        sops.from_layer_alpha(rgb)


def test_from_layer_alpha_rejects_threshold_above_255():
    img = np.zeros((2, 2, 4), dtype=np.uint8)
    with pytest.raises(ValueError, match=r"\[0, 255\]"):
        sops.from_layer_alpha(img, threshold=256)


def test_from_layer_alpha_rejects_negative_threshold():
    img = np.zeros((2, 2, 4), dtype=np.uint8)
    with pytest.raises(ValueError, match=r"\[0, 255\]"):
        sops.from_layer_alpha(img, threshold=-1)
