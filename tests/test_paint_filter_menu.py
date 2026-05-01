"""Tests for the Paint workspace's Filter menu and apply helpers."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.filter_menu import (
    FILTER_SPECS,
    FilterSpec,
    apply_filter_to_layer,
)


@pytest.fixture
def gray_canvas():
    """24x24 mid-grey canvas — wide tonal range so filters produce changes."""
    arr = np.full((24, 24, 4), 128, dtype=np.uint8)
    arr[..., 3] = 255
    arr[8:16, 8:16, :3] = 200    # bright square
    arr[0:4, 0:4, :3] = 30       # dark corner
    return arr


# ---------------------------------------------------------------------------
# FILTER_SPECS sanity
# ---------------------------------------------------------------------------


def test_filter_specs_have_unique_keys():
    keys = [spec.key for spec in FILTER_SPECS]
    assert len(keys) == len(set(keys))


def test_filter_specs_are_well_formed():
    for spec in FILTER_SPECS:
        assert spec.key
        assert spec.label_key
        assert callable(spec.apply_fn)
        for param in spec.parameters:
            assert param.name
            assert param.kind in (
                "int_slider", "float_slider", "bool", "choice",
            )
            if param.kind == "choice":
                assert param.choices, f"{spec.key}.{param.name} has no choices"


# ---------------------------------------------------------------------------
# apply_filter_to_layer
# ---------------------------------------------------------------------------


def _spec_by_key(key: str) -> FilterSpec:
    for spec in FILTER_SPECS:
        if spec.key == key:
            return spec
    raise KeyError(key)


def test_apply_filter_levels_changes_pixels(gray_canvas):
    spec = _spec_by_key("levels")
    out = apply_filter_to_layer(
        spec, {"black": 50, "white": 200, "gamma": 0.5},
        gray_canvas, selection=None,
    )
    assert out.shape == gray_canvas.shape
    assert out.dtype == np.uint8
    # Levels with non-identity params must change at least some pixels.
    assert not np.array_equal(out, gray_canvas)


def test_apply_filter_posterize_quantises(gray_canvas):
    spec = _spec_by_key("posterize")
    out = apply_filter_to_layer(
        spec, {"levels": 4}, gray_canvas, selection=None,
    )
    # 4-level quantisation: per-channel unique values ≤ 4.
    for c in range(3):
        assert len(np.unique(out[..., c])) <= 4


def test_apply_filter_threshold_yields_two_values_per_channel(gray_canvas):
    spec = _spec_by_key("threshold")
    out = apply_filter_to_layer(
        spec, {"level": 128}, gray_canvas, selection=None,
    )
    for c in range(3):
        unique = set(np.unique(out[..., c]).tolist())
        assert unique <= {0, 255}


def test_apply_filter_auto_balance_runs_each_method(gray_canvas):
    spec = _spec_by_key("auto_balance")
    for method in ("gray_world", "white_patch", "percentile_stretch", "simplified_retinex"):
        out = apply_filter_to_layer(
            spec, {"method": method, "intensity": 1.0},
            gray_canvas, selection=None,
        )
        assert out.shape == gray_canvas.shape
        assert out.dtype == np.uint8


def test_apply_filter_film_grain_changes_pixels(gray_canvas):
    spec = _spec_by_key("film_grain")
    out = apply_filter_to_layer(
        spec, {"intensity": 0.8, "size": 1}, gray_canvas, selection=None,
    )
    assert not np.array_equal(out, gray_canvas)


def test_apply_filter_halftone_produces_dot_pattern(gray_canvas):
    """The halftone filter must replace soft greys with a sparse dot
    pattern — so the output's alpha channel is no longer constant."""
    spec = _spec_by_key("halftone")
    out = apply_filter_to_layer(
        spec, {"lpi": 60}, gray_canvas, selection=None,
    )
    assert out.shape == gray_canvas.shape
    assert out.dtype == np.uint8
    # The dot pattern should produce variation in alpha across the
    # image; a flat fill would have a single alpha value.
    assert len(np.unique(out[..., 3])) > 1


# ---------------------------------------------------------------------------
# Selection clipping
# ---------------------------------------------------------------------------


def test_apply_filter_respects_selection(gray_canvas):
    spec = _spec_by_key("threshold")
    sel = np.zeros(gray_canvas.shape[:2], dtype=np.bool_)
    sel[8:16, 8:16] = True   # only the bright inner square
    out = apply_filter_to_layer(
        spec, {"level": 128}, gray_canvas, selection=sel,
    )
    # Inside the selection: pixels were thresholded.
    inside_unique = set(np.unique(out[8:16, 8:16, 0]).tolist())
    assert inside_unique <= {0, 255}
    # Outside: unchanged.
    np.testing.assert_array_equal(out[0:4, 0:4], gray_canvas[0:4, 0:4])


def test_apply_filter_rejects_selection_shape_mismatch(gray_canvas):
    spec = _spec_by_key("threshold")
    bad_sel = np.zeros((5, 5), dtype=np.bool_)
    with pytest.raises(ValueError):
        apply_filter_to_layer(
            spec, {"level": 128}, gray_canvas, selection=bad_sel,
        )


def test_apply_filter_rejects_non_rgba(sample_rgb_array):
    spec = _spec_by_key("levels")
    with pytest.raises(ValueError):
        apply_filter_to_layer(
            spec, {"black": 0, "white": 255, "gamma": 1.0},
            sample_rgb_array, selection=None,
        )


# ---------------------------------------------------------------------------
# Custom-spec round-trip — confirms the apply_fn → mask path is generic
# ---------------------------------------------------------------------------


def test_apply_filter_custom_spec(gray_canvas):
    """A toy filter that inverts RGB — checked end-to-end through
    apply_filter_to_layer."""
    def invert(arr, _params):
        out = arr.copy()
        out[..., :3] = 255 - out[..., :3]
        return out

    spec = FilterSpec(
        key="invert", label_key="x", label_fallback="x",
        parameters=(),
        apply_fn=invert,
    )
    out = apply_filter_to_layer(spec, {}, gray_canvas, selection=None)
    np.testing.assert_array_equal(out[..., :3], 255 - gray_canvas[..., :3])
    # Alpha untouched by the toy filter.
    np.testing.assert_array_equal(out[..., 3], gray_canvas[..., 3])


def test_apply_filter_rejects_filter_returning_wrong_dtype(gray_canvas):
    def broken(arr, _params):
        return arr.astype(np.float32)

    spec = FilterSpec(
        key="broken", label_key="x", label_fallback="x",
        parameters=(), apply_fn=broken,
    )
    with pytest.raises(ValueError):
        apply_filter_to_layer(spec, {}, gray_canvas, selection=None)


def test_apply_filter_rejects_filter_returning_wrong_shape(gray_canvas):
    def broken(arr, _params):
        return arr[:, :10]

    spec = FilterSpec(
        key="broken", label_key="x", label_fallback="x",
        parameters=(), apply_fn=broken,
    )
    with pytest.raises(ValueError):
        apply_filter_to_layer(spec, {}, gray_canvas, selection=None)


# ---------------------------------------------------------------------------
# Param spec coverage — every filter has at least one parameter
# ---------------------------------------------------------------------------


def test_each_builtin_filter_has_at_least_one_parameter():
    for spec in FILTER_SPECS:
        assert spec.parameters, f"filter {spec.key!r} has no parameters"


def test_param_spec_covers_documented_kinds():
    kinds_seen = {p.kind for spec in FILTER_SPECS for p in spec.parameters}
    # Every kind we register appears in at least one filter.
    for kind in kinds_seen:
        assert kind in ("int_slider", "float_slider", "bool", "choice")
