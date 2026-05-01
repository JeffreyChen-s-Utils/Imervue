"""Tests for the on-canvas transform handles math."""
from __future__ import annotations

import pytest

from Imervue.paint.transform_handles import (
    ALL_BOX_HANDLES,
    CORNER_HANDLES,
    EDGE_HANDLES,
    HANDLE_BODY,
    HANDLE_E,
    HANDLE_N,
    HANDLE_NE,
    HANDLE_NW,
    HANDLE_ROTATE,
    HANDLE_S,
    HANDLE_SE,
    HANDLE_SW,
    HANDLE_W,
    MIN_BOX_SIZE,
    TransformBox,
    apply_handle_drag,
    from_rect,
    handle_positions,
    hit_test,
)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_construct_minimal():
    box = TransformBox(cx=10.0, cy=20.0, width=30.0, height=40.0)
    assert box.cx == 10.0
    assert box.rotation_deg == 0.0


def test_rejects_undersized_width():
    with pytest.raises(ValueError, match="width"):
        TransformBox(cx=0, cy=0, width=MIN_BOX_SIZE - 1, height=10)


def test_rejects_undersized_height():
    with pytest.raises(ValueError, match="height"):
        TransformBox(cx=0, cy=0, width=10, height=MIN_BOX_SIZE - 1)


def test_from_rect_centres_correctly():
    box = from_rect(10, 20, 40, 60)
    assert box.cx == 30.0
    assert box.cy == 50.0
    assert box.width == 40.0
    assert box.height == 60.0


# ---------------------------------------------------------------------------
# Handle positions — geometry
# ---------------------------------------------------------------------------


def test_handle_positions_axis_aligned():
    box = from_rect(0, 0, 100, 60)
    pos = handle_positions(box)
    assert pos[HANDLE_NW] == pytest.approx((0.0, 0.0))
    assert pos[HANDLE_NE] == pytest.approx((100.0, 0.0))
    assert pos[HANDLE_SE] == pytest.approx((100.0, 60.0))
    assert pos[HANDLE_SW] == pytest.approx((0.0, 60.0))


def test_handle_positions_includes_all_documented_handles():
    box = from_rect(0, 0, 100, 60)
    pos = handle_positions(box)
    assert set(pos.keys()) == set(ALL_BOX_HANDLES)


def test_rotate_handle_sits_above_top_edge():
    """The rotate handle lives along the local -y axis, past the
    top edge by ``ROTATE_HANDLE_OFFSET``."""
    box = from_rect(0, 0, 100, 60)
    pos = handle_positions(box)
    # N edge midpoint is (50, 0); rotate handle is above it.
    rotate = pos[HANDLE_ROTATE]
    n = pos[HANDLE_N]
    assert rotate[0] == pytest.approx(n[0])
    assert rotate[1] < n[1]


def test_handle_positions_after_90_degree_rotation():
    """A 90° clockwise rotation puts the original NW corner where
    the original NE corner used to be."""
    box = from_rect(0, 0, 100, 60).__class__(
        cx=50.0, cy=30.0, width=100.0, height=60.0, rotation_deg=90.0,
    )
    pos = handle_positions(box)
    # NW was at (0, 0); rotated 90° around centre (50, 30) → (80, -20).
    assert pos[HANDLE_NW] == pytest.approx((80.0, -20.0))


# ---------------------------------------------------------------------------
# hit_test
# ---------------------------------------------------------------------------


def test_hit_test_corner_within_radius():
    box = from_rect(0, 0, 100, 60)
    assert hit_test(box, (3.0, 3.0)) == HANDLE_NW


def test_hit_test_outside_returns_none():
    box = from_rect(0, 0, 100, 60)
    assert hit_test(box, (-200.0, -200.0)) is None


def test_hit_test_body_returns_body_marker():
    """Click in the box's interior (not on a handle) returns the
    HANDLE_BODY sentinel so the caller can route as translation."""
    box = from_rect(0, 0, 100, 60)
    assert hit_test(box, (50.0, 30.0)) == HANDLE_BODY


def test_hit_test_rotate_handle():
    box = from_rect(0, 0, 100, 60)
    pos = handle_positions(box)
    rotate_pos = pos[HANDLE_ROTATE]
    assert hit_test(box, rotate_pos) == HANDLE_ROTATE


def test_hit_test_inside_rotated_box():
    """A 45°-rotated box still treats its centre as body-clickable."""
    box = TransformBox(
        cx=50.0, cy=50.0, width=40.0, height=40.0, rotation_deg=45.0,
    )
    assert hit_test(box, (50.0, 50.0)) == HANDLE_BODY


def test_hit_test_handles_have_priority_over_body():
    """A click that's inside the body AND within the corner-handle
    radius must report the corner — handle dragging is the more
    specific intent."""
    box = from_rect(0, 0, 100, 60)
    # (4, 4) is inside the box AND within 8 px of the NW corner.
    assert hit_test(box, (4.0, 4.0)) == HANDLE_NW


# ---------------------------------------------------------------------------
# apply_handle_drag — translation
# ---------------------------------------------------------------------------


def test_drag_body_translates_centre():
    box = from_rect(10, 10, 40, 40)
    moved = apply_handle_drag(box, HANDLE_BODY, (15.0, -5.0))
    assert moved.cx == pytest.approx(box.cx + 15.0)
    assert moved.cy == pytest.approx(box.cy - 5.0)


# ---------------------------------------------------------------------------
# apply_handle_drag — resize
# ---------------------------------------------------------------------------


def test_drag_se_grows_width_and_height():
    box = from_rect(0, 0, 40, 40)
    enlarged = apply_handle_drag(box, HANDLE_SE, (10.0, 5.0))
    assert enlarged.width == pytest.approx(50.0)
    assert enlarged.height == pytest.approx(45.0)


def test_drag_se_shifts_centre_to_keep_nw_anchor_fixed():
    """Dragging SE must leave the NW corner where it was — the
    opposite corner is the anchor for a corner resize."""
    box = from_rect(0, 0, 40, 40)
    nw_before = handle_positions(box)[HANDLE_NW]
    enlarged = apply_handle_drag(box, HANDLE_SE, (10.0, 10.0))
    nw_after = handle_positions(enlarged)[HANDLE_NW]
    assert nw_after == pytest.approx(nw_before)


def test_drag_nw_shrinks_keeping_se_anchor():
    box = from_rect(0, 0, 40, 40)
    se_before = handle_positions(box)[HANDLE_SE]
    shrunk = apply_handle_drag(box, HANDLE_NW, (10.0, 10.0))
    se_after = handle_positions(shrunk)[HANDLE_SE]
    assert se_after == pytest.approx(se_before)


def test_drag_n_only_changes_height():
    box = from_rect(0, 0, 40, 40)
    moved = apply_handle_drag(box, HANDLE_N, (0.0, -5.0))
    assert moved.width == pytest.approx(box.width)
    assert moved.height == pytest.approx(45.0)


def test_drag_e_only_changes_width():
    box = from_rect(0, 0, 40, 40)
    moved = apply_handle_drag(box, HANDLE_E, (8.0, 0.0))
    assert moved.height == pytest.approx(box.height)
    assert moved.width == pytest.approx(48.0)


def test_drag_floor_clamps_to_min_size():
    """Pulling SE inward past the centre must clamp at MIN_BOX_SIZE
    rather than letting the box invert."""
    box = from_rect(0, 0, 40, 40)
    pulled = apply_handle_drag(box, HANDLE_SE, (-1000.0, -1000.0))
    assert pulled.width == MIN_BOX_SIZE
    assert pulled.height == MIN_BOX_SIZE


def test_drag_resize_on_rotated_box_uses_local_axes():
    """A rotated box must resize along ITS axes, not the world's.
    Dragging the local +x direction by ``d`` extends the width by
    exactly ``d``, not a smaller projection."""
    box = TransformBox(
        cx=0.0, cy=0.0, width=40.0, height=40.0, rotation_deg=90.0,
    )
    # In the rotated frame, +x of the box points along world +y.
    # The E handle is therefore at world (0, +20). Dragging it by
    # (0, 10) world → width grows to 50.
    enlarged = apply_handle_drag(box, HANDLE_E, (0.0, 10.0))
    assert enlarged.width == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# apply_handle_drag — rotate
# ---------------------------------------------------------------------------


def test_drag_rotate_handle_changes_rotation():
    box = from_rect(0, 0, 40, 40)
    pos = handle_positions(box)
    rotate_x, rotate_y = pos[HANDLE_ROTATE]
    # Move the rotate handle 10 px to the right.
    new = apply_handle_drag(box, HANDLE_ROTATE, (10.0, 0.0))
    assert new.rotation_deg != box.rotation_deg


def test_rotate_drag_landing_at_east_yields_90_degrees():
    """If the rotate handle (originally at -90° local) is dragged
    until it's where the E handle was (0° world from centre), the
    box has rotated by +90°."""
    box = from_rect(0, 0, 40, 40)
    pos = handle_positions(box)
    rotate_x, rotate_y = pos[HANDLE_ROTATE]
    target_x = pos[HANDLE_E][0]
    target_y = pos[HANDLE_E][1]
    delta = (target_x - rotate_x, target_y - rotate_y)
    rotated = apply_handle_drag(box, HANDLE_ROTATE, delta)
    assert rotated.rotation_deg == pytest.approx(90.0)


# ---------------------------------------------------------------------------
# apply_handle_drag — error cases
# ---------------------------------------------------------------------------


def test_apply_unknown_handle_raises():
    box = from_rect(0, 0, 40, 40)
    with pytest.raises(ValueError, match="unknown handle"):
        apply_handle_drag(box, "diagonal", (1.0, 1.0))


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_handle_groups_match_documentation():
    """Catch accidental drift in the handle naming sets."""
    assert set(CORNER_HANDLES) == {HANDLE_NW, HANDLE_NE, HANDLE_SE, HANDLE_SW}
    assert set(EDGE_HANDLES) == {HANDLE_N, HANDLE_E, HANDLE_S, HANDLE_W}
    assert HANDLE_ROTATE in ALL_BOX_HANDLES


def test_min_box_size_is_at_least_one():
    """Anything smaller and the resize math becomes degenerate
    (a 0-size box has no defined corner positions)."""
    assert MIN_BOX_SIZE >= 1.0
