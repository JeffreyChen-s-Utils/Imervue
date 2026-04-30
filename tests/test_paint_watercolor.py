"""Tests for the wet-on-wet watercolor simulation."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.watercolor import (
    WetField,
    add_dab,
    composite_to_canvas,
    diffuse,
    evaporate,
)


def _white_canvas(h=20, w=20):
    return np.full((h, w, 4), 255, dtype=np.uint8)


# ---------------------------------------------------------------------------
# WetField construction
# ---------------------------------------------------------------------------


def test_wet_field_empty_starts_dry():
    field = WetField.empty((10, 10))
    assert field.water.sum() == 0
    assert field.pigment.sum() == 0


def test_wet_field_shape_property():
    field = WetField.empty((5, 8))
    assert field.shape == (5, 8)


def test_wet_field_water_dtype_float32():
    field = WetField.empty((4, 4))
    assert field.water.dtype == np.float32
    assert field.pigment.dtype == np.float32


# ---------------------------------------------------------------------------
# add_dab
# ---------------------------------------------------------------------------


def test_add_dab_deposits_water_at_centre():
    field = WetField.empty((10, 10))
    add_dab(field, 5, 5, radius=2, water=1.0, color=(255, 0, 0))
    assert field.water[5, 5] > 0


def test_add_dab_zero_radius_is_noop():
    field = WetField.empty((10, 10))
    add_dab(field, 5, 5, radius=0, water=1.0, color=(255, 0, 0))
    assert field.water.sum() == 0


def test_add_dab_zero_water_is_noop():
    field = WetField.empty((10, 10))
    add_dab(field, 5, 5, radius=2, water=0.0)
    assert field.water.sum() == 0


def test_add_dab_pigment_takes_color():
    field = WetField.empty((10, 10))
    add_dab(field, 5, 5, radius=2, water=1.0, color=(255, 0, 0))
    # Centre pigment should be red-biased.
    assert field.pigment[5, 5, 0] > 0
    assert field.pigment[5, 5, 1] == 0
    assert field.pigment[5, 5, 2] == 0


def test_add_dab_falloff_decays_with_distance():
    field = WetField.empty((20, 20))
    add_dab(field, 10, 10, radius=4, water=1.0, color=(0, 255, 0))
    centre = float(field.water[10, 10])
    far = float(field.water[10, 19])
    assert centre > far


def test_add_dab_accumulates_across_calls():
    field = WetField.empty((10, 10))
    add_dab(field, 5, 5, radius=2, water=1.0, color=(255, 0, 0))
    first_water = float(field.water[5, 5])
    add_dab(field, 5, 5, radius=2, water=1.0, color=(255, 0, 0))
    second_water = float(field.water[5, 5])
    assert second_water > first_water


# ---------------------------------------------------------------------------
# diffuse
# ---------------------------------------------------------------------------


def test_diffuse_spreads_water_to_neighbours():
    field = WetField.empty((10, 10))
    field.water[5, 5] = 1.0
    diffuse(field)
    # 4-connected neighbours should have water now.
    assert field.water[5, 4] > 0
    assert field.water[5, 6] > 0
    assert field.water[4, 5] > 0
    assert field.water[6, 5] > 0


def test_diffuse_zero_rate_is_noop():
    field = WetField.empty((10, 10))
    field.water[5, 5] = 1.0
    snapshot = field.water.copy()
    diffuse(field, rate=0.0)
    np.testing.assert_array_equal(field.water, snapshot)


def test_diffuse_clamps_oversized_rate():
    field = WetField.empty((10, 10))
    field.water[5, 5] = 1.0
    diffuse(field, rate=10.0)   # clamps to 0.25 (max stable rate)
    # At rate=0.25 the centre exactly drains into its 4 neighbours;
    # what matters is that water is conserved (no overshoot / NaN)
    # and the neighbours picked it up.
    assert field.water[5, 4] > 0
    total = float(field.water.sum())
    assert abs(total - 1.0) < 1e-3


def test_diffuse_pigment_only_moves_where_water_is():
    """Pigment shouldn't migrate to dry pixels (no water carrier)."""
    field = WetField.empty((10, 10))
    # Pigment without water at one location.
    field.pigment[5, 5] = (0.5, 0.0, 0.0)
    # No water anywhere.
    diffuse(field)
    # Pigment stays put (water_mask was zero everywhere).
    assert field.pigment[5, 4, 0] == 0


# ---------------------------------------------------------------------------
# evaporate
# ---------------------------------------------------------------------------


def test_evaporate_reduces_water_by_rate():
    field = WetField.empty((4, 4))
    field.water[...] = 2.0
    evaporate(field, rate=0.5)
    np.testing.assert_allclose(field.water, np.full((4, 4), 1.0, dtype=np.float32))


def test_evaporate_pigment_unchanged():
    field = WetField.empty((4, 4))
    field.water[...] = 1.0
    field.pigment[...] = (0.5, 0.5, 0.5)
    evaporate(field, rate=0.5)
    np.testing.assert_array_equal(
        field.pigment, np.full((4, 4, 3), 0.5, dtype=np.float32),
    )


def test_evaporate_zero_rate_is_noop():
    field = WetField.empty((4, 4))
    field.water[...] = 1.0
    snapshot = field.water.copy()
    evaporate(field, rate=0.0)
    np.testing.assert_array_equal(field.water, snapshot)


# ---------------------------------------------------------------------------
# composite_to_canvas
# ---------------------------------------------------------------------------


def test_composite_returns_false_for_empty_field():
    canvas = _white_canvas()
    field = WetField.empty(canvas.shape[:2])
    snapshot = canvas.copy()
    assert composite_to_canvas(canvas, field) is False
    np.testing.assert_array_equal(canvas, snapshot)


def test_composite_renders_red_pigment_onto_canvas():
    canvas = _white_canvas(h=10, w=10)
    field = WetField.empty(canvas.shape[:2])
    add_dab(field, 5, 5, radius=2, water=1.0, color=(255, 0, 0))
    composite_to_canvas(canvas, field)
    # Centre should pick up some red.
    assert canvas[5, 5, 0] > 200
    assert canvas[5, 5, 2] < 200


def test_composite_rejects_non_rgba_canvas():
    canvas = np.zeros((10, 10, 3), dtype=np.uint8)
    field = WetField.empty((10, 10))
    with pytest.raises(ValueError, match="HxWx4"):
        composite_to_canvas(canvas, field)


def test_composite_rejects_shape_mismatch():
    canvas = _white_canvas(h=10, w=10)
    field = WetField.empty((5, 5))
    with pytest.raises(ValueError, match="does not match"):
        composite_to_canvas(canvas, field)


# ---------------------------------------------------------------------------
# Lifecycle smoke test
# ---------------------------------------------------------------------------


def test_full_lifecycle_dab_diffuse_evaporate_composite():
    """Drop a wet pigment dab, run a couple of diffuse + evaporate
    steps, composite to canvas — should produce a soft blob with
    fading edges."""
    canvas = _white_canvas(h=20, w=20)
    field = WetField.empty(canvas.shape[:2])
    add_dab(field, 10, 10, radius=3, water=1.5, color=(255, 0, 0))
    for _ in range(3):
        diffuse(field, rate=0.2)
        evaporate(field, rate=0.1)
    composite_to_canvas(canvas, field)
    # Compare colour shift vs. pure white: at the centre the red
    # pigment pushes G + B way down, at a far edge the canvas is
    # essentially still white. The R channel itself can read low at
    # the centre because canvas-white blends with pigment-red — so
    # measure how far each pixel sits from neutral instead.
    centre_shift = (
        255 - int(canvas[10, 10, 1])    # green pulled down
        + 255 - int(canvas[10, 10, 2])  # blue pulled down
    )
    edge_shift = (
        255 - int(canvas[10, 18, 1])
        + 255 - int(canvas[10, 18, 2])
    )
    assert centre_shift > edge_shift
