"""Tests for the pure histogram / exposure-clipping helpers."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.histogram import (
    BIN_COUNT,
    ClipStats,
    compute_clipping,
    compute_histogram,
)


def _solid(value, *, h=4, w=5, channels=3):
    img = np.empty((h, w, channels), dtype=np.uint8)
    img[..., :3] = value
    if channels == 4:
        img[..., 3] = 255
    return img


class TestComputeHistogram:
    def test_counts_sum_to_pixel_total(self):
        rng = np.random.default_rng(0)
        img = rng.integers(0, 256, size=(10, 8, 3), dtype=np.uint8)
        hist = compute_histogram(img)
        total = 10 * 8
        for channel in (hist.r, hist.g, hist.b, hist.luma):
            assert channel.shape == (BIN_COUNT,)
            assert int(channel.sum()) == total

    def test_solid_grey_lands_in_one_bin(self):
        hist = compute_histogram(_solid(128))
        assert hist.r[128] == 20 and hist.r.sum() == 20
        # Luma of a neutral grey is the same grey value.
        assert hist.luma[128] == 20

    def test_luma_uses_rec601_weights(self):
        # Pure red → luma round(0.299*255) = 76.
        img = np.zeros((1, 1, 3), dtype=np.uint8)
        img[..., 0] = 255
        hist = compute_histogram(img)
        assert hist.luma[76] == 1

    def test_alpha_channel_is_ignored(self):
        rgb = _solid(200, channels=3)
        rgba = _solid(200, channels=4)
        rgba[..., 3] = 0  # fully transparent must not change the RGB histogram
        assert np.array_equal(compute_histogram(rgb).r, compute_histogram(rgba).r)

    @pytest.mark.parametrize("bad", [
        np.zeros((4, 4), dtype=np.uint8),           # 2-D
        np.zeros((4, 4, 2), dtype=np.uint8),         # 2 channels
        np.zeros((4, 4, 3), dtype=np.float32),       # wrong dtype
    ])
    def test_invalid_image_raises(self, bad):
        with pytest.raises(ValueError, match="HxWx3/4 uint8"):
            compute_histogram(bad)


class TestComputeClipping:
    def test_midtone_image_has_no_clipping(self):
        stats = compute_clipping(_solid(128))
        assert stats == ClipStats(over_fraction=0.0, under_fraction=0.0)

    def test_all_white_is_fully_over(self):
        stats = compute_clipping(_solid(255))
        assert stats.over_fraction == 1.0
        assert stats.under_fraction == 0.0

    def test_all_black_is_fully_under(self):
        stats = compute_clipping(_solid(0))
        assert stats.under_fraction == 1.0
        assert stats.over_fraction == 0.0

    def test_over_fires_on_any_single_blown_channel(self):
        # One blown channel (red) is enough to flag a highlight.
        img = _solid(100)
        img[..., 0] = 255
        assert compute_clipping(img).over_fraction == 1.0

    def test_under_needs_all_channels_dark(self):
        # A single dark channel is NOT a crushed shadow — colour detail remains.
        img = _solid(0)
        img[..., 1] = 40
        assert compute_clipping(img).under_fraction == 0.0

    def test_half_clipped_reports_half_fraction(self):
        img = _solid(128, h=2, w=2)
        img[0, :, :] = 255  # top row blown
        assert compute_clipping(img).over_fraction == pytest.approx(0.5)

    def test_threshold_boundaries(self):
        # Pixels at exactly 254 are >= the default high (clipped); 253 is not.
        assert compute_clipping(_solid(254)).over_fraction == 1.0
        assert compute_clipping(_solid(253)).over_fraction == 0.0
        # And 1 is <= the default low (crushed); 2 is not.
        assert compute_clipping(_solid(1)).under_fraction == 1.0
        assert compute_clipping(_solid(2)).under_fraction == 0.0

    def test_custom_thresholds_are_honoured_and_clamped(self):
        img = _solid(200)
        assert compute_clipping(img, high=200).over_fraction == 1.0
        assert compute_clipping(img, high=201).over_fraction == 0.0
        # Out-of-range thresholds clamp rather than crash.
        assert compute_clipping(_solid(255), high=999).over_fraction == 1.0

    def test_empty_image_reports_no_clipping(self):
        empty = np.zeros((0, 0, 3), dtype=np.uint8)
        assert compute_clipping(empty) == ClipStats(0.0, 0.0)

    def test_invalid_image_raises(self):
        with pytest.raises(ValueError, match="HxWx3/4 uint8"):
            compute_clipping(np.zeros((3, 3), dtype=np.uint8))
