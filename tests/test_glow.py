"""Tests for the diffuse-glow / Orton bloom effect."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.glow import apply_glow, screen_blend


def _rgba(rgb, alpha=255, size=(8, 8)):
    arr = np.zeros((size[0], size[1], 4), dtype=np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = rgb
    arr[..., 3] = alpha
    return arr


# ---------------------------------------------------------------------------
# screen_blend
# ---------------------------------------------------------------------------


def test_screen_blend_endpoints():
    assert screen_blend(np.array(0.0), np.array(0.0)) == pytest.approx(0.0)
    assert screen_blend(np.array(1.0), np.array(0.3)) == pytest.approx(1.0)
    assert screen_blend(np.array(0.5), np.array(0.5)) == pytest.approx(0.75)


def test_screen_blend_never_darkens():
    base = np.linspace(0, 1, 50)
    top = np.linspace(0, 1, 50)
    assert np.all(screen_blend(base, top) >= base - 1e-6)


# ---------------------------------------------------------------------------
# apply_glow
# ---------------------------------------------------------------------------


def test_amount_zero_is_identity():
    arr = _rgba((120, 80, 40))
    assert np.array_equal(apply_glow(arr, amount=0.0), arr)


def test_glow_never_darkens_rgb():
    arr = _rgba((120, 80, 40))
    out = apply_glow(arr, amount=0.8, radius=4)
    assert np.all(out[..., :3] >= arr[..., :3])


def test_glow_brightens_midtone():
    arr = _rgba((120, 80, 40))
    out = apply_glow(arr, amount=0.8, radius=4)
    assert int(out[..., :3].sum()) > int(arr[..., :3].sum())


def test_white_stays_white():
    arr = _rgba((255, 255, 255))
    out = apply_glow(arr, amount=1.0, radius=4)
    assert np.all(out[..., :3] == 255)


def test_black_stays_black():
    arr = _rgba((0, 0, 0))
    out = apply_glow(arr, amount=1.0, radius=4)
    assert np.all(out[..., :3] == 0)


def test_alpha_preserved():
    arr = _rgba((120, 80, 40), alpha=200)
    out = apply_glow(arr, amount=0.7, radius=4)
    assert np.array_equal(out[..., 3], arr[..., 3])


def test_high_threshold_suppresses_glow_on_midtone():
    arr = _rgba((120, 80, 40))
    out = apply_glow(arr, amount=1.0, radius=4, threshold=1.0)
    # A mid-tone frame is below the highlight threshold, so it barely changes.
    assert np.array_equal(out[..., :3], arr[..., :3])


def test_does_not_mutate_input():
    arr = _rgba((120, 80, 40))
    before = arr.copy()
    apply_glow(arr, amount=0.6, radius=4)
    assert np.array_equal(arr, before)


@pytest.mark.parametrize("bad", [
    np.zeros((8, 8, 3), dtype=np.uint8),
    np.zeros((8, 8, 4), dtype=np.float32),
    np.zeros((8, 8), dtype=np.uint8),
])
def test_rejects_bad_input(bad):
    with pytest.raises(ValueError, match="HxWx4 uint8"):
        apply_glow(bad)
