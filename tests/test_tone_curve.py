"""Tests for the tone curve module."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image import tone_curve as tc


class TestIsIdentity:
    def test_empty_is_identity(self):
        assert tc.is_identity_points([]) is True

    def test_straight_line_is_identity(self):
        assert tc.is_identity_points([(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)]) is True

    def test_bent_line_is_not_identity(self):
        assert tc.is_identity_points([(0.0, 0.0), (0.5, 0.7), (1.0, 1.0)]) is False


class TestBuildLut:
    def test_identity_lut_is_0_to_255(self):
        lut = tc.build_lut([])
        assert lut.tolist() == list(range(256))

    def test_black_clipping_curve(self):
        lut = tc.build_lut([(0.0, 0.2), (1.0, 1.0)])
        assert lut[0] >= 50  # 0.2 * 255 ~= 51
        assert lut[255] == 255

    def test_inversion_curve(self):
        lut = tc.build_lut([(0.0, 1.0), (1.0, 0.0)])
        assert lut[0] == 255
        assert lut[255] == 0

    def test_lut_is_monotone_for_monotone_points(self):
        lut = tc.build_lut([(0.0, 0.0), (0.3, 0.1), (0.7, 0.6), (1.0, 1.0)])
        diffs = np.diff(lut.astype(int))
        assert (diffs >= 0).all()

    def test_lut_returns_uint8_length_256(self):
        lut = tc.build_lut([(0.0, 0.0), (1.0, 1.0)])
        assert lut.dtype == np.uint8
        assert lut.shape == (256,)


class TestApplyToneCurve:
    def test_identity_leaves_array_unchanged(self):
        rng = np.random.default_rng(0)
        arr = rng.integers(0, 256, (4, 5, 4), dtype=np.uint8)
        out = tc.apply_tone_curve(arr, [])
        assert out is arr

    def test_rejects_non_rgba(self):
        arr = np.zeros((4, 5, 3), dtype=np.uint8)
        with pytest.raises(ValueError):
            tc.apply_tone_curve(arr, [(0.0, 0.5), (1.0, 1.0)])

    def test_alpha_channel_is_preserved(self):
        arr = np.full((4, 5, 4), 128, dtype=np.uint8)
        arr[..., 3] = 200
        out = tc.apply_tone_curve(arr, [(0.0, 0.0), (1.0, 0.5)])
        assert (out[..., 3] == 200).all()

    def test_per_channel_curve_only_touches_its_channel(self):
        arr = np.full((2, 2, 4), 128, dtype=np.uint8)
        out = tc.apply_tone_curve(
            arr, [], r_points=[(0.0, 0.0), (1.0, 0.0)],
        )
        assert (out[..., 0] == 0).all()
        assert (out[..., 1] == 128).all()
        assert (out[..., 2] == 128).all()

    def test_bright_curve_raises_midtone_value(self):
        arr = np.full((2, 2, 4), 128, dtype=np.uint8)
        out = tc.apply_tone_curve(
            arr, [(0.0, 0.0), (0.5, 0.8), (1.0, 1.0)],
        )
        assert out[0, 0, 0] > 128
