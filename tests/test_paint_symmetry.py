"""Tests for the pure-numpy symmetry helper used by the brush tool."""
from __future__ import annotations

import math

import pytest

from Imervue.paint import symmetry


CENTRE = (50.0, 40.0)


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------


def test_symmetry_modes_includes_documented_set():
    assert set(symmetry.SYMMETRY_MODES) == {
        "off", "horizontal", "vertical", "both", "radial_4", "radial_8",
    }


def test_default_mode_is_off():
    assert symmetry.DEFAULT_SYMMETRY_MODE == "off"
    assert symmetry.DEFAULT_SYMMETRY_MODE in symmetry.SYMMETRY_MODES


# ---------------------------------------------------------------------------
# Mode contracts — count + source-first ordering
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mode", "expected_count"),
    [
        ("off", 1),
        ("horizontal", 2),
        ("vertical", 2),
        ("both", 4),
        ("radial_4", 4),
        ("radial_8", 8),
    ],
)
def test_mirror_points_yields_expected_stroke_count(mode, expected_count):
    pts = symmetry.mirror_points((10.0, 5.0), mode, CENTRE)
    assert len(pts) == expected_count


@pytest.mark.parametrize("mode", list(symmetry.SYMMETRY_MODES))
def test_source_point_is_always_first(mode):
    pts = symmetry.mirror_points((11.5, 7.25), mode, CENTRE)
    assert pts[0] == (11.5, 7.25)


@pytest.mark.parametrize("mode", list(symmetry.SYMMETRY_MODES))
def test_call_is_deterministic(mode):
    pts_a = symmetry.mirror_points((3.0, 9.0), mode, CENTRE)
    pts_b = symmetry.mirror_points((3.0, 9.0), mode, CENTRE)
    assert pts_a == pts_b


# ---------------------------------------------------------------------------
# Per-mode geometry
# ---------------------------------------------------------------------------


def test_off_returns_only_source():
    assert symmetry.mirror_points((4.0, 6.0), "off", CENTRE) == [(4.0, 6.0)]


def test_horizontal_flips_across_vertical_axis():
    pts = symmetry.mirror_points((10.0, 5.0), "horizontal", CENTRE)
    assert pts[1] == (90.0, 5.0)  # 2*50 - 10 = 90; y stays


def test_vertical_flips_across_horizontal_axis():
    pts = symmetry.mirror_points((10.0, 5.0), "vertical", CENTRE)
    assert pts[1] == (10.0, 75.0)  # 2*40 - 5 = 75; x stays


def test_both_yields_source_h_v_diagonal():
    pts = symmetry.mirror_points((10.0, 5.0), "both", CENTRE)
    assert pts == [
        (10.0, 5.0),
        (90.0, 5.0),
        (10.0, 75.0),
        (90.0, 75.0),
    ]


def test_radial_4_first_entry_is_source():
    pts = symmetry.mirror_points((60.0, 40.0), "radial_4", CENTRE)
    assert pts[0] == pytest.approx((60.0, 40.0))


def test_radial_4_180_degree_rotation_matches_both_diagonal():
    pts = symmetry.mirror_points((60.0, 50.0), "radial_4", CENTRE)
    # 180° rotation around (50, 40) of (60, 50) → (40, 30).
    rx, ry = pts[2]
    assert rx == pytest.approx(40.0)
    assert ry == pytest.approx(30.0)


def test_radial_4_full_set_lies_on_one_circle():
    src = (70.0, 40.0)  # 20px right of centre
    pts = symmetry.mirror_points(src, "radial_4", CENTRE)
    radii = [math.hypot(x - CENTRE[0], y - CENTRE[1]) for x, y in pts]
    for r in radii:
        assert r == pytest.approx(20.0)


def test_radial_8_step_is_45_degrees():
    src = (CENTRE[0] + 10.0, CENTRE[1])  # angle 0, radius 10
    pts = symmetry.mirror_points(src, "radial_8", CENTRE)
    expected_angles = [0, 45, 90, 135, 180, 225, 270, 315]
    for (x, y), angle in zip(pts, expected_angles, strict=True):
        rad = math.radians(angle)
        ex = CENTRE[0] + 10.0 * math.cos(rad)
        ey = CENTRE[1] + 10.0 * math.sin(rad)
        assert x == pytest.approx(ex)
        assert y == pytest.approx(ey)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_point_at_origin_collapses_all_mirrors_to_origin():
    pts = symmetry.mirror_points(CENTRE, "radial_8", CENTRE)
    for x, y in pts:
        assert x == pytest.approx(CENTRE[0])
        assert y == pytest.approx(CENTRE[1])


def test_custom_origin_overrides_default_axis():
    # With origin (0, 0), horizontal mirror of (3, 4) is (-3, 4).
    pts = symmetry.mirror_points((3.0, 4.0), "horizontal", (0.0, 0.0))
    assert pts == [(3.0, 4.0), (-3.0, 4.0)]


def test_integer_inputs_are_accepted():
    pts = symmetry.mirror_points((10, 5), "horizontal", (50, 40))
    assert pts == [(10.0, 5.0), (90.0, 5.0)]


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_unknown_mode_raises_value_error():
    with pytest.raises(ValueError, match="unknown symmetry mode"):
        symmetry.mirror_points((1.0, 1.0), "kaleidoscope", CENTRE)


def test_error_message_lists_valid_modes():
    with pytest.raises(ValueError, match="off"):
        symmetry.mirror_points((1.0, 1.0), "bogus", CENTRE)
