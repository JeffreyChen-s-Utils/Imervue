"""Tests for manga speed-line and halftone effect helpers."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.manga_effects import (
    DamageRect,
    render_halftone,
    render_speed_lines,
)


@pytest.fixture
def white_canvas():
    return np.full((200, 200, 4), 255, dtype=np.uint8)


def _painted_pixels(canvas: np.ndarray) -> np.ndarray:
    """Return a HxW bool mask of pixels that are not the white background."""
    return (canvas[..., :3] != 255).any(axis=-1)


# ---------------------------------------------------------------------------
# render_speed_lines — happy paths
# ---------------------------------------------------------------------------


def test_speed_lines_produces_paint(white_canvas):
    rect = render_speed_lines(
        white_canvas, centre=(100.0, 100.0),
        count=8, inner_radius=10.0, outer_radius=80.0,
    )
    assert _painted_pixels(white_canvas).any()
    assert not rect.is_empty


def test_speed_lines_leaves_inner_radius_clear(white_canvas):
    """The focal region inside ``inner_radius`` must not get inked."""
    render_speed_lines(
        white_canvas, centre=(100.0, 100.0),
        count=32, inner_radius=20.0, outer_radius=80.0,
    )
    # Pixel at the centre must remain white.
    assert tuple(white_canvas[100, 100]) == (255, 255, 255, 255)
    # A pixel well inside the inner-radius zone (5 px from centre) too.
    assert tuple(white_canvas[100, 105]) == (255, 255, 255, 255)


def test_speed_lines_count_zero_is_noop(white_canvas):
    snapshot = white_canvas.copy()
    rect = render_speed_lines(
        white_canvas, centre=(100.0, 100.0), count=0,
    )
    assert rect.is_empty
    np.testing.assert_array_equal(white_canvas, snapshot)


def test_speed_lines_full_circle_paints_all_quadrants(white_canvas):
    render_speed_lines(
        white_canvas, centre=(100.0, 100.0),
        count=64, inner_radius=10.0, outer_radius=80.0,
    )
    painted = _painted_pixels(white_canvas)
    # Each quadrant should have at least one painted pixel.
    assert painted[:100, :100].any()
    assert painted[:100, 100:].any()
    assert painted[100:, :100].any()
    assert painted[100:, 100:].any()


def test_speed_lines_partial_sweep_paints_only_one_quadrant(white_canvas):
    render_speed_lines(
        white_canvas, centre=(100.0, 100.0),
        count=32, inner_radius=10.0, outer_radius=80.0,
        angle_start_deg=0.0, angle_end_deg=90.0,
    )
    painted = _painted_pixels(white_canvas)
    # Sweep 0..90 corresponds (in image y-down coords) to the +x / +y
    # quadrant (rows below centre, cols right of centre). Other
    # quadrants should be untouched.
    assert painted[100:, 100:].any()
    assert not painted[:100, :100].any()
    assert not painted[:100, 100:].any()


def test_speed_lines_color_is_applied(white_canvas):
    render_speed_lines(
        white_canvas, centre=(100.0, 100.0),
        count=8, inner_radius=10.0, outer_radius=80.0,
        color=(255, 0, 0),
    )
    painted = _painted_pixels(white_canvas)
    ys, xs = np.nonzero(painted)
    sample = white_canvas[ys[0], xs[0]]
    assert tuple(sample) == (255, 0, 0, 255)


def test_speed_lines_thicker_line_paints_more_pixels(white_canvas):
    canvas_thin = white_canvas.copy()
    canvas_thick = white_canvas.copy()
    render_speed_lines(
        canvas_thin, centre=(100.0, 100.0),
        count=16, inner_radius=10.0, outer_radius=80.0, line_width=1, seed=1,
    )
    render_speed_lines(
        canvas_thick, centre=(100.0, 100.0),
        count=16, inner_radius=10.0, outer_radius=80.0, line_width=3, seed=1,
    )
    assert _painted_pixels(canvas_thick).sum() > _painted_pixels(canvas_thin).sum()


def test_speed_lines_jitter_is_deterministic_with_seed(white_canvas):
    a = white_canvas.copy()
    b = white_canvas.copy()
    render_speed_lines(
        a, centre=(100.0, 100.0), count=16,
        inner_radius=10.0, outer_radius=80.0, length_jitter=0.5, seed=42,
    )
    render_speed_lines(
        b, centre=(100.0, 100.0), count=16,
        inner_radius=10.0, outer_radius=80.0, length_jitter=0.5, seed=42,
    )
    np.testing.assert_array_equal(a, b)


def test_speed_lines_off_canvas_centre_clips_safely(white_canvas):
    """A centre outside the canvas must not raise; the rays that
    cross the canvas still ink it."""
    render_speed_lines(
        white_canvas, centre=(-50.0, -50.0),
        count=64, inner_radius=10.0, outer_radius=400.0,
    )
    assert _painted_pixels(white_canvas).any()


# ---------------------------------------------------------------------------
# render_speed_lines — error paths
# ---------------------------------------------------------------------------


def test_speed_lines_rejects_inverted_radii(white_canvas):
    with pytest.raises(ValueError, match="inner < outer"):
        render_speed_lines(
            white_canvas, centre=(100.0, 100.0),
            inner_radius=80.0, outer_radius=20.0,
        )


def test_speed_lines_rejects_negative_inner_radius(white_canvas):
    with pytest.raises(ValueError, match="inner < outer"):
        render_speed_lines(
            white_canvas, centre=(100.0, 100.0),
            inner_radius=-5.0, outer_radius=80.0,
        )


def test_speed_lines_rejects_zero_line_width(white_canvas):
    with pytest.raises(ValueError, match="line_width"):
        render_speed_lines(
            white_canvas, centre=(100.0, 100.0),
            count=8, inner_radius=10.0, outer_radius=80.0, line_width=0,
        )


def test_speed_lines_rejects_jitter_above_one(white_canvas):
    with pytest.raises(ValueError, match="length_jitter"):
        render_speed_lines(
            white_canvas, centre=(100.0, 100.0),
            count=8, inner_radius=10.0, outer_radius=80.0,
            length_jitter=1.5,
        )


def test_speed_lines_rejects_non_rgba_canvas():
    rgb = np.zeros((50, 50, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="HxWx4"):
        render_speed_lines(rgb, centre=(25.0, 25.0))


# ---------------------------------------------------------------------------
# render_halftone — happy paths
# ---------------------------------------------------------------------------


def test_halftone_paints_a_dot_grid(white_canvas):
    rect = render_halftone(
        white_canvas, dot_radius=2.0, spacing=10.0,
    )
    assert not rect.is_empty
    painted = _painted_pixels(white_canvas)
    # Expect dot count near (200/10) * (200/10) = 400 grid centres.
    # Most have a small dot of ~13 pixels. Sanity: more than 50 dots
    # were painted, less than the canvas was filled solid.
    assert 50 < painted.sum() < painted.size


def test_halftone_dots_appear_at_grid_centres(white_canvas):
    """With angle 0, dots should sit at multiples of spacing."""
    render_halftone(
        white_canvas, dot_radius=2.0, spacing=10.0, angle_deg=0.0,
    )
    # Pixel at (10, 10) should be inside a dot.
    assert tuple(white_canvas[10, 10]) == (0, 0, 0, 255)
    # Pixel at (15, 15) (between dots) should remain white.
    assert tuple(white_canvas[15, 15]) == (255, 255, 255, 255)


def test_halftone_color_applied(white_canvas):
    render_halftone(
        white_canvas, dot_radius=2.0, spacing=10.0, color=(0, 200, 0),
    )
    painted = _painted_pixels(white_canvas)
    ys, xs = np.nonzero(painted)
    assert tuple(white_canvas[ys[0], xs[0]]) == (0, 200, 0, 255)


def test_halftone_zero_dot_radius_is_noop(white_canvas):
    snapshot = white_canvas.copy()
    rect = render_halftone(
        white_canvas, dot_radius=0.0, spacing=10.0,
    )
    assert rect.is_empty
    np.testing.assert_array_equal(white_canvas, snapshot)


def test_halftone_respects_selection_mask(white_canvas):
    """Pixels outside the selection must remain unpainted."""
    selection = np.zeros((200, 200), dtype=bool)
    selection[50:150, 50:150] = True
    render_halftone(
        white_canvas, selection=selection,
        dot_radius=2.0, spacing=10.0,
    )
    painted = _painted_pixels(white_canvas)
    # No painted pixel outside the selection rectangle.
    assert not painted[:50].any()
    assert not painted[150:].any()
    assert not painted[:, :50].any()
    assert not painted[:, 150:].any()
    # Some painted pixel inside the selection.
    assert painted[50:150, 50:150].any()


def test_halftone_damage_rect_bounds_painted_region(white_canvas):
    selection = np.zeros((200, 200), dtype=bool)
    selection[60:140, 70:130] = True
    rect = render_halftone(
        white_canvas, selection=selection,
        dot_radius=2.0, spacing=10.0,
    )
    assert isinstance(rect, DamageRect)
    # Damage rect should be within the selection rectangle.
    assert rect.x >= 70
    assert rect.y >= 60
    assert rect.x + rect.w <= 130
    assert rect.y + rect.h <= 140


# ---------------------------------------------------------------------------
# render_halftone — error paths
# ---------------------------------------------------------------------------


def test_halftone_rejects_zero_spacing(white_canvas):
    with pytest.raises(ValueError, match="spacing"):
        render_halftone(white_canvas, dot_radius=2.0, spacing=0.0)


def test_halftone_rejects_negative_radius(white_canvas):
    with pytest.raises(ValueError, match="dot_radius"):
        render_halftone(white_canvas, dot_radius=-1.0, spacing=10.0)


def test_halftone_rejects_mismatched_selection(white_canvas):
    bad_mask = np.zeros((50, 50), dtype=bool)
    with pytest.raises(ValueError, match="does not match"):
        render_halftone(
            white_canvas, selection=bad_mask,
            dot_radius=2.0, spacing=10.0,
        )


def test_halftone_rejects_non_rgba_canvas():
    rgb = np.zeros((50, 50, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="HxWx4"):
        render_halftone(rgb, dot_radius=2.0, spacing=10.0)
