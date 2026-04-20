"""Tests for compare_dialog math helpers (overlay / difference)."""
from __future__ import annotations

import numpy as np
import pytest


@pytest.fixture
def ops():
    from Imervue.gpu_image_view.actions import compare_dialog as m
    return m


def _rgba(h: int, w: int, rgb: tuple[int, int, int]) -> np.ndarray:
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = rgb
    arr[..., 3] = 255
    return arr


class TestOverlay:
    def test_alpha_zero_returns_a(self, ops):
        a = _rgba(4, 4, (255, 0, 0))
        b = _rgba(4, 4, (0, 0, 255))
        out = ops.compute_overlay(a, b, 0.0)
        # Same shape and the RGB is exactly A's — tolerate the forced alpha=255
        assert out.shape == a.shape
        assert np.array_equal(out[..., :3], a[..., :3])

    def test_alpha_one_returns_b(self, ops):
        a = _rgba(4, 4, (255, 0, 0))
        b = _rgba(4, 4, (0, 0, 255))
        out = ops.compute_overlay(a, b, 1.0)
        assert np.array_equal(out[..., :3], b[..., :3])

    def test_alpha_half_is_midpoint(self, ops):
        a = _rgba(2, 2, (200, 100, 50))
        b = _rgba(2, 2, (100, 200, 150))
        out = ops.compute_overlay(a, b, 0.5)
        expected = np.array([150, 150, 100], dtype=np.uint8)
        # Per-pixel check
        assert np.all(out[..., :3] == expected)

    def test_size_mismatch_resizes_b(self, ops):
        a = _rgba(10, 10, (128, 128, 128))
        b = _rgba(2, 2, (0, 0, 0))
        out = ops.compute_overlay(a, b, 0.5)
        assert out.shape == a.shape  # Output matches A's geometry

    def test_alpha_clamped(self, ops):
        a = _rgba(2, 2, (0, 0, 0))
        b = _rgba(2, 2, (100, 100, 100))
        out_under = ops.compute_overlay(a, b, -1.0)
        out_over = ops.compute_overlay(a, b, 2.0)
        assert np.array_equal(out_under[..., :3], a[..., :3])
        assert np.array_equal(out_over[..., :3], b[..., :3])


class TestDifference:
    def test_identical_images_produce_zero(self, ops):
        a = _rgba(4, 4, (100, 50, 200))
        b = _rgba(4, 4, (100, 50, 200))
        diff = ops.compute_difference(a, b, gain=1.0)
        assert np.all(diff[..., :3] == 0)

    def test_gain_amplifies_small_diff(self, ops):
        a = _rgba(2, 2, (100, 100, 100))
        b = _rgba(2, 2, (110, 100, 100))  # 10 on red channel
        # gain 1 → 10, gain 10 → 100
        low = ops.compute_difference(a, b, gain=1.0)
        high = ops.compute_difference(a, b, gain=10.0)
        assert high[0, 0, 0] > low[0, 0, 0]
        assert low[0, 0, 0] == 10
        assert high[0, 0, 0] == 100

    def test_gain_clamps_to_255(self, ops):
        a = _rgba(2, 2, (0, 0, 0))
        b = _rgba(2, 2, (200, 0, 0))
        # 200 * 10 = 2000 → clipped
        out = ops.compute_difference(a, b, gain=10.0)
        assert out[0, 0, 0] == 255

    def test_output_is_opaque(self, ops):
        a = _rgba(2, 2, (0, 0, 0))
        b = _rgba(2, 2, (0, 0, 0))
        out = ops.compute_difference(a, b, 1.0)
        assert np.all(out[..., 3] == 255)


class TestSplitLabel:
    def test_defaults_to_half(self, ops, qapp):
        widget = ops._SplitLabel()
        assert widget.split() == pytest.approx(0.5)

    def test_set_split_clamps_below_zero(self, ops, qapp):
        widget = ops._SplitLabel()
        widget.set_split(-0.5)
        assert widget.split() == pytest.approx(0.0)

    def test_set_split_clamps_above_one(self, ops, qapp):
        widget = ops._SplitLabel()
        widget.set_split(2.0)
        assert widget.split() == pytest.approx(1.0)

    def test_set_split_updates_value(self, ops, qapp):
        widget = ops._SplitLabel()
        widget.set_split(0.75)
        assert widget.split() == pytest.approx(0.75)

    def test_split_changed_emits_on_change(self, ops, qapp):
        widget = ops._SplitLabel()
        seen: list[float] = []
        widget.split_changed.connect(seen.append)
        widget.set_split(0.3)
        assert seen == [0.3]

    def test_split_changed_silent_on_noop(self, ops, qapp):
        widget = ops._SplitLabel()
        widget.set_split(0.4)
        seen: list[float] = []
        widget.split_changed.connect(seen.append)
        widget.set_split(0.4)
        assert seen == []
