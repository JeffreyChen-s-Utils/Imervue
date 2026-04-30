"""Tests for text-along-path rendering."""
from __future__ import annotations

import math

import numpy as np
import pytest

from Imervue.paint.text_on_path import (
    cumulative_distances,
    path_length,
    render_text_on_path,
    sample_path,
)


# ---------------------------------------------------------------------------
# Pure-math helpers
# ---------------------------------------------------------------------------


def test_path_length_empty_path_is_zero():
    assert path_length([]) == 0.0


def test_path_length_single_point_is_zero():
    assert path_length([(0.0, 0.0)]) == 0.0


def test_path_length_horizontal_segment():
    assert path_length([(0.0, 0.0), (10.0, 0.0)]) == pytest.approx(10.0)


def test_path_length_diagonal_pythagorean():
    length = path_length([(0.0, 0.0), (3.0, 4.0)])
    assert length == pytest.approx(5.0)


def test_path_length_polyline_sums_segments():
    length = path_length([(0.0, 0.0), (10.0, 0.0), (10.0, 5.0)])
    assert length == pytest.approx(15.0)


def test_cumulative_distances_starts_at_zero():
    cum = cumulative_distances([(0.0, 0.0), (5.0, 0.0), (5.0, 12.0)])
    assert cum[0] == 0.0
    assert cum[-1] == pytest.approx(17.0)


def test_cumulative_distances_empty_returns_empty():
    assert cumulative_distances([]) == []


def test_sample_path_at_zero_returns_first_point():
    pts = [(2.0, 3.0), (12.0, 3.0)]
    x, y, _ = sample_path(pts, 0.0)
    assert x == pytest.approx(2.0)
    assert y == pytest.approx(3.0)


def test_sample_path_at_full_length_reaches_last_point():
    pts = [(0.0, 0.0), (10.0, 0.0)]
    x, y, _ = sample_path(pts, 10.0)
    assert x == pytest.approx(10.0)
    assert y == pytest.approx(0.0)


def test_sample_path_horizontal_tangent_zero():
    pts = [(0.0, 0.0), (10.0, 0.0)]
    _, _, angle = sample_path(pts, 5.0)
    assert angle == pytest.approx(0.0)


def test_sample_path_vertical_tangent_pi_over_two():
    pts = [(0.0, 0.0), (0.0, 10.0)]
    _, _, angle = sample_path(pts, 5.0)
    assert angle == pytest.approx(math.pi / 2)


def test_sample_path_clamps_distance_above_length():
    pts = [(0.0, 0.0), (10.0, 0.0)]
    x, _, _ = sample_path(pts, 50.0)
    assert x == pytest.approx(10.0)


def test_sample_path_clamps_negative_distance():
    pts = [(2.0, 3.0), (12.0, 3.0)]
    x, y, _ = sample_path(pts, -5.0)
    assert x == pytest.approx(2.0)
    assert y == pytest.approx(3.0)


def test_sample_path_polyline_corner_uses_following_segment():
    pts = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
    x, y, angle = sample_path(pts, 13.0)   # 3 px past the corner
    assert x == pytest.approx(10.0)
    assert y == pytest.approx(3.0)
    assert angle == pytest.approx(math.pi / 2)


def test_sample_path_rejects_single_point():
    with pytest.raises(ValueError, match="2 points"):
        sample_path([(0.0, 0.0)], 0.0)


# ---------------------------------------------------------------------------
# Qt renderer
# ---------------------------------------------------------------------------


def test_render_text_on_path_returns_canvas_sized_buffer(qapp):
    out = render_text_on_path(
        "Hello",
        [(0.0, 30.0), (200.0, 30.0)],
        canvas_size=(60, 200),
        size=20,
    )
    assert out.shape == (60, 200, 4)
    assert out.dtype == np.uint8


def test_render_text_on_path_paints_along_path(qapp):
    out = render_text_on_path(
        "Hello",
        [(0.0, 30.0), (200.0, 30.0)],
        canvas_size=(60, 200),
        size=24, color=(0, 0, 0),
    )
    # Some pixels should be painted along the path's row band.
    band = out[10:50, :, 3]
    assert (band > 0).any()


def test_render_text_on_path_empty_text_returns_zero_canvas(qapp):
    out = render_text_on_path(
        "",
        [(0.0, 30.0), (200.0, 30.0)],
        canvas_size=(60, 200),
    )
    assert out.shape == (60, 200, 4)
    assert (out[..., 3] == 0).all()


def test_render_text_on_path_zero_length_path_returns_blank(qapp):
    out = render_text_on_path(
        "Hi",
        [(50.0, 30.0), (50.0, 30.0)],   # both points identical
        canvas_size=(60, 200),
    )
    assert (out[..., 3] == 0).all()


def test_render_text_on_path_too_short_path_drops_overflow_glyphs(qapp):
    """A 20-px path can't fit much text — extra glyphs are dropped
    rather than crashing."""
    out = render_text_on_path(
        "Hello, world!",
        [(0.0, 30.0), (20.0, 30.0)],
        canvas_size=(60, 60),
        size=24,
    )
    # Should not raise; some painted pixels (a glyph or two) appear.
    assert out.shape == (60, 60, 4)


def test_render_text_on_path_rejects_zero_canvas(qapp):
    with pytest.raises(ValueError, match="canvas_size"):
        render_text_on_path(
            "X", [(0.0, 0.0), (10.0, 0.0)], canvas_size=(0, 0),
        )


def test_render_text_on_path_rejects_short_path(qapp):
    with pytest.raises(ValueError, match="2 points"):
        render_text_on_path(
            "X", [(5.0, 5.0)], canvas_size=(40, 40),
        )


def test_render_text_on_path_curved_polyline(qapp):
    """A polyline that turns 90° should still produce a valid render
    with glyphs both on the horizontal segment and the vertical one.
    Path: 30-px horizontal then 70-px vertical; the 8-character text
    overruns the first segment so later glyphs land on the second."""
    pts = [(0.0, 30.0), (30.0, 30.0), (30.0, 100.0)]
    out = render_text_on_path(
        "ABCDEFGH", pts, canvas_size=(140, 80), size=16,
    )
    horizontal_band = out[20:40, :, 3]
    vertical_band = out[40:120, :, 3]
    assert (horizontal_band > 0).any()
    assert (vertical_band > 0).any()
