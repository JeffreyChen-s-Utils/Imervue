"""Tests for the canvas view transform (pan + zoom + rotation)."""
from __future__ import annotations

import math

import pytest

from Imervue.paint.view_transform import (
    ViewTransform,
    image_to_screen,
    normalise_rotation,
    reset_rotation,
    rotate_around,
    screen_to_image,
)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_default_transform_is_identity():
    t = ViewTransform()
    assert t.pan_x == pytest.approx(0.0) and t.pan_y == pytest.approx(0.0)
    assert t.zoom == pytest.approx(1.0)
    assert t.rotation_deg == pytest.approx(0.0)


def test_zero_zoom_rejected():
    with pytest.raises(ValueError, match="zoom"):
        ViewTransform(zoom=0.0)


def test_negative_zoom_rejected():
    with pytest.raises(ValueError, match="zoom"):
        ViewTransform(zoom=-2.0)


# ---------------------------------------------------------------------------
# Round trip — image ↔ screen
# ---------------------------------------------------------------------------


def test_identity_round_trip():
    t = ViewTransform()
    screen = (123.0, 456.0)
    image = screen_to_image(t, screen)
    assert image_to_screen(t, image) == pytest.approx(screen)


def test_pan_only_round_trip():
    t = ViewTransform(pan_x=50.0, pan_y=-20.0)
    image = screen_to_image(t, (100.0, 100.0))
    assert image_to_screen(t, image) == pytest.approx((100.0, 100.0))


def test_zoom_only_round_trip():
    t = ViewTransform(zoom=2.0)
    image = screen_to_image(t, (200.0, 100.0))
    assert image_to_screen(t, image) == pytest.approx((200.0, 100.0))


def test_rotation_only_round_trip():
    t = ViewTransform(rotation_deg=37.5)
    screen = (123.0, 456.0)
    image = screen_to_image(t, screen)
    assert image_to_screen(t, image) == pytest.approx(screen, abs=1e-9)


def test_full_combo_round_trip():
    t = ViewTransform(pan_x=20.0, pan_y=-15.0, zoom=1.7, rotation_deg=45.0)
    screen = (200.0, 300.0)
    image = screen_to_image(t, screen)
    assert image_to_screen(t, image) == pytest.approx(screen)


# ---------------------------------------------------------------------------
# Geometric sanity
# ---------------------------------------------------------------------------


def test_image_origin_at_pan_with_zero_rotation():
    """At rotation=0, image (0, 0) maps to (pan_x, pan_y) on screen."""
    t = ViewTransform(pan_x=42.0, pan_y=-7.0, zoom=2.0)
    screen = image_to_screen(t, (0.0, 0.0))
    assert screen == pytest.approx((42.0, -7.0))


def test_rotation_90_swaps_axes():
    """A 90° rotation maps image (10, 0) onto screen (0, 10) when
    pan = 0 and zoom = 1."""
    t = ViewTransform(rotation_deg=90.0)
    screen = image_to_screen(t, (10.0, 0.0))
    assert screen == pytest.approx((0.0, 10.0))


def test_zoom_scales_distance():
    t = ViewTransform(zoom=3.0)
    screen = image_to_screen(t, (5.0, 0.0))
    assert screen == pytest.approx((15.0, 0.0))


# ---------------------------------------------------------------------------
# rotate_around
# ---------------------------------------------------------------------------


def test_rotate_around_pivot_keeps_pivot_stationary():
    """The classic 'rotate around the cursor' UX guarantee."""
    t = ViewTransform(pan_x=50.0, pan_y=50.0, zoom=1.5)
    pivot = (200.0, 100.0)
    rotated = rotate_around(t, pivot, 45.0)
    pivot_after = image_to_screen(rotated, screen_to_image(t, pivot))
    assert pivot_after == pytest.approx(pivot)


def test_rotate_around_changes_rotation_field():
    t = ViewTransform()
    rotated = rotate_around(t, (0.0, 0.0), 30.0)
    assert rotated.rotation_deg == pytest.approx(30.0)


def test_rotate_around_wraps_into_canonical_range():
    t = ViewTransform()
    rotated = rotate_around(t, (0.0, 0.0), 250.0)
    assert -180.0 < rotated.rotation_deg <= 180.0


def test_rotate_around_full_turn_is_identity_visually():
    """Rotating by exactly 360° must leave every screen point
    visible at the same image position (within float epsilon)."""
    t = ViewTransform(pan_x=20.0, pan_y=30.0, zoom=2.0, rotation_deg=15.0)
    rotated = rotate_around(t, (100.0, 100.0), 360.0)
    # Sample a few points and verify the image-space mapping matches
    # the original transform.
    for screen in [(0.0, 0.0), (50.0, 50.0), (123.4, 567.8)]:
        before = screen_to_image(t, screen)
        after = screen_to_image(rotated, screen)
        assert after == pytest.approx(before, abs=1e-6)


# ---------------------------------------------------------------------------
# reset_rotation / normalise_rotation
# ---------------------------------------------------------------------------


def test_reset_rotation_zeroes_angle_keeping_pan_zoom():
    t = ViewTransform(pan_x=20.0, pan_y=30.0, zoom=2.0, rotation_deg=45.0)
    cleared = reset_rotation(t)
    assert cleared.rotation_deg == pytest.approx(0.0)
    assert cleared.pan_x == pytest.approx(20.0)
    assert cleared.pan_y == pytest.approx(30.0)
    assert cleared.zoom == pytest.approx(2.0)


def test_normalise_rotation_wraps_large_value():
    t = ViewTransform(rotation_deg=720.0)
    n = normalise_rotation(t)
    assert -180.0 < n.rotation_deg <= 180.0


def test_normalise_rotation_preserves_canonical_value():
    t = ViewTransform(rotation_deg=37.5)
    n = normalise_rotation(t)
    assert n.rotation_deg == pytest.approx(37.5)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_screen_to_image_with_tiny_zoom_does_not_explode():
    """A zoom of 0.0001 mustn't produce inf / NaN — the helpers
    must be defensible when the user has zoomed all the way out."""
    t = ViewTransform(zoom=0.0001)
    out = screen_to_image(t, (100.0, 100.0))
    assert math.isfinite(out[0])
    assert math.isfinite(out[1])
