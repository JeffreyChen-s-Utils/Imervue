"""Tests for the time-lapse deflicker module."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.deflicker import (
    DeflickerOptions,
    apply_gain,
    compute_gain_factors,
    deflicker_frames,
    frame_luminance_means,
)


def _solid(h, w, rgb):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = rgb
    arr[..., 3] = 255
    return arr


# ---------------------------------------------------------------------------
# frame_luminance_means
# ---------------------------------------------------------------------------


def test_frame_luminance_means_empty_returns_empty_array():
    out = frame_luminance_means([])
    assert out.shape == (0,)


def test_frame_luminance_means_uniform_frames():
    frames = [_solid(8, 8, (100, 100, 100)),
              _solid(8, 8, (200, 200, 200))]
    means = frame_luminance_means(frames)
    assert means.shape == (2,)
    assert means[0] == pytest.approx(100.0, abs=1)
    assert means[1] == pytest.approx(200.0, abs=1)


def test_frame_luminance_rejects_non_rgba():
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        frame_luminance_means([arr])


# ---------------------------------------------------------------------------
# compute_gain_factors
# ---------------------------------------------------------------------------


def test_compute_gains_global_mean_pulls_outliers_inward():
    """A bright outlier frame should get gain < 1, a dark one gain > 1."""
    means = np.array([50, 100, 150], dtype=np.float32)
    opts = DeflickerOptions(target_mode="global_mean")
    gains = compute_gain_factors(means, opts)
    assert gains[0] > 1.0   # boosts the dark frame
    assert gains[2] < 1.0   # tames the bright frame
    assert gains[1] == pytest.approx(1.0, abs=0.05)


def test_compute_gains_clamped_to_min_max():
    means = np.array([1, 100, 1000], dtype=np.float32)
    opts = DeflickerOptions(
        target_mode="global_mean", max_gain=2.0, min_gain=0.5,
    )
    gains = compute_gain_factors(means, opts)
    assert gains.max() <= 2.0
    assert gains.min() >= 0.5


def test_compute_gains_handles_zero_mean_safely():
    """Black frames (mean ≈ 0) shouldn't blow up the gain computation."""
    means = np.array([0.0, 100.0, 200.0], dtype=np.float32)
    gains = compute_gain_factors(means, DeflickerOptions(target_mode="global_mean"))
    assert np.isfinite(gains).all()


def test_compute_gains_rolling_window_smooths_jitter():
    """Frame-to-frame jitter should be reduced compared to no smoothing."""
    means = np.array([100, 110, 90, 100, 108, 92, 100], dtype=np.float32)
    rolled = compute_gain_factors(means, DeflickerOptions(rolling_window=3))
    # Rolling-mean correction should pull means toward each other.
    corrected = means * rolled
    spread_before = means.max() - means.min()
    spread_after = corrected.max() - corrected.min()
    assert spread_after < spread_before


# ---------------------------------------------------------------------------
# apply_gain
# ---------------------------------------------------------------------------


def test_apply_gain_brightens():
    base = _solid(4, 4, (100, 100, 100))
    out = apply_gain(base, 1.5)
    # Channels should land around 150 (clipped before going over 255)
    assert int(out[0, 0, 0]) == 150


def test_apply_gain_clips_to_255():
    base = _solid(4, 4, (200, 200, 200))
    out = apply_gain(base, 2.0)
    assert (out[..., :3] == 255).all()


def test_apply_gain_preserves_alpha():
    base = _solid(4, 4, (100, 100, 100))
    base[..., 3] = 80
    out = apply_gain(base, 1.5)
    assert (out[..., 3] == 80).all()


def test_apply_gain_rejects_non_rgba():
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        apply_gain(arr, 1.5)


# ---------------------------------------------------------------------------
# deflicker_frames (end-to-end)
# ---------------------------------------------------------------------------


def test_deflicker_frames_reduces_brightness_spread():
    """Three frames of varying brightness should converge after deflicker."""
    frames = [
        _solid(8, 8, (50, 50, 50)),
        _solid(8, 8, (150, 150, 150)),
        _solid(8, 8, (100, 100, 100)),
    ]
    out = deflicker_frames(frames, DeflickerOptions(target_mode="global_mean"))
    means_before = frame_luminance_means(frames)
    means_after = frame_luminance_means(out)
    spread_before = means_before.max() - means_before.min()
    spread_after = means_after.max() - means_after.min()
    assert spread_after < spread_before


def test_deflicker_handles_empty_input():
    assert deflicker_frames([]) == []
