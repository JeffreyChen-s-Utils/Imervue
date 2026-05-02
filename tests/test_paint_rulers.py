"""Tests for the pure-math ruler / drawing-aid helpers."""
from __future__ import annotations

import dataclasses
import math

import pytest

from Imervue.paint import rulers
from Imervue.paint.rulers import Ruler, snap_to_ruler


# ---------------------------------------------------------------------------
# Module-level constants & dataclass defaults
# ---------------------------------------------------------------------------


def test_ruler_modes_includes_documented_set():
    assert set(rulers.RULER_MODES) == {
        "off", "linear", "cross", "ellipse", "concentric", "parallel",
        "perspective", "curve",
    }


def test_default_ruler_mode_is_off():
    assert rulers.DEFAULT_RULER_MODE == "off"
    assert rulers.DEFAULT_RULER_MODE in rulers.RULER_MODES


def test_default_ruler_is_off_mode():
    assert Ruler().mode == "off"


def test_off_ruler_singleton_is_off():
    assert rulers.OFF_RULER.mode == "off"


def test_ruler_is_frozen():
    r = Ruler(mode="linear")
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.mode = "ellipse"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# off mode
# ---------------------------------------------------------------------------


def test_off_mode_returns_input_unchanged():
    pt = (12.5, -3.25)
    assert snap_to_ruler(pt, Ruler(mode="off")) == pt


def test_off_mode_returns_floats_even_for_integer_input():
    out = snap_to_ruler((10, 5), Ruler(mode="off"))
    assert out == (10.0, 5.0)
    assert isinstance(out[0], float)


# ---------------------------------------------------------------------------
# Linear mode — perpendicular foot on infinite line
# ---------------------------------------------------------------------------


def test_linear_horizontal_collapses_y_to_anchor():
    r = Ruler(mode="linear", anchor=(0.0, 5.0), angle_deg=0.0)
    assert snap_to_ruler((10.0, 100.0), r) == pytest.approx((10.0, 5.0))


def test_linear_vertical_collapses_x_to_anchor():
    r = Ruler(mode="linear", anchor=(5.0, 0.0), angle_deg=90.0)
    snapped = snap_to_ruler((100.0, 10.0), r)
    assert snapped[0] == pytest.approx(5.0)
    assert snapped[1] == pytest.approx(10.0)


def test_linear_point_already_on_line_is_identity():
    r = Ruler(mode="linear", anchor=(0.0, 0.0), angle_deg=45.0)
    pt = (3.0, 3.0)  # on the y=x line
    snapped = snap_to_ruler(pt, r)
    assert snapped[0] == pytest.approx(3.0)
    assert snapped[1] == pytest.approx(3.0)


def test_linear_anchor_returns_anchor():
    r = Ruler(mode="linear", anchor=(7.0, 11.0), angle_deg=33.0)
    assert snap_to_ruler((7.0, 11.0), r) == pytest.approx((7.0, 11.0))


def test_linear_perpendicular_distance_minimised():
    """Snap point distance from line == perpendicular distance."""
    r = Ruler(mode="linear", anchor=(0.0, 0.0), angle_deg=0.0)
    pt = (5.0, 9.0)
    snapped = snap_to_ruler(pt, r)
    # The snap is on y=0; perpendicular distance is 9.0.
    dist = math.hypot(pt[0] - snapped[0], pt[1] - snapped[1])
    assert dist == pytest.approx(9.0)


# ---------------------------------------------------------------------------
# Cross mode — closer of two perpendicular lines
# ---------------------------------------------------------------------------


def test_cross_snaps_to_horizontal_when_closer():
    r = Ruler(mode="cross", anchor=(0.0, 0.0), angle_deg=0.0)
    # Point near the horizontal axis.
    snapped = snap_to_ruler((10.0, 1.0), r)
    assert snapped[1] == pytest.approx(0.0)


def test_cross_snaps_to_vertical_when_closer():
    r = Ruler(mode="cross", anchor=(0.0, 0.0), angle_deg=0.0)
    # Point near the vertical axis (small x, large y).
    snapped = snap_to_ruler((1.0, 10.0), r)
    assert snapped[0] == pytest.approx(0.0)


def test_cross_point_on_horizontal_stays():
    r = Ruler(mode="cross", anchor=(0.0, 0.0), angle_deg=0.0)
    assert snap_to_ruler((5.0, 0.0), r) == pytest.approx((5.0, 0.0))


def test_cross_at_45_degrees_breaks_tie_deterministically():
    r = Ruler(mode="cross", anchor=(0.0, 0.0), angle_deg=0.0)
    # Equidistant from both lines — two consecutive calls must agree.
    a = snap_to_ruler((5.0, 5.0), r)
    b = snap_to_ruler((5.0, 5.0), r)
    assert a == b


# ---------------------------------------------------------------------------
# Ellipse mode — radial projection onto perimeter
# ---------------------------------------------------------------------------


def test_ellipse_point_on_perimeter_x_axis_stays():
    r = Ruler(mode="ellipse", anchor=(0.0, 0.0), rx=10.0, ry=5.0)
    snapped = snap_to_ruler((10.0, 0.0), r)
    assert snapped[0] == pytest.approx(10.0)
    assert snapped[1] == pytest.approx(0.0)


def test_ellipse_point_on_perimeter_y_axis_stays():
    r = Ruler(mode="ellipse", anchor=(0.0, 0.0), rx=10.0, ry=5.0)
    snapped = snap_to_ruler((0.0, 5.0), r)
    assert snapped[0] == pytest.approx(0.0)
    assert snapped[1] == pytest.approx(5.0)


def test_ellipse_far_point_pulled_to_perimeter():
    r = Ruler(mode="ellipse", anchor=(0.0, 0.0), rx=10.0, ry=5.0)
    # Point on the +x ray, well outside the ellipse.
    snapped = snap_to_ruler((100.0, 0.0), r)
    assert snapped == pytest.approx((10.0, 0.0))


def test_ellipse_inside_point_pushed_to_perimeter():
    r = Ruler(mode="ellipse", anchor=(0.0, 0.0), rx=10.0, ry=5.0)
    # Point well inside the ellipse — radial projection still pushes
    # it to the boundary.
    snapped = snap_to_ruler((1.0, 0.0), r)
    assert snapped == pytest.approx((10.0, 0.0))


def test_ellipse_centre_returns_deterministic_perimeter_point():
    r = Ruler(mode="ellipse", anchor=(50.0, 30.0), rx=10.0, ry=5.0)
    snapped = snap_to_ruler((50.0, 30.0), r)
    # Documented fallback: the +rx point along the local x axis.
    assert snapped == pytest.approx((60.0, 30.0))


def test_ellipse_off_centre_anchor_translates_correctly():
    r = Ruler(mode="ellipse", anchor=(100.0, 200.0), rx=10.0, ry=10.0)
    # Point on +x ray from anchor.
    snapped = snap_to_ruler((150.0, 200.0), r)
    assert snapped == pytest.approx((110.0, 200.0))


def test_ellipse_rotated_90_swaps_axes():
    """A 90° rotation should turn the major axis vertical."""
    r = Ruler(
        mode="ellipse", anchor=(0.0, 0.0), rx=10.0, ry=5.0, angle_deg=90.0,
    )
    # Cursor on +y axis — should land at distance rx along that axis.
    snapped = snap_to_ruler((0.0, 100.0), r)
    assert snapped[0] == pytest.approx(0.0)
    assert snapped[1] == pytest.approx(10.0)


def test_ellipse_zero_rx_raises_value_error():
    r = Ruler(mode="ellipse", anchor=(0.0, 0.0), rx=0.0, ry=5.0)
    with pytest.raises(ValueError, match="positive"):
        snap_to_ruler((1.0, 1.0), r)


def test_ellipse_negative_ry_raises_value_error():
    r = Ruler(mode="ellipse", anchor=(0.0, 0.0), rx=5.0, ry=-2.0)
    with pytest.raises(ValueError, match="positive"):
        snap_to_ruler((1.0, 1.0), r)


# ---------------------------------------------------------------------------
# Concentric mode — nearest ring around anchor
# ---------------------------------------------------------------------------


def test_concentric_snaps_to_nearest_ring():
    r = Ruler(mode="concentric", anchor=(0.0, 0.0), spacing=10.0)
    # Point at radius 12 → nearest ring is radius 10.
    snapped = snap_to_ruler((12.0, 0.0), r)
    assert snapped == pytest.approx((10.0, 0.0))


def test_concentric_snaps_outward_when_closer():
    r = Ruler(mode="concentric", anchor=(0.0, 0.0), spacing=10.0)
    # Point at radius 17 → nearest ring is 20.
    snapped = snap_to_ruler((17.0, 0.0), r)
    assert snapped == pytest.approx((20.0, 0.0))


def test_concentric_point_on_ring_stays():
    r = Ruler(mode="concentric", anchor=(0.0, 0.0), spacing=10.0)
    snapped = snap_to_ruler((10.0, 0.0), r)
    assert snapped == pytest.approx((10.0, 0.0))


def test_concentric_point_at_anchor_returns_anchor():
    r = Ruler(mode="concentric", anchor=(50.0, 30.0), spacing=10.0)
    snapped = snap_to_ruler((50.0, 30.0), r)
    assert snapped == pytest.approx((50.0, 30.0))


def test_concentric_close_to_anchor_collapses_to_anchor():
    """A point closer to the anchor than spacing/2 snaps to the centre
    (ring radius 0)."""
    r = Ruler(mode="concentric", anchor=(0.0, 0.0), spacing=10.0)
    snapped = snap_to_ruler((2.0, 0.0), r)
    assert snapped == pytest.approx((0.0, 0.0))


def test_concentric_preserves_angle():
    r = Ruler(mode="concentric", anchor=(0.0, 0.0), spacing=10.0)
    # Point at 45°, radius ~14.14. Nearest ring 10. Angle preserved.
    snapped = snap_to_ruler((10.0, 10.0), r)
    angle = math.atan2(snapped[1], snapped[0])
    assert angle == pytest.approx(math.pi / 4)
    assert math.hypot(*snapped) == pytest.approx(10.0)


def test_concentric_zero_spacing_raises():
    r = Ruler(mode="concentric", anchor=(0.0, 0.0), spacing=0.0)
    with pytest.raises(ValueError, match="positive"):
        snap_to_ruler((5.0, 5.0), r)


# ---------------------------------------------------------------------------
# Parallel mode — nearest of N parallel lines
# ---------------------------------------------------------------------------


def test_parallel_horizontal_snaps_to_nearest_y():
    """angle_deg=0 → lines y=0, y=±10, y=±20 …"""
    r = Ruler(mode="parallel", anchor=(0.0, 0.0), angle_deg=0.0, spacing=10.0)
    # Point (5, 12) → nearest line is y=10. x along stays.
    snapped = snap_to_ruler((5.0, 12.0), r)
    assert snapped[0] == pytest.approx(5.0)
    assert snapped[1] == pytest.approx(10.0)


def test_parallel_vertical_snaps_to_nearest_x():
    r = Ruler(mode="parallel", anchor=(0.0, 0.0), angle_deg=90.0, spacing=10.0)
    snapped = snap_to_ruler((12.0, 5.0), r)
    assert snapped[0] == pytest.approx(10.0)
    assert snapped[1] == pytest.approx(5.0)


def test_parallel_point_on_anchor_line_stays():
    r = Ruler(mode="parallel", anchor=(0.0, 0.0), angle_deg=0.0, spacing=10.0)
    snapped = snap_to_ruler((5.0, 0.0), r)
    assert snapped == pytest.approx((5.0, 0.0))


def test_parallel_off_anchor_line_snaps_to_neighbour():
    r = Ruler(mode="parallel", anchor=(0.0, 0.0), angle_deg=0.0, spacing=10.0)
    # Slightly above y=20: should snap to y=20 (closer than y=30).
    snapped = snap_to_ruler((3.0, 21.0), r)
    assert snapped[1] == pytest.approx(20.0)


def test_parallel_negative_offset_works():
    r = Ruler(mode="parallel", anchor=(0.0, 0.0), angle_deg=0.0, spacing=10.0)
    snapped = snap_to_ruler((3.0, -7.0), r)
    assert snapped[1] == pytest.approx(-10.0)


def test_parallel_zero_spacing_raises():
    r = Ruler(mode="parallel", anchor=(0.0, 0.0), angle_deg=0.0, spacing=0.0)
    with pytest.raises(ValueError, match="positive"):
        snap_to_ruler((5.0, 5.0), r)


# ---------------------------------------------------------------------------
# perspective ruler
# ---------------------------------------------------------------------------


def test_perspective_one_point_snaps_to_line_through_vp():
    """One-point perspective: cursor snaps to the perpendicular foot
    on the line from the stroke anchor through the vanishing point."""
    r = Ruler(mode="perspective", vanishing_points=((100.0, 0.0),))
    # Stroke anchor at origin; cursor at (50, 30). The line from
    # anchor through VP is the +x axis, so the perpendicular foot is
    # (50, 0).
    snapped = snap_to_ruler((50.0, 30.0), r, stroke_anchor=(0.0, 0.0))
    assert snapped == pytest.approx((50.0, 0.0))


def test_perspective_picks_nearest_vanishing_point():
    """Two-point perspective: the cursor snaps onto whichever VP's
    line is closest. A cursor up and slightly right snaps onto the
    upward line, not the rightward one."""
    r = Ruler(
        mode="perspective",
        vanishing_points=((100.0, 0.0), (0.0, 100.0)),
    )
    # Cursor near the +y axis — closer to the line toward (0, 100).
    snapped = snap_to_ruler((5.0, 80.0), r, stroke_anchor=(0.0, 0.0))
    assert snapped == pytest.approx((0.0, 80.0))


def test_perspective_three_point_picks_minimum_distance():
    r = Ruler(
        mode="perspective",
        vanishing_points=(
            (1000.0, 0.0),     # rightward
            (-1000.0, 0.0),    # leftward (collinear with the first)
            (0.0, -1000.0),    # upward
        ),
    )
    snapped = snap_to_ruler((1.0, -50.0), r, stroke_anchor=(0.0, 0.0))
    # The upward line gives the smaller perpendicular distance.
    assert snapped == pytest.approx((0.0, -50.0))


def test_perspective_no_vanishing_points_returns_input():
    r = Ruler(mode="perspective", vanishing_points=())
    snapped = snap_to_ruler((5.0, 7.0), r, stroke_anchor=(0.0, 0.0))
    assert snapped == pytest.approx((5.0, 7.0))


def test_perspective_vp_at_anchor_is_skipped():
    """A VP coincident with the stroke anchor has no defined direction
    and must be silently skipped — never propagate a NaN through the
    snap. Falls back to the next VP, or to "no snap" if none remain."""
    r = Ruler(
        mode="perspective",
        vanishing_points=((0.0, 0.0), (10.0, 0.0)),
    )
    snapped = snap_to_ruler((5.0, 7.0), r, stroke_anchor=(0.0, 0.0))
    # The valid VP is along +x, so the cursor (5, 7) snaps to (5, 0).
    assert snapped == pytest.approx((5.0, 0.0))


def test_perspective_falls_back_to_ruler_anchor_when_no_stroke_anchor():
    """Callers that don't supply a stroke anchor (e.g. tests, future
    tools) should still get a usable snap — the ruler's own anchor
    field acts as the line origin."""
    r = Ruler(
        mode="perspective",
        anchor=(10.0, 10.0),
        vanishing_points=((110.0, 10.0),),
    )
    snapped = snap_to_ruler((20.0, 30.0), r)
    assert snapped == pytest.approx((20.0, 10.0))


def test_perspective_caps_vanishing_points_from_dict():
    """The 1/2/3-point convention is enforced on the storage path —
    a corrupted settings file with 5 VPs is silently truncated."""
    raw = {
        "mode": "perspective",
        "vanishing_points": [[i, 0] for i in range(5)],
    }
    rebuilt = Ruler.from_dict(raw)
    assert len(rebuilt.vanishing_points) == 3


def test_perspective_round_trip_via_dict():
    original = Ruler(
        mode="perspective",
        vanishing_points=((-200.0, 0.0), (200.0, 0.0), (0.0, -800.0)),
    )
    rebuilt = Ruler.from_dict(original.to_dict())
    assert rebuilt == original


def test_perspective_from_dict_drops_malformed_vp_entries():
    raw = {
        "mode": "perspective",
        "vanishing_points": [[1, 2], "garbage", [3], [4, 5]],
    }
    rebuilt = Ruler.from_dict(raw)
    assert rebuilt.vanishing_points == ((1.0, 2.0), (4.0, 5.0))


# ---------------------------------------------------------------------------
# from_dict / to_dict round-trip
# ---------------------------------------------------------------------------


def test_to_dict_emits_json_friendly_types():
    r = Ruler(
        mode="linear", anchor=(1.0, 2.0), angle_deg=30.0,
        rx=11.0, ry=22.0, spacing=5.0,
    )
    raw = r.to_dict()
    assert raw == {
        "mode": "linear",
        "anchor": [1.0, 2.0],
        "angle_deg": 30.0,
        "rx": 11.0,
        "ry": 22.0,
        "spacing": 5.0,
        "vanishing_points": [],
        "control_points": [],
    }


def test_round_trip_via_to_from_dict():
    original = Ruler(
        mode="ellipse", anchor=(50.0, 30.0), angle_deg=15.0,
        rx=12.0, ry=8.0, spacing=3.0,
    )
    rebuilt = Ruler.from_dict(original.to_dict())
    assert rebuilt == original


def test_from_dict_handles_missing_dict():
    rebuilt = Ruler.from_dict(None)
    assert rebuilt.mode == "off"


def test_from_dict_handles_empty_dict():
    rebuilt = Ruler.from_dict({})
    assert rebuilt.mode == "off"


def test_from_dict_drops_unknown_mode():
    rebuilt = Ruler.from_dict({"mode": "fractal"})
    assert rebuilt.mode == "off"


def test_from_dict_recovers_corrupt_anchor():
    rebuilt = Ruler.from_dict({"mode": "linear", "anchor": "garbage"})
    assert rebuilt.anchor == (0.0, 0.0)


def test_from_dict_recovers_negative_rx():
    """rx <= 0 must fall back to the default — never bypass the
    positive-axis invariant."""
    rebuilt = Ruler.from_dict({"mode": "ellipse", "rx": -5.0})
    assert rebuilt.rx == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# Error handling at the dispatcher layer
# ---------------------------------------------------------------------------


def test_unknown_mode_at_runtime_raises():
    """Direct construction with a typo'd mode is allowed (frozen
    dataclass), but snap_to_ruler must reject it loudly."""
    r = Ruler.__new__(Ruler)
    object.__setattr__(r, "mode", "nonsense")
    object.__setattr__(r, "anchor", (0.0, 0.0))
    object.__setattr__(r, "angle_deg", 0.0)
    object.__setattr__(r, "rx", 50.0)
    object.__setattr__(r, "ry", 50.0)
    object.__setattr__(r, "spacing", 20.0)
    object.__setattr__(r, "vanishing_points", ())
    object.__setattr__(r, "control_points", ())
    with pytest.raises(ValueError, match="unknown ruler mode"):
        snap_to_ruler((1.0, 1.0), r)


# ---------------------------------------------------------------------------
# Curve ruler
# ---------------------------------------------------------------------------


def test_curve_ruler_in_modes_list():
    assert "curve" in rulers.RULER_MODES


def test_curve_with_no_points_falls_through_to_input():
    ruler = Ruler(mode="curve", control_points=())
    assert snap_to_ruler((3.0, 5.0), ruler) == (3.0, 5.0)


def test_curve_with_one_point_falls_through_to_input():
    """Single-point curve is degenerate — must not snap blindly to it."""
    ruler = Ruler(mode="curve", control_points=((10.0, 10.0),))
    assert snap_to_ruler((3.0, 5.0), ruler) == (3.0, 5.0)


def test_curve_two_points_snaps_onto_segment():
    """Two-point curve degenerates to a straight segment — cursor far
    from the segment must snap onto it."""
    ruler = Ruler(
        mode="curve",
        control_points=((0.0, 0.0), (10.0, 0.0)),
    )
    snapped = snap_to_ruler((5.0, 50.0), ruler)
    # Closest point on the segment to (5, 50) is the foot at (5, 0).
    assert snapped[0] == pytest.approx(5.0, abs=0.5)
    assert snapped[1] == pytest.approx(0.0, abs=0.5)


def test_curve_endpoints_are_passed_through():
    """A cursor exactly at a control point must snap to it (the curve
    passes through every control point)."""
    pts = ((0.0, 0.0), (5.0, 5.0), (10.0, 0.0))
    ruler = Ruler(mode="curve", control_points=pts)
    for pt in pts:
        snapped = snap_to_ruler(pt, ruler)
        assert snapped[0] == pytest.approx(pt[0], abs=0.5)
        assert snapped[1] == pytest.approx(pt[1], abs=0.5)


def test_curve_snap_finds_midpoint_for_midpoint_query():
    """A cursor right between two adjacent controls must snap to a
    point near the midpoint, not to either endpoint exclusively."""
    ruler = Ruler(
        mode="curve",
        control_points=((0.0, 0.0), (10.0, 0.0)),
    )
    snapped = snap_to_ruler((5.0, 0.0), ruler)
    assert snapped[0] == pytest.approx(5.0, abs=0.5)
    assert snapped[1] == pytest.approx(0.0, abs=0.5)


def test_curve_round_trips_through_to_dict():
    pts = ((1.0, 2.0), (3.0, 4.0), (5.0, 6.0))
    original = Ruler(mode="curve", control_points=pts)
    rebuilt = Ruler.from_dict(original.to_dict())
    assert rebuilt.mode == "curve"
    assert rebuilt.control_points == pts


def test_curve_drops_malformed_control_points_on_load():
    """A hand-edited settings dict must never crash boot."""
    rebuilt = Ruler.from_dict({
        "mode": "curve",
        "control_points": [
            [1.0, 2.0],
            "garbage",
            [3.0],
            [None, None],
            [4.0, 5.0],
        ],
    })
    assert rebuilt.control_points == ((1.0, 2.0), (4.0, 5.0))


def test_curve_caps_control_count_at_max():
    over = [[float(i), 0.0] for i in range(rulers.CURVE_MAX_POINTS + 10)]
    rebuilt = Ruler.from_dict({"mode": "curve", "control_points": over})
    assert len(rebuilt.control_points) == rulers.CURVE_MAX_POINTS
