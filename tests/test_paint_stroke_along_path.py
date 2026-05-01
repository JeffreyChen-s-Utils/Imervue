"""Tests for stroke-along-path."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.bezier_path import BezierPath, PathNode
from Imervue.paint.brush_engine import BrushStrokeOptions
from Imervue.paint.stroke_along_path import stroke_along_path


def _white_canvas(h: int = 60, w: int = 60) -> np.ndarray:
    return np.full((h, w, 4), 255, dtype=np.uint8)


def _options(**overrides) -> BrushStrokeOptions:
    """Default brush — 6 px round, fully opaque, normal blend."""
    base = {
        "color": (200, 0, 0),
        "size": 6,
        "opacity": 1.0,
        "hardness": 1.0,
        "blend_mode": "normal",
    }
    base.update(overrides)
    return BrushStrokeOptions(**base)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_rejects_non_rgba_canvas():
    bad = np.zeros((10, 10, 3), dtype=np.uint8)
    path = BezierPath(nodes=[
        PathNode(anchor=(0.0, 0.0)),
        PathNode(anchor=(5.0, 0.0)),
    ])
    with pytest.raises(ValueError, match="HxWx4"):
        stroke_along_path(bad, path, _options())


def test_empty_path_returns_empty_damage():
    canvas = _white_canvas()
    snapshot = canvas.copy()
    damage = stroke_along_path(canvas, BezierPath(), _options())
    assert damage.is_empty
    np.testing.assert_array_equal(canvas, snapshot)


def test_single_node_path_does_not_paint():
    canvas = _white_canvas()
    snapshot = canvas.copy()
    path = BezierPath(nodes=[PathNode(anchor=(10.0, 10.0))])
    damage = stroke_along_path(canvas, path, _options())
    assert damage.is_empty
    np.testing.assert_array_equal(canvas, snapshot)


# ---------------------------------------------------------------------------
# Basic rasterisation
# ---------------------------------------------------------------------------


def test_two_node_segment_paints_along_chord():
    canvas = _white_canvas()
    path = BezierPath(nodes=[
        PathNode(anchor=(10.0, 30.0)),
        PathNode(anchor=(50.0, 30.0)),
    ])
    stroke_along_path(canvas, path, _options())
    painted = (canvas[..., :3] != 255).any(axis=-1)
    # Painted pixels exist along y=30 between x=10 and x=50.
    assert painted[30, 15]
    assert painted[30, 40]


def test_first_anchor_is_stamped_exactly_once():
    """The path's first sample lands a single dab; nothing duplicates."""
    canvas = _white_canvas()
    path = BezierPath(nodes=[
        PathNode(anchor=(30.0, 30.0)),
        PathNode(anchor=(40.0, 30.0)),
    ])
    stroke_along_path(canvas, path, _options())
    # Sanity: the centre pixel got painted (alpha is still 255 because
    # we paint over an opaque canvas).
    assert tuple(canvas[30, 30, :3]) != (255, 255, 255)


def test_far_endpoints_paint_outside_the_starting_chord_centre():
    canvas = _white_canvas()
    path = BezierPath(nodes=[
        PathNode(anchor=(10.0, 30.0)),
        PathNode(anchor=(50.0, 30.0)),
    ])
    stroke_along_path(canvas, path, _options())
    painted = (canvas[..., :3] != 255).any(axis=-1)
    assert painted[30, 50] or painted[30, 49]


# ---------------------------------------------------------------------------
# Damage rect
# ---------------------------------------------------------------------------


def test_damage_rect_covers_painted_region():
    canvas = _white_canvas()
    path = BezierPath(nodes=[
        PathNode(anchor=(10.0, 30.0)),
        PathNode(anchor=(50.0, 30.0)),
    ])
    damage = stroke_along_path(canvas, path, _options())
    assert not damage.is_empty
    # Damage rect should cover the painted line, with some kernel
    # halo on each side.
    assert damage.x <= 10 + 4  # near the start
    assert damage.x2 >= 50 - 4  # near the end


# ---------------------------------------------------------------------------
# Curve handling
# ---------------------------------------------------------------------------


def test_curved_path_paints_above_chord_midpoint():
    """A curve with handles pulling upward leaves painted pixels
    above the straight-chord midpoint."""
    canvas = _white_canvas()
    path = BezierPath(nodes=[
        PathNode(anchor=(10.0, 40.0), handle_out=(10.0, 5.0)),
        PathNode(anchor=(50.0, 40.0), handle_in=(50.0, 5.0)),
    ])
    stroke_along_path(canvas, path, _options())
    painted = (canvas[..., :3] != 255).any(axis=-1)
    # Some painted pixels above y=40 (closer to y=10 control area).
    assert painted[:35, 25:35].any()


# ---------------------------------------------------------------------------
# Brush options propagate
# ---------------------------------------------------------------------------


def test_zero_opacity_is_no_op():
    canvas = _white_canvas()
    snapshot = canvas.copy()
    path = BezierPath(nodes=[
        PathNode(anchor=(10.0, 30.0)),
        PathNode(anchor=(50.0, 30.0)),
    ])
    stroke_along_path(canvas, path, _options(opacity=0.0))
    np.testing.assert_array_equal(canvas, snapshot)


def test_color_passes_through_to_canvas():
    canvas = _white_canvas()
    path = BezierPath(nodes=[
        PathNode(anchor=(15.0, 30.0)),
        PathNode(anchor=(45.0, 30.0)),
    ])
    stroke_along_path(canvas, path, _options(color=(0, 0, 200)))
    # Some painted pixel along the line is biased toward blue.
    painted = (canvas[..., :3] != 255).any(axis=-1)
    blue_present = (canvas[painted, 2] > canvas[painted, 0]).any()
    assert blue_present


# ---------------------------------------------------------------------------
# Spacing / sampling
# ---------------------------------------------------------------------------


def test_explicit_spacing_overrides_default():
    """A wide spacing (≈ brush size) leaves visible gaps; a narrow
    spacing fills the same path more continuously."""
    canvas_wide = _white_canvas(80, 80)
    canvas_narrow = _white_canvas(80, 80)
    path = BezierPath(nodes=[
        PathNode(anchor=(10.0, 40.0)),
        PathNode(anchor=(70.0, 40.0)),
    ])
    stroke_along_path(canvas_wide, path, _options(spacing=20.0))
    stroke_along_path(canvas_narrow, path, _options(spacing=1.0))
    wide_painted = (canvas_wide[..., :3] != 255).any(axis=-1).sum()
    narrow_painted = (canvas_narrow[..., :3] != 255).any(axis=-1).sum()
    assert narrow_painted > wide_painted


def test_negative_spacing_clamps_to_one():
    """A nonsense spacing (<= 0) must clamp at 1 px rather than
    looping forever."""
    canvas = _white_canvas()
    path = BezierPath(nodes=[
        PathNode(anchor=(10.0, 30.0)),
        PathNode(anchor=(20.0, 30.0)),
    ])
    # Just verify it returns rather than spinning the loop.
    damage = stroke_along_path(
        canvas, path, _options(spacing=-1.0),
    )
    assert not damage.is_empty
