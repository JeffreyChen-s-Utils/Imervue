"""Tests for variable-density tonal halftone."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.manga_effects import DamageRect, render_tonal_halftone


def _solid_source(rgb, shape=(40, 40)):
    img = np.zeros((*shape, 4), dtype=np.uint8)
    img[..., :3] = rgb
    img[..., 3] = 255
    return img


def _white_canvas(shape=(40, 40)):
    return np.full((*shape, 4), 255, dtype=np.uint8)


def _painted_count(canvas, color):
    """Count pixels matching the dot colour on all three channels."""
    r, g, b = color
    return int(
        ((canvas[..., 0] == r)
         & (canvas[..., 1] == g)
         & (canvas[..., 2] == b)).sum()
    )


# ---------------------------------------------------------------------------
# Sanity
# ---------------------------------------------------------------------------


def test_render_tonal_halftone_returns_damage_rect():
    canvas = _white_canvas()
    source = _solid_source((50, 50, 50))   # mid-dark
    rect = render_tonal_halftone(canvas, source, dot_max_radius=3, spacing=10)
    assert isinstance(rect, DamageRect)


def test_render_tonal_halftone_rejects_shape_mismatch():
    canvas = _white_canvas((40, 40))
    bad_source = _solid_source((50, 50, 50), shape=(20, 20))
    with pytest.raises(ValueError, match="does not match"):
        render_tonal_halftone(canvas, bad_source)


def test_render_tonal_halftone_rejects_zero_spacing():
    canvas = _white_canvas()
    source = _solid_source((100, 100, 100))
    with pytest.raises(ValueError, match="spacing"):
        render_tonal_halftone(canvas, source, spacing=0.0)


def test_render_tonal_halftone_rejects_negative_radius():
    canvas = _white_canvas()
    source = _solid_source((100, 100, 100))
    with pytest.raises(ValueError, match="dot_max_radius"):
        render_tonal_halftone(canvas, source, dot_max_radius=-1.0)


def test_render_tonal_halftone_rejects_non_rgba_canvas():
    canvas = np.zeros((10, 10, 3), dtype=np.uint8)
    source = _solid_source((100, 100, 100), shape=(10, 10))
    with pytest.raises(ValueError, match="HxWx4"):
        render_tonal_halftone(canvas, source)


# ---------------------------------------------------------------------------
# Tonal mapping
# ---------------------------------------------------------------------------


def test_pure_white_source_produces_no_dots():
    canvas = _white_canvas()
    source = _solid_source((255, 255, 255))   # max luminance
    rect = render_tonal_halftone(canvas, source, dot_max_radius=4, spacing=10)
    # No dot pixels painted → empty damage rect.
    assert rect.is_empty
    # Canvas unchanged.
    assert (canvas == 255).all()


def test_pure_black_source_produces_full_size_dots():
    canvas = _white_canvas()
    black = _solid_source((0, 0, 0))   # min luminance
    render_tonal_halftone(canvas, black, dot_max_radius=4, spacing=10)
    # Painted pixel count is high (close to π * r² * grid_count).
    assert _painted_count(canvas, (0, 0, 0)) > 50


def test_dark_source_produces_more_paint_than_light():
    """Darker source ⇒ bigger dots ⇒ more painted pixels."""
    light_canvas = _white_canvas()
    dark_canvas = _white_canvas()
    light = _solid_source((220, 220, 220))   # mostly white
    dark = _solid_source((30, 30, 30))       # mostly black
    render_tonal_halftone(light_canvas, light, dot_max_radius=5, spacing=10)
    render_tonal_halftone(dark_canvas, dark, dot_max_radius=5, spacing=10)
    assert _painted_count(dark_canvas, (0, 0, 0)) > _painted_count(
        light_canvas, (0, 0, 0),
    )


def test_invert_reverses_luminance_relationship():
    """With invert=True, light source produces big dots and dark
    source produces small / no dots — the opposite of the default."""
    canvas_normal = _white_canvas()
    canvas_inverted = _white_canvas()
    light = _solid_source((220, 220, 220))
    render_tonal_halftone(
        canvas_normal, light, dot_max_radius=5, spacing=10,
    )
    render_tonal_halftone(
        canvas_inverted, light, dot_max_radius=5, spacing=10, invert=True,
    )
    # Light source: normal halftone produces few dots, invert produces many.
    assert _painted_count(canvas_inverted, (0, 0, 0)) > _painted_count(
        canvas_normal, (0, 0, 0),
    )


def test_zero_dot_max_radius_paints_nothing():
    canvas = _white_canvas()
    source = _solid_source((0, 0, 0))   # darkest possible
    rect = render_tonal_halftone(
        canvas, source, dot_max_radius=0.0, spacing=10,
    )
    assert rect.is_empty
    assert (canvas == 255).all()


def test_color_argument_changes_dot_color():
    canvas = _white_canvas()
    source = _solid_source((0, 0, 0))
    render_tonal_halftone(
        canvas, source, dot_max_radius=4, spacing=10,
        color=(255, 100, 0),
    )
    assert _painted_count(canvas, (255, 100, 0)) > 50


def test_gradient_source_produces_density_gradient():
    """A horizontal grayscale gradient source should produce more
    painted pixels on the dark (left) half than the light (right)
    half."""
    h, w = 40, 80
    canvas = _white_canvas((h, w))
    source = np.zeros((h, w, 4), dtype=np.uint8)
    source[..., 3] = 255
    for x in range(w):
        # x=0 is dark, x=w-1 is light.
        v = int(255 * x / (w - 1))
        source[:, x, :3] = v
    render_tonal_halftone(canvas, source, dot_max_radius=5, spacing=10)
    left_paint = _painted_count(canvas[:, : w // 2], (0, 0, 0))
    right_paint = _painted_count(canvas[:, w // 2:], (0, 0, 0))
    assert left_paint > right_paint
