"""Tests for pen-pressure response curves."""
from __future__ import annotations

import dataclasses

import pytest

from Imervue.paint.pressure_curve import (
    BUILT_IN_CURVES,
    HARD_FLOOR,
    IDENTITY,
    LIGHT_TOUCH,
    PressureCurve,
    SOFT_TAPER,
    apply_curve,
)


# ---------------------------------------------------------------------------
# PressureCurve construction
# ---------------------------------------------------------------------------


def test_default_curve_is_identity():
    c = PressureCurve()
    assert c.apply(0.0) == 0.0
    assert c.apply(0.5) == 0.5
    assert c.apply(1.0) == 1.0


def test_curve_is_frozen():
    c = PressureCurve()
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.points = ((0.0, 0.0), (1.0, 1.0))  # type: ignore[misc]


def test_curve_rejects_single_point():
    with pytest.raises(ValueError, match="2 points"):
        PressureCurve(points=((0.0, 0.0),))


def test_curve_rejects_out_of_range_value():
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        PressureCurve(points=((0.0, 0.0), (1.5, 1.0)))


def test_curve_rejects_unsorted_points():
    with pytest.raises(ValueError, match="non-decreasing"):
        PressureCurve(points=(
            (0.0, 0.0), (0.7, 0.3), (0.3, 0.7), (1.0, 1.0),
        ))


def test_curve_rejects_partial_coverage():
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        PressureCurve(points=((0.2, 0.0), (0.8, 1.0)))


# ---------------------------------------------------------------------------
# apply
# ---------------------------------------------------------------------------


def test_apply_clamps_negative_input():
    c = PressureCurve()
    assert c.apply(-0.5) == 0.0


def test_apply_clamps_above_one():
    c = PressureCurve()
    assert c.apply(2.0) == 1.0


def test_apply_interpolates_between_control_points():
    """A curve that maps 0.5 to 0.8 should interpolate halfway through
    each segment."""
    c = PressureCurve(points=((0.0, 0.0), (0.5, 0.8), (1.0, 1.0)))
    # Quarter input — halfway through first segment.
    assert abs(c.apply(0.25) - 0.4) < 1e-6
    # Three-quarter input — halfway through second segment.
    assert abs(c.apply(0.75) - 0.9) < 1e-6


def test_apply_at_control_point_exact():
    c = PressureCurve(points=((0.0, 0.0), (0.5, 0.8), (1.0, 1.0)))
    assert c.apply(0.0) == 0.0
    assert c.apply(0.5) == 0.8
    assert c.apply(1.0) == 1.0


def test_apply_curve_helper_handles_none():
    # apply_curve(None, p) should return p clamped.
    assert apply_curve(None, 0.5) == 0.5
    assert apply_curve(None, -1.0) == 0.0
    assert apply_curve(None, 2.0) == 1.0


def test_apply_curve_helper_uses_curve():
    c = PressureCurve(points=((0.0, 0.0), (0.5, 0.0), (1.0, 1.0)))
    # Below 0.5 → 0; above ramps up.
    assert apply_curve(c, 0.3) == 0.0


# ---------------------------------------------------------------------------
# Round-trip via dict
# ---------------------------------------------------------------------------


def test_round_trip_via_dict():
    c = PressureCurve(points=(
        (0.0, 0.0), (0.3, 0.1), (0.7, 0.6), (1.0, 1.0),
    ))
    rebuilt = PressureCurve.from_dict(c.to_dict())
    assert rebuilt == c


def test_from_dict_rejects_non_dict():
    with pytest.raises(ValueError, match="dict"):
        PressureCurve.from_dict("garbage")  # type: ignore[arg-type]


def test_from_dict_drops_corrupt_entries():
    rebuilt = PressureCurve.from_dict({
        "points": [
            [0.0, 0.0],
            "garbage",
            [0.5, 0.5],
            [99.0],   # too few elements
            [1.0, 1.0],
        ],
    })
    # Only the three valid points kept.
    positions = [pt[0] for pt in rebuilt.points]
    assert positions == [0.0, 0.5, 1.0]


def test_from_dict_pads_partial_coverage():
    """A persisted curve with no point at 0 or 1 is auto-padded so it
    satisfies the full-coverage invariant on reload."""
    rebuilt = PressureCurve.from_dict({
        "points": [[0.3, 0.4], [0.7, 0.6]],
    })
    assert rebuilt.points[0][0] == 0.0
    assert rebuilt.points[-1][0] == 1.0


def test_from_dict_empty_falls_back_to_identity():
    rebuilt = PressureCurve.from_dict({"points": []})
    assert rebuilt.points == ((0.0, 0.0), (1.0, 1.0))


# ---------------------------------------------------------------------------
# Built-in presets
# ---------------------------------------------------------------------------


def test_built_in_curves_unique_names():
    names = [name for name, _ in BUILT_IN_CURVES]
    assert len(set(names)) == len(names)


def test_built_in_curves_include_starter_set():
    names = {name for name, _ in BUILT_IN_CURVES}
    assert {"Identity", "Soft Taper", "Hard Floor", "Light Touch"} <= names


def test_soft_taper_softens_light_pressure():
    """A 0.2 input should map below 0.2 — soft taper crushes the
    bottom half of the range."""
    out = SOFT_TAPER.apply(0.2)
    assert out < 0.2


def test_hard_floor_lifts_zero_pressure():
    """Hard floor should produce a non-zero output even at p=0."""
    assert HARD_FLOOR.apply(0.0) > 0.3


def test_light_touch_caps_below_one():
    """Light touch attenuates the maximum response."""
    assert LIGHT_TOUCH.apply(1.0) < 1.0


def test_identity_constant_matches_default_apply():
    assert IDENTITY.apply(0.5) == 0.5
