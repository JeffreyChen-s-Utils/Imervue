"""Tests for the curves tone-mapping module."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.curves import (
    IDENTITY_POINTS,
    CurveOptions,
    _is_identity,
    _normalise_points,
    apply_curves,
    build_lut,
    compress_highlights_preset,
    lift_shadows_preset,
    s_curve_preset,
)


def _rgba(value=128, h=8, w=8):
    arr = np.full((h, w, 4), value, dtype=np.uint8)
    arr[..., 3] = 255
    return arr


def test_build_lut_identity():
    lut = build_lut(IDENTITY_POINTS)
    assert lut.shape == (256,)
    assert np.array_equal(lut, np.arange(256, dtype=np.uint8))


def test_build_lut_monotonic_for_s_curve():
    lut = build_lut(s_curve_preset(0.3))
    assert np.all(np.diff(lut.astype(int)) >= 0)
    assert lut[0] == 0 and lut[255] == 255


def test_build_lut_clamps_out_of_range_points():
    lut = build_lut([(-50, 300), (999, -10)])
    assert lut.min() >= 0 and lut.max() <= 255


def test_apply_curves_disabled_returns_input():
    img = _rgba()
    opts = CurveOptions(enabled=False)
    assert apply_curves(img, opts) is img


def test_apply_curves_identity_returns_input():
    img = _rgba()
    opts = CurveOptions(enabled=True)  # all identity
    assert apply_curves(img, opts) is img


def test_apply_curves_s_curve_increases_contrast():
    dark = _rgba(64)
    bright = _rgba(192)
    opts = CurveOptions(enabled=True)
    opts.per_channel["rgb"] = s_curve_preset(0.3)
    out_dark = apply_curves(dark, opts)
    out_bright = apply_curves(bright, opts)
    assert out_dark[0, 0, 0] < 64      # shadows pushed down
    assert out_bright[0, 0, 0] > 192   # highlights lifted
    assert np.all(out_dark[..., 3] == 255)


def test_apply_curves_per_channel_only_touches_that_channel():
    img = _rgba(100)
    opts = CurveOptions(enabled=True)
    opts.per_channel["r"] = ((0, 0), (255, 128))  # halve red
    out = apply_curves(img, opts)
    assert out[0, 0, 0] < 100
    assert out[0, 0, 1] == 100 and out[0, 0, 2] == 100


def test_apply_curves_bad_shape_raises():
    opts = CurveOptions(enabled=True)
    opts.per_channel["rgb"] = s_curve_preset(0.2)
    with pytest.raises(ValueError):
        apply_curves(np.zeros((8, 8, 3), dtype=np.uint8), opts)


def test_normalise_points_dedup_keeps_last():
    out = _normalise_points([(0, 0), (0, 255), (255, 255)])
    assert out == ((0, 255), (255, 255))


def test_normalise_points_pads_endpoints_and_sorts():
    out = _normalise_points([(200, 10), (50, 90)])
    assert out[0][0] == 0 and out[-1][0] == 255
    assert [p[0] for p in out] == sorted(p[0] for p in out)


def test_normalise_points_empty_is_identity():
    assert _normalise_points([]) == IDENTITY_POINTS
    assert _normalise_points("garbage") == IDENTITY_POINTS


def test_is_identity():
    assert _is_identity(IDENTITY_POINTS)
    assert not _is_identity(s_curve_preset(0.2))


def test_options_round_trip():
    opts = CurveOptions(enabled=True)
    opts.per_channel["rgb"] = s_curve_preset(0.25)
    restored = CurveOptions.from_dict(opts.to_dict())
    assert restored.enabled
    assert restored.per_channel["rgb"] == _normalise_points(opts.per_channel["rgb"])


def test_presets_are_clamped_and_bounded():
    for points in (s_curve_preset(9.9), lift_shadows_preset(9.9),
                   compress_highlights_preset(9.9)):
        for x, y in points:
            assert 0 <= x <= 255 and 0 <= y <= 255
