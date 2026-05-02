"""Tests for the Gradient Map preset palette."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.adjustments import Adjustment, apply_adjustment
from Imervue.paint.gradient_map_presets import (
    GRADIENT_MAP_PRESETS,
    preset_ids,
    preset_stops,
)


# ---------------------------------------------------------------------------
# Preset palette structure
# ---------------------------------------------------------------------------


def test_grayscale_preset_is_first():
    """Identity-like grayscale preset must be the default first entry
    so a one-click without a preset choice still produces something
    sensible."""
    assert GRADIENT_MAP_PRESETS[0][0] == "grayscale"


def test_every_preset_has_at_least_two_stops():
    """A 1-stop gradient is degenerate — the LUT builder pads it to
    2-stop fallback. We never want that fallback to fire on a preset."""
    for entry in GRADIENT_MAP_PRESETS:
        stops = entry[3]
        assert len(stops) >= 2


def test_every_preset_has_unique_id():
    ids = [entry[0] for entry in GRADIENT_MAP_PRESETS]
    assert len(set(ids)) == len(ids)


def test_every_preset_stop_color_in_range():
    """Each colour component must be a valid 0..255 byte."""
    for entry in GRADIENT_MAP_PRESETS:
        for stop in entry[3]:
            for component in stop["color"]:
                assert 0 <= component <= 255


def test_every_preset_position_in_range():
    for entry in GRADIENT_MAP_PRESETS:
        for stop in entry[3]:
            assert 0.0 <= stop["position"] <= 1.0


def test_preset_ids_returns_canonical_order():
    assert preset_ids() == tuple(entry[0] for entry in GRADIENT_MAP_PRESETS)


# ---------------------------------------------------------------------------
# preset_stops
# ---------------------------------------------------------------------------


def test_preset_stops_for_known_id_returns_copy():
    a = preset_stops("grayscale")
    b = preset_stops("grayscale")
    assert a == b
    # Mutating one must not affect the other — confirms a deep copy.
    a[0]["color"][0] = 99
    assert b[0]["color"][0] == 0


def test_preset_stops_unknown_id_returns_none():
    assert preset_stops("not-a-preset") is None


# ---------------------------------------------------------------------------
# Integration with apply_adjustment
# ---------------------------------------------------------------------------


def test_grayscale_preset_leaves_grayscale_input_unchanged():
    """A grayscale image fed through the grayscale preset comes out
    visually identical (within rounding)."""
    img = np.zeros((4, 4, 4), dtype=np.uint8)
    img[..., 3] = 255
    img[..., :3] = 128   # mid-grey
    stops = preset_stops("grayscale")
    out = apply_adjustment(
        img, Adjustment(kind="gradient_map", params={"stops": stops}),
    )
    np.testing.assert_allclose(out[..., :3], img[..., :3], atol=2)


def test_sunset_preset_recolours_a_grayscale_input():
    """A grayscale ramp through Sunset must produce a non-grey output —
    catches a regression where the preset stops collapse to identity."""
    img = np.zeros((1, 4, 4), dtype=np.uint8)
    img[..., 3] = 255
    img[0, :, :3] = np.array([[0, 0, 0], [80, 80, 80], [170, 170, 170], [255, 255, 255]])
    stops = preset_stops("sunset")
    out = apply_adjustment(
        img, Adjustment(kind="gradient_map", params={"stops": stops}),
    )
    # Output is no longer monochrome — at least one row pixel has
    # unequal RGB components.
    assert any(
        out[0, x, 0] != out[0, x, 1] or out[0, x, 1] != out[0, x, 2]
        for x in range(4)
    )


@pytest.mark.parametrize("preset_id", [p[0] for p in GRADIENT_MAP_PRESETS])
def test_every_preset_round_trips_through_adjustment(preset_id):
    """Every preset must build a valid Adjustment that apply runs
    without raising."""
    img = np.full((2, 2, 4), 200, dtype=np.uint8)
    stops = preset_stops(preset_id)
    out = apply_adjustment(
        img, Adjustment(kind="gradient_map", params={"stops": stops}),
    )
    assert out.shape == img.shape
    assert out.dtype == np.uint8
