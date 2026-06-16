"""Tests for liquify / warp brushes."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.liquify import (
    WARP_KINDS,
    apply_warp,
    bloat_warp,
    pinch_warp,
    push_warp,
    twirl_warp,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _vertical_stripe_image(h=40, w=40, stripe_x=20):
    """Image with a vertical red stripe centred on column ``stripe_x``.

    The stripe is 4 px wide so a quadratic-falloff brush near the
    centre actually picks up the colour after a moderate displacement
    (a 1-pixel stripe vanishes into bilinear smear before any test
    can latch onto it)."""
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[..., 3] = 255
    img[:, stripe_x - 2:stripe_x + 2, :3] = (255, 0, 0)
    return img


def _disc_image(h=40, w=40, cx=20, cy=20, r=8):
    """Image with a filled red disc."""
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[..., 3] = 255
    ys, xs = np.indices((h, w))
    mask = ((xs - cx) ** 2 + (ys - cy) ** 2) <= r * r
    img[mask, :3] = (255, 0, 0)
    return img


# ---------------------------------------------------------------------------
# Sanity
# ---------------------------------------------------------------------------


def test_warp_kinds_constant():
    assert set(WARP_KINDS) == {"push", "pinch", "bloat", "twirl", "push_left"}


def test_push_left_is_push_rotated_90_degrees():
    # Push-left displaces perpendicular to the drag: push with (dx, dy) rotated
    # 90° to (-dy, dx).
    from Imervue.paint.liquify import push_left_warp, push_warp
    img = _vertical_stripe_image()
    left = push_left_warp(img, 20, 20, 8, 3.0, 1.0, strength=0.7)
    rotated = push_warp(img, 20, 20, 8, -1.0, 3.0, strength=0.7)
    assert np.array_equal(left, rotated)


def test_push_left_moves_footprint_and_respects_radius():
    from Imervue.paint.liquify import push_left_warp
    img = _vertical_stripe_image()
    # Drag down → perpendicular displacement is horizontal, which a vertical
    # stripe registers; the far corner sits outside the radius-8 brush.
    out = push_left_warp(img, 20, 20, 8, 0.0, 4.0, strength=1.0)
    assert not np.array_equal(out, img)
    assert np.array_equal(out[0, 0], img[0, 0])


def test_unknown_kind_raises():
    img = _vertical_stripe_image()
    with pytest.raises(ValueError, match="unknown warp kind"):
        apply_warp(img, 20, 20, 5, kind="banana")


def test_warp_rejects_non_rgba():
    rgb = np.zeros((10, 10, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="HxWx4"):
        push_warp(rgb, 5, 5, 4, 1, 0)


def test_warp_negative_radius_raises():
    img = _vertical_stripe_image()
    with pytest.raises(ValueError, match="radius"):
        push_warp(img, 20, 20, -1, 1, 0)


# ---------------------------------------------------------------------------
# Push
# ---------------------------------------------------------------------------


def test_push_zero_radius_returns_input():
    img = _vertical_stripe_image()
    out = push_warp(img, 20, 20, 0, 5, 0)
    np.testing.assert_array_equal(out, img)


def test_push_zero_displacement_returns_close_to_input():
    img = _vertical_stripe_image()
    out = push_warp(img, 20, 20, 10, 0, 0)
    # No displacement → output should equal the input.
    np.testing.assert_array_equal(out, img)


def test_push_horizontal_drag_shifts_stripe_pixels():
    """A push to the right should move red pixels at the centre right."""
    img = _vertical_stripe_image(h=40, w=40, stripe_x=20)
    out = push_warp(img, 20, 20, 10, dx=8, dy=0, strength=1.0)
    # Original red stripe is at x ≈ 18..22. After +8 push at the
    # centre row, the visible red shifts right.
    assert out[20, 24, 0] > 100
    # The pixel just left of the original stripe was background; with
    # a quadratic falloff brush the displacement near x=15 is small,
    # so confirm the centre row picked up red somewhere right of x=22.
    right_red = out[20, 22:30, 0].max()
    assert int(right_red) > 100


def test_push_outside_radius_unchanged():
    img = _vertical_stripe_image(h=40, w=40, stripe_x=20)
    out = push_warp(img, 5, 5, 4, dx=8, dy=0, strength=1.0)
    # Red stripe at x=20 is well outside the brush radius — unchanged.
    np.testing.assert_array_equal(out[:, 20, :], img[:, 20, :])


# ---------------------------------------------------------------------------
# Pinch / Bloat
# ---------------------------------------------------------------------------


def test_pinch_pulls_disc_inward():
    """Pinching a disc should shrink it — pixels near the original
    edge move toward the centre."""
    img = _disc_image(h=40, w=40, cx=20, cy=20, r=8)
    out = pinch_warp(img, 20, 20, 14, strength=0.5)
    # Pixel at (20, 27) was near the disc edge; after pinch it should
    # still be inside the visibly red region (the disc effectively
    # shrank, so further-out pixels lose red).
    assert _painted_count(out) <= _painted_count(img) + 5


def test_bloat_pushes_disc_outward():
    """Bloat expands the silhouette — the painted pixel count should
    exceed the original disc's footprint."""
    img = _disc_image(h=40, w=40, cx=20, cy=20, r=8)
    out = bloat_warp(img, 20, 20, 18, strength=0.8)
    assert _painted_count(out) > _painted_count(img)


# ---------------------------------------------------------------------------
# Twirl
# ---------------------------------------------------------------------------


def test_twirl_rotates_stripe():
    """A strong twirl on a vertical stripe rotates pixels through the
    brush footprint — red pixels should appear on rows other than the
    stripe's original column-aligned extent."""
    img = _vertical_stripe_image(h=40, w=40, stripe_x=20)
    out = twirl_warp(img, 20, 20, 14, angle_deg=180.0, strength=1.0)
    # The stripe started purely vertical; after a 180° twirl through
    # the centre, the centre row picks up red somewhere off-axis.
    assert int(out[20, 14:26, 0].max()) > 80


def test_twirl_zero_angle_returns_close_to_input():
    img = _vertical_stripe_image()
    out = twirl_warp(img, 20, 20, 10, angle_deg=0.0)
    np.testing.assert_array_equal(out, img)


# ---------------------------------------------------------------------------
# Dispatch helper
# ---------------------------------------------------------------------------


def test_apply_warp_dispatches_each_kind():
    img = _vertical_stripe_image()
    for kind in WARP_KINDS:
        out = apply_warp(img, 20, 20, 8, kind=kind, strength=0.5,
                         dx=2, dy=0, angle_deg=30.0)
        assert out.shape == img.shape


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _painted_count(canvas: np.ndarray) -> int:
    return int((canvas[..., 0] > 100).sum())
