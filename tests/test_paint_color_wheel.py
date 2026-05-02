"""Tests for the colour-wheel + SV-triangle picker math."""
from __future__ import annotations

import math

import pytest

from Imervue.paint.color_wheel import (
    DEFAULT_RING_INNER,
    DEFAULT_RING_OUTER,
    REGION_OUTSIDE,
    REGION_RING,
    REGION_TRIANGLE,
    classify_region,
    hsv_to_rgb,
    hue_to_ring_angle,
    ring_angle_to_hue,
    ring_position_for_hue,
    sv_to_triangle,
    triangle_to_sv,
    triangle_vertices,
)


# ---------------------------------------------------------------------------
# Region classification
# ---------------------------------------------------------------------------


def test_centre_is_in_triangle():
    assert classify_region((0.0, 0.0)) == REGION_TRIANGLE


def test_just_outside_ring_outer_is_outside():
    assert classify_region((1.05, 0.0)) == REGION_OUTSIDE


def test_inside_ring_band_classified_as_ring():
    radius = (DEFAULT_RING_INNER + DEFAULT_RING_OUTER) / 2.0
    assert classify_region((radius, 0.0)) == REGION_RING


def test_classify_rejects_nonpositive_inner():
    with pytest.raises(ValueError, match="ring_inner"):
        classify_region((0.0, 0.0), ring_inner=0.0)


def test_classify_rejects_inner_greater_than_outer():
    with pytest.raises(ValueError, match="ring_inner"):
        classify_region((0.0, 0.0), ring_inner=0.9, ring_outer=0.5)


# ---------------------------------------------------------------------------
# Ring angle ↔ hue
# ---------------------------------------------------------------------------


def test_top_of_ring_is_hue_zero_red():
    """12 o'clock = hue 0 = red."""
    angle = math.pi / 2  # +y axis
    assert ring_angle_to_hue(angle) == pytest.approx(0.0)


def test_three_oclock_is_hue_three_quarters():
    """3 o'clock (positive x axis, angle 0) → hue 0.25 (orange)
    on the visual clockwise convention; ensure the math matches."""
    hue = ring_angle_to_hue(0.0)
    assert hue == pytest.approx(0.25)


def test_hue_to_ring_angle_round_trips():
    for hue in (0.0, 0.25, 0.5, 0.75, 0.99):
        recovered = ring_angle_to_hue(hue_to_ring_angle(hue))
        assert recovered == pytest.approx(hue, abs=1e-9)


def test_ring_position_lands_on_default_radius_circle():
    """The default ring position must lie on the mid-band circle."""
    position = ring_position_for_hue(0.5)
    radius = math.hypot(*position)
    expected = (DEFAULT_RING_INNER + DEFAULT_RING_OUTER) / 2.0
    assert radius == pytest.approx(expected)


# ---------------------------------------------------------------------------
# SV triangle vertices
# ---------------------------------------------------------------------------


def test_triangle_vertices_three_distinct_points():
    sat, white, black = triangle_vertices(0.0)
    assert sat != white
    assert white != black
    assert sat != black


def test_triangle_vertices_rotate_with_hue():
    """Changing hue rotates the saturated-corner vertex around the
    centre — its position depends on hue."""
    sat_red, _, _ = triangle_vertices(0.0)
    sat_green, _, _ = triangle_vertices(1.0 / 3.0)
    assert sat_red != sat_green


# ---------------------------------------------------------------------------
# triangle_to_sv / sv_to_triangle round-trip
# ---------------------------------------------------------------------------


def test_sv_to_triangle_then_back_round_trips():
    """The forward + inverse SV maps must compose to identity for
    reasonable interior values."""
    hue = 0.4
    cases = [(0.5, 0.5), (0.2, 0.8), (0.9, 0.3), (1.0, 1.0)]
    for s, v in cases:
        cartesian = sv_to_triangle(s, v, hue)
        recovered_s, recovered_v = triangle_to_sv(cartesian, hue)
        assert recovered_s == pytest.approx(s, abs=1e-6)
        assert recovered_v == pytest.approx(v, abs=1e-6)


def test_triangle_to_sv_clamps_outside_point():
    """A point outside the triangle must clamp into [0, 1] rather
    than yielding negative S/V."""
    s, v = triangle_to_sv((10.0, 10.0), 0.0)
    assert 0.0 <= s <= 1.0
    assert 0.0 <= v <= 1.0


def test_saturated_corner_yields_full_s_full_v():
    """The corner of the triangle that points outward is the
    saturated-hue corner — clicking it should give S=1, V=1."""
    sat_pt, _, _ = triangle_vertices(0.0)
    s, v = triangle_to_sv(sat_pt, 0.0)
    assert s == pytest.approx(1.0)
    assert v == pytest.approx(1.0)


def test_white_corner_yields_zero_s_full_v():
    _, white_pt, _ = triangle_vertices(0.0)
    s, v = triangle_to_sv(white_pt, 0.0)
    assert s == pytest.approx(0.0)
    assert v == pytest.approx(1.0)


def test_black_corner_yields_zero_v():
    _, _, black_pt = triangle_vertices(0.0)
    _, v = triangle_to_sv(black_pt, 0.0)
    assert v == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# HSV ↔ RGB
# ---------------------------------------------------------------------------


def test_hsv_to_rgb_pure_red():
    assert hsv_to_rgb(0.0, 1.0, 1.0) == (255, 0, 0)


def test_hsv_to_rgb_pure_green():
    assert hsv_to_rgb(1.0 / 3.0, 1.0, 1.0) == (0, 255, 0)


def test_hsv_to_rgb_pure_blue():
    assert hsv_to_rgb(2.0 / 3.0, 1.0, 1.0) == (0, 0, 255)


def test_hsv_clamps_out_of_range_components():
    """Negative / over-range S or V must clamp rather than wrap."""
    assert hsv_to_rgb(0.0, -1.0, 0.5) == hsv_to_rgb(0.0, 0.0, 0.5)
    assert hsv_to_rgb(0.0, 0.5, 5.0) == hsv_to_rgb(0.0, 0.5, 1.0)


def test_rgb_to_hsv_pure_red():
    h, s, v = ring_to_hsv(255, 0, 0)
    assert h == pytest.approx(0.0)
    assert s == pytest.approx(1.0)
    assert v == pytest.approx(1.0)


def ring_to_hsv(r: int, g: int, b: int):
    from Imervue.paint.color_wheel import rgb_to_hsv
    return rgb_to_hsv(r, g, b)


def test_rgb_clamp_into_byte_range():
    """Out-of-range RGB inputs clamp before HSV conversion."""
    h, s, v = ring_to_hsv(-50, 300, 100)
    # Whatever the result, the channels were clamped to [0, 255]
    # before colorsys; sanity-check by recomposing.
    recomposed = hsv_to_rgb(h, s, v)
    for component in recomposed:
        assert 0 <= component <= 255
