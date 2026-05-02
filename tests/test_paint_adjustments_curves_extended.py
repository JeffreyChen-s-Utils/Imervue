"""Tests for per-RGB-channel curves added in 15a."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.adjustments import Adjustment, apply_adjustment


def _solid(rgb, h=4, w=4):
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[..., 0] = rgb[0]
    img[..., 1] = rgb[1]
    img[..., 2] = rgb[2]
    img[..., 3] = 255
    return img


# ---------------------------------------------------------------------------
# Backward-compat: existing ``points`` still works
# ---------------------------------------------------------------------------


def test_single_points_curve_still_inverts():
    img = _solid((10, 200, 50))
    out = apply_adjustment(
        img,
        Adjustment(
            kind="curves",
            params={"points": [[0, 255], [255, 0]]},
        ),
    )
    assert abs(int(out[0, 0, 0]) - 245) <= 2
    assert abs(int(out[0, 0, 1]) - 55) <= 2
    assert abs(int(out[0, 0, 2]) - 205) <= 2


# ---------------------------------------------------------------------------
# Per-channel curves
# ---------------------------------------------------------------------------


def test_red_only_curve_lifts_red_channel():
    """A curve that maps R via [0,128] (input 0..255 squeezed to 0..128)
    only affects the red channel; G and B stay at their original."""
    img = _solid((255, 100, 50))
    out = apply_adjustment(
        img,
        Adjustment(
            kind="curves",
            params={"points_r": [[0, 0], [255, 128]]},
        ),
    )
    # R at input 255 maps to 128.
    assert abs(int(out[0, 0, 0]) - 128) <= 1
    # G and B unaffected.
    assert int(out[0, 0, 1]) == 100
    assert int(out[0, 0, 2]) == 50


def test_green_only_curve_inverts_green_channel():
    img = _solid((100, 200, 50))
    out = apply_adjustment(
        img,
        Adjustment(
            kind="curves",
            params={"points_g": [[0, 255], [255, 0]]},
        ),
    )
    # G inverted: 200 → 55.
    assert abs(int(out[0, 0, 1]) - 55) <= 2
    # R, B unchanged.
    assert int(out[0, 0, 0]) == 100
    assert int(out[0, 0, 2]) == 50


def test_blue_only_curve_inverts_blue_channel():
    img = _solid((50, 100, 200))
    out = apply_adjustment(
        img,
        Adjustment(
            kind="curves",
            params={"points_b": [[0, 255], [255, 0]]},
        ),
    )
    assert abs(int(out[0, 0, 2]) - 55) <= 2
    assert int(out[0, 0, 0]) == 50
    assert int(out[0, 0, 1]) == 100


def test_per_channel_curves_can_be_combined():
    """All three per-channel curves applied simultaneously."""
    img = _solid((255, 255, 255))
    out = apply_adjustment(
        img,
        Adjustment(
            kind="curves",
            params={
                "points_r": [[0, 0], [255, 100]],
                "points_g": [[0, 0], [255, 150]],
                "points_b": [[0, 0], [255, 50]],
            },
        ),
    )
    assert abs(int(out[0, 0, 0]) - 100) <= 1
    assert abs(int(out[0, 0, 1]) - 150) <= 1
    assert abs(int(out[0, 0, 2]) - 50) <= 1


def test_base_points_apply_to_unspecified_channels():
    """A base curve plus a per-R override: R uses its own curve,
    G and B fall through to the base."""
    img = _solid((255, 255, 255))
    out = apply_adjustment(
        img,
        Adjustment(
            kind="curves",
            params={
                "points": [[0, 0], [255, 200]],   # base: 255 → 200
                "points_r": [[0, 0], [255, 100]],  # R-specific: 255 → 100
            },
        ),
    )
    assert abs(int(out[0, 0, 0]) - 100) <= 1   # used R-specific
    assert abs(int(out[0, 0, 1]) - 200) <= 1   # used base
    assert abs(int(out[0, 0, 2]) - 200) <= 1   # used base


def test_per_channel_single_point_falls_back_to_base():
    """A per-channel curve with < 2 points isn't usable on its own — it
    falls back to the base curve (or identity if no base)."""
    img = _solid((255, 255, 255))
    out = apply_adjustment(
        img,
        Adjustment(
            kind="curves",
            params={
                "points": [[0, 0], [255, 200]],   # base
                "points_r": [[128, 50]],          # only one point — invalid
            },
        ),
    )
    # R uses the base curve.
    assert abs(int(out[0, 0, 0]) - 200) <= 1


def test_per_channel_alpha_unchanged():
    img = _solid((100, 100, 100))
    img[..., 3] = 200
    out = apply_adjustment(
        img,
        Adjustment(
            kind="curves",
            params={"points_r": [[0, 255], [255, 0]]},
        ),
    )
    assert (out[..., 3] == 200).all()


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("key", ["points_r", "points_g", "points_b"])
def test_per_channel_curves_round_trip_via_dict(key):
    a = Adjustment(
        kind="curves",
        params={key: [[0, 0], [128, 200], [255, 255]]},
    )
    rebuilt = Adjustment.from_dict(a.to_dict())
    assert rebuilt.params[key] == [[0, 0], [128, 200], [255, 255]]
