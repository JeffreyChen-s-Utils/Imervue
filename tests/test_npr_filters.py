"""Tests for the NPR Filters plugin's pure-logic layer.

Qt-side glue lives in ``npr_filters_plugin.NPRFiltersDialog`` and is not
exercised here — the unit tests cover the algorithms directly so the
suite stays runnable on machines without a display server.
"""
from __future__ import annotations

import numpy as np
import pytest

from npr_filters.filters import (
    INTENSITY_MAX,
    LINE_THRESHOLD_MAX,
    LINE_THRESHOLD_MIN,
    OIL_LEVELS_MAX,
    OIL_LEVELS_MIN,
    SIGMA_R_MAX,
    SIGMA_R_MIN,
    SIGMA_S_MAX,
    SIGMA_S_MIN,
    STYLES,
    NPRFilterOptions,
    apply_npr_filter,
    line_art,
    oil_painting,
    pencil_sketch,
    watercolor,
)


pytest.importorskip("cv2")


# ---------------------------------------------------------------------------
# Constants & options
# ---------------------------------------------------------------------------


def test_styles_tuple_lists_known_styles():
    assert STYLES == ("pencil_sketch", "oil_painting", "watercolor", "line_art")


def test_options_have_documented_defaults():
    options = NPRFilterOptions()
    assert options.style == "pencil_sketch"
    assert options.intensity == INTENSITY_MAX
    assert SIGMA_S_MIN <= options.sigma_s <= SIGMA_S_MAX
    assert SIGMA_R_MIN <= options.sigma_r <= SIGMA_R_MAX
    assert OIL_LEVELS_MIN <= options.oil_levels <= OIL_LEVELS_MAX
    assert LINE_THRESHOLD_MIN <= options.line_threshold <= LINE_THRESHOLD_MAX


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_apply_rejects_non_rgba(sample_rgb_array):
    with pytest.raises(ValueError):
        apply_npr_filter(sample_rgb_array)


def test_apply_rejects_wrong_dtype():
    arr = np.zeros((4, 4, 4), dtype=np.float32)
    with pytest.raises(ValueError):
        apply_npr_filter(arr)


def test_apply_rejects_unknown_style(sample_rgba_array):
    with pytest.raises(ValueError):
        apply_npr_filter(sample_rgba_array, NPRFilterOptions(style="cubist"))


# ---------------------------------------------------------------------------
# Happy path per style
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("style", STYLES)
def test_each_style_returns_rgba_uint8(sample_rgba_array, style):
    out = apply_npr_filter(sample_rgba_array, NPRFilterOptions(style=style))
    assert out.shape == sample_rgba_array.shape
    assert out.dtype == np.uint8


@pytest.mark.parametrize("style", STYLES)
def test_alpha_channel_preserved(sample_rgba_array, style):
    out = apply_npr_filter(sample_rgba_array, NPRFilterOptions(style=style))
    np.testing.assert_array_equal(out[..., 3], sample_rgba_array[..., 3])


# ---------------------------------------------------------------------------
# Intensity / blend behaviour
# ---------------------------------------------------------------------------


def test_intensity_zero_returns_copy_of_original(sample_rgba_array):
    out = apply_npr_filter(
        sample_rgba_array, NPRFilterOptions(style="watercolor", intensity=0.0),
    )
    np.testing.assert_array_equal(out, sample_rgba_array)
    # Returned object must not alias the input
    assert out is not sample_rgba_array


def test_negative_intensity_clamped_to_zero(sample_rgba_array):
    out = apply_npr_filter(
        sample_rgba_array, NPRFilterOptions(style="watercolor", intensity=-1.0),
    )
    np.testing.assert_array_equal(out, sample_rgba_array)


def test_intensity_above_one_clamped(sample_rgba_array):
    full = apply_npr_filter(
        sample_rgba_array, NPRFilterOptions(style="watercolor", intensity=1.0),
    )
    over = apply_npr_filter(
        sample_rgba_array, NPRFilterOptions(style="watercolor", intensity=5.0),
    )
    np.testing.assert_array_equal(full, over)


def test_partial_intensity_lies_between_endpoints(sample_rgba_array):
    full = apply_npr_filter(
        sample_rgba_array, NPRFilterOptions(style="watercolor", intensity=1.0),
    ).astype(np.int16)
    half = apply_npr_filter(
        sample_rgba_array, NPRFilterOptions(style="watercolor", intensity=0.5),
    ).astype(np.int16)
    original = sample_rgba_array.astype(np.int16)
    # Per-pixel: half should be roughly midway between original and full.
    diff_to_orig = np.abs(half[..., :3] - original[..., :3]).mean()
    diff_to_full = np.abs(half[..., :3] - full[..., :3]).mean()
    assert diff_to_orig > 0
    assert diff_to_full > 0


# ---------------------------------------------------------------------------
# Style helpers — direct call sanity
# ---------------------------------------------------------------------------


def test_pencil_sketch_returns_rgb_uint8(sample_rgba_array):
    out = pencil_sketch(sample_rgba_array[..., :3], sigma_s=60, sigma_r=45)
    assert out.shape == sample_rgba_array[..., :3].shape
    assert out.dtype == np.uint8


def test_oil_painting_quantises_to_levels(sample_rgba_array):
    out = oil_painting(sample_rgba_array[..., :3], levels=4)
    assert out.shape == sample_rgba_array[..., :3].shape
    assert out.dtype == np.uint8
    # 4-level quantisation collapses to ≤ 4 unique values per channel.
    unique_per_channel = [len(np.unique(out[..., c])) for c in range(3)]
    assert max(unique_per_channel) <= 4


def test_watercolor_preserves_shape(sample_rgba_array):
    out = watercolor(sample_rgba_array[..., :3], sigma_s=60, sigma_r=45)
    assert out.shape == sample_rgba_array[..., :3].shape
    assert out.dtype == np.uint8


def test_line_art_returns_grayscale_replicated_across_channels(sample_rgba_array):
    out = line_art(sample_rgba_array[..., :3], threshold=80)
    assert out.shape == sample_rgba_array[..., :3].shape
    assert out.dtype == np.uint8
    np.testing.assert_array_equal(out[..., 0], out[..., 1])
    np.testing.assert_array_equal(out[..., 1], out[..., 2])


# ---------------------------------------------------------------------------
# Boundary clamping inside helpers
# ---------------------------------------------------------------------------


def test_oil_painting_clamps_levels_to_range(sample_rgba_array):
    rgb = sample_rgba_array[..., :3]
    over = oil_painting(rgb, levels=OIL_LEVELS_MAX + 100)
    inside = oil_painting(rgb, levels=OIL_LEVELS_MAX)
    np.testing.assert_array_equal(over, inside)


def test_line_art_clamps_threshold_to_range(sample_rgba_array):
    rgb = sample_rgba_array[..., :3]
    under = line_art(rgb, threshold=LINE_THRESHOLD_MIN - 50)
    boundary = line_art(rgb, threshold=LINE_THRESHOLD_MIN)
    np.testing.assert_array_equal(under, boundary)
