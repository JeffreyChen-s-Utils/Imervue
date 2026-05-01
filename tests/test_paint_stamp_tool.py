"""Tests for the clone-stamp tool."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.stamp_tool import StampState, stamp_dab


def _patterned_canvas(h: int = 80, w: int = 80) -> np.ndarray:
    """Canvas with a recognisable solid red square at (10..30, 10..30)
    on a white background — easy to verify the stamp picked up the
    right pixels."""
    arr = np.full((h, w, 4), 255, dtype=np.uint8)
    arr[10:30, 10:30, 0] = 200
    arr[10:30, 10:30, 1] = 0
    arr[10:30, 10:30, 2] = 0
    return arr


# ---------------------------------------------------------------------------
# StampState
# ---------------------------------------------------------------------------


def test_state_starts_without_source():
    state = StampState()
    assert not state.has_source()
    assert state.offset_for((10, 10)) is None


def test_set_source_records_point():
    state = StampState()
    state.set_source((20.0, 30.0))
    assert state.has_source()
    assert state.source == (20.0, 30.0)


def test_set_source_resets_stroke_anchor():
    """Setting a fresh source mid-session must invalidate the
    previous stroke's anchor — otherwise the next dab would use a
    stale offset that no longer maps to the new source."""
    state = StampState()
    state.set_source((10.0, 10.0))
    state.begin_stroke((50.0, 50.0))
    state.set_source((100.0, 100.0))
    assert state.stroke_anchor is None


def test_offset_for_returns_none_without_anchor():
    state = StampState()
    state.set_source((10.0, 10.0))
    assert state.offset_for((20.0, 20.0)) is None


def test_offset_for_returns_source_plus_delta():
    state = StampState()
    state.set_source((10.0, 10.0))
    state.begin_stroke((50.0, 50.0))
    # First dab is at the anchor → offset is the source itself.
    assert state.offset_for((50.0, 50.0)) == (10.0, 10.0)
    # Move 5 px right → source point also moves 5 px right.
    assert state.offset_for((55.0, 50.0)) == (15.0, 10.0)


def test_end_stroke_clears_anchor():
    state = StampState()
    state.set_source((10.0, 10.0))
    state.begin_stroke((40.0, 40.0))
    state.end_stroke()
    assert state.stroke_anchor is None


# ---------------------------------------------------------------------------
# stamp_dab — validation
# ---------------------------------------------------------------------------


def test_stamp_dab_rejects_non_rgba():
    state = StampState()
    state.set_source((10, 10))
    bad = np.zeros((10, 10, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="HxWx4"):
        stamp_dab(bad, state, 5, 5)


def test_stamp_dab_no_source_is_no_op():
    canvas = _patterned_canvas()
    snapshot = canvas.copy()
    state = StampState()
    damage = stamp_dab(canvas, state, 50, 50)
    assert damage.is_empty
    np.testing.assert_array_equal(canvas, snapshot)


def test_stamp_dab_zero_opacity_is_no_op():
    canvas = _patterned_canvas()
    snapshot = canvas.copy()
    state = StampState()
    state.set_source((20, 20))
    damage = stamp_dab(canvas, state, 50, 50, opacity=0.0)
    assert damage.is_empty
    np.testing.assert_array_equal(canvas, snapshot)


def test_stamp_dab_rejects_out_of_range_opacity():
    canvas = _patterned_canvas()
    state = StampState()
    state.set_source((20, 20))
    with pytest.raises(ValueError, match="opacity"):
        stamp_dab(canvas, state, 50, 50, opacity=2.0)


# ---------------------------------------------------------------------------
# stamp_dab — actual cloning
# ---------------------------------------------------------------------------


def test_stamp_dab_paints_red_at_destination():
    """Source area is the red square; destination is white. After
    the stamp, red pixels appear at the destination."""
    canvas = _patterned_canvas()
    state = StampState()
    # Source: centre of the red square.
    state.set_source((20, 20))
    # Destination: middle of the white area.
    stamp_dab(canvas, state, 60, 60, size=10, hardness=1.0)
    # Centre of the destination region picked up red.
    assert canvas[60, 60, 0] >= 100
    assert canvas[60, 60, 1] <= 100


def test_stamp_dab_first_call_pins_stroke_anchor():
    """The first stamp_dab in a stroke binds the anchor to the dab
    position — subsequent dabs sample with that delta."""
    canvas = _patterned_canvas()
    state = StampState()
    state.set_source((20, 20))
    stamp_dab(canvas, state, 60, 60, size=10, hardness=1.0)
    assert state.stroke_anchor == (60.0, 60.0)


def test_stamp_dab_second_dab_offsets_correctly():
    """Move the cursor 10 px right between dabs; the source sample
    point also moves 10 px right relative to the original source."""
    canvas = _patterned_canvas()
    state = StampState()
    state.set_source((20, 20))
    stamp_dab(canvas, state, 60, 60, size=10, hardness=1.0)
    # The second dab samples 10 px right of source = (30, 20). That
    # column is on the boundary of the red square; stamp_dab paints
    # whatever colour was there.
    stamp_dab(canvas, state, 70, 60, size=10, hardness=1.0)
    # Damage area at (70, 60) was painted (alpha unchanged because
    # canvas was already opaque). Red channel is somewhere between
    # white (255) and source (200).
    sample = canvas[60, 70]
    assert int(sample[0]) >= 100


def test_stamp_dab_outside_source_has_no_effect():
    """If the source offset puts the entire sampled patch off-canvas,
    nothing is painted."""
    canvas = _patterned_canvas(20, 20)
    state = StampState()
    state.set_source((-100, -100))
    snapshot = canvas.copy()
    stamp_dab(canvas, state, 10, 10, size=4, hardness=1.0)
    np.testing.assert_array_equal(canvas, snapshot)


def test_stamp_dab_returns_damage_rect():
    canvas = _patterned_canvas()
    state = StampState()
    state.set_source((20, 20))
    damage = stamp_dab(canvas, state, 60, 60, size=10, hardness=1.0)
    assert not damage.is_empty
    # Damage covers a 10×10-ish area centred at (60, 60).
    assert damage.x <= 60
    assert damage.x2 >= 60
    assert damage.y <= 60
    assert damage.y2 >= 60
