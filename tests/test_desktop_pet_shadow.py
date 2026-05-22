"""Tests for the pet drop-shadow helpers.

Pure-Python — no GL needed. The canvas integration is rendering
code (covered by ``# pragma: no cover - GL needs display``), so
the unit-test surface is the math in :mod:`pet_shadow` and the
pet-window setters that thread through to the canvas.
"""
from __future__ import annotations

import pytest

from Imervue.desktop_pet.pet_shadow import (
    DEFAULT_FALLOFF_EXP,
    DEFAULT_HEIGHT_RATIO,
    DEFAULT_MAX_ALPHA,
    DEFAULT_TEXTURE_SIZE,
    DEFAULT_VERTICAL_OFFSET,
    DEFAULT_WIDTH_RATIO,
    make_shadow_pixels,
    shadow_quad_geometry,
)


# ---------------------------------------------------------------
# make_shadow_pixels
# ---------------------------------------------------------------


def test_pixels_dimensions_match_size():
    """Helper must return a size×size grid — the canvas uploads
    this verbatim with ``glTexImage2D``."""
    rows = make_shadow_pixels(size=16)
    assert len(rows) == 16
    assert all(len(row) == 16 for row in rows)


def test_pixels_center_alpha_is_max():
    """Centre pixel is fully opaque (modulo the configured max),
    so the shadow has a solid core that fades outward."""
    rows = make_shadow_pixels(size=15, max_alpha=200)
    centre = rows[7][7]
    # rgb = black, alpha at centre = max_alpha (or very close after
    # rounding through the exponent).
    assert centre[0] == 0
    assert centre[1] == 0
    assert centre[2] == 0
    assert centre[3] == 200


def test_pixels_corner_alpha_is_zero():
    """Corners are outside the inscribed circle → alpha 0."""
    rows = make_shadow_pixels(size=16)
    # Corner pixel — well outside the inscribed circle of radius 8.
    assert rows[0][0][3] == 0
    assert rows[15][15][3] == 0


def test_pixels_alpha_falloff_monotonic():
    """Moving from the centre outward, alpha must decrease (or stay
    equal due to rounding) — never increase."""
    rows = make_shadow_pixels(size=21)
    cy = 10
    last_alpha = 256
    for x in range(10, 21):
        a = rows[cy][x][3]
        assert a <= last_alpha
        last_alpha = a


def test_pixels_clamps_alpha():
    """Caller passing max_alpha=300 → clamped to 255. Defends the
    byte range from a misconfigured caller."""
    rows = make_shadow_pixels(size=5, max_alpha=300)
    centre = rows[2][2]
    assert 0 <= centre[3] <= 255


def test_pixels_zero_size_returns_single_transparent():
    """Boundary: size <= 0 → 1×1 transparent pixel rather than
    raise. Lets the caller upload *something* without special-
    casing."""
    rows = make_shadow_pixels(size=0)
    assert rows == [[(0, 0, 0, 0)]]


def test_pixels_falloff_exponent_changes_shape():
    """A higher falloff exponent makes the edge softer → alpha
    at the half-radius is lower than with falloff=1.0."""
    soft = make_shadow_pixels(size=31, falloff_exp=2.5)
    hard = make_shadow_pixels(size=31, falloff_exp=1.0)
    centre_x = 15
    half_r_x = 22   # ~7.5 px from centre — between centre and edge
    assert soft[centre_x][half_r_x][3] < hard[centre_x][half_r_x][3]


def test_default_constants_are_sane():
    """Sanity guards so a future tuning PR can't ship out-of-range
    defaults silently."""
    assert 16 <= DEFAULT_TEXTURE_SIZE <= 256
    assert 0.5 <= DEFAULT_FALLOFF_EXP <= 3.0
    assert 0 <= DEFAULT_MAX_ALPHA <= 255
    assert 0.1 <= DEFAULT_WIDTH_RATIO <= 1.0
    assert 0.1 <= DEFAULT_HEIGHT_RATIO <= 1.0
    assert 0.5 <= DEFAULT_VERTICAL_OFFSET <= 1.0


# ---------------------------------------------------------------
# shadow_quad_geometry
# ---------------------------------------------------------------


def test_quad_centered_horizontally():
    """The quad must be horizontally centred under the puppet."""
    x, y, w, h = shadow_quad_geometry((1000, 2000), scale=1.0)
    # Centre of quad along x.
    centre_x = x + w / 2
    assert centre_x == pytest.approx(500.0)


def test_quad_near_bottom_of_canvas():
    """Default vertical offset puts the quad near the bottom of
    the canvas (rigs are authored feet-at-bottom)."""
    _, y, _, h = shadow_quad_geometry((1000, 2000), scale=1.0)
    centre_y = y + h / 2
    assert centre_y > 1500.0   # well past the midpoint


def test_quad_zero_size_document_is_zero():
    """No document yet → zero-sized quad rather than crash."""
    assert shadow_quad_geometry((0, 0)) == (0.0, 0.0, 0.0, 0.0)
    assert shadow_quad_geometry((-1, 100)) == (0.0, 0.0, 0.0, 0.0)


def test_quad_scale_zero_makes_zero_quad():
    """``scale=0`` → no shadow drawn. Useful as an "invisible but
    still allocated" state for animation transitions."""
    out = shadow_quad_geometry((1000, 2000), scale=0.0)
    assert out[2] == 0.0
    assert out[3] == 0.0


def test_quad_scale_doubles_width_and_height():
    base_w = shadow_quad_geometry((1000, 2000), scale=1.0)[2]
    big_w = shadow_quad_geometry((1000, 2000), scale=2.0)[2]
    assert big_w == pytest.approx(2.0 * base_w)


def test_quad_height_is_flatter_than_width():
    """Default ratio gives a flattened ellipse (h < w)."""
    _, _, w, h = shadow_quad_geometry((1000, 2000), scale=1.0)
    assert h < w


def test_quad_uses_document_width_for_size():
    """Wider document → wider shadow."""
    _, _, w1, _ = shadow_quad_geometry((1000, 2000), scale=1.0)
    _, _, w2, _ = shadow_quad_geometry((2000, 2000), scale=1.0)
    assert w2 == pytest.approx(2.0 * w1)


def test_quad_custom_ratios_propagate():
    """User-supplied ratios override the defaults — useful for
    tuning via settings in follow-up work."""
    _, _, w, h = shadow_quad_geometry(
        (1000, 2000), scale=1.0,
        width_ratio=0.6, height_ratio=0.5,
    )
    assert w == pytest.approx(600.0)
    assert h == pytest.approx(300.0)
