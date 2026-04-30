"""Tests for Channel Mixer + Posterize + Threshold adjustments (15c)."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.adjustments import (
    ADJUSTMENT_KINDS,
    Adjustment,
    apply_adjustment,
)


def _solid(rgb, h=4, w=4):
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[..., 0] = rgb[0]
    img[..., 1] = rgb[1]
    img[..., 2] = rgb[2]
    img[..., 3] = 255
    return img


def test_registry_includes_new_kinds():
    assert "channel_mixer" in ADJUSTMENT_KINDS
    assert "posterize" in ADJUSTMENT_KINDS
    assert "threshold" in ADJUSTMENT_KINDS


# ---------------------------------------------------------------------------
# Channel Mixer
# ---------------------------------------------------------------------------


def test_channel_mixer_identity_preserves_pixels():
    img = _solid((128, 64, 200))
    out = apply_adjustment(img, Adjustment(kind="channel_mixer"))
    np.testing.assert_array_equal(out[..., :3], img[..., :3])


def test_channel_mixer_swap_red_and_blue():
    img = _solid((255, 0, 0))   # pure red
    out = apply_adjustment(img, Adjustment(
        kind="channel_mixer",
        params={
            "output_red": [0.0, 0.0, 1.0, 0.0],   # red comes from blue input
            "output_blue": [1.0, 0.0, 0.0, 0.0],   # blue comes from red input
        },
    ))
    # Red input went into the blue output channel.
    assert int(out[0, 0, 0]) == 0
    assert int(out[0, 0, 2]) == 255


def test_channel_mixer_constant_offset_brightens():
    img = _solid((100, 100, 100))
    out = apply_adjustment(img, Adjustment(
        kind="channel_mixer",
        params={
            "output_red": [1.0, 0.0, 0.0, 0.5],   # +50%
        },
    ))
    # 100 + 0.5 * 255 = 227.5 → 228.
    assert int(out[0, 0, 0]) >= 220


def test_channel_mixer_corrupt_row_falls_back_to_default():
    img = _solid((128, 128, 128))
    out = apply_adjustment(img, Adjustment(
        kind="channel_mixer",
        params={"output_red": "garbage"},
    ))
    # Falls back to identity row [1, 0, 0, 0] → R unchanged.
    assert int(out[0, 0, 0]) == 128


def test_channel_mixer_alpha_unchanged():
    img = _solid((128, 128, 128))
    img[..., 3] = 200
    out = apply_adjustment(img, Adjustment(kind="channel_mixer"))
    assert (out[..., 3] == 200).all()


# ---------------------------------------------------------------------------
# Posterize
# ---------------------------------------------------------------------------


def test_posterize_reduces_distinct_values():
    """A smooth gradient should collapse to a small number of levels."""
    img = np.zeros((1, 256, 4), dtype=np.uint8)
    img[..., 3] = 255
    img[0, :, 0] = np.arange(256, dtype=np.uint8)
    out = apply_adjustment(img, Adjustment(
        kind="posterize", params={"levels": 4},
    ))
    distinct = np.unique(out[0, :, 0])
    assert len(distinct) == 4


def test_posterize_levels_two_yields_black_and_white():
    img = np.zeros((1, 256, 4), dtype=np.uint8)
    img[..., 3] = 255
    img[0, :, 0] = np.arange(256, dtype=np.uint8)
    img[0, :, 1] = np.arange(256, dtype=np.uint8)
    img[0, :, 2] = np.arange(256, dtype=np.uint8)
    out = apply_adjustment(img, Adjustment(
        kind="posterize", params={"levels": 2},
    ))
    distinct = set(np.unique(out[..., 0]).tolist())
    assert distinct <= {0, 255}


def test_posterize_levels_clamped_below_two():
    img = _solid((100, 100, 100))
    # levels=1 clamps to 2 (the minimum valid count).
    out = apply_adjustment(img, Adjustment(
        kind="posterize", params={"levels": 1},
    ))
    assert int(out[0, 0, 0]) in (0, 255)


def test_posterize_alpha_unchanged():
    img = _solid((128, 128, 128))
    img[..., 3] = 150
    out = apply_adjustment(img, Adjustment(
        kind="posterize", params={"levels": 4},
    ))
    assert (out[..., 3] == 150).all()


# ---------------------------------------------------------------------------
# Threshold
# ---------------------------------------------------------------------------


def test_threshold_pure_white_above_threshold_stays_white():
    img = _solid((255, 255, 255))
    out = apply_adjustment(img, Adjustment(
        kind="threshold", params={"threshold": 128},
    ))
    assert tuple(out[0, 0, :3]) == (255, 255, 255)


def test_threshold_pure_black_below_threshold_stays_black():
    img = _solid((0, 0, 0))
    out = apply_adjustment(img, Adjustment(
        kind="threshold", params={"threshold": 128},
    ))
    assert tuple(out[0, 0, :3]) == (0, 0, 0)


def test_threshold_yields_only_two_colors():
    """Random RGB input should produce only black or white pixels."""
    rng = np.random.default_rng(seed=1)
    img = np.zeros((4, 4, 4), dtype=np.uint8)
    img[..., :3] = rng.integers(0, 256, (4, 4, 3), dtype=np.uint8)
    img[..., 3] = 255
    out = apply_adjustment(img, Adjustment(kind="threshold"))
    distinct = set(np.unique(out[..., :3]).tolist())
    assert distinct <= {0, 255}


def test_threshold_uses_luminance_not_per_channel():
    """A pixel where R=255 but G=B=0 has luminance ≈ 76, below 128 →
    becomes black despite R being max."""
    img = _solid((255, 0, 0))
    out = apply_adjustment(img, Adjustment(
        kind="threshold", params={"threshold": 128},
    ))
    assert tuple(out[0, 0, :3]) == (0, 0, 0)


def test_threshold_alpha_unchanged():
    img = _solid((128, 128, 128))
    img[..., 3] = 200
    out = apply_adjustment(img, Adjustment(kind="threshold"))
    assert (out[..., 3] == 200).all()


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind,params", [
    ("channel_mixer", {"output_red": [0.5, 0.5, 0.0, 0.1]}),
    ("posterize", {"levels": 8}),
    ("threshold", {"threshold": 200}),
])
def test_round_trip_via_dict(kind, params):
    a = Adjustment(kind=kind, params=params)
    rebuilt = Adjustment.from_dict(a.to_dict())
    for key, value in params.items():
        assert rebuilt.params[key] == value
